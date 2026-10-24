"""demo.py step matching and step-line format, with a fake buyer: no wallet, no purchases."""
import demo

TX = "AB" * 32


def test_step5_matches_only_merchant_not_credentialed():
    assert demo.step_ok({"decision": "refused", "reason": "merchant_not_credentialed"}, "refused")
    assert not demo.step_ok({"decision": "refused", "reason": "merchant_not_allowed"}, "refused")
    assert not demo.step_ok({"decision": "refused", "reason": "daily_budget_exceeded"}, "refused")


def test_settled_step_line_carries_explorer_url():
    line = demo.step_line(1, "/lookup", {"decision": "auto", "tx": TX, "status": 200, "settled": True})
    assert line == f"step=1 path=/lookup decision=auto tx={TX} explorer=https://testnet.xrpl.org/transactions/{TX} status=200"


def test_unsettled_and_refused_lines_have_no_explorer_url():
    signed = demo.step_line(2, "/infer", {"decision": "auto", "tx": None, "signed": TX, "status": 402, "reason": "x"})
    assert signed == f"step=2 path=/infer decision=auto signed={TX} status=402 reason=x"
    refused = demo.step_line(5, "/lookup", {"decision": "refused", "reason": "merchant_not_credentialed"})
    assert refused == "step=5 path=/lookup decision=refused reason=merchant_not_credentialed"


def test_scripted_run_prints_five_lines_and_matches(monkeypatch, capsys):
    class FakeBuyer:
        def __init__(self, wallet_url):
            pass

        def buy(self, merchant, path, purpose):
            if merchant == "rogue":
                return {"decision": "refused", "reason": "merchant_not_credentialed"}
            decision = "approved" if path == "/dataset" else "auto"
            return {"decision": decision, "tx": TX, "status": 200, "settled": True}

    monkeypatch.setattr(demo, "Buyer", FakeBuyer)
    monkeypatch.setattr(demo, "warn_if_budget_short", lambda url: None)
    assert demo.run_scripted("http://wallet.invalid") == 0
    out = capsys.readouterr().out
    assert out.count("explorer=https://testnet.xrpl.org/transactions/") == 4
    assert "done: 5/5 steps matched" in out
