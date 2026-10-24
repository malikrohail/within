"""The agent's only way to pay: ask the policy wallet to sign. No signing key lives in this process."""
import os
from pathlib import Path

import requests
from dotenv import dotenv_values
from x402_xrpl.client.presigned_payment_payer import build_payment_header_for_signed_blob
from x402_xrpl.clients import x402_requests
from xrpl.wallet import Wallet

DEFAULT_WALLET_URL = "http://localhost:7402"
WALLET_ENV = Path(__file__).resolve().parent.parent / "wallet" / ".env"


def operator_headers() -> dict:
    """X-Wallet-Token for the wallet's operator routes: WALLET_ADMIN_TOKEN from the env, else wallet/.env."""
    token = os.environ.get("WALLET_ADMIN_TOKEN") or dotenv_values(WALLET_ENV).get("WALLET_ADMIN_TOKEN")
    return {"X-Wallet-Token": token} if token else {}
DEFAULT_RPC_URL = "https://s.altnet.rippletest.net:51234/"
FALLBACK_READ_TIMEOUT = 130
REFUSAL_STATUSES = {403, 408, 503}


class PolicyRefused(Exception):
    """The wallet said no: refused by policy, denied on the device, hold expired, or device missing."""

    def __init__(self, reason, request_id=None, status=None):
        super().__init__(reason)
        self.reason = reason
        self.request_id = request_id
        self.status = status


class WalletError(RuntimeError):
    """The wallet was unreachable or answered outside the contract."""


def _read_timeout(wallet_url):
    # /v1/pay blocks for up to holdTimeoutSeconds on a held request.
    try:
        hold = int(requests.get(f"{wallet_url}/v1/policy", timeout=5).json()["holdTimeoutSeconds"])
        return hold + 40
    except Exception:
        return FALLBACK_READ_TIMEOUT


def make_wallet_header_factory(wallet_url=DEFAULT_WALLET_URL, purpose_getter=lambda: "agent purchase"):
    """Build a payment_header_factory for x402_requests that delegates signing to the wallet.

    After each call, factory.last_result holds the wallet's 200 body and factory.last_error the
    exception it raised (if any). x402_requests swallows factory exceptions and returns the 402,
    so callers use paid_get() to get PolicyRefused back.
    """
    wallet_url = wallet_url.rstrip("/")

    def factory(reqs, *, extensions=None, resource=None) -> str:
        factory.last_result = None
        factory.last_error = None
        try:
            body = _pay(wallet_url, reqs, purpose_getter(), resource)
            factory.last_result = body
            return build_payment_header_for_signed_blob(
                req=reqs, signed_tx_blob=body["signedTxBlob"], invoice_id=reqs.invoice_id(),
                extensions=extensions, resource=resource)
        except Exception as exc:
            factory.last_error = exc
            raise

    factory.last_result = None
    factory.last_error = None
    return factory


def _pay(wallet_url, reqs, purpose, resource):
    payload = {
        "requirements": reqs.to_dict(),
        "purpose": purpose,
        "resource": resource.to_dict() if resource else None,
    }
    try:
        resp = requests.post(f"{wallet_url}/v1/pay", json=payload, timeout=(5, _read_timeout(wallet_url)))
    except requests.ReadTimeout as exc:
        raise WalletError(f"timed out waiting for the wallet decision at {wallet_url}: {exc}") from exc
    except requests.RequestException as exc:
        raise WalletError(f"wallet unreachable at {wallet_url}: {exc}") from exc
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code == 200 and isinstance(body, dict) and body.get("signedTxBlob"):
        return body
    if resp.status_code in REFUSAL_STATUSES:
        raise PolicyRefused(body.get("reason") or f"http_{resp.status_code}", body.get("requestId"), resp.status_code)
    raise WalletError(f"wallet returned {resp.status_code}: {resp.text[:200]}")


def make_session(factory, rpc_url=DEFAULT_RPC_URL):
    # The wallet argument is required by x402_requests but never used once a factory is set.
    return x402_requests(Wallet.create(), rpc_url=rpc_url, payment_header_factory=factory,
                         network_filter=None, scheme_filter="exact")


def paid_get(session, factory, url, **kwargs):
    """GET through the x402 session, re-raising what the factory raised instead of returning the 402."""
    factory.last_result = None
    factory.last_error = None
    resp = session.get(url, **kwargs)
    if factory.last_error is not None:
        raise factory.last_error
    if resp.status_code == 402 and factory.last_result is None:
        raise WalletError("got 402 but the wallet was never asked (no usable payment requirements)")
    return resp
