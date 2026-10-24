"""One headless model call. ask() never raises and returns None on any failure.

With ANTHROPIC_API_KEY in the environment or lending/.env the call goes through the anthropic SDK and every call is
costed into data/llm_cost.jsonl; past LLM_BUDGET_USD ask() returns None (the desk then behaves as with the model down).
Without the key it is the local `claude -p` CLI (already signed in). The key is never logged or printed.
Schema = {key: type}; type is "str" | "int" | "bool" | "list" | "dict" | "null", a nested schema dict
(an object with those keys), or a list of these (any one matches). Every schema key is required;
extra keys are ignored. The CLI runs in the system temp dir so no repo instructions reach the prompt.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_PATH = HERE / "data" / "llm.jsonl"
MODEL = "claude-sonnet-5-5"
RAW_MAX = 2000  # characters of the raw result kept in the log
COST_PATH = HERE / "data" / "llm_cost.jsonl"
LLM_BUDGET_USD = 80.0  # in code, not .env; a shell LLM_BUDGET_USD overrides it
PRICES = {"claude-sonnet-5-5": (2.00, 10.00, 0.20)}  # USD per million tokens: input, output, cache read
MAX_TOKENS = 1024
_BUDGET_LOCK = threading.Lock()  # budget check + call + cost append as one step, so concurrent asks cannot overspend

_TYPES = {"str": str, "int": int, "bool": bool, "list": list, "dict": dict}
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S)


def matches(value, spec) -> bool:
    """Keys and types only: True if value fits spec."""
    if isinstance(spec, list):
        return any(matches(value, s) for s in spec)
    if isinstance(spec, dict):
        return isinstance(value, dict) and all(k in value and matches(value[k], s) for k, s in spec.items())
    if spec == "null":
        return value is None
    if spec == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    t = _TYPES.get(spec)
    return t is not None and isinstance(value, t)


def parse_result(text: str):
    """The model's reply as JSON; tolerates one fenced ```json block. Raises ValueError."""
    s = text.strip()
    m = _FENCE.match(s)
    return json.loads(m.group(1) if m else s)


def _log(entry: dict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def _api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        for line in (HERE / ".env").read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip() or None
    except OSError:
        pass
    return None


def budget_usd() -> float:
    try:
        return float(os.environ.get("LLM_BUDGET_USD") or LLM_BUDGET_USD)
    except ValueError:
        return LLM_BUDGET_USD


def cost_summary() -> dict:
    """GET /v1/llm/cost: the sum of data/llm_cost.jsonl."""
    spent, calls, last = 0.0, 0, None
    try:
        for line in COST_PATH.read_text().splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            spent += float(row.get("cost_usd") or 0)
            calls += 1
            last = row.get("ts", last)
    except OSError:
        pass
    return {"spent_usd": round(spent, 6), "budget_usd": budget_usd(), "calls": calls, "last_ts": last}


def _cost(model: str, usage) -> float:
    pin, pout, pcache = PRICES.get(model, PRICES[MODEL])
    cache = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (usage.input_tokens * pin + usage.output_tokens * pout + cache * pcache) / 1_000_000


def _api_call(key: str, system: str, user: str, timeout_s: int, request_id: str | None) -> str:
    import anthropic  # only on the API path

    client = anthropic.Anthropic(api_key=key, timeout=timeout_s, max_retries=0)
    resp = client.messages.create(model=MODEL, max_tokens=MAX_TOKENS, system=system,
                                  messages=[{"role": "user", "content": user}])
    u = resp.usage
    row = {"ts": int(time.time()), "model": MODEL, "request_id": request_id or getattr(resp, "id", None),
           "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
           "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0, "cost_usd": round(_cost(MODEL, u), 6)}
    try:
        COST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(COST_PATH, "a") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        pass
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def _cli_call(prompt: str, timeout_s: int) -> str:
    exe = shutil.which("claude")
    if not exe:
        raise FileNotFoundError("claude CLI not found")
    p = subprocess.run([exe, "-p", prompt, "--output-format", "json", "--model", MODEL, "--tools", ""],
                       capture_output=True, text=True, timeout=timeout_s, cwd=tempfile.gettempdir())
    if p.returncode != 0:
        raise RuntimeError(f"exit {p.returncode}")
    env = json.loads(p.stdout)
    raw = env.get("result") if isinstance(env, dict) else None
    if not isinstance(env, dict) or env.get("is_error") or not isinstance(raw, str):
        raise ValueError("cli error envelope")
    return raw


def ask(system: str, user: str, schema: dict, timeout_s: int = 40, request_id: str | None = None) -> dict | None:
    contract = (f"Reply with ONLY one JSON object (no prose, no code fence) with these keys "
                f"and types: {json.dumps(schema)}. A list of types means any one of them.")
    prompt = f"{system}\n\n{user}\n\n{contract}"
    t0 = time.time()
    raw, err, out = None, None, None
    key = _api_key()
    try:
        if key:
            with _BUDGET_LOCK:
                if cost_summary()["spent_usd"] >= budget_usd():
                    raise RuntimeError("budget_exhausted")
                raw = _api_call(key, system, f"{user}\n\n{contract}", timeout_s, request_id)
        else:
            raw = _cli_call(prompt, timeout_s)
        val = parse_result(raw)
        if not isinstance(val, dict) or not matches(val, schema):
            raise ValueError("schema mismatch")
        out = val
    except subprocess.TimeoutExpired:
        err = f"timeout after {timeout_s}s"
    except Exception as e:  # noqa: BLE001 - ask never raises into a caller
        err = f"{type(e).__name__}: {e}"[:300]
    _log({"ts": int(time.time()), "requestId": request_id, "path": "api" if key else "cli", "ok": out is not None, "ms": int((time.time() - t0) * 1000),
          "raw_result": raw[:RAW_MAX] if isinstance(raw, str) else None, "error": err})
    return out
