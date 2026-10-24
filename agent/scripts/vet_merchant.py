"""Vet the good merchant (and only it) on the ledger: the wallet issues a Credential, the merchant accepts it.

  python scripts/vet_merchant.py [--wallet http://localhost:7402] [--timeout 120]

Writes CREDENTIAL_ISSUER (and CREDENTIAL_TYPE) to agent/.env so the running merchant's
auto-accept loop picks them up, then waits until GET /v1/merchants shows the good merchant accepted.
Idempotent.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values, set_key

AGENT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = AGENT_DIR / ".env"
EXPLORER = "https://testnet.xrpl.org/transactions/"
POLL_SECONDS = 2


def _entry(wallet_url, address):
    resp = requests.get(f"{wallet_url}/v1/merchants", timeout=10)
    resp.raise_for_status()
    return next((m for m in resp.json() if m.get("address") == address), None)


def _print_tx(label, tx_hash):
    if tx_hash:
        print(f"{label} {tx_hash} {EXPLORER}{tx_hash}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--wallet", default="http://localhost:7402")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    wallet_url = args.wallet.rstrip("/")
    good = json.loads((AGENT_DIR / "merchants.json").read_text())["good"]["address"]

    resp = requests.get(f"{wallet_url}/v1/policy", timeout=10)
    resp.raise_for_status()
    policy = resp.json()
    issuer = policy.get("credentialIssuer")
    if not issuer:
        print("GET /v1/policy has no credentialIssuer; is the wallet on contract v1.4?", file=sys.stderr)
        return 1
    ENV_PATH.touch(exist_ok=True)
    set_key(ENV_PATH, "CREDENTIAL_ISSUER", issuer, quote_mode="never")
    set_key(ENV_PATH, "CREDENTIAL_TYPE", policy.get("credentialType") or "x402-merchant", quote_mode="never")
    print(f"issuer {issuer} written to {ENV_PATH.name}", flush=True)

    entry = _entry(wallet_url, good)
    if entry and entry.get("accepted"):
        print(f"good merchant {good} already vetted and accepted", flush=True)
        _print_tx("Credential tx", entry.get("txHash"))  # PreviousTxnID: the accept, not the create
        return 0
    tx_hash = entry.get("txHash") if entry else None
    if entry is None:
        # The wallet's operator routes need X-Wallet-Token (WALLET_ADMIN_TOKEN, env or wallet/.env).
        token = os.environ.get("WALLET_ADMIN_TOKEN") or dotenv_values(AGENT_DIR.parent / "wallet" / ".env").get("WALLET_ADMIN_TOKEN")
        resp = requests.post(f"{wallet_url}/v1/merchants", json={"address": good}, headers={"X-Wallet-Token": token} if token else {}, timeout=60)
        if resp.status_code == 200:
            tx_hash = resp.json().get("txHash")
        elif resp.status_code != 409:  # 409: the credential already exists, just wait for the accept
            print(f"POST /v1/merchants failed: {resp.status_code} {resp.text}", file=sys.stderr)
            return 1
    _print_tx("CredentialCreate", tx_hash)

    print(f"waiting up to {args.timeout:.0f}s for {good} to accept...", flush=True)
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        try:
            entry = _entry(wallet_url, good)
        except requests.RequestException as exc:  # live ledger read; one RPC hiccup must not end the run
            print(f"GET /v1/merchants failed, retrying: {exc}", file=sys.stderr)
            entry = None
        if entry and entry.get("accepted"):
            print(f"good merchant {good} accepted", flush=True)
            if not tx_hash:
                _print_tx("Credential tx", entry.get("txHash"))
            return 0
        time.sleep(POLL_SECONDS)
    print(f"timed out: {good} has not accepted the credential (is the merchant running the auto-accept loop?)",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
