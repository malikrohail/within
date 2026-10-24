"""llm.ask with a faked CLI. No real model call."""
import json
import subprocess
from types import SimpleNamespace

import pytest

import llm

SCHEMA = {"say": "str", "ask": [{"invoice": ["str", "null"], "principalDrops": "str", "termSeconds": "int"}, "null"],
          "wait": "bool"}
GOOD = {"say": "hi", "ask": {"invoice": "INV-1", "principalDrops": "30000000", "termSeconds": 270}, "wait": False}


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "LOG_PATH", tmp_path / "llm.jsonl")
    monkeypatch.setattr(llm.shutil, "which", lambda name: "/fake/claude")
    box = {"stdout": None, "rc": 0, "exc": None, "argv": None}

    def run(argv, **kw):
        box["argv"], box["kw"] = argv, kw
        if box["exc"]:
            raise box["exc"]
        return SimpleNamespace(returncode=box["rc"], stdout=box["stdout"], stderr="")

    monkeypatch.setattr(llm.subprocess, "run", run)
    box["log"] = lambda: [json.loads(x) for x in (tmp_path / "llm.jsonl").read_text().splitlines()]
    return box


def envelope(result, is_error=False):
    return json.dumps({"type": "result", "subtype": "success", "is_error": is_error, "result": result})


def test_ok_and_logged(cli):
    cli["stdout"] = envelope(json.dumps(GOOD))
    assert llm.ask("sys", "user", SCHEMA, request_id="t1") == GOOD
    argv = cli["argv"]
    assert argv[0] == "/fake/claude" and argv[1] == "-p" and "sys" in argv[2] and "user" in argv[2]
    assert argv[3:] == ["--output-format", "json", "--model", "claude-sonnet-5-5", "--tools", ""]
    assert argv[argv.index("--tools") + 1] == ""  # no shell, no file tools for the model
    assert cli["kw"]["timeout"] == 40
    (e,) = cli["log"]()
    assert e["requestId"] == "t1" and e["ok"] is True and e["error"] is None and "30000000" in e["raw_result"]


def test_fenced_json_tolerated(cli):
    cli["stdout"] = envelope("```json\n" + json.dumps(GOOD) + "\n```")
    assert llm.ask("s", "u", SCHEMA) == GOOD


def test_timeout_returns_none(cli):
    cli["exc"] = subprocess.TimeoutExpired(cmd="claude", timeout=3)
    assert llm.ask("s", "u", SCHEMA, timeout_s=3) is None
    (e,) = cli["log"]()
    assert e["ok"] is False and "timeout" in e["error"]


@pytest.mark.parametrize("stdout", [
    "not json at all",                                   # CLI envelope is not JSON
    envelope("Sure! Here is my answer."),                # result is not JSON
    envelope(json.dumps(GOOD), is_error=True),           # CLI says is_error
    envelope(json.dumps([GOOD])),                        # not an object
    envelope(json.dumps({**GOOD, "wait": "no"})),        # wrong type
    envelope(json.dumps({"say": "hi", "wait": False})),  # missing key
    envelope(json.dumps({**GOOD, "ask": {**GOOD["ask"], "termSeconds": True}})),   # bool is not int
    envelope(json.dumps({**GOOD, "ask": {**GOOD["ask"], "principalDrops": 30}})),  # nested type
])
def test_bad_output_returns_none(cli, stdout):
    cli["stdout"] = stdout
    assert llm.ask("s", "u", SCHEMA) is None
    assert cli["log"]()[0]["ok"] is False


def test_nonzero_exit_returns_none(cli):
    cli["rc"], cli["stdout"] = 1, envelope(json.dumps(GOOD))
    assert llm.ask("s", "u", SCHEMA) is None


def test_missing_binary_returns_none(cli, monkeypatch):
    monkeypatch.setattr(llm.shutil, "which", lambda name: None)
    cli["stdout"] = envelope(json.dumps(GOOD))
    assert llm.ask("s", "u", SCHEMA) is None
    assert cli["argv"] is None  # never ran


def test_oserror_returns_none(cli):
    cli["exc"] = OSError("exec format error")
    assert llm.ask("s", "u", SCHEMA) is None


def test_null_ask_matches():
    assert llm.matches({**GOOD, "ask": None}, SCHEMA)
    assert not llm.matches({**GOOD, "ask": {"invoice": None}}, SCHEMA)


class _Usage:
    def __init__(self, i, o, c=0):
        self.input_tokens, self.output_tokens, self.cache_read_input_tokens = i, o, c


class _Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, text, usage):
        self.content, self.usage, self.id = [_Block(text)], usage, "msg_test"


def _fake_anthropic(monkeypatch, text, usage, calls):
    import types

    class Messages:
        def create(self, **kw):
            calls.append(kw)
            return _Resp(text, usage)

    class Client:
        def __init__(self, **kw):
            calls.append({"client": sorted(kw)})
            self.messages = Messages()

    monkeypatch.setitem(__import__("sys").modules, "anthropic", types.SimpleNamespace(Anthropic=Client))


def test_api_path_costs_every_call_and_never_uses_the_cli(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_api_key", lambda: "test-key")
    monkeypatch.setattr(llm.shutil, "which", lambda _: (_ for _ in ()).throw(AssertionError("cli used")))
    _fake_anthropic(monkeypatch, '{"ok": true}', _Usage(2000, 300, 1000), calls)
    assert llm.ask("sys", "user", {"ok": "bool"}, request_id="lr_1") == {"ok": True}
    assert calls[1]["model"] == "claude-sonnet-5-5" and calls[1]["system"] == "sys" and "tools" not in calls[1]
    row = json.loads(llm.COST_PATH.read_text().splitlines()[0])
    assert row["request_id"] == "lr_1" and row["input_tokens"] == 2000 and row["output_tokens"] == 300
    assert row["cost_usd"] == round((2000 * 2.00 + 300 * 10.00 + 1000 * 0.20) / 1e6, 6)
    assert "test-key" not in llm.COST_PATH.read_text() and "test-key" not in llm.LOG_PATH.read_text()
    s = llm.cost_summary()
    assert s["calls"] == 1 and s["spent_usd"] == row["cost_usd"] and s["budget_usd"] == 80.0


def test_budget_exhausted_returns_none_without_calling(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_api_key", lambda: "test-key")
    _fake_anthropic(monkeypatch, '{"ok": true}', _Usage(1, 1), calls)
    llm.COST_PATH.write_text(json.dumps({"ts": 1, "cost_usd": 80.0}) + "\n")
    assert llm.ask("sys", "user", {"ok": "bool"}) is None
    assert calls == []
    last = json.loads(llm.LOG_PATH.read_text().splitlines()[-1])
    assert "budget_exhausted" in last["error"] and last["path"] == "api"
    monkeypatch.setenv("LLM_BUDGET_USD", "100")
    assert llm.ask("sys", "user", {"ok": "bool"}) == {"ok": True}
