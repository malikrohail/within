"""Delegate spike: pay the good merchant FROM the treasury, signed by the hot key.

  python -m scripts.spike_delegated_pay <treasury> [--path /lookup] [--direct]

Default: the real x402 flow (merchant 402 -> PAYMENT-SIGNATURE -> T54 facilitator verify/settle).
--direct: skip x402 and submit the delegated blob to rippled, printing the raw engine_result.
Testnet only. The hot seed is read from wallet/.env and never printed.
"""
import argparse
import pathlib

from x402_xrpl.client import presigned_payment_payer as payer_mod
from x402_xrpl.clients import decode_payment_response, x402_requests
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import SubmitOnly
from xrpl.models.transactions import Payment
from xrpl.wallet import Wallet

from merchants.common import RPC_URL, load_merchants

ENV = pathlib.Path(__file__).resolve().parents[2] / "wallet" / ".env"


def hot_wallet():
    for line in ENV.read_text().splitlines():
        if line.startswith("HOT_WALLET_SEED="):
            return Wallet.from_seed(line.split("=", 1)[1].strip().strip('"'))
    raise SystemExit("HOT_WALLET_SEED missing from wallet/.env")


def _error(resp):
    try:
        return resp.json().get("error")
    except ValueError:
        return resp.text[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("treasury")
    ap.add_argument("--path", default="/lookup")
    ap.add_argument("--direct", action="store_true")
    args = ap.parse_args()
    assert "altnet" in RPC_URL or "testnet" in RPC_URL, "testnet only"

    hot = hot_wallet()
    # The payer builds Payment(account=<signing wallet>, ...): swap in Account=treasury, Delegate=hot.
    payer_mod.Payment = lambda **kw: Payment(**{**kw, "account": args.treasury, "delegate": hot.classic_address})
    payer = payer_mod.XRPLPresignedPaymentPayer(
        payer_mod.XRPLPresignedPaymentPayerOptions(wallet=hot, network="xrpl:1", rpc_url=RPC_URL))
    signed = {}

    def factory(reqs, *, extensions=None, resource=None):
        prepared = payer.prepare_payment(reqs, extensions=extensions, resource=resource)
        signed["blob"] = prepared.signed_tx_blob
        return prepared.payment_header

    url = f"http://localhost:{load_merchants()['good']['port']}{args.path}"
    print(f"treasury={args.treasury} delegate(hot)={hot.classic_address} url={url}")
    session = x402_requests(hot, rpc_url=RPC_URL, payment_header_factory=factory, network_filter=None, scheme_filter="exact")

    if args.direct:
        # Get the 402 requirements, sign, then submit ourselves to see rippled's own verdict.
        first = session.get(url, timeout=60)  # pays through x402 as a side effect, so use --direct only when expected to fail
        if "blob" not in signed:
            raise SystemExit(f"no payment was signed (status {first.status_code})")
        res = JsonRpcClient(RPC_URL).request(SubmitOnly(tx_blob=signed["blob"])).result
        print(f"x402 status={first.status_code} error={_error(first)}")
        print(f"direct submit engine_result={res.get('engine_result')} code={res.get('engine_result_code')} "
              f"message={res.get('engine_result_message')!r} hash={res.get('tx_json', {}).get('hash')}")
        return

    resp = session.get(url, timeout=120)
    settlement = decode_payment_response(resp.headers["PAYMENT-RESPONSE"]) if "PAYMENT-RESPONSE" in resp.headers else {}
    print(f"status={resp.status_code} settlement={settlement}")
    print(f"error={_error(resp)} body={resp.text[:200]}")


if __name__ == "__main__":
    main()
