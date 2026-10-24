"""Write lending/EVIDENCE.md: the raw devnet record behind every milestone claim.

Sources, all re-read from devnet at generation time (nothing is copied from our own logs unverified):
- accounts.json setupTx / history hashes, and any --tx label=HASH given on the command line
- data/rawlog.jsonl: exact JSON we submitted + rippled's submit response, written by common.py as it happens
- data/desk_examples.jsonl: real desk request/response bodies
- ledger_entry of the Vault, the LoanBroker and every Loan of that broker

  .venv/bin/python make_evidence.py [--tx smokeLoanSet=HASH ...]
Seeds never appear: any seed-shaped string or seed/secret key is redacted before writing.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
DEVNET_URL = "https://s.devnet.rippletest.net:51234/"
EXPLORER = "https://devnet.xrpl.org/transactions/"
SEED_RE = re.compile(r"\bs[1-9A-HJ-NP-Za-km-z]{25,35}\b")
SECRET_KEYS = {"seed", "secret", "private_key", "privatekey", "master_seed", "plaid_secret"}
MAX_STR = 160
# Phase 3 findings that every regeneration keeps (batch spike, all-or-nothing drill, cover-rate fix).
PINNED_TX = [
    ("batch spike LoanBrokerSet (liquidation 100000)", "3CFEBBBE9CED518A9F1AAA6D0683F22BFF27A705B65977CEFD945A2A33B7B6B6"),
    ("batch spike co-signed LoanSet 60 XRP (lands before the Batch)", "90B14608F08FD217562606260DB6D8D1AF5E2F4E5882D4876CC28E70C77E1927"),
    ("batch spike Batch C AllOrNothing: 55 XRP supplier + 1 XRP fee", "35DF41124FF1DF972A654BC43A482E087A5322E55E4BDF4549D18D17C0F059FA"),
    ("batch spike inner Payment supplier 55 XRP", "CEC27BB43A0C353234573F27634F33159EBDE9A469E5F1755625F1CBB2A2397B"),
    ("batch spike inner Payment broker fee 1 XRP", "3B49A298F91AF946C002B97BABDA55CB81E7B1240452A43DB7674173B098C6B3"),
    ("batch drill Batch D AllOrNothing, 5000 XRP supplier leg (no inner applies)", "2DCCD2D2349A917560F4539AFCCD561D78F5227FC165C257150055B6919A50F5"),
    ("batch drill inner Payment (not applied)", "6F8FFB50200842336CB82E24761B2B8B1A23A1E11E75862C28243C9B20CDC2CD"),
    ("cover fix LoanManage default 60 XRP loan (cover 20 -> 14 XRP)", "A8DCC89330485B28AA960332DB87D2984C6AB1B2D268B95A80E6B1F628D6991E"),
]

# The gate-ON run (verified): the approval Payment lives on testnet, the loan on devnet.
GATE_ON_APPROVAL = "8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C"
GATE_ON_TX = [
    ("gate-ON LoanSet 30 XRP, co-signed after the Ledger approval", "C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13"),
    ("gate-ON Batch AllOrNothing: 29 XRP compute supplier + 1 XRP fee", "6C506E2B9E7B6027C9BBC80E6A75480A1DF2382346567F0BD98E60A540A29DDB"),
    ("gate-ON inner Payment supplier 29 XRP", "EB3922C3198E1B7891F12B4323B6B696CE10834D0E17DE66A218AF8119E618FE"),
    ("gate-ON inner Payment broker fee 1 XRP", "1760EA4403177EF90BEBF8EE1509777E810DD25FCBBB54F71B83E52ABDCE5CD6"),
]


def rpc(method, **params):
    for attempt in range(4):  # devnet resets connections now and then
        try:
            resp = requests.post(DEVNET_URL, json={"method": method, "params": [params]}, timeout=30)
            resp.raise_for_status()
            return resp.json()["result"]
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def scrub(value, key=""):
    """Redact seeds and secrets, trim long hex blobs."""
    if isinstance(value, dict):
        return {k: scrub(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, key) for v in value]
    if isinstance(value, str):
        if key.lower() in SECRET_KEYS or key.lower().endswith("_seed") or SEED_RE.fullmatch(value):
            return "<redacted>"
        value = SEED_RE.sub("<redacted>", value)
        if len(value) > MAX_STR:
            return f"{value[:64]}…({len(value)} chars)"
    return value


def block(obj):
    return "```json\n" + json.dumps(scrub(obj), indent=2, sort_keys=False) + "\n```\n"


def compact_meta(meta):
    """Keep TransactionResult and, per affected node, type + index + the final/new fields of lending objects."""
    nodes = []
    for wrapper in meta.get("AffectedNodes", []):
        (kind, node), = wrapper.items()
        entry = {"node": kind, "LedgerEntryType": node.get("LedgerEntryType"), "LedgerIndex": node.get("LedgerIndex")}
        if node.get("LedgerEntryType") in {"Vault", "LoanBroker", "Loan", "MPTokenIssuance", "MPToken"}:
            entry["fields"] = node.get("NewFields") or node.get("FinalFields")
            if node.get("PreviousFields"):
                entry["PreviousFields"] = node["PreviousFields"]
        nodes.append(entry)
    out = {"TransactionResult": meta.get("TransactionResult"), "AffectedNodes": nodes}
    if "delivered_amount" in meta:
        out["delivered_amount"] = meta["delivered_amount"]
    return out


def tx_section(label, tx_hash):
    r = rpc("tx", transaction=tx_hash)
    if r.get("error"):
        return f"### {label}\n`{tx_hash}`: **{r.get('error')}** {r.get('error_message', '')}\n\n"
    tx_json = r.get("tx_json") or {k: v for k, v in r.items() if k[0].isupper()}
    meta = r.get("meta") or {}
    head = (f"### {label}\n- hash: [`{tx_hash}`]({EXPLORER}{tx_hash})\n- validated: `{r.get('validated')}`, "
            f"ledger `{r.get('ledger_index')}`, meta.TransactionResult: **`{meta.get('TransactionResult')}`**\n\n")
    return head + "tx_json (as validated on devnet):\n" + block(tx_json) + "meta:\n" + block(compact_meta(meta))


def object_section(label, index):
    r = rpc("ledger_entry", index=index, ledger_index="validated")
    if r.get("error"):
        return f"### {label}\n`{index}`: **{r.get('error')}**\n\n"
    return f"### {label} (ledger {r.get('ledger_index')})\n" + block(r.get("node"))


def broker_loans(owner, loan_broker_id):
    loans, marker = [], None
    while True:
        params = dict(account=owner, type="loan", ledger_index="validated", limit=200)
        if marker:
            params["marker"] = marker
        r = rpc("account_objects", **params)
        loans += [o for o in r.get("account_objects", []) if o.get("LoanBrokerID") == loan_broker_id]
        marker = r.get("marker")
        if not marker:
            return loans


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tx", action="append", default=[], help="label=HASH, repeatable")
    parser.add_argument("--out", default=str(HERE / "EVIDENCE.md"))
    args = parser.parse_args()
    accounts = json.loads((HERE / "accounts.json").read_text())
    extra = [tuple(t.split("=", 1)) for t in args.tx]

    parts = [
        "# Lending Desk — raw devnet evidence\n\n",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} by `lending/make_evidence.py`; every tx and object "
        f"below was re-read from devnet (`{DEVNET_URL}`) at that time. Long hex is trimmed; seeds never appear.\n\n",
        "**Why tecTOO_SOON and tecEXPIRED appear below:** the vault is close-ended (`VaultKind` 1). Before its "
        "`SubscriptionDate` it is raising funds: `VaultDeposit` succeeds and `LoanSet` is rejected `tecTOO_SOON`. After that "
        "date it is lending: `LoanSet` succeeds and a late `VaultDeposit` is rejected `tecEXPIRED`. Each scripted demo run "
        "opens a new vault with a ~120 s subscription window, takes the deposits inside it, then lends.\n\n",
        "**Scripted run switches:** the pre-staged 9/9 ran with the approver gate and the second opinion off "
        "(`DESK_APPROVER_ACCOUNT=off SECOND_OPINION=off`), because a fresh account with 22 memo-dated active days is "
        "exactly what the model should flag; the stage's live held request runs with both ON.\n\n",
        "**Cover units:** LoanBroker rates are in 1/100,000 (10000 = 10 %). On a default the ledger takes "
        "`DebtTotal x CoverRateMinimum x CoverRateLiquidation` from first-loss cover. With 10 % x 100 % that is 10 % "
        "of the debt (cover 20 -> 14 XRP on a 60 XRP default in the batch spike below). Runs before this change used "
        "liquidation 10000, i.e. 1 % (20 -> 19.33 XRP).\n\n",
        "## Accounts and ids\n", block({k: accounts.get(k) for k in
                                        ("network", "accounts", "vaultId", "shareMptId", "loanBrokerId", "vaultKind",
                                         "subscriptionDate", "redemptionDate", "history")}),
        "## Setup transactions (M1)\n",
    ]
    for label, tx_hash in (accounts.get("setupTx") or {}).items():
        parts.append(tx_section(label, tx_hash))
    if extra:
        parts.append("## Milestone transactions\n")
        for label, tx_hash in extra:
            parts.append(tx_section(label, tx_hash))
    sweeps = json.loads((HERE / "data" / "sweeps.json").read_text()) if (HERE / "data" / "sweeps.json").exists() else []
    if sweeps:
        parts.append("## Auto-repay sweeps (data/sweeps.json, verified by the desk)\n"
                     "Each sweep: a customer x402 Payment to the borrower (income), then the borrower's sweeper pays one "
                     "installment from it with LoanPay (borrower key only). The desk stored the record after reading "
                     "both hashes on devnet.\n\n")
        for rec in sweeps:
            parts.append(f"### sweep record, loan {rec.get('loanId')}\n" + block(rec))
            parts.append(tx_section(f"sweep income Payment {int(rec['incomeDrops']) / 1e6:g} XRP (invoice memo)",
                                    rec["incomeHash"]))
            parts.append(tx_section(f"sweep LoanPay {int(rec['drops']) / 1e6:g} XRP (sweeper, borrower-signed)",
                                    rec["loanPayHash"]))
    parts.append("## Gate-ON device approval, end to end (lr_0030, desk e629fb0)\n"
                 "A held 30 XRP working-capital draw approved on the Ledger: approval Payment "
                 f"`{GATE_ON_APPROVAL}` on testnet (two memos: loan-approval = sha256 of the borrower-signed LoanSet, "
                 "loan-terms 'approve loan 30 XRP to rBZQ4Z23RsLF3yZzWUAc5jfu1VHrYQUUYG 6 payments'), verified by the desk "
                 "(signer, memo hash, terms against the stored blob) before it co-signed. Record: decidedBy ledger.\n\n")
    for label, tx_hash in GATE_ON_TX:
        parts.append(tx_section(label, tx_hash))
    parts.append("## Phase 3 findings (batch spike, drill, cover fix)\n")
    for label, tx_hash in PINNED_TX:
        parts.append(tx_section(label, tx_hash))

    raw = read_jsonl(HERE / "data" / "rawlog.jsonl")
    if raw:
        parts.append("## Raw submissions, as they happened (data/rawlog.jsonl)\n"
                     "Each entry: the exact JSON we submitted (signed, decoded) and rippled's submit response.\n\n")
        for entry in raw:
            parts.append(f"### {entry.get('label', entry.get('tx_json', {}).get('TransactionType'))} — {entry.get('ts')}\n"
                         + block(entry))

    batch = read_jsonl(HERE / "data" / "batch_rawlog.jsonl")
    if batch:
        parts.append("## Batch spike, raw submissions (data/batch_rawlog.jsonl, `batch/spike.py`, `batch/probe_inner.py`)\n"
                     "Fresh accounts and a fresh vault, separate from the desk. `temINVALID_INNER_BATCH` is a preflight "
                     "rejection: rippled does not accept LoanSet (either orientation, with or without "
                     "CounterpartySignature) or VaultDeposit as a Batch inner transaction. Payments-only Batch after a "
                     "co-signed LoanSet works.\n\n")
        for entry in batch:
            parts.append(f"### {entry.get('label')} — {entry.get('ts')}\n" + block(entry))

    parts.append("## Ledger objects now\n")
    parts.append(object_section("Vault", accounts["vaultId"]))
    parts.append(object_section("LoanBroker", accounts["loanBrokerId"]))
    # Loans live in the owner directory of the LoanBroker's pseudo-account, not the broker owner's.
    pseudo = rpc("ledger_entry", index=accounts["loanBrokerId"], ledger_index="validated").get("node", {}).get("Account")
    for loan in broker_loans(pseudo, accounts["loanBrokerId"]) if pseudo else []:
        parts.append(f"### Loan {loan['index']}\n" + block(loan))

    desk = read_jsonl(HERE / "data" / "desk_examples.jsonl")
    if desk:
        parts.append("## Desk API, real bodies (data/desk_examples.jsonl)\n")
        for ex in desk:
            parts.append(f"### {ex.get('label')}: {ex.get('method')} {ex.get('path')}\n" + block(ex))

    text = "".join(parts)
    if SEED_RE.search(text.replace("<redacted>", "")):
        print("refusing to write: seed-shaped string survived scrubbing", file=sys.stderr)
        return 1
    Path(args.out).write_text(text)
    print(f"wrote {args.out} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
