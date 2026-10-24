"""Authorization and admission guards for the Lending Desk.

Four pure pieces, wired into desk.py:
  1. Operator token: env DESK_TOKEN, header X-Desk-Token. require_operator fails closed (503) when the env var is
     unset and 401 on a missing or wrong token. require_operator_unless_local exempts loopback callers (the borrower
     agent posting notes on the same host).
  2. Pending-exposure cap: pending_exposure_drops sums the principal of every held or in-flight request; a new
     request is refused when it would push that sum over policy["maxPendingDrops"] (0 = no cap).
  3. Idempotency key: blob_key is (Account, Sequence|TicketSequence) of the borrower-signed LoanSet; a second POST with
     the same key returns the first record instead of creating another.
  4. Ledger approval token: a held loan is approved by a 1-drop testnet Payment the Ledger signed, carrying
     sha256(LoanSet blob) in a Memo (wallet POST /v1/lend/approve). verify_approval_payment checks that tx offline;
     fetch_testnet_tx reads it from testnet. The desk co-signs only when the check passes.
"""
from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import Header, HTTPException, Request
from xrpl.clients import JsonRpcClient
from xrpl.core import keypairs
from xrpl.core.binarycodec import decode
from xrpl.models.requests import Tx

TOKEN_ENV = "DESK_TOKEN"
TOKEN_HEADER = "X-Desk-Token"
APPROVER_ENV = "DESK_APPROVER_ACCOUNT"   # the Ledger (treasury) address that signs approval Payments
APPROVER_PUBKEY_ENV = "DESK_APPROVER_PUBKEY"   # optional: pin the device's public key (else: master key of the account)
TESTNET_URL = "https://s.altnet.rippletest.net:51234/"
APPROVAL_MEMO_TYPE = "loan-approval".encode().hex().upper()   # 6C6F616E2D617070726F76616C
TERMS_MEMO_TYPE = "loan-terms".encode().hex().upper()   # optional second Memo (wallet contract v1.7)
LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
PENDING_STATUSES = frozenset({"held"})
BLOB_FIELD = "_signedLoanSet"   # desk._BLOB: the stored borrower-signed blob of a held or in-flight record


# ---- 1. operator token --------------------------------------------------------
def configured_token() -> str | None:
    t = os.environ.get(TOKEN_ENV, "").strip()
    return t or None


def token_ok(presented: str | None) -> bool:
    t = configured_token()
    return bool(t and presented and hmac.compare_digest(t.encode(), presented.encode()))


def require_operator(x_desk_token: str | None = Header(None, alias=TOKEN_HEADER)) -> None:
    """FastAPI dependency for the operator routes (approve, deny, PUT policy, cover top-up)."""
    if configured_token() is None:
        raise HTTPException(503, detail="operator_token_unset")
    if not token_ok(x_desk_token):
        raise HTTPException(401, detail="operator_token_required")


def is_local(request: Request) -> bool:
    return bool(request.client) and request.client.host in LOCAL_HOSTS


def require_operator_unless_local(request: Request,
                                  x_desk_token: str | None = Header(None, alias=TOKEN_HEADER)) -> None:
    """Notes: loopback callers (the borrower agent on this host) need no token; anyone else does."""
    if not is_local(request):
        require_operator(x_desk_token)


# ---- 2. pending-exposure cap ------------------------------------------------------
def _hold_lapsed(r: dict, inflight: set, now: int | None, hold_timeout: int | None) -> bool:
    """desk.expire_if_due's condition: a held record past its deadline is expired already, whether or not a GET has
    swept it yet (review C4), so it no longer counts toward the pending cap."""
    return now is not None and hold_timeout is not None and r.get("status") == "held" and r["id"] not in inflight \
        and now >= int(r.get("ts", 0)) + int(hold_timeout)


def pending_exposure_drops(records: dict, inflight: set, reserved: dict | None = None, now: int | None = None,
                           hold_timeout: int | None = None) -> int:
    """Principal of every request that may still turn into a loan: held (deadline not passed), auto in progress
    (inflight), or still being decided (reserved: blobKey -> principalDrops, kept by the Store while the second
    opinion runs)."""
    return sum(int(r["principalDrops"]) for r in records.values()
               if (r.get("status") in PENDING_STATUSES or r["id"] in inflight)
               and not _hold_lapsed(r, inflight, now, hold_timeout)) \
        + sum(int(p) for p in (reserved or {}).values())


def pending_cap_exceeded(records: dict, inflight: set, principal_drops: str | int, policy: dict,
                         reserved: dict | None = None, now: int | None = None) -> bool:
    cap = int(policy.get("maxPendingDrops", "0") or 0)
    hold = policy.get("holdTimeoutSeconds")
    return cap > 0 and pending_exposure_drops(records, inflight, reserved, now, hold) + int(principal_drops) > cap


# ---- 3. idempotency key ------------------------------------------------------------
def blob_key(blob: str) -> str | None:
    """'<Account>:<Sequence or TicketSequence>' of a signed blob; None if it cannot be decoded."""
    try:
        tx = decode(blob)
    except Exception:  # noqa: BLE001 - verify_loan_set_blob reports the decode error itself
        return None
    seq = tx.get("TicketSequence") if tx.get("Sequence", 0) == 0 else tx.get("Sequence")
    acct = tx.get("Account")
    return f"{acct}:{seq}" if acct and seq is not None else None


TERMINAL_UNLANDED = frozenset({"expired", "denied", "refused"})   # nothing was ever submitted for these


