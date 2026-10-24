#!/usr/bin/env python
"""Follow-up to run.py step 7p: borrower2 (whose trust line was auto-created by LoanSet with limit 0) ran out of USD
before the full payoff. This script shows the IOU gotcha and repairs it so the vault can be fully withdrawn:

  1. issuer Payment 1 USD -> borrower2 on the limit-0 line   (expect tecPATH_DRY: a zero-limit line accepts nothing)
  2. borrower2 TrustSet limit 1,000,000 USD
  3. issuer Payment 1 USD -> borrower2                        (now tesSUCCESS)
  4. LoanPay tfLoanFullPayment, 5. LoanDelete by the broker owner

Run: experiments/.venv/bin/python experiments/010-iou-vault/repay_probe.py [LoanID]
Default LoanID: the "7p LoanSet" entry in run-log.json. Log: probe-log.json.
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

from xrpl.clients import JsonRpcClient
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.requests import GenericRequest
from xrpl.models.transactions import LoanDelete, LoanPay, Payment, TrustSet
from xrpl.models.transactions.loan_pay import LoanPayFlag
from xrpl.transaction import submit_and_wait
from xrpl.wallet import Wallet

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import CURRENCY, EXPLORER, TRUST_LIMIT, ceil_iou, iou_balance, iou_lines, ledger_entry  # noqa: E402

HERE = Path(__file__).resolve().parent
client = JsonRpcClient("https://s.devnet.rippletest.net:51234")
seeds = json.loads((HERE.parent / ".secrets" / "010.json").read_text())
issuer_w, broker, b2 = (Wallet.from_seed(seeds[n]) for n in ["issuer", "broker", "borrower2"])
issuer = issuer_w.address
log_path = HERE / "probe-log.json"
log = json.loads(log_path.read_text()) if log_path.exists() else []

if len(sys.argv) > 1:
    loan_id = sys.argv[1]
else:
    loan_id = next(r["loan_id"] for r in json.loads((HERE / "run-log.json").read_text()) if r["step"] == "7p LoanSet")


def usd(v: str) -> IssuedCurrencyAmount:
    return IssuedCurrencyAmount(currency=CURRENCY, issuer=issuer, value=v)


def go(step, tx, wallet):
    print(f"\n[{step}] {tx.transaction_type.value} from {wallet.address}")
    try:
        res = submit_and_wait(tx, client, wallet).result
        code, h = res["meta"]["TransactionResult"], res["hash"]
    except Exception as e:
        code, h = f"EXCEPTION: {e}", None
    print(f"  -> {code}  hash={h}")
    if h:
        print(f"     {EXPLORER}{h}")
    log.append({"step": step, "result": code, "hash": h, "explorer": (EXPLORER + h) if h else None})
    log_path.write_text(json.dumps(log, indent=2))
    return code


print(f"borrower2 {b2.address} line before: {json.dumps(iou_lines(b2.address, issuer))}")
go("p1 Payment issuer -> borrower2 on limit-0 auto-created line", Payment(account=issuer, destination=b2.address, amount=usd("1")), issuer_w)
go("p2 TrustSet borrower2", TrustSet(account=b2.address, limit_amount=usd(TRUST_LIMIT)), b2)
go("p3 Payment issuer -> borrower2 after TrustSet", Payment(account=issuer, destination=b2.address, amount=usd("1")), issuer_w)
print(f"borrower2 line after: {json.dumps(iou_lines(b2.address, issuer))}")

loan = ledger_entry(loan_id)
full = Decimal(ceil_iou(loan["TotalValueOutstanding"])) + Decimal(loan.get("ClosePaymentFee", "0")) + Decimal(loan.get("LoanServiceFee", "0"))
full_s = format(full.normalize(), "f")
print(f"\nfull payoff = ceil6(TotalValueOutstanding {loan['TotalValueOutstanding']}) + ClosePaymentFee + LoanServiceFee = {full_s} {CURRENCY}")
code = go("p4 LoanPay full payoff (tfLoanFullPayment)", LoanPay(account=b2.address, loan_id=loan_id, amount=usd(full_s), flags=LoanPayFlag.TF_LOAN_FULL_PAYMENT), b2)
loan = ledger_entry(loan_id)
print(f"  Loan after: PaymentRemaining={loan.get('PaymentRemaining')} PrincipalOutstanding={loan.get('PrincipalOutstanding')}")
if int(loan.get("PaymentRemaining", 0)) == 0:
    go("p5 LoanDelete (broker owner)", LoanDelete(account=broker.address, loan_id=loan_id), broker)
print(f"\nborrower2 {CURRENCY}: {iou_balance(b2.address, issuer)}   broker {CURRENCY}: {iou_balance(broker.address, issuer)}")
vault_id = ledger_entry(next(r["loan_broker_id"] for r in json.loads((HERE / "run-log.json").read_text()) if r["step"] == "5b LoanBrokerSet"))["VaultID"]
v = ledger_entry(vault_id)
print(f"Vault: AssetsTotal={v.get('AssetsTotal')} AssetsAvailable={v.get('AssetsAvailable')}")
log.append({"step": "probe final", "vault": {k: v.get(k) for k in ["AssetsTotal", "AssetsAvailable"]}, "borrower2_lines": iou_lines(b2.address, issuer)})
log_path.write_text(json.dumps(log, indent=2))
