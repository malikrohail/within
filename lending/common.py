"""Shared devnet helpers for the lending desk (contract: lending/INTERFACES.md §0-§3).

Seeds are read from lending/.env only and are never logged. Never print a Wallet
object: xrpl-py's Wallet repr includes the seed. Use wallet.address.
"""
from __future__ import annotations

import json
import math
import os
import time
from decimal import Decimal
from pathlib import Path

from dotenv import dotenv_values
from xrpl.clients import JsonRpcClient
from xrpl.core import keypairs
from xrpl.core.binarycodec import decode, encode, encode_for_signing
from xrpl.models.requests import AccountObjects, Ledger, LedgerEntry, SubmitOnly, Tx
from xrpl.models.requests.account_objects import AccountObjectType
from xrpl.models.transactions import LoanManage, LoanPay, LoanSet, Transaction
from xrpl.models.transactions.loan_manage import LoanManageFlag
from xrpl.transaction import autofill, sign, sign_loan_set_by_counterparty
from xrpl.wallet import Wallet

# ---- §0 constants -----------------------------------------------------------
DEVNET_URL = "https://s.devnet.rippletest.net:51234/"
RIPPLE_EPOCH = 946684800
PAYMENT_INTERVAL = 90
GRACE_PERIOD = 60
LOAN_SET_FEE = "30"
SUBSCRIPTION_HOURS = 4         # INTERFACES §0 name kept; superseded by SUBSCRIPTION_SECONDS (devnet probe)
# CLOSED vault is two-phase (proven on devnet 2026-10-24): VaultDeposit only before SubscriptionDate
# (after -> tecEXPIRED), LoanSet only after it (before -> tecTOO_SOON). So the window is short.
SUBSCRIPTION_SECONDS = 180
REDEMPTION_HOURS = 8
COVER_DEPOSIT_DROPS = "20000000"
# Rates are 1/100,000 (10000 = 10 %). On default the ledger takes DebtTotal x CoverRateMinimum x CoverRateLiquidation
# from cover: 10 % x 100 % = 10 % of debt (20 -> 14 XRP on a 60 XRP default, devnet A8DCC893).
LOAN_BROKER = dict(management_fee_rate=1000, debt_maximum="0",
                   cover_rate_minimum=10000, cover_rate_liquidation=100000)
SETUP_DEPOSITS = {"depositorA": "20000000", "depositorB": "10000000"}

LENDING_DIR = Path(__file__).resolve().parent
ENV_PATH = LENDING_DIR / ".env"
ACCOUNTS_PATH = LENDING_DIR / "accounts.json"
AUDIT_PATH = LENDING_DIR / "data" / "audit.jsonl"
RAWLOG_PATH = LENDING_DIR / "data" / "rawlog.jsonl"

SEED_VARS = {"broker": "BROKER_SEED", "depositorA": "DEPOSITOR_A_SEED",
             "depositorB": "DEPOSITOR_B_SEED", "borrower": "BORROWER_SEED",
             "customer": "CUSTOMER_SEED"}  # demo.py --income: the x402 customer that pays the borrower

LSF_LOAN_DEFAULT = 0x10000
LSF_LOAN_IMPAIRED = 0x20000
LOAN_LAST_LEDGER_OFFSET = 60
# Wall-clock backstop only: past the LOAN_LAST_LEDGER_OFFSET horizon (60 ledgers, ~3-4 min on devnet), so the
# ledger_index > LastLedgerSequence branch in wait_for_tx is what ends a wait for a tx that will never validate.
WAIT_TIMEOUT_S = 300


# ---- time -------------------------------------------------------------------
def to_ripple(unix_s: int) -> int:
    return int(unix_s) - RIPPLE_EPOCH


def from_ripple(ripple_s: int) -> int:
    return int(ripple_s) + RIPPLE_EPOCH


# ---- client / accounts / wallets -------------------------------------------
_client: JsonRpcClient | None = None


def client() -> JsonRpcClient:
    global _client
    if _client is None:
        _client = JsonRpcClient(DEVNET_URL)
    assert _client.url == DEVNET_URL, "devnet only"
    return _client


def load_accounts() -> dict:
    return json.loads(ACCOUNTS_PATH.read_text())


def write_accounts(data: dict) -> None:
    text = json.dumps(data, indent=2) + "\n"
    for seed in read_env().values():
        if seed and seed in text:
            raise RuntimeError("refusing to write a seed into accounts.json")
    ACCOUNTS_PATH.write_text(text)


def read_env() -> dict:
    return dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}


