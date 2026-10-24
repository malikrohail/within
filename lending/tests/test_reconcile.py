"""reconcile.py: dead or already-landed blobs on held/auto records (no network)."""
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from xrpl.core.binarycodec import encode
from xrpl.transaction import sign
from xrpl.wallet import Wallet

import common
import desk
import policy as pol
import reconcile as R

XRP = 1_000_000
LB = "E43DA4D38D7DA816256CA4947839187C41A113FC81AB5A3568B2C7BF7CB1CC91"


def blob(borrower, broker, seq=5, lls=1000):
    tx = common.build_loan_set(borrower.address, LB, broker.address, str(60 * XRP), 270, 8000)
    return encode(sign(replace(tx, sequence=seq, last_ledger_sequence=lls), borrower).to_xrpl())


def rec(b, status="held", **over):
    return {"id": "lr_0001", "status": status, "txHash": None, "loanId": None, "decidedBy": "policy",
            "reason": None, R.BLOB_KEY: b, **over}


def test_blob_facts():
    bo, br = Wallet.create(), Wallet.create()
    f = R.blob_facts(blob(bo, br, seq=7, lls=1234))
    assert {k: f[k] for k in ("account", "sequence", "lastLedger")} == {"account": bo.address, "sequence": 7,
                                                                          "lastLedger": 1234}
    assert f["loanBrokerId"] and f["txnSignature"]  # F1: reconcile matches this blob's broker and signature
    assert R.blob_facts("ZZ") is None


def test_classify_matrix():
    bo, br = Wallet.create(), Wallet.create()
    b = blob(bo, br, seq=5, lls=1000)
    assert R.classify(rec(b), 5, 900, None) == ("keep", {})
    assert R.classify(rec(b), 5, 1001, None) == ("expired", {})
    assert R.classify(rec(b), 6, 900, None) == ("consumed", {})
    assert R.classify(rec(b), 6, 900, {"engineResult": "tesSUCCESS", "hash": "H", "loanId": "L"}) == ("landed", {"hash": "H", "loanId": "L"})
    assert R.classify(rec(b), 6, 900, {"engineResult": "tecNO_PERMISSION", "hash": "H"}) == ("consumed", {})
    assert R.classify(rec(b, status="denied"), 6, 1001, None) == ("keep", {})          # not a candidate
    assert R.classify(rec(b, txHash="X"), 6, 1001, None) == ("keep", {})               # already settled


def test_apply_shapes():
    bo, br = Wallet.create(), Wallet.create()
    r = rec(blob(bo, br), status="held")
    assert R.apply(r, "landed", {"hash": "H", "loanId": "L"}, 42)
    assert r["status"] == "approved" and r["decidedBy"] == "human" and r["txHash"] == "H" and R.BLOB_KEY not in r
    r = rec(blob(bo, br), status="auto")
    R.apply(r, "landed", {"hash": "H", "loanId": "L"}, 42)
    assert r["status"] == "auto" and r["decidedBy"] == "policy"
    r = rec(blob(bo, br)); R.apply(r, "expired", {}, 42)
    assert (r["status"], r["reason"]) == ("expired", "blob_expired") and R.BLOB_KEY not in r
    r = rec(blob(bo, br)); assert not R.apply(r, "keep", {}, 42) and R.BLOB_KEY in r


class FakeChain:
    def __init__(self, seq=5, ledger=900, landed=None):
        self.seq, self.ledger, self.landed = seq, ledger, landed
        self.calls = []

    def account_sequence(self, a):
        self.calls.append("seq"); return self.seq

    def ledger_index(self):
        return self.ledger

    def find_loan_set(self, a, s, broker_id=None, sig=None):
        self.calls.append("find"); return self.landed


def test_reconcile_record_only_looks_up_when_sequence_moved():
    bo, br = Wallet.create(), Wallet.create()
    ch = FakeChain(seq=5)
    assert R.reconcile_record(rec(blob(bo, br)), ch, 1) == ("keep", {}) and ch.calls == ["seq"]
    ch = FakeChain(seq=6, landed={"engineResult": "tesSUCCESS", "hash": "H", "loanId": "L"})
    r = rec(blob(bo, br))
    assert R.reconcile_record(r, ch, 1) == ("landed", {"hash": "H", "loanId": "L"}) and ch.calls == ["seq", "find"]
    assert r["status"] == "approved"


# ---- desk wiring -------------------------------------------------------------------
from tests.test_desk import FakeLedger, T0  # noqa: E402
import auth  # noqa: E402
import json  # noqa: E402


