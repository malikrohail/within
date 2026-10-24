"""Borrower agent (INTERFACES.md §6). Holds only the borrower key; never sees the broker key.

It builds and signs its own LoanSet (Account=borrower, Counterparty=broker) and sends the blob with
the loan request; the desk verifies it and adds the broker's CounterpartySignature on auto/approve.
accounts.json is re-read on every call: each scripted run opens a new vault and may rotate the borrower.
"""
from __future__ import annotations

import os
import time

import requests

import common
from batch import working_capital as wc

DESK_URL = os.environ.get("DESK_URL") or common.read_env().get("DESK_URL") or "http://localhost:7500"
# A POST may block on the 20 s second opinion plus two serial wait_for_tx (working capital: LoanSet, then the Batch),
# each up to common.WAIT_TIMEOUT_S, plus evidence and vault reads. The desk, not this socket, decides when a tx expired.
POST_TIMEOUT_S = 2 * common.WAIT_TIMEOUT_S + 60
FINAL_STATUSES = ("auto", "approved", "denied", "refused", "expired", "failed")


def desk_get(path: str, desk_url: str = DESK_URL) -> dict:
    r = requests.get(desk_url + path, timeout=60)
    r.raise_for_status()
    return r.json()


def build_request_body(w, principal_drops: str, term_seconds: int, purpose: str, existing_debt_drops: str,
                       accounts: dict, policy: dict, sign=None) -> dict:
    """The POST /v1/loan-requests body with the borrower-signed LoanSet blob (pure apart from `sign`)."""
    sign = sign or common.borrower_sign_loan_set
    tx = common.build_loan_set(w.address, accounts["loanBrokerId"], accounts["accounts"]["broker"],
                               str(principal_drops), int(term_seconds), int(policy["interestRateBps"]) * 10)
    return {"borrower": w.address, "principalDrops": str(principal_drops), "termSeconds": int(term_seconds),
            "purpose": purpose, "declared": {"existingDebtDrops": str(existing_debt_drops)},
            "signedLoanSet": sign(w, tx)}


def post_request(body: dict, desk_url: str = DESK_URL) -> tuple[int, dict]:
    r = requests.post(desk_url + "/v1/loan-requests", json=body, timeout=POST_TIMEOUT_S)
    return r.status_code, r.json()


def request_loan(principal_drops: str, term_seconds: int, purpose: str, existing_debt_drops: str,
                 wallet=None, desk_url: str = DESK_URL) -> dict:
    """Sign a LoanSet and ask the desk for it. Returns the desk record; raises on a non-200."""
    w = wallet or common.wallet("borrower")
    policy = desk_get("/v1/policy", desk_url)
    body = build_request_body(w, principal_drops, term_seconds, purpose, existing_debt_drops,
                              common.load_accounts(), policy)
    status, out = post_request(body, desk_url)
    if status != 200:
        raise RuntimeError(f"desk {status}: {out}")
    return out


def build_working_capital_body(w, principal_drops: str, term_seconds: int, purpose: str, existing_debt_drops: str,
                               disbursement: dict, accounts: dict, policy: dict, **build_kw) -> tuple[dict, dict]:
    """INTERFACES §8 body: the LoanSet (Sequence N) and the payments Batch (N+1) come from one builder call, so
    the two blobs agree. build_kw (sequence, last_ledger_sequence, batch_fee) -> no network (offline tests).
    Returns (body, built) where built carries the predicted batchHash and innerHashes."""
    d = {"supplier": disbursement["supplier"], "supplierDrops": str(disbursement["supplierDrops"]),
         "feeDrops": str(disbursement["feeDrops"]), "invoice": disbursement["invoice"]}
    terms = {"loanBrokerId": accounts["loanBrokerId"], "principalDrops": str(principal_drops),
             "termSeconds": int(term_seconds), "interestRate": int(policy["interestRateBps"]) * 10}
    built = wc.build_working_capital_batch(w, terms, d["supplier"], d["supplierDrops"], d["feeDrops"], d["invoice"],
                                           accounts["accounts"]["broker"], **build_kw)
    body = {"borrower": w.address, "principalDrops": str(principal_drops), "termSeconds": int(term_seconds),
            "purpose": purpose, "declared": {"existingDebtDrops": str(existing_debt_drops)},
            "signedLoanSet": built["signedLoanSet"], "disbursement": d, "signedBatch": built["signedBatch"]}
    return body, built


def request_working_capital(principal_drops: str, term_seconds: int, purpose: str, existing_debt_drops: str,
                            disbursement: dict, wallet=None, desk_url: str = DESK_URL) -> dict:
    """Working-capital draw (§8): signed LoanSet + signed all-or-nothing payments Batch in one POST.
    disbursement = {"supplier", "supplierDrops", "feeDrops", "invoice"}. Returns the desk record plus
    "predicted": {"batchHash", "innerHashes"} from the builder; raises on a non-200."""
    w = wallet or common.wallet("borrower")
    policy = desk_get("/v1/policy", desk_url)
    body, built = build_working_capital_body(w, principal_drops, term_seconds, purpose, existing_debt_drops,
                                             disbursement, common.load_accounts(), policy)
    status, out = post_request(body, desk_url)
    if status != 200:
        raise RuntimeError(f"desk {status}: {out}")
    return {**out, "predicted": {"batchHash": built["batchHash"], "innerHashes": built["innerHashes"]}}


def wait_for(request_id: str, statuses=("approved", "denied", "expired", "failed"), timeout: int = 180,
             desk_url: str = DESK_URL) -> dict:
    deadline = time.time() + timeout
    while True:
        rec = desk_get(f"/v1/loan-requests/{request_id}", desk_url)
        if rec["status"] in statuses or time.time() > deadline:
            return rec
        time.sleep(2)


def pay_installment(loan_id: str) -> dict:
    return common.loan_pay(common.wallet("borrower"), loan_id)
