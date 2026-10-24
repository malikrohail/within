"""M3 smoke test: one 10 XRP LoanSet co-signed on devnet.

A FRESH faucet account (seed in memory only, never written) is the borrower. It signs the
LoanSet first (Account=borrower, Counterparty=broker); the broker adds CounterpartySignature
and submits (common.build_loan_set / borrower_sign_loan_set / cosign_loan_set). The result is
confirmed with the tx RPC (validated + tesSUCCESS) and the Loan object is printed.
"""
from __future__ import annotations

import json
import sys
import time

from xrpl.core.binarycodec import decode
from xrpl.models.requests import Tx
from xrpl.wallet import generate_faucet_wallet

import common as C

PRINCIPAL_DROPS = "10000000"   # 10 XRP
TERM_SECONDS = 3 * C.PAYMENT_INTERVAL   # 3 payments, 90 s apart
INTEREST_RATE = 800 * 10       # policy interestRateBps 800 -> 1/10 bps
MAX_WAIT_S = 900


def public_tx_json(blob: str) -> dict:
    """Decoded tx for the report. Holds public keys and signatures only, never a seed."""
    return decode(blob)


def main() -> int:
    acc = C.load_accounts()
    broker = C.wallet("broker")
    assert broker.address == acc["accounts"]["broker"]
    # CLOSED vault: LoanSet is tecTOO_SOON until SubscriptionDate has passed.
    wait = acc["subscriptionDate"] + 5 - int(time.time())
    if wait > MAX_WAIT_S:
        print(f"vault subscription window closes in {wait}s (> {MAX_WAIT_S}s); "
              f"run setup.py --new-vault for a short window")
        return 1
    if wait > 0:
        print(f"waiting {wait}s for the vault subscription window to close", flush=True)
        time.sleep(wait)
    borrower = generate_faucet_wallet(C.client())
    print(f"borrower (fresh, in-memory) {borrower.address}", flush=True)

    tx = C.build_loan_set(borrower.address, acc["loanBrokerId"], broker.address,
                          PRINCIPAL_DROPS, TERM_SECONDS, INTEREST_RATE)
    blob = C.borrower_sign_loan_set(borrower, tx)
    policy = {"interestRateBps": INTEREST_RATE // 10}
    reason = C.verify_loan_set_blob(blob, {"borrower": borrower.address, "principalDrops": PRINCIPAL_DROPS,
                                           "termSeconds": TERM_SECONDS}, acc, policy)
    print(f"verify_loan_set_blob -> {reason or 'ok'}", flush=True)
    res = C.cosign_loan_set(broker, blob)
    print(f"LoanSet {res['engineResult']} {res['hash']} validated={res['validated']} "
          f"loanId={res['loanId']}", flush=True)
    if res["engineResult"] != "tesSUCCESS":
        print("tx_json sent (borrower-signed, before CounterpartySignature):")
        print(json.dumps(public_tx_json(blob), indent=2))
        if res.get("engineResultMessage"):
            print(f"engine_result_message: {res['engineResultMessage']}")
        return 1

    txr = C.client().request(Tx(transaction=res["hash"])).result
    ok = bool(txr.get("validated")) and txr["meta"]["TransactionResult"] == "tesSUCCESS"
    print(f"tx RPC: validated={txr.get('validated')} result={txr['meta']['TransactionResult']} "
          f"ledger={txr.get('ledger_index')}", flush=True)
    loan = C.ledger_entry(res["loanId"])
    print("Loan object:")
    print(json.dumps(loan, indent=2))
    print("list_loans item:")
    print(json.dumps(C.loan_item(loan), indent=2))
    C.audit_append({"event": "smoke_loan", "hash": res["hash"], "loanId": res["loanId"],
                    "borrower": borrower.address, "engineResult": res["engineResult"]})
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
