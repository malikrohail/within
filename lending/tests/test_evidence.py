"""Offline evidence parsing: canned devnet-shaped (api_version 2) JSON, no network."""
import datetime as dt
import json

import pytest

import evidence
import policy

B = "rBorrowerXXXXXXXXXXXXXXXXXXXXXXXXX"
BROKER = "rBrokerXXXXXXXXXXXXXXXXXXXXXXXXXXX"
C1, C2, C3 = "rCust1", "rCust2", "rCust3"
FAUCET = "rht5xsioM3iix1hx4i2zJX2WJ1JDTwLGJe"
NOW = int(dt.datetime(2026, 10, 24, 12, tzinfo=dt.timezone.utc).timestamp())
XRP = 1_000_000
ORIG_PLAID_KEYS = evidence._plaid_keys


def memo(date):
    data = json.dumps({"invoice": "INV-1", "date": date}).encode().hex().upper()
    return [{"Memo": {"MemoType": "invoice".encode().hex().upper(), "MemoData": data}}]


def ripple(y, m, d):
    return int(dt.datetime(y, m, d, 15, tzinfo=dt.timezone.utc).timestamp()) - evidence.RIPPLE_EPOCH


def pay(h, sender, drops, date=None, li=1000, result="tesSUCCESS", dest=B, close=(2026, 10, 24), extra_nodes=(),
        amount=None):
    tx = {"TransactionType": "Payment", "Account": sender, "Destination": dest, "DeliverMax": str(drops),
          "date": ripple(*close)}
    if date:
        tx["Memos"] = memo(date)
    meta = {"TransactionResult": result, "AffectedNodes": list(extra_nodes),
            "delivered_amount": amount if amount is not None else str(drops)}
    return {"hash": h, "ledger_index": li, "validated": True, "tx_json": tx, "meta": meta,
            "close_time_iso": "2026-10-24T07:44:12Z"}


CREATE_B = {"CreatedNode": {"LedgerEntryType": "AccountRoot", "LedgerIndex": "X", "NewFields": {"Account": B}}}
TXS = [  # newest first
    pay("H1", C1, 3 * XRP, "2026-10-24", li=1100),
    pay("H2", C2, 2 * XRP, "2026-10-24", li=1099),     # same day as H1
    pay("H3", C1, 1 * XRP, "2026-10-20", li=1098),
    pay("H4", C3, 4 * XRP, "2026-09-24", li=1097),     # exactly 30 days back: inside (inclusive)
    pay("H5", C3, 9 * XRP, "2026-09-23", li=1096),     # 31 days back: outside
    pay("H6", C2, 7 * XRP, "2026-10-25", li=1095),     # future-dated invoice: outside
    pay("H7", C2, 5 * XRP, None, li=1094, close=(2026, 10, 22)),   # no memo -> close-time day 10-22
    pay("H8", C1, 5 * XRP, "2026-10-21", result="tecUNFUNDED_PAYMENT", li=1093),
    pay("H9", C1, 5 * XRP, "2026-10-21", dest="rSomeoneElse", li=1092),
    pay("H10", B, 5 * XRP, "2026-10-21", li=1091),     # self
    pay("H11", C1, 5 * XRP, "2026-10-21", amount={"currency": "USD", "issuer": C2, "value": "5"}, li=1090),
    pay("H12", FAUCET, 100 * XRP, None, li=1050),     # faucet top-up
    pay("H13", "rOtherFaucet", 100 * XRP, None, li=1000, extra_nodes=[CREATE_B]),  # account-creating payment
]


class FakeLedger:
    def __init__(self, txs=TXS, objects=(), broker_objects=(), exists=True, page=5):
        self.txs, self.objects, self.broker_objects, self.exists, self.page = list(txs), list(objects), \
            list(broker_objects), exists, page
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method == "account_info":
            if not self.exists:
                return {"error": "actNotFound", "status": "error"}
            return {"account_data": {"Account": B}, "ledger_index": 1500, "validated": True}
        if method == "account_tx":
            start = int(params.get("marker", 0))
            res = {"transactions": self.txs[start:start + self.page]}
            if start + self.page < len(self.txs):
                res["marker"] = start + self.page
            return res
        if method == "account_objects":
            return {"account_objects": self.objects if params["account"] == B else self.broker_objects}
        raise AssertionError(method)


