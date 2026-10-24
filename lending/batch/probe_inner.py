"""Preflight probe: which lending transactions does rippled accept inside a Batch?

temINVALID_INNER_BATCH is a preflight (tem) result, so it does not depend on ledger state: the ids below are dummies,
and an allowed inner type shows up as a tec/tes result instead. Two fresh faucet accounts, seeds in memory only.

  .venv/bin/python -m batch.probe_inner
"""
import json
import sys

from xrpl.core.binarycodec import encode
from xrpl.models.requests import AccountInfo
from xrpl.models.transactions import Batch, BatchFlag, LoanSet, Payment, TransactionFlag, VaultDeposit
from xrpl.models.transactions.loan_set import CounterpartySignature
from xrpl.transaction import autofill, sign, sign_multiaccount_batch
from xrpl.transaction.counterparty_signer import compute_signature

import common as C
import setup as S

C.RAWLOG_PATH = C.LENDING_DIR / "data" / "batch_rawlog.jsonl"
INNER = TransactionFlag.TF_INNER_BATCH_TXN
DUMMY = "AB" * 32


def probe(label, borrower, broker, inner, batch_signers):
    batch = Batch(account=borrower.address, flags=BatchFlag.TF_ALL_OR_NOTHING, raw_transactions=inner)
    filled = autofill(batch, C.client(), signers_count=len(batch_signers))
    for w in batch_signers:
        filled = sign_multiaccount_batch(w, filled)
    signed = sign(filled, borrower)
    res = C.submit_blob(encode(signed.to_xrpl()), signed.last_ledger_sequence, label=f"probe: {label}")
    row = {"probe": label, "engineResult": res["engineResult"], "hash": res["hash"],
           "message": res.get("engineResultMessage")}
    print(json.dumps(row), flush=True)
    return row


def main() -> int:
    borrower, broker = S.faucet(), S.faucet()
    pay = Payment(account=borrower.address, destination=broker.address, amount="1000000", flags=INNER)
    terms = dict(account=borrower.address, counterparty=broker.address, loan_broker_id=DUMMY,
                 principal_requested="1000000", payment_total=1, payment_interval=C.PAYMENT_INTERVAL,
                 grace_period=C.GRACE_PERIOD, flags=INNER)

    # LoanSet carrying the broker's CounterpartySignature over the inner tx (Fee 0, empty SigningPubKey).
    seq = int(C._rpc(AccountInfo(account=borrower.address))["account_data"]["Sequence"])
    bare = LoanSet(**terms, sequence=seq + 1, fee="0", signing_pub_key="")
    sig = compute_signature(bare.to_xrpl(), broker.private_key)
    cosigned = LoanSet(**terms, sequence=seq + 1, fee="0", signing_pub_key="",
                       counterparty_signature=CounterpartySignature(signing_pub_key=broker.public_key,
                                                                    txn_signature=sig))
    rows = [
        probe("LoanSet + CounterpartySignature, broker BatchSigner", borrower, broker, [cosigned, pay], [broker]),
        probe("LoanSet + CounterpartySignature, no BatchSigner", borrower, broker, [cosigned, pay], []),
        probe("VaultDeposit inner (control)", borrower, broker,
              [VaultDeposit(account=borrower.address, vault_id=DUMMY, amount="1000000", flags=INNER), pay], []),
    ]
    # LoanPay is not probed: xrpl-py 5.2 rejects tfInnerBatchTxn on LoanPay client-side ("Unrecognised flag").
    print("PROBE_RESULT " + json.dumps(rows), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
