"""Lending desk API (INTERFACES.md §5). `python -m desk` serves 127.0.0.1:${DESK_PORT:-7500}.

The desk holds only the broker key. accounts.json and policy.json are re-read on every request
(the scripted demo opens a new vault each run). Every devnet call goes through the Ledger adapter
(FastAPI dependency get_ledger) so tests inject a fake; the real adapter turns any ledger/transport
error into RuntimeError, which the app maps to 503 ledger_unavailable.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from xrpl.core.addresscodec import is_valid_classic_address
from xrpl.models.requests import AccountTx, LedgerEntry, Tx
from xrpl.models.transactions import CredentialCreate, LoanBrokerCoverDeposit

import auth
import common
import evidence
import policy as pol
import reconcile
import llm
import second_opinion
import setup
from batch import working_capital as wc

HERE = Path(__file__).resolve().parent
ACCOUNTS_PATH = common.ACCOUNTS_PATH
POLICY_PATH = HERE / "policy.json"
REQUESTS_PATH = HERE / "data" / "requests.json"
EXAMPLES_PATH = HERE / "data" / "desk_examples.jsonl"
DEFAULTS_PATH = HERE / "data" / "defaults.json"   # {loanId: default entry}, see save_default()
SWEEPS_PATH = HERE / "data" / "sweeps.json"       # [verified sweep record], keyed by loanPayHash (INTERFACES §9)
UI_ORIGIN = "http://localhost:5175"
MANAGE_ACTIONS = ("impair", "unimpair", "default")
_BLOB = "_signedLoanSet"  # private record key: persisted for approve, never returned
_BATCH = "_signedBatch"   # same for the working-capital Batch blob (INTERFACES §8)
_PRIVATE = (_BLOB, _BATCH)
TF_LOAN_DEFAULT = 0x10000
_META_KEYS = ("coverBeforeDrops", "coverAfterDrops", "coverAbsorbedDrops", "vaultLossDrops", "defaultAmountDrops")
COVER_TOPUP_MAX_DROPS = 100_000_000  # one top-up is at most 100 XRP
SECOND_OPINION_TIMEOUT_S = 20        # Agent 2: a timeout counts as "agree"
_LEND_LOCK = threading.Lock()         # one policy re-check + co-sign at a time, so each re-check sees the previous loan on-ledger
_POLICY_LOCK = threading.Lock()       # PUT /v1/policy writes under it; the pending-cap read + admission run under it


def now() -> int:
    return int(time.time())


# ---- ledger adapter ----------------------------------------------------------
class Ledger:
    """Real devnet adapter. Any failure surfaces as RuntimeError (-> 503), never a refusal."""

    @staticmethod
    def _call(fn, *args):
        try:
            return fn(*args)
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001 - httpx/requests/xrpl/KeyError on a missing node
            raise RuntimeError(f"{type(e).__name__}: {e}") from e

    def build_evidence(self, borrower: str, declared: dict) -> dict:
        return self._call(evidence.build_evidence, borrower, declared)

    def vault_state(self, vault_id: str, loan_broker_id: str) -> dict:
        return self._call(common.vault_state, vault_id, loan_broker_id)

    def list_loans(self, loan_broker_id: str) -> list[dict]:
        return self._call(common.list_loans, loan_broker_id)

    def ledger_index(self) -> int:
        return self._call(common.current_ledger_index)

    def verify_loan_set_blob(self, blob: str, request: dict, accounts: dict, policy: dict) -> str | None:
        return common.verify_loan_set_blob(blob, request, accounts, policy)  # offline decode, no ledger

    def cosign_loan_set(self, blob: str) -> dict:
        return self._call(lambda: common.cosign_loan_set(common.wallet("broker"), blob))

    def loan_manage(self, loan_id: str, action: str) -> dict:
        return self._call(lambda: common.loan_manage(common.wallet("broker"), loan_id, action))

    def verify_working_capital_batch(self, batch_blob: str, loan_blob: str, body: dict, accounts: dict) -> str | None:
        return wc.verify_working_capital_batch(batch_blob, loan_blob, body, accounts)  # offline decode, no ledger

    def submit_batch(self, blob: str) -> dict:
        last = common.decode(blob).get("LastLedgerSequence")
        return self._call(common.submit_blob, blob, last, "Working-capital Batch (borrower-signed, tfAllOrNothing)")

    def unfold_batch(self, batch_hash: str) -> dict | None:
        return self._call(wc.unfold_batch, batch_hash)  # None = unknown hash -> 404

    def broker_cover(self, loan_broker_id: str) -> int:
        """LoanBroker.CoverAvailable in drops, from the validated ledger."""
        return self._call(lambda: common._drops(common.ledger_entry(loan_broker_id).get("CoverAvailable")))

    def cover_deposit(self, loan_broker_id: str, amount_drops: str) -> dict:
        def go():
            w = common.wallet("broker")
            return common.submit_and_wait(LoanBrokerCoverDeposit(
                account=w.address, loan_broker_id=loan_broker_id, amount=amount_drops), w)
        return self._call(go)

    def find_default(self, loan_id: str) -> dict | None:
        """Backfill: the LoanManage(default) of a loan and its cover hit, from devnet. None = not found."""
        return self._call(_find_default, loan_id)

    def fetch_tx(self, tx_hash: str) -> dict | None:
        """A devnet tx (Tx request) or None when the ledger does not know it. Other errors -> RuntimeError (503)."""
        def go():
            res = common._rpc(Tx(transaction=tx_hash))
            if res.get("error") == "txnNotFound":
                return None
            if "error" in res:
                raise RuntimeError(f"tx {tx_hash}: {res.get('error')}")
            return res
        return self._call(go)

    def loan_borrower(self, loan_id: str) -> str | None:
        """Loan.Borrower from the validated ledger; None when there is no such Loan."""
        def go():
            res = common._rpc(LedgerEntry(index=loan_id, ledger_index="validated"))
            if res.get("error") == "entryNotFound":
                return None
            if "error" in res:
                raise RuntimeError(f"ledger_entry {loan_id}: {res.get('error')}")
            node = res.get("node") or {}
            return node.get("Borrower") if node.get("LedgerEntryType") == "Loan" else None
        return self._call(go)

    def account_sequence(self, account: str) -> int:
        from xrpl.models.requests import AccountInfo
        return self._call(lambda: int(common._rpc(AccountInfo(account=account, ledger_index="validated"))["account_data"]["Sequence"]))

    def find_loan_set(self, account: str, sequence: int, loan_broker_id: str | None = None,
                      txn_signature: str | None = None) -> dict | None:
        """The validated LoanSet from `account` with this Sequence for THIS desk's LoanBroker (accounts.json unless
        given), and, when given, the borrower's TxnSignature of the stored blob; a LoanSet with another broker is None."""
        broker_id = (loan_broker_id or load_accounts().get("loanBrokerId") or "").upper()

        def mine(tx: dict) -> bool:
            return ((tx.get("LoanBrokerID") or "").upper() == broker_id
                    and (txn_signature is None or (tx.get("TxnSignature") or "").upper() == txn_signature.upper()))

        def go():
            marker = None
            for _ in range(5):
                kw = {"account": account, "limit": 200, "api_version": 2, **({"marker": marker} if marker else {})}
                res = common._rpc(AccountTx(**kw))
                for item in res.get("transactions", []):
                    tx = item.get("tx_json") or item.get("tx") or {}
                    meta = item.get("meta") or {}
                    if (tx.get("TransactionType") == "LoanSet" and int(tx.get("Sequence", -1)) == int(sequence)
                            and item.get("validated") and mine(tx)):
                        return {"hash": item.get("hash") or tx.get("hash"), "engineResult": meta.get("TransactionResult"),
                                "loanId": common._created(meta).get("Loan")}
                marker = res.get("marker")
                if not marker:
                    break
            return None
        return self._call(go)

    def find_credential(self, subject: str, broker: str) -> dict | None:
        """The broker's kyb-borrower Credential for subject (accepted or not), or None."""
        return self._call(setup.find_credential, subject, broker)

    def create_credential(self, subject: str) -> dict:
        def go():
            w = common.wallet("broker")
            return common.submit_and_wait(CredentialCreate(
                account=w.address, subject=subject, credential_type=evidence.KYB_CREDENTIAL_TYPE), w)
        return self._call(go)

    def fetch_testnet_tx(self, tx_hash: str) -> dict:
        """The Ledger-signed approval Payment lives on testnet (wallet POST /v1/lend/approve), the loan on devnet."""
        return self._call(auth.fetch_testnet_tx, tx_hash)


