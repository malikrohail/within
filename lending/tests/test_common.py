"""Offline unit tests for common.py and setup.py helpers (no devnet calls)."""
import json
import re
from pathlib import Path

import pytest
from xrpl.core.binarycodec import decode, encode
from xrpl.transaction import sign
from xrpl.wallet import Wallet

import common as C
import setup as S

LENDING = Path(C.__file__).resolve().parent
LB_ID = "E43DA4D38D7DA816256CA4947839187C41A113FC81AB5A3568B2C7BF7CB1CC91"


def test_ripple_epoch_round_trip():
    assert C.RIPPLE_EPOCH == 946684800
    assert C.to_ripple(946684800) == 0
    assert C.from_ripple(C.to_ripple(1792828695)) == 1792828695


def test_constants_match_interfaces():
    assert C.DEVNET_URL == "https://s.devnet.rippletest.net:51234/"
    assert 60 <= C.PAYMENT_INTERVAL <= 120
    assert 60 <= C.GRACE_PERIOD <= C.PAYMENT_INTERVAL
    assert int(C.LOAN_SET_FEE) >= 20
    assert C.SETUP_DEPOSITS == {"depositorA": "20000000", "depositorB": "10000000"}
    assert C.client().url == C.DEVNET_URL


def test_history_schedule_lands_in_good_small_buckets():
    rows = S.history_schedule()
    facts = S.schedule_facts(rows)
    assert facts == {"payments": 24, "activeDays": 22, "volumeDrops": 61_000_000,
                     "payers": 5, "topPayerSharePct": 31.1}
    assert all(1 <= days_ago <= 28 for days_ago, _, _ in rows)
    assert all(1_000_000 <= drops <= 5_000_000 for _, _, drops in rows)


def test_invoice_memo_shape():
    m = S.invoice_memo("INV-20261023-024", "2026-10-23")
    assert bytes.fromhex(m.memo_type).decode() == "invoice"
    assert json.loads(bytes.fromhex(m.memo_data).decode()) == {"invoice": "INV-20261023-024",
                                                              "date": "2026-10-23"}


def test_build_loan_set_terms():
    tx = C.build_loan_set("rBorrower", LB_ID, "rBroker", "10000000", 270, 8000)
    assert (tx.account, tx.counterparty) == ("rBorrower", "rBroker")
    assert (tx.payment_total, tx.payment_interval, tx.grace_period) == (3, 90, 60)
    assert tx.interest_rate == 8000 and tx.fee == C.LOAN_SET_FEE
    assert C.build_loan_set("rB", LB_ID, "rK", "1", 60, 0).payment_total == 1


def _signed_blob(borrower: Wallet, broker_addr: str, **over) -> str:
    tx = C.build_loan_set(borrower.address, LB_ID, broker_addr, "10000000", 270, 8000)
    tx_json = {**tx.to_xrpl(), "Sequence": 1, "LastLedgerSequence": 100, **over}
    from xrpl.models.transactions import LoanSet
    return encode(sign(LoanSet.from_xrpl(tx_json), borrower).to_xrpl())


def test_verify_loan_set_blob():
    borrower, broker = Wallet.create(), Wallet.create()
    accounts = {"accounts": {"broker": broker.address}, "loanBrokerId": LB_ID}
    req = {"borrower": borrower.address, "principalDrops": "10000000", "termSeconds": 270}
    policy = {"interestRateBps": 800}
    assert C.verify_loan_set_blob(_signed_blob(borrower, broker.address), req, accounts, policy) is None
    other = Wallet.create().address
    assert C.verify_loan_set_blob(_signed_blob(borrower, other), req, accounts, policy) \
        == "blob_mismatch:Counterparty"
    assert C.verify_loan_set_blob(_signed_blob(borrower, broker.address, Fee="12"), req, accounts,
                                  policy) == "blob_mismatch:Fee"
    assert C.verify_loan_set_blob(_signed_blob(borrower, broker.address), {**req, "principalDrops": "9"},
                                  accounts, policy) == "blob_mismatch:PrincipalRequested"
    assert C.verify_loan_set_blob("zz", req, accounts, policy).startswith("undecodable_blob")
    assert decode(_signed_blob(borrower, broker.address))["Account"] == borrower.address


def test_loan_item_status_and_units():
    base = {"index": "AB", "Borrower": "r1", "PrincipalOutstanding": "10000000",
            "TotalValueOutstanding": "10000005", "PeriodicPayment": "3333334.855405329915",
            "InterestRate": 8000, "PaymentInterval": 90, "GracePeriod": 60,
            "NextPaymentDueDate": 846144010, "PaymentRemaining": 3, "StartDate": 846143920, "Flags": 0}
    item = C.loan_item(base)
    assert item["periodicPaymentDrops"] == "3333335"
    assert item["nextPaymentDue"] == 846144010 + C.RIPPLE_EPOCH
    assert item["status"] == "active"
    assert C.loan_item({**base, "Flags": 0x10000})["status"] == "defaulted"
    assert C.loan_item({**base, "Flags": 0x20000})["status"] == "impaired"
    assert C.loan_item({**base, "PaymentRemaining": 0})["status"] == "paid"


