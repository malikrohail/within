"""Borrower-side auto-repay sweeper.

Runs with the BORROWER wallet from lending/.env (never the broker key). Every --interval seconds it reads the
borrower's account_tx forward from the last seen ledger; each new x402 income adds its delivered drops to
unspentIncomeDrops, and it pays one installment (LoanPay for periodicPaymentDrops) on each due loan of this borrower
only while unspentIncomeDrops covers it and the balance after the installment and its fee stays >= reserve + 2 XRP.
The trigger is money, not a memo: a 1-drop memo'd payment never pays a 3.33 XRP installment.
One sweeper per state file (flock on data/sweeper_state.lock; a second one exits 3). The state names its borrower;
after a rotation it resets and pins the cursor at the tip again.
Each payment is appended to data/sweeps.jsonl and POSTed to the desk at POST /v1/loans/{loanId}/sweeps; the desk
only observes (a desk error is logged and retried next sweep, never fatal).

The x402 classifier is local (evidence.py has none yet): inbound validated tesSUCCESS XRP Payment, not from the
borrower / faucet / account creator, with a Memo whose MemoType is hex("invoice") or hex("x402") and whose
MemoData hex-decodes to a JSON object.

CLI: python sweeper.py [--once] [--interval 10] [--desk http://127.0.0.1:7500]
"""
from __future__ import annotations

import argparse
import fcntl
import json
import sys
import time
from pathlib import Path
from typing import Protocol

import requests

import common

DESK_URL = "http://127.0.0.1:7500"
STATE_PATH = common.LENDING_DIR / "data" / "sweeper_state.json"
SWEEPS_PATH = common.LENDING_DIR / "data" / "sweeps.jsonl"
MARGIN_DROPS = 2_000_000  # never pay below reserve + 2 XRP
MAX_LEDGER_ERRORS = 3
FALLBACK_FEE_DROPS = 12
POST_TIMEOUT_S = 4
EXIT_LOCKED = 3
FAUCET_ACCOUNTS = frozenset({"rht5xsioM3iix1hx4i2zJX2WJ1JDTwLGJe"})  # same as evidence.py
INCOME_MEMO_TYPES = frozenset({"invoice".encode().hex().upper(), "x402".encode().hex().upper()})


class LedgerError(RuntimeError):
    pass


# ---- classifier ---------------------------------------------------------------
def _created_account(meta: dict, account: str) -> bool:
    for n in meta.get("AffectedNodes", []):
        c = n.get("CreatedNode")
        if c and c.get("LedgerEntryType") == "AccountRoot" and c.get("NewFields", {}).get("Account") == account:
            return True
    return False


def _has_income_memo(tx: dict) -> bool:
    for m in tx.get("Memos") or []:
        memo = m.get("Memo", {})
        if (memo.get("MemoType") or "").upper() not in INCOME_MEMO_TYPES:
            continue
        try:
            if isinstance(json.loads(bytes.fromhex(memo.get("MemoData", "")).decode()), dict):
                return True
        except (ValueError, TypeError):
            continue
    return False


def x402_income(entry: dict, borrower: str) -> dict | None:
    """{hash, drops, payer, ledgerIndex} if this account_tx entry is x402 income to borrower, else None."""
    tx = entry.get("tx_json") or entry.get("tx") or {}
    meta = entry.get("meta") or entry.get("metaData") or {}
    if tx.get("TransactionType") != "Payment" or tx.get("Destination") != borrower:
        return None
    if entry.get("validated") is False or meta.get("TransactionResult") != "tesSUCCESS":
        return None
    sender = tx.get("Account")
    if sender == borrower or sender in FAUCET_ACCOUNTS or _created_account(meta, borrower):
        return None
    amt = meta.get("delivered_amount", tx.get("DeliverMax", tx.get("Amount")))
    if not isinstance(amt, str) or not amt.isdigit() or not _has_income_memo(tx):  # skips "unavailable" too
        return None
    return {"hash": entry.get("hash") or tx.get("hash"), "drops": int(amt), "payer": sender,
            "ledgerIndex": entry.get("ledger_index") or tx.get("ledger_index")}


