"""Working-capital draw, design C (INTERFACES.md §8).

rippled rejects LoanSet as a Batch inner tx (temINVALID_INNER_BATCH), so the borrower signs TWO blobs up front:
  1. LoanSet, Sequence N, Fee 30, LastLedgerSequence L (the desk co-signs and submits it first)
  2. Batch tfAllOrNothing, Sequence N+1, LastLedgerSequence L, inner Payments N+2 (supplier, invoice memo)
     and N+3 (broker fee). Borrower-only: no BatchSigners.
The desk submits the Batch only after the LoanSet is tesSUCCESS. A failed all-or-nothing Batch is still outer
tesSUCCESS (fee charged); its inner txs never reach the ledger (tx RPC txnNotFound -> "not_applied").
Never print a Wallet object: its repr includes the seed.
"""
from __future__ import annotations

import json
import time
from dataclasses import replace

from xrpl.account import get_next_valid_seq_number
from xrpl.core.binarycodec import decode, encode
from xrpl.models.requests import Tx
from xrpl.models.transactions import Batch, BatchFlag, Payment, Transaction, TransactionFlag
from xrpl.transaction import autofill, sign
from xrpl.utils import hex_to_str, str_to_hex
from xrpl.wallet import Wallet

import common as C
import setup as S

ALL_OR_NOTHING = int(BatchFlag.TF_ALL_OR_NOTHING)  # 0x00010000
INNER = int(TransactionFlag.TF_INNER_BATCH_TXN)     # 0x40000000
INVOICE_TYPE = str_to_hex("invoice").upper()


def inner_hash(raw: dict) -> str:
    """Hash of one inner tx as rippled reports it (proven on devnet against applied inners CEC27BB4/3B49A298)."""
    return Transaction.from_xrpl(raw).get_hash()


def sign_payments_batch(w: Wallet, payments: list[Payment], sequence: int, last_ledger_sequence: int,
                        fee: str | None = None) -> tuple[str, Batch]:
    """Borrower-only tfAllOrNothing Batch of `payments` (already inner-shaped). Fee None -> autofill (2 x base +
    inner fees). Returns (signed blob, signed Batch)."""
    batch = Batch(account=w.address, flags=ALL_OR_NOTHING, raw_transactions=payments, sequence=sequence,
                  last_ledger_sequence=last_ledger_sequence, fee=fee)
    if fee is None:
        batch = autofill(batch, C.client(), signers_count=0)  # keeps the given outer + inner sequences
        assert batch.sequence == sequence and [t.sequence for t in batch.raw_transactions] == \
            [p.sequence for p in payments], "autofill changed a sequence"
    signed = sign(batch, w)
    return encode(signed.to_xrpl()), signed


def build_working_capital_batch(w_borrower: Wallet, loan_terms: dict, supplier: str, amount_drops: str,
                                fee_drops: str, invoice: str, broker: str, *, sequence: int | None = None,
                                last_ledger_sequence: int | None = None, batch_fee: str | None = None) -> dict:
    """loan_terms = {"loanBrokerId", "principalDrops", "termSeconds", "interestRate"}.
    sequence / last_ledger_sequence / batch_fee given -> no network (offline tests)."""
    addr = w_borrower.address
    n = sequence if sequence is not None else get_next_valid_seq_number(addr, C.client())
    last = last_ledger_sequence if last_ledger_sequence is not None \
        else C.current_ledger_index() + C.LOAN_LAST_LEDGER_OFFSET
    loan = replace(C.build_loan_set(addr, loan_terms["loanBrokerId"], broker, str(loan_terms["principalDrops"]),
                                    int(loan_terms["termSeconds"]), int(loan_terms["interestRate"])),
                   sequence=n, last_ledger_sequence=last, fee=C.LOAN_SET_FEE)
    loan_blob = encode(sign(loan, w_borrower).to_xrpl())
    inner = dict(account=addr, flags=INNER, fee="0", signing_pub_key="")
    payments = [
        Payment(**inner, destination=supplier, amount=str(amount_drops), sequence=n + 2,
                memos=[S.invoice_memo(invoice, time.strftime("%Y-%m-%d", time.gmtime()))]),
        Payment(**inner, destination=broker, amount=str(fee_drops), sequence=n + 3),
    ]
    batch_blob, signed = sign_payments_batch(w_borrower, payments, n + 1, last, batch_fee)
    raws = [r["RawTransaction"] for r in decode(batch_blob)["RawTransactions"]]
    return {"signedLoanSet": loan_blob, "signedBatch": batch_blob, "loanSetSequence": n,
            "batchHash": signed.get_hash(), "innerHashes": [inner_hash(r) for r in raws]}


