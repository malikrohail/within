#!/usr/bin/env python
"""Experiment 010: XLS-65 vault + XLS-66 loan denominated in a trust-line token (IOU) on devnet.

Run:  experiments/.venv/bin/python experiments/010-iou-vault/run.py [--skip-noline] [--no-withdraw]

Devnet has no RLUSD, so a self-issued IOU "USD" plays the stablecoin. Steps (each prints result code,
hash and https://devnet.xrpl.org/transactions/<hash>):
  1. wallets: issuer, depositor, broker (== vault owner), borrower, borrower2 (probe, no trust line)
  2a. PROBE VaultCreate(IOU) before the issuer sets DefaultRipple (fail_hard, expect terNO_RIPPLE)
  2b. issuer AccountSet asfDefaultRipple
  3. TrustSet depositor/broker/borrower -> issuer; issuer pays 1000 / 100 / 50 USD
  4. VaultCreate Asset={currency,issuer}, close-ended (VaultKind 1, Subscription +120 s, Redemption +900 s)
  5. VaultDeposit 500 USD; LoanBrokerSet; LoanBrokerCoverDeposit 50 USD
  6. after SubscriptionDate: LoanSet 100 USD (borrower signs, broker counter-signs), read Loan
  7. LoanPay one installment, LoanPay tfLoanFullPayment, LoanDelete
  7p. PROBE: LoanSet 1 USD to borrower2 who has NO trust line (does the ledger create it?), repay, delete
  8. after RedemptionDate: VaultWithdraw 500 USD by the depositor, then the remainder

Seeds live in experiments/.secrets/010.json (mode 600) and are never printed.
A machine-readable log of every tx is written to run-log.json next to this file.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import time
from decimal import ROUND_UP, Decimal
from pathlib import Path
from typing import Any, Optional

from xrpl.clients import JsonRpcClient
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.currencies import IssuedCurrency
from xrpl.models.requests import AccountInfo, AccountLines, GenericRequest, Ledger, Tx
from xrpl.models.transactions import (
    AccountSet,
    AccountSetAsfFlag,
    LoanBrokerCoverDeposit,
    LoanBrokerSet,
    LoanDelete,
    LoanPay,
    LoanSet,
    Payment,
    Transaction,
    TrustSet,
    VaultCreate,
    VaultDeposit,
    VaultWithdraw,
)
from xrpl.models.transactions.loan_pay import LoanPayFlag
from xrpl.models.transactions.vault_create import VaultKind, WithdrawalPolicy
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
SECRETS = HERE.parent / ".secrets" / "010.json"
LOG_PATH = HERE / "run-log.json"

CURRENCY = "USD"            # 3-letter test code; the issuer is one of our faucet wallets
TRUST_LIMIT = "1000000"     # generous trust-line limit for every holder
ISSUE_DEPOSITOR = "1000"
ISSUE_BROKER = "100"        # broker needs USD for the cover deposit (and to receive fees)
ISSUE_BORROWER = "50"       # so the borrower can pay interest + fees
DEPOSIT = "500"             # depositor -> vault
COVER = "50"                # broker first-loss capital
PRINCIPAL = "100"           # main loan
PROBE_PRINCIPAL = "1"       # no-trust-line probe loan
DEBT_MAXIMUM = "200"        # Number, in asset units (not drops)
SUBSCRIPTION_SECS = 120
INVESTMENT_SECS = 900       # min 180 (kMinInvestmentPeriod)
PAYMENT_TOTAL = 3
PAYMENT_INTERVAL = 60
INTEREST_RATE = 10_000      # 1/10 bp => 10 % APR
MANAGEMENT_FEE_RATE = 1_000
COVER_RATE_MINIMUM = 10_000
COVER_RATE_LIQUIDATION = 50_000
ORIGINATION_FEE = "0.1"     # distinct values so RESULT.md can tell the fees apart
SERVICE_FEE = "0.01"
CLOSE_FEE = "0.02"
TX_FEE_DROPS = "200"
IOU_PLACES = Decimal("0.000001")  # VaultCreate Scale default 6 for trust-line tokens

client = JsonRpcClient(JSON_RPC)
LOG: list[dict[str, Any]] = []


# ---------------------------------------------------------------- helpers
def now_ripple() -> int:
    return int(time.time()) - RIPPLE_EPOCH


def ledger_close_time() -> int:
    return int(client.request(Ledger(ledger_index="validated")).result["ledger"]["close_time"])


def balance_drops(addr: str) -> Optional[int]:
    try:
        return int(client.request(AccountInfo(account=addr, ledger_index="validated")).result["account_data"]["Balance"])
    except Exception:
        return None


def iou_lines(addr: str, issuer: str) -> list[dict[str, Any]]:
    try:
        r = client.request(AccountLines(account=addr, peer=issuer, ledger_index="validated")).result
        return [l for l in r.get("lines", []) if l.get("currency") == CURRENCY]
    except Exception:
        return []


def iou_balance(addr: str, issuer: str) -> Optional[str]:
    lines = iou_lines(addr, issuer)
    return lines[0]["balance"] if lines else None


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
    LOG_PATH.write_text(json.dumps(LOG, indent=2, default=str))
    print(f"  -> {code}  hash={tx_hash}")
    if tx_hash:
        print(f"     {EXPLORER}{tx_hash}")


def submit(step: str, tx: Transaction, wallet: Wallet) -> Optional[dict[str, Any]]:
    """Sign+submit+wait. Prints result and returns the validated tx result (with meta) or None."""
    print(f"\n[{step}] {tx.transaction_type.value} from {wallet.address}")
    try:
        resp = submit_and_wait(tx, client, wallet)
    except Exception as e:  # tem/tef/tel/ter rejections or timeouts surface here
        record(step, f"EXCEPTION: {e}", None)
        return None
    res = resp.result
    code = res.get("meta", {}).get("TransactionResult", res.get("engine_result", "?"))
    record(step, code, res.get("hash"))
    return res if code == "tesSUCCESS" else None


def submit_probe(step: str, tx: Transaction, wallet: Wallet) -> tuple[str, Optional[dict[str, Any]]]:
    """Submit with fail_hard so a ter* result is NOT held and retried by the node later.
    Returns (engine_result or final result, validated tx or None)."""
    print(f"\n[{step}] PROBE {tx.transaction_type.value} from {wallet.address} (fail_hard)")
    try:
        signed = sign(autofill(tx, client), wallet)
        sub = client.request(GenericRequest(method="submit", tx_blob=signed.blob(), fail_hard=True)).result
        er = sub.get("engine_result", "?")
        print(f"  submit: {er} {sub.get('engine_result_message')}")
        if er == "tesSUCCESS" or er.startswith("tec"):
            res = wait_validated(sub["tx_json"]["hash"])
            code = res["meta"]["TransactionResult"]
            record(step, code, res["hash"], {"submit_engine_result": er})
            return code, res
        record(step, er, None, {"engine_result_message": sub.get("engine_result_message")})
        return er, None
    except Exception as e:
        record(step, f"EXCEPTION: {e}", None)
        return f"EXCEPTION: {e}", None


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


def ceil_iou(number_str: str) -> str:
    """rippled Number fields come back as decimal strings; round UP to the vault precision (6 places)."""
    d = Decimal(number_str).quantize(IOU_PLACES, rounding=ROUND_UP)
    return format(d.normalize(), "f")


def usd(issuer: str, value: str) -> IssuedCurrencyAmount:
    return IssuedCurrencyAmount(currency=CURRENCY, issuer=issuer, value=value)


def loan_view(loan: dict[str, Any]) -> dict[str, Any]:
    return {k: loan.get(k) for k in [
        "Borrower", "PrincipalOutstanding", "TotalValueOutstanding", "PeriodicPayment", "PaymentRemaining",
        "NextPaymentDueDate", "StartDate", "PaymentInterval", "InterestRate", "LoanOriginationFee", "LoanServiceFee",
        "ClosePaymentFee", "LoanScale", "Flags"]}


# ---------------------------------------------------------------- step 1: wallets
NAMES = ["issuer", "depositor", "broker", "borrower", "borrower2"]


def load_wallets() -> dict[str, Wallet]:
    if SECRETS.exists():
        seeds = json.loads(SECRETS.read_text())
        wallets = {n: Wallet.from_seed(seeds[n]) for n in NAMES}
        print(f"[1] loaded wallets from {SECRETS}")
    else:
        wallets = {n: Wallet.create() for n in NAMES}
        SECRETS.parent.mkdir(parents=True, exist_ok=True)
        SECRETS.write_text(json.dumps({n: w.seed for n, w in wallets.items()}, indent=2))
        os.chmod(SECRETS, stat.S_IRUSR | stat.S_IWUSR)
        print(f"[1] created new wallets, seeds written to {SECRETS} (mode 600)")
    for n, w in wallets.items():
        for _ in range(4):
            b = balance_drops(w.address)
            if b is not None and b >= int(xrp_to_drops(20)):
                break
            print(f"  funding {n} {w.address} via faucet (balance {drops_to_xrp(str(b or 0))} XRP)")
            generate_faucet_wallet(client, wallet=w, faucet_host=FAUCET_HOST)
            time.sleep(2)
        print(f"  {n:9s} {w.address}  {drops_to_xrp(str(balance_drops(w.address)))} XRP")
    return wallets


def print_balances(wallets: dict[str, Wallet], issuer: str, title: str) -> None:
    print(f"\n{title}")
    for n, w in wallets.items():
        print(f"  {n:9s} {w.address}  {drops_to_xrp(str(balance_drops(w.address)))} XRP  {iou_balance(w.address, issuer)} {CURRENCY}")


# ---------------------------------------------------------------- loan cycle (used twice)
def run_loan(label: str, borrower: Wallet, broker: Wallet, issuer: str, broker_id: str, vault_id: str,
             principal: str, full_cycle: bool = True) -> Optional[str]:
    """LoanSet (two signatures) -> LoanPay installment -> LoanPay full -> LoanDelete. Returns loan_id or None."""
    loan_tx = LoanSet(
        account=borrower.address,
        loan_broker_id=broker_id,
        counterparty=broker.address,
        principal_requested=principal,           # Number: plain decimal string in asset units
        payment_total=PAYMENT_TOTAL,
        payment_interval=PAYMENT_INTERVAL,
        grace_period=PAYMENT_INTERVAL,
        interest_rate=INTEREST_RATE,
        loan_origination_fee=ORIGINATION_FEE,    # Number, asset units
        loan_service_fee=SERVICE_FEE,
        close_payment_fee=CLOSE_FEE,
        fee=TX_FEE_DROPS,
    )
    loan_tx = autofill(loan_tx, client)
    borrower_signed = sign(loan_tx, borrower)
    counter = sign_loan_set_by_counterparty(broker, borrower_signed)
    print(f"\n[{label} LoanSet] {principal} {CURRENCY}; borrower-signed, broker counter-signed (hash {counter.hash})")
    print(f"  borrower {CURRENCY} before: {iou_balance(borrower.address, issuer)}  lines={len(iou_lines(borrower.address, issuer))}")
    sub: dict[str, Any] = {}
    try:
        sub = client.request(GenericRequest(method="submit", tx_blob=counter.tx_blob)).result
        print(f"  submit: {sub.get('engine_result')} {sub.get('engine_result_message')}")
        er = sub.get("engine_result", "?")
        if er == "tesSUCCESS" or er.startswith("tec"):
            res = wait_validated(counter.hash)
            code = res["meta"]["TransactionResult"]
        else:
            code, res = er, None
    except Exception as e:
        code, res = f"EXCEPTION: {e}", None
    record(f"{label} LoanSet", code, counter.hash if res else None,
           {"submit_engine_result": sub.get("engine_result"), "engine_result_message": sub.get("engine_result_message")})
    loan_id = created_node_id(res["meta"], "Loan") if res and code == "tesSUCCESS" else None
    if not loan_id:
        print(f"  LoanSet failed ({code})")
        return None
    LOG[-1]["loan_id"] = loan_id
    loan = ledger_entry(loan_id)
    lines = iou_lines(borrower.address, issuer)
    print(f"  LoanID = {loan_id}")
    print("  Loan: " + json.dumps(loan_view(loan)))
    print(f"  borrower {CURRENCY} after: {iou_balance(borrower.address, issuer)}  trust line: {json.dumps(lines)}")
    LOG[-1]["loan"] = loan_view(loan)
    LOG[-1]["borrower_lines_after"] = lines
    if not full_cycle:
        return loan_id

    # installment: ceil(PeriodicPayment) + LoanServiceFee, in asset units
    periodic = Decimal(ceil_iou(loan["PeriodicPayment"]))
    inst = format((periodic + Decimal(loan.get("LoanServiceFee", "0"))).normalize(), "f")
    print(f"\n[{label}a] installment = ceil6(PeriodicPayment {loan['PeriodicPayment']}) + LoanServiceFee = {inst} {CURRENCY}")
    submit(f"{label}a LoanPay installment", LoanPay(account=borrower.address, loan_id=loan_id, amount=usd(issuer, inst)), borrower)
    loan = ledger_entry(loan_id)
    print("  Loan after: " + json.dumps(loan_view(loan)))
    LOG[-1]["loan_after"] = loan_view(loan)

    if int(loan.get("PaymentRemaining", 0)) > 1:
        full = Decimal(ceil_iou(loan["TotalValueOutstanding"])) + Decimal(loan.get("ClosePaymentFee", "0")) + Decimal(loan.get("LoanServiceFee", "0"))
        full_s = format(full.normalize(), "f")
        print(f"\n[{label}b] full payoff = ceil6(TotalValueOutstanding) + ClosePaymentFee + LoanServiceFee = {full_s} {CURRENCY}")
        submit(f"{label}b LoanPay full payoff (tfLoanFullPayment)", LoanPay(
            account=borrower.address, loan_id=loan_id, amount=usd(issuer, full_s),
            flags=LoanPayFlag.TF_LOAN_FULL_PAYMENT), borrower)
        loan = ledger_entry(loan_id)
        print("  Loan after: " + json.dumps(loan_view(loan)))
        LOG[-1]["loan_after"] = loan_view(loan)
    if int(loan.get("PaymentRemaining", 0)) == 0:
        submit(f"{label}c LoanDelete (broker owner)", LoanDelete(account=broker.address, loan_id=loan_id), broker)
    else:
        print(f"\n[{label}c] skipped LoanDelete: PaymentRemaining={loan.get('PaymentRemaining')}")
    print(f"  borrower {CURRENCY}: {iou_balance(borrower.address, issuer)}   broker {CURRENCY}: {iou_balance(broker.address, issuer)}")
    return loan_id


# ---------------------------------------------------------------- main
def main() -> None:
    skip_noline = "--skip-noline" in sys.argv
    do_withdraw = "--no-withdraw" not in sys.argv
    wallets = load_wallets()
    issuer_w, depositor, broker, borrower, borrower2 = (wallets[n] for n in NAMES)
    issuer = issuer_w.address
    asset = IssuedCurrency(currency=CURRENCY, issuer=issuer)
    print(f"  asset = {CURRENCY}.{issuer}")

    # ---- step 2a: probe VaultCreate before DefaultRipple (only meaningful on a fresh issuer)
    issuer_flags = client.request(AccountInfo(account=issuer, ledger_index="validated")).result["account_data"]["Flags"]
    default_ripple_on = bool(issuer_flags & 0x00800000)  # lsfDefaultRipple
    print(f"\n[2] issuer Flags={issuer_flags:#x} DefaultRipple={'on' if default_ripple_on else 'off'}")
    sub_date = ledger_close_time() + SUBSCRIPTION_SECS
    red_date = sub_date + INVESTMENT_SECS

    def vault_create_tx() -> VaultCreate:
        return VaultCreate(
            account=broker.address, asset=asset,
            withdrawal_policy=WithdrawalPolicy.VAULT_STRATEGY_FIRST_COME_FIRST_SERVE,
            vault_kind=VaultKind.CLOSED, subscription_date=sub_date, redemption_date=red_date,
            data="303130",  # "010"
        )

    vault_res: Optional[dict[str, Any]] = None
    if not default_ripple_on:
        code, res = submit_probe("2a VaultCreate before DefaultRipple", vault_create_tx(), broker)
        if code == "tesSUCCESS":
            vault_res = res  # surprise: adopt the vault
        # ---- step 2b: AccountSet DefaultRipple
        submit("2b AccountSet asfDefaultRipple (issuer)", AccountSet(account=issuer, set_flag=AccountSetAsfFlag.ASF_DEFAULT_RIPPLE), issuer_w)
    else:
        print("  DefaultRipple already on (re-run); skipping probe 2a and AccountSet 2b")

    # ---- step 3: trust lines + issuance (skip what already exists)
    for name, w, amount in [("depositor", depositor, ISSUE_DEPOSITOR), ("broker", broker, ISSUE_BROKER), ("borrower", borrower, ISSUE_BORROWER)]:
        if not iou_lines(w.address, issuer):
            submit(f"3 TrustSet {name}", TrustSet(account=w.address, limit_amount=usd(issuer, TRUST_LIMIT)), w)
        bal = Decimal(iou_balance(w.address, issuer) or "0")
        if bal < Decimal(amount):
            top = format((Decimal(amount) - bal).normalize(), "f")
            submit(f"3 Payment issuer -> {name} {top} {CURRENCY}", Payment(account=issuer, destination=w.address, amount=usd(issuer, top)), issuer_w)
    print_balances(wallets, issuer, "Balances after issuance")

    # ---- step 4: VaultCreate (IOU, close-ended)
    if vault_res is None:
        sub_date = ledger_close_time() + SUBSCRIPTION_SECS
        red_date = sub_date + INVESTMENT_SECS
        print(f"\n  SubscriptionDate={sub_date} RedemptionDate={red_date} (ripple epoch; now {now_ripple()})")
        vault_res = submit("4 VaultCreate (IOU)", vault_create_tx(), broker)
    if not vault_res:
        sys.exit("VaultCreate failed, stopping")
    vault_id = created_node_id(vault_res["meta"], "Vault")
    vault = ledger_entry(vault_id)
    sub_date, red_date = int(vault["SubscriptionDate"]), int(vault["RedemptionDate"])
    pseudo = vault.get("Account")
    LOG[-1].update({"vault_id": vault_id, "share_mpt_id": vault.get("ShareMPTID"), "vault": vault,
                    "pseudo_lines": iou_lines(pseudo, issuer)})
    print(f"  VaultID      = {vault_id}")
    print(f"  ShareMPTID   = {vault.get('ShareMPTID')}   Scale={vault.get('Scale')}  Asset={vault.get('Asset')}")
    print(f"  pseudo acct  = {pseudo}  Flags={vault.get('Flags')} VaultKind={vault.get('VaultKind')}")
    print(f"  pseudo acct trust lines to issuer (created by VaultCreate?): {json.dumps(iou_lines(pseudo, issuer))}")
    created_types = [n["CreatedNode"]["LedgerEntryType"] for n in vault_res["meta"]["AffectedNodes"] if "CreatedNode" in n]
    print(f"  CreatedNodes in VaultCreate meta: {created_types}")
    LOG[-1]["created_nodes"] = created_types

    # ---- step 5: VaultDeposit, LoanBrokerSet, CoverDeposit
    submit("5a VaultDeposit", VaultDeposit(account=depositor.address, vault_id=vault_id, amount=usd(issuer, DEPOSIT)), depositor)
    vault = ledger_entry(vault_id)
    print(f"  Vault AssetsTotal={vault.get('AssetsTotal')} AssetsAvailable={vault.get('AssetsAvailable')}")
    print(f"  pseudo acct trust line after deposit: {json.dumps(iou_lines(pseudo, issuer))}")
    print(f"  depositor {CURRENCY}: {iou_balance(depositor.address, issuer)}")
    LOG[-1]["pseudo_lines_after_deposit"] = iou_lines(pseudo, issuer)
    try:
        mpt = client.request(GenericRequest(method="ledger_entry", mpt_issuance=vault["ShareMPTID"], ledger_index="validated")).result["node"]
        print(f"  share MPTokenIssuance: OutstandingAmount={mpt.get('OutstandingAmount')} AssetScale={mpt.get('AssetScale')} Flags={mpt.get('Flags')}")
        LOG[-1]["share_mpt"] = {k: mpt.get(k) for k in ["OutstandingAmount", "AssetScale", "Flags", "Issuer"]}
    except Exception as e:
        print(f"  (could not read share MPT: {e})")

    res = submit("5b LoanBrokerSet", LoanBrokerSet(
        account=broker.address, vault_id=vault_id, management_fee_rate=MANAGEMENT_FEE_RATE,
        debt_maximum=DEBT_MAXIMUM, cover_rate_minimum=COVER_RATE_MINIMUM,
        cover_rate_liquidation=COVER_RATE_LIQUIDATION, data="303130"), broker)
    if not res:
        sys.exit("LoanBrokerSet failed, stopping")
    broker_id = created_node_id(res["meta"], "LoanBroker")
    LOG[-1]["loan_broker_id"] = broker_id
    print(f"  LoanBrokerID = {broker_id}")

    submit("5c LoanBrokerCoverDeposit", LoanBrokerCoverDeposit(account=broker.address, loan_broker_id=broker_id, amount=usd(issuer, COVER)), broker)
    lb = ledger_entry(broker_id)
    lb_pseudo = lb.get("Account")
    print(f"  LoanBroker: Owner={lb.get('Owner')} Account={lb_pseudo} CoverAvailable={lb.get('CoverAvailable')} "
          f"DebtTotal={lb.get('DebtTotal')} DebtMaximum={lb.get('DebtMaximum')}")
    print(f"  broker pseudo acct trust line: {json.dumps(iou_lines(lb_pseudo, issuer))}")
    LOG[-1]["loan_broker"] = lb
    LOG[-1]["broker_pseudo_lines"] = iou_lines(lb_pseudo, issuer)

    # ---- step 6/7: main loan
    print("\n[6] waiting for the vault's Investment phase (LoanSet is tecTOO_SOON during Subscription)")
    wait_for_ledger_time(sub_date + 1, "Investment phase")
    main_loan = run_loan("6", borrower, broker, issuer, broker_id, vault_id, PRINCIPAL)
    print_balances(wallets, issuer, "Balances after main loan cycle")

    # ---- step 7p: probe loan to a borrower with no trust line
    if not skip_noline:
        print(f"\n[7p] PROBE: LoanSet {PROBE_PRINCIPAL} {CURRENCY} to borrower2 {borrower2.address}, which has NO trust line to the issuer")
        run_loan("7p", borrower2, broker, issuer, broker_id, vault_id, PROBE_PRINCIPAL)
    else:
        print("\n[7p] skipped no-trust-line probe")

    # ---- final objects
    vault = ledger_entry(vault_id)
    lb = ledger_entry(broker_id)
    print("\n[7 final] Vault:      " + json.dumps({k: vault.get(k) for k in ["AssetsTotal", "AssetsAvailable", "LossUnrealized", "Scale", "VaultKind", "SubscriptionDate", "RedemptionDate"]}))
    print("          LoanBroker: " + json.dumps({k: lb.get(k) for k in ["DebtTotal", "CoverAvailable", "OwnerCount", "DebtMaximum", "ManagementFeeOutstanding"]}))
    LOG.append({"step": "7 final", "vault": vault, "loan_broker": lb, "main_loan_id": main_loan})
    LOG_PATH.write_text(json.dumps(LOG, indent=2, default=str))
    print_balances(wallets, issuer, "Balances before withdraw")

    # ---- step 8: VaultWithdraw after RedemptionDate
    if do_withdraw:
        print("\n[8] waiting for the Redemption phase so the depositor can withdraw")
        wait_for_ledger_time(red_date + 1, "Redemption phase")
        submit("8a VaultWithdraw deposit", VaultWithdraw(account=depositor.address, vault_id=vault_id, amount=usd(issuer, DEPOSIT)), depositor)
        vault = ledger_entry(vault_id)
        rest = vault.get("AssetsTotal", "0")
        print(f"  Vault after: AssetsTotal={vault.get('AssetsTotal')} AssetsAvailable={vault.get('AssetsAvailable')}")
        if Decimal(rest) > 0:
            submit(f"8b VaultWithdraw remainder {rest}", VaultWithdraw(account=depositor.address, vault_id=vault_id, amount=usd(issuer, rest)), depositor)
            vault = ledger_entry(vault_id)
            print(f"  Vault after: AssetsTotal={vault.get('AssetsTotal')} AssetsAvailable={vault.get('AssetsAvailable')}")
        print_balances(wallets, issuer, "Balances after withdraw")
    else:
        print("\n[8] skipped VaultWithdraw (--no-withdraw)")
    print(f"\nlog: {LOG_PATH}")


if __name__ == "__main__":
    main()
