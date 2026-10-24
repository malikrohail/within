"""Security review 2: C1/C4 checklist probes and adversarial probes for
the terms Memo, the restart reconcile, the credentials route, SECOND_OPINION=off and the LLM budget. Offline: FakeLedger,
synthetic keys, no devnet. Every test asserts the behaviour the checklist or contract demands; a failing test is a finding."""
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient
from xrpl.core.binarycodec import decode
from xrpl.wallet import Wallet

import auth
import common
import desk
import llm
import policy as pol
import reconcile as R
from tests.test_auth import approval_tx, signed_blob, terms_memo
from tests.test_desk import GOOD, T0, XRP, _ledger_approval, audit_rows, body, env  # noqa: F401 - env is a fixture

TOK = {"X-Desk-Token": "test-token"}


def _put(env, **over):
    r = env["c"].put("/v1/policy", json={**pol.DEFAULT_POLICY, **over})
    assert r.status_code == 200, r.text
    return pol.policy_hash(r.json())


def _inflight():
    return set(desk.store().inflight)


# ---- C1: policy tightened mid-flight (FIXES.md checklist 1-7) ----------------------------------------------------
def test_c1_approve_blocked_by_route_put_during_testnet_read(env, monkeypatch):
    """Checklist probe 1: pause fetch_testnet_tx on a held 60, PUT maxPrincipalDrops 100 -> 50 through the route from
    another thread, release a matching receipt: 409, record still held, no co-sign, approve_blocked carries the new hash."""
    key = Wallet.create()
    monkeypatch.setenv("DESK_APPROVER_ACCOUNT", key.address)
    rec = env["c"].post("/v1/loan-requests", json=body(60)).json()
    assert rec["status"] == "held"
    gate, inside = threading.Event(), threading.Event()

    def read(h):
        inside.set()
        gate.wait(5)
        return _ledger_approval(rec["loanSetHash"], key)
    env["fake"].fetch_testnet_tx = read
    out = {}
    t = threading.Thread(target=lambda: out.update(
        r=env["c"].post(f"/v1/loan-requests/{rec['id']}/approve", json={"approvalTxHash": "A" * 64})))
    t.start()
    assert inside.wait(5)
    h_new = _put(env, maxPrincipalDrops=str(50 * XRP))
    gate.set()
    t.join(10)
    r = out["r"]
    assert r.status_code == 409, r.text
    assert env["fake"].cosigned == [] and _inflight() == set()
    got = env["c"].get(f"/v1/loan-requests/{rec['id']}").json()
    assert got["status"] == "held" and got["policyHash"] == rec["policyHash"]
    row = audit_rows(env, "approve_blocked")[-1]
    assert row["policyHash"] == rec["policyHash"] and row["recheckPolicyHash"] == h_new != rec["policyHash"]


def test_c1_approve_block_reason_is_policy_changed_mid_flight(env, monkeypatch):
    """Checklist item 3: when the gate hash differs from rec.policyHash and the fresh decision blocks, the reason is
    policy_changed_mid_flight and the underlying rule is kept in the audit line."""
    key = Wallet.create()
    monkeypatch.setenv("DESK_APPROVER_ACCOUNT", key.address)
    rec = env["c"].post("/v1/loan-requests", json=body(60)).json()

    def read(h):
        pol.save_policy({**pol.DEFAULT_POLICY, "maxPrincipalDrops": str(50 * XRP)}, env["dir"] / "policy.json")
        return _ledger_approval(rec["loanSetHash"], key)
    env["fake"].fetch_testnet_tx = read
    r = env["c"].post(f"/v1/loan-requests/{rec['id']}/approve", json={"approvalTxHash": "A" * 64})
    assert r.status_code == 409 and env["fake"].cosigned == []
    row = audit_rows(env, "approve_blocked")[-1]
    assert r.json()["detail"] == "policy_changed_mid_flight", r.json()
    assert row.get("recheckReason") == "over_max_principal"


