"""batch/working_capital.py offline (INTERFACES.md §8). No network: fixed sequences and fee."""
import copy

import pytest
from xrpl.core.binarycodec import decode, encode
from xrpl.models.transactions import Transaction
from xrpl.wallet import Wallet

import policy as pol
from batch import working_capital as W

XRP = 1_000_000
LB = "9A4C18DF8CC19294ACC631B844231F235372E67FBC12A745DB49780A436610B3"


@pytest.fixture(scope="module")
def built():
    borrower, supplier, broker = Wallet.create(), Wallet.create(), Wallet.create()
    terms = {"loanBrokerId": LB, "principalDrops": str(5 * XRP), "termSeconds": 270,
             "interestRate": pol.DEFAULT_POLICY["interestRateBps"] * 10}
    out = W.build_working_capital_batch(borrower, terms, supplier.address, str(3 * XRP), str(1 * XRP), "INV-WC-1",
                                        broker.address, sequence=100, last_ledger_sequence=5000, batch_fee="40")
    body = {"borrower": borrower.address,
            "disbursement": {"supplier": supplier.address, "supplierDrops": str(3 * XRP),
                             "feeDrops": str(1 * XRP), "invoice": "INV-WC-1"}}
    return {"out": out, "body": body, "accounts": {"accounts": {"broker": broker.address}, "loanBrokerId": LB},
            "broker": broker.address, "supplier": supplier.address, "borrower": borrower.address}


def verify(b, batch_blob=None, loan_blob=None, body=None):
    return W.verify_working_capital_batch(batch_blob or b["out"]["signedBatch"], loan_blob or b["out"]["signedLoanSet"],
                                          body or b["body"], b["accounts"])


def tamper(blob, fn):
    tx = copy.deepcopy(decode(blob))
    fn(tx)
    return encode(tx)


def test_build_shape(built):
    out = built["out"]
    loan, batch = decode(out["signedLoanSet"]), decode(out["signedBatch"])
    assert out["loanSetSequence"] == 100
    assert loan["TransactionType"] == "LoanSet" and loan["Sequence"] == 100 and loan["Fee"] == "30"
    assert loan["LastLedgerSequence"] == 5000 and loan["Account"] == built["borrower"]
    assert loan["Counterparty"] == built["broker"] and loan["PrincipalRequested"] == str(5 * XRP)
    assert batch["TransactionType"] == "Batch" and batch["Sequence"] == 101 and batch["LastLedgerSequence"] == 5000
    assert batch["Flags"] == 0x10000 and batch["Fee"] == "40" and batch["TxnSignature"] and "BatchSigners" not in batch
    raws = [r["RawTransaction"] for r in batch["RawTransactions"]]
    assert [r["Sequence"] for r in raws] == [102, 103]
    assert all(r["Flags"] == 0x40000000 and r["Fee"] == "0" and r["SigningPubKey"] == "" for r in raws)
    assert [(r["Destination"], r["Amount"]) for r in raws] == [(built["supplier"], str(3 * XRP)),
                                                              (built["broker"], str(1 * XRP))]
    assert out["innerHashes"] == [Transaction.from_xrpl(r).get_hash() for r in raws]
    assert out["batchHash"] == Transaction.from_xrpl(batch).get_hash()


def test_round_trip_verifies(built):
    assert verify(built) is None


@pytest.mark.parametrize("reason,fn", [
    ("not_batch", lambda t: t.update(TransactionType="Payment")),
    ("flags", lambda t: t.update(Flags=0x20000)),                                    # tfOnlyOne
    ("flags", lambda t: t["RawTransactions"][0]["RawTransaction"].update(Flags=0x40020000)),  # + partial payment
    ("account", lambda t: t.update(Account="rEH59tesggzmgg42PeHvByQQ3kmUNhegVw")),
    ("account", lambda t: t["RawTransactions"][1]["RawTransaction"].update(Account="rEH59tesggzmgg42PeHvByQQ3kmUNhegVw")),
    ("sequence", lambda t: t.update(Sequence=105)),
    ("sequence", lambda t: t["RawTransactions"][1]["RawTransaction"].update(Sequence=110)),
    ("inner_count", lambda t: t["RawTransactions"].pop()),
    ("destination", lambda t: t["RawTransactions"][0]["RawTransaction"].update(Destination="rEH59tesggzmgg42PeHvByQQ3kmUNhegVw")),
    ("amount", lambda t: t["RawTransactions"][0]["RawTransaction"].update(Amount=str(4 * XRP))),
    ("amount", lambda t: t["RawTransactions"][1]["RawTransaction"].update(Amount=str(2 * XRP))),
    ("memo", lambda t: t["RawTransactions"][0]["RawTransaction"].pop("Memos")),
    ("unsigned", lambda t: t.pop("TxnSignature")),
])
def test_tamper_reasons(built, reason, fn):
    assert verify(built, batch_blob=tamper(built["out"]["signedBatch"], fn)) == f"batch_mismatch:{reason}"