def test_accounts_json_has_no_seed():
    accounts, env = LENDING / "accounts.json", LENDING / ".env"
    if not accounts.exists():
        pytest.skip("setup.py not run yet")
    text = accounts.read_text()
    assert not re.search(r'"s[1-9A-HJ-NP-Za-km-z]{24,}"', text)  # no XRPL family seed string
    for value in C.read_env().values() if env.exists() else []:
        assert not value or value not in text


def test_write_accounts_refuses_seed(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("BROKER_SEED=FAKESEED_NOT_REAL_123\n")
    monkeypatch.setattr(C, "ENV_PATH", env)
    monkeypatch.setattr(C, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    with pytest.raises(RuntimeError):
        C.write_accounts({"oops": "FAKESEED_NOT_REAL_123"})
    C.write_accounts({"ok": True})
    assert json.loads((tmp_path / "accounts.json").read_text()) == {"ok": True}


def _flip_sig(sig: str) -> str:
    return sig[:-1] + ("0" if sig[-1] != "0" else "1")


def test_verify_loan_set_blob_signature():
    """A real offline-signed blob passes; a tampered signature, a victim's pubkey with a garbage signature and a
    blob signed by another key all return blob_mismatch:bad_signature (a reason, never an exception)."""
    borrower, broker, mallory = Wallet.create(), Wallet.create(), Wallet.create()
    accounts = {"accounts": {"broker": broker.address}, "loanBrokerId": LB_ID}
    req = {"borrower": borrower.address, "principalDrops": "10000000", "termSeconds": 270}
    policy = {"interestRateBps": 800}
    good = _signed_blob(borrower, broker.address)
    assert C.verify_loan_set_blob(good, req, accounts, policy) is None
    tx = decode(good)
    tampered = encode({**tx, "TxnSignature": _flip_sig(tx["TxnSignature"])})
    garbage = encode({**tx, "SigningPubKey": borrower.public_key, "TxnSignature": "00" * 70})
    forged = encode({**decode(_signed_blob(mallory, broker.address)), "Account": borrower.address})
    other_terms = encode({**tx, "PrincipalRequested": "10000000", "Sequence": 2})  # fields match, signature does not
    for blob in (tampered, garbage, forged, other_terms):
        assert C.verify_loan_set_blob(blob, req, accounts, policy) == "blob_mismatch:bad_signature"
    assert C.signed_by_account({"Account": borrower.address}) is False  # missing fields: False, no KeyError


def test_wait_for_tx_exits_on_the_ledger_not_the_clock(monkeypatch):
    """A tx that never validates ends when the validated ledger passes its LastLedgerSequence, with the wall clock
    frozen: the 300 s timeout is only a backstop past the 60-ledger horizon."""
    assert C.WAIT_TIMEOUT_S == 300 and C.wait_for_tx.__defaults__ == (300,)
    monkeypatch.setattr(C, "_rpc", lambda req: {"error": "txnNotFound"})
    ledgers = iter(range(95, 200))
    seen = []

    def current_ledger_index():
        seen.append(next(ledgers))
        return seen[-1]

    monkeypatch.setattr(C, "current_ledger_index", current_ledger_index)
    monkeypatch.setattr(C.time, "time", lambda: 1_000_000.0)   # the deadline can never fire
    monkeypatch.setattr(C.time, "sleep", lambda s: None)
    out = C.wait_for_tx("AB" * 32, 100)
    assert out == {"hash": "AB" * 32, "engineResult": "txnNotFound", "validated": False, "ledgerIndex": None,
                   "created": {}}
    assert seen[-1] == 101 and len(seen) == 7  # 95..100 keep waiting, 101 > LastLedgerSequence ends it


def test_wait_for_tx_backstop_says_timeout_waiting(monkeypatch):
    """The 300 s wall clock fires while the ledger is still at or below LastLedgerSequence: a distinct reason
    (timeout_waiting), not the expired-before-validation one."""
    monkeypatch.setattr(C, "_rpc", lambda req: {"error": "txnNotFound"})
    monkeypatch.setattr(C, "current_ledger_index", lambda: 50)  # never passes LastLedgerSequence 100
    clock = iter([1_000_000.0, 1_000_100.0, 1_000_301.0])
    monkeypatch.setattr(C.time, "time", lambda: next(clock))
    monkeypatch.setattr(C.time, "sleep", lambda s: None)
    out = C.wait_for_tx("AB" * 32, 100)
    assert out == {"hash": "AB" * 32, "engineResult": "timeout_waiting", "validated": False, "ledgerIndex": None,
                   "created": {}}


def test_borrower_post_timeout_covers_two_waits():
    import borrower
    assert borrower.POST_TIMEOUT_S > 2 * C.WAIT_TIMEOUT_S