def test_c1_auto_refused_by_route_put_during_second_opinion(env, monkeypatch):
    """Checklist probe 2: pause the second opinion on an auto 10, PUT maxPrincipalDrops + maxAutoPrincipalDrops to 5
    through the route, release: refused, no co-sign, blob dropped, auto_recheck_blocked with the new hash."""
    gate, inside = threading.Event(), threading.Event()

    def slow_review(*a, **k):
        inside.set()
        gate.wait(5)
        return None
    monkeypatch.setattr(desk.second_opinion, "review", slow_review)
    out = {}
    t = threading.Thread(target=lambda: out.update(r=env["c"].post("/v1/loan-requests", json=body(10))))
    t.start()
    assert inside.wait(5)
    h_new = _put(env, maxPrincipalDrops=str(5 * XRP), maxAutoPrincipalDrops=str(5 * XRP))
    gate.set()
    t.join(10)
    rec = out["r"].json()
    assert rec["decision"] == "auto" and rec["status"] == "refused" and rec["reason"] is not None
    assert env["fake"].cosigned == [] and _inflight() == set()
    assert rec["policyHash"] == pol.policy_hash(pol.DEFAULT_POLICY) and rec["recheckPolicyHash"] == h_new
    row = audit_rows(env, "auto_recheck_blocked")[-1]
    assert (row["policyHash"], row["recheckPolicyHash"]) == (rec["policyHash"], h_new)
    saved = json.loads((env["dir"] / "data" / "requests.json").read_text())
    assert desk._BLOB not in saved[0]  # refused: blob dropped


def test_c1_auto_block_reason_is_policy_changed_mid_flight(env, monkeypatch):
    """Checklist item 3 on the auto path."""
    tight = {**pol.DEFAULT_POLICY, "maxPrincipalDrops": str(5 * XRP), "maxAutoPrincipalDrops": str(5 * XRP)}
    monkeypatch.setattr(desk.second_opinion, "review",
                        lambda *a, **k: pol.save_policy(tight, env["dir"] / "policy.json") and None)
    rec = env["c"].post("/v1/loan-requests", json=body(10)).json()
    assert rec["status"] == "refused" and env["fake"].cosigned == []
    assert rec["reason"] == "policy_changed_mid_flight", rec["reason"]
    assert audit_rows(env, "auto_recheck_blocked")[-1].get("recheckReason") == "over_max_principal"


def test_c1_control_benign_put_during_second_opinion_still_signs(env, monkeypatch):
    """Checklist control: a PUT that keeps the request permitted (minScore 41) lands during the pause: still signs,
    record keeps the hash it was decided under, recheckPolicyHash is the new hash."""
    gate, inside = threading.Event(), threading.Event()

    def slow_review(*a, **k):
        inside.set()
        gate.wait(5)
        return None
    monkeypatch.setattr(desk.second_opinion, "review", slow_review)
    out = {}
    t = threading.Thread(target=lambda: out.update(r=env["c"].post("/v1/loan-requests", json=body(10))))
    t.start()
    assert inside.wait(5)
    h_new = _put(env, minScore=41)
    gate.set()
    t.join(10)
    rec = out["r"].json()
    assert rec["status"] == "auto" and env["fake"].cosigned == ["AABB"]
    assert rec["policyHash"] == pol.policy_hash(pol.DEFAULT_POLICY) and rec["recheckPolicyHash"] == h_new
    assert _inflight() == set()


def test_c1_auto_gate_fails_closed_when_policy_unloadable(env, monkeypatch):
    """Checklist item 5: policy.json fails to load at the gate (ValueError). Must hold, never sign, never 500 with the
    id left in inflight."""
    def review(*a, **k):
        (env["dir"] / "policy.json").write_text("{")  # a hand edit / half write lands while the model thinks
        return None
    monkeypatch.setattr(desk.second_opinion, "review", review)
    c = TestClient(desk.app, headers=TOK, raise_server_exceptions=False)
    r = c.post("/v1/loan-requests", json=body(10))
    assert env["fake"].cosigned == []
    assert _inflight() == set(), f"lr left in inflight after a {r.status_code}"
    assert r.status_code != 500, r.text
    rec = desk.store().records["lr_0001"]
    assert rec["status"] == "held"


def test_c1_approve_gate_fails_closed_when_policy_unloadable(env, monkeypatch):
    key = Wallet.create()
    monkeypatch.setenv("DESK_APPROVER_ACCOUNT", key.address)
    rec = env["c"].post("/v1/loan-requests", json=body(60)).json()

    def read(h):
        (env["dir"] / "policy.json").write_text("{")
        return _ledger_approval(rec["loanSetHash"], key)
    env["fake"].fetch_testnet_tx = read
    c = TestClient(desk.app, headers=TOK, raise_server_exceptions=False)
    r = c.post(f"/v1/loan-requests/{rec['id']}/approve", json={"approvalTxHash": "A" * 64})
    assert r.status_code != 200 and env["fake"].cosigned == []
    assert _inflight() == set()
    assert desk.store().records[rec["id"]]["status"] == "held"


