"""auth.py: operator token, pending-exposure cap, idempotency key, Ledger approval token (no network).
The desk-wiring tests at the bottom are skipped until desk.py imports auth; they turn on by
themselves once it does."""
import copy
import hashlib
import json
from dataclasses import replace

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from xrpl.core.binarycodec import decode, encode
from xrpl.transaction import sign
from xrpl.wallet import Wallet

import auth
import common
import policy as pol

XRP = 1_000_000
LB = "E43DA4D38D7DA816256CA4947839187C41A113FC81AB5A3568B2C7BF7CB1CC91"
APPROVER_KEY = Wallet.create()   # synthetic device key: approval fixtures carry its SigningPubKey (R2 signer check)
APPROVER = APPROVER_KEY.address


def signed_blob(borrower: Wallet, broker: Wallet, principal_xrp=10, sequence=5) -> str:
    tx = common.build_loan_set(borrower.address, LB, broker.address, str(principal_xrp * XRP), 270,
                               pol.DEFAULT_POLICY["interestRateBps"] * 10)
    return encode(sign(replace(tx, sequence=sequence, last_ledger_sequence=1000), borrower).to_xrpl())


# ---- 1. operator token --------------------------------------------------------------
def tiny_app() -> FastAPI:
    app = FastAPI()

    @app.post("/op", dependencies=[Depends(auth.require_operator)])
    def op():
        return {"ok": True}

    @app.post("/notes", dependencies=[Depends(auth.require_operator_unless_local)])
    def notes():
        return {"ok": True}

    return app


def test_token_fails_closed_when_unset(monkeypatch):
    monkeypatch.delenv(auth.TOKEN_ENV, raising=False)
    c = TestClient(tiny_app())
    assert c.post("/op").status_code == 503
    assert c.post("/op", headers={auth.TOKEN_HEADER: "anything"}).json() == {"detail": "operator_token_unset"}


def test_token_required_and_checked(monkeypatch):
    monkeypatch.setenv(auth.TOKEN_ENV, "s3cret")
    c = TestClient(tiny_app())
    assert c.post("/op").status_code == 401
    assert c.post("/op", headers={auth.TOKEN_HEADER: "wrong"}).json() == {"detail": "operator_token_required"}
    assert c.post("/op", headers={auth.TOKEN_HEADER: "s3cret"}).status_code == 200
    assert not auth.token_ok("")
    assert not auth.token_ok(None)


def test_notes_local_exempt_remote_needs_token(monkeypatch):
    monkeypatch.setenv(auth.TOKEN_ENV, "s3cret")
    local = TestClient(tiny_app())  # TestClient's default client host is "testclient" (loopback stand-in)
    assert local.post("/notes").status_code == 200
    remote = TestClient(tiny_app(), client=("10.0.0.7", 51234))
    assert remote.post("/notes").status_code == 401
    assert remote.post("/notes", headers={auth.TOKEN_HEADER: "s3cret"}).status_code == 200


def test_is_local_hosts():
    class R:
        def __init__(self, host):
            self.client = type("C", (), {"host": host})()
    assert auth.is_local(R("127.0.0.1")) and auth.is_local(R("::1"))
    assert not auth.is_local(R("203.0.113.9"))
    assert not auth.is_local(type("R", (), {"client": None})())


# ---- 2. pending-exposure cap ------------------------------------------------------
def recs(*items):
    return {r["id"]: r for r in items}


def test_pending_exposure_counts_held_and_inflight():
    r = recs({"id": "lr_0001", "status": "held", "principalDrops": str(60 * XRP)},
             {"id": "lr_0002", "status": "auto", "principalDrops": str(10 * XRP)},
             {"id": "lr_0003", "status": "auto", "principalDrops": str(15 * XRP)},
             {"id": "lr_0004", "status": "denied", "principalDrops": str(99 * XRP)},
             {"id": "lr_0005", "status": "expired", "principalDrops": str(99 * XRP)})
    assert auth.pending_exposure_drops(r, set()) == 60 * XRP
    assert auth.pending_exposure_drops(r, {"lr_0003"}) == 75 * XRP   # auto still co-signing counts


