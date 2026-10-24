"""Restart reconcile for held / auto records whose borrower-signed LoanSet blob may already be dead or landed.

The crash window: cosign() submits the co-signed LoanSet, the loan lands, and the process dies before s.save().
After a restart the record is still "held" (approve path) or "auto" with txHash None (auto path) and still carries
the blob. A second approve would co-sign the same blob -> tefPAST_SEQ -> status "failed" although the loan exists.
The same happens, without any crash, once the blob's LastLedgerSequence has passed.

classify() is pure. reconcile_record() applies one classification to one record under the caller's lock.
"""
from __future__ import annotations

from xrpl.core.binarycodec import decode

BLOB_KEY = "_signedLoanSet"
CANDIDATE_STATUSES = frozenset({"held", "auto"})


def blob_facts(blob: str) -> dict | None:
    """{account, sequence, lastLedger} of a signed blob, or None if it cannot be decoded."""
    try:
        tx = decode(blob)
    except Exception:  # noqa: BLE001
        return None
    seq = tx.get("TicketSequence") if tx.get("Sequence", 0) == 0 else tx.get("Sequence")
    if not tx.get("Account") or seq is None:
        return None
    return {"account": tx["Account"], "sequence": int(seq), "lastLedger": int(tx.get("LastLedgerSequence") or 0),
            "loanBrokerId": tx.get("LoanBrokerID"), "txnSignature": tx.get("TxnSignature")}


def is_candidate(rec: dict) -> bool:
    return rec.get("status") in CANDIDATE_STATUSES and bool(rec.get(BLOB_KEY)) and not rec.get("txHash")


def classify(rec: dict, account_sequence: int, current_ledger: int, landed: dict | None) -> tuple[str, dict]:
    """("landed", {hash, loanId}) | ("consumed", {}) | ("expired", {}) | ("keep", {}).
    landed = the validated tesSUCCESS LoanSet that consumed the blob's Sequence, if the caller found one."""
    facts = blob_facts(rec.get(BLOB_KEY) or "")
    if not is_candidate(rec) or facts is None:
        return "keep", {}
    if account_sequence > facts["sequence"]:
        if landed and landed.get("engineResult") == "tesSUCCESS":
            return "landed", {"hash": landed.get("hash"), "loanId": landed.get("loanId")}
        return "consumed", {}
    if facts["lastLedger"] and current_ledger > facts["lastLedger"]:
        return "expired", {}
    return "keep", {}


def apply(rec: dict, action: str, info: dict, now: int) -> bool:
    """Mutate rec for a non-keep action; returns True if it changed. Blobs are dropped on every change."""
    if action == "landed":
        rec.update(status="approved" if rec["status"] == "held" else "auto", txHash=info.get("hash"),
                   engineResult="tesSUCCESS", loanId=info.get("loanId"), reason="reconciled_after_restart")
        if rec.get("decidedBy") == "policy" and rec["status"] == "approved":
            rec["decidedBy"] = "human"  # the approve that landed never got to save its decidedBy
    elif action == "consumed":
        rec.update(status="expired", reason="sequence_consumed", decidedBy="reconcile")
    elif action == "expired":
        rec.update(status="expired", reason="blob_expired", decidedBy="reconcile")
    else:
        return False
    rec["reconciledAt"] = int(now)
    for k in (BLOB_KEY, "_signedBatch"):
        rec.pop(k, None)
    return True


def reconcile_record(rec: dict, ledger, now: int) -> tuple[str, dict]:
    """Classify one record against the ledger (adapter methods: account_sequence, ledger_index, find_loan_set)
    and apply the result. Caller holds the store lock. Ledger errors propagate (RuntimeError -> 503 upstream)."""
    if not is_candidate(rec):
        return "keep", {}
    facts = blob_facts(rec[BLOB_KEY])
    if facts is None:
        return "keep", {}
    seq = ledger.account_sequence(facts["account"])
    # only THIS blob landing settles it: same broker and the borrower's own signature, not Account + Sequence alone
    landed = (ledger.find_loan_set(facts["account"], facts["sequence"], facts["loanBrokerId"], facts["txnSignature"])
              if seq > facts["sequence"] else None)
    action, info = classify(rec, seq, ledger.ledger_index(), landed)
    apply(rec, action, info, now)
    return action, info
