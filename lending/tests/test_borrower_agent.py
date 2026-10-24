"""borrower_agent.run with a fake model and a fake desk. No network, no model."""
import json

import pytest

import borrower_agent as ba
import llm
import policy as pol

XRP = 1_000_000
SUPPLIER = "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe"
INVOICES = [{"invoice": "INV-AGENT-1", "supplier": SUPPLIER, "drops": str(29 * XRP), "due": "2026-10-30"}]
VAULT = {"assetsTotalDrops": str(132 * XRP), "assetsAvailableDrops": str(66 * XRP), "loansOutstandingDrops": str(66 * XRP),
         "debtTotalDrops": str(66 * XRP), "coverDrops": str(27 * XRP), "utilizationPct": 50.0, "coverRatioPct": 41.0,
         "phase": "lending"}


def wc_ask(principal=30, fee="1000000", invoice="INV-AGENT-1", term=270, purpose="inventory"):
    return {"invoice": invoice, "principalDrops": str(principal * XRP), "termSeconds": term, "purpose": purpose,
            "feeDrops": fee}


def turn(ask, say="thinking", wait=False):
    return {"say": say, "ask": ask, "wait": wait}


class FakeDesk:
    def __init__(self, replies=None, final=None):
        self.replies = list(replies or [])  # (status, record) per submit
        self.final = final
        self.submitted, self.notes, self.waited = [], [], []
        self.address = "rBorrower"

    def policy(self):
        return dict(pol.DEFAULT_POLICY)

    def vault(self):
        return dict(VAULT)

    def history(self):
        return []

    def submit(self, plan):
        self.submitted.append(plan)
        return self.replies.pop(0)

    def note(self, rid, text):
        self.notes.append((rid, text))
        return True

    def wait(self, rid, timeout):
        self.waited.append((rid, timeout))
        return self.final


class FakeAsk:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, system, user, schema, timeout_s=40, request_id=None):
        assert schema is ba.SCHEMA
        self.prompts.append(json.loads(user))
        return self.answers.pop(0) if self.answers else None


def run(ask, desk, **kw):
    return ba.run("Pay supplier invoice INV-AGENT-1 of 29 XRP this week", INVOICES, desk, ask_fn=ask,
                  out=lambda line: None, sleep=lambda s: None, **kw)


def held_rec(rid="lr_0042"):
    return {"id": rid, "kind": "working_capital", "status": "held", "reason": "over_auto_limit",
            "principalDrops": str(30 * XRP), "score": 85}


def approved_rec(rid="lr_0042"):
    return {**held_rec(rid), "status": "approved", "decidedBy": "human", "txHash": "LOANSETHASH",
            "engineResult": "tesSUCCESS", "loanId": "LOANID",
            "batch": {"supplier": SUPPLIER, "supplierDrops": str(29 * XRP), "feeDrops": str(XRP), "invoice": "INV-AGENT-1",
                      "hash": "BATCHHASH", "engineResult": "tesSUCCESS",
                      "legs": [{"result": "tesSUCCESS"}, {"result": "tesSUCCESS"}]}}


def test_model_none_stops_cleanly_without_money():
    desk = FakeDesk()
    res = run(FakeAsk(), desk)
    assert res["outcome"] == "model_unavailable" and desk.submitted == [] and res["requestIds"] == []
    assert "stopping" in res["lines"][-1]


def test_unknown_invoice_dropped_and_fed_back():
    desk = FakeDesk()
    ask = FakeAsk(turn(wc_ask(invoice="INV-EVIL")), None)
    res = run(ask, desk)
    assert desk.submitted == [] and res["outcome"] == "model_unavailable"
    fb = ask.prompts[1]["earlierTurnsThisRun"][0]
    assert "INV-EVIL" in fb["outcome"] and "not in my invoice list" in fb["outcome"]


@pytest.mark.parametrize("bad, words", [
    (wc_ask(principal=101), "over the policy cap"),
    (wc_ask(term=60), "termSeconds 60 is outside"),
    (wc_ask(term=90_000), "outside"),
    (wc_ask(principal=29), "plus fee"),                       # 29 + 1 > 29: cannot fund its own disbursement
    (wc_ask(fee=None), "feeDrops"),
    (wc_ask(fee="0"), "feeDrops"),
    (wc_ask(purpose="yachts"), "purpose"),
    ({**wc_ask(), "principalDrops": "30.5"}, "not a positive integer string"),
    ({**wc_ask(), "principalDrops": "030000000"}, "not a positive integer string"),
])
def test_out_of_policy_ask_never_submitted(bad, words):
    desk = FakeDesk()
    ask = FakeAsk(turn(bad))
    run(ask, desk)
    assert desk.submitted == []
    assert words in ask.prompts[1]["earlierTurnsThisRun"][0]["outcome"]


