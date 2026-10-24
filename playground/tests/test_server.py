"""Offline tests: a fake chain and a fake desk, no devnet, no :7500."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server as S  # noqa: E402

XRP = 1_000_000


class FakeWallet:
    def __init__(self, i=None, address=None, seed=None):
        self.address = address or f"rPool{i}"
        self.seed = seed or f"sEedPool{i}"


SEEDS = {f"sEedPool{i}": f"rPool{i}" for i in range(3)} | {f"sEedCust{i}": f"rCust{i}" for i in range(3)}


class FakeChain:
    def __init__(self):
        self.t = 1_800_000_000
        self.payments, self.accepts, self.faucets = [], [], []
        self.loans: list[dict] = []
        self.ledger_tip = 100

    def now(self):
        return self.t

    def wallet_from_seed(self, seed):
        return FakeWallet(address=SEEDS[seed], seed=seed)

    def faucet_wallet(self, w=None):
        self.faucets.append(w.address if w else None)
        return w or FakeWallet(len(self.faucets))

    def balance(self, address):
        return 100 * XRP

    def pay_income(self, w, dest, drops, invoice, date):
        self.ledger_tip += 1
        h = f"INC{len(self.payments) + 1}"
        self.payments.append({"payer": w.address, "dest": dest, "drops": drops, "invoice": invoice, "date": date,
                              "ledger_index": self.ledger_tip, "hash": h})
        return {"hash": h, "engineResult": "tesSUCCESS", "validated": True, "ledgerIndex": self.ledger_tip}

    def evidence(self, address, declared):
        mine = [p for p in self.payments if p["dest"] == address]
        per = {}
        for p in mine:
            per[p["payer"]] = per.get(p["payer"], 0) + p["drops"]
        vol = sum(per.values())
        return {"borrower": address, "asOf": self.t, "windowDays": 30, "bank": None, "declared": declared,
                "ledger": {"accountExists": True, "accountAgeLedgers": 10, "inboundPaymentCount": len(mine),
                           "inboundVolumeDrops": str(vol), "distinctPayers": len(per),
                           "topPayerSharePct": round(100 * max(per.values()) / vol, 1) if vol else 0.0,
                           "activeDays": 1 if mine else 0, "activeLoans": 0, "loanDebtDrops": "0", "loanPrincipalDrops": "0",
                           "pastDefaults": 0, "hasAcceptedCredential": any(a == address for a in self.accepts),
                           "sampleTxHashes": []}}

    def sign_loan_set(self, w, tx):
        return "BLOB:" + w.address

    def credential_accept(self, w, issuer):
        self.accepts.append(w.address)
        return {"hash": "ACC1", "engineResult": "tesSUCCESS", "validated": True}

    def sweeper_ledger(self, w):
        return FakeSweepLedger(self, w.address)


class FakeSweepLedger:
    def __init__(self, chain, borrower):
        self.chain, self.borrower = chain, borrower
        self.pays = []

    def account_tx(self, since):
        entries = []
        for p in self.chain.payments:
            if p["dest"] != self.borrower or p["ledger_index"] <= since:
                continue
            memo = {"Memo": {"MemoType": "696E766F696365",
                             "MemoData": json.dumps({"invoice": p["invoice"], "date": p["date"]}).encode().hex().upper()}}
            entries.append({"hash": p["hash"], "ledger_index": p["ledger_index"], "validated": True,
                            "tx_json": {"TransactionType": "Payment", "Account": p["payer"], "Destination": self.borrower,
                                        "DeliverMax": str(p["drops"]), "Memos": [memo]},
                            "meta": {"TransactionResult": "tesSUCCESS", "delivered_amount": str(p["drops"]), "AffectedNodes": []}})
        return entries, self.chain.ledger_tip

    def loans_of(self):
        return [ln for ln in self.chain.loans if ln["borrower"] == self.borrower]

    def balance_and_reserve(self):
        return 100 * XRP, 1 * XRP

    def fee_drops(self):
        return 12

    def loan_pay(self, loan_id, drops):
        self.pays.append((loan_id, drops))
        self.chain.loans_paid = getattr(self.chain, "loans_paid", []) + [(loan_id, drops)]
        return {"hash": f"PAY{len(self.chain.loans_paid)}", "engineResult": "tesSUCCESS", "validated": True, "ledgerIndex": 200}


class FakeDesk:
    """Records every path it was asked for; the never-approve test reads `calls`."""

    def __init__(self, decision="held", credential_status=404):
        self.decision, self.credential_status = decision, credential_status
        self.calls, self.records, self.sweeps = [], {}, []
        self.url, self.token = "fake", "t"
        self.sweep_desk = self

    def policy(self):
        self.calls.append("GET /v1/policy")
        return S.policy.load_policy()

    def post_request(self, body):
        self.calls.append("POST /v1/loan-requests")
        rid = f"lr_{len(self.records) + 1:04d}"
        rec = {"id": rid, "ts": 1, "status": self.decision, "reason": "score_below_auto" if self.decision == "held" else None,
               "loanId": "LOAN1" if self.decision == "auto" else None, "txHash": "LOANSET1" if self.decision == "auto" else None,
               "score": 43, "decidedBy": "policy", "memo": None, "engineResult": None, "principalDrops": body["principalDrops"]}
        self.records[rid] = rec
        return 200, rec

    def get_request(self, rid):
        self.calls.append(f"GET /v1/loan-requests/{rid}")
        return self.records[rid]

    def request_credential(self, subject):
        self.calls.append("POST /v1/broker/credentials")
        if self.credential_status == 200:
            return 200, {"hash": "CRED1"}
        return self.credential_status, {"detail": "not found"}

    def manage_default(self, loan_id):
        self.calls.append(f"POST /v1/loans/{loan_id}/manage")
        return 200, {"loanId": loan_id, "action": "default", "hash": "DEF1", "engineResult": "tesSUCCESS",
                     "coverAbsorbedDrops": "300000", "vaultLossDrops": "2700000", "defaultAmountDrops": "3000000"}

    def post_sweep(self, rec):
        self.sweeps.append(rec)


@pytest.fixture
def pool(tmp_path):
    data = {"pool": [{"address": f"rPool{i}", "seed": f"sEedPool{i}", "claimedBy": None, "used": False} for i in range(2)],
            "customers": [{"address": f"rCust{i}", "seed": f"sEedCust{i}"} for i in range(3)]}
    (tmp_path / "pool.json").write_text(json.dumps(data))
    return tmp_path


def make(pool, decision="held", credential_status=404):
    chain, desk = FakeChain(), FakeDesk(decision, credential_status)
    app = S.make_app(pool, chain=chain, desk=desk)
    return TestClient(app), chain, desk


def wait_decided(c, sid):
    for _ in range(50):
        s = c.get(f"/v1/sessions/{sid}").json()
        if s["loan"]["status"] != "deciding":
            return s
        time.sleep(0.02)
    raise AssertionError("loan never decided")


def test_claim_release_and_no_seed_in_responses(pool):
    c, chain, desk = make(pool)
    a = c.post("/v1/sessions").json()
    assert a["address"] == "rPool0" and a["level"] == 2 and "poolIndex" not in a and "sEed" not in json.dumps(a)
    assert a["score"] == 24 and a["breakdown"]["ledger"]["score"] == 20
    b = c.post("/v1/sessions").json()
    assert b["address"] == "rPool1"
    assert c.post("/v1/sessions").status_code == 503   # pool empty
    assert c.post(f"/v1/sessions/{a['id']}/reset").json()["released"] == "rPool0"
    assert c.get(f"/v1/sessions/{a['id']}").status_code == 404
    assert c.post("/v1/sessions").json()["address"] == "rPool0"   # released account comes back
    saved = json.loads((pool / "pool.json").read_text())
    assert saved["pool"][0]["claimedBy"] is not None and saved["pool"][0]["used"] is True


def test_customer_rotation_and_score_climbs(pool):
    c, chain, desk = make(pool)
    sid = c.post("/v1/sessions").json()["id"]
    payers = []
    for i in range(4):
        r = c.post(f"/v1/sessions/{sid}/income").json()
        payers.append(r["payment"]["payer"])
        assert r["payment"]["drops"] == str(5 * XRP) and r["payment"]["hash"] == f"INC{i + 1}"
        assert r["session"]["level"] == 4
    assert payers == ["rCust0", "rCust1", "rCust2", "rCust0"]
    inv = chain.payments[0]["invoice"]
    assert inv.startswith("INV-PG-") and chain.payments[0]["date"] == time.strftime("%Y-%m-%d", time.gmtime(chain.t))
    s = c.get(f"/v1/sessions/{sid}").json()
    assert s["score"] == 48 and s["ledger"]["distinctPayers"] == 3 and s["ledger"]["topPayerSharePct"] == 50.0


def test_level_gates(pool):
    c, chain, desk = make(pool)
    sid = c.post("/v1/sessions").json()["id"]
    assert c.post(f"/v1/sessions/{sid}/borrow", json={"amountXrp": 2}).status_code == 409
    assert c.post(f"/v1/sessions/{sid}/credential").status_code == 409
    assert c.post(f"/v1/sessions/{sid}/default").status_code == 409
    assert c.get("/v1/sessions/nope").status_code == 404


def test_ask_cap(pool):
    c, chain, desk = make(pool)
    sid = c.post("/v1/sessions").json()["id"]
    c.post(f"/v1/sessions/{sid}/income")
    for bad in (0.5, 5.000001, 6, 50, -1):
        assert c.post(f"/v1/sessions/{sid}/borrow", json={"amountXrp": bad}).status_code == 422, bad
    assert "POST /v1/loan-requests" not in desk.calls
    r = c.post(f"/v1/sessions/{sid}/borrow", json={"amountXrp": 5})
    assert r.status_code == 200 and r.json()["loan"]["status"] in ("deciding", "held")
    s = wait_decided(c, sid)
    assert s["loan"]["principalDrops"] == str(5 * XRP)
    assert c.post(f"/v1/sessions/{sid}/borrow", json={"amountXrp": 1}).status_code == 409   # held = in progress


def test_held_never_approved(pool):
    c, chain, desk = make(pool, decision="held")
    sid = c.post("/v1/sessions").json()["id"]
    c.post(f"/v1/sessions/{sid}/income")
    c.post(f"/v1/sessions/{sid}/borrow", json={"amountXrp": 2})
    s = wait_decided(c, sid)
    assert s["loan"]["status"] == "held" and s["loan"]["reason"] == "score_below_auto" and s["level"] == 4
    desk.records["lr_0001"]["status"] = "expired"
    s = c.get(f"/v1/sessions/{sid}").json()
    assert s["loan"]["status"] == "expired"
    assert not any("approve" in p or "deny" in p for p in desk.calls), desk.calls
    assert "/approve" not in Path(S.__file__).read_text() and "/deny" not in Path(S.__file__).read_text()


def test_auto_then_sweep_then_default(pool):
    c, chain, desk = make(pool, decision="auto")
    sid = c.post("/v1/sessions").json()["id"]
    c.post(f"/v1/sessions/{sid}/income")
    c.post(f"/v1/sessions/{sid}/borrow", json={"amountXrp": 3})
    s = wait_decided(c, sid)
    assert s["loan"]["status"] == "auto" and s["loan"]["loanId"] == "LOAN1" and s["level"] == 5
    assert s["loan"]["sweeperPinned"] is True
    state = json.loads((pool / sid / "sweeper_state.json").read_text())
    assert state["cursor"] == chain.ledger_tip and state["borrower"] == "rPool0"   # earlier income is ignored
    chain.loans = [{"loanId": "LOAN1", "borrower": "rPool0", "periodicPaymentDrops": "1010000", "status": "active",
                    "nextPaymentDue": chain.t + 30, "paymentRemaining": 3}]
    r = c.post(f"/v1/sessions/{sid}/income").json()
    assert len(r["sweeps"]) == 1 and r["sweeps"][0]["loanPayHash"] == "PAY1" and r["sweeps"][0]["incomeHash"] == "INC2"
    assert desk.sweeps[0]["loanId"] == "LOAN1"
    assert r["session"]["sweeps"][0]["drops"] == "1010000"
    r = c.post(f"/v1/sessions/{sid}/default").json()
    assert r["default"]["coverAbsorbedDrops"] == "300000" and r["default"]["vaultLossDrops"] == "2700000"
    assert r["session"]["loan"]["status"] == "defaulted"
    assert "POST /v1/loans/LOAN1/manage" in desk.calls


def test_credential_away_and_present(pool):
    c, chain, desk = make(pool, credential_status=404)
    sid = c.post("/v1/sessions").json()["id"]
    c.post(f"/v1/sessions/{sid}/income")
    r = c.post(f"/v1/sessions/{sid}/credential").json()
    assert r["away"] is True and r["session"]["credential"] is None
    c2, chain2, desk2 = make(pool, credential_status=200)
    sid2 = c2.post("/v1/sessions").json()["id"]
    c2.post(f"/v1/sessions/{sid2}/income")
    r = c2.post(f"/v1/sessions/{sid2}/credential").json()
    assert r["credential"]["acceptHash"] == "ACC1" and r["session"]["ledger"]["hasAcceptedCredential"] is True
    assert r["session"]["score"] == 40   # one payer at 100 % share: ledger 20 + 15 credential, ask 2 of 5 XRP volume


def test_customer_topup_when_low(pool):
    c, chain, desk = make(pool)
    chain.balance = lambda address: 2 * XRP if address.startswith("rCust") else 100 * XRP
    sid = c.post("/v1/sessions").json()["id"]
    c.post(f"/v1/sessions/{sid}/income")
    assert chain.faucets == ["rCust0"]


def test_policy_untouched():
    import subprocess
    root = Path(S.__file__).resolve().parents[1]
    assert subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "lending/policy.json"], cwd=root).returncode == 0