@pytest.fixture(autouse=True)
def no_accounts_no_plaid(monkeypatch):
    monkeypatch.setattr(evidence, "_broker_address", lambda: None)
    monkeypatch.setattr(evidence, "_demo_borrower", lambda: None)
    monkeypatch.setattr(evidence, "_plaid_keys", lambda: None)
    evidence._bank_cache.clear()


def test_ledger_parsing():
    fake = FakeLedger()
    led = evidence.ledger_evidence(B, fake, NOW, 30)
    # counted: H1 C1 3, H2 C2 2, H3 C1 1, H4 C3 4, H7 C2 5 -> 15 XRP
    assert led["inboundPaymentCount"] == 5
    assert led["inboundVolumeDrops"] == str(15 * XRP)
    assert led["distinctPayers"] == 3
    assert led["topPayerSharePct"] == round(100 * 7 / 15, 1) == 46.7  # C2 = 2 + 5
    assert led["activeDays"] == 4  # 10-24, 10-20, 09-24, 10-22
    assert led["memoDatedPayments"] == 4  # H1-H4; H7 has no memo
    assert led["ledgerActiveDays"] == 2  # close dates of the eligible payments: 10-24 (H1-H6), 10-22 (H7)
    assert led["sampleTxHashes"] == ["H1", "H2", "H3", "H4", "H7"]
    assert led["accountAgeLedgers"] == 1500 - 1000  # from the account-creating payment
    assert led["accountExists"] is True
    assert (led["activeLoans"], led["pastDefaults"], led["hasAcceptedCredential"]) == (0, 0, False)
    # paginated with marker
    markers = [p.get("marker") for m, p in fake.calls if m == "account_tx"]
    assert markers == [None, 5, 10]


def test_window_is_configurable():
    led = evidence.ledger_evidence(B, FakeLedger(), NOW, 3)  # 10-21..10-24
    assert led["inboundPaymentCount"] == 3 and led["activeDays"] == 2  # H1, H2, H7


def test_faucet_and_creating_payment_excluded():
    led = evidence.ledger_evidence(B, FakeLedger(txs=[TXS[11], TXS[12]]), NOW, 30)
    assert led["inboundPaymentCount"] == 0 and led["inboundVolumeDrops"] == "0" and led["topPayerSharePct"] == 0.0


def test_missing_account():
    led = evidence.ledger_evidence(B, FakeLedger(exists=False), NOW, 30)
    assert led["accountExists"] is False and led["inboundPaymentCount"] == 0


@pytest.mark.parametrize("err", ["tooBusy", "slowDown", "lgrNotFound", "noNetwork"])
def test_transient_account_info_error_raises(err):
    def client(method, params):
        if method == "account_info":
            return {"error": err, "status": "error"}
        return FakeLedger()(method, params)
    with pytest.raises(RuntimeError, match=err):
        evidence.ledger_evidence(B, client, NOW, 30)


def test_account_info_without_account_data_raises():
    with pytest.raises(RuntimeError):
        evidence.ledger_evidence(B, lambda m, p: {"status": "success"}, NOW, 30)


def test_rpc_retries_too_busy_once(monkeypatch):
    replies = [{"error": "tooBusy", "status": "error"}, {"account_data": {"Account": B}, "status": "success"}]
    posts = []

    class Resp:
        def __init__(self, result):
            self.result = result

        def raise_for_status(self):
            pass

        def json(self):
            return {"result": self.result}

    def post(url, json, timeout):
        posts.append(url)
        return Resp(replies[len(posts) - 1])

    monkeypatch.setattr(evidence.requests, "post", post)
    monkeypatch.setattr(evidence.time, "sleep", lambda s: None)
    assert "account_data" in evidence._rpc(None, "account_info", {"account": B})
    assert len(posts) == 2


def loan(index, flags=0, remaining=2, owed="10500000", borrower=B):
    return {"LedgerEntryType": "Loan", "index": index, "Borrower": borrower, "Flags": flags,
            "PaymentRemaining": remaining, "TotalValueOutstanding": owed, "PrincipalOutstanding": "10000000"}