def default_from_tx(t: dict, loan_id: str) -> dict | None:
    """A defaults.json entry from a tx / account_tx item, iff it is the validated tesSUCCESS
    LoanManage(default) of loan_id whose meta modified the LoanBroker; else None."""
    tx = t.get("tx_json") or t.get("tx") or {}
    meta = t.get("meta") or t.get("metaData") or {}
    if tx.get("TransactionType") != "LoanManage" or str(tx.get("LoanID", "")).upper() != loan_id.upper() \
            or not int(tx.get("Flags", 0)) & TF_LOAN_DEFAULT or not t.get("validated") \
            or not isinstance(meta, dict) or meta.get("TransactionResult") != "tesSUCCESS":
        return None
    lb = next((n["ModifiedNode"] for n in meta.get("AffectedNodes", [])
               if n.get("ModifiedNode", {}).get("LedgerEntryType") == "LoanBroker"), None)
    if lb is None:
        return None
    # CoverAvailable is soeDEFAULT: rippled omits it at 0, so a missing FinalFields value is a drained cover.
    after = lb.get("FinalFields", {}).get("CoverAvailable", "0")
    before = lb.get("PreviousFields", {}).get("CoverAvailable", after)  # absent = cover unchanged
    b, a = common._drops(before), common._drops(after)
    # Depositors' share: the Vault's AssetsTotal drop (absent from PreviousFields = unchanged).
    vault = next((n["ModifiedNode"] for n in meta.get("AffectedNodes", [])
                  if n.get("ModifiedNode", {}).get("LedgerEntryType") == "Vault"), None)
    vault_loss = None
    if vault is not None:
        v_after = vault.get("FinalFields", {}).get("AssetsTotal", "0")
        vault_loss = str(common._drops(vault.get("PreviousFields", {}).get("AssetsTotal", v_after))
                         - common._drops(v_after))
    # Default amount: the Loan's principal before the default zeroed it.
    loan = next((n["ModifiedNode"] for n in meta.get("AffectedNodes", [])
                 if n.get("ModifiedNode", {}).get("LedgerEntryType") == "Loan"
                 and str(n["ModifiedNode"].get("LedgerIndex", "")).upper() == loan_id.upper()), None)
    principal = (loan or {}).get("PreviousFields", {}).get("PrincipalOutstanding")
    date = tx.get("date")
    return {"hash": t.get("hash") or tx.get("hash"), "engineResult": "tesSUCCESS",
            "coverBeforeDrops": str(b), "coverAfterDrops": str(a), "coverAbsorbedDrops": str(b - a),
            "vaultLossDrops": vault_loss,
            "defaultAmountDrops": None if principal is None else str(common._drops(principal)),
            "ts": common.from_ripple(int(date)) if date else now()}


def _find_default(loan_id: str, pages: int = 5) -> dict | None:
    loan = common.ledger_entry(loan_id)
    if loan.get("PreviousTxnID"):  # the default is normally the last tx that touched the Loan
        hit = default_from_tx(common._rpc(Tx(transaction=loan["PreviousTxnID"])), loan_id)
        if hit:
            return hit
    pseudo = common.ledger_entry(loan["LoanBrokerID"])["Account"]  # else the broker pseudo-account history
    marker = None
    for _ in range(pages):
        kw = {"account": pseudo, "limit": 200, **({"marker": marker} if marker else {})}
        res = common._rpc(AccountTx(**kw))
        for item in res.get("transactions", []):
            hit = default_from_tx(item, loan_id)
            if hit:
                return hit
        marker = res.get("marker")
        if not marker:
            break
    return None


def get_ledger() -> Ledger:
    return Ledger()


# ---- config (re-read per request) ----------------------------------------------
def load_accounts() -> dict:
    return json.loads(Path(ACCOUNTS_PATH).read_text())


def load_policy() -> dict:
    return pol.load_policy(POLICY_PATH)


def recheck_policy_now() -> dict:
    """The policy as of the last completed PUT, for the final re-check before a co-sign. Read under _POLICY_LOCK:
    pol.save_policy rewrites policy.json in place (no tmp + replace), so an unlocked read can see half a file."""
    with _POLICY_LOCK:
        return load_policy()


def vault_phase(accounts: dict, t: int) -> tuple[str, int]:
    sub, red = int(accounts.get("subscriptionDate") or 0), int(accounts.get("redemptionDate") or 0)
    phase = "subscription" if t < sub else "redemption" if red and t >= red else "lending"
    return phase, max(0, sub - t)


# ---- defaults.json (LoanManage default + cover hit per loan) --------------------
_defaults_lock = threading.Lock()


def load_defaults() -> dict:
    try:
        d = json.loads(Path(DEFAULTS_PATH).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_default(loan_id: str, entry: dict) -> None:
    """Atomic write (tmp + os.replace, like requests.json)."""
    path = Path(DEFAULTS_PATH)
    with _defaults_lock:
        d = load_defaults()
        d[loan_id] = entry
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, indent=1))
        os.replace(tmp, path)


# ---- sweeps.json (borrower-side auto-repay, INTERFACES §9) -----------------------
_sweeps_lock = threading.Lock()


def load_sweeps() -> list[dict]:
    try:
        d = json.loads(Path(SWEEPS_PATH).read_text())
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def _tx_parts(res: dict) -> tuple[dict, dict]:
    return (res.get("tx_json") or res.get("tx") or res), (res.get("meta") or res.get("metaData") or {})