def _can_match(rec: dict) -> bool:
    """A record only blocks a replay if its blob may have landed or still can: terminal records that never
    submitted anything (expired/denied/refused, or failed without a txHash) must not, because the borrower's next
    blob carries the SAME Sequence until a tx lands on-chain (red-team finding, 2026-10-24)."""
    status = rec.get("status")
    if status in TERMINAL_UNLANDED:
        return False
    if status == "failed" and not rec.get("txHash"):
        return False
    return True


def record_blob_key(rec: dict, blob_field: str = BLOB_FIELD) -> str | None:
    """rec["blobKey"]; a record stored before the auth change has none, so derive it from the stored blob and write it
    back (lazy migration, security review C3). Terminal records dropped their blob and stay keyless."""
    key = rec.get("blobKey")
    if not key and rec.get(blob_field):
        key = rec["blobKey"] = blob_key(rec[blob_field])
    return key


def find_duplicate(records: dict, key: str | None, blob_field: str = BLOB_FIELD) -> dict | None:
    """The live record (held, auto in flight, approved, or failed after a submit) carrying `key`; expired, denied
    and refused records never block (see _can_match), and a pre-migration record is matched by its stored blob."""
    if not key:
        return None
    return next((r for r in records.values() if _can_match(r) and record_blob_key(r, blob_field) == key), None)


# ---- 4. Ledger approval token ----------------------------------------------------
def loan_set_hash(blob: str) -> str:
    """sha256 over the blob bytes, uppercase hex. This is the value the wallet puts in MemoData."""
    return hashlib.sha256(bytes.fromhex(blob)).hexdigest().upper()


def configured_approver() -> str | None:
    a = os.environ.get(APPROVER_ENV, "").strip()
    return a or None


def configured_approver_pubkey() -> str | None:
    k = os.environ.get(APPROVER_PUBKEY_ENV, "").strip()
    return k.upper() or None


def _signer_mismatch(body: dict, approver: str) -> str | None:
    """The Payment must be signed by the approver's own key, not just debited from its account: no Delegate (the hot
    wallet holds Payment delegation from the treasury), no multisig (empty SigningPubKey), no regular key. With
    DESK_APPROVER_PUBKEY set the key must equal it; otherwise it must be the account's master key."""
    if "Delegate" in body:
        return "approval_delegated"
    spk = (body.get("SigningPubKey") or "").upper()
    if not spk:
        return "approval_wrong_signer"
    pinned = configured_approver_pubkey()
    if pinned:
        return None if spk == pinned else "approval_wrong_signer"
    try:
        return None if keypairs.derive_classic_address(spk) == approver else "approval_wrong_signer"
    except Exception:  # noqa: BLE001 - a malformed key is a reject reason, not a 500
        return "approval_wrong_signer"


def verify_approval_payment(tx: dict, expected_hash: str, approver: str | None) -> str | None:
    """Offline check of a `tx` response. Returns a mismatch reason or None when the Payment is a valid approval."""
    if not approver:
        return "approver_unset"
    if tx.get("error"):
        return f"tx_lookup_failed:{tx.get('error')}"
    body = tx.get("tx_json") or tx
    meta = tx.get("meta") or tx.get("metaData") or {}
    if not tx.get("validated"):
        return "approval_not_validated"
    if not isinstance(meta, dict) or meta.get("TransactionResult") != "tesSUCCESS":
        return f"approval_not_success:{meta.get('TransactionResult') if isinstance(meta, dict) else None}"
    if body.get("TransactionType") != "Payment":
        return "approval_not_payment"
    if body.get("Account") != approver:
        return "approval_wrong_account"
    signer = _signer_mismatch(body, approver)
    if signer:
        return signer
    memos = body.get("Memos") or []
    memo = (memos[0].get("Memo") or {}) if memos else {}
    if (memo.get("MemoType") or "").upper() != APPROVAL_MEMO_TYPE:
        return "approval_wrong_memo_type"
    if (memo.get("MemoData") or "").upper() != expected_hash.upper():
        return "approval_hash_mismatch"
    return None


def stnumber_int(v) -> int:
    """PrincipalRequested is an STNumber: decode() gives '60000000' below 1e11 drops and mantissa/exponent form
    ('1e11', '15e10', '123456789012e0') above it (wallet contract v1.7)."""
    m, _, e = str(v).lower().partition("e")
    return int(m) * 10 ** int(e or 0)


def loan_terms_text(blob: str) -> str:
    """The loan-terms Memo text the wallet signs, built from the stored borrower-signed blob (never the request body).
    Byte for byte the wallet's loanTermsText: principal in XRP without trailing zeros, borrower = the LoanSet Account."""
    ls = decode(blob)
    whole, frac = divmod(stnumber_int(ls["PrincipalRequested"]), 1_000_000)
    xrp = f"{whole}.{frac:06d}".rstrip("0") if frac else str(whole)
    return f"approve loan {xrp} XRP to {ls['Account']} {ls['PaymentTotal']} payments"


def verify_loan_terms(tx: dict, blob: str) -> str | None:
    """An approval Payment may carry a second Memo loan-terms; when it does, its ASCII text must match the stored blob.
    Absent = accepted (approvals signed before contract v1.7 still verify)."""
    body = tx.get("tx_json") or tx
    for m in body.get("Memos") or []:
        memo = m.get("Memo") or {}
        if (memo.get("MemoType") or "").upper() != TERMS_MEMO_TYPE:
            continue
        try:
            text = bytes.fromhex(memo.get("MemoData") or "").decode("ascii")
        except ValueError:
            return "terms_mismatch"
        return None if text == loan_terms_text(blob) else "terms_mismatch"
    return None


def fetch_testnet_tx(tx_hash: str, url: str = TESTNET_URL) -> dict:
    """Read a validated tx from testnet (the approval Payment lives there, the loan on devnet)."""
    return JsonRpcClient(url).request(Tx(transaction=tx_hash)).result
