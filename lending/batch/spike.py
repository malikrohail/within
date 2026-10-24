"""Batch spike: can a LoanSet ride inside an all-or-nothing Batch?

Runs on its own fresh devnet accounts (seeds in memory only) and its own close-ended vault, so the desk's
vault and broker sequence are untouched. Every submission goes to data/batch_rawlog.jsonl for EVIDENCE.md.

  A  Batch(borrower, AllOrNothing): LoanSet Account=broker Counterparty=borrower, Payment->supplier, Payment->broker fee
  B  if A fails: same with LoanSet Account=borrower Counterparty=broker
  C  if both fail: co-signed LoanSet first, then Batch of the two payments only
  D  drill: Batch with a LoanSet and an unpayable supplier Payment -> nothing applies, vault unchanged
  E  cover check: default the 60 XRP loan after its grace period and read the LoanBroker cover hit

  .venv/bin/python -m batch.spike
"""
import json
import sys
import time
from dataclasses import replace

from xrpl.core.binarycodec import encode

from xrpl.models.requests import Ledger, Tx
from xrpl.models.transactions import (Batch, BatchFlag, LoanBrokerCoverDeposit, LoanBrokerSet, LoanSet, Payment,
                                      TransactionFlag, VaultDeposit)
from xrpl.transaction import autofill, sign, sign_loan_set_by_counterparty, sign_multiaccount_batch

import common as C
import setup as S

C.RAWLOG_PATH = C.LENDING_DIR / "data" / "batch_rawlog.jsonl"
XRP_ = 1_000_000
SUB_SECONDS = 60
LOAN = 60 * XRP_
SUPPLIER = 55 * XRP_
FEE = 1 * XRP_
COVER = 20 * XRP_
DEPOSIT = 90 * XRP_
LIQUIDATION = 100000  # 100% of the minimum cover -> DebtTotal x 10% x 100% = 10% of debt on default
INNER = TransactionFlag.TF_INNER_BATCH_TXN
out: dict = {"txs": {}}


def say(*a):
    print(*a, flush=True)


def ok(label, res):
    out["txs"][label] = {"hash": res["hash"], "engineResult": res["engineResult"]}
    say(f"{label:28s} {res['engineResult']:16s} {res['hash']}")
    return res


def tx_result(h):
    r = C._rpc(Tx(transaction=h))
    return r.get("meta", {}).get("TransactionResult") if r.get("validated") else (r.get("error") or "not_validated")


def close_time() -> int:
    return int(C._rpc(Ledger(ledger_index="validated"))["ledger"]["close_time"])


def loan_terms(account, counterparty, broker_id, principal):
    return dict(account=account, counterparty=counterparty, loan_broker_id=broker_id, principal_requested=str(principal),
                interest_rate=500, payment_total=3, payment_interval=C.PAYMENT_INTERVAL, grace_period=C.GRACE_PERIOD)


def invoice(n):
    return [S.invoice_memo(f"INV-BATCH-{n}", time.strftime("%Y-%m-%d"))]


def submit_batch(label, borrower, signers, inner):
    """Outer Batch from the borrower; each wallet in `signers` adds a BatchSigner. Returns outer + inner results."""
    batch = Batch(account=borrower.address, flags=BatchFlag.TF_ALL_OR_NOTHING, raw_transactions=inner)
    filled = autofill(batch, C.client(), signers_count=len(signers))
    for w in signers:
        filled = sign_multiaccount_batch(w, filled)
    signed = sign(filled, borrower)
    res = C.submit_blob(encode(signed.to_xrpl()), signed.last_ledger_sequence, label=label)
    inner_hashes = [t.get_hash() for t in filled.raw_transactions]
    time.sleep(1)
    inner_res = [{"type": t.transaction_type.value, "hash": h, "result": tx_result(h)}
                 for t, h in zip(filled.raw_transactions, inner_hashes)]
    out["txs"][label] = {"hash": res["hash"], "engineResult": res["engineResult"], "inner": inner_res,
                         **({"engineResultMessage": res["engineResultMessage"]} if res.get("engineResultMessage") else {})}
    say(f"{label:28s} outer {res['engineResult']} {res['hash']} {res.get('engineResultMessage', '')}")
    for r in inner_res:
        say(f"    inner {r['type']:10s} {r['result']:16s} {r['hash']}")
    return res, inner_res


def landed(res, inner_res):
    return res["engineResult"] == "tesSUCCESS" and all(r["result"] == "tesSUCCESS" for r in inner_res)


