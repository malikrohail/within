"""Agent 1, the goal-driven borrower. Think (model) -> check (code) -> submit -> react, max 4 turns.

The one rule: the model only proposes. It picks an invoice ID; code takes the supplier address and amount from the
invoice list, checks every number against GET /v1/policy, and signs with the borrower key from lending/.env through
borrower.py. The desk alone decides. If the model call fails, the agent says so and stops: no ask, no money.

    .venv/bin/python borrower_agent.py [--goal "..."] [--invoices data/invoices.json]
The default goal is the stage draw: 30 XRP (the 29 XRP GPU-COMPUTE-HOURS-1 invoice + a 1 XRP broker fee), which fits
the stock vault's ~38 XRP headroom; 60 XRP does not.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

import borrower
import common
import evidence
import llm

AGENT = "borrower-agent"
HERE = Path(__file__).resolve().parent
INVOICES_PATH = HERE / "data" / "invoices.json"
NOTE_MAX = 500
WAIT_SECONDS = 30          # model said "wait" with no ask: sleep this long, then think again
MODEL_TIMEOUT_S = 60
STAGE_DRAW_XRP = 30
DEFAULT_GOAL = (f"Pre-buy GPU-COMPUTE-HOURS-1 (29 XRP) with a {STAGE_DRAW_XRP} XRP working-capital draw "
                "(invoice + 1 XRP fee) before tonight's batch job")
XRP = 1_000_000
DROPS = re.compile(r"^[1-9]\d*$")
ADDRESS = re.compile(r"^r[1-9A-HJ-NP-Za-km-z]{24,34}$")
PURPOSES = ("inventory", "payroll", "equipment", "receivables")  # policy.PURPOSES: the declared purposes the score knows

SCHEMA = {"say": "str",
          "ask": [{"invoice": ["str", "null"], "principalDrops": "str", "termSeconds": "int", "purpose": "str",
                   "feeDrops": ["str", "null"]}, "null"],
          "wait": "bool"}

SYSTEM = f"""You are {AGENT}, a service agent that sells API calls over x402 and pays for its compute through a Policy
Wallet. Before a big job you borrow XRP working capital from a lending desk on the XRP Ledger devnet to pre-buy
compute, and you repay from the x402 receipts the job earns. You get a goal, your unpaid compute invoices, the desk's
policy, the vault's state and your past requests. Each turn you decide one thing: ask the desk for a loan, wait, or
stop.

