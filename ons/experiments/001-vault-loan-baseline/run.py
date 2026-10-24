#!/usr/bin/env python
"""Experiment 001: XLS-65 Single Asset Vault + XLS-66 Lending Protocol happy path on devnet.

Run:  experiments/.venv/bin/python experiments/001-vault-loan-baseline/run.py [--withdraw]

Steps (each prints result code, hash, explorer link):
  1. load/create + fund wallets (depositor, broker == vault owner, borrower)
  2. VaultCreate (XRP, public, CLOSE-ENDED: LendingProtocolV1_1 only lets a LoanBroker attach to a close-ended vault)
  3. VaultDeposit by depositor
  4. LoanBrokerSet + LoanBrokerCoverDeposit by broker
  5. wait for the vault's Investment phase, then LoanSet (borrower signs, broker counter-signs, borrower submits)
  6. LoanPay one installment, then LoanPay tfLoanFullPayment, then LoanDelete by the broker owner
  7. final balances + Vault / LoanBroker / Loan objects
  8. (--withdraw) wait for Redemption phase, VaultWithdraw by depositor

Seeds live in experiments/.secrets/001.json and are never printed.
A machine-readable log of every tx is written to run-log.json next to this file.
"""
from __future__ import annotations

import json
import math
import os
import stat
import sys
import time
from pathlib import Path
from typing import Any, Optional

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo, GenericRequest, Ledger, Tx
from xrpl.models.transactions import (
    LoanBrokerCoverDeposit,
    LoanBrokerSet,
    LoanDelete,
    LoanPay,
    LoanSet,
    Transaction,
    VaultCreate,
    VaultDeposit,
    VaultWithdraw,
)
from xrpl.models.transactions.loan_pay import LoanPayFlag
from xrpl.models.transactions.vault_create import VaultKind, WithdrawalPolicy
from xrpl.models.currencies import XRP
from xrpl.transaction import autofill, sign, submit_and_wait
from xrpl.transaction.counterparty_signer import sign_loan_set_by_counterparty
from xrpl.utils import drops_to_xrp, xrp_to_drops
from xrpl.wallet import Wallet, generate_faucet_wallet

# ---------------------------------------------------------------- constants
JSON_RPC = "https://s.devnet.rippletest.net:51234"
FAUCET_HOST = "faucet.devnet.rippletest.net"
EXPLORER = "https://devnet.xrpl.org/transactions/"
RIPPLE_EPOCH = 946684800

HERE = Path(__file__).resolve().parent
SECRETS = HERE.parent / ".secrets" / "001.json"
LOG_PATH = HERE / "run-log.json"

DEPOSIT_XRP = 200           # depositor -> vault
COVER_XRP = 20              # broker first-loss capital
PRINCIPAL_XRP = 50          # loan principal
SUBSCRIPTION_SECS = 120     # how long the vault accepts deposits (Subscription phase)
INVESTMENT_SECS = 600       # Subscription->Redemption window; min 180 (rippled kMinInvestmentPeriod)
PAYMENT_TOTAL = 3           # 3 installments so a "full early payoff" is still allowed after one payment
PAYMENT_INTERVAL = 60       # seconds, the minimum
INTEREST_RATE = 10_000      # 1/10 bp => 10% annualised
MANAGEMENT_FEE_RATE = 1_000 # 1/10 bp => 1% of interest to the broker
COVER_RATE_MINIMUM = 10_000 # 10% of debt must be covered by first-loss capital
COVER_RATE_LIQUIDATION = 50_000  # 50% of minimum cover liquidated on default
DEBT_MAXIMUM_DROPS = str(xrp_to_drops(100))
TX_FEE_DROPS = "200"        # generous flat fee; LoanSet carries two signatures

client = JsonRpcClient(JSON_RPC)
LOG: list[dict[str, Any]] = []


# ---------------------------------------------------------------- helpers
def now_ripple() -> int:
    return int(time.time()) - RIPPLE_EPOCH


def ledger_close_time() -> int:
    r = client.request(Ledger(ledger_index="validated")).result
    return int(r["ledger"]["close_time"])


def balance_drops(addr: str) -> Optional[int]:
    try:
        r = client.request(AccountInfo(account=addr, ledger_index="validated")).result
        return int(r["account_data"]["Balance"])
    except Exception:
        return None


def ledger_entry(index: str) -> dict[str, Any]:
    return client.request(GenericRequest(method="ledger_entry", index=index, ledger_index="validated")).result["node"]


def created_node_id(meta: dict[str, Any], ledger_entry_type: str) -> Optional[str]:
    for n in meta.get("AffectedNodes", []):
        c = n.get("CreatedNode")
        if c and c.get("LedgerEntryType") == ledger_entry_type:
            return c["LedgerIndex"]
    return None


