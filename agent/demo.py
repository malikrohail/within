"""Demo agent. Buys from the x402 merchants through the policy wallet; it never holds a signing key.

  python demo.py --scripted [--wallet http://localhost:7402]
  python demo.py --llm      (needs ANTHROPIC_API_KEY)
  python demo.py --revoke-drill [--tap-after N]   (delegated payment, revoke, refused payment, re-grant)
"""
import argparse
import json
import secrets
import sys
import threading
import time

import requests
from x402_xrpl.clients import decode_payment_response

from merchants.common import RPC_URL, load_merchants
from remote_signer import (DEFAULT_WALLET_URL, PolicyRefused, WalletError, _read_timeout, make_session,
                           make_wallet_header_factory, operator_headers, paid_get)

# step, merchant, path, purpose, expected decision
SCRIPT = [
    (1, "good", "/lookup", "lookup comps for 123 Main St", "auto"),
    (2, "good", "/infer", "classify kitchen photo", "auto"),
    (3, "good", "/lookup", "lookup comps for 125 Main St", "auto"),
    (4, "good", "/dataset", "buy full MLS dataset", "approved"),
    (5, "rogue", "/lookup", "lookup from unverified vendor", "refused"),
]
REFUSAL_DECISIONS = {403: "refused", 408: "expired", 503: "refused"}
RUN_SPEND_DROPS = 1000 + 50000 + 1000 + 5000000  # steps 1-4 count toward the wallet's spent-today
EXPLORER = "https://testnet.xrpl.org/transactions/"


class Buyer:
    """One x402 session whose payments are all signed by the wallet at wallet_url."""

    def __init__(self, wallet_url, rpc_url=RPC_URL):
        self.purpose = "agent purchase"
        self.factory = make_wallet_header_factory(wallet_url, purpose_getter=lambda: self.purpose)
        self.session = make_session(self.factory, rpc_url)
        self.merchants = load_merchants()

    def buy(self, merchant, path, purpose):
        """Returns {decision, reason, tx, status, settled, body}; never raises for a wallet refusal."""
        self.purpose = purpose
        url = f"http://localhost:{self.merchants[merchant]['port']}{path}"
        try:
            resp = paid_get(self.session, self.factory, url, timeout=180)
        except PolicyRefused as exc:
            return {"decision": REFUSAL_DECISIONS.get(exc.status, "refused"), "reason": exc.reason,
                    "requestId": exc.request_id}
        except WalletError as exc:
            return {"decision": "error", "reason": str(exc)}
        except requests.RequestException as exc:
            return {"decision": "error", "reason": f"merchant unreachable: {exc}"}
        wallet = self.factory.last_result or {}
        settlement = decode_payment_response(resp.headers["PAYMENT-RESPONSE"]) if "PAYMENT-RESPONSE" in resp.headers else {}
        try:
            body = resp.json()
        except ValueError:
            body = resp.text[:200]
        settled = resp.status_code == 200 and settlement.get("success") is True
        reason = None
        if not settled:
            reason = settlement.get("errorReason") or (body.get("error") if isinstance(body, dict) else None) or "not_settled"
        return {"decision": wallet.get("decision", "none"), "requestId": wallet.get("requestId"),
                # Only a settled payment has an explorer page; otherwise show the unsubmitted blob's hash as signed=.
                "tx": settlement.get("transaction") if settled else None,
                "signed": None if settled else wallet.get("txHash"),
                "status": resp.status_code, "settled": settled, "reason": reason, "body": body}


def step_ok(result, expected):
    if expected == "refused":
        return result["decision"] == "refused" and result["reason"] == "merchant_not_credentialed"
    return result["decision"] == expected and result.get("status") == 200 and result.get("settled")


def step_line(step, path, result):
    line = f"step={step} path={path} decision={result['decision']}"
    if result.get("tx"):
        line += f" tx={result['tx']} explorer={EXPLORER}{result['tx']}"
    if result.get("signed"):
        line += f" signed={result['signed']}"
    if result.get("status") is not None:
        line += f" status={result['status']}"
    if result.get("reason"):
        line += f" reason={result['reason']}"
    return line