def test_c1_put_policy_never_waits_on_the_lend_lock(env):
    """Checklist item 7: put_policy takes only _POLICY_LOCK, so a PUT completes while a co-sign holds _LEND_LOCK."""
    done = threading.Event()
    with desk._LEND_LOCK:
        t = threading.Thread(target=lambda: (_put(env, minScore=41), done.set()))
        t.start()
        assert done.wait(3), "PUT /v1/policy blocked behind _LEND_LOCK"
    t.join(3)


# ---- C4: expired holds and the pending cap (FIXES.md checklist 1-4) ---------------------------------------------
def test_c4_lapsed_hold_frees_cap_without_get_then_expires_once(env):
    c = env["c"]
    _put(env, maxPendingDrops=str(100 * XRP))
    first = c.post("/v1/loan-requests", json=body(60, blob="AA01")).json()
    assert first["status"] == "held"
    env["clock"]["t"] += pol.DEFAULT_POLICY["holdTimeoutSeconds"]
    second = c.post("/v1/loan-requests", json=body(60, blob="AA02")).json()  # no GET in between
    assert second["status"] == "held" and second["reason"] == "over_auto_limit"
    assert audit_rows(env, "loan_request_expired") == [] or len(audit_rows(env, "loan_request_expired")) == 1
    got = c.get(f"/v1/loan-requests/{first['id']}").json()
    assert got["status"] == "expired" and got["decidedBy"] == "timeout"
    c.get("/v1/loan-requests")
    assert len(audit_rows(env, "loan_request_expired")) == 1


def test_c4_lapsed_hold_with_approve_in_flight_still_counts(env):
    """Checklist item 2: a held record whose approve is inside the signing section (id in inflight) keeps its cap room
    even after its deadline passes."""
    c = env["c"]
    _put(env, maxPendingDrops=str(100 * XRP))
    first = c.post("/v1/loan-requests", json=body(60, blob="AA01")).json()
    gate, inside = threading.Event(), threading.Event()
    orig = env["fake"].vault_state

    def slow_vault(*a):
        inside.set()
        gate.wait(5)
        return orig(*a)
    env["fake"].vault_state = slow_vault
    out = {}
    t = threading.Thread(target=lambda: out.update(r=c.post(f"/v1/loan-requests/{first['id']}/approve", json={})))
    t.start()
    assert inside.wait(5)
    assert first["id"] in _inflight()
    env["clock"]["t"] += pol.DEFAULT_POLICY["holdTimeoutSeconds"]
    env["fake"].vault_state = orig
    second = c.post("/v1/loan-requests", json=body(60, blob="AA02")).json()
    assert second["status"] == "refused" and second["reason"] == "pending_exposure_cap"
    gate.set()
    t.join(10)
    assert out["r"].status_code == 200 and env["fake"].cosigned == ["AA01"]


# ---- b79532b: loan-terms Memo ------------------------------------------------------------------------------------
def test_terms_memo_matching_hash_but_other_borrower_or_format_is_refused():
    borrower, broker = Wallet.create(), Wallet.create()
    blob = signed_blob(borrower, broker, principal_xrp=60)
    h = auth.loan_set_hash(blob)
    right = auth.loan_terms_text(blob)
    other = Wallet.create().address
    for text in (right.replace(borrower.address, other),            # same amount, different borrower
                 right.replace("60 XRP", "60.0 XRP"),                # same value, different format
                 right.replace("60 XRP", "60 XRP "),                 # trailing space
                 right.upper(),                                      # case
                 right.replace(f"{decode(blob)['PaymentTotal']} payments", "1 payments")):
        tx = approval_tx(h)
        tx["tx_json"]["Memos"].append(terms_memo(text))
        assert auth.verify_approval_payment(tx, h, approval_tx(h)["tx_json"]["Account"]) is None
        assert auth.verify_loan_terms(tx, blob) == "terms_mismatch", text
    first_wrong = approval_tx(h)
    first_wrong["tx_json"]["Memos"] += [terms_memo(right.replace("60 XRP", "6 XRP")), terms_memo(right)]
    assert auth.verify_loan_terms(first_wrong, blob) == "terms_mismatch"   # the first loan-terms Memo is the one checked
    non_ascii = approval_tx(h)
    non_ascii["tx_json"]["Memos"].append({"Memo": {"MemoType": auth.TERMS_MEMO_TYPE,
                                                   "MemoData": right.encode().hex().upper() + "C3A9"}})
    assert auth.verify_loan_terms(non_ascii, blob) == "terms_mismatch"


def test_terms_memo_before_approval_memo_is_not_an_approval():
    """Memo order is part of the contract: the approval Memo must be Memos[0]."""
    borrower, broker = Wallet.create(), Wallet.create()
    blob = signed_blob(borrower, broker, principal_xrp=60)
    h = auth.loan_set_hash(blob)
    tx = approval_tx(h)
    tx["tx_json"]["Memos"].insert(0, terms_memo(auth.loan_terms_text(blob)))
    assert auth.verify_approval_payment(tx, h, tx["tx_json"]["Account"]) == "approval_wrong_memo_type"