def _memo_invoice(tx: dict) -> str | None:
    for m in tx.get("Memos") or []:
        memo = m.get("Memo", {})
        if str(memo.get("MemoType", "")).upper() == INVOICE_TYPE:
            try:
                return json.loads(hex_to_str(memo.get("MemoData", "")))["invoice"]
            except (ValueError, KeyError, TypeError):
                return None
    return None


def verify_working_capital_batch(batch_blob: str, loan_blob: str, body: dict, accounts: dict) -> str | None:
    """None if the Batch moves exactly the declared disbursement, else "batch_mismatch:<what>"."""
    d = body.get("disbursement") or {}
    borrower, broker = body["borrower"], accounts["accounts"]["broker"]
    try:
        tx, loan = decode(batch_blob), decode(loan_blob)
    except Exception:  # noqa: BLE001 - any decode error is a reject reason
        return "batch_mismatch:not_batch"
    if tx.get("TransactionType") != "Batch":
        return "batch_mismatch:not_batch"
    raws = [r.get("RawTransaction", {}) for r in tx.get("RawTransactions") or []]
    if int(tx.get("Flags", 0)) != ALL_OR_NOTHING or any(int(r.get("Flags", 0)) != INNER for r in raws):
        return "batch_mismatch:flags"
    if tx.get("Account") != borrower or any(r.get("Account") != borrower for r in raws):
        return "batch_mismatch:account"
    seq = loan.get("Sequence")
    if not isinstance(seq, int) or tx.get("Sequence") != seq + 1 or \
            any(r.get("Sequence") != seq + 2 + i for i, r in enumerate(raws)):
        return "batch_mismatch:sequence"
    if len(raws) != 2 or any(r.get("TransactionType") != "Payment" for r in raws):
        return "batch_mismatch:inner_count"
    if [r.get("Destination") for r in raws] != [d.get("supplier"), broker]:
        return "batch_mismatch:destination"
    if [r.get("Amount") for r in raws] != [str(d.get("supplierDrops")), str(d.get("feeDrops"))]:
        return "batch_mismatch:amount"
    if _memo_invoice(raws[0]) != d.get("invoice"):
        return "batch_mismatch:memo"
    if not tx.get("TxnSignature") or not tx.get("SigningPubKey") or tx.get("BatchSigners"):
        return "batch_mismatch:unsigned"
    if not C.signed_by_account(tx):
        return "batch_mismatch:bad_signature"
    return None


def _tx(h: str) -> dict:
    return C._rpc(Tx(transaction=h))


def unfold_batch(batch_hash: str) -> dict | None:
    """GET /v1/batches/{hash} body; None when the ledger does not know the hash or it is not a Batch."""
    res = _tx(batch_hash)
    tj = res.get("tx_json") or {}
    if res.get("error") or tj.get("TransactionType") != "Batch":
        return None
    validated = bool(res.get("validated"))
    legs = []
    for i, entry in enumerate(tj.get("RawTransactions") or []):
        raw = entry["RawTransaction"]
        h = inner_hash(raw)
        r = _tx(h)
        if r.get("error") == "txnNotFound" and validated and \
                res.get("meta", {}).get("TransactionResult") == "tesSUCCESS":
            time.sleep(1)  # inner txs share the outer's ledger; one retry covers a lagging node
            r = _tx(h)
        if r.get("error"):
            result = "not_applied" if r["error"] == "txnNotFound" else r["error"]
        else:
            result = r.get("meta", {}).get("TransactionResult") if r.get("validated") else "not_validated"
        amount = raw.get("Amount")
        legs.append({"index": i, "type": raw.get("TransactionType"), "account": raw.get("Account"),
                     "destination": raw.get("Destination"),
                     "amountDrops": amount if isinstance(amount, str) else None, "hash": h, "result": result})
    return {"hash": res.get("hash", batch_hash), "validated": validated,
            "engineResult": res.get("meta", {}).get("TransactionResult") if validated else "not_validated",
            "account": tj.get("Account"), "flags": int(tj.get("Flags", 0)), "legs": legs}
