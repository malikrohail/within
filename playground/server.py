"""Playground backend: borrower-side only, FastAPI on :7510.

Imports the lending helpers read-only (common, borrower, evidence, policy, sweeper) and talks to the desk only
through its public HTTP routes on :7500. It never holds the broker key; the operator token, when a step needs it,
is read server-side from lending/.env and never leaves this process. Seeds live in playground/data/pool.json
(gitignored) and are never put in a response or printed.

  .venv/bin/python server.py --fund 10   # claim 10 pool accounts + 3 customers from the devnet faucet
  .venv/bin/python server.py             # serve on :7510
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LENDING = ROOT / "lending"
sys.path.insert(0, str(LENDING))

import common  # noqa: E402
import borrower  # noqa: E402
import evidence  # noqa: E402
import policy  # noqa: E402
import sweeper  # noqa: E402
from dotenv import dotenv_values  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

XRP = 1_000_000
INCOME_DROPS = 5 * XRP          # every customer invoice is 5 XRP: equal amounts keep the top-payer share <= 40 %
MIN_ASK_DROPS, MAX_ASK_DROPS = 1 * XRP, 5 * XRP   # hard cap: visitors cannot drain the stage vault
TERM_SECONDS = 270
PURPOSE = "inventory"
CUSTOMERS = 3
CUSTOMER_FLOOR_DROPS = INCOME_DROPS + 3 * XRP
KYB_TYPE_HEX = evidence.KYB_CREDENTIAL_TYPE
FINAL = ("auto", "approved", "denied", "refused", "expired", "failed")
ACTIVE = ("auto", "approved")
DEFAULT_PORT = 7510
UI_ORIGINS = ["http://localhost:5176", "http://127.0.0.1:5176"]
# Offline ceiling for a fresh account (age ~0, activeDays 1, 10 x 5 XRP from 3 payers split 4/3/3).
CEILING = {"noCredential": 61, "withCredential": 75}


def desk_url() -> str:
    env = dotenv_values(HERE / ".env") if (HERE / ".env").exists() else {}
    return (os.environ.get("DESK_URL") or env.get("DESK_URL") or "http://127.0.0.1:7500").rstrip("/")


def desk_token() -> str | None:
    return os.environ.get("DESK_TOKEN") or dotenv_values(LENDING / ".env").get("DESK_TOKEN")


# ---- adapters (tests inject fakes) ------------------------------------------------------------------------------
class Chain:
    """Devnet over the lending helpers. Holds wallets only for the call."""

    def now(self) -> int:
        return int(time.time())

    def faucet_wallet(self, w=None):
        from xrpl.wallet import generate_faucet_wallet
        last = None
        for attempt in range(4):
            try:
                return generate_faucet_wallet(common.client(), wallet=w)
            except Exception as e:  # noqa: BLE001 - faucet throttling
                last = e
                time.sleep(3 + 3 * attempt)
        raise RuntimeError(f"faucet failed: {type(last).__name__}")

    def balance(self, address: str) -> int:
        from xrpl.models.requests import AccountInfo
        res = common._rpc(AccountInfo(account=address, ledger_index="validated"))
        return int(res["account_data"]["Balance"]) if "account_data" in res else 0

    def pay_income(self, w_customer, dest: str, drops: int, invoice: str, date: str) -> dict:
        from xrpl.models.transactions import Memo, Payment
        from xrpl.utils import str_to_hex
        memo = Memo(memo_type=str_to_hex("invoice"), memo_data=str_to_hex(json.dumps({"invoice": invoice, "date": date})))
        return common.submit_and_wait(Payment(account=w_customer.address, destination=dest, amount=str(drops),
                                              memos=[memo]), w_customer)

    def evidence(self, address: str, declared: dict) -> dict:
        return evidence.build_evidence(address, declared, client=common.client())

    def sign_loan_set(self, w, tx) -> str:
        return common.borrower_sign_loan_set(w, tx)

    def credential_accept(self, w, issuer: str) -> dict:
        from xrpl.models.transactions import CredentialAccept
        return common.submit_and_wait(CredentialAccept(account=w.address, issuer=issuer, credential_type=KYB_TYPE_HEX), w)

    def sweeper_ledger(self, w):
        return sweeper.XrplLedger(w)

    def wallet_from_seed(self, seed: str):
        from xrpl.wallet import Wallet
        return Wallet.from_seed(seed)


class Desk:
    """The desk's public routes. The token is attached only to the two operator calls, server-side."""

    def __init__(self, url: str, token: str | None):
        import requests
        self.url, self.token, self._r = url, token, requests
        self.sweep_desk = sweeper.HttpDesk(url)

    def _auth(self) -> dict:
        return {"X-Desk-Token": self.token} if self.token else {}

    def policy(self) -> dict:
        return borrower.desk_get("/v1/policy", self.url)

    def post_request(self, body: dict) -> tuple[int, dict]:
        return borrower.post_request(body, self.url)

    def get_request(self, rid: str) -> dict:
        return borrower.desk_get(f"/v1/loan-requests/{rid}", self.url)

    def request_credential(self, subject: str) -> tuple[int, dict]:
        r = self._r.post(f"{self.url}/v1/broker/credentials", json={"subject": subject}, headers=self._auth(), timeout=120)
        return r.status_code, _json(r)

    def manage_default(self, loan_id: str) -> tuple[int, dict]:
        r = self._r.post(f"{self.url}/v1/loans/{loan_id}/manage", json={"action": "default"}, headers=self._auth(),
                         timeout=borrower.POST_TIMEOUT_S)
        return r.status_code, _json(r)


