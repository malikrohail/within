"""011 - A Ledger emulator (Speculos Stax, patched XRP app 2.8.2 from experiment 005) shows the lending fields and signs a LoanSet and a LoanPay
that validate on XRPL devnet.

The device is the borrower (Account). Its key never leaves the emulator: this script asks the app for the public key
(APDU GET_PUBLIC_KEY), builds the transactions with xrpl-py, sends the serialized bytes to the app (APDU SIGN, chunked,
the app adds the STX signing prefix itself), walks the review pages on the Stax screen (saving a PNG of every page),
holds "Hold to sign", and puts the returned DER signature into TxnSignature. The LoanSet then gets the broker's
CounterpartySignature with xrpl-py (software key, as in experiment 001) and is submitted; the LoanPay is signed by the
device alone.

Fresh vault + loan broker per run (close-ended, 60 s subscription window) from the experiment 001 depositor/broker
seeds in ons/experiments/.secrets/001.json (never printed). The device account is funded by the devnet faucet.

Run:  (Speculos already on :5001 with the patched elf, see README.md)
  <scratch venv>/bin/python ons/experiments/011-speculos-loanset-devnet/run.py
Writes run-log.json (hashes, explorer links) and screens/*.png next to this file.
"""
from __future__ import annotations

import json
import math
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

import requests
from xrpl.clients import JsonRpcClient
from xrpl.core import keypairs
from xrpl.core.binarycodec import decode, encode, encode_for_signing
from xrpl.models.currencies import XRP
from xrpl.models.requests import AccountInfo, GenericRequest, Ledger, LedgerEntry, Tx
from xrpl.models.transactions import (LoanBrokerCoverDeposit, LoanBrokerSet, LoanPay, LoanSet, Transaction,
                                      VaultCreate, VaultDeposit)
from xrpl.models.transactions.vault_create import VaultKind, WithdrawalPolicy
from xrpl.transaction import autofill, sign, sign_loan_set_by_counterparty
from xrpl.utils import xrp_to_drops
from xrpl.wallet import Wallet, generate_faucet_wallet

HERE = Path(__file__).resolve().parent
SECRETS = HERE.parent / ".secrets" / "001.json"
LOG_PATH = HERE / "run-log.json"
SCREENS = HERE / "screens"

JSON_RPC = "https://s.devnet.rippletest.net:51234"
FAUCET = "https://faucet.devnet.rippletest.net/accounts"
EXPLORER = "https://devnet.xrpl.org/transactions/"
SPECULOS = "http://127.0.0.1:5001"
PATH = "44'/144'/0'/0/0"

DEPOSIT_XRP = 60
COVER_XRP = 5
PRINCIPAL_XRP = 10
SUBSCRIPTION_SECS = 60
INVESTMENT_SECS = 600
PAYMENT_TOTAL = 3
PAYMENT_INTERVAL = 60
INTEREST_RATE = 10_000       # 1/10 bp => 10 %
MANAGEMENT_FEE_RATE = 1_000
COVER_RATE_MINIMUM = 10_000
COVER_RATE_LIQUIDATION = 50_000
DEBT_MAXIMUM_DROPS = str(xrp_to_drops(50))
FEE = "200"

client = JsonRpcClient(JSON_RPC)
LOG: list[dict[str, Any]] = []


# ---------------------------------------------------------------- Speculos / APDU
def pack_path(path: str) -> bytes:
    parts = path.replace("m/", "").split("/")
    out = bytes([len(parts)])
    for p in parts:
        v = int(p.rstrip("'")) + (0x80000000 if p.endswith("'") else 0)
        out += v.to_bytes(4, "big")
    return out


def apdu(data: bytes, timeout: int = 300) -> bytes:
    r = requests.post(f"{SPECULOS}/apdu", json={"data": data.hex()}, timeout=timeout)
    r.raise_for_status()
    return bytes.fromhex(r.json()["data"])


def device_pubkey() -> tuple[str, str]:
    p = pack_path(PATH)
    rep = apdu(bytes([0xE0, 0x02, 0x00, 0x40, len(p)]) + p)
    assert rep[-2:] == b"\x90\x00", f"GET_PUBLIC_KEY sw={rep[-2:].hex()}"
    pub = rep[1:1 + rep[0]].hex().upper()
    return pub, keypairs.derive_classic_address(pub)


