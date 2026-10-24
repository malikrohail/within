"""Idempotent devnet setup for the lending desk (INTERFACES.md §0, §2, §7).

M1: faucet broker/depositorA/depositorB/borrower, the broker's kyb-borrower Credential to the borrower
(CredentialCreate + CredentialAccept), CLOSED vault, LoanBroker, first-loss cover,
two bootstrap deposits. Then seeds the borrower with a 30-day revenue history as real devnet
Payments with invoice memos from 5 in-memory customer accounts.

Re-running verifies the existing vault / broker / cover / deposits / history; it does not create
a second vault. Flags:
  --rotate-borrower   fresh borrower account (new BORROWER_SEED in .env) + re-seed history
  --new-vault         create a fresh vault + LoanBroker
  --subscription-seconds N   new vault's deposit window (default common.SUBSCRIPTION_SECONDS)
A CLOSED vault is two-phase: VaultDeposit only before SubscriptionDate (after: tecEXPIRED),
LoanSet only after it (before: tecTOO_SOON).
Seeds go to lending/.env only and are never printed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from dotenv import set_key
from xrpl.models.currencies import XRP
from xrpl.models.requests import AccountInfo
from xrpl.models.transactions import (CredentialAccept, CredentialCreate, LoanBrokerCoverDeposit,
                                      LoanBrokerSet, Memo, Payment, VaultCreate, VaultDeposit)
from xrpl.models.transactions.vault_create import VaultKind
from xrpl.utils import str_to_hex
from xrpl.wallet import Wallet, generate_faucet_wallet

import common as C

XRP_DROPS = 1_000_000
# Minimum balances (XRP) after setup's own spends, so the demo can deposit A 100 / B 50 on top.
MIN_BALANCE_XRP = {"broker": 40, "depositorA": 130, "depositorB": 70, "borrower": 20}

# 30-day revenue history: (days_ago, customer_index, xrp). Deterministic on purpose.
# 24 payments, 22 distinct days in 1..28 (days 3, 8, 12, 17, 21, 26 skipped), 5 customers,
# 61 XRP total, top customer 19 XRP = 31.1 %. Lands in the GOOD_SMALL buckets (INTERFACES §4/§7).
_DAYS = [28, 27, 25, 24, 23, 22, 20, 19, 18, 16, 15, 15, 14, 13, 11, 10, 9, 7, 6, 5, 5, 4, 2, 1]
_CUST = [0, 1, 2, 3, 4, 0, 1, 2, 0, 3, 4, 1, 2, 0, 3, 1, 4, 2, 0, 1, 3, 2, 4, 0]
_AMOUNTS = {0: ["4.5", "3", "2.5", "4", "2", "3"], 1: ["3", "2", "4", "2", "3"],
            2: ["2", "3.5", "2", "2.5", "2"], 3: ["2", "3", "1", "3"], 4: ["1", "2", "2", "2"]}


def history_schedule() -> list[tuple[int, int, int]]:
    """[(days_ago, customer_index, drops)] oldest first."""
    queues = {k: list(v) for k, v in _AMOUNTS.items()}
    rows = []
    for days_ago, cust in zip(_DAYS, _CUST):
        xrp = queues[cust].pop(0)
        rows.append((days_ago, cust, int(float(xrp) * XRP_DROPS)))
    assert all(not q for q in queues.values())
    return rows


def schedule_facts(rows) -> dict:
    total = sum(r[2] for r in rows)
    by_payer: dict[int, int] = {}
    for _, cust, drops in rows:
        by_payer[cust] = by_payer.get(cust, 0) + drops
    return {"payments": len(rows), "activeDays": len({r[0] for r in rows}),
            "volumeDrops": total, "payers": len(by_payer),
            "topPayerSharePct": round(100 * max(by_payer.values()) / total, 1)}


def invoice_memo(invoice: str, date: str) -> Memo:
    return Memo(memo_type=str_to_hex("invoice"),
                memo_data=str_to_hex(json.dumps({"invoice": invoice, "date": date})))


# ---- helpers ----------------------------------------------------------------
def log(step: str, res: dict | None = None, extra: str = "") -> None:
    if res is None:
        print(f"{step:<16} {extra}".rstrip(), flush=True)
    else:
        print(f"{step:<16} {res['engineResult']:<14} {res['hash']} {extra}".rstrip(), flush=True)


def need_success(step: str, res: dict) -> dict:
    log(step, res)
    if res["engineResult"] != "tesSUCCESS" or not res["validated"]:
        msg = res.get("engineResultMessage", "")
        sys.exit(f"FAILED {step}: {res['engineResult']} {msg}")
    return res


def balance_drops(address: str) -> int:
    res = C.client().request(AccountInfo(account=address, ledger_index="validated")).result
    if "account_data" not in res:
        return 0
    return int(res["account_data"]["Balance"])


def faucet(w: Wallet | None = None) -> Wallet:
    last = None
    for attempt in range(4):
        try:
            return generate_faucet_wallet(C.client(), wallet=w)
        except Exception as e:  # noqa: BLE001 - faucet throttling / transient HTTP
            last = e
            time.sleep(3 + 3 * attempt)
    raise RuntimeError(f"faucet failed: {type(last).__name__}")


def ensure_env_file() -> None:
    if not C.ENV_PATH.exists():
        C.ENV_PATH.touch(mode=0o600)


def ensure_wallet(name: str, rotate: bool = False) -> Wallet:
    seed = C.read_env().get(C.SEED_VARS[name])
    if seed and not rotate:
        return Wallet.from_seed(seed)
    w = faucet()
    set_key(str(C.ENV_PATH), C.SEED_VARS[name], w.seed, quote_mode="never")
    log(f"faucet {name}", extra=f"{w.address} (new; seed -> lending/.env)")
    return w


def ensure_balance(name: str, w: Wallet) -> None:
    want = MIN_BALANCE_XRP[name] * XRP_DROPS
    for _ in range(6):
        bal = balance_drops(w.address)
        if bal >= want:
            log(f"balance {name}", extra=f"{w.address} {bal / XRP_DROPS:.2f} XRP")
            return
        faucet(w)
    sys.exit(f"FAILED balance {name}: {balance_drops(w.address)} drops < {want}")


# ---- KYB credential ---------------------------------------------------------
def find_credential(borrower: str, broker: str) -> dict | None:
    from evidence import KYB_CREDENTIAL_TYPE
    for obj in C.account_objects(borrower, "credential"):
        if obj.get("Issuer") == broker and obj.get("Subject") == borrower \
                and obj.get("CredentialType", "").upper() == KYB_CREDENTIAL_TYPE:
            return obj
    return None


def ensure_credential(w_broker: Wallet, w_borrower: Wallet, setup_tx: dict) -> None:
    """Broker vets the borrower: CredentialCreate(broker -> borrower, "kyb-borrower") + CredentialAccept(borrower).
    Idempotent; a rotated borrower has no credential yet, so it is issued again."""
    from evidence import KYB_CREDENTIAL_TYPE, LSF_CREDENTIAL_ACCEPTED
    broker, borrower = w_broker.address, w_borrower.address
    cred = find_credential(borrower, broker)
    if cred is None:
        res = need_success("credentialCreate", C.submit_and_wait(CredentialCreate(
            account=broker, subject=borrower, credential_type=KYB_CREDENTIAL_TYPE), w_broker))
        setup_tx["credentialCreate"] = res["hash"]
        cred = {"Flags": 0}
    else:
        log("credentialCreate", extra=f"exists {cred['index']} (tx {setup_tx.get('credentialCreate', '?')})")
    if int(cred.get("Flags", 0)) & LSF_CREDENTIAL_ACCEPTED:
        log("credentialAccept", extra=f"exists (tx {setup_tx.get('credentialAccept', '?')})")
        return
    res = need_success("credentialAccept", C.submit_and_wait(CredentialAccept(
        account=borrower, issuer=broker, credential_type=KYB_CREDENTIAL_TYPE), w_borrower))
    setup_tx["credentialAccept"] = res["hash"]


# ---- M1 objects -------------------------------------------------------------
def find_vault(broker: str, prev: dict, new_vault: bool) -> dict | None:
    if new_vault:
        return None
    vaults = {v["index"]: v for v in C.account_objects(broker, "vault")}
    if prev.get("vaultId") in vaults:
        return vaults[prev["vaultId"]]
    closed = [v for v in vaults.values() if int(v.get("VaultKind", 0)) == int(VaultKind.CLOSED)]
    closed.sort(key=lambda v: v.get("SubscriptionDate", 0), reverse=True)
    return closed[0] if closed else None


def create_vault(w_broker: Wallet, subscription_seconds: int) -> tuple[dict, str]:
    now = int(time.time())
    sub = C.to_ripple(now + subscription_seconds)
    red = C.to_ripple(now + C.REDEMPTION_HOURS * 3600)
    res = need_success("vaultCreate", C.submit_and_wait(VaultCreate(
        account=w_broker.address, asset=XRP(), vault_kind=VaultKind.CLOSED,
        subscription_date=sub, redemption_date=red), w_broker))
    vault_id = res["created"]["Vault"]
    return C.ledger_entry(vault_id), res["hash"]


def find_loan_broker(broker: str, vault_id: str) -> dict | None:
    for obj in C.account_objects(broker, "loan_broker"):
        if obj.get("VaultID", "").upper() == vault_id.upper():
            return obj
    return None


def share_balance(holder: str, share_mpt_id: str) -> int:
    for obj in C.account_objects(holder, "mptoken"):
        if obj.get("MPTokenIssuanceID", "").upper() == share_mpt_id.upper():
            return int(obj.get("MPTAmount", "0"))
    return 0


# ---- history ------------------------------------------------------------------
def seed_history(borrower: str) -> dict:
    rows = history_schedule()
    facts = schedule_facts(rows)
    today = dt.datetime.now(dt.timezone.utc).date()
    with ThreadPoolExecutor(max_workers=5) as ex:
        customers = list(ex.map(lambda _: faucet(), range(5)))
    for i, c in enumerate(customers):
        log(f"customer {i}", extra=f"{c.address} (in-memory seed)")

    plan: dict[int, list[tuple[int, int, int, str]]] = {i: [] for i in range(5)}
    for n, (days_ago, cust, drops) in enumerate(rows):
        date = (today - dt.timedelta(days=days_ago)).isoformat()
        plan[cust].append((n, days_ago, drops, date))

    hashes: dict[int, str] = {}

    def run_customer(i: int) -> None:
        w = customers[i]
        for n, _days_ago, drops, date in plan[i]:
            invoice = f"INV-{date.replace('-', '')}-{n + 1:03d}"
            res = C.submit_and_wait(Payment(account=w.address, destination=borrower,
                                            amount=str(drops), memos=[invoice_memo(invoice, date)]), w)
            if res["engineResult"] != "tesSUCCESS" or not res["validated"]:
                raise RuntimeError(f"history payment {invoice}: {res['engineResult']}")
            hashes[n] = res["hash"]
            print(f"history {n + 1:>2}/24   {res['engineResult']:<14} {res['hash']} "
                  f"{date} {drops / XRP_DROPS:>4} XRP from customer {i}", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=5) as ex:
        list(ex.map(run_customer, range(5)))
    log("history", extra=f"{len(hashes)} payments in {time.time() - t0:.0f}s {facts}")
    return {"borrower": borrower, "customers": [c.address for c in customers],
            "paymentCount": len(hashes), "volumeDrops": str(facts["volumeDrops"]),
            "activeDays": facts["activeDays"], "topPayerSharePct": facts["topPayerSharePct"],
            "firstHash": hashes[0], "lastHash": hashes[len(rows) - 1],
            "seededAt": int(time.time())}


def history_valid(hist: dict | None, borrower: str) -> bool:
    if not hist or hist.get("borrower") != borrower:
        return False
    for h in (hist.get("firstHash"), hist.get("lastHash")):
        if not h:
            return False
        r = C.wait_for_tx(h, None, timeout=5)
        if r["engineResult"] != "tesSUCCESS":
            return False
    return True


def score_gate(borrower: str) -> int:
    try:
        from evidence import build_evidence  # node N2
        from policy import GOOD_SMALL, load_policy, score  # node N2
    except ImportError as e:
        facts = schedule_facts(history_schedule())
        ok = (20 <= facts["activeDays"] <= 25 and 55 <= facts["volumeDrops"] / XRP_DROPS <= 80
              and facts["payers"] == 5 and facts["topPayerSharePct"] <= 35)
        log("score gate", extra=f"SKIPPED exact-score check ({e.name} not present yet); "
                                f"schedule buckets {'OK' if ok else 'BAD'} {facts}")
        return 0 if ok else 1
    ev = build_evidence(borrower, GOOD_SMALL["declared"])
    s, cred, need = score(ev), ev["ledger"]["hasAcceptedCredential"], load_policy()["minScoreAuto"]
    ok = s >= need and cred
    log("score gate", extra=f"score(build_evidence(borrower, GOOD_SMALL.declared)) = {s}, broker credential "
                            f"{'accepted' if cred else 'MISSING'} ({'OK' if ok else 'EXPECTED'} >= {need} + credential)")
    return 0 if ok else 1


# ---- main -------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotate-borrower", action="store_true")
    ap.add_argument("--new-vault", action="store_true")
    ap.add_argument("--subscription-seconds", type=int, default=C.SUBSCRIPTION_SECONDS,
                    help="new vault only: deposits accepted for N s, loans accepted after")
    args = ap.parse_args()

    ensure_env_file()
    try:
        prev = C.load_accounts()
    except FileNotFoundError:
        prev = {}

    wallets = {n: ensure_wallet(n, rotate=(n == "borrower" and args.rotate_borrower))
               for n in ("broker", "depositorA", "depositorB", "borrower")}
    for n, w in wallets.items():
        ensure_balance(n, w)
    wb = wallets["broker"]
    setup_tx = dict(prev.get("setupTx", {}))
    ensure_credential(wb, wallets["borrower"], setup_tx)

    # Vault (CLOSED). Reuse unless --new-vault.
    vault = find_vault(wb.address, prev, args.new_vault)
    if vault is None:
        vault, setup_tx["vaultCreate"] = create_vault(wb, args.subscription_seconds)
        for k in ("loanBrokerSet", "coverDeposit", "depositA", "depositB"):
            setup_tx.pop(k, None)
    else:
        log("vaultCreate", extra=f"exists {vault['index']} (tx {setup_tx.get('vaultCreate', '?')})")
    vault_id, share_id = vault["index"], vault["ShareMPTID"]
    sub_unix, red_unix = C.from_ripple(vault["SubscriptionDate"]), C.from_ripple(vault["RedemptionDate"])
    left = sub_unix - int(time.time())
    log("vault window", extra=f"deposits accepted until {sub_unix} ({max(left, 0)}s left); "
                              f"loans accepted after it; redemption {red_unix}")

    # LoanBroker
    lb = find_loan_broker(wb.address, vault_id)
    if lb is None:
        res = need_success("loanBrokerSet", C.submit_and_wait(LoanBrokerSet(
            account=wb.address, vault_id=vault_id, **C.LOAN_BROKER), wb))
        setup_tx["loanBrokerSet"] = res["hash"]
        lb = C.ledger_entry(res["created"]["LoanBroker"])
    else:
        log("loanBrokerSet", extra=f"exists {lb['index']} (tx {setup_tx.get('loanBrokerSet', '?')})")
    lb_id = lb["index"]

    # First-loss cover
    cover = int(C.ledger_entry(lb_id).get("CoverAvailable", "0"))
    target = int(C.COVER_DEPOSIT_DROPS)
    if cover < target:
        res = need_success("coverDeposit", C.submit_and_wait(LoanBrokerCoverDeposit(
            account=wb.address, loan_broker_id=lb_id, amount=str(target - cover)), wb))
        setup_tx["coverDeposit"] = res["hash"]
    else:
        log("coverDeposit", extra=f"exists cover={cover} drops (tx {setup_tx.get('coverDeposit', '?')})")

    # Bootstrap deposits
    for name, key in (("depositorA", "depositA"), ("depositorB", "depositB")):
        w = wallets[name]
        held = share_balance(w.address, share_id)
        if held > 0:
            log(key, extra=f"exists shares={held} (tx {setup_tx.get(key, '?')})")
            continue
        res = need_success(key, C.submit_and_wait(VaultDeposit(
            account=w.address, vault_id=vault_id, amount=C.SETUP_DEPOSITS[name]), w))
        setup_tx[key] = res["hash"]

    accounts = {
        "network": "devnet",
        "createdAt": prev.get("createdAt") if prev.get("vaultId") == vault_id else int(time.time()),
        # keep roles setup does not own (e.g. "supplier", labelled for the accounts route), then its own wallets
        "accounts": {**prev.get("accounts", {}), **{n: w.address for n, w in wallets.items()}},
        "vaultId": vault_id, "shareMptId": share_id, "loanBrokerId": lb_id,
        "vaultKind": "closed", "subscriptionDate": sub_unix, "redemptionDate": red_unix,
        "setupTx": setup_tx,
        "history": prev.get("history"),
    }
    C.write_accounts(accounts)  # M1 state is durable before the slower history step
    log("M1", extra=f"vaultId={vault_id} loanBrokerId={lb_id} shareMptId={share_id}")

    borrower = wallets["borrower"].address
    if history_valid(prev.get("history"), borrower) and not args.rotate_borrower:
        h = prev["history"]
        log("history", extra=f"exists {h['paymentCount']} payments first={h['firstHash']} "
                             f"last={h['lastHash']}")
    else:
        accounts["history"] = seed_history(borrower)
        C.write_accounts(accounts)
    log("accounts.json", extra=str(C.ACCOUNTS_PATH))
    return score_gate(borrower)


if __name__ == "__main__":
    sys.exit(main())