# ---- 8f6b0b4 / 26b7f9c: restart reconcile ------------------------------------------------------------------------
def _account_tx_with(loan_set: dict, result="tesSUCCESS"):
    return {"transactions": [{"validated": True, "hash": "FOREIGN", "tx_json": loan_set,
                              "meta": {"TransactionResult": result, "AffectedNodes": [
                                  {"CreatedNode": {"LedgerEntryType": "Loan", "LedgerIndex": "L_FOREIGN"}}]}}]}


def test_repro_reconcile_lands_a_loan_set_the_desk_never_signed(env, monkeypatch):
    """A validated LoanSet from the borrower with the same Sequence but another LoanBrokerID / Counterparty (a loan with
    a different broker) must not settle the desk's held record as approved."""
    borrower = Wallet.create()
    foreign = {"TransactionType": "LoanSet", "Account": borrower.address, "Sequence": 5,
               "Counterparty": "rOtherBroker111111111111111111111", "LoanBrokerID": "F" * 64,
               "PrincipalRequested": str(60 * XRP)}
    monkeypatch.setattr(common, "_rpc", lambda req: _account_tx_with(foreign))
    hit = desk.Ledger().find_loan_set(borrower.address, 5)
    assert hit is None, f"find_loan_set returned a LoanSet with LoanBrokerID {foreign['LoanBrokerID'][:8]}..: {hit}"


def test_reconcile_consumed_sequence_with_failed_result_is_not_approved():
    bo, br = Wallet.create(), Wallet.create()
    rec = {"id": "lr_0001", "status": "held", "txHash": None, "loanId": None, "decidedBy": "policy", "reason": None,
           R.BLOB_KEY: signed_blob(bo, br, principal_xrp=60)}
    action, info = R.classify(rec, 6, 900, {"engineResult": "tecINSUFFICIENT_FUNDS", "hash": "HFAIL", "loanId": None})
    assert action == "consumed" and info == {}
    R.apply(rec, action, info, 1)
    assert rec["status"] != "approved" and R.BLOB_KEY not in rec


def test_boot_reconcile_thread_survives_a_dead_node(env, monkeypatch, capsys):
    class Down:
        def account_sequence(self, a):
            raise RuntimeError("node down")

        ledger_index = find_loan_set = account_sequence
    held = env["c"].post("/v1/loan-requests", json=body(60, blob=signed_blob(Wallet.create(), Wallet.create(), 60))).json()
    monkeypatch.setattr(desk, "get_ledger", lambda: Down())
    desk._reconcile_now()
    assert "reconcile on boot skipped" in capsys.readouterr().out
    assert env["c"].get(f"/v1/loan-requests/{held['id']}").json()["status"] == "held"


# ---- 4f679c4: POST /v1/broker/credentials ------------------------------------------------------------------------
def test_credentials_route_fails_closed_and_rejects_wrong_token(env, monkeypatch):
    c = TestClient(desk.app)
    assert c.post("/v1/broker/credentials", json={"subject": GOOD}, headers={"X-Desk-Token": "nope"}).status_code == 401
    assert c.post("/v1/broker/credentials", json={"subject": GOOD}, headers={"Authorization": "Bearer test-token"}).status_code == 401
    monkeypatch.delenv("DESK_TOKEN")
    assert c.post("/v1/broker/credentials", json={"subject": GOOD}, headers=TOK).status_code == 503
    assert env["fake"].issued == {}


def test_credentials_route_returns_200_on_a_failed_credential_create(env):
    """Observation: engineResult is passed through, not checked (same contract as /v1/broker/cover)."""
    env["fake"].create_credential = lambda s: {"hash": "HX", "engineResult": "tecNO_TARGET", "validated": True}
    r = env["c"].post("/v1/broker/credentials", json={"subject": GOOD})
    assert r.status_code == 200 and r.json()["engineResult"] == "tecNO_TARGET"


# ---- 6d18faa: SECOND_OPINION=off -------------------------------------------------------------------------------
def test_repro_second_opinion_off_in_dotenv_leaks_into_a_normal_start(monkeypatch, capsys):
    """INTERFACES.md: 'a shell switch ... the shell value wins; lending/.env leaves it on'. A persisted
    SECOND_OPINION=off in lending/.env must not turn the model off for a non-scripted start."""
    monkeypatch.delenv("SECOND_OPINION", raising=False)
    monkeypatch.setattr(desk.common, "read_env", lambda: {"SECOND_OPINION": "off"})
    desk.load_auth_env()
    assert not desk.second_opinion.is_off(), "SECOND_OPINION=off read from lending/.env"
    assert "second opinion OFF" not in capsys.readouterr().out


