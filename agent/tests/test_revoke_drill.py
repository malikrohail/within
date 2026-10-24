"""demo.py --revoke-drill against a fake wallet over real HTTP: no keys, no ledger, no device."""
import threading
import uuid

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

import demo
from tests.serve import serve

PAY_TO = "rwKL4Bir4ED8jbMheyMGMnTWyeUcL3VpCa"
TX = "AB" * 32


def fake_wallet(granted=True, ignore_revoke=False, stale_row=False):
    """The contract's /v1/pay (source treasury), /v1/delegate and hold queue, kept in memory."""
    app = FastAPI()
    state = {"granted": granted, "pays": [], "delegates": [], "taps": []}
    rows = []  # newest first, like the real audit list
    waiters = {}
    if stale_row:
        rows.append({"id": "stale", "kind": "delegate", "status": "held", "resourceUrl": "delegate://revoke"})

    @app.get("/v1/policy")
    def policy():
        return {"holdTimeoutSeconds": 5}

    @app.get("/v1/delegate")
    def get_delegate():
        perms = ["Payment"] if state["granted"] else []
        return {"treasury": "rTreasury", "agent": "rAgent", "permissions": perms,
                "objects": [{"LedgerEntryType": "Delegate", "Permissions": perms}] if perms else []}

    @app.post("/v1/delegate")
    def post_delegate(body: dict):
        action = body["action"]
        state["delegates"].append(action)
        row = {"id": uuid.uuid4().hex[:12], "kind": "delegate", "status": "held", "resourceUrl": f"delegate://{action}"}
        rows.insert(0, row)
        event = threading.Event()
        waiters[row["id"]] = event
        if not event.wait(5):
            return JSONResponse(status_code=408, content={"reason": "hold_timeout"})
        state["granted"] = action == "grant"
        row.update(status="approved", txHash=TX)
        return {"action": action, "requestId": row["id"], "txHash": TX, "engineResult": "tesSUCCESS",
                "permissions": ["Payment"] if state["granted"] else []}

    @app.get("/v1/requests")
    def list_requests(limit: int = 200):
        return rows[:limit]

    @app.post("/v1/requests/{request_id}/device-tap")
    def device_tap(request_id: str):
        state["taps"].append(request_id)
        event = waiters.pop(request_id, None)
        if event is None:
            return JSONResponse(status_code=409, content={"reason": "not_pending"})
        event.set()
        return JSONResponse(status_code=202, content={"ok": True})

    @app.post("/v1/pay")
    def pay(body: dict):
        state["pays"].append(body)
        if state["granted"] or ignore_revoke:
            return {"decision": "auto", "requestId": "p", "source": "treasury", "signer": "hot (delegated)",
                    "account": "rTreasury", "txHash": TX, "engineResult": "tesSUCCESS"}
        return JSONResponse(status_code=403, content={
            "decision": "refused", "requestId": "p", "source": "treasury", "reason": "terNO_DELEGATE_PERMISSION",
            "engineResult": "terNO_DELEGATE_PERMISSION", "txHash": None})

    return app, state


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(demo, "load_merchants", lambda: {"good": {"address": PAY_TO, "port": 8001}})
    monkeypatch.setattr(demo, "DRILL_POLL_SECONDS", 0.05)


@pytest.mark.parametrize("start_granted", [True, False])
def test_drill_happy_path_exits_zero(capsys, start_granted):
    app, state = fake_wallet(granted=start_granted)
    with serve(app) as url:
        assert demo.run_revoke_drill(url) == 0
    out = capsys.readouterr().out
    assert state["delegates"] == (["grant"] if not start_granted else []) + ["revoke", "grant"]
    assert state["granted"]
    assert len(state["pays"]) == 2
    for body in state["pays"]:
        assert body["source"] == "treasury"
        assert body["purpose"] == "revoke drill: delegated payment"
        req = body["requirements"]
        assert (req["scheme"], req["network"], req["asset"], req["amount"], req["payTo"], req["maxTimeoutSeconds"]) == \
            ("exact", "xrpl:1", "XRP", "1000", PAY_TO, 10)
    invoices = [b["requirements"]["extra"]["invoiceId"] for b in state["pays"]]
    assert invoices[0].startswith("drill-2-") and invoices[1].startswith("drill-4-")
    assert f"drill step=2 pay status=200 decision=auto engine_result=tesSUCCESS tx={TX} " \
           f"explorer=https://testnet.xrpl.org/transactions/{TX}" in out
    assert "drill step=3 revoke status=200" in out and 'permissions=[]' in out
    assert "drill step=4 pay status=403 decision=refused engine_result=terNO_DELEGATE_PERMISSION tx=None" in out
    assert "(ter = not applied, no ledger entry)" in out
    assert "drill step=4 delegate status=200 treasury=rTreasury agent=rAgent permissions=[] objects=[]" in out
    assert 'drill step=5 delegate status=200 treasury=rTreasury agent=rAgent permissions=["Payment"]' in out
    assert "MISMATCH" not in out
    assert "drill done: all checks passed" in out


def test_step4_mismatch_exits_nonzero_and_still_regrants(capsys):
    app, state = fake_wallet(ignore_revoke=True)
    with serve(app) as url:
        assert demo.run_revoke_drill(url) == 1
    out = capsys.readouterr().out
    assert "drill step=4 pay status=200" in out and "MISMATCH expected=refused/terNO_DELEGATE_PERMISSION" in out
    assert state["delegates"] == ["revoke", "grant"]
    assert state["granted"]
    assert "drill done: FAILED step4_refused" in out


def test_drill_taps_the_new_row_not_a_stale_one():
    app, state = fake_wallet(stale_row=True)
    with serve(app) as url:
        assert demo.run_revoke_drill(url) == 0
    assert "stale" not in state["taps"]
    assert len(state["taps"]) == 2