def record(step: str, code: str, tx_hash: Optional[str], extra: Optional[dict[str, Any]] = None) -> None:
    row = {"step": step, "result": code, "hash": tx_hash, "explorer": (EXPLORER + tx_hash) if tx_hash else None}
    if extra:
        row.update(extra)
    LOG.append(row)
    LOG_PATH.write_text(json.dumps(LOG, indent=2))
    print(f"  -> {code}  hash={tx_hash}")
    if tx_hash:
        print(f"     {EXPLORER}{tx_hash}")


def submit(step: str, tx: Transaction, wallet: Wallet) -> Optional[dict[str, Any]]:
    """Sign+submit+wait. Prints result and returns the validated tx result (with meta) or None."""
    print(f"\n[{step}] {tx.transaction_type.value} from {wallet.address}")
    try:
        resp = submit_and_wait(tx, client, wallet)
    except Exception as e:  # tem/tef/tel rejections or timeouts surface here
        record(step, f"EXCEPTION: {e}", None)
        return None
    res = resp.result
    code = res.get("meta", {}).get("TransactionResult", res.get("engine_result", "?"))
    record(step, code, res.get("hash"))
    return res if code == "tesSUCCESS" else None


def wait_validated(tx_hash: str, timeout: int = 60) -> dict[str, Any]:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = client.request(Tx(transaction=tx_hash)).result
            if r.get("validated"):
                return r
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError(f"tx {tx_hash} not validated in {timeout}s")


def wait_for_ledger_time(target: int, label: str) -> None:
    while True:
        t = ledger_close_time()
        if t >= target:
            print(f"  ledger close_time {t} >= {target}: {label}")
            return
        print(f"  waiting for {label}: ledger time {t}, need {target} ({target - t}s)")
        time.sleep(min(10, max(2, target - t)))


def ceil_drops(number_str: str) -> int:
    """rippled Number fields come back as decimal strings; the borrower pays rounded UP."""
    return math.ceil(float(number_str))


# ---------------------------------------------------------------- step 1: wallets
def load_wallets() -> dict[str, Wallet]:
    names = ["depositor", "broker", "borrower"]
    if SECRETS.exists():
        seeds = json.loads(SECRETS.read_text())
        wallets = {n: Wallet.from_seed(seeds[n]) for n in names}
        print(f"[1] loaded wallets from {SECRETS}")
    else:
        wallets = {n: Wallet.create() for n in names}
        SECRETS.parent.mkdir(parents=True, exist_ok=True)
        SECRETS.write_text(json.dumps({n: w.seed for n, w in wallets.items()}, indent=2))
        os.chmod(SECRETS, stat.S_IRUSR | stat.S_IWUSR)
        print(f"[1] created new wallets, seeds written to {SECRETS}")
    targets = {"depositor": DEPOSIT_XRP + 20, "broker": COVER_XRP + 20, "borrower": 20}
    for n, w in wallets.items():
        for _ in range(4):
            b = balance_drops(w.address)
            if b is not None and b >= int(xrp_to_drops(targets[n])):
                break
            print(f"  funding {n} {w.address} via faucet (balance {drops_to_xrp(str(b or 0))} XRP)")
            generate_faucet_wallet(client, wallet=w, faucet_host=FAUCET_HOST)
            time.sleep(2)
        b = balance_drops(w.address)
        print(f"  {n:9s} {w.address}  {drops_to_xrp(str(b))} XRP")
    return wallets


def print_balances(wallets: dict[str, Wallet], title: str) -> None:
    print(f"\n{title}")
    for n, w in wallets.items():
        print(f"  {n:9s} {w.address}  {drops_to_xrp(str(balance_drops(w.address)))} XRP")