def screen() -> list[dict]:
    return requests.get(f"{SPECULOS}/events?currentscreenonly=true", timeout=10).json()["events"]


def screen_text() -> list[str]:
    return [e["text"] for e in screen()]


def finger(action: str, x: int, y: int) -> None:
    requests.post(f"{SPECULOS}/finger", json={"action": action, "x": x, "y": y}, timeout=10).raise_for_status()


def snap(name: str) -> None:
    png = requests.get(f"{SPECULOS}/screenshot", timeout=10).content
    (SCREENS / f"{name}.png").write_bytes(png)


def device_sign(label: str, tx_bytes: bytes) -> bytes:
    """Sends the SIGN APDUs in a thread, drives the Stax review on the main thread, returns the DER signature."""
    p = pack_path(PATH)
    payload = p + tx_bytes
    chunks = [payload[i:i + 255] for i in range(0, len(payload), 255)]
    result: dict[str, Any] = {}

    def worker() -> None:
        try:
            if len(chunks) == 1:
                result["rep"] = apdu(bytes([0xE0, 0x04, 0x00, 0x40, len(chunks[0])]) + chunks[0])
                return
            p1 = 0x80
            for c in chunks[:-1]:
                rep = apdu(bytes([0xE0, 0x04, p1, 0x40, len(c)]) + c)
                assert rep[-2:] == b"\x90\x00", f"chunk sw={rep[-2:].hex()}"
                p1 = 0x81
            result["rep"] = apdu(bytes([0xE0, 0x04, 0x01, 0x40, len(chunks[-1])]) + chunks[-1])
        except Exception as e:  # noqa: BLE001
            result["err"] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    # wait for the review to appear
    deadline = time.time() + 20
    while time.time() < deadline and not any("transaction type" in s.lower() or "review" in s.lower() for s in screen_text()):
        time.sleep(0.25)
    pages: list[list[str]] = []
    taps = 0
    while taps < 12:
        txt = screen_text()
        if not pages or txt != pages[-1]:
            pages.append(txt)
            snap(f"{label}-{len(pages):02d}")
            print(f"    page {len(pages)}: {txt}")
        if any("hold to sign" in s.lower() for s in txt):
            break
        if any(w in " ".join(txt).lower() for w in ("blind signing", "continue anyway", "cannot be clear", "back to safety")):
            raise RuntimeError(f"fail closed: the app showed a blind-signing page for this transaction, screen={txt}")
        finger("press-and-release", 350, 620)
        taps += 1
        time.sleep(0.8)
    if not any("hold to sign" in s.lower() for s in screen_text()):
        raise RuntimeError(f"no 'Hold to sign' page after {taps} taps, screen={screen_text()}")
    finger("press", 336, 515)
    time.sleep(3.2)
    finger("release", 336, 515)
    t.join(timeout=60)
    time.sleep(0.5)
    snap(f"{label}-{len(pages) + 1:02d}-after")
    print(f"    after sign: {screen_text()}")
    if "err" in result:
        raise result["err"]
    rep = result["rep"]
    assert rep[-2:] == b"\x90\x00", f"SIGN sw={rep[-2:].hex()}"
    return rep[:-2]


def sign_on_device(label: str, tx: Transaction, pub: str) -> tuple[str, dict]:
    """autofill -> SigningPubKey -> device signs -> verified blob (hex) + tx_json."""
    tx = autofill(tx, client)
    tx_json = tx.to_xrpl()
    tx_json["SigningPubKey"] = pub
    tx_json.pop("TxnSignature", None)
    unsigned_blob = encode(tx_json)
    print(f"  [{label}] {len(unsigned_blob) // 2} bytes to the device; LastLedgerSequence={tx_json.get('LastLedgerSequence')}")
    sig = device_sign(label, bytes.fromhex(unsigned_blob))
    tx_json["TxnSignature"] = sig.hex().upper()
    ok = keypairs.is_valid_message(bytes.fromhex(encode_for_signing(tx_json)), sig, pub)
    print(f"  [{label}] device signature verifies against the Account key: {ok}")
    assert ok, "device signature does not verify"
    return encode(tx_json), tx_json


# ---------------------------------------------------------------- ledger helpers
def ledger_close_time() -> int:
    return client.request(Ledger(ledger_index="validated")).result["ledger"]["close_time"]