def test_supplier_and_amount_come_from_invoice_list_only():
    """Extra keys the model invents (an address, a supplier amount) are ignored: code builds the disbursement."""
    desk = FakeDesk(replies=[(200, {**held_rec(), "status": "auto", "decidedBy": "policy", "txHash": "H",
                                    "engineResult": "tesSUCCESS", "loanId": "L"})])
    ask = FakeAsk(turn({**wc_ask(), "supplier": "rEvil1111111111111111111111", "supplierDrops": "1"}))
    run(ask, desk)
    (plan,) = desk.submitted
    assert plan["disbursement"] == {"supplier": SUPPLIER, "supplierDrops": str(29 * XRP), "feeDrops": str(XRP),
                                    "invoice": "INV-AGENT-1"}
    assert plan["principalDrops"] == str(30 * XRP) and plan["termSeconds"] == 270


def test_held_then_approved_cites_hashes_and_posts_notes():
    desk = FakeDesk(replies=[(200, held_rec())], final=approved_rec())
    res = run(FakeAsk(turn(wc_ask(), say="I will ask for 30 XRP to pay INV-AGENT-1.")), desk)
    assert res["outcome"] == "held_approved" and res["requestIds"] == ["lr_0042"]
    assert desk.waited == [("lr_0042", 180)]
    texts = [t for rid, t in desk.notes if rid == "lr_0042"]
    assert texts[0] == "I will ask for 30 XRP to pay INV-AGENT-1."   # pre-id say flushed onto the record
    assert "waiting for a human" in texts[1] and "over_auto_limit" in texts[1]
    assert "LOANSETHASH" in texts[2] and "BATCHHASH" in texts[2] and "a human approved it" in texts[2]
    assert len(texts) == len(res["lines"]) == 3


def test_refused_reason_fed_back_then_adapts():
    refused = {"id": "lr_0001", "kind": "working_capital", "status": "refused", "reason": "vault_utilization",
               "principalDrops": str(60 * XRP), "score": 85}
    desk = FakeDesk(replies=[(200, refused), (200, held_rec("lr_0002"))], final=approved_rec("lr_0002"))
    ask = FakeAsk(turn(wc_ask(principal=60)), turn(wc_ask(principal=30)))
    res = run(ask, desk)
    assert res["outcome"] == "held_approved" and res["requestIds"] == ["lr_0001", "lr_0002"]
    fb = ask.prompts[1]["earlierTurnsThisRun"][0]
    assert fb["requestId"] == "lr_0001" and "vault_utilization" in fb["outcome"] and "80% limit" in fb["outcome"]


def test_desk_http_error_fed_back():
    desk = FakeDesk(replies=[(409, {"detail": "vault_in_subscription"})])
    ask = FakeAsk(turn(wc_ask()))
    res = run(ask, desk)
    assert "vault_in_subscription" in ask.prompts[1]["earlierTurnsThisRun"][0]["outcome"]
    assert res["outcome"] == "model_unavailable"


def test_max_turns_then_stop():
    desk = FakeDesk()
    ask = FakeAsk(*[turn(wc_ask(invoice="NOPE"))] * 6)
    res = run(ask, desk, max_turns=4)
    assert res["outcome"] == "out_of_turns" and len(ask.prompts) == 4 and desk.submitted == []


def test_no_ask_stops_or_waits():
    desk = FakeDesk()
    assert run(FakeAsk(turn(None, wait=False)), desk)["outcome"] == "stopped_by_model"
    ask = FakeAsk(turn(None, wait=True), turn(None, wait=False))
    assert run(ask, desk)["outcome"] == "stopped_by_model" and len(ask.prompts) == 2


def test_plain_sentence_mirrors_copy():
    p = pol.DEFAULT_POLICY
    r = {"principalDrops": str(30 * XRP), "score": 85, "reason": "over_auto_limit", "status": "held"}
    assert ba.plain_sentence(r, p) == ("Held for you. 30 XRP is more than the 20 XRP the desk approves on its own. "
                                       "The score itself looks fine.")
    r = {"principalDrops": str(10 * XRP), "score": 20, "reason": "score_too_low", "status": "refused"}
    assert ba.plain_sentence(r, p) == "Refused. The score is 20; the desk lends from 40. No transaction was made."
    assert "cover would fall under 10% of debt" in ba.plain_sentence({"reason": "cover_below_minimum"}, p)
    assert ba.plain_sentence({"reason": "no_broker_credential", "status": "held"}, p) == \
        "Held for you. The borrower has no KYB credential from this broker yet."


def test_example_invoices_file_loads():
    items = ba.load_invoices(ba.HERE / "invoices.example.json")
    assert items and all(set(i) >= {"invoice", "supplier", "drops"} for i in items)
    assert llm.matches({"say": "x", "ask": None, "wait": False}, ba.SCHEMA)