def wallet(name: str) -> Wallet:
    seed = read_env().get(SEED_VARS[name])
    if not seed:
        raise KeyError(f"{SEED_VARS[name]} missing from lending/.env (run setup.py)")
    return Wallet.from_seed(seed)


# ---- submit -----------------------------------------------------------------
def _rpc(req) -> dict:
    resp = client().request(req)
    return resp.result


def current_ledger_index() -> int:
    return int(_rpc(Ledger(ledger_index="validated"))["ledger_index"])


def _created(meta: dict) -> dict:
    out: dict = {}
    for node in meta.get("AffectedNodes", []) if isinstance(meta, dict) else []:
        c = node.get("CreatedNode")
        if c:
            out[c["LedgerEntryType"]] = c["LedgerIndex"]
    return out


def wait_for_tx(tx_hash: str, last_ledger: int | None, timeout: int = WAIT_TIMEOUT_S) -> dict:
    """Poll tx until validated, past last_ledger, or timeout. Returns the §3 submit shape."""
    deadline = time.time() + timeout
    while True:
        res = _rpc(Tx(transaction=tx_hash))
        if res.get("validated"):
            meta = res.get("meta", {})
            return {"hash": tx_hash, "engineResult": meta.get("TransactionResult"),
                    "validated": True, "ledgerIndex": res.get("ledger_index"),
                    "created": _created(meta)}
        if last_ledger and current_ledger_index() > last_ledger:  # expired: past LastLedgerSequence
            return {"hash": tx_hash, "engineResult": res.get("error") or "not_validated",
                    "validated": False, "ledgerIndex": None, "created": {}}
        if time.time() > deadline:  # wall-clock backstop, the ledger has not passed LastLedgerSequence
            return {"hash": tx_hash, "engineResult": "timeout_waiting",
                    "validated": False, "ledgerIndex": None, "created": {}}
        time.sleep(1.0)


def rawlog(entry: dict) -> None:
    """Append one raw devnet exchange to data/rawlog.jsonl (make_evidence.py renders it into EVIDENCE.md).
    Holds signed tx JSON and rippled responses only; a signed tx never contains a seed."""
    RAWLOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RAWLOG_PATH.open("a") as f:
        f.write(json.dumps({"ts": int(time.time()), **entry}) + "\n")


def submit_blob(blob: str, last_ledger: int | None, label: str | None = None) -> dict:
    res = _rpc(SubmitOnly(tx_blob=blob))
    prelim = res.get("engine_result")
    tx_hash = res.get("tx_json", {}).get("hash")
    submitted = decode(blob)
    entry = {"label": label or submitted.get("TransactionType"), "tx_json": submitted,
             "submit_response": {k: res.get(k) for k in ("engine_result", "engine_result_code", "engine_result_message",
                                                         "accepted", "applied", "error", "error_message")
                                 if k in res} | {"hash": tx_hash}}
    if prelim is None or tx_hash is None:
        rawlog(entry)
        raise RuntimeError(f"submit failed: {res.get('error')} {res.get('error_message')}")
    # tem/tef/tel are never applied; ter/tes/tec may still land.
    if prelim[:3] in ("tem", "tef", "tel"):
        rawlog(entry)
        return {"hash": tx_hash, "engineResult": prelim, "validated": False,
                "ledgerIndex": None, "created": {},
                "engineResultMessage": res.get("engine_result_message")}
    out = wait_for_tx(tx_hash, last_ledger)
    if not out["validated"]:
        out["engineResultMessage"] = res.get("engine_result_message")
    rawlog({**entry, "final": {"validated": out["validated"], "meta.TransactionResult": out["engineResult"],
                               "ledgerIndex": out["ledgerIndex"], "created": out["created"]}})
    return out


def submit_and_wait(tx: Transaction, w: Wallet) -> dict:
    filled = autofill(tx, client())
    signed = sign(filled, w)
    return submit_blob(encode(signed.to_xrpl()), signed.last_ledger_sequence)


