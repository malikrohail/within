"""Stand-in for the wallet API so the agent can be tested without it. Run: python -m tests.stub_wallet

Serves the contract's wallet API on :7403. Signs every allowed request with a faucet-funded
STUB_SEED (a real testnet blob, so purchases settle for real). Refuses any payTo not in
allowedMerchants (default: the good merchant from merchants.json, or STUB_ALLOWLIST=r1,r2).
Over-cap requests come back "approved" at once, or with STUB_HOLD=1 wait as "held" for
/device-tap or /deny like the real wallet does.
"""
import os
import threading
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from x402_xrpl.client import XRPLPresignedPaymentPayer, XRPLPresignedPaymentPayerOptions
from x402_xrpl.types import PaymentRequirements
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo
from xrpl.models.transactions import Transaction
from xrpl.wallet import Wallet, generate_faucet_wallet

from merchants.common import MERCHANTS_JSON, RPC_URL, ensure_seeds, load_merchants

PORT = 7403
DEVICE_ACCOUNT = "rUGeRsKjpnDVAi1uJYhAxWXbETC917VQ6B"
MIN_BALANCE_DROPS = 10_000_000
DEFAULT_POLICY = {
    "perTxCapDrops": "100000",
    "dailyBudgetDrops": "100000000",
    "allowedMerchants": [],
    "allowedNetworks": ["xrpl:1"],
    "allowedAssets": ["XRP"],
    "holdTimeoutSeconds": 90,
}
POLICY_KEYS = set(DEFAULT_POLICY)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _balance(client, address):
    result = client.request(AccountInfo(account=address, ledger_index="validated")).result
    return int(result["account_data"]["Balance"]) if "account_data" in result else 0