def test_body_mismatch_reasons(built):
    d = built["body"]["disbursement"]
    assert verify(built, body={**built["body"], "disbursement": {**d, "invoice": "INV-OTHER"}}) == "batch_mismatch:memo"
    assert verify(built, body={**built["body"], "disbursement": {**d, "feeDrops": "1"}}) == "batch_mismatch:amount"
    assert verify(built, body={**built["body"], "borrower": built["broker"]}) == "batch_mismatch:account"
    assert verify(built, batch_blob="ZZ") == "batch_mismatch:not_batch"
    other_loan = tamper(built["out"]["signedLoanSet"], lambda t: t.update(Sequence=7))
    assert verify(built, loan_blob=other_loan) == "batch_mismatch:sequence"


class FakeRpc:
    def __init__(self, table):
        self.table = table

    def __call__(self, h):
        return self.table.get(h, {"error": "txnNotFound"})


def _ledger_view(built, applied: bool):
    batch = decode(built["out"]["signedBatch"])
    outer = {"hash": built["out"]["batchHash"], "validated": True, "tx_json": batch,
             "meta": {"TransactionResult": "tesSUCCESS"}}
    table = {built["out"]["batchHash"]: outer}
    if applied:
        for h in built["out"]["innerHashes"]:
            table[h] = {"hash": h, "validated": True, "meta": {"TransactionResult": "tesSUCCESS"}}
    return table


def test_unfold_applied(built, monkeypatch):
    monkeypatch.setattr(W, "_tx", FakeRpc(_ledger_view(built, applied=True)))
    u = W.unfold_batch(built["out"]["batchHash"])
    assert u["validated"] and u["engineResult"] == "tesSUCCESS" and u["flags"] == 0x10000
    assert u["account"] == built["borrower"]
    assert [(l["index"], l["type"], l["destination"], l["amountDrops"], l["result"]) for l in u["legs"]] == [
        (0, "Payment", built["supplier"], str(3 * XRP), "tesSUCCESS"),
        (1, "Payment", built["broker"], str(1 * XRP), "tesSUCCESS")]
    assert [l["hash"] for l in u["legs"]] == built["out"]["innerHashes"]


def test_unfold_rolled_back_and_unknown(built, monkeypatch):
    monkeypatch.setattr(W, "_tx", FakeRpc(_ledger_view(built, applied=False)))
    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    u = W.unfold_batch(built["out"]["batchHash"])
    assert u["engineResult"] == "tesSUCCESS" and [l["result"] for l in u["legs"]] == ["not_applied", "not_applied"]
    assert W.unfold_batch("00" * 32) is None


def test_unfunded_is_a_desk_rule_not_a_signing_rule(built):
    """supplier + fee > principal still builds and verifies: batch_unfunded is the desk's policy refusal (§8)."""
    b, s, k = Wallet.create(), Wallet.create(), Wallet.create()
    terms = {"loanBrokerId": LB, "principalDrops": str(5 * XRP), "termSeconds": 270, "interestRate": 8000}
    out = W.build_working_capital_batch(b, terms, s.address, str(5 * XRP), str(1 * XRP), "INV-WC-2", k.address,
                                        sequence=7, last_ledger_sequence=99, batch_fee="40")
    body = {"borrower": b.address, "disbursement": {"supplier": s.address, "supplierDrops": str(5 * XRP),
                                                    "feeDrops": str(1 * XRP), "invoice": "INV-WC-2"}}
    assert W.verify_working_capital_batch(out["signedBatch"], out["signedLoanSet"], body,
                                          {"accounts": {"broker": k.address}}) is None


def test_signature_reasons(built):
    """The real offline-signed Batch passes (test_round_trip_verifies); a tampered signature, the borrower's pubkey
    with a garbage signature, and a Batch signed by another key are batch_mismatch:bad_signature, never a raise."""
    sig = decode(built["out"]["signedBatch"])["TxnSignature"]
    mallory = Wallet.create()
    flipped = tamper(built["out"]["signedBatch"], lambda t: t.update(TxnSignature=sig[:-1] + ("0" if sig[-1] != "0" else "1")))
    garbage = tamper(built["out"]["signedBatch"], lambda t: t.update(TxnSignature="00" * 70))
    other_key = tamper(built["out"]["signedBatch"], lambda t: t.update(SigningPubKey=mallory.public_key))
    edited = tamper(built["out"]["signedBatch"], lambda t: t.update(LastLedgerSequence=5001))  # unchecked field
    for blob in (flipped, garbage, other_key, edited):
        assert verify(built, batch_blob=blob) == "batch_mismatch:bad_signature"