def _json(r) -> dict:
    try:
        return r.json()
    except ValueError:
        return {"detail": r.text[:200]}


# ---- pool + sessions --------------------------------------------------------------------------------------------
class Store:
    """pool.json: {"pool": [{address, seed, claimedBy, used}], "customers": [{address, seed}]}; sessions.json: {id: session}.
    Seeds never leave this class except as a Wallet handed to the chain adapter."""

    def __init__(self, data_dir: Path, wallet_from_seed=None):
        self.wallet_from_seed = wallet_from_seed or Chain().wallet_from_seed
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.pool = self._load("pool.json", {"pool": [], "customers": []})
        self.sessions = self._load("sessions.json", {})

    def _load(self, name: str, default):
        try:
            return json.loads((self.dir / name).read_text())
        except (FileNotFoundError, ValueError):
            return default

    def _save(self, name: str, data) -> None:
        tmp = self.dir / (name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n")
        tmp.replace(self.dir / name)

    def save(self) -> None:
        with self.lock:
            self._save("pool.json", self.pool)
            self._save("sessions.json", self.sessions)

    def add_pool_account(self, w) -> None:
        self.pool["pool"].append({"address": w.address, "seed": w.seed, "claimedBy": None, "used": False})

    def add_customer(self, w) -> None:
        self.pool["customers"].append({"address": w.address, "seed": w.seed})

    def claim(self, session_id: str) -> int:
        """Index of the claimed pool account: never-used first (a released account carries its history)."""
        with self.lock:
            free = [i for i, a in enumerate(self.pool["pool"]) if a["claimedBy"] is None]
            free.sort(key=lambda i: self.pool["pool"][i]["used"])
            if not free:
                raise HTTPException(503, "pool_empty: run server.py --fund N")
            i = free[0]
            self.pool["pool"][i].update(claimedBy=session_id, used=True)
            return i

    def release(self, index: int) -> None:
        with self.lock:
            self.pool["pool"][index]["claimedBy"] = None

    def wallet(self, index: int):
        return self.wallet_from_seed(self.pool["pool"][index]["seed"])

    def customer_wallet(self, n: int):
        customers = self.pool["customers"]
        if len(customers) < CUSTOMERS:
            raise HTTPException(503, "no_customers: run server.py --fund N")
        return self.wallet_from_seed(customers[n % CUSTOMERS]["seed"])


# ---- app --------------------------------------------------------------------------------------------------------
class BorrowBody(BaseModel):
    amountXrp: float


def declared_for(session: dict) -> dict:
    ask = (session.get("loan") or {}).get("principalDrops") or str(2 * XRP)
    return {"purpose": PURPOSE, "principalDrops": ask, "termSeconds": TERM_SECONDS, "existingDebtDrops": "0"}


def public(session: dict) -> dict:
    """Response shape: never the pool index path to a seed, never a seed."""
    out = {k: v for k, v in session.items() if k != "poolIndex"}
    out["level"] = unlocked(session)
    return out


def unlocked(s: dict) -> int:
    loan = s.get("loan") or {}
    if loan.get("status") in ACTIVE and loan.get("loanId"):
        return 5
    if s.get("payments"):
        return 4   # level 3 (credential) is skippable, so 3 and 4 open together
    return 2


def make_app(data_dir: Path, chain=None, desk=None) -> FastAPI:
    app = FastAPI(title="playground")
    app.add_middleware(CORSMiddleware, allow_origins=UI_ORIGINS, allow_methods=["*"], allow_headers=["*"])
    chain = chain or Chain()
    store = Store(data_dir, chain.wallet_from_seed)
    desk = desk or Desk(desk_url(), desk_token())
    app.state.store, app.state.chain, app.state.desk = store, chain, desk
    real_policy = policy.load_policy()   # lending/policy.json, read-only

    def session(sid: str) -> dict:
        s = store.sessions.get(sid)
        if not s:
            raise HTTPException(404, "unknown_session")
        return s

    def rescore(s: dict) -> None:
        ev = chain.evidence(s["address"], declared_for(s))
        bd = policy.score_breakdown(ev)
        led = ev["ledger"]
        s["score"] = bd["total"]
        s["breakdown"] = bd
        s["ledger"] = {k: led.get(k) for k in ("inboundPaymentCount", "inboundVolumeDrops", "distinctPayers",
                                              "topPayerSharePct", "activeDays", "activeLoans", "pastDefaults",
                                              "hasAcceptedCredential", "accountAgeLedgers")}

    def sweep_paths(s: dict) -> tuple[Path, Path]:
        d = store.dir / s["id"]
        d.mkdir(parents=True, exist_ok=True)
        return d / "sweeper_state.json", d / "sweeps.jsonl"

    def run_sweep(s: dict) -> list[dict]:
        """One sweep_once with this session's key; the first call only pins the cursor."""
        state_path, sweeps_path = sweep_paths(s)
        state = sweeper.load_state(state_path)
        ledger = chain.sweeper_ledger(store.wallet(s["poolIndex"]))
        try:
            return sweeper.sweep_once(state, ledger, desk.sweep_desk, chain.now(), sweeps_path,
                                      persist=lambda: sweeper.save_state(state_path, state))
        finally:
            sweeper.save_state(state_path, state)

    def refresh_loan(s: dict) -> None:
        loan = s.get("loan")
        if not loan or loan.get("status") in FINAL or not loan.get("requestId"):
            return
        rec = desk.get_request(loan["requestId"])
        loan.update(status=rec["status"], reason=rec.get("reason"), loanId=rec.get("loanId"), txHash=rec.get("txHash"),
                    score=rec.get("score"), decidedBy=rec.get("decidedBy"), memo=rec.get("memo"),
                    engineResult=rec.get("engineResult"), deskTs=rec.get("ts"))
        if rec["status"] in ACTIVE and rec.get("loanId") and not loan.get("sweeperPinned"):
            run_sweep(s)   # pin the cursor now, so the level-5 income is the first thing the sweeper sees
            loan["sweeperPinned"] = True
            loan["activeAt"] = chain.now()
        store.save()

    @app.get("/health")
    def health():
        free = sum(1 for a in store.pool["pool"] if a["claimedBy"] is None)
        return {"ok": True, "network": "devnet", "desk": getattr(desk, "url", "fake"), "poolFree": free,
                "customers": len(store.pool["customers"]), "tokenLoaded": bool(getattr(desk, "token", None))}

    @app.get("/v1/facts")
    def facts():
        return {"minScoreAuto": real_policy["minScoreAuto"], "minScore": real_policy["minScore"],
                "holdTimeoutSeconds": real_policy["holdTimeoutSeconds"], "maxAutoPrincipalDrops": real_policy["maxAutoPrincipalDrops"],
                "maxAskDrops": str(MAX_ASK_DROPS), "minAskDrops": str(MIN_ASK_DROPS), "incomeDrops": str(INCOME_DROPS),
                "paymentInterval": common.PAYMENT_INTERVAL, "gracePeriod": common.GRACE_PERIOD, "termSeconds": TERM_SECONDS,
                "ceiling": CEILING, "broker": common.load_accounts()["accounts"]["broker"], "policyHash": policy.policy_hash(real_policy)}

    @app.post("/v1/sessions")
    def create_session():
        sid = "ps_" + secrets.token_hex(4)
        idx = store.claim(sid)
        addr = store.pool["pool"][idx]["address"]
        s = {"id": sid, "address": addr, "poolIndex": idx, "createdAt": chain.now(), "payments": [], "customerCount": 0,
             "credential": None, "loan": None, "sweeps": [], "default": None}
        s["balanceDrops"] = str(chain.balance(addr))
        rescore(s)
        store.sessions[sid] = s
        store.save()
        return public(s)

    @app.get("/v1/sessions/{sid}")
    def get_session(sid: str):
        s = session(sid)
        refresh_loan(s)
        return public(s)

    @app.post("/v1/sessions/{sid}/reset")
    def reset(sid: str):
        s = session(sid)
        store.release(s["poolIndex"])
        del store.sessions[sid]
        store.save()
        return {"ok": True, "released": s["address"]}

    @app.post("/v1/sessions/{sid}/income")
    def income(sid: str):
        s = session(sid)
        n = s["customerCount"]
        w = store.customer_wallet(n)
        if chain.balance(w.address) < CUSTOMER_FLOOR_DROPS:
            chain.faucet_wallet(w)
        invoice = f"INV-PG-{chain.now()}-{n % CUSTOMERS}"
        date = time.strftime("%Y-%m-%d", time.gmtime(chain.now()))
        res = chain.pay_income(w, s["address"], INCOME_DROPS, invoice, date)
        s["customerCount"] = n + 1
        pay = {"hash": res["hash"], "engineResult": res["engineResult"], "validated": res["validated"],
               "drops": str(INCOME_DROPS), "payer": w.address, "invoice": invoice, "ledgerIndex": res.get("ledgerIndex")}
        if not (res["validated"] and res["engineResult"] == "tesSUCCESS"):
            store.save()
            raise HTTPException(502, f"payment_not_validated:{res['engineResult']}")
        s["payments"].append(pay)
        s["balanceDrops"] = str(chain.balance(s["address"]))
        sweeps: list[dict] = []
        refresh_loan(s)
        if unlocked(s) == 5:
            sweeps = run_sweep(s)
            s["sweeps"].extend(sweeps)
        rescore(s)
        store.save()
        return {"payment": pay, "sweeps": sweeps, "session": public(s)}

    @app.post("/v1/sessions/{sid}/credential")
    def credential(sid: str):
        s = session(sid)
        if not s["payments"]:
            raise HTTPException(409, "earn_first")
        if s.get("credential"):
            return {"credential": s["credential"], "session": public(s)}
        status, out = desk.request_credential(s["address"])
        if status in (404, 405, 501):
            return {"away": True, "detail": "the broker is away", "session": public(s)}
        if status in (401, 503):
            raise HTTPException(502, f"broker_token:{out.get('detail')}")
        if status != 200:
            raise HTTPException(502, f"broker_{status}:{out.get('detail')}")
        broker = common.load_accounts()["accounts"]["broker"]
        acc = chain.credential_accept(store.wallet(s["poolIndex"]), broker)
        s["credential"] = {"createHash": out.get("hash"), "acceptHash": acc["hash"], "acceptResult": acc["engineResult"],
                           "issuer": broker, "type": "kyb-borrower"}
        rescore(s)
        store.save()
        return {"credential": s["credential"], "session": public(s)}

    @app.post("/v1/sessions/{sid}/borrow")
    def borrow(sid: str, body: BorrowBody):
        s = session(sid)
        drops = int(round(body.amountXrp * XRP))
        if drops < MIN_ASK_DROPS or drops > MAX_ASK_DROPS:
            raise HTTPException(422, "ask_out_of_range: 1 to 5 XRP")
        if not s["payments"]:
            raise HTTPException(409, "earn_first")
        loan = s.get("loan")
        if loan and (loan["status"] not in FINAL or loan["status"] in ACTIVE):
            raise HTTPException(409, f"loan_in_progress:{loan['status']}")
        w = store.wallet(s["poolIndex"])
        body_ = borrower.build_request_body(w, str(drops), TERM_SECONDS, PURPOSE, "0", common.load_accounts(),
                                            desk.policy(), sign=chain.sign_loan_set)
        s["loan"] = {"status": "deciding", "principalDrops": str(drops), "requestId": None, "askedAt": chain.now(),
                     "reason": None, "loanId": None, "txHash": None}
        store.save()

        def post():
            try:
                status, rec = desk.post_request(body_)
            except Exception as e:  # noqa: BLE001 - desk unreachable: the visitor sees a failed level, not a hang
                status, rec = 0, {"detail": f"{type(e).__name__}: {e}"}
            with store.lock:
                loan = s["loan"]
                if status != 200:
                    loan.update(status="failed", reason=f"desk_{status}:{rec.get('detail')}")
                else:
                    loan.update(requestId=rec["id"], status=rec["status"], reason=rec.get("reason"), loanId=rec.get("loanId"),
                                txHash=rec.get("txHash"), score=rec.get("score"), decidedBy=rec.get("decidedBy"),
                                memo=rec.get("memo"), engineResult=rec.get("engineResult"), deskTs=rec.get("ts"))
                    if rec["status"] in ACTIVE and rec.get("loanId"):
                        run_sweep(s)
                        loan.update(sweeperPinned=True, activeAt=chain.now())
                store.save()

        threading.Thread(target=post, daemon=True).start()
        return public(s)

    @app.post("/v1/sessions/{sid}/default")
    def default(sid: str):
        s = session(sid)
        refresh_loan(s)
        loan = s.get("loan") or {}
        if loan.get("status") not in ACTIVE or not loan.get("loanId"):
            raise HTTPException(409, "no_active_loan")
        status, out = desk.manage_default(loan["loanId"])
        if status != 200:
            raise HTTPException(502, f"desk_{status}:{out.get('detail')}")
        s["default"] = out
        if out.get("engineResult") == "tesSUCCESS":
            loan["status"] = "defaulted"
        rescore(s)
        store.save()
        return {"default": out, "session": public(s)}

    return app


# ---- CLI --------------------------------------------------------------------------------------------------------
def fund(store: Store, chain: Chain, n: int) -> None:
    while len(store.pool["customers"]) < CUSTOMERS:
        store.add_customer(chain.faucet_wallet())
        store.save()
        print(f"customer {len(store.pool['customers'])}/{CUSTOMERS} {store.pool['customers'][-1]['address']}", flush=True)
    for i in range(n):
        store.add_pool_account(chain.faucet_wallet())
        store.save()
        print(f"pool +1 ({i + 1}/{n}) {store.pool['pool'][-1]['address']}", flush=True)
    print(f"pool: {len(store.pool['pool'])} accounts, {len(store.pool['customers'])} customers (seeds in {store.dir}/pool.json)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Playground backend (:7510).")
    ap.add_argument("--fund", type=int, metavar="N", help="claim N pool accounts (+3 customers) from the devnet faucet")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args(argv)
    data = HERE / "data"
    if args.fund is not None:
        fund(Store(data), Chain(), args.fund)
        return 0
    import uvicorn
    uvicorn.run(make_app(data), host="127.0.0.1", port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