# ---- ledger -------------------------------------------------------------------
class Ledger(Protocol):
    borrower: str

    def account_tx(self, since_ledger: int) -> tuple[list[dict], int]: ...  # (entries oldest first, latest validated)

    def loans_of(self) -> list[dict]: ...  # common.loan_item shape

    def balance_and_reserve(self) -> tuple[int, int]: ...  # (balance drops, base + owner reserve drops)

    def fee_drops(self) -> int: ...  # network fee a LoanPay will pay

    def loan_pay(self, loan_id: str, drops: int) -> dict: ...  # {hash, engineResult, validated, ledgerIndex}


class XrplLedger:
    """Devnet implementation over common.py. Holds the borrower wallet only."""

    def __init__(self, w):
        self._w = w
        self.borrower = w.address

    def current(self) -> int:
        return common.current_ledger_index()

    def account_tx(self, since_ledger: int) -> tuple[list[dict], int]:
        from xrpl.models.requests import AccountTx
        cur = common.current_ledger_index()
        if since_ledger >= cur:
            return [], cur
        out, marker = [], None
        while True:
            kw = {"account": self.borrower, "ledger_index_min": since_ledger + 1, "ledger_index_max": cur,
                  "forward": True, "limit": 200, "api_version": 2, **({"marker": marker} if marker else {})}
            res = common._rpc(AccountTx(**kw))
            if "error" in res:
                raise LedgerError(f"account_tx: {res.get('error')}")
            out.extend(res.get("transactions", []))
            marker = res.get("marker")
            if not marker:
                return out, cur

    def loans_of(self) -> list[dict]:
        return [common.loan_item(o) for o in common.account_objects(self.borrower, "loan")
                if o.get("Borrower") == self.borrower]

    def balance_and_reserve(self) -> tuple[int, int]:
        from xrpl.models.requests import AccountInfo, ServerState
        info = common._rpc(AccountInfo(account=self.borrower, ledger_index="validated"))
        if "account_data" not in info:
            raise LedgerError(f"account_info: {info.get('error')}")
        vl = common._rpc(ServerState())["state"]["validated_ledger"]
        owner = int(info["account_data"].get("OwnerCount", 0))
        return int(info["account_data"]["Balance"]), int(vl["reserve_base"]) + owner * int(vl["reserve_inc"])

    def fee_drops(self) -> int:
        from xrpl.models.requests import Fee
        try:
            return int(common._rpc(Fee())["drops"]["open_ledger_fee"])
        except Exception:  # noqa: BLE001 - the floor check falls back to the base fee
            return FALLBACK_FEE_DROPS

    def loan_pay(self, loan_id: str, drops: int) -> dict:
        return common.loan_pay(self._w, loan_id, str(drops))


# ---- desk ---------------------------------------------------------------------
class HttpDesk:
    def __init__(self, url: str = DESK_URL):
        self.url = url.rstrip("/")

    def post_sweep(self, record: dict) -> None:
        r = requests.post(f"{self.url}/v1/loans/{record['loanId']}/sweeps", json=record, timeout=POST_TIMEOUT_S)
        r.raise_for_status()


# ---- state --------------------------------------------------------------------
def load_state(path: Path) -> dict:
    try:
        s = json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        s = {}
    return {"borrower": s.get("borrower"), "cursor": s.get("cursor"), "seen": s.get("seen", {}),
            "done": s.get("done", []), "unspentIncomeDrops": int(s.get("unspentIncomeDrops", 0)),
            "pendingPosts": s.get("pendingPosts", [])}


def lock_path(state_path: Path) -> Path:
    return Path(state_path).with_suffix(".lock")