# ---- LoanSet co-signing (borrower signs first, broker adds CounterpartySignature) ----
def build_loan_set(borrower_addr: str, loan_broker_id: str, broker_addr: str, principal_drops: str,
                   term_seconds: int, interest_rate: int) -> LoanSet:
    return LoanSet(
        account=borrower_addr,
        counterparty=broker_addr,
        loan_broker_id=loan_broker_id,
        principal_requested=str(principal_drops),
        interest_rate=int(interest_rate),
        payment_total=max(1, int(term_seconds) // PAYMENT_INTERVAL),
        payment_interval=PAYMENT_INTERVAL,
        grace_period=GRACE_PERIOD,
        fee=LOAN_SET_FEE,
    )


def borrower_sign_loan_set(w_borrower: Wallet, tx: LoanSet) -> str:
    from dataclasses import replace
    tx = replace(tx, last_ledger_sequence=current_ledger_index() + LOAN_LAST_LEDGER_OFFSET,
                 fee=LOAN_SET_FEE)
    filled = autofill(tx, client())  # fills Sequence; keeps our Fee and LastLedgerSequence
    signed = sign(filled, w_borrower)
    return encode(signed.to_xrpl())


def verify_loan_set_blob(blob: str, request: dict, accounts: dict, policy: dict) -> str | None:
    try:
        tx = decode(blob)
    except Exception as e:  # noqa: BLE001 - any decode error is a reject reason
        return f"undecodable_blob: {e}"
    expected = {
        "TransactionType": "LoanSet",
        "Account": request["borrower"],
        "Counterparty": accounts["accounts"]["broker"],
        "LoanBrokerID": accounts["loanBrokerId"],
        "PrincipalRequested": str(request["principalDrops"]),
        "InterestRate": int(policy["interestRateBps"]) * 10,
        "PaymentTotal": max(1, int(request["termSeconds"]) // PAYMENT_INTERVAL),
        "PaymentInterval": PAYMENT_INTERVAL,
        "GracePeriod": GRACE_PERIOD,
        "Fee": LOAN_SET_FEE,
    }
    for key, want in expected.items():
        got = tx.get(key)
        if isinstance(want, str) and isinstance(got, str) and key in ("LoanBrokerID",):
            got, want = got.upper(), want.upper()
        if got != want:
            return f"blob_mismatch:{key}"
    if "CounterpartySignature" in tx:
        return "blob_mismatch:already_cosigned"
    if not tx.get("TxnSignature"):
        return "blob_mismatch:unsigned"
    if not signed_by_account(tx):
        return "blob_mismatch:bad_signature"
    return None


def signed_by_account(tx: dict) -> bool:
    """True iff SigningPubKey belongs to Account (no regular key, no multisign) and TxnSignature is that key's
    signature over the single-signing encoding. CounterpartySignature is not a signing field, so a borrower-signed
    LoanSet verifies before and after the broker co-signs. Any decode/crypto error (e.g. a victim's real pubkey with
    a garbage signature) is False, never an exception."""
    try:
        pub = tx["SigningPubKey"]
        if keypairs.derive_classic_address(pub) != tx["Account"]:
            return False
        return bool(keypairs.is_valid_message(bytes.fromhex(encode_for_signing(tx)),
                                              bytes.fromhex(tx["TxnSignature"]), pub))
    except Exception:  # noqa: BLE001 - malformed key/signature is a reject reason, not a 500
        return False


def cosign_loan_set(w_broker: Wallet, blob: str) -> dict:
    last_ledger = decode(blob).get("LastLedgerSequence")
    rawlog({"label": "LoanSet step 1/2: borrower-signed blob received by the broker", "tx_json": decode(blob)})
    signed = sign_loan_set_by_counterparty(w_broker, blob)
    out = submit_blob(signed.tx_blob, last_ledger, label="LoanSet step 2/2: broker adds CounterpartySignature and submits")
    return {"hash": out["hash"], "engineResult": out["engineResult"],
            "validated": out["validated"], "loanId": out["created"].get("Loan"),
            **({"engineResultMessage": out["engineResultMessage"]}
               if out.get("engineResultMessage") else {})}


# ---- loans ------------------------------------------------------------------
def ledger_entry(index: str) -> dict:
    return _rpc(LedgerEntry(index=index, ledger_index="validated"))["node"]


def _drops(x) -> int:
    return int(Decimal(str(x))) if x is not None else 0


def _ceil_drops(x) -> int:
    return int(math.ceil(Decimal(str(x)))) if x is not None else 0


def loan_pay(w_borrower: Wallet, loan_id: str, amount_drops: str | None = None) -> dict:
    if amount_drops is None:
        amount_drops = str(_ceil_drops(ledger_entry(loan_id)["PeriodicPayment"]))
    return submit_and_wait(LoanPay(account=w_borrower.address, loan_id=loan_id,
                                   amount=str(amount_drops)), w_borrower)


_MANAGE_FLAGS = {"impair": LoanManageFlag.TF_LOAN_IMPAIR,
                 "unimpair": LoanManageFlag.TF_LOAN_UNIMPAIR,
                 "default": LoanManageFlag.TF_LOAN_DEFAULT}


def loan_manage(w_broker: Wallet, loan_id: str, action: str) -> dict:
    return submit_and_wait(LoanManage(account=w_broker.address, loan_id=loan_id,
                                      flags=int(_MANAGE_FLAGS[action])), w_broker)


def vault_state(vault_id: str, loan_broker_id: str) -> dict:
    res = _rpc(LedgerEntry(index=vault_id, ledger_index="validated"))
    vault, ledger_index = res["node"], res.get("ledger_index")
    broker = ledger_entry(loan_broker_id)
    share_id = vault["ShareMPTID"]
    issuance = _rpc(LedgerEntry(mpt_issuance=share_id, ledger_index="validated"))["node"]
    total = _drops(vault.get("AssetsTotal"))
    avail = _drops(vault.get("AssetsAvailable"))
    outstanding = total - avail
    debt = _drops(broker.get("DebtTotal"))
    cover = _drops(broker.get("CoverAvailable"))
    return {
        "vaultId": vault_id, "loanBrokerId": loan_broker_id, "shareMptId": share_id,
        "assetsTotalDrops": str(total), "assetsAvailableDrops": str(avail),
        "loansOutstandingDrops": str(outstanding), "debtTotalDrops": str(debt),
        "lossUnrealizedDrops": str(_drops(vault.get("LossUnrealized"))),
        "coverDrops": str(cover),
        "sharesTotal": str(issuance.get("OutstandingAmount", "0")),
        "utilizationPct": round(100 * outstanding / total, 2) if total else 0.0,
        "coverRatioPct": round(100 * cover / debt, 2) if debt else 100.0,
        "subscriptionDate": from_ripple(vault["SubscriptionDate"]) if "SubscriptionDate" in vault else 0,
        "redemptionDate": from_ripple(vault["RedemptionDate"]) if "RedemptionDate" in vault else 0,
        "ledgerIndex": int(ledger_index or 0),
    }


def account_objects(account: str, type_: str | None = None) -> list[dict]:
    out, marker = [], None
    while True:
        kw = {"account": account, "ledger_index": "validated", "limit": 400}
        if type_:
            kw["type"] = AccountObjectType(type_)
        if marker:
            kw["marker"] = marker
        res = _rpc(AccountObjects(**kw))
        out.extend(res.get("account_objects", []))
        marker = res.get("marker")
        if not marker:
            return out


def _loan_status(obj: dict) -> str:
    flags = int(obj.get("Flags", 0))
    if flags & LSF_LOAN_DEFAULT:
        return "defaulted"
    if flags & LSF_LOAN_IMPAIRED:
        return "impaired"
    if int(obj.get("PaymentRemaining", 0)) == 0:
        return "paid"
    return "active"


def loan_item(obj: dict) -> dict:
    return {
        "loanId": obj["index"], "borrower": obj.get("Borrower"),
        "principalDrops": str(_drops(obj.get("PrincipalOutstanding"))),
        "totalOutstandingDrops": str(_drops(obj.get("TotalValueOutstanding"))),
        "periodicPaymentDrops": str(_ceil_drops(obj.get("PeriodicPayment"))),
        "interestRate": int(obj.get("InterestRate", 0)),
        "paymentInterval": int(obj.get("PaymentInterval", 0)),
        "gracePeriod": int(obj.get("GracePeriod", 0)),
        "nextPaymentDue": from_ripple(obj["NextPaymentDueDate"]) if obj.get("NextPaymentDueDate") else 0,
        "paymentRemaining": int(obj.get("PaymentRemaining", 0)),
        "startDate": from_ripple(obj["StartDate"]) if obj.get("StartDate") else 0,
        "status": _loan_status(obj),
    }


def list_loans(loan_broker_id: str) -> list[dict]:
    # Loans live in the LoanBroker pseudo-account's owner dir (LoanBroker.Account) and the
    # borrower's, not the broker owner's (verified on devnet). The pseudo-account has them all.
    pseudo = ledger_entry(loan_broker_id)["Account"]
    loans = [o for o in account_objects(pseudo, "loan")
             if o.get("LoanBrokerID", "").upper() == loan_broker_id.upper()]
    items = [loan_item(o) for o in loans]
    items.sort(key=lambda i: (i["startDate"], i["loanId"]), reverse=True)
    return items


# ---- audit ------------------------------------------------------------------
def audit_append(record: dict) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("a") as f:
        f.write(json.dumps({"ts": int(time.time()), **record}) + "\n")
