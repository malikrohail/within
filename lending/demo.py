"""Scripted Lending Desk demo on XRPL devnet (INTERFACES.md §6).

  cd lending && .venv/bin/python -m desk &        # :7500 must be up
  .venv/bin/python demo.py --scripted

Preflight: desk /health; rotate the borrower when its evidence shows activeLoans>0 or pastDefaults>0;
faucet top-ups for the depositors; `setup.py --new-vault --subscription-seconds 120` (close-ended vault:
deposits only before SubscriptionDate, loans only after it). Then 9 steps, one line each:
"step N OK <what> <hash>" or "step N FAIL <why>". Exit 0 iff 9/9. A step whose desk record is left held is
approved with the operator token (approver gate off) or waited out, and no step may get an earlier record back.
Last, not scored: `setup.py --rotate-borrower` ("post: rotated borrower -> r…") so the stage borrower is clean.

  .venv/bin/python demo.py --income 5   # autorepay scene
One customer Payment with an invoice memo to the current borrower; the borrower's sweeper (already running and
past its 'watching' line) pays the due installment from it; the LoanPay hash is printed when the desk has it.
Steps 8-9 (working capital, INTERFACES §8) run inside step 7's grace wait, before loan 4 is defaulted
(a past default caps the borrower's score), so the run order is 1-6, 8, 9, 7.
All waits use the validated ledger's close time, not the local clock.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from xrpl.account import get_next_valid_seq_number
from xrpl.core.binarycodec import decode
from xrpl.models.requests import AccountInfo, Ledger
from xrpl.models.transactions import Payment, VaultDeposit

import borrower as B
import common as C
import llm
from batch import working_capital as wc

HERE = Path(__file__).resolve().parent
PY = sys.executable
XRP = 1_000_000
TOTAL_STEPS = 9
RUN_ORDER = (3, 4, 5, 6, 8, 9, 7)  # 8-9 before the default in 7 (INTERFACES §8)
SUBSCRIPTION_SECONDS = 120
TERM_SECONDS = 270
DEPOSITS = {1: ("depositorA", 100 * XRP), 2: ("depositorB", 50 * XRP)}
# Balance floors before setup's bootstrap deposits (20 / 10 XRP) + the demo deposits + reserve margin.
TOPUP_FLOOR_XRP = {"depositorA": 150, "depositorB": 90}
# (principal, existingDebt) per INTERFACES §4 fixtures GOOD_SMALL / GOOD_LARGE / BAD.
STEP3 = (str(10 * XRP), str(5 * XRP))
STEP4 = (str(60 * XRP), str(15 * XRP))
STEP5 = (str(10 * XRP), str(30 * XRP))
# Working capital (§8): 60 XRP principal, 55 XRP to a supplier + 1 XRP broker fee. Declared debt = loans 3 + 4.
STEP8 = {"principal": str(60 * XRP), "debt": str(70 * XRP), "supplier": str(55 * XRP), "fee": str(1 * XRP)}
STEP9A_SUPPLIER = str(70 * XRP)          # supplier 70 + fee 1 > principal 60 -> desk refuses batch_unfunded
DRILL_OVER_BALANCE = 10 * XRP            # 9b supplier leg = borrower balance + 10 XRP -> cannot apply
DEFAULT_MARGIN_S = 5
STAGE_DRAW_XRP = 30                      # live held draw on stage: stock vault headroom is ~38 XRP, so not 60
SCRIPTED_BANNER = ("scripted run: start the desk with DESK_APPROVER_ACCOUNT=off SECOND_OPINION=off "
                   ".venv/bin/python -m desk")
EXAMPLES_PATH = HERE / "data" / "desk_examples.jsonl"
HOLD_WAIT_S = 120 + 60                   # policy holdTimeoutSeconds + margin: a held record expires by then


class StepFail(Exception):
    pass


# ---- bookkeeping (pure, tested offline) ------------------------------------------
class Steps:
    def __init__(self, total: int = TOTAL_STEPS, out=print):
        self.total, self.out, self.results = total, out, {}

    def ok(self, n: int, what: str, *hashes: str) -> None:
        self.results[n] = True
        self.out(" ".join(["step", str(n), "OK", what, *[h for h in hashes if h]]))

    def fail(self, n: int, why: str) -> None:
        self.results[n] = False
        self.out(f"step {n} FAIL {why}")

    def run(self, n: int, fn) -> bool:
        """fn() -> (what, [hashes]); StepFail or any exception marks the step FAIL."""
        try:
            what, hashes = fn()
        except StepFail as e:
            self.fail(n, str(e))
        except Exception as e:  # noqa: BLE001 - a crash in one step is a FAIL line, not a traceback
            self.fail(n, f"{type(e).__name__}: {e}")
        else:
            self.ok(n, what, *hashes)
        return self.results[n]

    def passed(self) -> int:
        return sum(1 for v in self.results.values() if v)

    def exit_code(self) -> int:
        return 0 if all(self.results.get(n) for n in range(1, self.total + 1)) else 1


def needs_rotation(ev: dict) -> bool:
    led = ev.get("ledger") or {}
    return int(led.get("activeLoans", 0)) > 0 or int(led.get("pastDefaults", 0)) > 0


def default_allowed_at(loan: dict, margin: int = DEFAULT_MARGIN_S) -> int:
    return int(loan["nextPaymentDue"]) + int(loan.get("gracePeriod") or C.GRACE_PERIOD) + margin


def find_loan(loans: list[dict], loan_id: str) -> dict | None:
    return next((x for x in loans if x["loanId"].upper() == loan_id.upper()), None)


def need(cond: bool, why: str) -> None:
    if not cond:
        raise StepFail(why)


def evidence_tx_args(hashes: list[tuple[str, str]]) -> list[str]:
    out = []
    for label, h in hashes:
        out += ["--tx", f"{label}={h}"]
    return out


def drill_lines(names: dict, before: dict, after: dict, fee: int) -> list[str]:
    """Step 9b balance proof. names = {"borrower": addr, "supplier": addr, "broker": addr}; before/after map
    role -> validated balance in drops. Supplier and broker must be unchanged and the borrower must be down by
    exactly the outer Batch Fee; otherwise StepFail."""
    lines = []
    for role in ("borrower", "supplier", "broker"):
        b, a = int(before[role]), int(after[role])
        head = f"{role} {names[role]} balance {b} -> {a} drops:"
        if role == "borrower":
            need(b - a == fee, f"borrower delta {b - a} drops != Batch Fee {fee} drops")
            lines.append(f"{head} unchanged apart from the {fee}-drop Batch network fee")
        else:
            need(a == b, f"{role} balance changed {b} -> {a}")
            lines.append(f"{head} unchanged")
    return lines


def drill_payments(borrower: str, supplier: str, broker: str, supplier_drops: int, fee_drops: int,
                   sequence: int, invoice: str, date: str) -> list[Payment]:
    """Inner Payments of the 9b drill Batch at Sequence `sequence` (inners sequence+1, +2), shaped as in
    batch/working_capital.py: tfInnerBatchTxn, Fee 0, no SigningPubKey."""
    import setup as S
    inner = dict(account=borrower, flags=wc.INNER, fee="0", signing_pub_key="")
    return [Payment(**inner, destination=supplier, amount=str(supplier_drops), sequence=sequence + 1,
                    memos=[S.invoice_memo(invoice, date)]),
            Payment(**inner, destination=broker, amount=str(fee_drops), sequence=sequence + 2)]


# ---- ledger / desk I/O -------------------------------------------------------------
def retry(fn, tries: int = 5, pause: float = 3.0):
    for i in range(tries):
        try:
            return fn()
        except Exception:  # noqa: BLE001 - transient devnet/desk errors
            if i == tries - 1:
                raise
            time.sleep(pause)


def ledger_close_unix() -> int:
    res = retry(lambda: C._rpc(Ledger(ledger_index="validated")))
    return C.from_ripple(res["ledger"]["close_time"])


def countdown(target_unix: int, fmt: str, now_fn=ledger_close_unix, sleep=time.sleep, tick: int = 10,
              out=print) -> None:
    while True:
        left = target_unix - now_fn()
        if left <= 0:
            return
        out(fmt.format(left))
        sys.stdout.flush()
        sleep(min(tick, left))


def desk_post(path: str, body: dict) -> dict:
    # approve and manage are operator routes: X-Desk-Token from the shell or lending/.env (never printed)
    token = os.environ.get("DESK_TOKEN") or C.read_env().get("DESK_TOKEN")
    headers = {"X-Desk-Token": token} if token else {}
    r = requests.post(B.DESK_URL + path, json=body, headers=headers,
                      timeout=B.POST_TIMEOUT_S)  # approve = co-sign + Batch, two waits
    if r.status_code != 200:
        raise StepFail(f"desk {r.status_code} {path}: {r.text[:200]}")
    return r.json()


def get_loans(record: bool = False) -> list[dict]:
    body = retry(lambda: B.desk_get("/v1/loans"))
    if record:
        EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with EXAMPLES_PATH.open("a") as f:
            f.write(json.dumps({"ts": int(time.time()), "label": "loans", "method": "GET", "path": "/v1/loans",
                                "request": None, "status": 200, "response": body}) + "\n")
    return body["loans"]


def balance_at(address: str, ledger_index) -> int:
    res = retry(lambda: C._rpc(AccountInfo(account=address, ledger_index=ledger_index)))
    need("account_data" in res, f"account_info {address} @ {ledger_index}: {res.get('error')}")
    return int(res["account_data"]["Balance"])


def info(msg: str) -> None:
    print(f"  {msg}", flush=True)


def run_setup(*args: str, run=subprocess.run) -> tuple[int, list[str]]:
    info(f"setup.py {' '.join(args)}")
    p = run([PY, "setup.py", *args], cwd=HERE, capture_output=True, text=True)
    lines = (p.stdout + p.stderr).splitlines()
    for line in lines:
        info(f"  | {line}")
    if p.returncode != 0 and "FAILED" in p.stderr + p.stdout:
        raise StepFail(f"setup.py {' '.join(args)} exited {p.returncode}")
    if p.returncode != 0:
        info("setup.py score gate not exact; the demo asserts decisions, continuing")
    return p.returncode, lines


def post_rotate(run=run_setup, load=C.load_accounts, out=print) -> None:
    """After the scored steps and EVIDENCE.md: give the stage a clean borrower (loan 4's default caps the old
    one's score at 35). Same path as `setup.py --rotate-borrower`. Not a scored step: the run stays 9/9."""
    try:
        _, lines = run("--rotate-borrower")
    except Exception as e:  # noqa: BLE001 - stage hygiene; report it, the 9 steps are already decided
        out(f"post: rotate borrower FAIL {type(e).__name__}: {e} (run setup.py --rotate-borrower before the stage)")
        return
    gate = next((x.strip() for x in lines if x.startswith("score gate")), "score gate line missing from setup.py")
    out(f"post: rotated borrower -> {load()['accounts']['borrower']}")
    out(f"post: {gate}")
    out(f"post: stage live held draw = {STAGE_DRAW_XRP} XRP (borrower_agent.py default goal)")


def settle(rec: dict, seen: set, gate_off: bool, out=info, post=None, wait=None) -> dict:
    """Every desk record a step gets back must be new: the desk is idempotent on (Account, Sequence), so a
    request left held makes the borrower's next blob replay it. A non-terminal record is driven to a terminal
    state before the step ends: with the approver gate off (scripted run) it is approved through the operator
    route (token from the shell or lending/.env, never printed); otherwise the hold is waited out."""
    post, wait = post or desk_post, wait or B.wait_for
    rid = rec["id"]
    need(rid not in seen, f"desk returned the earlier record {rid} ({rec['status']}) again: same Account+Sequence")
    seen.add(rid)
    if rec["status"] in B.FINAL_STATUSES:
        return rec
    if gate_off:
        out(f"{rid} {rec['status']} ({rec.get('reason')}): scripted run, approver gate off -> approving it "
            "through POST /approve with the operator token")
        try:
            post(f"/v1/loan-requests/{rid}/approve", {})
        except StepFail as e:
            out(f"approve {rid} failed ({e}); waiting for a terminal state")
    return wait(rid, statuses=B.FINAL_STATUSES, timeout=HOLD_WAIT_S)


def archive_data_logs() -> None:
    """EVIDENCE.md should show this run's vault: move the previous raw logs aside (never delete)."""
    stamp = int(time.time())
    arch = HERE / "data" / "archive"
    for p in (C.RAWLOG_PATH, EXAMPLES_PATH):
        if p.exists():
            arch.mkdir(parents=True, exist_ok=True)
            p.rename(arch / f"{p.stem}.{stamp}{p.suffix}")


# ---- preflight -----------------------------------------------------------------------
def preflight() -> tuple[dict, bool]:
    import evidence
    import policy
    import setup as S

    health = retry(lambda: B.desk_get("/health"))
    need(health.get("ok") is True, f"desk /health: {health}")
    info(f"desk {B.DESK_URL} ok, broker {health['broker']}, ledger {health['ledgerIndex']}")
    gate_off = not health.get("approverAccount")
    info(f"approver gate {'OFF' if gate_off else 'ON'}")
    archive_data_logs()

    acc = C.load_accounts()
    who = acc["accounts"]["borrower"]
    ev = retry(lambda: evidence.build_evidence(who, policy.GOOD_SMALL["declared"]))
    led = ev["ledger"]
    info(f"borrower {who}: activeLoans={led['activeLoans']} pastDefaults={led['pastDefaults']}")
    if needs_rotation(ev):
        run_setup("--rotate-borrower")  # before --new-vault: history seeding must not eat the deposit window
        info(f"borrower rotated -> {C.load_accounts()['accounts']['borrower']}")

    for name, floor in TOPUP_FLOOR_XRP.items():
        w = C.wallet(name)
        for _ in range(6):
            bal = S.balance_drops(w.address)
            if bal >= floor * XRP:
                break
            S.faucet(w)
        info(f"{name} {w.address} balance {S.balance_drops(w.address) / XRP:.2f} XRP (floor {floor})")

    run_setup("--new-vault", "--subscription-seconds", str(SUBSCRIPTION_SECONDS))
    acc = C.load_accounts()
    left = acc["subscriptionDate"] - ledger_close_unix()
    info(f"vault {acc['vaultId']} loanBroker {acc['loanBrokerId']}; deposit window {left}s left")
    need(left > 15, f"deposit window already closing ({left}s left)")
    return acc, gate_off


# ---- steps -------------------------------------------------------------------------------
def main_scripted() -> int:
    print(SCRIPTED_BANNER, flush=True)
    steps = Steps()
    tx: list[tuple[str, str]] = []
    ctx: dict = {}
    seen: set[str] = set()  # desk record ids already returned this run
    try:
        acc, gate_off = preflight()
    except Exception as e:  # noqa: BLE001
        print(f"preflight FAIL {type(e).__name__}: {e}", flush=True)
        for n in range(1, TOTAL_STEPS + 1):
            steps.fail(n, "preflight failed")
        return steps.exit_code()

    def deposit(n: int):
        name, drops = DEPOSITS[n]
        w = C.wallet(name)
        res = C.submit_and_wait(VaultDeposit(account=w.address, vault_id=acc["vaultId"], amount=str(drops)), w)
        need(res["engineResult"] == "tesSUCCESS" and res["validated"],
             f"VaultDeposit {name} {res['engineResult']} {res['hash']}")
        tx.append((f"demo step {n} VaultDeposit {name} {drops // XRP} XRP", res["hash"]))
        return f"VaultDeposit {name} {drops // XRP} XRP", [res["hash"]]

    steps.run(1, lambda: deposit(1))
    steps.run(2, lambda: deposit(2))

    sub = int(C.load_accounts()["subscriptionDate"])
    countdown(sub + 1, "lending opens in {}s")
    while int(time.time()) < sub + 1:  # the desk's phase check uses local time
        time.sleep(1)
    print("lending is open (validated ledger close time >= SubscriptionDate)", flush=True)

    def step3():
        p, debt = STEP3
        rec = B.request_loan(p, TERM_SECONDS, "inventory", debt)
        if rec["status"] == "failed" and rec.get("engineResult") == "tecTOO_SOON":
            info("tecTOO_SOON at the window edge; retrying once in 5 s")
            time.sleep(5)
            rec = B.request_loan(p, TERM_SECONDS, "inventory", debt)
        info(f"request {rec['id']} score={rec['score']} decision={rec['decision']} status={rec['status']}")
        held = rec["status"] not in B.FINAL_STATUSES
        rec = settle(rec, seen, gate_off)
        if held and rec["status"] == "approved" and rec["loanId"]:
            ctx["loan3"] = rec["loanId"]  # step 6 can still pay it; step 3 itself still FAILs (expected auto)
        need(rec["decision"] == "auto" and rec["status"] == "auto" and rec["txHash"] and rec["loanId"],
             f"expected auto, got {rec['status']} reason={rec['reason']} tx={rec['txHash']}")
        loan = find_loan(get_loans(record=True), rec["loanId"])
        need(loan is not None, f"loan {rec['loanId']} not in GET /v1/loans")
        ctx["loan3"] = rec["loanId"]
        tx.append(("demo step 3 LoanSet auto 10 XRP (co-signed)", rec["txHash"]))
        return (f"auto score={rec['score']} LoanSet loan={rec['loanId']} visible in /v1/loans "
                f"paymentRemaining={loan['paymentRemaining']}"), [rec["txHash"]]

    def step4():
        p, debt = STEP4
        rec = B.request_loan(p, TERM_SECONDS, "inventory", debt)
        info(f"request {rec['id']} score={rec['score']} decision={rec['decision']} "
             f"status={rec['status']} reason={rec['reason']}")
        need(rec["id"] not in seen, f"desk returned the earlier record {rec['id']} ({rec['status']}) again")
        if rec["decision"] != "hold" or rec["status"] != "held":
            settle(rec, seen, gate_off)
            raise StepFail(f"expected held, got {rec['status']}")
        try:
            out = desk_post(f"/v1/loan-requests/{rec['id']}/approve", {})
        finally:
            settle(B.desk_get(f"/v1/loan-requests/{rec['id']}"), seen, gate_off)
        final = B.wait_for(rec["id"], timeout=30)
        need(out["status"] == "approved" and final["status"] == "approved" and out["txHash"] and out["loanId"],
             f"approve -> {out['status']} reason={out['reason']} tx={out['txHash']}")
        ctx["loan4"] = out["loanId"]
        tx.append(("demo step 4 LoanSet held 60 XRP, approved by POST /approve", out["txHash"]))
        return f"hold({rec['reason']}) -> approved loan={out['loanId']}", [out["txHash"]]

    def step5():
        import setup as S
        fresh = S.faucet()  # seed stays in memory
        info(f"fresh borrower {fresh.address} (in-memory seed)")
        p, debt = STEP5
        rec = settle(B.request_loan(p, TERM_SECONDS, "inventory", debt, wallet=fresh), seen, gate_off)
        need(rec["status"] == "refused" and rec["reason"] == "score_too_low" and rec["txHash"] is None,
             f"expected refused score_too_low, got {rec['status']} {rec['reason']} tx={rec['txHash']}")
        return f"refused score_too_low score={rec['score']} no tx", []

    def step6():
        need("loan3" in ctx, "skipped (needs loan 3)")
        before = find_loan(get_loans(), ctx["loan3"])
        res = B.pay_installment(ctx["loan3"])
        if res["engineResult"] != "tesSUCCESS":
            info(f"LoanPay {res['engineResult']} {res['hash']}; retrying once after nextPaymentDue")
            countdown(before["nextPaymentDue"], "loan 3 payment due in {}s")
            res = B.pay_installment(ctx["loan3"])
        need(res["engineResult"] == "tesSUCCESS" and res["validated"], f"LoanPay {res['engineResult']} {res['hash']}")
        after = find_loan(get_loans(), ctx["loan3"])
        need(after is not None and after["paymentRemaining"] < before["paymentRemaining"],
             f"paymentRemaining {before['paymentRemaining']} -> {after and after['paymentRemaining']}")
        tx.append(("demo step 6 LoanPay first installment of loan 3", res["hash"]))
        return (f"LoanPay {before['periodicPaymentDrops']} drops tesSUCCESS paymentRemaining "
                f"{before['paymentRemaining']}->{after['paymentRemaining']}"), [res["hash"]]

    def step7():
        need("loan4" in ctx, "skipped (needs loan 4)")
        loan = find_loan(get_loans(), ctx["loan4"])
        countdown(default_allowed_at(loan), "loan 4 missed its payment; default allowed in {}s")
        cover_before = retry(lambda: B.desk_get("/v1/vault"))
        hashes = []
        res = desk_post(f"/v1/loans/{ctx['loan4']}/manage", {"action": "default"})
        hashes.append(res["hash"])
        tx.append((f"demo step 7 LoanManage default ({res['engineResult']})", res["hash"]))
        if res["engineResult"] != "tesSUCCESS":
            info(f"default -> {res['engineResult']} {res['hash']}; impair first, then default")
            imp = desk_post(f"/v1/loans/{ctx['loan4']}/manage", {"action": "impair"})
            hashes.append(imp["hash"])
            tx.append((f"demo step 7 LoanManage impair ({imp['engineResult']})", imp["hash"]))
            need(imp["engineResult"] == "tesSUCCESS", f"impair {imp['engineResult']} {imp['hash']}")
            res = desk_post(f"/v1/loans/{ctx['loan4']}/manage", {"action": "default"})
            hashes.append(res["hash"])
            tx.append((f"demo step 7 LoanManage default after impair ({res['engineResult']})", res["hash"]))
        need(res["engineResult"] == "tesSUCCESS", f"default {res['engineResult']} {res['hash']}")
        after = find_loan(get_loans(record=True), ctx["loan4"])
        need(after is not None and after["status"] == "defaulted", f"loan 4 status {after and after['status']}")
        cover_after = retry(lambda: B.desk_get("/v1/vault"))
        info(f"LoanBroker CoverAvailable {cover_before['coverDrops']} -> {cover_after['coverDrops']} drops; "
             f"vault AssetsTotal {cover_before['assetsTotalDrops']} -> {cover_after['assetsTotalDrops']}; "
             f"lossUnrealized {cover_before['lossUnrealizedDrops']} -> {cover_after['lossUnrealizedDrops']}")
        return (f"loan 4 defaulted cover {cover_before['coverDrops']}->{cover_after['coverDrops']} drops"), hashes

    def step8():
        import setup as S
        supplier = S.faucet()  # seed stays in memory; never print the Wallet object
        ctx["supplier"] = supplier.address
        info(f"fresh supplier {supplier.address} (in-memory seed)")
        invoice = f"INV-WC-{int(time.time())}"
        dis = {"supplier": supplier.address, "supplierDrops": STEP8["supplier"], "feeDrops": STEP8["fee"],
               "invoice": invoice}
        rec = B.request_working_capital(STEP8["principal"], TERM_SECONDS, "inventory", STEP8["debt"], dis)
        info(f"request {rec['id']} kind={rec.get('kind')} score={rec['score']} decision={rec['decision']} "
             f"status={rec['status']} reason={rec['reason']}")
        need(rec["id"] not in seen, f"desk returned the earlier record {rec['id']} ({rec['status']}) again")
        if rec.get("kind") != "working_capital" or rec["status"] != "held":
            settle(rec, seen, gate_off)
            raise StepFail(f"expected held working_capital, got {rec.get('kind')} {rec['status']} {rec['reason']}")
        try:
            out = desk_post(f"/v1/loan-requests/{rec['id']}/approve", {})
        finally:
            settle(B.desk_get(f"/v1/loan-requests/{rec['id']}"), seen, gate_off)
        b = out.get("batch") or {}
        info(f"approve -> status={out['status']} reason={out['reason']} LoanSet {out['txHash']} "
             f"{out['engineResult']} loan={out['loanId']}; Batch {b.get('hash')} {b.get('engineResult')}")
        need(out["status"] == "approved" and out["txHash"] and out["loanId"] and b.get("hash"),
             f"approve -> {out['status']} reason={out['reason']} tx={out['txHash']} batch={b.get('hash')}")
        tx.append(("demo step 8 working-capital LoanSet 60 XRP, held then approved (co-signed)", out["txHash"]))
        tx.append(("demo step 8 working-capital Batch (tfAllOrNothing, borrower-signed)", b["hash"]))
        u = retry(lambda: B.desk_get(f"/v1/batches/{b['hash']}"))
        legs = u.get("legs") or []
        for leg in legs:
            info(f"leg {leg['index']} {leg['type']} {leg['account']} -> {leg['destination']} "
                 f"{leg['amountDrops']} drops {leg['result']} {leg['hash']}")
        need(u.get("engineResult") == "tesSUCCESS" and len(legs) == 2
             and all(leg["result"] == "tesSUCCESS" for leg in legs),
             f"GET /v1/batches: outer {u.get('engineResult')} legs {[leg.get('result') for leg in legs]}")
        need([leg["amountDrops"] for leg in legs] == [STEP8["supplier"], STEP8["fee"]]
             and [leg["destination"] for leg in legs] == [supplier.address, acc["accounts"]["broker"]],
             f"legs moved {[(leg['destination'], leg['amountDrops']) for leg in legs]}")
        need(b["hash"] == rec["predicted"]["batchHash"]
             and [leg["hash"] for leg in legs] == rec["predicted"]["innerHashes"],
             "ledger hashes differ from the borrower's predicted Batch / inner hashes")
        tx.append(("demo step 8 Batch leg 0: Payment 55 XRP to the supplier (invoice memo)", legs[0]["hash"]))
        tx.append(("demo step 8 Batch leg 1: Payment 1 XRP fee to the broker", legs[1]["hash"]))
        ctx["loan8"] = out["loanId"]
        return (f"working capital held({rec['reason']}) -> approved loan={out['loanId']} LoanSet "
                f"{out['engineResult']}, Batch {u['engineResult']} legs supplier 55 XRP {legs[0]['result']} + "
                f"broker fee 1 XRP {legs[1]['result']}"), [out["txHash"], b["hash"]]

    def step9():
        need("supplier" in ctx, "skipped (needs the step 8 supplier)")
        broker = acc["accounts"]["broker"]
        # (a) policy layer: the disbursement cannot exceed the principal -> recorded refusal, no tx.
        dis = {"supplier": ctx["supplier"], "supplierDrops": STEP9A_SUPPLIER, "feeDrops": STEP8["fee"],
               "invoice": f"INV-WC-{int(time.time())}-OVER"}
        rec = settle(B.request_working_capital(STEP8["principal"], TERM_SECONDS, "inventory", STEP8["debt"], dis),
                     seen, gate_off)
        b = rec.get("batch") or {}
        need(rec["status"] == "refused" and rec["reason"] == "batch_unfunded" and rec["txHash"] is None
             and b.get("hash") is None,
             f"9a expected refused batch_unfunded, got {rec['status']} {rec['reason']} tx={rec['txHash']} "
             f"batch={b.get('hash')}")
        info(f"9a {rec['id']} supplier 70 XRP + fee 1 XRP on 60 XRP principal -> refused batch_unfunded, no tx")
        # (b) ledger: a raw all-or-nothing Batch whose supplier leg exceeds the borrower's balance.
        w = C.wallet("borrower")
        names = {"borrower": w.address, "supplier": ctx["supplier"], "broker": broker}
        v0 = C.current_ledger_index()
        before = {role: balance_at(addr, v0) for role, addr in names.items()}
        n = get_next_valid_seq_number(w.address, C.client())
        pays = drill_payments(w.address, ctx["supplier"], broker, before["borrower"] + DRILL_OVER_BALANCE,
                              int(STEP8["fee"]), n, f"INV-WC-{int(time.time())}-DRILL",
                              time.strftime("%Y-%m-%d", time.gmtime()))
        blob, signed = wc.sign_payments_batch(w, pays, n, C.current_ledger_index() + 20)
        fee = int(decode(blob)["Fee"])
        inner = [wc.inner_hash(r["RawTransaction"]) for r in decode(blob)["RawTransactions"]]
        info(f"9b drill Batch: supplier leg {pays[0].amount} drops > borrower balance {before['borrower']} drops, "
             f"fee leg {pays[1].amount} drops, outer Fee {fee} drops")
        res = C.submit_blob(blob, signed.last_ledger_sequence,
                            label="demo step 9b drill Batch (tfAllOrNothing, supplier leg exceeds the borrower balance)")
        need(res["validated"] and res["engineResult"] == "tesSUCCESS",
             f"drill outer {res['engineResult']} validated={res['validated']} {res['hash']}")
        tx.append(("demo step 9b drill Batch outer (tfAllOrNothing, unpayable supplier leg)", res["hash"]))
        tx.append(("demo step 9b drill inner 0: supplier Payment (expected not applied)", inner[0]))
        tx.append(("demo step 9b drill inner 1: broker fee Payment (expected not applied)", inner[1]))
        after = {role: balance_at(addr, res["ledgerIndex"]) for role, addr in names.items()}
        info(f"9b balances, validated ledger {v0} -> {res['ledgerIndex']}:")
        for line in drill_lines(names, before, after, fee):
            info(line)
        u = retry(lambda: B.desk_get(f"/v1/batches/{res['hash']}"))
        legs = u.get("legs") or []
        info(f"9b outer {res['hash']} {u.get('engineResult')}; " +
             ", ".join(f"inner {leg['hash']} {leg['result']}" for leg in legs))
        need([leg["hash"] for leg in legs] == inner and all(leg["result"] == "not_applied" for leg in legs),
             f"drill legs {[(leg.get('hash'), leg.get('result')) for leg in legs]}")
        return (f"9a refused batch_unfunded no tx; 9b drill Batch outer {res['engineResult']}, both inner "
                f"not_applied, supplier and broker unchanged, borrower paid only the {fee}-drop fee"), [res["hash"]]

    fns = {3: step3, 4: step4, 5: step5, 6: step6, 7: step7, 8: step8, 9: step9}
    for n in RUN_ORDER:
        if n == 8:
            info("loan 4 is in its grace period: working capital (steps 8-9) runs now, before the default")
        steps.run(n, fns[n])

    labels = {json.loads(x).get("label") for x in EXAMPLES_PATH.read_text().splitlines()} \
        if EXAMPLES_PATH.exists() else set()
    for want in ("loan-request auto", "loan-request held", "approve approved", "loan-request refused", "loans",
                 "working-capital held", "working-capital approve approved", "working-capital refused",
                 "batch unfold"):
        if want not in labels:
            info(f"WARNING desk_examples.jsonl has no '{want}' body")
    if tx:
        p = subprocess.run([PY, "make_evidence.py", *evidence_tx_args(tx)], cwd=HERE, capture_output=True, text=True)
        info(f"make_evidence.py exit {p.returncode}: {(p.stdout + p.stderr).strip()[-300:]}")
    print(f"demo {steps.passed()}/{TOTAL_STEPS} steps OK", flush=True)
    spend = llm.cost_summary()  # API-key path only; claude -p calls cost nothing here
    print(f"model spend: ${spend['spent_usd']:.4f} of ${spend['budget_usd']:.0f} ({spend['calls']} API calls)", flush=True)
    for label, h in tx:
        print(f"  {label}: {h}")
    post_rotate()
    return steps.exit_code()


# ---- autorepay scene: demo.py --income <xrp> --------------------------------
INCOME_POLL_S = 60
SWEEPER_CMD = ".venv/bin/python sweeper.py"


def income_drops(xrp: str) -> int:
    """'5' -> 5000000; '3.5' -> 3500000. Positive, at most 6 decimals."""
    try:
        d = Decimal(xrp) * XRP
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"not an XRP amount: {xrp!r}")
    if d <= 0 or d != d.to_integral_value():
        raise argparse.ArgumentTypeError(f"XRP amount must be > 0 with at most 6 decimals: {xrp!r}")
    return int(d)