def warn_if_budget_short(wallet_url):
    """The real wallet refuses step 4 once today's spend leaves less than one run of budget."""
    try:
        spent = int(requests.get(f"{wallet_url}/v1/status", timeout=5).json()["spentTodayDrops"])
        budget = int(requests.get(f"{wallet_url}/v1/policy", timeout=5).json()["dailyBudgetDrops"])
    except Exception:
        return
    if spent + RUN_SPEND_DROPS > budget:
        print(f"warning: spent today {spent} + this run {RUN_SPEND_DROPS} > daily budget {budget} drops; "
              "step 4 will be refused with daily_budget_exceeded", file=sys.stderr, flush=True)


def run_scripted(wallet_url):
    warn_if_budget_short(wallet_url)
    buyer = Buyer(wallet_url)
    matched = 0
    for step, merchant, path, purpose, expected in SCRIPT:
        if expected == "approved":
            print(f"step={step} path={path} waiting for approval on the device...", file=sys.stderr, flush=True)
        result = buyer.buy(merchant, path, purpose)
        line = step_line(step, path, result)
        if step_ok(result, expected):
            matched += 1
        else:
            line += f" MISMATCH expected={expected}"
        print(line, flush=True)
    print(f"done: {matched}/{len(SCRIPT)} steps matched", flush=True)
    return 0 if matched == len(SCRIPT) else 1


LLM_MODEL = "claude-sonnet-5-5"
LLM_MAX_TURNS = 10
LLM_SYSTEM = (
    "You are a real-estate research agent. You pay for data with an x402 wallet you do not control: "
    "every purchase goes to a policy wallet that decides in code whether to sign it, hold it for a "
    "human to approve on a hardware device, or refuse it. You cannot change that decision. "
    "If a tool reports a refusal, accept it, do not retry that vendor, and continue with the rest."
)
LLM_TASK = (
    "Prepare a pricing brief for 123 Main St. Use each of your four tools exactly once, in this order: "
    "lookup (comps for 123 Main St), infer (classify the kitchen photo), dataset (the full MLS dataset), "
    "rogue_lookup (a second opinion on comps from the unverified vendor). Then write a three-line brief "
    "that says which purchases went through and which were refused."
)
# tool name -> (merchant, path, description)
LLM_TOOLS = {
    "lookup": ("good", "/lookup", "Buy a comparable-sales lookup for an address (0.001 XRP)."),
    "infer": ("good", "/infer", "Buy a photo classification of the listing's kitchen photo (0.05 XRP)."),
    "dataset": ("good", "/dataset", "Buy the full MLS dataset export (5 XRP)."),
    "rogue_lookup": ("rogue", "/lookup", "Buy a comparable-sales lookup from an unverified vendor (0.001 XRP)."),
}


def llm_tool_specs():
    return [{
        "name": name,
        "description": description + " Payment is made by the policy wallet.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"purpose": {"type": "string", "description": "One short line saying why you are buying this; shown to the human approver."}},
            "required": ["purpose"],
            "additionalProperties": False,
        },
    } for name, (_, _, description) in LLM_TOOLS.items()]


def run_tool(buyer, name, tool_input):
    merchant, path, _ = LLM_TOOLS[name]
    result = buyer.buy(merchant, path, tool_input.get("purpose") or name)
    print(f"tool={name} path={path} decision={result['decision']}"
          + (f" tx={result['tx']}" if result.get("tx") else "")
          + (f" reason={result['reason']}" if result.get("reason") else ""), flush=True)
    return {k: result.get(k) for k in ("decision", "reason", "tx", "body") if result.get(k) is not None}