def main() -> int:
    say("funding fresh accounts (seeds stay in memory)")
    broker, depositor, borrower, supplier = (S.faucet() for _ in range(4))
    out["accounts"] = {"broker": broker.address, "depositor": depositor.address,
                       "borrower": borrower.address, "supplier": supplier.address}
    say(json.dumps(out["accounts"]))

    vault, h = S.create_vault(broker, SUB_SECONDS)
    out["txs"]["VaultCreate"] = {"hash": h, "engineResult": "tesSUCCESS"}
    vault_id = vault["index"]
    sub_date = int(vault["SubscriptionDate"])
    lb = ok("LoanBrokerSet", C.submit_and_wait(LoanBrokerSet(
        account=broker.address, vault_id=vault_id, management_fee_rate=1000, debt_maximum="0",
        cover_rate_minimum=10000, cover_rate_liquidation=LIQUIDATION), broker))
    broker_id = lb["created"]["LoanBroker"]
    ok("LoanBrokerCoverDeposit", C.submit_and_wait(LoanBrokerCoverDeposit(
        account=broker.address, loan_broker_id=broker_id, amount=str(COVER)), broker))
    ok("VaultDeposit", C.submit_and_wait(VaultDeposit(
        account=depositor.address, vault_id=vault_id, amount=str(DEPOSIT)), depositor))
    out.update(vaultId=vault_id, loanBrokerId=broker_id)
    while (left := sub_date - close_time()) > 0:
        say(f"lending opens in {left}s")
        time.sleep(min(10, left + 1))

    pay_supplier = Payment(account=borrower.address, destination=supplier.address, amount=str(SUPPLIER),
                           memos=invoice(1), flags=INNER)
    pay_fee = Payment(account=borrower.address, destination=broker.address, amount=str(FEE), flags=INNER)

    loan_id = None
    # A: broker-originated LoanSet; the borrower is the counterparty and the outer signer.
    res, inner = submit_batch("Batch A (LoanSet broker->borrower)", borrower, [broker], [
        LoanSet(**loan_terms(broker.address, borrower.address, broker_id, LOAN), flags=INNER), pay_supplier, pay_fee])
    out["variant"] = "A" if landed(res, inner) else None
    if not out["variant"]:
        # B: borrower-originated LoanSet; the broker is the counterparty and signs via BatchSigners.
        res, inner = submit_batch("Batch B (LoanSet borrower->broker)", borrower, [broker], [
            LoanSet(**loan_terms(borrower.address, broker.address, broker_id, LOAN), flags=INNER), pay_supplier, pay_fee])
        out["variant"] = "B" if landed(res, inner) else None
    if out["variant"]:
        loan_id = C._rpc(Tx(transaction=inner[0]["hash"])).get("meta", {})
        loan_id = C._created(loan_id).get("Loan")
    else:
        # C: LoanSet lands immediately before, payments-only Batch.
        ls = replace(C.build_loan_set(borrower.address, broker_id, broker.address, str(LOAN), 270, 500),
                     last_ledger_sequence=C.current_ledger_index() + C.LOAN_LAST_LEDGER_OFFSET)
        blob = encode(sign(autofill(ls, C.client()), borrower).to_xrpl())
        cs = ok("LoanSet (before batch)", C.submit_blob(sign_loan_set_by_counterparty(broker, blob).tx_blob,
                                                         ls.last_ledger_sequence, label="LoanSet before Batch C"))
        loan_id = cs["created"].get("Loan")
        res, inner = submit_batch("Batch C (payments only)", borrower, [], [pay_supplier, pay_fee])
        out["variant"] = "C" if landed(res, inner) else "none"
    out["loanId"] = loan_id
    say(f"variant {out['variant']} loan {loan_id}")

    # D: all-or-nothing drill. The supplier leg is more than the borrower can pay, so the LoanSet must not apply either.
    before = C.ledger_entry(vault_id)
    big = Payment(account=borrower.address, destination=supplier.address, amount=str(5000 * XRP_),
                  memos=invoice(2), flags=INNER)
    lo = (broker.address, borrower.address) if out["variant"] != "B" else (borrower.address, broker.address)
    res_d, inner_d = submit_batch("Batch D (drill, unpayable)", borrower, [broker] if out["variant"] in ("A", "B") else [], [
        LoanSet(**loan_terms(*lo, broker_id, 20 * XRP_), flags=INNER), big] if out["variant"] in ("A", "B") else [big, pay_fee])
    after = C.ledger_entry(vault_id)
    out["drill"] = {"AssetsAvailable": [before.get("AssetsAvailable"), after.get("AssetsAvailable")],
                    "AssetsTotal": [before.get("AssetsTotal"), after.get("AssetsTotal")]}
    say(f"drill vault AssetsAvailable {before.get('AssetsAvailable')} -> {after.get('AssetsAvailable')}")

    # E: default the 60 XRP loan once the first payment is past due + grace; cover should drop ~10% of DebtTotal.
    if loan_id:
        loan = C.ledger_entry(loan_id)
        allowed = int(loan["NextPaymentDueDate"]) + C.GRACE_PERIOD
        while (left := allowed - close_time()) >= 0:
            say(f"default allowed in {left + 1}s")
            time.sleep(min(15, left + 2))
        lb_before = C.ledger_entry(broker_id)
        d = ok("LoanManage default", C.loan_manage(broker, loan_id, "default"))
        lb_after = C.ledger_entry(broker_id)
        out["cover"] = {k: [lb_before.get(k), lb_after.get(k)] for k in ("CoverAvailable", "DebtTotal")}
        say(f"cover {out['cover']}")
    print("SPIKE_RESULT " + json.dumps(out), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
