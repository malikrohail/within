"""Shared merchant setup: seeds in agent/.env, addresses in agent/merchants.json, x402 wiring."""
import fcntl
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from dotenv import dotenv_values
from fastapi import FastAPI
from x402_xrpl.server import require_payment
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountObjects, AccountObjectType
from xrpl.models.transactions import CredentialAccept
from xrpl.transaction import submit_and_wait
from xrpl.wallet import Wallet, generate_faucet_wallet

AGENT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = AGENT_DIR / ".env"
MERCHANTS_JSON = AGENT_DIR / "merchants.json"
LOCK_PATH = AGENT_DIR / ".setup.lock"


def _setting(name, default):
    # Read single settings from agent/.env without loading its seeds into os.environ.
    values = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    return os.getenv(name) or values.get(name) or default


RPC_URL = _setting("XRPL_RPC_URL", "https://s.altnet.rippletest.net:51234/")
FACILITATOR_URL = _setting("XRPL_FACILITATOR_URL", "https://xrpl-facilitator-testnet.t54.ai")

LSF_ACCEPTED = 0x00010000
ACCEPT_INTERVAL_SECONDS = 5

MERCHANTS = {
    "good": {"seed_var": "MERCHANT_SEED", "port": 8001},
    "rogue": {"seed_var": "ROGUE_SEED", "port": 8002},
}


@contextmanager
def _setup_lock():
    # good and rogue may start at the same moment; one of them does the whole first run.
    with open(LOCK_PATH, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _ensure_seeds_locked(seed_vars):
    values = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    seeds = {}
    for var in seed_vars:
        seed = values.get(var) or os.getenv(var)
        if not seed:
            seed = generate_faucet_wallet(JsonRpcClient(RPC_URL), debug=False).seed
            with open(ENV_PATH, "a") as env:
                env.write(f"{var}={seed}\n")
        seeds[var] = seed
    return seeds


def ensure_seeds(*seed_vars):
    """Return {var: seed}, creating and faucet-funding any that are missing from agent/.env."""
    with _setup_lock():
        return _ensure_seeds_locked(seed_vars)


def ensure_merchants():
    """Make sure both merchant seeds exist and merchants.json matches them. Returns the json dict."""
    with _setup_lock():
        seeds = _ensure_seeds_locked([m["seed_var"] for m in MERCHANTS.values()])
        data = {
            name: {"address": Wallet.from_seed(seeds[m["seed_var"]]).classic_address, "port": m["port"]}
            for name, m in MERCHANTS.items()
        }
        if not MERCHANTS_JSON.exists() or json.loads(MERCHANTS_JSON.read_text()) != data:
            MERCHANTS_JSON.write_text(json.dumps(data, indent=2) + "\n")
        return data


def load_merchants():
    return json.loads(MERCHANTS_JSON.read_text())


def add_paid_path(app: FastAPI, *, path, price, source_tag, pay_to, description):
    app.middleware("http")(require_payment(
        path=path, price=str(price), pay_to_address=pay_to, facilitator_url=FACILITATOR_URL,
        network="xrpl:1", asset="XRP", description=description,
        extra={"sourceTag": source_tag}))


def accept_pending_credential(client, wallet, issuer, credential_type):
    """Submit one CredentialAccept for a pending (issuer, type) credential on this account. Returns its hash or None."""
    type_hex = credential_type.encode().hex().upper()
    resp = client.request(AccountObjects(account=wallet.classic_address, type=AccountObjectType.CREDENTIAL))
    for obj in resp.result.get("account_objects", []):
        if (obj.get("Issuer") == issuer and obj.get("CredentialType", "").upper() == type_hex
                and not obj.get("Flags", 0) & LSF_ACCEPTED):
            tx = CredentialAccept(account=wallet.classic_address, issuer=issuer, credential_type=type_hex)
            result = submit_and_wait(tx, client, wallet).result
            return result["hash"]
    return None


def _accept_tick(client, wallet, name):
    # CREDENTIAL_ISSUER is read every tick so a value vet_merchant.py writes later is picked up without a restart.
    try:
        issuer = _setting("CREDENTIAL_ISSUER", None)
        if not issuer:
            return
        tx_hash = accept_pending_credential(client, wallet, issuer, _setting("CREDENTIAL_TYPE", "x402-merchant"))
    except Exception as exc:
        print(f"{name} merchant credential check failed, retrying: {exc}", flush=True)
        return
    if tx_hash:
        print(f"{name} merchant accepted credential from {issuer} tx={tx_hash}", flush=True)


def _accept_loop(wallet, name):
    client = JsonRpcClient(RPC_URL)
    while True:
        _accept_tick(client, wallet, name)
        time.sleep(ACCEPT_INTERVAL_SECONDS)


def run(name, create_app):
    import uvicorn

    merchants = ensure_merchants()
    me = merchants[name]
    wallet = Wallet.from_seed(ensure_seeds(MERCHANTS[name]["seed_var"])[MERCHANTS[name]["seed_var"]])
    threading.Thread(target=_accept_loop, args=(wallet, name), daemon=True).start()
    print(f"{name} merchant {me['address']} on :{me['port']}", flush=True)
    uvicorn.run(create_app(me["address"]), host="127.0.0.1", port=me["port"])