def run_llm(buyer, client=None):
    import json
    import os

    import anthropic

    if client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("--llm needs ANTHROPIC_API_KEY", file=sys.stderr)
            return 2
        client = anthropic.Anthropic()
    messages = [{"role": "user", "content": LLM_TASK}]
    called = set()
    for _ in range(LLM_MAX_TURNS):
        response = client.beta.messages.create(
            model=LLM_MODEL, max_tokens=16000, system=LLM_SYSTEM, tools=llm_tool_specs(), messages=messages,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        if response.stop_reason == "refusal":
            print("model refused the task", flush=True)
            return 1
        messages.append({"role": "assistant", "content": response.content})
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason != "tool_use" or not tool_uses:
            text = "\n".join(b.text for b in response.content if b.type == "text")
            print(text.strip(), flush=True)
            return 0 if called == set(LLM_TOOLS) else 1
        results = []
        for block in tool_uses:
            if block.name in LLM_TOOLS:
                called.add(block.name)
                content, is_error = json.dumps(run_tool(buyer, block.name, block.input)), False
            else:
                content, is_error = f"unknown tool {block.name}", True
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": results})
    print(f"stopped after {LLM_MAX_TURNS} turns", flush=True)
    return 1


DRILL_POLL_SECONDS = 0.5
DRILL_ROW_WAIT_SECONDS = 30


def _json(resp):
    try:
        body = resp.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def drill_state(wallet_url, step):
    """GET /v1/delegate and print it. Returns the permissions list, or None if the wallet did not answer 200."""
    resp = requests.get(f"{wallet_url}/v1/delegate", timeout=10)
    body = _json(resp)
    permissions = body.get("permissions") if resp.status_code == 200 else None
    print(f"drill step={step} delegate status={resp.status_code} treasury={body.get('treasury')} agent={body.get('agent')} "
          f"permissions={json.dumps(permissions)} objects={json.dumps(body.get('objects'))}"
          + (f" reason={body.get('reason')}" if resp.status_code != 200 else ""), flush=True)
    return permissions


def drill_pay(wallet_url, timeout, pay_to, n):
    """Direct delegated payment from the treasury. maxTimeoutSeconds 10 -> LastLedgerSequence = validated + 4."""
    requirements = {"scheme": "exact", "network": "xrpl:1", "asset": "XRP", "amount": "1000", "payTo": pay_to,
                    "maxTimeoutSeconds": 10, "extra": {"invoiceId": f"drill-{n}-{secrets.token_hex(4)}"}}
    resp = requests.post(f"{wallet_url}/v1/pay", timeout=timeout, json={
        "requirements": requirements, "purpose": "revoke drill: delegated payment", "source": "treasury"})
    return resp.status_code, _json(resp)


def drill_delegate(wallet_url, timeout, action, tap_after):
    """POST /v1/delegate (blocks until the device signs) and tap its held row, standing in for the dashboard Approve."""
    rows_url = f"{wallet_url}/v1/requests"
    before = {row.get("id") for row in requests.get(rows_url, params={"limit": 20}, timeout=10).json()}
    result = {}

    def call():
        try:
            resp = requests.post(f"{wallet_url}/v1/delegate", json={"action": action}, headers=operator_headers(), timeout=timeout)
            result.update(status=resp.status_code, body=_json(resp))
        except requests.RequestException as exc:
            result.update(status=None, body={"reason": f"wallet unreachable: {exc}"})

    thread = threading.Thread(target=call, daemon=True)
    thread.start()
    row, deadline = None, time.monotonic() + DRILL_ROW_WAIT_SECONDS
    while row is None and thread.is_alive() and time.monotonic() < deadline:
        rows = requests.get(rows_url, params={"limit": 20}, timeout=10).json()
        row = next((r for r in rows if r.get("kind") == "delegate" and r.get("status") == "held"
                    and r.get("resourceUrl") == f"delegate://{action}" and r.get("id") not in before), None)
        if row is None:
            time.sleep(DRILL_POLL_SECONDS)
    if row is not None:
        print(f"drill {action} held requestId={row['id']}: approve on the dashboard or the drill taps in {tap_after:g}s",
              file=sys.stderr, flush=True)
        thread.join(tap_after)
        if thread.is_alive():
            # 409 not_pending means the dashboard approved it first.
            tap = requests.post(f"{rows_url}/{row['id']}/device-tap", timeout=10)
            print(f"drill {action} device-tap requestId={row['id']} status={tap.status_code}", file=sys.stderr, flush=True)
    elif thread.is_alive():
        print(f"drill {action}: no held row within {DRILL_ROW_WAIT_SECONDS}s, waiting on the wallet", file=sys.stderr, flush=True)
    thread.join()
    return result["status"], result["body"]


def drill_line(step, what, status, body):
    tx = body.get("txHash")
    line = f"drill step={step} {what} status={status}"
    if body.get("decision"):
        line += f" decision={body['decision']}"
    line += f" engine_result={body.get('engineResult')} tx={tx}"
    if tx:
        line += f" explorer={EXPLORER}{tx}"
    if "permissions" in body:
        line += f" permissions={json.dumps(body['permissions'])}"
    if body.get("reason"):
        line += f" reason={body['reason']}"
    return line


def drill_delegate_ok(wallet_url, timeout, action, tap_after, step):
    status, body = drill_delegate(wallet_url, timeout, action, tap_after)
    ok = status == 200 and body.get("engineResult") == "tesSUCCESS"
    print(drill_line(step, action, status, body) + ("" if ok else " MISMATCH expected=tesSUCCESS"), flush=True)
    return ok


def run_revoke_drill(wallet_url, tap_after=0):
    """Delegated payment while granted, revoke, the same payment refused by the ledger, re-grant. 0 only if all hold."""
    wallet_url = wallet_url.rstrip("/")
    timeout = (5, _read_timeout(wallet_url))
    pay_to = load_merchants()["good"]["address"]
    try:
        # 1. Start granted.
        permissions = drill_state(wallet_url, 1)
        if permissions is None:
            print("drill done: FAILED could not read /v1/delegate", flush=True)
            return 1
        if "Payment" not in permissions:
            print("drill step=1 agent has no Payment permission; granting first", flush=True)
            if not drill_delegate_ok(wallet_url, timeout, "grant", tap_after, 1) or drill_state(wallet_url, 1) != ["Payment"]:
                print("drill done: FAILED initial grant", flush=True)
                return 1
        # 2. Delegated payment while granted.
        status, body = drill_pay(wallet_url, timeout, pay_to, 2)
        ok = status == 200 and body.get("decision") == "auto" and body.get("engineResult") == "tesSUCCESS"
        print(drill_line(2, "pay", status, body) + ("" if ok else " MISMATCH expected=auto/tesSUCCESS"), flush=True)
        if not ok:
            print("drill done: FAILED delegated payment while granted", flush=True)
            return 1
        # 3. Revoke on the device.
        if not drill_delegate_ok(wallet_url, timeout, "revoke", tap_after, 3):
            print("drill done: FAILED revoke", flush=True)
            return 1
        # 4. Same payment again: the ledger refuses it with a ter, so nothing is applied and there is no ledger entry.
        status, body = drill_pay(wallet_url, timeout, pay_to, 4)
        refused = (status == 403 and body.get("decision") == "refused"
                   and body.get("engineResult") == "terNO_DELEGATE_PERMISSION")
        print(drill_line(4, "pay", status, body)
              + (" (ter = not applied, no ledger entry)" if refused else " MISMATCH expected=refused/terNO_DELEGATE_PERMISSION"),
              flush=True)
        revoked = drill_state(wallet_url, 4) == []
        # 5. Re-grant even after a step-4 mismatch so the agent is never left revoked.
        regranted = drill_delegate_ok(wallet_url, timeout, "grant", tap_after, 5)
        restored = drill_state(wallet_url, 5) == ["Payment"]
    except requests.RequestException as exc:
        print(f"drill done: FAILED wallet unreachable at {wallet_url}: {exc}", flush=True)
        return 1
    failed = [name for name, passed in [("step4_refused", refused), ("step4_permissions_empty", revoked),
                                        ("regrant", regranted), ("regrant_permissions", restored)] if not passed]
    print("drill done: " + ("all checks passed" if not failed else "FAILED " + ",".join(failed)), flush=True)
    return 0 if not failed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--scripted", action="store_true", help="run the five fixed purchases")
    mode.add_argument("--llm", action="store_true", help="let Claude decide the purchases (needs ANTHROPIC_API_KEY)")
    mode.add_argument("--revoke-drill", action="store_true",
                      help="delegated treasury payment, revoke, refused payment, re-grant")
    parser.add_argument("--wallet", default=DEFAULT_WALLET_URL, help="policy wallet base URL")
    parser.add_argument("--tap-after", type=float, default=0,
                        help="revoke drill: seconds to wait for a dashboard Approve before the drill taps the device")
    args = parser.parse_args()
    if args.scripted:
        return run_scripted(args.wallet)
    if args.revoke_drill:
        return run_revoke_drill(args.wallet, args.tap_after)
    return run_llm(Buyer(args.wallet))


if __name__ == "__main__":
    sys.exit(main())