def kyb(**kw):
    """Broker-issued, accepted kyb-borrower Credential; kw overrides any field (None removes it)."""
    c = {"LedgerEntryType": "Credential", "Subject": B, "Issuer": BROKER, "CredentialType": evidence.KYB_CREDENTIAL_TYPE,
         "Flags": evidence.LSF_CREDENTIAL_ACCEPTED, "index": "C1"}
    c.update(kw)
    return {k: v for k, v in c.items() if v is not None}


def test_loan_flags_to_active_and_defaults(monkeypatch):
    monkeypatch.setattr(evidence, "_broker_address", lambda: BROKER)
    objs = [loan("L1"), loan("L2", flags=evidence.LSF_LOAN_IMPAIRED, owed="5000000.4"), loan("L3", flags=0x10000),
            loan("L4", remaining=0, owed="0"), loan("L5", borrower="rOther"), kyb()]
    led = evidence.ledger_evidence(B, FakeLedger(txs=[], objects=objs), NOW, 30)
    assert led["activeLoans"] == 2  # active + impaired
    assert led["loanDebtDrops"] == str(10500000 + 5000000)
    assert led["loanPrincipalDrops"] == str(2 * 10000000)  # same loans, PrincipalOutstanding (policy guard)
    assert led["pastDefaults"] == 1
    assert led["hasAcceptedCredential"] is True


@pytest.mark.parametrize("cred, counted", [
    (kyb(), True),
    (kyb(CredentialType=evidence.KYB_CREDENTIAL_TYPE.lower()), True),        # hex case does not matter
    (kyb(Expiration=NOW - evidence.RIPPLE_EPOCH + 60), True),               # expires in a minute
    (kyb(Flags=0), False),                                                   # issued, not accepted
    (kyb(Issuer="rSomeoneElse"), False),                                     # not the broker
    (kyb(Issuer=None), False),
    (kyb(CredentialType="unrelated".encode().hex()), False),                 # wrong type
    (kyb(Expiration=NOW - evidence.RIPPLE_EPOCH), False),                    # expired at asOf
    (kyb(Subject="rOther"), False),
])
def test_only_broker_kyb_credential_counts(monkeypatch, cred, counted):
    monkeypatch.setattr(evidence, "_broker_address", lambda: BROKER)
    led = evidence.ledger_evidence(B, FakeLedger(txs=[], objects=[cred]), NOW, 30)
    assert led["hasAcceptedCredential"] is counted
    # the Why panel's credential line: issuer + plain type only when the broker credential counts
    assert (led.get("credentialIssuer"), led.get("credentialType")) == ((BROKER, "kyb-borrower") if counted else (None, None))


def test_no_broker_address_no_credential(monkeypatch):
    monkeypatch.setattr(evidence, "_broker_address", lambda: None)
    assert evidence.ledger_evidence(B, FakeLedger(txs=[], objects=[kyb()]), NOW, 30)["hasAcceptedCredential"] is False


def test_ons_unrelated_expired_credential_no_longer_lifts_to_auto(monkeypatch):
    """Upstream review case: 24 same-day payments from 4 payers score 69 (hold); an unrelated,
    expired, accepted Credential lifted it to 82 (auto). It must not count now."""
    monkeypatch.setattr(evidence, "_broker_address", lambda: BROKER)  # the real broker: still must not count
    txs = [pay(f"{i + 1:064X}", f"rPayer{i % 4}", 3 * XRP, None, li=1000) for i in range(24)]
    unrelated = {"LedgerEntryType": "Credential", "Subject": B, "Issuer": "rUntrustedIssuer",
                 "CredentialType": "unrelated".encode().hex(), "Flags": evidence.LSF_CREDENTIAL_ACCEPTED,
                 "Expiration": NOW - evidence.RIPPLE_EPOCH - 60, "index": "CX"}
    declared = {"principalDrops": str(10 * XRP), "existingDebtDrops": "0", "termSeconds": 270, "purpose": "inventory"}
    vault = {"assetsTotalDrops": str(180 * XRP), "loansOutstandingDrops": "0", "debtTotalDrops": "0",
             "coverDrops": str(20 * XRP)}
    out = []
    for objs in ([], [unrelated]):
        led = evidence.ledger_evidence(B, FakeLedger(txs=txs, objects=objs), NOW, 30)
        ev = {"ledger": led, "bank": None, "declared": declared}
        out.append((led["hasAcceptedCredential"],
                    policy.decide({"principalDrops": str(10 * XRP), "evidence": ev}, vault, policy.DEFAULT_POLICY)))
    assert [(c, d["score"], d["decision"]) for c, d in out] == [(False, 69, "hold"), (False, 69, "hold")]


