#!/usr/bin/env python
"""Redeem the depositor's shares from a close-ended vault created by run.py once its RedemptionDate has passed.

Run: experiments/.venv/bin/python experiments/001-vault-loan-baseline/withdraw.py <VaultID> [amount_xrp]
Default amount: the full DEPOSIT_XRP (200). Waits for the Redemption phase, then VaultWithdraw by the depositor.
"""
import json
import sys
import time
from pathlib import Path

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import GenericRequest, Ledger, AccountInfo
from xrpl.models.transactions import VaultWithdraw
from xrpl.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops, drops_to_xrp
from xrpl.wallet import Wallet

HERE = Path(__file__).resolve().parent
client = JsonRpcClient("https://s.devnet.rippletest.net:51234")
vault_id = sys.argv[1]
amount_xrp = float(sys.argv[2]) if len(sys.argv) > 2 else 200
depositor = Wallet.from_seed(json.loads((HERE.parent / ".secrets" / "001.json").read_text())["depositor"])

vault = client.request(GenericRequest(method="ledger_entry", index=vault_id, ledger_index="validated")).result["node"]
red = int(vault["RedemptionDate"])
while True:
    t = int(client.request(Ledger(ledger_index="validated")).result["ledger"]["close_time"])
    if t > red:
        break
    print(f"waiting for RedemptionDate {red}: ledger time {t} ({red - t}s)")
    time.sleep(min(10, max(2, red - t)))
print(f"Vault before: AssetsTotal={vault['AssetsTotal']} AssetsAvailable={vault['AssetsAvailable']}")
bal0 = int(client.request(AccountInfo(account=depositor.address, ledger_index="validated")).result["account_data"]["Balance"])
tx = VaultWithdraw(account=depositor.address, vault_id=vault_id, amount=xrp_to_drops(amount_xrp))
try:
    res = submit_and_wait(tx, client, depositor).result
    code = res["meta"]["TransactionResult"]; h = res["hash"]
except Exception as e:
    code, h = f"EXCEPTION: {e}", None
print(f"VaultWithdraw -> {code} hash={h}\nhttps://devnet.xrpl.org/transactions/{h}")
vault = client.request(GenericRequest(method="ledger_entry", index=vault_id, ledger_index="validated")).result["node"]
bal1 = int(client.request(AccountInfo(account=depositor.address, ledger_index="validated")).result["account_data"]["Balance"])
print(f"Vault after: AssetsTotal={vault.get('AssetsTotal')} AssetsAvailable={vault.get('AssetsAvailable')}")
print(f"depositor balance {drops_to_xrp(str(bal0))} -> {drops_to_xrp(str(bal1))} XRP (delta {bal1 - bal0} drops)")
log_path = HERE / "run-log.json"
log = json.loads(log_path.read_text()) if log_path.exists() else []
log.append({"step": "8 VaultWithdraw", "result": code, "hash": h, "explorer": f"https://devnet.xrpl.org/transactions/{h}", "vault_after": vault, "depositor_delta_drops": bal1 - bal0})
log_path.write_text(json.dumps(log, indent=2))
