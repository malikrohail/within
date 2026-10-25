"""Fetch the three transactions behind the gate-ON Ledger-approved loan (lr_0030, 2026-10-24 18:07 ET)
from the PUBLIC XRPL nodes, save the exact JSON-RPC request and response for each, and re-derive the
approval memo from the validated LoanSet. Run: python3 -I rpc_capture.py (needs lending/.venv for xrpl-py)."""
import hashlib, json, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TXS = [
    ("01-testnet-approval-payment", "https://s.altnet.rippletest.net:51234/", "8AC151230EAF1AC6F9928CF3E5A5F25DF2DE6AC2454C76DD6136466987B7919C"),
    ("02-devnet-loanset",           "https://s.devnet.rippletest.net:51234/", "C9627B03199430510F43567C6A93A446116606AC4DA5FAE763BA8FAA6CDDDF13"),
    ("03-devnet-batch",             "https://s.devnet.rippletest.net:51234/", "6C506E2B9E7B6027C9BBC80E6A75480A1DF2382346567F0BD98E60A540A29DDB"),
]
out = {}
for name, url, h in TXS:
    req = {"method": "tx", "params": [{"transaction": h, "binary": False}]}
    body = json.dumps(req).encode()
    r = urllib.request.urlopen(urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}), timeout=20)
    resp = json.loads(r.read())
    (HERE / f"{name}.request.json").write_text(json.dumps({"url": url, **req}, indent=2) + "\n")
    (HERE / f"{name}.response.json").write_text(json.dumps(resp, indent=2) + "\n")
    out[name] = resp["result"]
    print(name, "validated", resp["result"].get("validated"), resp["result"].get("meta", {}).get("TransactionResult"))

pay, loan = out["01-testnet-approval-payment"], out["02-devnet-loanset"]
memos = {bytes.fromhex(m["Memo"]["MemoType"]).decode(): m["Memo"]["MemoData"] for m in pay["Memos"]}
approval_hash = memos["loan-approval"]
terms = bytes.fromhex(memos["loan-terms"]).decode()

# Rebuild the borrower-signed blob: the validated LoanSet minus the counterparty's signature and the ledger metadata.
from xrpl.core.binarycodec import encode
tx = {k: v for k, v in loan.items() if k not in ("CounterpartySignature", "hash", "ledger_index", "meta", "validated", "date", "inLedger", "ctid", "ledger_hash", "close_time_iso", "status", "tx_json")}
blob = encode(tx)
digest = hashlib.sha256(bytes.fromhex(blob)).hexdigest().upper()
derived_terms = f"approve loan {int(loan['PrincipalRequested']) // 1_000_000} XRP to {loan['Account']} {loan['PaymentTotal']} payments"
result = {
    "approvalPayment": {"hash": pay["hash"], "network": "testnet", "Account": pay["Account"], "Destination": pay["Destination"], "Amount": pay["Amount"], "memo_loan_approval": approval_hash, "memo_loan_terms": terms, "has_Delegate": "Delegate" in pay},
    "loanSet": {"hash": loan["hash"], "network": "devnet", "Account": loan["Account"], "Counterparty": loan.get("Counterparty"), "PrincipalRequested": loan["PrincipalRequested"], "PaymentTotal": loan["PaymentTotal"], "has_CounterpartySignature": "CounterpartySignature" in loan},
    "rebuilt_borrower_signed_blob_sha256": digest,
    "memo_equals_rebuilt_blob_sha256": digest == approval_hash,
    "derived_terms": derived_terms,
    "memo_terms_equal_derived": derived_terms == terms,
    "batch": {"hash": out["03-devnet-batch"]["hash"], "Flags_hex": hex(out["03-devnet-batch"].get("Flags", 0)), "inner_count": len(out["03-devnet-batch"].get("RawTransactions", [])), "result": out["03-devnet-batch"]["meta"]["TransactionResult"]},
}
(HERE / "04-binding-check.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
