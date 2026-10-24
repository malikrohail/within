"""--llm loop with a fake Anthropic client: no API calls, no purchases."""
from types import SimpleNamespace as NS

import demo


class FakeBuyer:
    def __init__(self):
        self.calls = []

    def buy(self, merchant, path, purpose):
        self.calls.append((merchant, path, purpose))
        if merchant == "rogue":
            return {"decision": "refused", "reason": "merchant_not_allowed"}
        return {"decision": "auto", "tx": "AB" * 32, "status": 200, "body": {"ok": True}}


class FakeClient:
    def __init__(self):
        self.requests = []
        turns = [[NS(type="tool_use", id=f"t{i}", name=name, input={"purpose": f"why {name}"})]
                 for i, name in enumerate(demo.LLM_TOOLS)]
        self.responses = [NS(stop_reason="tool_use", content=c) for c in turns]
        self.responses.append(NS(stop_reason="end_turn", content=[NS(type="text", text="brief")]))
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses[len(self.requests) - 1]


def test_llm_mode_runs_all_four_tools_through_the_buyer(capsys):
    buyer, client = FakeBuyer(), FakeClient()
    assert demo.run_llm(buyer, client=client) == 0
    assert buyer.calls == [("good", "/lookup", "why lookup"), ("good", "/infer", "why infer"),
                           ("good", "/dataset", "why dataset"), ("rogue", "/lookup", "why rogue_lookup")]
    assert client.requests[0]["model"] == "claude-sonnet-5-5"
    results = [part for m in client.requests[-1]["messages"] if m["role"] == "user" and isinstance(m["content"], list)
               for part in m["content"]]
    refused = next(r for r in results if r["tool_use_id"] == "t3")
    assert '"merchant_not_allowed"' in refused["content"]
    out = capsys.readouterr().out
    assert "tool=rogue_lookup path=/lookup decision=refused reason=merchant_not_allowed" in out