def test_pending_cap():
    r = recs({"id": "lr_0001", "status": "held", "principalDrops": str(60 * XRP)})
    assert not auth.pending_cap_exceeded(r, set(), 10 * XRP, {"maxPendingDrops": "0"})          # 0 = off
    assert not auth.pending_cap_exceeded(r, set(), 10 * XRP, {})                                  # key absent = off
    assert not auth.pending_cap_exceeded(r, set(), 40 * XRP, {"maxPendingDrops": str(100 * XRP)})
    assert auth.pending_cap_exceeded(r, set(), 41 * XRP, {"maxPendingDrops": str(100 * XRP)})
    assert auth.pending_cap_exceeded({}, set(), 101 * XRP, {"maxPendingDrops": str(100 * XRP)})


# ---- 3. idempotency key ---------------------------------------------------------------
def test_blob_key_is_account_and_sequence():
    borrower, broker = Wallet.create(), Wallet.create()
    blob = signed_blob(borrower, broker, sequence=5)
    assert auth.blob_key(blob) == f"{borrower.address}:5"
    assert auth.blob_key(signed_blob(borrower, broker, sequence=6)) == f"{borrower.address}:6"
    assert auth.blob_key(signed_blob(borrower, broker, principal_xrp=60, sequence=5)) == f"{borrower.address}:5"
    assert auth.blob_key("ZZ") is None and auth.blob_key("") is None


def test_blob_key_uses_ticket_when_sequence_is_zero():
    borrower, broker = Wallet.create(), Wallet.create()
    tx = common.build_loan_set(borrower.address, LB, broker.address, str(10 * XRP), 270, 8000)
    blob = encode(sign(replace(tx, sequence=0, ticket_sequence=77, last_ledger_sequence=1000), borrower).to_xrpl())
    assert auth.blob_key(blob) == f"{borrower.address}:77"


def test_find_duplicate():
    r = recs({"id": "lr_0001", "status": "held", "blobKey": "rA:5"}, {"id": "lr_0002", "status": "auto"})
    assert auth.find_duplicate(r, "rA:5")["id"] == "lr_0001"
    assert auth.find_duplicate(r, "rA:6") is None
    assert auth.find_duplicate(r, None) is None


# ---- 4. Ledger approval token --------------------------------------------------------
def approval_tx(h: str, **over) -> dict:
    tx = {"TransactionType": "Payment", "Account": APPROVER, "Destination": "rUPNkALm1111111111111111111111111",
          "Amount": "1", "Memos": [{"Memo": {"MemoType": auth.APPROVAL_MEMO_TYPE, "MemoData": h}}],
          "SigningPubKey": APPROVER_KEY.public_key}
    out = {"validated": True, "meta": {"TransactionResult": "tesSUCCESS"}, "tx_json": tx, "hash": "F" * 64}
    out.update(over)
    return out


def test_loan_set_hash_is_sha256_of_blob_bytes():
    borrower, broker = Wallet.create(), Wallet.create()
    blob = signed_blob(borrower, broker)
    assert auth.loan_set_hash(blob) == hashlib.sha256(bytes.fromhex(blob)).hexdigest().upper()
    assert len(auth.loan_set_hash(blob)) == 64


def test_verify_approval_payment_accepts_the_wallet_shape():
    h = "AB" * 32
    assert auth.verify_approval_payment(approval_tx(h), h, APPROVER) is None
    assert auth.verify_approval_payment(approval_tx(h.lower()), h, APPROVER) is None     # case-insensitive memo
    assert auth.verify_approval_payment(approval_tx(h), h.lower(), APPROVER) is None


@pytest.mark.parametrize("over,reason", [
    ({"validated": False}, "approval_not_validated"),
    ({"meta": {"TransactionResult": "tecUNFUNDED_PAYMENT"}}, "approval_not_success:tecUNFUNDED_PAYMENT"),
    ({"error": "txnNotFound"}, "tx_lookup_failed:txnNotFound"),
])
def test_verify_approval_payment_rejects_bad_tx(over, reason):
    h = "AB" * 32
    assert auth.verify_approval_payment(approval_tx(h, **over), h, APPROVER) == reason