How the desk works:
- All amounts are XRP drops as integer strings (1 XRP = 1000000 drops).
- A working-capital draw pays one of your invoices in the same step: the desk co-signs your loan, then one
  all-or-nothing batch pays the compute provider (the invoice's supplier) the invoice amount and pays the broker an arrangement fee. To make one, set
  "invoice" to the invoice ID from your list, and "feeDrops" to the fee (at least 1 drop; the desk's usual fee is
  1 XRP = "1000000"). principalDrops must cover the invoice amount plus the fee. You never give an address: the
  supplier comes from the invoice list.
- A plain loan (no invoice) sets "invoice" and "feeDrops" to null.
- termSeconds must be within the policy's termSecondsMin..termSecondsMax. One payment falls due every 90 seconds;
  270 means three payments.
- purpose must be one of: {", ".join(PURPOSES)}. Pre-buying compute for a job is "inventory".
- The desk approves on its own up to maxAutoPrincipalDrops with a high score. Above that, up to maxPrincipalDrops,
  a human must approve. It refuses if the score is too low, the vault would be lent out past maxUtilizationPct, or
  the broker's cover would fall under minCoverRatioPct of debt. "headroom" in the vault data says how much more the
  vault can lend under each limit right now.
- Ask for what the goal needs, not more. If a turn was refused or dropped, read why and change the ask, wait, or stop.

Fields: "say" is one or two plain sentences to the human running the desk, in the first person, saying what you
are doing and why. "ask" is your loan request, or null. "wait" is true only when "ask" is null and you want to try
again in {WAIT_SECONDS} seconds."""


# ---- reason code -> plain sentence (mirrors ui/src/copy.ts reasonSentence) ----------
def _x(drops) -> str:
    v = int(drops) / XRP
    return f"{v:g}" if v == int(v) else f"{v:.2f}"


def plain_sentence(rec: dict, policy: dict) -> str:
    amt, score, code = _x(rec.get("principalDrops") or 0), rec.get("score"), rec.get("reason") or ""
    b = rec.get("batch") or {}
    ev = rec.get("evidence") or {}
    words = {
        "over_auto_limit": lambda: f"Held for you. {amt} XRP is more than the {_x(policy['maxAutoPrincipalDrops'])} XRP "
                                   "the desk approves on its own. The score itself looks fine.",
        "score_below_auto": lambda: f"Held for you. The score is {score}, under the {policy['minScoreAuto']} the desk "
                                    "needs to approve on its own.",
        "score_too_low": lambda: f"Refused. The score is {score}; the desk lends from {policy['minScore']}. "
                                 "No transaction was made.",
        "over_max_principal": lambda: f"Refused. {amt} XRP is above the {_x(policy['maxPrincipalDrops'])} XRP cap. "
                                      "No transaction was made.",
        "vault_utilization": lambda: "Refused. This loan would have put more of the vault out on loan than the "
                                     f"{policy['maxUtilizationPct']}% limit. No transaction was made.",
        "cover_below_minimum": lambda: f"Refused. The broker's cover would fall under {policy['minCoverRatioPct']}% "
                                       "of debt. No transaction was made.",
        "declared_debt_understated": lambda: (
            f"Refused. They declared {_x(ev.get('declared', {}).get('existingDebtDrops') or 0)} XRP of existing debt "
            f"but the ledger shows {_x(ev.get('ledger', {}).get('loanPrincipalDrops') or 0)} XRP outstanding. "
            "No transaction was made."),
        "batch_unfunded": lambda: f"Refused. The supplier and fee legs "
                                  f"({_x(int(b.get('supplierDrops', 0)) + int(b.get('feeDrops', 0)))} XRP) are more "
                                  f"than the loan ({amt} XRP). No transaction was made.",
        "no_broker_credential": lambda: "Held for you. The borrower has no KYB credential from this broker yet.",
        "hold_timeout": lambda: "Request expired. Nobody approved in time, no transaction made.",
    }
    if code in words:
        return words[code]()
    if rec.get("status") == "denied":
        return "You denied this request. No transaction was made."
    if code == "timeout_waiting":
        return "Timed out waiting for validation. The desk stopped waiting before devnet reached the last valid ledger."
    if code == "batch:timeout_waiting":
        return "Loan made, timed out waiting for the batch to validate."
    if code in ("txnNotFound", "not_validated"):
        return "Expired before validation. Devnet passed the transaction's last valid ledger without including it."
    if code.startswith("batch:") and code[6:] in ("txnNotFound", "not_validated"):
        return "Loan made, batch expired before validation. No supplier leg moved."
    if code.startswith("batch:"):
        return f"Loan made, batch failed. The ledger refused the supplier batch: {code[6:]}."
    if code.startswith("ledger_unavailable"):
        return "Not submitted. The desk could not reach the ledger."
    return f"The ledger refused it: {code}." if code else ""


# ---- check (code, never the model) -------------------------------------------------
def check(ask: dict, policy: dict, invoices: list[dict]) -> tuple[str | None, dict | None]:
    """(reason, None) if the ask is outside policy or the invoice list, else (None, plan) built from code-owned data."""
    p = ask["principalDrops"]
    if not DROPS.match(p):
        return f"principalDrops {p!r} is not a positive integer string of drops", None
    if int(p) > int(policy["maxPrincipalDrops"]):
        return f"principalDrops {p} is over the policy cap maxPrincipalDrops {policy['maxPrincipalDrops']}", None
    t = ask["termSeconds"]
    if not policy["termSecondsMin"] <= t <= policy["termSecondsMax"]:
        return f"termSeconds {t} is outside {policy['termSecondsMin']}..{policy['termSecondsMax']}", None
    if ask["purpose"] not in PURPOSES:
        return f"purpose {ask['purpose']!r} is not one of {', '.join(PURPOSES)}", None
    plan = {"principalDrops": p, "termSeconds": t, "purpose": ask["purpose"], "disbursement": None}
    if ask["invoice"] is None:
        return None, plan
    inv = next((i for i in invoices if i["invoice"] == ask["invoice"]), None)
    if inv is None:
        return f"invoice {ask['invoice']!r} is not in my invoice list ({', '.join(i['invoice'] for i in invoices)})", None
    fee = ask["feeDrops"]
    if not isinstance(fee, str) or not DROPS.match(fee):
        return f"feeDrops {fee!r} must be a positive integer string of drops for a working-capital draw", None
    if int(inv["drops"]) + int(fee) > int(p):
        return (f"invoice {inv['invoice']} ({inv['drops']} drops) plus fee {fee} drops is more than "
                f"principalDrops {p}"), None
    plan["disbursement"] = {"supplier": inv["supplier"], "supplierDrops": inv["drops"], "feeDrops": fee,
                            "invoice": inv["invoice"]}
    return None, plan


def load_invoices(path: Path) -> list[dict]:
    items = json.loads(Path(path).read_text())
    for i in items:
        if not (isinstance(i.get("invoice"), str) and 0 < len(i["invoice"]) <= 64 and ADDRESS.match(i.get("supplier", ""))
                and DROPS.match(str(i.get("drops", "")))):
            raise ValueError(f"bad invoice entry: {i.get('invoice')!r}")
        i["drops"] = str(i["drops"])
    return items


# ---- the desk, over HTTP, signing with the borrower key -----------------------------
class HttpDesk:
    def __init__(self, url: str = borrower.DESK_URL, wallet=None):
        self.url = url
        self.w = wallet or common.wallet("borrower")
        self.address = self.w.address

    def policy(self) -> dict:
        return borrower.desk_get("/v1/policy", self.url)

    def vault(self) -> dict:
        return borrower.desk_get("/v1/vault", self.url)

    def history(self) -> list[dict]:
        return [r for r in borrower.desk_get("/v1/loan-requests", self.url)["requests"] if r["borrower"] == self.address]

    def declared_debt(self) -> str:
        """Existing debt to declare: this borrower's outstanding on-ledger loan principal, read by code with the same
        evidence function the desk scores with (never from the model), so the desk's declared_debt_understated check
        never refuses the agent over its own loans."""
        return evidence.ledger_evidence(self.address, common.client(), int(time.time()), 30)["loanPrincipalDrops"]

    def submit(self, plan: dict) -> tuple[int, dict]:
        policy, accounts = self.policy(), common.load_accounts()
        args = (self.w, plan["principalDrops"], plan["termSeconds"], plan["purpose"], self.declared_debt())
        if plan["disbursement"]:
            body, _ = borrower.build_working_capital_body(*args, plan["disbursement"], accounts, policy)
        else:
            body = borrower.build_request_body(*args, accounts, policy)
        return borrower.post_request(body, self.url)

    def note(self, rid: str, text: str) -> bool:
        try:
            r = requests.post(f"{self.url}/v1/loan-requests/{rid}/notes",
                              json={"from": AGENT, "text": text[:NOTE_MAX]}, timeout=30)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def wait(self, rid: str, timeout: int) -> dict:
        return borrower.wait_for(rid, timeout=timeout, desk_url=self.url)


# ---- the loop ----------------------------------------------------------------------
def vault_view(v: dict, policy: dict) -> dict:
    assets, out = int(v["assetsTotalDrops"]), int(v["loansOutstandingDrops"])
    debt, cover = int(v["debtTotalDrops"]), int(v["coverDrops"])
    util_room = max(0, assets * policy["maxUtilizationPct"] // 100 - out)
    cover_room = max(0, cover * 100 // policy["minCoverRatioPct"] - debt) if policy["minCoverRatioPct"] else None
    return {"phase": v.get("phase"), "assetsTotalDrops": v["assetsTotalDrops"],
            "assetsAvailableDrops": v["assetsAvailableDrops"], "loansOutstandingDrops": v["loansOutstandingDrops"],
            "debtTotalDrops": v["debtTotalDrops"], "coverDrops": v["coverDrops"],
            "utilizationPct": v.get("utilizationPct"), "coverRatioPct": v.get("coverRatioPct"),
            "headroom": {"underUtilizationLimitDrops": str(util_room),
                         "underCoverMinimumDrops": None if cover_room is None else str(cover_room)}}


def history_view(recs: list[dict]) -> list[dict]:
    keep = ("id", "kind", "status", "reason", "principalDrops", "score", "ts")
    return [{k: r.get(k) for k in keep} for r in recs[:5]]


def outcome_line(rec: dict) -> str:
    who = "a human approved it" if rec.get("decidedBy") == "human" else "the desk approved it on its own"
    b = rec.get("batch")
    if rec.get("kind") == "working_capital" and b:
        legs = ", ".join(f"{l.get('result')}" for l in b.get("legs", [])) or "unknown"
        return (f"{rec['id']} is done: {who}. LoanSet {rec.get('txHash')} ({rec.get('engineResult')}), then one "
                f"all-or-nothing Batch {b.get('hash')} ({b.get('engineResult')}) paid the supplier "
                f"{_x(b['supplierDrops'])} XRP for {b['invoice']} and the broker a {_x(b['feeDrops'])} XRP fee "
                f"(legs: {legs}).")
    return f"{rec['id']} is done: {who}. LoanSet {rec.get('txHash')} ({rec.get('engineResult')}), loan {rec.get('loanId')}."


def run(goal: str, invoices: list[dict], desk, ask_fn=llm.ask, max_turns: int = 4, out=print, sleep=time.sleep,
        run_id: str | None = None) -> dict:
    """Returns {"outcome", "requestIds", "lines", "record"}. Never moves money without a model ask that passed check()."""
    run_id = run_id or f"agent-{int(time.time())}"
    lines, pending, ids, feedback = [], [], [], []
    state = {"rid": None}

    def say(text: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {AGENT}: {text}"
        out(line)
        lines.append(line)
        pending.append(text)
        if state["rid"]:
            flush()

    def flush() -> None:
        while pending:
            desk.note(state["rid"], pending.pop(0))

    def done(outcome: str, rec: dict | None = None) -> dict:
        return {"outcome": outcome, "requestIds": ids, "lines": lines, "record": rec}

    try:
        for turn in range(1, max_turns + 1):
            policy = desk.policy()
            ctx = {"goal": goal, "turn": turn, "maxTurns": max_turns,
                   "invoices": [{"invoice": i["invoice"], "drops": i["drops"], "xrp": _x(i["drops"]), "due": i.get("due")}
                                for i in invoices],
                   "policy": policy, "vault": vault_view(desk.vault(), policy), "myRequests": history_view(desk.history()),
                   "earlierTurnsThisRun": feedback}
            r = ask_fn(SYSTEM, json.dumps(ctx, indent=1), SCHEMA, timeout_s=MODEL_TIMEOUT_S, request_id=f"{run_id}-t{turn}")
            if r is None:
                say("I could not get an answer from my model, so I am stopping here. I sent no request this turn.")
                return done("model_unavailable")
            say(r["say"])
            if r["ask"] is None:
                if r["wait"] and turn < max_turns:
                    feedback.append({"turn": turn, "ask": None, "outcome": f"waited {WAIT_SECONDS} s"})
                    sleep(WAIT_SECONDS)
                    continue
                return done("stopped_by_model")
            why, plan = check(r["ask"], policy, invoices)
            if why:
                say(f"My own check dropped that ask before sending it: {why}.")
                feedback.append({"turn": turn, "ask": r["ask"], "outcome": f"dropped by the agent's code check: {why}"})
                continue
            status, rec = desk.submit(plan)
            if status != 200:
                detail = rec.get("detail") if isinstance(rec, dict) else rec
                say(f"The desk did not take the request ({status}: {detail}).")
                feedback.append({"turn": turn, "ask": r["ask"], "outcome": f"desk HTTP {status}: {detail}"})
                continue
            rid = rec["id"]
            ids.append(rid)
            state["rid"] = rid
            flush()
            st = rec["status"]
            if st == "auto":
                say(outcome_line(rec))
                return done("auto", rec)
            if st == "held":
                say(f"{rid} is held ({rec['reason']}): {plain_sentence(rec, policy)} I am waiting for a human to "
                    "approve or deny it.")
                final = desk.wait(rid, timeout=int(policy["holdTimeoutSeconds"]) + 60)
                fs = final["status"]
                if fs == "approved":
                    say(outcome_line(final))
                elif fs == "failed":
                    say(f"{rid} was approved but did not complete: {plain_sentence(final, policy)} "
                        f"LoanSet {final.get('txHash')}.")
                elif fs == "held":
                    say(f"{rid} is still waiting after {int(policy['holdTimeoutSeconds']) + 60} s; I stop watching it.")
                else:
                    say(f"{rid} ended {fs}: {plain_sentence(final, policy)} I will not ask again in this run.")
                return done(f"held_{fs}", final)
            if st == "refused":
                words = plain_sentence(rec, policy)
                say(f"{rid} was refused ({rec['reason']}): {words}")
                feedback.append({"turn": turn, "ask": r["ask"], "outcome": f"refused {rec['reason']}: {words}",
                                 "requestId": rid})
                continue
            say(f"{rid} ended {st}: {plain_sentence(rec, policy)}")
            return done(st, rec)
        say(f"I used my {max_turns} turns without reaching the goal, so I am stopping.")
        return done("out_of_turns")
    except (requests.RequestException, RuntimeError, KeyError, ValueError) as e:
        say(f"I lost contact with the desk or the ledger ({type(e).__name__}), so I am stopping.")
        return done("error")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--goal", default=DEFAULT_GOAL)
    ap.add_argument("--invoices", default=str(INVOICES_PATH))
    ap.add_argument("--desk", default=borrower.DESK_URL)
    ap.add_argument("--max-turns", type=int, default=4)
    a = ap.parse_args()
    desk = HttpDesk(a.desk)
    print(f"[{time.strftime('%H:%M:%S')}] {AGENT} for {desk.address} against {a.desk}, goal: {a.goal}")
    res = run(a.goal, load_invoices(Path(a.invoices)), desk, max_turns=max(1, min(a.max_turns, 4)))
    print(json.dumps({k: res[k] for k in ("outcome", "requestIds")}))
    return 1 if res["outcome"] == "error" else 0  # a model failure or a no leaves flows as they were


if __name__ == "__main__":
    sys.exit(main())