def create_app(wallet: Wallet, allowlist=None, rpc_url=RPC_URL, hold=False) -> FastAPI:
    app = FastAPI(title="stub wallet")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5174", "http://localhost:5173"],
                       allow_methods=["*"], allow_headers=["*"])
    client = JsonRpcClient(rpc_url)
    payer = XRPLPresignedPaymentPayer(
        XRPLPresignedPaymentPayerOptions(wallet=wallet, network="xrpl:1", rpc_url=rpc_url), client=client)
    policy = dict(DEFAULT_POLICY, allowedMerchants=list(allowlist or []))
    records = []  # newest last
    waiters = {}  # request id -> (Event, outcome dict)
    lock = threading.Lock()
    balance_cache = {"at": 0.0, "drops": None}

    def record(**fields):
        item = {"id": uuid.uuid4().hex[:12], "ts": _now(), "reason": None, "signer": None, "txHash": None, **fields}
        with lock:
            records.append(item)
        return item

    def spent_today():
        today = datetime.now().astimezone().date()
        return sum(int(r["amountDrops"]) for r in records if r["status"] in ("auto", "approved")
                   and datetime.fromisoformat(r["ts"].replace("Z", "+00:00")).astimezone().date() == today)

    def sign(req, fields, decision, signer, item=None):
        try:
            prepared = payer.prepare_payment(req)
        except Exception as exc:
            if item is not None:
                item.update(status="refused", reason="sign_failed")
            return JSONResponse(status_code=502, content={"reason": f"sign_failed: {exc}"})
        tx_hash = Transaction.from_blob(prepared.signed_tx_blob).get_hash()
        if item is None:
            item = record(**fields)
        item.update(status=decision, signer=signer, txHash=tx_hash)
        return {"decision": decision, "requestId": item["id"], "signer": signer, "account": wallet.classic_address,
                "signedTxBlob": prepared.signed_tx_blob, "txHash": tx_hash}

    def refuse(item, status, decision, reason):
        item.update(status=decision, reason=reason)
        return JSONResponse(status_code=status, content={"decision": decision, "requestId": item["id"], "reason": reason})

    @app.post("/v1/pay")
    def pay(body: dict):
        try:
            req = PaymentRequirements.from_dict(body["requirements"])
            amount = int(req.amount)
            if not req.invoice_id():
                raise ValueError("missing invoiceId")
        except Exception as exc:
            return JSONResponse(status_code=400, content={"reason": f"malformed: {exc}"})
        resource = body.get("resource") or {}
        fields = dict(merchant=req.pay_to, amountDrops=str(amount), purpose=body.get("purpose") or "",
                      resourceUrl=resource.get("url"))
        # Contract decision order; a row is written with its real status, never a transient "held".
        for refused, reason in [
            (req.network not in policy["allowedNetworks"], "network_not_allowed"),
            (str(req.asset or "XRP") not in policy["allowedAssets"], "asset_not_allowed"),
            (req.pay_to not in policy["allowedMerchants"], "merchant_not_credentialed"),
            (amount + spent_today() > int(policy["dailyBudgetDrops"]), "daily_budget_exceeded"),
        ]:
            if refused:
                return refuse(record(**fields, status="refused"), 403, "refused", reason)
        if amount <= int(policy["perTxCapDrops"]):
            return sign(req, fields, "auto", "hot")
        if not hold:
            return sign(req, fields, "approved", "device")
        item = record(**fields, status="held")
        event, outcome = threading.Event(), {}
        waiters[item["id"]] = (event, outcome)
        try:
            if not event.wait(int(policy["holdTimeoutSeconds"])):
                return refuse(item, 408, "expired", "hold_timeout")
        finally:
            waiters.pop(item["id"], None)
        if outcome.get("deny"):
            return refuse(item, 403, "refused", "denied_on_device")
        return sign(req, fields, "approved", "device", item)

    def resolve(request_id, **outcome):
        waiter = waiters.get(request_id)
        if waiter is None:
            return JSONResponse(status_code=404, content={"reason": "not_held"})
        waiter[1].update(outcome)
        waiter[0].set()
        return JSONResponse(status_code=202, content={"ok": True})

    @app.post("/v1/requests/{request_id}/device-tap")
    def device_tap(request_id: str):
        return resolve(request_id, deny=False)

    @app.post("/v1/requests/{request_id}/deny")
    def deny(request_id: str):
        return resolve(request_id, deny=True)

    @app.get("/v1/requests")
    def list_requests(limit: int = 200):
        with lock:
            return list(reversed(records))[:limit]

    @app.get("/v1/policy")
    def get_policy():
        return policy

    @app.put("/v1/policy")
    async def put_policy(request: Request):
        new = await request.json()
        if not isinstance(new, dict) or set(new) != POLICY_KEYS:
            return JSONResponse(status_code=400, content={"reason": "policy must have exactly " + ", ".join(sorted(POLICY_KEYS))})
        policy.clear()
        policy.update(new)
        return policy

    @app.get("/v1/status")
    def status():
        if time.monotonic() - balance_cache["at"] > 10:
            try:
                balance_cache["drops"] = str(_balance(client, wallet.classic_address))
                balance_cache["at"] = time.monotonic()
            except Exception:
                pass
        return {"hotAccount": wallet.classic_address, "hotBalanceDrops": balance_cache["drops"] or "0",
                "deviceAccount": DEVICE_ACCOUNT, "deviceBalanceDrops": "98000000", "deviceConnected": True,
                "deviceApp": "XRP 2.8.1 (stub)", "spentTodayDrops": str(spent_today()), "pending": len(waiters)}

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


def _default_allowlist():
    env = os.getenv("STUB_ALLOWLIST")
    if env:
        return [a.strip() for a in env.split(",") if a.strip()]
    return [load_merchants()["good"]["address"]] if MERCHANTS_JSON.exists() else []


def main():
    import uvicorn

    wallet = Wallet.from_seed(ensure_seeds("STUB_SEED")["STUB_SEED"])
    client = JsonRpcClient(RPC_URL)
    if _balance(client, wallet.classic_address) < MIN_BALANCE_DROPS:
        generate_faucet_wallet(client, wallet=wallet, debug=False)
    allowlist = _default_allowlist()
    hold = os.getenv("STUB_HOLD") == "1"
    print(f"stub wallet {wallet.classic_address} balance={_balance(client, wallet.classic_address)} drops "
          f"allowlist={allowlist} hold={hold} on :{PORT}", flush=True)
    uvicorn.run(create_app(wallet, allowlist, hold=hold), host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