def test_verify_approval_payment_rejects_wrong_fields():
    h = "AB" * 32
    t = approval_tx(h)
    wrong_acct = copy.deepcopy(t); wrong_acct["tx_json"]["Account"] = "rSomeoneElse"
    assert auth.verify_approval_payment(wrong_acct, h, APPROVER) == "approval_wrong_account"
    other_hash = approval_tx("CD" * 32)
    assert auth.verify_approval_payment(other_hash, h, APPROVER) == "approval_hash_mismatch"
    wrong_type = copy.deepcopy(t); wrong_type["tx_json"]["Memos"][0]["Memo"]["MemoType"] = "696E766F696365"  # "invoice"
    assert auth.verify_approval_payment(wrong_type, h, APPROVER) == "approval_wrong_memo_type"
    no_memo = copy.deepcopy(t); no_memo["tx_json"].pop("Memos")
    assert auth.verify_approval_payment(no_memo, h, APPROVER) == "approval_wrong_memo_type"
    not_payment = copy.deepcopy(t); not_payment["tx_json"]["TransactionType"] = "TrustSet"
    assert auth.verify_approval_payment(not_payment, h, APPROVER) == "approval_not_payment"
    assert auth.verify_approval_payment(t, h, None) == "approver_unset"


def test_verify_accepts_api_v1_tx_shape():
    """rippled api_version 1 puts the fields at the top level instead of tx_json."""
    h = "AB" * 32
    t = approval_tx(h)
    flat = {**t["tx_json"], "validated": True, "meta": t["meta"]}
    assert auth.verify_approval_payment(flat, h, APPROVER) is None


# ---- desk wiring (active once desk.py is wired to auth) ------------------------------------
import desk  # noqa: E402

wired = pytest.mark.skipif(not hasattr(desk, "auth"), reason="desk.py not wired to auth")