def sweeper_ready(state_path: Path, borrower: str) -> str | None:
    """None when a sweeper is running on this borrower with a pinned cursor, else why not. Offline: reads the
    state file and tries the sweeper's lock (free lock = no sweeper process)."""
    import sweeper as SW
    try:
        st = json.loads(Path(state_path).read_text())
    except (OSError, ValueError):
        return "no sweeper state yet"
    if st.get("cursor") is None:
        return "the sweeper has not pinned its cursor yet"
    if st.get("borrower") != borrower:
        return f"the sweeper state is for {st.get('borrower')}, not the current borrower {borrower}"
    lock = SW.acquire_lock(state_path)
    if lock is not None:
        lock.close()
        return "no sweeper process holds the lock"
    return None


def ensure_customer():
    """The 'customer' role: an existing funded account that is neither the faucet nor the borrower's creator.
    Created once from the faucet; its seed goes to lending/.env like setup.py does, never printed."""
    from dotenv import set_key
    from xrpl.wallet import Wallet
    import setup as S
    acc = C.load_accounts()
    seed = C.read_env().get(C.SEED_VARS["customer"])
    if seed:
        w = Wallet.from_seed(seed)
    else:
        S.ensure_env_file()
        w = S.faucet()
        set_key(str(C.ENV_PATH), C.SEED_VARS["customer"], w.seed, quote_mode="never")
        info(f"customer {w.address} created from the faucet (seed -> lending/.env)")
    if acc["accounts"].get("customer") != w.address:
        acc["accounts"]["customer"] = w.address
        C.write_accounts(acc)
    return w


