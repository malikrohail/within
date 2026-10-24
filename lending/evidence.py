"""Evidence builder (INTERFACES.md §4).

The desk builds Evidence; the borrower only declares purpose, principal, term and existing debt.
- ledger: read from XRPL devnet (account_tx paginated, account_objects, account_info).
- bank:   Plaid Sandbox, only when PLAID_CLIENT_ID + PLAID_SECRET are in lending/.env and the
          borrower is accounts.json's `borrower`; otherwise None (UI: "bank data: not connected").

Payment "day" = the `date` of its invoice memo (MemoType hex "invoice", MemoData hex JSON
{"invoice","date"}), else the ledger close time. The 30-day demo history is written in one setup
run, so the memo carries the business date; ledger timestamps are never faked.
The memo date is used only when it is within MEMO_DATE_TOLERANCE_DAYS (env; unset = unlimited, the
demo default; 7 in production) of the close date; otherwise the close date counts. The ledger also
reports memoDatedPayments and ledgerActiveDays (the same payments by close date, memos ignored).
Window: a payment counts when 0 <= (asOf UTC date - payment date).days <= window_days
(inclusive; future-dated invoices are excluded).
"""
import datetime as dt
import json
import os
import time
from decimal import Decimal
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
DEVNET_URL = "https://s.devnet.rippletest.net:51234/"  # mirrors common.DEVNET_URL (common may not exist yet)
RIPPLE_EPOCH = 946684800

# Devnet faucet sender(s); their payments are funding, not revenue.
FAUCET_ACCOUNTS = frozenset({"rht5xsioM3iix1hx4i2zJX2WJ1JDTwLGJe"})

LSF_LOAN_DEFAULT = 0x00010000
LSF_LOAN_IMPAIRED = 0x00020000
LSF_CREDENTIAL_ACCEPTED = 0x00010000
# The one Credential that counts: issued by this desk's broker (accounts.json), this type, accepted, unexpired.
KYB_CREDENTIAL_TYPE = "kyb-borrower".encode().hex().upper()
INVOICE_MEMO_TYPE = "invoice".encode().hex().upper()
X402_MEMO_TYPES = frozenset({INVOICE_MEMO_TYPE, "x402".encode().hex().upper()})
SAMPLE_HASHES = 5

PLAID_URL = "https://sandbox.plaid.com"
PLAID_INSTITUTION = "ins_109508"
PLAID_DAYS = 90
PLAID_RETRIES = 6
PLAID_RETRY_SLEEP = 2.0
_bank_cache: dict = {}


# ---------------------------------------------------------------- JSON-RPC
def _rpc(client, method: str, params: dict) -> dict:
    """client: None / xrpl JsonRpcClient (devnet URL only) / callable(method, params) -> result."""
    if callable(client):
        return client(method, params)
    url = getattr(client, "url", DEVNET_URL) if client is not None else DEVNET_URL
    if url.rstrip("/") != DEVNET_URL.rstrip("/"):
        raise ValueError("evidence: devnet only")
    for attempt in range(2):  # one retry on a transient devnet error
        try:
            r = requests.post(DEVNET_URL, json={"method": method, "params": [params]}, timeout=20)
            r.raise_for_status()
            res = r.json()["result"]
        except requests.RequestException:
            if attempt:
                raise
            time.sleep(1)
            continue
        if attempt or res.get("error") not in ("tooBusy", "slowDown"):
            return res
        time.sleep(1)  # JSON-RPC overload errors come back as HTTP 200


def _paged(client, method: str, params: dict, key: str) -> list:
    out, marker = [], None
    for _ in range(100):
        p = dict(params)
        if marker is not None:
            p["marker"] = marker
        res = _rpc(client, method, p)
        if res.get("status") == "error" or "error" in res:
            raise RuntimeError(res.get("error", "rpc error"))
        out.extend(res.get(key, []))
        marker = res.get("marker")
        if marker is None:
            break
    return out


# ---------------------------------------------------------------- ledger
def _memo_date(tx: dict) -> dt.date | None:
    for m in tx.get("Memos") or []:
        memo = m.get("Memo", {})
        if (memo.get("MemoType") or "").upper() != INVOICE_MEMO_TYPE:
            continue
        try:
            data = json.loads(bytes.fromhex(memo.get("MemoData", "")).decode())
            return dt.date.fromisoformat(data["date"])
        except (ValueError, KeyError, TypeError):
            continue
    return None