def ledger_entry(index: str) -> dict:
    return client.request(LedgerEntry(index=index, ledger_index="validated")).result["node"]


def balance(addr: str) -> Optional[int]:
    r = client.request(AccountInfo(account=addr, ledger_index="validated")).result
    return int(r["account_data"]["Balance"]) if "account_data" in r else None


def created_node_id(meta: dict, typ: str) -> Optional[str]:
    for n in meta.get("AffectedNodes", []):
        c = n.get("CreatedNode")
        if c and c.get("LedgerEntryType") == typ:
            return c["LedgerIndex"]
    return None


def wait_validated(tx_hash: str, timeout: int = 90) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        r = client.request(Tx(transaction=tx_hash)).result
        if r.get("validated"):
            return r
        time.sleep(2)
    raise TimeoutError(f"{tx_hash} not validated in {timeout}s")


def record(step: str, code: str, tx_hash: Optional[str], extra: Optional[dict] = None) -> None:
    e = {"step": step, "result": code, "hash": tx_hash, "explorer": EXPLORER + tx_hash if tx_hash else None}
    e.update(extra or {})
    LOG.append(e)
    LOG_PATH.write_text(json.dumps(LOG, indent=2))
    print(f"  {step}: {code} {tx_hash or ''}")


def submit_blob(step: str, blob: str, tx_hash_hint: Optional[str] = None, extra: Optional[dict] = None) -> dict:
    sub = client.request(GenericRequest(method="submit", tx_blob=blob)).result
    tx_hash = sub.get("tx_json", {}).get("hash") or tx_hash_hint
    print(f"  submit {step}: {sub.get('engine_result')} {sub.get('engine_result_message', '')}")
    res = wait_validated(tx_hash)
    record(step, res["meta"]["TransactionResult"], tx_hash, {"submit_engine_result": sub.get("engine_result"), **(extra or {})})
    if res["meta"]["TransactionResult"] != "tesSUCCESS":
        sys.exit(f"{step} failed: {res['meta']['TransactionResult']}")
    return res


def submit_sw(step: str, tx: Transaction, w: Wallet) -> dict:
    tx = autofill(tx, client)
    s = sign(tx, w)
    return submit_blob(step, encode(s.to_xrpl()))


def wait_for_ledger_time(target: int, label: str) -> None:
    while True:
        t = ledger_close_time()
        if t > target:
            return
        print(f"  waiting for {label}: ledger close_time {t} -> {target} ({target - t}s)")
        time.sleep(min(10, max(2, target - t)))


def ensure_funds(w: Wallet, need_xrp: int, name: str) -> None:
    b = balance(w.address)
    while (b or 0) < int(xrp_to_drops(need_xrp)):
        print(f"  funding {name} {w.address} via faucet (balance {b})")
        generate_faucet_wallet(client, wallet=w, faucet_host="faucet.devnet.rippletest.net")
        b = balance(w.address)


def ensure_device_funds(addr: str, need_xrp: int) -> None:
    b = balance(addr)
    while (b or 0) < int(xrp_to_drops(need_xrp)):
        print(f"  funding device account {addr} via faucet (balance {b})")
        r = requests.post(FAUCET, json={"destination": addr, "xrpAmount": "100"}, timeout=60)
        r.raise_for_status()
        time.sleep(6)
        b = balance(addr)