def test_ons_backdated_memos_blocked_at_tolerance_7(monkeypatch):
    """Upstream review case: 24 payments closed the same day, 4 payers, score 69 (hold);
    invoice memos backdated one day each lifted it to 24 active days, 87 (auto). At MEMO_DATE_TOLERANCE_DAYS=7
    only memos within 7 days of the close date count (8 days, below the >=10 bucket), so it stays 69 (hold)."""
    txs = [pay(f"{i + 1:064X}", f"rPayer{i % 4}", 3 * XRP, (dt.date(2026, 10, 24) - dt.timedelta(days=i)).isoformat())
           for i in range(24)]
    declared = {"principalDrops": str(10 * XRP), "existingDebtDrops": "0", "termSeconds": 270, "purpose": "inventory"}
    vault = {"assetsTotalDrops": str(180 * XRP), "loansOutstandingDrops": "0", "debtTotalDrops": "0",
             "coverDrops": str(20 * XRP)}
    out = []
    for tolerance in (None, "7"):
        if tolerance is None:
            monkeypatch.delenv("MEMO_DATE_TOLERANCE_DAYS", raising=False)
        else:
            monkeypatch.setenv("MEMO_DATE_TOLERANCE_DAYS", tolerance)
        led = evidence.ledger_evidence(B, FakeLedger(txs=txs), NOW, 30)
        d = policy.decide({"principalDrops": str(10 * XRP), "evidence": {"ledger": led, "bank": None,
                                                                         "declared": declared}},
                          vault, policy.DEFAULT_POLICY)
        out.append((led["activeDays"], led["memoDatedPayments"], led["ledgerActiveDays"], d["score"], d["decision"]))
    assert out == [(24, 24, 1, 87, "auto"), (8, 8, 1, 69, "hold")]


def test_loans_in_broker_directory_deduped(monkeypatch):
    monkeypatch.setattr(evidence, "_broker_address", lambda: BROKER)
    fake = FakeLedger(txs=[], objects=[loan("L1")], broker_objects=[loan("L1"), loan("L2"), loan("L9", borrower="rX"),
                                                                    {"LedgerEntryType": "LoanBroker", "index": "LB"}])
    led = evidence.ledger_evidence(B, fake, NOW, 30)
    assert led["activeLoans"] == 2


def test_defaulted_loan_seen_only_in_tx_meta():
    node = {"ModifiedNode": {"LedgerEntryType": "Loan", "LedgerIndex": "LD",
                             "FinalFields": {"Borrower": B, "Flags": 0x10000}}}
    tx = {"hash": "HM", "ledger_index": 1200, "validated": True,
          "tx_json": {"TransactionType": "LoanManage", "Account": BROKER, "date": ripple(2026, 10, 24)},
          "meta": {"TransactionResult": "tesSUCCESS", "AffectedNodes": [node]}}
    led = evidence.ledger_evidence(B, FakeLedger(txs=[tx], objects=[loan("LD", flags=0x10000)]), NOW, 30)
    assert led["pastDefaults"] == 1  # same loan in meta and objects counted once


def test_v1_tx_shape_supported():
    entry = pay("HV1", C1, 2 * XRP, "2026-10-23")
    entry["tx"] = entry.pop("tx_json")
    led = evidence.ledger_evidence(B, FakeLedger(txs=[entry]), NOW, 30)
    assert led["inboundPaymentCount"] == 1


def test_build_evidence_shape_and_score():
    e = evidence.build_evidence(B, {"purpose": "inventory", "principalDrops": str(1 * XRP), "termSeconds": 270,
                                    "existingDebtDrops": "0"}, client=FakeLedger(), now=NOW)
    assert set(e) == {"borrower", "asOf", "windowDays", "ledger", "bank", "declared"}
    assert e["bank"] is None and e["asOf"] == NOW and e["windowDays"] == 30
    assert e["declared"] == {"purpose": "inventory", "principalDrops": "1000000", "termSeconds": 270,
                             "existingDebtDrops": "0"}
    json.dumps(e)
    assert 0 <= policy.score(e) <= 100