def _is_x402_income(tx: dict) -> bool:
    """An inbound Payment is x402 income when a Memo of type invoice or x402 carries parseable MemoData
    (UTF-8 text; JSON for invoice). The merchants in agent/merchants/ and demo.py write invoice memos."""
    for m in tx.get("Memos") or []:
        memo = m.get("Memo", {})
        mtype = (memo.get("MemoType") or "").upper()
        if mtype not in X402_MEMO_TYPES:
            continue
        try:
            text = bytes.fromhex(memo.get("MemoData", "")).decode()
            if mtype == INVOICE_MEMO_TYPE:
                json.loads(text)
            elif not text.strip():
                continue
            return True
        except (ValueError, TypeError):
            continue
    return False


def _memo_tolerance_days() -> int | None:
    """MEMO_DATE_TOLERANCE_DAYS from the process env, read per call; unset or empty = unlimited."""
    v = os.environ.get("MEMO_DATE_TOLERANCE_DAYS", "").strip()
    return int(v) if v else None


def _close_date(entry: dict, tx: dict) -> dt.date | None:
    if tx.get("date") is not None:
        return dt.datetime.fromtimestamp(int(tx["date"]) + RIPPLE_EPOCH, dt.timezone.utc).date()
    iso = entry.get("close_time_iso")
    if iso:
        return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
    return None


def _created_account(meta: dict, account: str) -> bool:
    for n in meta.get("AffectedNodes", []):
        c = n.get("CreatedNode")
        if c and c.get("LedgerEntryType") == "AccountRoot" and c.get("NewFields", {}).get("Account") == account:
            return True
    return False


def _defaulted_loans_in_meta(meta: dict, borrower: str) -> set:
    ids = set()
    for n in meta.get("AffectedNodes", []):
        node = n.get("ModifiedNode") or n.get("DeletedNode") or n.get("CreatedNode") or {}
        if node.get("LedgerEntryType") != "Loan":
            continue
        f = node.get("FinalFields") or node.get("NewFields") or {}
        if f.get("Borrower") == borrower and int(f.get("Flags", 0)) & LSF_LOAN_DEFAULT:
            ids.add(node.get("LedgerIndex"))
    return ids


def _broker_address() -> str | None:
    try:
        return json.loads((HERE / "accounts.json").read_text())["accounts"]["broker"]
    except (OSError, ValueError, KeyError):
        return None


def _broker_credential(o: dict, borrower: str, broker: str | None, now: int) -> bool:
    """Accepted kyb-borrower Credential from the broker to this borrower, not expired at `now` (unix s).
    Expiration is Ripple time; absent = never expires (mirrors wallet/src/credentials.ts)."""
    exp = o.get("Expiration")
    return (broker is not None and o.get("Issuer") == broker and o.get("Subject") == borrower
            and (o.get("CredentialType") or "").upper() == KYB_CREDENTIAL_TYPE
            and bool(int(o.get("Flags", 0)) & LSF_CREDENTIAL_ACCEPTED)
            and (exp is None or int(exp) > now - RIPPLE_EPOCH))