@pytest.fixture
def denv(tmp_path, monkeypatch):
    monkeypatch.setenv(auth.TOKEN_ENV, "tok")
    monkeypatch.delenv(auth.APPROVER_ENV, raising=False)
    accounts = {"network": "devnet", "accounts": {"broker": "rBroker"}, "vaultId": "V", "loanBrokerId": "LB",
                "shareMptId": "S", "subscriptionDate": 0, "redemptionDate": 0}
    (tmp_path / "accounts.json").write_text(json.dumps(accounts))
    (tmp_path / "policy.json").write_text(json.dumps(pol.DEFAULT_POLICY))
    for name, p in {"ACCOUNTS_PATH": "accounts.json", "POLICY_PATH": "policy.json", "REQUESTS_PATH": "data/requests.json",
                    "EXAMPLES_PATH": "data/ex.jsonl", "DEFAULTS_PATH": "data/defaults.json"}.items():
        monkeypatch.setattr(desk, name, tmp_path / p)
    monkeypatch.setattr(common, "AUDIT_PATH", tmp_path / "data" / "audit.jsonl")
    monkeypatch.setattr(desk, "_store", None)
    monkeypatch.setattr(desk, "now", lambda: T0)
    monkeypatch.setattr(desk.second_opinion, "review", lambda *a, **k: None)
    fake = FakeLedger()
    fake.seq, fake.landed = 5, None
    fake.account_sequence = lambda a: fake.seq
    fake.find_loan_set = lambda a, s, b=None, sig=None: fake.landed
    desk.app.dependency_overrides[desk.get_ledger] = lambda: fake
    yield {"c": TestClient(desk.app), "fake": fake, "dir": tmp_path}
    desk.app.dependency_overrides.clear()


TOK = {auth.TOKEN_HEADER: "tok"}


def body(b, borrower):
    return {"borrower": borrower, "principalDrops": str(60 * XRP), "termSeconds": 270, "purpose": "inventory",
            "declared": {"existingDebtDrops": "0"}, "signedLoanSet": b}


def test_approve_refuses_a_landed_blob_and_settles_the_record(denv):
    c, fake = denv["c"], denv["fake"]
    bo, br = Wallet.create(), Wallet.create()
    held = c.post("/v1/loan-requests", json=body(blob(bo, br), bo.address)).json()
    assert held["status"] == "held"
    fake.seq, fake.landed = 6, {"engineResult": "tesSUCCESS", "hash": "HLANDED", "loanId": "LX"}  # crash after submit
    r = c.post(f"/v1/loan-requests/{held['id']}/approve", json={}, headers=TOK)
    assert r.status_code == 409 and r.json()["detail"] == "already_landed:HLANDED"
    rec = c.get(f"/v1/loan-requests/{held['id']}").json()
    assert rec["status"] == "approved" and rec["txHash"] == "HLANDED" and rec["loanId"] == "LX"
    assert fake.cosigned == []  # never co-signed a second time


def test_approve_refuses_an_expired_blob(denv):
    c, fake = denv["c"], denv["fake"]
    bo, br = Wallet.create(), Wallet.create()
    held = c.post("/v1/loan-requests", json=body(blob(bo, br, lls=50), bo.address)).json()
    fake.ledger_index = lambda: 77  # > LastLedgerSequence 50
    r = c.post(f"/v1/loan-requests/{held['id']}/approve", json={}, headers=TOK)
    assert r.status_code == 409 and r.json()["detail"] == "blob_expired"
    assert c.get(f"/v1/loan-requests/{held['id']}").json()["status"] == "expired" and fake.cosigned == []


def test_reconcile_all_on_boot(denv):
    c, fake = denv["c"], denv["fake"]
    bo, br = Wallet.create(), Wallet.create()
    held = c.post("/v1/loan-requests", json=body(blob(bo, br), bo.address)).json()
    fake.seq = 6  # consumed by something else, no LoanSet found
    changed = desk.reconcile_all(fake)
    assert changed == [{"id": held["id"], "action": "consumed"}]
    assert c.get(f"/v1/loan-requests/{held['id']}").json()["reason"] == "sequence_consumed"
    assert desk.reconcile_all(fake) == []


def test_find_loan_set_matches_only_this_broker_and_signature(monkeypatch):
    """F1 positive control: the desk's own LoanSet (accounts.json LoanBrokerID + the stored blob's signature) is found;
    the same Sequence with another signature is not."""
    import common
    import desk
    bo = Wallet.create()
    mine = {"TransactionType": "LoanSet", "Account": bo.address, "Sequence": 5, "LoanBrokerID": "AB" * 32,
            "TxnSignature": "5167"}
    page = {"transactions": [{"validated": True, "hash": "H1", "tx_json": mine,
                              "meta": {"TransactionResult": "tesSUCCESS", "AffectedNodes": [
                                  {"CreatedNode": {"LedgerEntryType": "Loan", "LedgerIndex": "L1"}}]}}]}
    monkeypatch.setattr(common, "_rpc", lambda req: page)
    monkeypatch.setattr(desk, "load_accounts", lambda: {"loanBrokerId": "ab" * 32})
    assert desk.Ledger().find_loan_set(bo.address, 5)["loanId"] == "L1"
    assert desk.Ledger().find_loan_set(bo.address, 5, txn_signature="5167")["hash"] == "H1"
    assert desk.Ledger().find_loan_set(bo.address, 5, txn_signature="9999") is None