def test_build_evidence_matches_good_small_buckets():
    """A history shaped like setup.py's lands on GOOD_SMALL's score."""
    payers = ["rA", "rB", "rC", "rD", "rE"]
    amounts = [3, 2, 4, 1, 5, 2, 3, 1, 4, 2, 3, 5, 2, 1, 3, 4, 2, 3, 1, 2, 4, 3, 2, 0]
    txs, day = [], 0
    for i, a in enumerate(amounts[:22]):
        day += 1 if i % 4 else 2  # some days skipped
        date = (dt.date(2026, 10, 24) - dt.timedelta(days=day - 1)).isoformat()
        txs.append(pay(f"S{i}", payers[i % 5], a * XRP + 500000, date, li=2000 - i))
    e = evidence.build_evidence(B, policy.GOOD_SMALL["declared"], client=FakeLedger(txs=txs), now=NOW)
    led = e["ledger"]
    assert led["activeDays"] >= 20 and led["distinctPayers"] == 5 and int(led["inboundVolumeDrops"]) >= 50 * XRP
    assert policy.score(e) == 85


def test_devnet_only_guard():
    class Testnet:
        url = "https://s.altnet.rippletest.net:51234/"
    with pytest.raises(ValueError):
        evidence.ledger_evidence(B, Testnet(), NOW, 30)


# ---------------------------------------------------------------- Plaid (requests mocked, no keys)
class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


PLAID_TX = {"accounts": [{"type": "depository", "balances": {"current": 1000}},
                         {"type": "depository", "balances": {"current": 3000}},
                         {"type": "credit", "balances": {"current": 99999}}],
            "transactions": [{"amount": -9000, "name": "Payroll deposit"}, {"amount": -6000, "name": "ACH credit"},
                             {"amount": 5000, "name": "Rent"}, {"amount": 4000, "name": "Supplies"},
                             {"amount": 35, "name": "Overdraft fee", "category": ["Bank Fees", "Overdraft"]}]}


@pytest.fixture
def plaid_on(monkeypatch):
    monkeypatch.setattr(evidence, "_plaid_keys", lambda: ("cid", "sek"))
    monkeypatch.setattr(evidence, "_demo_borrower", lambda: B)
    monkeypatch.setattr(evidence.time, "sleep", lambda s: None)
    calls = []

    def install(responses):
        it = iter(responses)

        def post(url, json=None, timeout=None):
            calls.append((url, json))
            return next(it)
        monkeypatch.setattr(evidence.requests, "post", post)
        return calls
    return install


def test_plaid_happy_path_with_retry(plaid_on):
    calls = plaid_on([Resp(200, {"public_token": "pub"}), Resp(200, {"access_token": "acc"}),
                      Resp(400, {"error_code": "PRODUCT_NOT_READY"}), Resp(400, {"error_code": "PRODUCT_NOT_READY"}),
                      Resp(200, PLAID_TX)])
    bank = evidence.bank_evidence(B)
    assert bank == {"connected": True, "institution": "ins_109508", "days": 90,
                    "avgMonthlyInflowUsd": 5000.0, "avgBalanceUsd": 2000.0,
                    "inflowOutflowRatio": round(15000 / 9035, 2), "nsfCount": 1}
    paths = [u.replace(evidence.PLAID_URL, "") for u, _ in calls]
    assert paths == ["/sandbox/public_token/create", "/item/public_token/exchange"] + ["/transactions/get"] * 3
    assert calls[0][1]["institution_id"] == "ins_109508" and calls[0][1]["initial_products"] == ["transactions"]
    assert calls[1][1]["public_token"] == "pub" and calls[2][1]["access_token"] == "acc"
    assert "sek" not in json.dumps(bank) and "cid" not in json.dumps(bank)
    # cached: no second round of calls
    assert evidence.bank_evidence(B) == bank and len(calls) == 5