def ledger_evidence(borrower: str, client, now: int, window_days: int) -> dict:
    ev = {"accountExists": False, "accountAgeLedgers": 0, "inboundPaymentCount": 0,
          "inboundVolumeDrops": "0", "distinctPayers": 0, "topPayerSharePct": 0.0, "activeDays": 0,
          "activeLoans": 0, "loanDebtDrops": "0", "loanPrincipalDrops": "0", "pastDefaults": 0,
          "hasAcceptedCredential": False, "sampleTxHashes": [], "memoDatedPayments": 0, "ledgerActiveDays": 0,
          "x402IncomeDrops": "0", "x402Payments": 0, "x402Payers": 0, "otherInboundDrops": "0"}
    info = _rpc(client, "account_info", {"account": borrower, "ledger_index": "validated"})
    if info.get("error") == "actNotFound":
        return ev
    if "error" in info or "account_data" not in info:
        raise RuntimeError(info.get("error", "account_info: no account_data"))
    ev["accountExists"] = True
    current = int(info.get("ledger_index") or info.get("ledger_current_index") or 0)

    txs = _paged(client, "account_tx", {"account": borrower, "ledger_index_min": -1, "ledger_index_max": -1,
                                        "limit": 200, "api_version": 2}, "transactions")
    as_of = dt.datetime.fromtimestamp(now, dt.timezone.utc).date()
    created_at, earliest = None, None
    per_payer: dict = {}
    days, ledger_days, hashes, defaulted = set(), set(), [], set()
    count = memo_dated = 0
    tolerance = _memo_tolerance_days()
    x402_drops, x402_count, x402_payers, other_drops = 0, 0, set(), 0  # evidence only; score() never reads these
    for entry in txs:  # newest first
        tx = entry.get("tx_json") or entry.get("tx") or {}
        meta = entry.get("meta") or entry.get("metaData") or {}
        li = entry.get("ledger_index") or tx.get("ledger_index")
        if li is not None:
            earliest = int(li) if earliest is None else min(earliest, int(li))
        if _created_account(meta, borrower) and li is not None:
            created_at = int(li)
        defaulted |= _defaulted_loans_in_meta(meta, borrower)

        if tx.get("TransactionType") != "Payment" or tx.get("Destination") != borrower:
            continue
        if entry.get("validated") is False or meta.get("TransactionResult") != "tesSUCCESS":
            continue
        sender = tx.get("Account")
        if sender == borrower or sender in FAUCET_ACCOUNTS or _created_account(meta, borrower):
            continue
        amt = meta.get("delivered_amount", tx.get("DeliverMax", tx.get("Amount")))
        if not isinstance(amt, str):  # IOU / MPT, not XRP
            continue
        close, memo = _close_date(entry, tx), _memo_date(tx)
        if close is not None and 0 <= (as_of - close).days <= window_days:
            ledger_days.add(close)
        # A memo date counts only within tolerance of the close date (no close date: unverifiable unless unlimited).
        use_memo = memo is not None and (tolerance is None
                                         or (close is not None and abs((close - memo).days) <= tolerance))
        day = memo if use_memo else close
        if day is None or not (0 <= (as_of - day).days <= window_days):
            continue
        count += 1
        memo_dated += use_memo
        per_payer[sender] = per_payer.get(sender, 0) + int(amt)
        days.add(day)
        if _is_x402_income(tx):
            x402_drops, x402_count = x402_drops + int(amt), x402_count + 1
            x402_payers.add(sender)
        else:
            other_drops += int(amt)
        if len(hashes) < SAMPLE_HASHES:
            hashes.append(entry.get("hash") or tx.get("hash"))

    volume = sum(per_payer.values())
    first = created_at if created_at is not None else earliest
    ev.update({
        "accountAgeLedgers": max(0, current - first) if first is not None and current else 0,
        "inboundPaymentCount": count,
        "inboundVolumeDrops": str(volume),
        "distinctPayers": len(per_payer),
        "topPayerSharePct": round(100 * max(per_payer.values()) / volume, 1) if volume else 0.0,
        "activeDays": len(days),
        "sampleTxHashes": hashes,
        "memoDatedPayments": memo_dated,
        "ledgerActiveDays": len(ledger_days),
        "x402IncomeDrops": str(x402_drops),
        "x402Payments": x402_count,
        "x402Payers": len(x402_payers),
        "otherInboundDrops": str(other_drops),
    })

    # Loan + Credential objects. Loans may sit in the borrower's or the broker's owner directory.
    objs = _paged(client, "account_objects", {"account": borrower, "ledger_index": "validated", "limit": 400},
                  "account_objects")
    broker = _broker_address()
    if broker and broker != borrower:
        objs += [o for o in _paged(client, "account_objects", {"account": broker, "ledger_index": "validated",
                                                               "limit": 400}, "account_objects")
                 if o.get("LedgerEntryType") == "Loan"]
    seen, active, debt, principal = set(), 0, 0, 0
    for o in objs:
        t = o.get("LedgerEntryType")
        if t == "Credential":
            if _broker_credential(o, borrower, broker, now):
                ev["hasAcceptedCredential"] = True
                ev["credentialIssuer"] = broker  # only when the broker credential counts (Why panel line)
                ev["credentialType"] = "kyb-borrower"
        elif t == "Loan" and o.get("Borrower") == borrower and o.get("index") not in seen:
            seen.add(o.get("index"))
            if int(o.get("Flags", 0)) & LSF_LOAN_DEFAULT:
                defaulted.add(o.get("index"))
            elif int(o.get("PaymentRemaining", 0)) > 0:
                active += 1
                debt += int(Decimal(str(o.get("TotalValueOutstanding", o.get("PrincipalOutstanding", "0")))))
                principal += int(Decimal(str(o.get("PrincipalOutstanding", "0"))))
    ev["activeLoans"] = active
    ev["loanDebtDrops"] = str(debt)
    ev["loanPrincipalDrops"] = str(principal)  # policy.decide: declared existing debt may not be below this
    ev["pastDefaults"] = len(defaulted)
    return ev