def verify_sweep(loan_id: str, body: dict, borrower: str, pay: dict | None, income: dict | None) -> str | None:
    """None when the claimed sweep is on the validated ledger as claimed, else the 422 reason.
    LoanPay: validated, LoanID == loan_id, Account == the loan's Borrower, Amount == drops, on-ledger result ==
    the claimed engineResult (a tec LoanPay verifies as a failed record). Income: validated tesSUCCESS Payment to
    the borrower from payer, delivered incomeDrops, with an invoice/x402 memo, in a ledger no later than the LoanPay."""
    if pay is None:
        return "loan_pay_not_found"
    tx, meta = _tx_parts(pay)
    if not pay.get("validated"):
        return "loan_pay_not_validated"
    if tx.get("TransactionType") != "LoanPay":
        return "not_loan_pay"
    if str(tx.get("LoanID", "")).upper() != loan_id.upper():
        return "wrong_loan_id"
    if tx.get("Account") != borrower:
        return "wrong_account"
    if str(tx.get("Amount")) != body["drops"]:
        return "amount_mismatch"
    if meta.get("TransactionResult") != body["engineResult"]:
        return "engine_result_mismatch"
    if income is None:
        return "income_not_found"
    itx, imeta = _tx_parts(income)
    if not income.get("validated"):
        return "income_not_validated"
    if imeta.get("TransactionResult") != "tesSUCCESS":
        return "income_not_success"
    if itx.get("TransactionType") != "Payment":
        return "income_not_payment"
    if itx.get("Destination") != borrower:
        return "income_wrong_destination"
    if itx.get("Account") != body["payer"]:
        return "income_payer_mismatch"
    if str(imeta.get("delivered_amount")) != body["incomeDrops"]:
        return "income_amount_mismatch"
    if not evidence._is_x402_income(itx):
        return "income_no_x402_memo"
    if int(income.get("ledger_index") or 0) > int(pay.get("ledger_index") or 0):
        return "income_after_loan_pay"  # the LoanPay cannot have been paid from income that came later
    return None


# ---- store ---------------------------------------------------------------------
class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.inflight: set[str] = set()
        self.reserved: dict[str, str] = {}   # reservation key -> principalDrops of requests still being decided (auth.py)
        self.records: dict[str, dict] = {}
        if self.path.exists():
            try:
                self.records = {r["id"]: r for r in json.loads(self.path.read_text())}
            except (ValueError, KeyError, TypeError):
                self.records = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(list(self.records.values()), indent=1))
        os.replace(tmp, self.path)

    def next_id(self) -> str:
        n = max((int(i.split("_")[1]) for i in [*self.records, *self.inflight]), default=0) + 1
        return f"lr_{n:04d}"


_store: Store | None = None
_store_lock = threading.Lock()