# ---------------------------------------------------------------- main
def main() -> None:
    do_withdraw = "--withdraw" in sys.argv
    wallets = load_wallets()
    depositor, broker, borrower = wallets["depositor"], wallets["broker"], wallets["borrower"]
    print_balances(wallets, "Starting balances")

    # ---- step 2: VaultCreate (close-ended; the broker owns the vault, per spec they must be the same account)
    sub_date = ledger_close_time() + SUBSCRIPTION_SECS
    red_date = sub_date + INVESTMENT_SECS
    vault_tx = VaultCreate(
        account=broker.address,
        asset=XRP(),
        withdrawal_policy=WithdrawalPolicy.VAULT_STRATEGY_FIRST_COME_FIRST_SERVE,
        vault_kind=VaultKind.CLOSED,
        subscription_date=sub_date,
        redemption_date=red_date,
        data="303031",  # "001"
    )
    print(f"\n  SubscriptionDate={sub_date} RedemptionDate={red_date} (ripple epoch; now {now_ripple()})")
    res = submit("2 VaultCreate", vault_tx, broker)
    if not res:
        sys.exit("VaultCreate failed, stopping")
    vault_id = created_node_id(res["meta"], "Vault")
    vault = ledger_entry(vault_id)
    LOG[-1]["vault_id"] = vault_id
    LOG[-1]["share_mpt_id"] = vault.get("ShareMPTID")
    print(f"  VaultID      = {vault_id}")
    print(f"  ShareMPTID   = {vault.get('ShareMPTID')}")
    print(f"  pseudo acct  = {vault.get('Account')}  Flags={vault.get('Flags')} VaultKind={vault.get('VaultKind')}")

    # ---- step 3: VaultDeposit
    res = submit("3 VaultDeposit", VaultDeposit(account=depositor.address, vault_id=vault_id,
                                                amount=xrp_to_drops(DEPOSIT_XRP)), depositor)
    vault = ledger_entry(vault_id)
    print(f"  Vault AssetsTotal={vault.get('AssetsTotal')} AssetsAvailable={vault.get('AssetsAvailable')} "
          f"SharesTotal={vault.get('SharesTotal')}")

    # ---- step 4: LoanBrokerSet + cover
    res = submit("4a LoanBrokerSet", LoanBrokerSet(
        account=broker.address,
        vault_id=vault_id,
        management_fee_rate=MANAGEMENT_FEE_RATE,
        debt_maximum=DEBT_MAXIMUM_DROPS,
        cover_rate_minimum=COVER_RATE_MINIMUM,
        cover_rate_liquidation=COVER_RATE_LIQUIDATION,
        data="303031",
    ), broker)
    if not res:
        sys.exit("LoanBrokerSet failed, stopping")
    broker_id = created_node_id(res["meta"], "LoanBroker")
    LOG[-1]["loan_broker_id"] = broker_id
    print(f"  LoanBrokerID = {broker_id}")

    res = submit("4b LoanBrokerCoverDeposit", LoanBrokerCoverDeposit(
        account=broker.address, loan_broker_id=broker_id, amount=xrp_to_drops(COVER_XRP)), broker)
    lb = ledger_entry(broker_id)
    print(f"  LoanBroker: Owner={lb.get('Owner')} VaultID={lb.get('VaultID')} CoverAvailable={lb.get('CoverAvailable')} "
          f"DebtTotal={lb.get('DebtTotal')} DebtMaximum={lb.get('DebtMaximum')} CoverRateMinimum={lb.get('CoverRateMinimum')}")

    # ---- step 5: LoanSet (two-party). Borrower is Account, broker owner is Counterparty.
    print("\n[5] waiting for the vault's Investment phase (LoanSet is rejected during Subscription)")
    wait_for_ledger_time(sub_date + 1, "Investment phase")
    loan_tx = LoanSet(
        account=borrower.address,
        loan_broker_id=broker_id,
        counterparty=broker.address,
        principal_requested=xrp_to_drops(PRINCIPAL_XRP),
        payment_total=PAYMENT_TOTAL,
        payment_interval=PAYMENT_INTERVAL,
        grace_period=PAYMENT_INTERVAL,
        interest_rate=INTEREST_RATE,
        loan_origination_fee=xrp_to_drops(0.1),
        loan_service_fee=xrp_to_drops(0.01),
        close_payment_fee=xrp_to_drops(0.01),
        fee=TX_FEE_DROPS,
    )
    loan_tx = autofill(loan_tx, client)
    borrower_signed = sign(loan_tx, borrower)                       # 1st signature: Account (borrower)
    counter = sign_loan_set_by_counterparty(broker, borrower_signed)  # 2nd: CounterpartySignature (broker owner)
    print(f"\n[5 LoanSet] borrower-signed, broker counter-signed; submitting blob (hash {counter.hash})")
    sub: dict[str, Any] = {}
    try:
        sub = client.request(GenericRequest(method="submit", tx_blob=counter.tx_blob)).result
        print(f"  submit: {sub.get('engine_result')} {sub.get('engine_result_message')}")
        res = wait_validated(counter.hash)
        code = res["meta"]["TransactionResult"]
    except Exception as e:
        code, res = f"EXCEPTION: {e}", None
    record("5 LoanSet", code, counter.hash, {"submit_engine_result": sub.get("engine_result")})
    loan_id = created_node_id(res["meta"], "Loan") if res and code == "tesSUCCESS" else None
    if not loan_id:
        print_balances(wallets, "Balances (loan not created)")
        sys.exit("LoanSet failed, stopping")
    LOG[-1]["loan_id"] = loan_id
    loan = ledger_entry(loan_id)
    print(f"  LoanID = {loan_id}")
    print("  Loan: " + json.dumps({k: loan.get(k) for k in [
        "Borrower", "PrincipalOutstanding", "TotalValueOutstanding", "PeriodicPayment", "PaymentRemaining",
        "NextPaymentDueDate", "StartDate", "PaymentInterval", "InterestRate", "LoanServiceFee", "ClosePaymentFee",
        "LoanScale", "Flags"]}))
    print_balances(wallets, "Balances after LoanSet")

    # ---- step 6: LoanPay one installment, then full payoff
    periodic = ceil_drops(loan["PeriodicPayment"])
    service_fee = int(loan.get("LoanServiceFee", "0"))
    inst_amount = periodic + service_fee
    print(f"\n[6a] installment = ceil(PeriodicPayment {loan['PeriodicPayment']}) + LoanServiceFee {service_fee} = {inst_amount} drops")
    res = submit("6a LoanPay installment", LoanPay(account=borrower.address, loan_id=loan_id, amount=str(inst_amount)), borrower)
    loan = ledger_entry(loan_id)
    print(f"  Loan after: PrincipalOutstanding={loan.get('PrincipalOutstanding')} TotalValueOutstanding={loan.get('TotalValueOutstanding')} "
          f"PaymentRemaining={loan.get('PaymentRemaining')} NextPaymentDueDate={loan.get('NextPaymentDueDate')}")

    if int(loan.get("PaymentRemaining", 0)) > 1:
        # full early repayment: principal + accrued interest + close fee. Paying the remaining
        # TotalValueOutstanding (full interest) + ClosePaymentFee is always >= the requirement; excess is ignored.
        close_fee = int(loan.get("ClosePaymentFee", "0"))
        full_amount = ceil_drops(loan["TotalValueOutstanding"]) + close_fee + service_fee
        print(f"\n[6b] full payoff = ceil(TotalValueOutstanding) + ClosePaymentFee + LoanServiceFee = {full_amount} drops")
        res = submit("6b LoanPay full payoff (tfLoanFullPayment)", LoanPay(
            account=borrower.address, loan_id=loan_id, amount=str(full_amount),
            flags=LoanPayFlag.TF_LOAN_FULL_PAYMENT), borrower)
        try:
            loan = ledger_entry(loan_id)
            print(f"  Loan after: PrincipalOutstanding={loan.get('PrincipalOutstanding')} PaymentRemaining={loan.get('PaymentRemaining')} Flags={loan.get('Flags')}")
        except Exception as e:
            print(f"  Loan object no longer readable ({e}) - may have been deleted")
    else:
        print("\n[6b] skipped full payoff: only one payment remains (spec: tfLoanFullPayment -> tecKILLED)")

    # A paid-off Loan object stays on the ledger (reserve on the borrower, OwnerCount on the broker) until deleted.
    if int(loan.get("PaymentRemaining", 0)) == 0:
        res = submit("6c LoanDelete (broker owner)", LoanDelete(account=broker.address, loan_id=loan_id), broker)
    else:
        print("\n[6c] skipped LoanDelete: loan still has payments remaining")

    # ---- step 7: final state
    print_balances(wallets, "\n[7] Final balances")
    vault = ledger_entry(vault_id)
    lb = ledger_entry(broker_id)
    print("  Vault:      " + json.dumps({k: vault.get(k) for k in ["AssetsTotal", "AssetsAvailable", "SharesTotal", "LossUnrealized", "VaultKind", "SubscriptionDate", "RedemptionDate"]}))
    print("  LoanBroker: " + json.dumps({k: lb.get(k) for k in ["DebtTotal", "CoverAvailable", "OwnerCount", "DebtMaximum"]}))
    LOG.append({"step": "7 final", "vault": vault, "loan_broker": lb})
    LOG_PATH.write_text(json.dumps(LOG, indent=2))

    # ---- step 8: optional VaultWithdraw after RedemptionDate
    if do_withdraw:
        print("\n[8] waiting for Redemption phase so the depositor can withdraw")
        wait_for_ledger_time(red_date + 1, "Redemption phase")
        res = submit("8 VaultWithdraw", VaultWithdraw(account=depositor.address, vault_id=vault_id,
                                                      amount=xrp_to_drops(DEPOSIT_XRP)), depositor)
        vault = ledger_entry(vault_id)
        print(f"  Vault after: AssetsTotal={vault.get('AssetsTotal')} AssetsAvailable={vault.get('AssetsAvailable')} SharesTotal={vault.get('SharesTotal')}")
        print_balances(wallets, "Balances after withdraw")
    else:
        print("\n[8] skipped VaultWithdraw (re-run with --withdraw to wait for RedemptionDate and redeem shares)")

    print(f"\nlog: {LOG_PATH}")


if __name__ == "__main__":
    main()