@pytest.mark.parametrize("outcome,code", [("auto", 0), ("held_approved", 0), ("held_denied", 0), ("held_expired", 0),
                                          ("model_unavailable", 0), ("stopped_by_model", 0), ("out_of_turns", 0),
                                          ("error", 1)])
def test_main_exit_code_nonzero_only_on_error(monkeypatch, outcome, code):
    monkeypatch.setattr(ba, "HttpDesk", lambda url: FakeDesk())
    monkeypatch.setattr(ba, "load_invoices", lambda path: INVOICES)
    monkeypatch.setattr(ba, "run", lambda *a, **k: {"outcome": outcome, "requestIds": []})
    monkeypatch.setattr("sys.argv", ["borrower_agent.py", "--goal", "pay INV-AGENT-1"])
    assert ba.main() == code


def test_plain_sentence_declared_debt_understated():
    r = {"reason": "declared_debt_understated", "status": "refused", "principalDrops": str(10 * XRP),
         "evidence": {"declared": {"existingDebtDrops": "0"}, "ledger": {"loanPrincipalDrops": str(66_666_668)}}}
    assert ba.plain_sentence(r, dict(pol.DEFAULT_POLICY)) == ("Refused. They declared 0 XRP of existing debt but the "
                                                              "ledger shows 66.67 XRP outstanding. No transaction was made.")


def test_http_desk_declares_its_on_ledger_principal(monkeypatch):
    """The agent's declared debt is computed in code from the same evidence the desk reads, never from the model,
    so a borrower with an open loan is not refused declared_debt_understated."""
    from xrpl.wallet import Wallet

    import borrower
    import common
    import evidence

    w = Wallet.create()
    seen = {}

    def ledger_evidence(addr, client, now, window_days):
        seen["addr"] = addr
        return {"loanPrincipalDrops": str(66_666_668)}

    monkeypatch.setattr(evidence, "ledger_evidence", ledger_evidence)
    monkeypatch.setattr(common, "client", lambda: None)
    monkeypatch.setattr(common, "load_accounts", lambda: {
        "accounts": {"broker": Wallet.create().address},
        "loanBrokerId": "E43DA4D38D7DA816256CA4947839187C41A113FC81AB5A3568B2C7BF7CB1CC91"})
    monkeypatch.setattr(borrower, "desk_get", lambda path, url: dict(pol.DEFAULT_POLICY))
    monkeypatch.setattr(common, "borrower_sign_loan_set", lambda wallet, tx: "BLOB")
    posted = []
    monkeypatch.setattr(borrower, "post_request", lambda body, url: (posted.append(body), (200, {}))[1])
    desk = ba.HttpDesk("http://desk", wallet=w)
    desk.submit({"principalDrops": str(10 * XRP), "termSeconds": 270, "purpose": "inventory", "disbursement": None})
    assert seen["addr"] == w.address
    assert posted[0]["declared"] == {"existingDebtDrops": "66666668"}


def test_plain_sentence_expired_tx():
    p = dict(pol.DEFAULT_POLICY)
    assert ba.plain_sentence({"reason": "txnNotFound", "status": "failed"}, p).startswith("Expired before validation.")
    assert ba.plain_sentence({"reason": "timeout_waiting", "status": "failed"}, p).startswith(
        "Timed out waiting for validation.")
    assert ba.plain_sentence({"reason": "batch:timeout_waiting", "status": "failed"}, p).startswith(
        "Loan made, timed out waiting")
    assert ba.plain_sentence({"reason": "not_validated", "status": "failed"}, p).startswith("Expired before validation.")
    assert ba.plain_sentence({"reason": "batch:txnNotFound", "status": "failed"}, p) == \
        "Loan made, batch expired before validation. No supplier leg moved."
    assert ba.plain_sentence({"reason": "tecNO_PERMISSION", "status": "failed"}, p) == \
        "The ledger refused it: tecNO_PERMISSION."


def test_default_goal_is_the_30_xrp_stage_draw(monkeypatch):
    """Stock vault headroom is ~38 XRP: the stage draw is the 29 XRP example invoice + 1 XRP fee = 30 XRP."""
    assert ba.STAGE_DRAW_XRP == 30 and "30 XRP" in ba.DEFAULT_GOAL
    inv = ba.load_invoices(ba.HERE / "invoices.example.json")
    assert int(inv[0]["drops"]) + 1 * XRP == ba.STAGE_DRAW_XRP * XRP
    seen = []
    monkeypatch.setattr(ba, "HttpDesk", lambda url: FakeDesk())
    monkeypatch.setattr(ba, "load_invoices", lambda path: INVOICES)
    monkeypatch.setattr(ba, "run", lambda goal, *a, **k: seen.append(goal) or {"outcome": "auto", "requestIds": []})
    monkeypatch.setattr("sys.argv", ["borrower_agent.py"])
    assert ba.main() == 0 and seen == [ba.DEFAULT_GOAL]
