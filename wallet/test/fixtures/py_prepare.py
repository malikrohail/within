"""Run the real x402_xrpl prepare_payment with a stubbed ledger; print the signed blob.
argv[1] = JSON {seed, req, ledger, fee, sequence}."""
import json, sys
from types import SimpleNamespace
import x402_xrpl.client.presigned_payment_payer as ppp
from xrpl.wallet import Wallet
from x402_xrpl.types import PaymentRequirements

args = json.loads(sys.argv[1])
ppp.get_latest_validated_ledger_sequence = lambda _c: args["ledger"]
ppp.autofill = lambda tx, _c: tx.__class__.from_dict({**tx.to_dict(), "fee": args["fee"], "sequence": args["sequence"]})

class Client:
    def request(self, _r):
        return SimpleNamespace(result={"info": {"network_id": 1}})

wallet = Wallet.from_seed(args["seed"])
payer = ppp.XRPLPresignedPaymentPayer(
    ppp.XRPLPresignedPaymentPayerOptions(wallet=wallet, network="xrpl:1", rpc_url="http://unused"),
    client=Client(),
)
prepared = payer.prepare_payment(PaymentRequirements.from_dict(args["req"]))
print(prepared.signed_tx_blob)