def test_plaid_bank_feeds_60_30_10(plaid_on):
    plaid_on([Resp(200, {"public_token": "p"}), Resp(200, {"access_token": "a"}), Resp(200, PLAID_TX)])
    e = evidence.build_evidence(B, policy.GOOD_SMALL["declared"], client=FakeLedger(), now=NOW)
    assert e["bank"]["connected"] is True
    assert policy.score_breakdown(e)["weights"] == {"ledger": 60, "bank": 30, "declared": 10}


def test_plaid_only_for_demo_borrower(plaid_on):
    calls = plaid_on([])
    assert evidence.bank_evidence("rFreshAccount") is None and calls == []


def test_plaid_error_gives_none(plaid_on, capsys):
    plaid_on([Resp(400, {"error_code": "INVALID_API_KEYS"})])
    assert evidence.bank_evidence(B) is None
    assert "sek" not in capsys.readouterr().out


def test_plaid_not_ready_gives_up(plaid_on):
    plaid_on([Resp(200, {"public_token": "p"}), Resp(200, {"access_token": "a"})]
             + [Resp(400, {"error_code": "PRODUCT_NOT_READY"})] * evidence.PLAID_RETRIES)
    assert evidence.bank_evidence(B) is None


def test_no_keys_no_bank(monkeypatch):
    monkeypatch.setattr(evidence, "_demo_borrower", lambda: B)
    monkeypatch.setattr(evidence.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    assert evidence.bank_evidence(B) is None


def test_plaid_keys_read_from_lending_env(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "HERE", tmp_path)
    assert ORIG_PLAID_KEYS() is None
    (tmp_path / ".env").write_text("BORROWER_SEED=x\nPLAID_CLIENT_ID=cid\n")
    assert ORIG_PLAID_KEYS() is None
    (tmp_path / ".env").write_text("PLAID_CLIENT_ID=cid\nPLAID_SECRET=sek\n")
    assert ORIG_PLAID_KEYS() == ("cid", "sek")


def x402memo(text):
    return [{"Memo": {"MemoType": "x402".encode().hex().upper(), "MemoData": text.encode().hex().upper()}}]


def test_x402_income_split_and_score_unchanged():
    """Memo'd (invoice / x402) inbound = x402 income, the rest = other inbound; score unchanged."""
    bare = pay("X1", C1, 6 * XRP, None, li=1100)                       # no memo: other inbound
    x402 = pay("X2", C2, 4 * XRP, None, li=1099); x402["tx_json"]["Memos"] = x402memo("receipt 42")
    blank = pay("X3", C3, 2 * XRP, None, li=1098); blank["tx_json"]["Memos"] = x402memo("   ")   # empty: not x402
    bad = pay("X4", C3, 1 * XRP, None, li=1097)
    bad["tx_json"]["Memos"] = [{"Memo": {"MemoType": "invoice".encode().hex().upper(), "MemoData": "ZZ"}}]  # undecodable
    txs = [pay("H1", C1, 3 * XRP, "2026-10-24", li=1101), bare, x402, blank, bad,
           pay("H7", C2, 5 * XRP, "2026-10-22", li=1096)]
    led = evidence.ledger_evidence(B, FakeLedger(txs), NOW, 30)
    assert led["inboundPaymentCount"] == 6 and led["inboundVolumeDrops"] == str(21 * XRP)
    assert led["x402IncomeDrops"] == str(12 * XRP) and led["x402Payments"] == 3 and led["x402Payers"] == 2  # H1 C1, X2 C2, H7 C2
    assert led["otherInboundDrops"] == str(9 * XRP)                                                        # X1, X3, X4
    assert int(led["x402IncomeDrops"]) + int(led["otherInboundDrops"]) == int(led["inboundVolumeDrops"])
    with_keys = policy.score({"ledger": led, "bank": None, "declared": {}})
    without = policy.score({"ledger": {k: v for k, v in led.items() if not k.startswith(("x402", "otherInbound"))},
                            "bank": None, "declared": {}})
    assert with_keys == without


def test_x402_keys_present_when_no_payments():
    led = evidence.ledger_evidence(B, FakeLedger([]), NOW, 30)
    assert (led["x402IncomeDrops"], led["x402Payments"], led["x402Payers"], led["otherInboundDrops"]) == ("0", 0, 0, "0")
    assert evidence.ledger_evidence(B, FakeLedger(exists=False), NOW, 30)["x402Payments"] == 0