@pytest.fixture
def denv(tmp_path, monkeypatch):
    from tests.test_desk import FakeLedger, T0
    monkeypatch.setenv(auth.TOKEN_ENV, "tok")
    monkeypatch.setenv(auth.APPROVER_ENV, APPROVER)
    accounts = {"network": "devnet", "accounts": {"broker": "rBroker", "depositorA": "rA", "depositorB": "rB",
                                                   "borrower": "rGoodSmallFixture"},
                "vaultId": "V", "loanBrokerId": "LB", "shareMptId": "S", "subscriptionDate": 0, "redemptionDate": 0}
    (tmp_path / "accounts.json").write_text(json.dumps(accounts))
    (tmp_path / "policy.json").write_text(json.dumps(pol.DEFAULT_POLICY))
    monkeypatch.setattr(desk, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(desk, "POLICY_PATH", tmp_path / "policy.json")
    monkeypatch.setattr(desk, "REQUESTS_PATH", tmp_path / "data" / "requests.json")
    monkeypatch.setattr(desk, "EXAMPLES_PATH", tmp_path / "data" / "desk_examples.jsonl")
    monkeypatch.setattr(desk, "DEFAULTS_PATH", tmp_path / "data" / "defaults.json")
    monkeypatch.setattr(common, "AUDIT_PATH", tmp_path / "data" / "audit.jsonl")
    monkeypatch.setattr(desk, "_store", None)
    monkeypatch.setattr(desk, "now", lambda: T0)
    monkeypatch.setattr(desk.second_opinion, "review", lambda *a, **k: None)
    fake = FakeLedger()
    fake.approvals = {}
    fake.fetch_testnet_tx = lambda h: fake.approvals.get(h, {"error": "txnNotFound"})
    desk.app.dependency_overrides[desk.get_ledger] = lambda: fake
    yield {"c": TestClient(desk.app), "fake": fake, "dir": tmp_path}
    desk.app.dependency_overrides.clear()


def req_body(principal_xrp, blob, borrower="rEtfjGvgSUkeQg45Eb8Mid4yWdc9FU3rRv"):
    return {"borrower": borrower, "principalDrops": str(principal_xrp * XRP), "termSeconds": 270,
            "purpose": "inventory", "declared": {"existingDebtDrops": "0"}, "signedLoanSet": blob}


TOK = {auth.TOKEN_HEADER: "tok"}


@wired
def test_operator_routes_need_token(denv):
    c = denv["c"]
    held = c.post("/v1/loan-requests", json=req_body(60, "CCDD")).json()
    assert held["status"] == "held"
    assert c.post(f"/v1/loan-requests/{held['id']}/approve", json={}).status_code == 401
    assert c.post(f"/v1/loan-requests/{held['id']}/deny", json={}).status_code == 401
    assert c.put("/v1/policy", json=pol.DEFAULT_POLICY).status_code == 401
    assert c.post("/v1/broker/cover", json={"amountDrops": "1000000"}).status_code == 401
    assert denv["fake"].cosigned == [] and denv["fake"].deposits == []
    assert c.post(f"/v1/loan-requests/{held['id']}/notes", json={"from": "agent", "text": "hi"}).status_code == 200
    assert c.post(f"/v1/loan-requests/{held['id']}/deny", json={}, headers=TOK).status_code == 200


@wired
def test_approve_requires_verified_ledger_payment(denv):
    c, fake = denv["c"], denv["fake"]
    held = c.post("/v1/loan-requests", json=req_body(60, "CCDD")).json()
    h = held["loanSetHash"]
    assert h == auth.loan_set_hash("CCDD")
    r = c.post(f"/v1/loan-requests/{held['id']}/approve", json={}, headers=TOK)
    assert r.status_code == 422 and r.json()["detail"] == "approval_tx_required"
    r = c.post(f"/v1/loan-requests/{held['id']}/approve", json={"approvalTxHash": "1" * 64}, headers=TOK)
    assert r.status_code == 409 and r.json()["detail"] == "tx_lookup_failed:txnNotFound"
    fake.approvals["2" * 64] = approval_tx("CD" * 32)
    r = c.post(f"/v1/loan-requests/{held['id']}/approve", json={"approvalTxHash": "2" * 64}, headers=TOK)
    assert r.status_code == 409 and r.json()["detail"] == "approval_hash_mismatch"
    assert fake.cosigned == []
    fake.approvals["3" * 64] = approval_tx(h)
    r = c.post(f"/v1/loan-requests/{held['id']}/approve", json={"approvalTxHash": "3" * 64}, headers=TOK)
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["status"] == "approved" and rec["decidedBy"] == "ledger" and rec["approvalTxHash"] == "3" * 64
    assert fake.cosigned == ["CCDD"]


@wired
def test_double_post_returns_first_record(denv):
    c = denv["c"]
    borrower, broker = Wallet.create(), Wallet.create()
    blob = signed_blob(borrower, broker, principal_xrp=60)
    a = c.post("/v1/loan-requests", json=req_body(60, blob, borrower=borrower.address)).json()
    b = c.post("/v1/loan-requests", json=req_body(60, blob, borrower=borrower.address)).json()
    assert a["id"] == b["id"] == "lr_0001" and a["blobKey"] == f"{borrower.address}:5"
    assert len(c.get("/v1/loan-requests").json()["requests"]) == 1


@wired
def test_pending_cap_refuses_before_decision(denv):
    c = denv["c"]
    policy = {**pol.DEFAULT_POLICY, "maxPendingDrops": str(100 * XRP)}
    assert c.put("/v1/policy", json=policy, headers=TOK).status_code == 200
    assert c.post("/v1/loan-requests", json=req_body(60, "C1")).json()["status"] == "held"
    r = c.post("/v1/loan-requests", json=req_body(60, "C2")).json()
    assert r["status"] == "refused" and r["reason"] == "pending_exposure_cap"
    assert c.post("/v1/loan-requests", json=req_body(30, "C3")).json()["status"] == "held"


def test_pending_exposure_counts_reserved():
    r = recs({"id": "lr_0001", "status": "held", "principalDrops": str(60 * XRP)})
    assert auth.pending_exposure_drops(r, set(), {"rA:5": str(30 * XRP)}) == 90 * XRP
    assert auth.pending_cap_exceeded(r, set(), 11 * XRP, {"maxPendingDrops": str(100 * XRP)}, {"rA:5": str(30 * XRP)})
    assert not auth.pending_cap_exceeded(r, set(), 10 * XRP, {"maxPendingDrops": str(100 * XRP)}, {"rA:5": str(30 * XRP)})


@wired
def test_duplicate_during_second_opinion_is_409(denv, monkeypatch):
    """The dedup window: a replay that lands while the first POST is still inside the second opinion."""
    import threading
    gate, inside = threading.Event(), threading.Event()

    def slow_review(*a, **k):
        inside.set()
        gate.wait(5)
        return None
    monkeypatch.setattr(desk.second_opinion, "review", slow_review)
    c = denv["c"]
    borrower, broker = Wallet.create(), Wallet.create()
    blob = signed_blob(borrower, broker, principal_xrp=60)
    first: dict = {}
    t = threading.Thread(target=lambda: first.update(c.post("/v1/loan-requests", json=req_body(60, blob, borrower.address)).json()))
    t.start()
    assert inside.wait(5)
    r = c.post("/v1/loan-requests", json=req_body(60, blob, borrower.address))
    assert r.status_code == 409 and r.json()["detail"] == "duplicate_in_progress"
    gate.set()
    t.join(5)
    assert first["status"] == "held" and first["blobKey"] == f"{borrower.address}:5"
    assert len(c.get("/v1/loan-requests").json()["requests"]) == 1
    assert c.post("/v1/loan-requests", json=req_body(60, blob, borrower.address)).json()["id"] == first["id"]


@wired
def test_pending_cap_counts_request_still_being_decided(denv, monkeypatch):
    import threading
    gate, inside = threading.Event(), threading.Event()

    def slow_review(*a, **k):
        inside.set()
        gate.wait(5)
        return None
    monkeypatch.setattr(desk.second_opinion, "review", slow_review)
    c = denv["c"]
    assert c.put("/v1/policy", json={**pol.DEFAULT_POLICY, "maxPendingDrops": str(100 * XRP)}, headers=TOK).status_code == 200
    b1, b2 = signed_blob(Wallet.create(), Wallet.create(), 60), signed_blob(Wallet.create(), Wallet.create(), 60)
    t = threading.Thread(target=lambda: c.post("/v1/loan-requests", json=req_body(60, b1)))
    t.start()
    assert inside.wait(5)
    monkeypatch.setattr(desk.second_opinion, "review", lambda *a, **k: None)
    r = c.post("/v1/loan-requests", json=req_body(60, b2)).json()
    assert r["status"] == "refused" and r["reason"] == "pending_exposure_cap"
    gate.set()
    t.join(5)


@wired
def test_signed_loan_set_is_operator_only_and_held_only(denv):
    c = denv["c"]
    held = c.post("/v1/loan-requests", json=req_body(60, "CCDD")).json()
    assert c.get(f"/v1/loan-requests/{held['id']}/signed-loan-set").status_code == 401
    r = c.get(f"/v1/loan-requests/{held['id']}/signed-loan-set", headers=TOK)
    assert r.status_code == 200 and r.json() == {"id": held["id"], "loanSetHash": auth.loan_set_hash("CCDD"),
                                                 "signedLoanSet": "CCDD"}
    assert "signedLoanSet" not in c.get(f"/v1/loan-requests/{held['id']}").json()   # still private on the record
    assert c.post(f"/v1/loan-requests/{held['id']}/deny", json={}, headers=TOK).status_code == 200
    assert c.get(f"/v1/loan-requests/{held['id']}/signed-loan-set", headers=TOK).status_code == 409


# ---- R2: the approval must be signed by the approver's own key, not a delegate of its account --------------
def delegated_approval_tx(h: str, delegate: Wallet) -> dict:
    """Account=treasury, Delegate=hot, signed by the hot key (the wallet's real Payment delegation shape)."""
    from xrpl.models.transactions import Memo, Payment
    p = Payment(account=APPROVER, delegate=delegate.address, destination=delegate.address, amount="1",
                sequence=7, fee="12", memos=[Memo(memo_type=auth.APPROVAL_MEMO_TYPE, memo_data=h)])
    tx = sign(p, delegate).to_xrpl()
    assert tx["SigningPubKey"] == delegate.public_key and tx["Delegate"] == delegate.address
    return {"validated": True, "meta": {"TransactionResult": "tesSUCCESS"}, "tx_json": tx, "hash": "E" * 64}


def test_verify_rejects_delegate_signed_and_foreign_signer(monkeypatch):
    monkeypatch.delenv(auth.APPROVER_PUBKEY_ENV, raising=False)
    h, hot = "AB" * 32, Wallet.create()
    assert auth.verify_approval_payment(delegated_approval_tx(h, hot), h, APPROVER) == "approval_delegated"
    no_delegate = delegated_approval_tx(h, hot)
    no_delegate["tx_json"].pop("Delegate")   # same hot key, no Delegate field: not the account's master key
    assert auth.verify_approval_payment(no_delegate, h, APPROVER) == "approval_wrong_signer"
    multisig = approval_tx(h); multisig["tx_json"]["SigningPubKey"] = ""
    assert auth.verify_approval_payment(multisig, h, APPROVER) == "approval_wrong_signer"
    missing = approval_tx(h); missing["tx_json"].pop("SigningPubKey")
    assert auth.verify_approval_payment(missing, h, APPROVER) == "approval_wrong_signer"
    monkeypatch.setenv(auth.APPROVER_PUBKEY_ENV, APPROVER_KEY.public_key.lower())   # pinned key: equality
    assert auth.verify_approval_payment(approval_tx(h), h, APPROVER) is None
    assert auth.verify_approval_payment(no_delegate, h, APPROVER) == "approval_wrong_signer"
    assert auth.verify_approval_payment(delegated_approval_tx(h, hot), h, APPROVER) == "approval_delegated"


@wired
def test_approve_refuses_delegate_signed_payment(denv):
    c, fake = denv["c"], denv["fake"]
    held = c.post("/v1/loan-requests", json=req_body(60, "CCDD")).json()
    fake.approvals["4" * 64] = delegated_approval_tx(held["loanSetHash"], Wallet.create())
    r = c.post(f"/v1/loan-requests/{held['id']}/approve", json={"approvalTxHash": "4" * 64}, headers=TOK)
    assert r.status_code == 409 and r.json()["detail"] == "approval_delegated"
    assert fake.cosigned == []
    assert c.get(f"/v1/loan-requests/{held['id']}").json()["status"] == "held"


def test_find_duplicate_ignores_terminal_records_that_never_submitted():
    """After a hold expires the borrower's next blob has the same Sequence: it must get a new record, not the old one."""
    key = "rA:5"
    for status in ("expired", "denied", "refused"):
        assert auth.find_duplicate(recs({"id": "lr_0001", "status": status, "blobKey": key}), key) is None
    assert auth.find_duplicate(recs({"id": "lr_0001", "status": "failed", "blobKey": key, "txHash": None}), key) is None
    for status in ("held", "auto", "approved"):
        assert auth.find_duplicate(recs({"id": "lr_0001", "status": status, "blobKey": key}), key)["id"] == "lr_0001"
    landed_then_failed = recs({"id": "lr_0001", "status": "failed", "blobKey": key, "txHash": "H1"})
    assert auth.find_duplicate(landed_then_failed, key)["id"] == "lr_0001"   # a submitted blob stays matched


@wired
def test_expired_hold_can_be_resubmitted_with_the_same_sequence(denv):
    c = denv["c"]
    borrower, broker = Wallet.create(), Wallet.create()
    blob = signed_blob(borrower, broker, principal_xrp=60, sequence=5)
    first = c.post("/v1/loan-requests", json=req_body(60, blob, borrower=borrower.address)).json()
    assert first["status"] == "held"
    assert c.post(f"/v1/loan-requests/{first['id']}/deny", json={}, headers=TOK).json()["status"] == "denied"
    second = c.post("/v1/loan-requests", json=req_body(60, blob, borrower=borrower.address)).json()
    assert second["id"] != first["id"] and second["status"] == "held" and second["blobKey"] == first["blobKey"]


def test_pending_exposure_skips_lapsed_holds():
    """Review C4: a held record past its deadline is expired in all but name; it must not hold cap room."""
    r = {"lr_0001": {"id": "lr_0001", "status": "held", "principalDrops": str(60 * XRP), "ts": 1000},
         "lr_0002": {"id": "lr_0002", "status": "held", "principalDrops": str(15 * XRP), "ts": 1100}}
    assert auth.pending_exposure_drops(r, set(), None, 1119, 120) == 75 * XRP
    assert auth.pending_exposure_drops(r, set(), None, 1120, 120) == 15 * XRP      # same boundary as expire_if_due
    assert auth.pending_exposure_drops(r, {"lr_0001"}, None, 1120, 120) == 75 * XRP  # approve in flight still counts
    assert auth.pending_exposure_drops(r, set()) == 75 * XRP                         # no clock: old behaviour
    pol_ = {"maxPendingDrops": str(80 * XRP), "holdTimeoutSeconds": 120}
    assert auth.pending_cap_exceeded(r, set(), 10 * XRP, pol_, None, 1119)
    assert not auth.pending_cap_exceeded(r, set(), 10 * XRP, pol_, None, 1120)


def terms_memo(text: str) -> dict:
    return {"Memo": {"MemoType": auth.TERMS_MEMO_TYPE, "MemoData": text.encode("ascii").hex().upper()}}


def test_loan_terms_text_matches_the_wallet_format():
    borrower, broker = Wallet.create(), Wallet.create()
    blob = signed_blob(borrower, broker, principal_xrp=30)
    total = decode(blob)["PaymentTotal"]
    assert auth.loan_terms_text(blob) == f"approve loan 30 XRP to {borrower.address} {total} payments"
    tx = replace(common.build_loan_set(borrower.address, LB, broker.address, "3333335", 270, 800), sequence=5,
                 last_ledger_sequence=1000)
    assert auth.loan_terms_text(encode(sign(tx, borrower).to_xrpl())).startswith("approve loan 3.333335 XRP to ")


def test_verify_loan_terms_present_absent_and_wrong():
    borrower, broker = Wallet.create(), Wallet.create()
    blob = signed_blob(borrower, broker, principal_xrp=30)
    h = auth.loan_set_hash(blob)
    ok = approval_tx(h)
    assert auth.verify_loan_terms(ok, blob) is None                                   # absent: accepted as before
    ok["tx_json"]["Memos"].append(terms_memo(auth.loan_terms_text(blob)))
    assert auth.verify_loan_terms(ok, blob) is None
    bad = approval_tx(h)
    bad["tx_json"]["Memos"].append(terms_memo(auth.loan_terms_text(blob).replace("30 XRP", "3 XRP")))
    assert auth.verify_loan_terms(bad, blob) == "terms_mismatch"
    junk = approval_tx(h)
    junk["tx_json"]["Memos"].append({"Memo": {"MemoType": auth.TERMS_MEMO_TYPE, "MemoData": "FF00"}})
    assert auth.verify_loan_terms(junk, blob) == "terms_mismatch"


@wired
def test_approve_refuses_mismatched_loan_terms_and_accepts_matching(denv, monkeypatch):
    c, fake = denv["c"], denv["fake"]
    monkeypatch.setattr(desk.reconcile, "reconcile_record", lambda rec, ledger, now: ("keep", {}))  # real blob, fake ledger
    borrower, broker = Wallet.create(), Wallet.create()
    blob = signed_blob(borrower, broker, principal_xrp=60)
    held = c.post("/v1/loan-requests", json=req_body(60, blob, borrower=borrower.address)).json()
    assert held["status"] == "held"
    h = held["loanSetHash"]
    wrong = approval_tx(h)
    wrong["tx_json"]["Memos"].append(terms_memo(f"approve loan 6 XRP to {borrower.address} 3 payments"))
    fake.approvals["4" * 64] = wrong
    r = c.post(f"/v1/loan-requests/{held['id']}/approve", json={"approvalTxHash": "4" * 64}, headers=TOK)
    assert r.status_code == 422 and r.json()["detail"] == "terms_mismatch"
    assert fake.cosigned == []
    right = approval_tx(h)
    right["tx_json"]["Memos"].append(terms_memo(auth.loan_terms_text(blob)))
    fake.approvals["5" * 64] = right
    r = c.post(f"/v1/loan-requests/{held['id']}/approve", json={"approvalTxHash": "5" * 64}, headers=TOK)
    assert r.status_code == 200, r.text
    assert r.json()["decidedBy"] == "ledger" and fake.cosigned == [blob]


@pytest.mark.parametrize("v, drops", [("60000000", 60_000_000), ("1e11", 10**11), ("15e10", 15 * 10**10),
                                      ("123456789012e0", 123456789012), (30000000, 30_000_000)])
def test_stnumber_int_parses_mantissa_exponent(v, drops):
    assert auth.stnumber_int(v) == drops


# ---- 006-desk-auth review, C2: a cap refusal is attributed to the policy that refused -----------------------
@wired
def test_cap_refusal_records_the_hash_of_the_policy_that_refused(denv, monkeypatch):
    """The cap is read as of admission (after a PUT that lowered it has landed); the record and the decision audit
    line must carry that policy's hash, not the one loaded when the request came in."""
    import threading
    c, fake = denv["c"], denv["fake"]
    initial = c.put("/v1/policy", json={**pol.DEFAULT_POLICY, "maxPendingDrops": str(100 * XRP)}, headers=TOK).json()
    gate, inside = threading.Event(), threading.Event()
    original = fake.verify_loan_set_blob

    def slow_verify(*a):
        inside.set()
        gate.wait(5)
        return original(*a)
    monkeypatch.setattr(fake, "verify_loan_set_blob", slow_verify)
    blob = signed_blob(Wallet.create(), Wallet.create(), 60)
    out: dict = {}
    t = threading.Thread(target=lambda: out.update(c.post("/v1/loan-requests", json=req_body(60, blob)).json()))
    t.start()
    assert inside.wait(5)
    current = c.put("/v1/policy", json={**initial, "maxPendingDrops": str(50 * XRP)}, headers=TOK).json()
    gate.set()
    t.join(5)
    assert out["status"] == "refused" and out["reason"] == "pending_exposure_cap"
    assert pol.policy_hash(current) != pol.policy_hash(initial)
    assert out["policyHash"] == pol.policy_hash(current)
    rows = [json.loads(l) for l in (denv["dir"] / "data" / "audit.jsonl").read_text().splitlines()]
    decided = next(r for r in rows if r["event"] == "loan_request_decided")
    assert decided["policyHash"] == pol.policy_hash(current)
    assert fake.cosigned == []


# ---- security review, C3: records stored before the auth change have no blobKey -------------------------
def test_find_duplicate_derives_blob_key_from_legacy_record():
    borrower, broker = Wallet.create(), Wallet.create()
    blob = signed_blob(borrower, broker, principal_xrp=60, sequence=5)
    key = f"{borrower.address}:5"
    legacy = {"id": "lr_0001", "status": "held", "principalDrops": str(60 * XRP), auth.BLOB_FIELD: blob}
    assert auth.find_duplicate(recs(legacy), key)["id"] == "lr_0001"
    assert legacy["blobKey"] == key                                   # migrated in place, so the next save keeps it
    assert auth.find_duplicate(recs(legacy), f"{borrower.address}:6") is None
    for status in ("expired", "denied", "refused"):                  # terminal, never submitted: must not block
        assert auth.find_duplicate(recs({"id": "lr_0002", "status": status, auth.BLOB_FIELD: blob}), key) is None
    assert auth.find_duplicate(recs({"id": "lr_0003", "status": "held"}), key) is None   # no key, no blob
    assert auth.record_blob_key({"id": "lr_0004", "status": "denied"}) is None


@wired
def test_legacy_record_without_blob_key_dedups_an_identical_resubmission(denv):
    c, fake = denv["c"], denv["fake"]
    borrower = Wallet.create()
    blob = signed_blob(borrower, Wallet.create(), principal_xrp=60, sequence=5)
    first = c.post("/v1/loan-requests", json=req_body(60, blob, borrower=borrower.address)).json()
    assert first["status"] == "held"
    s = desk.store()
    for field in ("blobKey", "loanSetHash", "approvalTxHash"):   # the pre-migration record shape
        s.records[first["id"]].pop(field, None)
    s.save()
    desk._store = None                                           # reload the Store from disk
    replay = c.post("/v1/loan-requests", json=req_body(60, blob, borrower=borrower.address)).json()
    assert replay["id"] == first["id"] and replay["blobKey"] == f"{borrower.address}:5"
    assert len(c.get("/v1/loan-requests").json()["requests"]) == 1
    assert fake.cosigned == []
    assert c.post(f"/v1/loan-requests/{first['id']}/deny", json={}, headers=TOK).json()["status"] == "denied"
    fresh = c.post("/v1/loan-requests", json=req_body(60, blob, borrower=borrower.address)).json()
    assert fresh["id"] != first["id"] and fresh["status"] == "held"   # a denied legacy record does not block