def test_second_opinion_off_never_reaches_llm_and_marks_refusals(env, monkeypatch):
    monkeypatch.setenv("SECOND_OPINION", "off")
    monkeypatch.setattr(llm, "ask", lambda *a, **k: (_ for _ in ()).throw(AssertionError("model called")))
    monkeypatch.setattr(desk.second_opinion, "review", lambda *a, **k: llm.ask())
    rec = env["c"].post("/v1/loan-requests", json=body(60)).json()
    assert rec["status"] == "held" and rec["secondOpinion"] == "off" and rec["secondOpinionMs"] is None
    assert audit_rows(env, "second_opinion") == []


# ---- c54fcf6: anthropic SDK path, cost log, budget stop ---------------------------------------------------------
class _Usage:
    input_tokens, output_tokens, cache_read_input_tokens = 1000, 1000, 0


def _blocking_anthropic(monkeypatch, gate, inside, calls):
    import types

    class Messages:
        def create(self, **kw):
            calls.append(kw)
            inside.set()
            gate.wait(5)
            return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text='{"ok": true}')],
                                         usage=_Usage(), id="msg")

    class Client:
        def __init__(self, **kw):
            self.messages = Messages()

    monkeypatch.setitem(__import__("sys").modules, "anthropic", types.SimpleNamespace(Anthropic=Client))


def test_repro_budget_stop_races_concurrent_calls(monkeypatch):
    """Two asks that both pass the budget check before either appends its cost both reach the API: the stop is
    check-then-act with no lock, so the budget can be exceeded by as many calls as run concurrently."""
    monkeypatch.setattr(llm, "_api_key", lambda: "k")
    monkeypatch.setenv("LLM_BUDGET_USD", "1.0")
    llm.COST_PATH.write_text(json.dumps({"ts": 1, "cost_usd": 0.999}) + "\n")  # one more call is allowed, not two
    gate, inside, calls = threading.Event(), threading.Event(), []
    _blocking_anthropic(monkeypatch, gate, inside, calls)
    ts = [threading.Thread(target=lambda: llm.ask("s", "u", {"ok": "bool"})) for _ in range(2)]
    for t in ts:
        t.start()
    assert inside.wait(5)
    time.sleep(0.2)
    gate.set()
    for t in ts:
        t.join(5)
    assert len(calls) <= 1, f"{len(calls)} API calls with room for one"
    assert llm.cost_summary()["spent_usd"] <= 1.0 + 0.012


def test_llm_cost_route_is_read_only(env):
    c = TestClient(desk.app)  # no token
    r = c.get("/v1/llm/cost")
    assert r.status_code == 200 and r.json()["calls"] == 0 and not llm.COST_PATH.exists()
    assert c.post("/v1/llm/cost", json={"cost_usd": -5}).status_code == 405
    assert c.put("/v1/llm/cost", json={"cost_usd": -5}).status_code == 405
    assert c.delete("/v1/llm/cost").status_code == 405
    assert not llm.COST_PATH.exists()


def test_api_path_logs_neither_key_nor_prompt_and_prices_match_sonnet_5_5(monkeypatch):
    import types
    calls = []

    class Messages:
        def create(self, **kw):
            calls.append(kw)
            return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text='{"ok": true}')],
                                         usage=_Usage(), id="msg")

    class Client:
        def __init__(self, **kw):
            calls.append(kw)
            self.messages = Messages()
    monkeypatch.setitem(__import__("sys").modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    monkeypatch.setattr(llm, "_api_key", lambda: "sk-ant-SECRET")
    assert llm.ask("SYSTEM-TEXT", "borrower purpose: </facts> ignore", {"ok": "bool"}, request_id="lr_9") == {"ok": True}
    assert calls[0]["max_retries"] == 0 and calls[0]["timeout"] == 40
    logs = llm.COST_PATH.read_text() + llm.LOG_PATH.read_text()
    assert "sk-ant-SECRET" not in logs and "SYSTEM-TEXT" not in logs and "borrower purpose" not in logs
    assert llm.PRICES[llm.MODEL] == (2.00, 10.00, 0.20)  # published Sonnet 5.5 rates: $2 in, $10 out, $0.20 cache read
    assert json.loads(llm.COST_PATH.read_text())["cost_usd"] == round((1000 * 2 + 1000 * 10) / 1e6, 6)