def main_income(xrp: str, state_path: Path | None = None) -> int:
    import sweeper as SW
    drops = income_drops(xrp)
    print(f"autorepay: start the sweeper first ({SWEEPER_CMD}) and wait for its 'watching' line", flush=True)
    borrower = C.load_accounts()["accounts"]["borrower"]
    why = sweeper_ready(state_path or SW.STATE_PATH, borrower)
    if why:
        print(f"start the sweeper first: {SWEEPER_CMD} ({why})", flush=True)
        return 2
    import setup as S
    w = ensure_customer()
    need(w.address != borrower, "the customer must not be the borrower")
    for _ in range(4):  # amount + reserve + a margin
        if S.balance_drops(w.address) >= drops + 3 * XRP:
            break
        S.faucet(w)
    today = time.strftime("%Y-%m-%d", time.gmtime())
    invoice = f"INV-AR-{int(time.time())}"
    res = C.submit_and_wait(Payment(account=w.address, destination=borrower, amount=str(drops),
                                    memos=[S.invoice_memo(invoice, today)]), w)
    print(f"income {res['hash']} {res['engineResult']} {drops / XRP:g} XRP customer {w.address} -> "
          f"borrower {borrower} invoice {invoice}", flush=True)
    if res["engineResult"] != "tesSUCCESS" or not res["validated"]:
        return 1
    deadline = time.time() + INCOME_POLL_S
    while time.time() < deadline:
        try:
            loans = get_loans()
        except Exception:  # noqa: BLE001 - desk blip: keep polling until the deadline
            loans = []
        hit = next((s for l in loans for s in l.get("sweeps") or [] if s["incomeHash"] == res["hash"].upper()), None)
        if hit:
            print(f"sweep LoanPay {hit['loanPayHash']} {hit['engineResult']} {int(hit['drops']) / XRP:g} XRP "
                  f"on loan {hit['loanId']} status={hit['status']}", flush=True)
            return 0 if hit["status"] == "repaid" else 1
        time.sleep(3)
    print(f"no sweep for income {res['hash']} on the desk within {INCOME_POLL_S}s "
          "(is a loan due within one payment interval? see the sweeper log)", flush=True)
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripted", action="store_true", help="run the 9-step devnet demo")
    ap.add_argument("--income", metavar="XRP", type=str,
                    help="send one customer x402 payment of XRP to the borrower; the running sweeper repays from it")
    args = ap.parse_args(argv)
    if args.income is not None:
        try:
            income_drops(args.income)
        except argparse.ArgumentTypeError as e:
            ap.error(str(e))
        return main_income(args.income)
    if not args.scripted:
        ap.print_help()
        return 2
    return main_scripted()


if __name__ == "__main__":
    sys.exit(main())