# ---------------------------------------------------------------- main
def main() -> None:
    SCREENS.mkdir(exist_ok=True)
    sec = json.loads(SECRETS.read_text())
    depositor, broker = Wallet.from_seed(sec["depositor"]), Wallet.from_seed(sec["broker"])
    pub, device = device_pubkey()
    print(f"device (Speculos, {PATH}): {device} pubkey {pub}")
    print(f"broker {broker.address}  depositor {depositor.address}")
    ensure_funds(depositor, DEPOSIT_XRP + 15, "depositor")
    ensure_funds(broker, COVER_XRP + 15, "broker")
    ensure_device_funds(device, 25)
    LOG.append({"device_account": device, "device_pubkey": pub, "path": PATH, "broker": broker.address,
                "depositor": depositor.address, "app": "app-xrp 2.8.2 + experiment 005 patch, Stax, API level 27, Speculos 0.27.1",
                "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")})

    sub_date = ledger_close_time() + SUBSCRIPTION_SECS
    red_date = sub_date + INVESTMENT_SECS
    res = submit_sw("1 VaultCreate", VaultCreate(account=broker.address, asset=XRP(),
                                                withdrawal_policy=WithdrawalPolicy.VAULT_STRATEGY_FIRST_COME_FIRST_SERVE,
                                                vault_kind=VaultKind.CLOSED, subscription_date=sub_date,
                                                redemption_date=red_date, data="303131"), broker)
    vault_id = created_node_id(res["meta"], "Vault")
    assert vault_id, "no Vault created"
    LOG[-1]["vault_id"] = vault_id
    submit_sw("2 VaultDeposit", VaultDeposit(account=depositor.address, vault_id=vault_id,
                                             amount=xrp_to_drops(DEPOSIT_XRP)), depositor)
    res = submit_sw("3 LoanBrokerSet", LoanBrokerSet(account=broker.address, vault_id=vault_id,
                                                     management_fee_rate=MANAGEMENT_FEE_RATE, debt_maximum=DEBT_MAXIMUM_DROPS,
                                                     cover_rate_minimum=COVER_RATE_MINIMUM,
                                                     cover_rate_liquidation=COVER_RATE_LIQUIDATION, data="303131"), broker)
    broker_id = created_node_id(res["meta"], "LoanBroker")
    assert broker_id, "no LoanBroker created"
    LOG[-1]["loan_broker_id"] = broker_id
    submit_sw("4 LoanBrokerCoverDeposit", LoanBrokerCoverDeposit(account=broker.address, loan_broker_id=broker_id,
                                                                 amount=xrp_to_drops(COVER_XRP)), broker)

    wait_for_ledger_time(sub_date + 1, "Investment phase")
    loan_tx = LoanSet(account=device, loan_broker_id=broker_id, counterparty=broker.address,
                      principal_requested=xrp_to_drops(PRINCIPAL_XRP), payment_total=PAYMENT_TOTAL,
                      payment_interval=PAYMENT_INTERVAL, grace_period=PAYMENT_INTERVAL, interest_rate=INTEREST_RATE,
                      loan_origination_fee=xrp_to_drops(0.1), loan_service_fee=xrp_to_drops(0.01),
                      close_payment_fee=xrp_to_drops(0.01), fee=FEE)
    print("\n[5] LoanSet: the device signs as the borrower (Account)")
    blob, tx_json = sign_on_device("loan-set", loan_tx, pub)
    counter = sign_loan_set_by_counterparty(broker, blob)
    assert "CounterpartySignature" in decode(counter.tx_blob)
    res = submit_blob("5 LoanSet (device-signed Account, broker CounterpartySignature)", counter.tx_blob, counter.hash,
                      {"device_signed_blob_sha256": __import__("hashlib").sha256(bytes.fromhex(blob)).hexdigest().upper(),
                       "tx_json_before_counterparty": tx_json})
    loan_id = created_node_id(res["meta"], "Loan") if res["meta"]["TransactionResult"] == "tesSUCCESS" else None
    if not loan_id:
        sys.exit("LoanSet failed, stopping")
    LOG[-1]["loan_id"] = loan_id
    loan = ledger_entry(loan_id)
    print("  Loan: " + json.dumps({k: loan.get(k) for k in ["Borrower", "PrincipalOutstanding", "PeriodicPayment",
                                                            "PaymentRemaining", "LoanServiceFee", "Flags"]}))

    periodic = math.ceil(float(loan["PeriodicPayment"]))
    inst = periodic + int(loan.get("LoanServiceFee", "0"))
    print(f"\n[6] LoanPay {inst} drops: the device signs alone")
    pay_tx = LoanPay(account=device, loan_id=loan_id, amount=str(inst), fee=FEE)
    blob, tx_json = sign_on_device("loan-pay", pay_tx, pub)
    submit_blob("6 LoanPay (device-signed, single signature)", blob, None, {"tx_json": tx_json})
    loan = ledger_entry(loan_id)
    print("  Loan after pay: " + json.dumps({k: loan.get(k) for k in ["PrincipalOutstanding", "PaymentRemaining",
                                                                       "NextPaymentDueDate"]}))
    LOG.append({"finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "device_balance_drops": balance(device)})
    LOG_PATH.write_text(json.dumps(LOG, indent=2))
    print("\ndone; run-log.json written")


if __name__ == "__main__":
    main()