def acquire_lock(state_path: Path):
    """Exclusive non-blocking flock next to the state file; the open file (keep it alive) or None if held."""
    p = lock_path(state_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    f = p.open("a")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    return f


def save_state(path: Path, state: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    tmp.replace(path)


def _xrp(drops: int) -> str:
    return f"{int(drops) / 1_000_000:.3f}"


def _flush_posts(state: dict, desk) -> None:
    left = []
    for rec in state["pendingPosts"]:
        try:
            desk.post_sweep(rec)
            print(f"desk: recorded sweep {rec['loanPayHash']} on loan {rec['loanId'][:8]}…")
        except Exception as e:  # noqa: BLE001 - desk down / route missing is never fatal
            print(f"desk: POST /v1/loans/{rec['loanId'][:8]}…/sweeps failed ({e}); retry next sweep")
            left.append(rec)
    state["pendingPosts"] = left


def sweep_once(state: dict, ledger: Ledger, desk, now: int, sweeps_path: Path = SWEEPS_PATH,
               persist=lambda: None) -> list[dict]:
    """One sweep. Mutates state; returns the records written. Ledger failures raise (the caller counts them).
    persist() writes state to disk; it is called before every LoanPay submit so a hard kill mid-submit can
    never re-pay the same loan for the same income after a restart (rule 4)."""
    if state["cursor"] is not None and state["borrower"] != ledger.borrower:  # rotation: old cursor is meaningless
        print(f"sweeper: borrower changed {state['borrower']} -> {ledger.borrower}; state reset", flush=True)
        state.update(cursor=None, seen={}, done=[], unspentIncomeDrops=0)
    if state["cursor"] is None:  # first run: start at the tip, never pay from historical income
        state["cursor"] = ledger.account_tx(1 << 62)[1]
        state["borrower"] = ledger.borrower
        print(f"sweeper: cursor pinned at ledger {state['cursor']}; earlier income is ignored", flush=True)
        _flush_posts(state, desk)
        return []
    entries, latest = ledger.account_tx(int(state["cursor"]))
    incomes = [i for i in (x402_income(e, ledger.borrower) for e in entries)
               if i and i["hash"] and i["hash"] not in state["done"]]
    records, paid_this_sweep = [], set()
    for inc in incomes:
        if inc["hash"] not in state["seen"]:  # credit each income's money exactly once, even across restarts
            state["unspentIncomeDrops"] += inc["drops"]
        done = state["seen"].setdefault(inc["hash"], {})
        loans = [ln for ln in ledger.loans_of()
                 if ln["status"] != "defaulted" and ln["paymentRemaining"] > 0
                 and ln["nextPaymentDue"] <= now + common.PAYMENT_INTERVAL]
        head = f"income {_xrp(inc['drops'])} XRP from {inc['payer'][:8]}… ({inc['hash']})"
        if not loans:
            print(f"{head} -> no installment due")
        for ln in loans:
            loan_id = ln["loanId"]
            if loan_id in done or loan_id in paid_this_sweep:
                continue  # rule 1 (one per loan per sweep) and rule 4 (one per loan per income)
            drops = int(ln["periodicPaymentDrops"])
            if state["unspentIncomeDrops"] < drops:  # P3/P4: never pay more than the income received
                print(f"{head} -> loan {loan_id[:8]}… not paid: unspent income {_xrp(state['unspentIncomeDrops'])} "
                      f"XRP < installment {_xrp(drops)} XRP")
                continue
            balance, reserve = ledger.balance_and_reserve()
            fee = ledger.fee_drops()
            if balance - drops - fee < reserve + MARGIN_DROPS:
                print(f"{head} -> loan {loan_id[:8]}… skipped: balance below reserve + 2 XRP "
                      f"(balance {_xrp(balance)}, reserve {_xrp(reserve)}, installment {_xrp(drops)}, fee {fee} drops)")
                done[loan_id] = "skipped:balance"
                continue
            done[loan_id] = "submitting"  # an ambiguous submit failure must never re-pay this loan for this income
            state["unspentIncomeDrops"] -= drops  # spent at submit: an ambiguous submit counts as paid
            paid_this_sweep.add(loan_id)
            persist()  # the marker must be on disk before the submit, not only at the end of the sweep
            res = ledger.loan_pay(loan_id, drops)
            done[loan_id] = res["hash"]  # never re-paid, whatever the result (P5: a tec is recorded as failed)
            ok = res["engineResult"] == "tesSUCCESS" and res.get("validated", True)
            print(f"{head} -> LoanPay {_xrp(drops)} XRP on loan {loan_id[:8]}… "
                  f"{res['engineResult'] if ok else 'FAILED ' + str(res['engineResult'])} {res['hash']}; "
                  f"unspent income {_xrp(state['unspentIncomeDrops'])} XRP")
            rec = {"incomeHash": inc["hash"], "incomeDrops": str(inc["drops"]), "payer": inc["payer"],
                   "loanId": loan_id, "loanPayHash": res["hash"], "drops": str(drops),
                   "engineResult": res["engineResult"], "ledgerIndex": res.get("ledgerIndex"), "at": int(now)}
            Path(sweeps_path).parent.mkdir(parents=True, exist_ok=True)
            with Path(sweeps_path).open("a") as f:
                f.write(json.dumps(rec) + "\n")
            records.append(rec)
            if res.get("validated", True):  # an unvalidated LoanPay can never verify on the desk: do not POST it
                state["pendingPosts"].append(rec)
            persist()
        state["done"].append(inc["hash"])  # complete only once every due loan was handled
    state["cursor"] = max(int(state["cursor"]), int(latest))
    _flush_posts(state, desk)
    return records


def run(ledger: Ledger, desk, state_path: Path = STATE_PATH, sweeps_path: Path = SWEEPS_PATH,
        interval: float = 10, once: bool = False, sleep=time.sleep, now=time.time,
        max_sweeps: int | None = None) -> int:
    """Sweep loop. Returns the exit code: 0 on a clean --once / max_sweeps, 2 after 3 consecutive ledger errors
    (1 for a ledger error under --once), 3 when another sweeper holds the lock on this state file."""
    lock = acquire_lock(state_path)
    if lock is None:
        print("sweeper: another sweeper holds the lock", flush=True)
        return EXIT_LOCKED
    try:
        return _loop(ledger, desk, state_path, sweeps_path, interval, once, sleep, now, max_sweeps)
    finally:
        lock.close()


def _loop(ledger, desk, state_path, sweeps_path, interval, once, sleep, now, max_sweeps) -> int:
    errors, sweeps, announced = 0, 0, False
    while True:
        state = load_state(state_path)
        try:
            sweep_once(state, ledger, desk, int(now()), sweeps_path, persist=lambda: save_state(state_path, state))
            errors = 0
            if not announced:  # every start, after its first good sweep: the operator waits for this line
                print(f"sweeper: watching {ledger.borrower} from ledger {state['cursor']}", flush=True)
                announced = True
        except Exception as e:  # noqa: BLE001 - every ledger/submit failure counts toward the stop rule
            errors += 1
            print(f"sweeper: ledger error {errors}/{MAX_LEDGER_ERRORS}: {type(e).__name__}: {e}")
            if once:
                return 1
            if errors >= MAX_LEDGER_ERRORS:
                print(f"sweeper: stopped after {MAX_LEDGER_ERRORS} consecutive ledger errors; last: {e}")
                return 2
        finally:
            save_state(state_path, state)
        sweeps += 1
        if once or (max_sweeps is not None and sweeps >= max_sweeps):
            return 0
        sleep(interval)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Auto-repay loans from x402 income (borrower key only).")
    ap.add_argument("--once", action="store_true", help="run one sweep and exit")
    ap.add_argument("--interval", type=float, default=10, help="seconds between sweeps (default 10)")
    ap.add_argument("--desk", default=DESK_URL, help=f"desk URL (default {DESK_URL})")
    args = ap.parse_args(argv)
    w = common.wallet("borrower")
    print(f"sweeper: borrower {w.address}, desk {args.desk}, interval {args.interval}s")
    return run(XrplLedger(w), HttpDesk(args.desk), interval=args.interval, once=args.once)


if __name__ == "__main__":
    sys.exit(main())