def store() -> Store:
    """One Store per process: two concurrent first requests must not build two (each with its own lock and
    reservations, which would defeat the pending cap and idempotency). Double-checked under _store_lock."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = Store(REQUESTS_PATH)
    return _store


def apply_second_opinion(decision: str, status: str, reason: str | None, so: dict | None) -> tuple[str, str | None]:
    """The second opinion's effect. It can only tighten: auto -> held, never hold -> auto,
    never refuse -> anything, never an automatic denial. agree / None (timeout, failure) -> no change."""
    rec = so.get("recommendation") if so else None
    if decision == "auto" and rec == "hold":
        return "held", "second_opinion_hold"
    if decision in ("auto", "hold") and rec == "deny":
        return "held", "second_opinion_deny"
    return status, reason


def public(rec: dict) -> dict:
    return {**{k: v for k, v in rec.items() if k not in _PRIVATE}, "notes": rec.get("notes", [])}


def drop_blobs(rec: dict) -> None:
    for k in _PRIVATE:
        rec.pop(k, None)


def expire_if_due(rec: dict, policy: dict, t: int) -> bool:
    if rec["status"] == "held" and rec["id"] not in store().inflight \
            and t >= rec["ts"] + int(policy["holdTimeoutSeconds"]):
        rec.update(status="expired", decidedBy="timeout", reason="hold_timeout")
        drop_blobs(rec)
        common.audit_append({"event": "loan_request_expired", "id": rec["id"]})
        return True
    return False


def expire_all(policy: dict) -> None:
    s, t = store(), now()
    with s.lock:
        if any([expire_if_due(r, policy, t) for r in s.records.values()]):
            s.save()


def example(label: str, method: str, path: str, request, status: int, response) -> None:
    """Append one real request/response pair to data/desk_examples.jsonl (make_evidence renders it)."""
    if isinstance(request, dict) and "signedLoanSet" in request:
        request = {**request, "signedLoanSet": f"<borrower-signed LoanSet blob, {len(request['signedLoanSet'])} hex chars>"}
    if isinstance(request, dict) and isinstance(request.get("signedBatch"), str):
        request = {**request, "signedBatch": f"<borrower-signed Batch blob, {len(request['signedBatch'])} hex chars>"}
    EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EXAMPLES_PATH, "a") as f:
        f.write(json.dumps({"ts": now(), "label": label, "method": method, "path": path,
                            "request": request, "status": status, "response": response}) + "\n")


def fail(status: int, label: str, method: str, path: str, request, detail: dict):
    example(label, method, path, request, status, detail)
    if set(detail) == {"detail"}:
        raise HTTPException(status, detail=detail["detail"])
    raise _Raw(status, detail)


class _Raw(Exception):
    """An error whose body carries more than {"detail"} (409 vault_in_subscription)."""

    def __init__(self, status: int, body: dict):
        self.status, self.body = status, body


# ---- app -----------------------------------------------------------------------
app = FastAPI(title="Lending Desk")
app.add_middleware(CORSMiddleware, allow_origins=[UI_ORIGIN], allow_methods=["*"], allow_headers=["*"])


def reconcile_all(ledger, t: int | None = None) -> list[dict]:
    """Settle every held/auto record whose blob is dead or already landed (restart window). Ledger errors propagate."""
    s, t = store(), now() if t is None else t
    changed = []
    with s.lock:
        for rec in s.records.values():
            action, info = reconcile.reconcile_record(rec, ledger, t)
            if action != "keep":
                changed.append({"id": rec["id"], "action": action, **info})
        if changed:
            s.save()
    for c in changed:
        common.audit_append({"event": "reconciled", **c})
    return changed


@app.on_event("startup")
def _reconcile_on_boot() -> None:
    # the sync xrpl client calls asyncio.run, which cannot run on the server's event loop: reconcile on a thread
    threading.Thread(target=_reconcile_now, daemon=True).start()


def _reconcile_now() -> None:
    try:
        changed = reconcile_all(get_ledger())
        if changed:
            print(f"desk: reconciled {len(changed)} record(s) after restart: {changed}")
    except RuntimeError as e:  # the node is down: nothing settled now; approve re-checks per record
        print(f"desk: reconcile on boot skipped (ledger_unavailable: {e})")


@app.exception_handler(_Raw)
def _raw_handler(_req: Request, exc: _Raw):
    return JSONResponse(exc.body, status_code=exc.status)


@app.exception_handler(RuntimeError)
def _ledger_handler(_req: Request, exc: RuntimeError):
    return JSONResponse({"detail": f"ledger_unavailable: {exc}"}, status_code=503)


class Declared(BaseModel):
    existingDebtDrops: str = Field("0", pattern=r"^\d+$")


class Disbursement(BaseModel):
    supplier: str = Field(pattern=r"^r[1-9A-HJ-NP-Za-km-z]{24,34}$")
    supplierDrops: str = Field(pattern=r"^[1-9]\d*$")
    feeDrops: str = Field(pattern=r"^[1-9]\d*$")
    invoice: str = Field(min_length=1, max_length=64)


class LoanRequestIn(BaseModel):
    borrower: str = Field(pattern=r"^r[1-9A-HJ-NP-Za-km-z]{24,34}$")
    principalDrops: str = Field(pattern=r"^[1-9]\d*$")
    termSeconds: int
    purpose: str = Field(min_length=1, max_length=64)
    declared: Declared = Declared()
    signedLoanSet: str = Field(min_length=2)
    disbursement: Disbursement | None = None   # working capital (§8): both or neither
    signedBatch: str | None = None


class DenyIn(BaseModel):
    reason: str | None = None


class ApproveIn(BaseModel):
    approvalTxHash: str | None = Field(None, pattern=r"^[0-9A-Fa-f]{64}$")  # testnet Payment the Ledger signed


class ManageIn(BaseModel):
    action: str


class NoteIn(BaseModel):
    from_: str = Field(alias="from", min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=500)


_HASH = r"^[0-9A-Fa-f]{64}$"


class SweepIn(BaseModel):
    incomeHash: str = Field(pattern=_HASH)
    incomeDrops: str = Field(pattern=r"^[1-9]\d*$")
    payer: str = Field(pattern=r"^r[1-9A-HJ-NP-Za-km-z]{24,34}$")
    loanId: str = Field(pattern=_HASH)
    loanPayHash: str = Field(pattern=_HASH)
    drops: str = Field(pattern=r"^[1-9]\d*$")
    engineResult: str = Field(min_length=3, max_length=40)
    ledgerIndex: int | None = None
    at: int


class CoverIn(BaseModel):
    amountDrops: str = Field(pattern=r"^\d+$")


class CredentialIn(BaseModel):
    subject: str = Field(pattern=r"^r[1-9A-HJ-NP-Za-km-z]{24,34}$")


@app.get("/v1/llm/cost")
def llm_cost():
    """Model spend on the API-key path (data/llm_cost.jsonl): {spent_usd, budget_usd, calls, last_ts}."""
    return llm.cost_summary()


@app.get("/health")
def health(ledger=Depends(get_ledger)):
    accounts = load_accounts()
    return {"ok": True, "network": "devnet", "broker": accounts["accounts"]["broker"],
            "ledgerIndex": ledger.ledger_index(),
            "approverAccount": auth.configured_approver()}  # set: approve needs a Ledger-signed testnet Payment


@app.post("/v1/loan-requests")
def create_request(body: LoanRequestIn, ledger=Depends(get_ledger)):
    path, raw = "/v1/loan-requests", body.model_dump(exclude_none=True)
    accounts, policy = load_accounts(), load_policy()
    req = {"borrower": body.borrower, "principalDrops": body.principalDrops, "termSeconds": body.termSeconds}
    if not policy["termSecondsMin"] <= body.termSeconds <= policy["termSecondsMax"]:
        fail(422, "loan-request rejected", "POST", path, raw, {"detail": "term_out_of_range"})
    mismatch = ledger.verify_loan_set_blob(body.signedLoanSet, req, accounts, policy)
    if mismatch:
        fail(400, "loan-request rejected", "POST", path, raw, {"detail": mismatch})
    s = store()
    blob_key = auth.blob_key(body.signedLoanSet)
    res_key = blob_key or f"_anon:{uuid.uuid4().hex}"  # an undecodable blob still counts toward the cap
    with s.lock:  # idempotent submit: the same signed blob (Account, Sequence) is the same request
        dup = auth.find_duplicate(s.records, blob_key)
        if dup is None and blob_key in s.reserved:
            fail(409, "loan-request rejected", "POST", path, raw, {"detail": "duplicate_in_progress"})
        if dup is None:
            s.reserved[res_key] = body.principalDrops  # counted by the pending cap until the record is stored
    if dup is not None:
        out = public(dup)
        example("loan-request replayed", "POST", path, raw, 200, out)
        return out
    try:
        return _create_request(body, ledger, path, raw, accounts, policy, req, s, blob_key, res_key)
    finally:
        with s.lock:
            s.reserved.pop(res_key, None)


def _create_request(body: LoanRequestIn, ledger, path: str, raw: dict, accounts: dict, policy: dict, req: dict,
                    s: Store, blob_key: str | None, res_key: str):
    is_wc = body.disbursement is not None or body.signedBatch is not None
    if is_wc:
        mismatch = "batch_mismatch:missing" if body.disbursement is None or not body.signedBatch else \
            ledger.verify_working_capital_batch(body.signedBatch, body.signedLoanSet, raw, accounts)
        if mismatch:
            fail(400, "working-capital rejected", "POST", path, raw, {"detail": mismatch})
    phase, wait = vault_phase(accounts, now())
    if phase == "subscription":
        fail(409, "loan-request rejected", "POST", path, raw,
             {"detail": "vault_in_subscription", "secondsToLending": wait})

    declared = {"purpose": body.purpose, "principalDrops": body.principalDrops,
                "termSeconds": body.termSeconds, "existingDebtDrops": body.declared.existingDebtDrops}
    try:
        ev = ledger.build_evidence(body.borrower, declared)
        vs = ledger.vault_state(accounts["vaultId"], accounts["loanBrokerId"])
    except RuntimeError as e:
        fail(503, "loan-request rejected", "POST", path, raw, {"detail": f"ledger_unavailable: {e}"})
    dis = body.disbursement
    with _POLICY_LOCK, s.lock:  # the cap as of now (a PUT that lowered it has landed), against every other pending
        cap_policy = load_policy()  # the whole policy: a cap refusal is recorded under this hash, not the stale one
        others = {k: v for k, v in s.reserved.items() if k != res_key}
        over_cap = auth.pending_cap_exceeded(s.records, s.inflight, body.principalDrops, cap_policy, others, now())
    if over_cap:
        policy = cap_policy  # 006-desk-auth review C2: the record and audit line carry the policy that refused
    if is_wc and int(dis.supplierDrops) + int(dis.feeDrops) > int(body.principalDrops):
        bd = pol.score_breakdown(ev)  # policy layer: the draw cannot fund its own disbursement -> no tx
        d = {"decision": "refuse", "reason": "batch_unfunded", "score": bd["total"], "breakdown": bd}
    elif over_cap:
        bd = pol.score_breakdown(ev)  # aggregate held + in-flight principal would pass policy.maxPendingDrops
        d = {"decision": "refuse", "reason": "pending_exposure_cap", "score": bd["total"], "breakdown": bd}
    else:
        d = pol.decide({**req, "evidence": ev}, vs, policy)
        if d["decision"] == "auto" and not (ev.get("ledger") or {}).get("hasAcceptedCredential"):
            # no broker-issued KYB Credential on the ledger: a human decides, never an automatic signature
            d = {**d, "decision": "hold", "reason": "no_broker_credential"}

    with s.lock:
        rid = s.next_id()
        s.inflight.add(rid)  # reserves the id while the second opinion runs (next_id skips inflight ids)
    so, so_ms = None, None
    so_off = second_opinion.is_off()  # scripted run: no model call, and the record says so ("off", never null)
    if d["decision"] in ("auto", "hold") and not so_off:  # never on refuse; before any co-sign
        t0 = time.monotonic()
        so = second_opinion.review(ev, d["breakdown"], policy, vs, rid, timeout_s=SECOND_OPINION_TIMEOUT_S)
        so_ms = int((time.monotonic() - t0) * 1000)
    policy_status = {"auto": "auto", "hold": "held", "refuse": "refused"}[d["decision"]]
    status, reason = apply_second_opinion(d["decision"], policy_status, d["reason"], so)
    with s.lock:
        rec = {"id": rid, "ts": now(), "kind": "working_capital" if is_wc else "loan",
               "borrower": body.borrower, "principalDrops": body.principalDrops,
               "termSeconds": body.termSeconds, "purpose": body.purpose, "evidence": ev,
               "breakdown": d["breakdown"], "score": d["score"], "decision": d["decision"],
               "status": status, "reason": reason, "loanId": None, "txHash": None, "engineResult": None,
               "decidedBy": "policy", "memo": so["memo"] if so else None,
               "secondOpinion": "off" if so_off else so, "secondOpinionMs": so_ms, "policyHash": pol.policy_hash(policy),
               "blobKey": blob_key, "loanSetHash": auth.loan_set_hash(body.signedLoanSet), "approvalTxHash": None}
        if is_wc:
            rec["batch"] = {**dis.model_dump(), "hash": None, "engineResult": None, "legs": []}
        if d["decision"] != "refuse":
            rec[_BLOB] = body.signedLoanSet
            if is_wc:
                rec[_BATCH] = body.signedBatch
        if status != "auto":
            s.inflight.discard(rid)
        s.records[rec["id"]] = rec
        s.reserved.pop(res_key, None)  # the record counts itself from here on (held or inflight), never twice
        s.save()
    common.audit_append({"event": "loan_request_decided", "id": rec["id"], "borrower": rec["borrower"],
                         "principalDrops": rec["principalDrops"], "score": rec["score"],
                         "decision": rec["decision"], "reason": d["reason"], "kind": rec["kind"],
                         "policyHash": rec["policyHash"]})
    if so_ms is not None:
        common.audit_append({"event": "second_opinion", "id": rid, "ms": so_ms,
                             "recommendation": so["recommendation"] if so else None,
                             "flags": so["flags"] if so else [], "status": rec["status"], "reason": rec["reason"]})
    if rec["status"] == "auto":
        with _LEND_LOCK:  # the vault may have moved during the second opinion: re-decide on a fresh read first
            try:
                recheck_policy = recheck_policy_now()  # and a PUT may have tightened the policy meanwhile (review C1)
                with s.lock:
                    rec["recheckPolicyHash"] = pol.policy_hash(recheck_policy)
                vs = ledger.vault_state(accounts["vaultId"], accounts["loanBrokerId"])
                recheck = pol.decide({**req, "evidence": ev}, vs, recheck_policy)
            except (RuntimeError, ValueError, OSError) as e:  # node down or policy.json unloadable: a human decides
                rec.setdefault("recheckPolicyHash", None)
                recheck = {"decision": "hold", "reason": f"recheck_unavailable: {e}"}
            if recheck["decision"] == "auto":
                cosign(rec, ledger, ok_status="auto")
        if recheck["decision"] != "auto":
            moved = rec["recheckPolicyHash"] not in (None, rec["policyHash"])  # blocked because the policy changed
            with s.lock:
                rec["status"] = "held" if recheck["decision"] == "hold" else "refused"
                rec["reason"] = "policy_changed_mid_flight" if moved else recheck["reason"]
                if rec["status"] == "refused":
                    drop_blobs(rec)
                s.inflight.discard(rid)
                s.save()
            common.audit_append({"event": "auto_recheck_blocked", "id": rid, "status": rec["status"],
                                 "reason": rec["reason"], "recheckReason": recheck["reason"],
                                 "policyHash": rec["policyHash"], "recheckPolicyHash": rec["recheckPolicyHash"]})
    out = public(rec)
    example(f"{'working-capital' if is_wc else 'loan-request'} {rec['status']}", "POST", path, raw, 200, out)
    return out


def cosign(rec: dict, ledger, ok_status: str) -> None:
    """Co-sign the stored blob and submit; rec id must already be in store().inflight.
    Working capital: only after the LoanSet is tesSUCCESS, submit the stored Batch and unfold its legs."""
    s = store()
    try:
        res = ledger.cosign_loan_set(rec[_BLOB])
        err = None
    except RuntimeError as e:
        res, err = {}, f"ledger_unavailable: {e}"
    loan_ok = res.get("engineResult") == "tesSUCCESS" and res.get("validated", True)
    batch_err = submit_batch(rec, ledger) if loan_ok and rec.get(_BATCH) else None
    with s.lock:
        s.inflight.discard(rec["id"])
        rec.update(txHash=res.get("hash"), engineResult=res.get("engineResult"), loanId=res.get("loanId"))
        if not loan_ok:
            rec.update(status="failed", reason=err or res.get("engineResult") or "not_validated")
        elif batch_err:
            rec.update(status="failed", reason=f"batch:{batch_err}")  # the loan exists; loanId stays on the record
        else:
            rec["status"] = ok_status
        drop_blobs(rec)
        s.save()
    common.audit_append({"event": "loan_set_cosigned", "id": rec["id"], "status": rec["status"],
                         "hash": rec["txHash"], "engineResult": rec["engineResult"],
                         "loanId": rec["loanId"], "reason": rec["reason"] if rec["status"] == "failed" else None})


def submit_batch(rec: dict, ledger) -> str | None:
    """Submit the stored all-or-nothing Batch, fill rec["batch"]; None if every leg is tesSUCCESS, else the error.
    Outer tesSUCCESS alone is not success: a failed all-or-nothing Batch is tesSUCCESS with no inner applied."""
    b = rec["batch"]
    try:
        res = ledger.submit_batch(rec[_BATCH])
    except RuntimeError as e:
        err = f"ledger_unavailable: {e}"
    else:
        b.update(hash=res.get("hash"), engineResult=res.get("engineResult"))
        err = None if res.get("engineResult") == "tesSUCCESS" and res.get("validated", True) \
            else res.get("engineResult") or "not_validated"
        if res.get("hash") and res.get("validated", True):
            try:
                u = ledger.unfold_batch(res["hash"])
            except RuntimeError as e:
                u, err = None, err or f"legs_unknown: {e}"
            b["legs"] = (u or {}).get("legs", [])
            bad = [l["result"] for l in b["legs"] if l.get("result") != "tesSUCCESS"]
            err = err or (bad[0] if bad else None) or (None if b["legs"] else "legs_unknown")
    common.audit_append({"event": "batch_submitted", "id": rec["id"], "hash": b["hash"],
                         "engineResult": b["engineResult"], "legs": [l.get("result") for l in b["legs"]],
                         "error": err})
    return err


@app.get("/v1/loan-requests")
def list_requests():
    expire_all(load_policy())
    recs = sorted(store().records.values(), key=lambda r: r["id"], reverse=True)
    return {"requests": [public(r) for r in recs]}


def _get(rid: str) -> dict:
    rec = store().records.get(rid)
    if rec is None:
        raise HTTPException(404, detail="unknown_request")
    return rec


@app.get("/v1/loan-requests/{rid}")
def get_request(rid: str):
    expire_all(load_policy())
    return public(_get(rid))


def _loan_set_hash(rec: dict) -> str | None:
    """Records stored before the auth change have no loanSetHash: derive it from the held blob."""
    return rec.get("loanSetHash") or (auth.loan_set_hash(rec[_BLOB]) if rec.get(_BLOB) else None)


@app.get("/v1/loan-requests/{rid}/signed-loan-set", dependencies=[Depends(auth.require_operator)])
def signed_loan_set(rid: str):
    """Operator-only: the borrower-signed blob of a HELD request, for the wallet's /v1/lend/approve loanSetBlob
    (the dashboard renders the loan terms above the 1-drop approval Payment). Never on any other status."""
    expire_all(load_policy())
    s = store()
    with s.lock:
        rec = _get(rid)
        if rec["status"] != "held" or not rec.get(_BLOB):
            raise HTTPException(409, detail=f"not_held: {rec['status']}")
        return {"id": rid, "loanSetHash": _loan_set_hash(rec), "signedLoanSet": rec[_BLOB]}


@app.post("/v1/loan-requests/{rid}/approve", dependencies=[Depends(auth.require_operator)])
def approve(rid: str, body: ApproveIn | None = None, ledger=Depends(get_ledger)):
    path = f"/v1/loan-requests/{rid}/approve"
    accounts, policy = load_accounts(), load_policy()
    expire_all(policy)
    s = store()
    approver = auth.configured_approver()
    approval_hash = body.approvalTxHash.upper() if body and body.approvalTxHash else None
    if approver and not approval_hash:  # DESK_APPROVER_ACCOUNT set: only the Ledger-signed Payment approves
        example("approve rejected", "POST", path, {}, 422, {"detail": "approval_tx_required"})
        raise HTTPException(422, detail="approval_tx_required")

    def held_or_409() -> dict:
        rec = _get(rid)
        if rec["status"] != "held" or rid in s.inflight:
            busy = rid in s.inflight
            detail = "approve_in_progress" if busy else f"not_held: {rec['status']}"
            example("approve rejected", "POST", path, {}, 409, {"detail": detail})
            raise HTTPException(409, detail=detail)
        return rec

    with s.lock:
        loan_set_hash = _loan_set_hash(held_or_409())
    if approver:  # testnet read outside the store lock; the held check is repeated under it below
        approval_tx = ledger.fetch_testnet_tx(approval_hash)
        mismatch = auth.verify_approval_payment(approval_tx, loan_set_hash or "", approver)
        if not mismatch and _get(rid).get(_BLOB):
            terms = auth.verify_loan_terms(approval_tx, _get(rid)[_BLOB])
            if terms:  # the human approved different terms than the blob the desk would co-sign
                common.audit_append({"event": "approve_blocked", "id": rid, "reason": terms,
                                     "approvalTxHash": approval_hash, "policyHash": _get(rid).get("policyHash"),
                                     "recheckPolicyHash": pol.policy_hash(policy)})
                example("approve rejected", "POST", path, {"approvalTxHash": approval_hash}, 422, {"detail": terms})
                raise HTTPException(422, detail=terms)
        if mismatch:
            rec = _get(rid)
            common.audit_append({"event": "approve_blocked", "id": rid, "reason": mismatch,
                                 "approvalTxHash": approval_hash, "policyHash": rec.get("policyHash"),
                                 "recheckPolicyHash": pol.policy_hash(policy)})
            example("approve rejected", "POST", path, {"approvalTxHash": approval_hash}, 409, {"detail": mismatch})
            raise HTTPException(409, detail=mismatch)
    with s.lock:
        rec = _get(rid)
        if expire_if_due(rec, policy, now()):  # the hold may have run out during the testnet read
            s.save()
        action, info = reconcile.reconcile_record(rec, ledger, now())  # dead or already-landed blob: never co-sign it
        if action != "keep":
            s.save()
            common.audit_append({"event": "reconciled", "id": rid, "action": action, **info})
            detail = f"already_landed:{info.get('hash')}" if action == "landed" else rec["reason"]
            example("approve rejected", "POST", path, {}, 409, {"detail": detail})
            raise HTTPException(409, detail=detail)
        rec = held_or_409()
        s.inflight.add(rid)
    with _LEND_LOCK:  # same serialization as the auto path: re-check and co-sign as one step
        try:
            recheck_policy = recheck_policy_now()  # not the policy read before the testnet lookup (review C1)
            recheck_hash = pol.policy_hash(recheck_policy)
            vs = ledger.vault_state(accounts["vaultId"], accounts["loanBrokerId"])
            recheck = pol.decide({"principalDrops": rec["principalDrops"], "evidence": rec["evidence"]}, vs,
                                 recheck_policy)
        except BaseException:
            with s.lock:
                s.inflight.discard(rid)
            raise
        if recheck["decision"] == "refuse":
            with s.lock:
                s.inflight.discard(rid)
            moved = rec.get("policyHash") not in (None, recheck_hash)
            reason = "policy_changed_mid_flight" if moved else recheck["reason"]
            common.audit_append({"event": "approve_blocked", "id": rid, "reason": reason,
                                 "recheckReason": recheck["reason"], "policyHash": rec.get("policyHash"),
                                 "recheckPolicyHash": recheck_hash})
            example("approve blocked", "POST", path, {}, 409, {"detail": reason})
            raise HTTPException(409, detail=reason)
        with s.lock:
            rec["decidedBy"] = "ledger" if approver else "human"
            rec["approvedBy"] = approver or "operator"  # the Ledger account whose Payment approved, or the token holder
            rec["approvedAt"] = now()
            rec["approvalTxHash"] = approval_hash
            rec["recheckPolicyHash"] = recheck_hash
        # the record keeps the hash it was decided under; the approve re-check's policy is logged beside it
        common.audit_append({"event": "loan_request_approved", "id": rid, "policyHash": rec.get("policyHash"),
                             "recheckPolicyHash": recheck_hash, "decidedBy": rec["decidedBy"],
                             "approvedBy": rec["approvedBy"], "approvedAt": rec["approvedAt"],
                             "approvalTxHash": approval_hash})
        cosign(rec, ledger, ok_status="approved")
    out = public(rec)
    wc_label = "working-capital " if rec.get("kind") == "working_capital" else ""
    example(f"{wc_label}approve {rec['status']}", "POST", path, {}, 200, out)
    return out


@app.post("/v1/loan-requests/{rid}/deny", dependencies=[Depends(auth.require_operator)])
def deny(rid: str, body: DenyIn | None = None):
    path = f"/v1/loan-requests/{rid}/deny"
    expire_all(load_policy())
    s = store()
    with s.lock:
        rec = _get(rid)
        if rec["status"] != "held" or rid in s.inflight:
            raise HTTPException(409, detail=f"not_held: {rec['status']}")
        rec.update(status="denied", decidedBy="human", reason=(body.reason if body else None) or "denied_by_human")
        drop_blobs(rec)
        s.save()
    common.audit_append({"event": "loan_request_denied", "id": rid, "reason": rec["reason"]})
    out = public(rec)
    example("deny", "POST", path, body.model_dump() if body else {}, 200, out)
    return out


@app.post("/v1/loan-requests/{rid}/notes", dependencies=[Depends(auth.require_operator_unless_local)])
def add_note(rid: str, body: NoteIn):
    """Append-only agent notes. Display only: no decision path reads them, and they change no other field."""
    s = store()
    with s.lock:
        rec = _get(rid)
        rec.setdefault("notes", []).append({"from": body.from_, "text": body.text, "ts": now()})
        s.save()
    return public(rec)


@app.post("/v1/loans/{loan_id}/manage", dependencies=[Depends(auth.require_operator)])
def manage(loan_id: str, body: ManageIn, ledger=Depends(get_ledger)):
    if body.action not in MANAGE_ACTIONS:
        raise HTTPException(422, detail="action must be impair|unimpair|default")
    lb_id = load_accounts()["loanBrokerId"] if body.action == "default" else None
    before = ledger.broker_cover(lb_id) if lb_id else None
    res = ledger.loan_manage(loan_id, body.action)
    out = {"loanId": loan_id, "action": body.action, "hash": res.get("hash"), "engineResult": res.get("engineResult")}
    if lb_id:
        try:  # the default already happened: a failed read must not turn it into a 503
            after = ledger.broker_cover(lb_id)
        except RuntimeError:
            after = None
        out.update(coverBeforeDrops=str(before), coverAfterDrops=None if after is None else str(after),
                   coverAbsorbedDrops=None if after is None else str(before - after),
                   vaultLossDrops=None, defaultAmountDrops=None)
        if res.get("engineResult") == "tesSUCCESS" and res.get("validated", True):
            try:  # the tx meta is exact and carries the depositors' loss; a failed read stays null
                meta = ledger.find_default(loan_id)
            except RuntimeError:
                meta = None
            if meta:
                out.update({k: meta[k] for k in _META_KEYS})
            if out["coverAbsorbedDrops"] is not None:
                entry = {k: out[k] for k in ("hash", "engineResult", "coverBeforeDrops",
                                             "coverAfterDrops", "coverAbsorbedDrops")}
                if meta:
                    entry |= {k: meta[k] for k in ("vaultLossDrops", "defaultAmountDrops")}
                save_default(loan_id, entry | {"ts": now()})
        # cover unknown: nothing stored; GET /v1/loans backfills it from the tx meta
        # meta unknown: stored without vaultLossDrops; GET /v1/loans backfills those fields once
    common.audit_append({"event": "loan_manage", **out})
    example(f"loan {body.action}", "POST", f"/v1/loans/{loan_id}/manage", body.model_dump(), 200, out)
    return out


@app.post("/v1/loans/{loan_id}/sweeps")
def post_sweep(loan_id: str, body: SweepIn, ledger=Depends(get_ledger)):
    """Borrower's sweeper reports an auto-repay LoanPay (INTERFACES §9). No token: nothing in the body is trusted,
    every field is checked on the validated ledger before it is stored. Idempotent on loanPayHash."""
    path, raw = f"/v1/loans/{loan_id}/sweeps", body.model_dump()
    key = body.loanPayHash.upper()

    def stored() -> dict | None:
        return next((r for r in load_sweeps() if r["loanPayHash"] == key), None)

    if body.loanId.upper() != loan_id.upper():
        fail(422, "sweep rejected", "POST", path, raw, {"detail": "loan_id_mismatch"})
    with _sweeps_lock:
        dup = stored()
    if dup is not None:  # idempotent: the verified record, whatever else this body claims
        if dup["loanId"].upper() != loan_id.upper():
            fail(422, "sweep rejected", "POST", path, raw, {"detail": "wrong_loan_id"})
        return dup
    borrower = ledger.loan_borrower(loan_id)
    if not borrower:
        fail(422, "sweep rejected", "POST", path, raw, {"detail": "unknown_loan"})
    pay = ledger.fetch_tx(key)
    income = ledger.fetch_tx(body.incomeHash.upper()) if pay is not None else None
    why = verify_sweep(loan_id, raw, borrower, pay, income)
    if why:
        fail(422, "sweep rejected", "POST", path, raw, {"detail": why})
    ok = body.engineResult == "tesSUCCESS"
    ptx = _tx_parts(pay)[0]
    rec = {"loanId": ptx["LoanID"], "borrower": borrower, "loanPayHash": key,
           "incomeHash": body.incomeHash.upper(), "incomeDrops": body.incomeDrops, "payer": body.payer,
           "drops": body.drops, "engineResult": body.engineResult,
           "status": "repaid" if ok else f"failed: {body.engineResult}",
           "ledgerIndex": pay.get("ledger_index"), "at": common.from_ripple(ptx["date"]), "verifiedAt": now()}
    with _sweeps_lock:
        dup = stored()
        if dup is not None:
            return dup
        rows = load_sweeps() + [rec]
        p = Path(SWEEPS_PATH)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, indent=1))
        os.replace(tmp, p)
    common.audit_append({"event": "loan_swept", **{k: rec[k] for k in (
        "loanId", "loanPayHash", "incomeHash", "incomeDrops", "drops", "engineResult", "status")}})
    example(f"sweep {'repaid' if ok else 'failed'}", "POST", path, raw, 200, rec)
    return rec


@app.get("/v1/loans")
def loans(ledger=Depends(get_ledger)):
    accounts = load_accounts()
    by_loan = {r["loanId"]: r["id"] for r in store().records.values() if r.get("loanId")}
    sweeps: dict[str, list] = {}
    for r in sorted(load_sweeps(), key=lambda r: r["at"]):
        sweeps.setdefault(r["loanId"].upper(), []).append(r)
    items = ledger.list_loans(accounts["loanBrokerId"])
    stored = load_defaults()
    out = []
    for i in items:
        d = stored.get(i["loanId"])
        if d is None and i.get("status") == "defaulted":
            try:  # backfill once from devnet; a failure is null for this poll and retried on the next
                d = ledger.find_default(i["loanId"])
            except RuntimeError:
                d = None
            if d:
                save_default(i["loanId"], d)
        elif d is not None and "vaultLossDrops" not in d:
            # an entry from before the depositor-loss fields: read the meta once; a miss stores
            # nulls so it is not retried, a failure keeps the entry and retries on the next poll
            try:
                hit = ledger.find_default(i["loanId"])
            except RuntimeError:
                hit = False
            if hit is not False:
                d = {**d, **(hit or {"vaultLossDrops": None, "defaultAmountDrops": None})}
                save_default(i["loanId"], d)
        out.append({**i, "requestId": by_loan.get(i["loanId"]), "default": d or None,
                    "sweeps": sweeps.get(i["loanId"].upper(), [])})
    return {"loans": out, "ledgerIndex": ledger.ledger_index()}


_cover_busy = threading.Lock()


@app.post("/v1/broker/cover", dependencies=[Depends(auth.require_operator)])
def broker_cover(body: CoverIn, ledger=Depends(get_ledger)):
    """LoanBrokerCoverDeposit signed by the broker key inside the desk (first-loss cover top-up)."""
    path, raw = "/v1/broker/cover", body.model_dump()
    amount = int(body.amountDrops)
    if not 0 < amount <= COVER_TOPUP_MAX_DROPS:
        fail(422, "cover top-up rejected", "POST", path, raw, {"detail": "amount_out_of_range"})
    if not _cover_busy.acquire(blocking=False):
        fail(409, "cover top-up rejected", "POST", path, raw, {"detail": "cover_deposit_in_progress"})
    try:
        lb_id = load_accounts()["loanBrokerId"]
        try:
            before = ledger.broker_cover(lb_id)
            res = ledger.cover_deposit(lb_id, str(amount))
        except RuntimeError as e:
            common.audit_append({"event": "broker_cover_deposit_failed", "amountDrops": str(amount), "error": str(e)})
            fail(503, "cover top-up failed", "POST", path, raw, {"detail": f"ledger_unavailable: {e}"})
        try:  # the deposit is on the ledger already: an unreadable after-value is null, not a 503
            after = ledger.broker_cover(lb_id)
        except RuntimeError:
            after = None
    finally:
        _cover_busy.release()
    out = {"hash": res.get("hash"), "engineResult": res.get("engineResult"),
           "coverBeforeDrops": str(before), "coverAfterDrops": None if after is None else str(after)}
    common.audit_append({"event": "broker_cover_deposit", "amountDrops": str(amount), **out})
    example(f"cover top-up {out['engineResult']}", "POST", path, raw, 200, out)
    return out


_credential_busy = threading.Lock()


@app.post("/v1/broker/credentials", dependencies=[Depends(auth.require_operator)])
def broker_credential(body: CredentialIn, ledger=Depends(get_ledger)):
    """The broker vets a borrower: CredentialCreate type kyb-borrower for subject, signed inside the desk. The subject
    still signs CredentialAccept itself. Idempotent: 409 credential_exists when this broker already issued one."""
    path, raw = "/v1/broker/credentials", body.model_dump()
    if not is_valid_classic_address(body.subject):
        fail(422, "credential rejected", "POST", path, raw, {"detail": "invalid_subject"})
    broker = load_accounts()["accounts"]["broker"]
    with _credential_busy:  # one lookup + create at a time, so two presses cannot issue twice
        if ledger.find_credential(body.subject, broker) is not None:
            fail(409, "credential rejected", "POST", path, raw, {"detail": "credential_exists"})
        res = ledger.create_credential(body.subject)
    out = {"hash": res.get("hash"), "engineResult": res.get("engineResult")}
    common.audit_append({"event": "broker_credential_create", "subject": body.subject, **out})
    example(f"credential {out['engineResult']}", "POST", path, raw, 200, out)
    return out


_batch_examples: set[str] = set()


@app.get("/v1/batches/{batch_hash}")
def get_batch(batch_hash: str, ledger=Depends(get_ledger)):
    path = f"/v1/batches/{batch_hash}"
    out = ledger.unfold_batch(batch_hash) if len(batch_hash) == 64 else None
    first = path not in _batch_examples  # the UI may poll; one example per hash is enough
    _batch_examples.add(path)
    if out is None:
        if first:
            example("batch unknown", "GET", path, None, 404, {"detail": "unknown_batch"})
        raise HTTPException(404, detail="unknown_batch")
    if first:
        example("batch unfold", "GET", path, None, 200, out)
    return out


@app.get("/v1/vault")
def vault(ledger=Depends(get_ledger)):
    accounts, policy = load_accounts(), load_policy()
    phase, wait = vault_phase(accounts, now())
    vs = ledger.vault_state(accounts["vaultId"], accounts["loanBrokerId"])
    return {**vs, "accounts": accounts["accounts"], "setupTx": accounts.get("setupTx", {}), "policy": policy,
            "phase": phase, "secondsToLending": wait}


@app.get("/v1/policy")
def get_policy():
    return load_policy()


@app.put("/v1/policy", dependencies=[Depends(auth.require_operator)])
def put_policy(body: dict = Body(...)):
    try:
        with _POLICY_LOCK:  # serialized with the pending-cap admission in create_request
            saved = pol.save_policy(body, POLICY_PATH)
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    common.audit_append({"event": "policy_updated", "policy": saved, "policyHash": pol.policy_hash(saved)})
    return saved


def load_auth_env() -> None:
    """lending/.env, unless the shell set it. DESK_APPROVER_ACCOUNT=off in the shell turns the Ledger approval gate off
    for a scripted run (approve is then decidedBy=human); 'off' means unset, anything else is an address.
    SECOND_OPINION=off in the shell skips the model for a scripted run (records store secondOpinion "off"); it is read
    from the shell only, never from lending/.env, so a stray line there cannot turn the model off for a normal start."""
    for k in (auth.TOKEN_ENV, auth.APPROVER_ENV, auth.APPROVER_PUBKEY_ENV):
        if k not in os.environ and common.read_env().get(k):  # an empty shell value turns it off
            os.environ[k] = common.read_env()[k]
    if os.environ.get(auth.APPROVER_ENV, "").strip().lower() == "off":
        os.environ[auth.APPROVER_ENV] = ""
        print("approver gate OFF (scripted run)", flush=True)
    if second_opinion.is_off():
        print("second opinion OFF (scripted run)", flush=True)


if __name__ == "__main__":
    import uvicorn

    load_auth_env()

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("DESK_PORT", "7500")))