# ---------------------------------------------------------------- bank (Plaid Sandbox)
def _plaid_keys() -> tuple[str, str] | None:
    from dotenv import dotenv_values
    env = dotenv_values(HERE / ".env")
    cid, secret = env.get("PLAID_CLIENT_ID"), env.get("PLAID_SECRET")
    return (cid, secret) if cid and secret else None


def _demo_borrower() -> str | None:
    try:
        return json.loads((HERE / "accounts.json").read_text())["accounts"]["borrower"]
    except (OSError, ValueError, KeyError):
        return None


def _plaid(path: str, body: dict) -> dict:
    r = requests.post(PLAID_URL + path, json=body, timeout=30)
    data = r.json()
    if r.status_code != 200:
        raise PlaidError(data.get("error_code", str(r.status_code)))
    return data


class PlaidError(Exception):
    pass


def bank_evidence(borrower: str) -> dict | None:
    keys = _plaid_keys()
    if keys is None or borrower != _demo_borrower():
        return None
    if borrower in _bank_cache:
        return _bank_cache[borrower]
    cid, secret = keys
    auth = {"client_id": cid, "secret": secret}
    try:
        pub = _plaid("/sandbox/public_token/create",
                     {**auth, "institution_id": PLAID_INSTITUTION, "initial_products": ["transactions"]})
        tok = _plaid("/item/public_token/exchange", {**auth, "public_token": pub["public_token"]})
        end = dt.date.today()
        body = {**auth, "access_token": tok["access_token"],
                "start_date": (end - dt.timedelta(days=PLAID_DAYS)).isoformat(), "end_date": end.isoformat(),
                "options": {"count": 500, "offset": 0}}
        for attempt in range(PLAID_RETRIES):
            try:
                data = _plaid("/transactions/get", body)
                break
            except PlaidError as e:
                if str(e) != "PRODUCT_NOT_READY" or attempt == PLAID_RETRIES - 1:
                    raise
                time.sleep(PLAID_RETRY_SLEEP)
    except (PlaidError, requests.RequestException, KeyError, ValueError) as e:
        print(f"evidence: plaid unavailable ({type(e).__name__}: {e}); bank = None")  # never prints keys
        return None
    result = bank_facts(data)
    _bank_cache[borrower] = result
    return result


def bank_facts(data: dict) -> dict:
    """Plaid amounts: positive = money out (debit), negative = money in (credit)."""
    inflow = outflow = 0.0
    nsf = 0
    for t in data.get("transactions", []):
        a = float(t.get("amount", 0))
        if a < 0:
            inflow += -a
        else:
            outflow += a
        cats = " ".join(t.get("category") or []) + " " + json.dumps(t.get("personal_finance_category") or {})
        text = (cats + " " + (t.get("name") or "")).lower()
        if "overdraft" in text or "insufficient" in text or "nsf" in text.split():
            nsf += 1
    deposit = [a for a in data.get("accounts", []) if a.get("type") == "depository"]
    balances = [float((a.get("balances") or {}).get("current") or 0) for a in deposit]
    if outflow:
        ratio = round(inflow / outflow, 2)
    else:
        ratio = 99.0 if inflow else 0.0
    return {"connected": True, "institution": PLAID_INSTITUTION, "days": PLAID_DAYS,
            "avgMonthlyInflowUsd": round(inflow * 30 / PLAID_DAYS, 2),
            "avgBalanceUsd": round(sum(balances) / len(balances), 2) if balances else 0.0,
            "inflowOutflowRatio": ratio, "nsfCount": nsf}


# ---------------------------------------------------------------- assemble
def _default_client():
    try:
        import common  # N1's module; lazy so policy/evidence tests run without it
        return common.client()
    except (ImportError, AttributeError):
        return None  # _rpc falls back to DEVNET_URL


def build_evidence(borrower: str, declared: dict, client=None, now: int | None = None, window_days: int = 30) -> dict:
    now = int(time.time()) if now is None else int(now)
    client = client if client is not None else _default_client()
    return {
        "borrower": borrower, "asOf": now, "windowDays": window_days,
        "ledger": ledger_evidence(borrower, client, now, window_days),
        "bank": bank_evidence(borrower),
        "declared": {"purpose": declared.get("purpose"),
                     "principalDrops": str(declared.get("principalDrops", "0")),
                     "termSeconds": int(declared.get("termSeconds", 0)),
                     "existingDebtDrops": str(declared.get("existingDebtDrops", "0"))},
    }
