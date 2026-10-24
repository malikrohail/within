"""Offline tests for demo.py bookkeeping and borrower.py blob construction (no network)."""
from dataclasses import replace

from xrpl.core.binarycodec import decode, encode
from xrpl.transaction import sign
from xrpl.wallet import Wallet

import pytest

import borrower as B
import common as C
import demo as D
import policy
from batch import working_capital as wc

XRP = 1_000_000
BROKER = Wallet.create()
ACCOUNTS = {"accounts": {"broker": BROKER.address},
            "loanBrokerId": "E43DA4D38D7DA816256CA4947839187C41A113FC81AB5A3568B2C7BF7CB1CC91"}


def offline_sign(w, tx):
    tx = replace(tx, sequence=7, last_ledger_sequence=1000, fee=C.LOAN_SET_FEE)
    return encode(sign(tx, w).to_xrpl())


def body_for(w, principal="10000000", term=270):
    return B.build_request_body(w, principal, term, "inventory", "5000000", ACCOUNTS,
                                policy.DEFAULT_POLICY, sign=offline_sign)


# ---- Steps bookkeeping ------------------------------------------------------------
def test_all_nine_ok_exits_zero():
    lines = []
    s = D.Steps(out=lines.append)
    for n in range(1, 10):
        s.ok(n, "fine", "H" * 64)
    assert s.exit_code() == 0 and s.passed() == 9
    assert lines[0] == f"step 1 OK fine {'H' * 64}"


def test_one_fail_exits_one():
    s = D.Steps(out=lambda _: None)
    for n in range(1, 10):
        s.ok(n, "fine") if n != 5 else s.fail(n, "nope")
    assert s.exit_code() == 1 and s.passed() == 8


def test_missing_step_exits_one():
    s = D.Steps(out=lambda _: None)
    for n in range(1, 9):
        s.ok(n, "fine")
    assert s.exit_code() == 1


def test_seven_of_nine_is_not_enough():
    s = D.Steps(out=lambda _: None)
    for n in range(1, 8):
        s.ok(n, "fine")
    assert D.TOTAL_STEPS == 9 and s.exit_code() == 1


def test_working_capital_runs_before_the_default():
    order = list(D.RUN_ORDER)
    assert sorted(order + [1, 2]) == list(range(1, 10))
    assert order.index(8) < order.index(7) and order.index(9) < order.index(7) and order.index(8) < order.index(9)


def test_run_records_stepfail_and_exceptions_as_fail():
    lines = []
    s = D.Steps(out=lines.append)

    def boom():
        raise ValueError("devnet hiccup")

    def refuse():
        raise D.StepFail("expected auto, got held")

    assert s.run(1, lambda: ("VaultDeposit", ["ABC"])) is True
    assert s.run(2, refuse) is False
    assert s.run(3, boom) is False
    assert lines == ["step 1 OK VaultDeposit ABC", "step 2 FAIL expected auto, got held",
                     "step 3 FAIL ValueError: devnet hiccup"]
    assert s.exit_code() == 1


def test_ok_line_skips_empty_hashes():
    lines = []
    D.Steps(out=lines.append).ok(5, "refused score_too_low no tx")
    assert lines == ["step 5 OK refused score_too_low no tx"]


# ---- pure helpers -------------------------------------------------------------------
def test_needs_rotation():
    assert not D.needs_rotation({"ledger": {"activeLoans": 0, "pastDefaults": 0}})
    assert D.needs_rotation({"ledger": {"activeLoans": 1, "pastDefaults": 0}})
    assert D.needs_rotation({"ledger": {"activeLoans": 0, "pastDefaults": 1}})


def test_default_allowed_at_is_due_plus_grace_plus_margin():
    assert D.default_allowed_at({"nextPaymentDue": 1_000, "gracePeriod": 60}) == 1_065
    assert D.default_allowed_at({"nextPaymentDue": 1_000, "gracePeriod": 0}) == 1_000 + C.GRACE_PERIOD + 5


def test_find_loan_is_case_insensitive():
    loans = [{"loanId": "ABCD"}, {"loanId": "EF01"}]
    assert D.find_loan(loans, "ef01") == {"loanId": "EF01"}
    assert D.find_loan(loans, "9999") is None


def test_countdown_prints_every_tick_until_target():
    clock = {"t": 100}
    lines = []

    def sleep(s):
        clock["t"] += s

    D.countdown(125, "lending opens in {}s", now_fn=lambda: clock["t"], sleep=sleep, out=lines.append)
    assert lines == ["lending opens in 25s", "lending opens in 15s", "lending opens in 5s"]
    assert clock["t"] == 125


def test_evidence_tx_args():
    assert D.evidence_tx_args([("demo step 1 VaultDeposit A", "H1"), ("x", "H2")]) == \
        ["--tx", "demo step 1 VaultDeposit A=H1", "--tx", "x=H2"]


# ---- borrower blob ---------------------------------------------------------------------
def test_borrower_body_passes_desk_verifier():
    w = Wallet.create()
    body = body_for(w)
    req = {"borrower": body["borrower"], "principalDrops": body["principalDrops"], "termSeconds": body["termSeconds"]}
    assert C.verify_loan_set_blob(body["signedLoanSet"], req, ACCOUNTS, policy.DEFAULT_POLICY) is None
    assert body["declared"] == {"existingDebtDrops": "5000000"} and body["purpose"] == "inventory"


def test_borrower_blob_fields():
    w = Wallet.create()
    tx = decode(body_for(w, principal="60000000")["signedLoanSet"])
    assert tx["Account"] == w.address and tx["Counterparty"] == BROKER.address
    assert tx["PrincipalRequested"] == "60000000" and tx["InterestRate"] == 8000
    assert tx["PaymentTotal"] == 3 and tx["PaymentInterval"] == 90 and tx["GracePeriod"] == 60
    assert tx["Fee"] == "30" and "CounterpartySignature" not in tx and tx["TxnSignature"]


def test_principal_and_term_cannot_disagree_with_blob():
    w = Wallet.create()
    body = body_for(w, principal="10000000")
    req = {"borrower": w.address, "principalDrops": "60000000", "termSeconds": 270}
    assert C.verify_loan_set_blob(body["signedLoanSet"], req, ACCOUNTS,
                                  policy.DEFAULT_POLICY) == "blob_mismatch:PrincipalRequested"


# ---- working capital (INTERFACES §8) ------------------------------------------------------
def wc_body(w, supplier_drops=D.STEP8["supplier"], principal=D.STEP8["principal"], invoice="INV-WC-TEST"):
    supplier = Wallet.create().address
    dis = {"supplier": supplier, "supplierDrops": supplier_drops, "feeDrops": D.STEP8["fee"], "invoice": invoice}
    return B.build_working_capital_body(w, principal, D.TERM_SECONDS, "inventory", D.STEP8["debt"], dis,
                                        ACCOUNTS, policy.DEFAULT_POLICY, sequence=7, last_ledger_sequence=1000,
                                        batch_fee="4")


def test_working_capital_body_passes_both_desk_verifiers():
    w = Wallet.create()
    body, built = wc_body(w)
    req = {"borrower": body["borrower"], "principalDrops": body["principalDrops"], "termSeconds": body["termSeconds"]}
    assert C.verify_loan_set_blob(body["signedLoanSet"], req, ACCOUNTS, policy.DEFAULT_POLICY) is None
    assert wc.verify_working_capital_batch(body["signedBatch"], body["signedLoanSet"], body, ACCOUNTS) is None
    assert body["disbursement"]["supplierDrops"] == "55000000" and body["disbursement"]["feeDrops"] == "1000000"
    assert body["declared"] == {"existingDebtDrops": "70000000"} and body["principalDrops"] == "60000000"
    assert decode(body["signedLoanSet"])["Sequence"] == 7 and decode(body["signedBatch"])["Sequence"] == 8
    assert len(built["innerHashes"]) == 2 and len(built["batchHash"]) == 64


def test_unfunded_shape_still_verifies_so_the_desk_refuses_at_the_policy_layer():
    w = Wallet.create()
    body, _ = wc_body(w, supplier_drops=D.STEP9A_SUPPLIER)
    assert wc.verify_working_capital_batch(body["signedBatch"], body["signedLoanSet"], body, ACCOUNTS) is None
    d = body["disbursement"]
    assert int(d["supplierDrops"]) + int(d["feeDrops"]) > int(body["principalDrops"])  # -> batch_unfunded


def test_working_capital_body_never_carries_a_seed():
    w = Wallet.create()
    body, built = wc_body(w)
    import json
    assert w.seed not in json.dumps(body) and w.seed not in json.dumps(built)


# ---- step 9b drill --------------------------------------------------------------------------
NAMES = {"borrower": "rB", "supplier": "rS", "broker": "rK"}


def test_drill_lines_borrower_pays_only_the_fee():
    before = {"borrower": 100_000_000, "supplier": 50_000_000, "broker": 70_000_000}
    after = {"borrower": 99_999_996, "supplier": 50_000_000, "broker": 70_000_000}
    lines = D.drill_lines(NAMES, before, after, 4)
    assert lines == [
        "borrower rB balance 100000000 -> 99999996 drops: unchanged apart from the 4-drop Batch network fee",
        "supplier rS balance 50000000 -> 50000000 drops: unchanged",
        "broker rK balance 70000000 -> 70000000 drops: unchanged"]
    assert not any("vault unchanged" in x for x in lines)


@pytest.mark.parametrize("after,why", [
    ({"borrower": 99_999_995, "supplier": 50_000_000, "broker": 70_000_000}, "borrower delta 5"),
    ({"borrower": 99_999_996, "supplier": 105_000_000, "broker": 70_000_000}, "supplier balance changed"),
    ({"borrower": 99_999_996, "supplier": 50_000_000, "broker": 71_000_000}, "broker balance changed"),
])
def test_drill_lines_fail_on_any_other_movement(after, why):
    before = {"borrower": 100_000_000, "supplier": 50_000_000, "broker": 70_000_000}
    with pytest.raises(D.StepFail, match=why):
        D.drill_lines(NAMES, before, after, 4)


def test_drill_batch_shape_and_inner_hashes():
    w, supplier, broker = Wallet.create(), Wallet.create().address, BROKER.address
    pays = D.drill_payments(w.address, supplier, broker, 5_000_000_000, 1_000_000, 40, "INV-WC-DRILL", "2026-10-24")
    blob, signed = wc.sign_payments_batch(w, pays, 40, 1000, fee="4")
    tx = decode(blob)
    raws = [r["RawTransaction"] for r in tx["RawTransactions"]]
    assert tx["TransactionType"] == "Batch" and tx["Flags"] == wc.ALL_OR_NOTHING and tx["Fee"] == "4"
    assert tx["Sequence"] == 40 and [r["Sequence"] for r in raws] == [41, 42]
    assert all(r["Flags"] == wc.INNER and r["Fee"] == "0" and r["SigningPubKey"] == "" for r in raws)
    assert [r["Destination"] for r in raws] == [supplier, broker]
    assert [r["Amount"] for r in raws] == ["5000000000", "1000000"]
    assert "BatchSigners" not in tx and tx["TxnSignature"]
    assert [wc.inner_hash(r) for r in raws] == [t.get_hash() for t in signed.raw_transactions]


def test_demo_declared_debt_clears_the_understated_guard():
    """STEP4 declares 15 XRP against loan 3's 10 XRP principal; STEP8/9a declare 70 XRP against loans 3 + 4
    (10 + 60 XRP before step 6's payment, ~66.67 after). Neither may trip declared_debt_understated."""
    vault = {"assetsTotalDrops": str(150 * XRP), "loansOutstandingDrops": "0", "debtTotalDrops": "0",
             "coverDrops": str(20 * XRP)}

    def decide(principal, debt, ledger_principal):
        ev = {**policy.GOOD_LARGE, "ledger": {**policy.GOOD_LARGE["ledger"], "loanPrincipalDrops": str(ledger_principal)},
              "declared": {**policy.GOOD_LARGE["declared"], "existingDebtDrops": debt}}
        return policy.decide({"principalDrops": principal, "evidence": ev}, vault, policy.DEFAULT_POLICY)["reason"]

    assert decide(*D.STEP4, 10 * XRP) == "over_auto_limit"
    for on_ledger in (70 * XRP, 66_666_668):
        assert decide(D.STEP8["principal"], D.STEP8["debt"], on_ledger) == "over_auto_limit"
    assert decide(D.STEP8["principal"], D.STEP8["debt"], 70 * XRP + 11) == "declared_debt_understated"


def test_desk_post_sends_operator_token_when_configured(monkeypatch):
    sent = []

    class R:
        status_code = 200

        def json(self):
            return {"ok": True}
    monkeypatch.setattr(D.requests, "post", lambda url, json, headers, timeout: sent.append(headers) or R())
    monkeypatch.setattr(C, "read_env", lambda: {})
    monkeypatch.delenv("DESK_TOKEN", raising=False)
    D.desk_post("/v1/loans/L1/manage", {"action": "impair"})
    monkeypatch.setattr(C, "read_env", lambda: {"DESK_TOKEN": "from-dotenv"})
    D.desk_post("/v1/loan-requests/lr_0001/approve", {})
    monkeypatch.setenv("DESK_TOKEN", "from-shell")
    D.desk_post("/v1/loan-requests/lr_0001/approve", {})
    assert sent == [{}, {"X-Desk-Token": "from-dotenv"}, {"X-Desk-Token": "from-shell"}]


# ---- demo.py --income -------------------------------------------
def test_income_drops():
    import argparse
    assert D.income_drops("5") == 5 * XRP and D.income_drops("3.5") == 3_500_000
    for bad in ("0", "-1", "abc", "0.0000001"):
        with pytest.raises(argparse.ArgumentTypeError):
            D.income_drops(bad)


def test_income_refuses_without_a_running_sweeper(tmp_path, monkeypatch, capsys):
    """No network: the refusal comes before any wallet, faucet or devnet call."""
    import json
    import sweeper as SW
    borrower = Wallet.create().address
    monkeypatch.setattr(C, "load_accounts", lambda: {"accounts": {"borrower": borrower}})
    monkeypatch.setattr(D, "ensure_customer", lambda: pytest.fail("must not touch the customer wallet"))
    sp = tmp_path / "sweeper_state.json"
    assert D.main_income("5", state_path=sp) == 2  # no state file
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("autorepay: start the sweeper first") and "'watching' line" in out
    assert "start the sweeper first: .venv/bin/python sweeper.py" in out
    sp.write_text(json.dumps({"borrower": borrower, "cursor": None}))
    assert D.main_income("5", state_path=sp) == 2
    sp.write_text(json.dumps({"borrower": "rSomeoneElse", "cursor": 100}))
    assert D.main_income("5", state_path=sp) == 2 and "not the current borrower" in capsys.readouterr().out
    sp.write_text(json.dumps({"borrower": borrower, "cursor": 100}))
    assert D.main_income("5", state_path=sp) == 2 and "no sweeper process holds the lock" in capsys.readouterr().out
    held = SW.acquire_lock(sp)  # a sweeper holds the lock: ready
    try:
        assert D.sweeper_ready(sp, borrower) is None
    finally:
        held.close()


def test_income_arg_path(monkeypatch):
    calls = []
    monkeypatch.setattr(D, "main_income", lambda xrp: calls.append(xrp) or 0)
    assert D.main(["--income", "5"]) == 0 and calls == ["5"]
    with pytest.raises(SystemExit):
        D.main(["--income", "nope"])
    assert calls == ["5"]


# ---- banner, post-run borrower rotation, held-step settling ----------------------------
def test_scripted_banner_names_both_switches(monkeypatch, capsys):
    monkeypatch.setattr(D, "preflight", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    assert D.main(["--scripted"]) == 1
    first = capsys.readouterr().out.splitlines()[0]
    assert first == ("scripted run: start the desk with DESK_APPROVER_ACCOUNT=off SECOND_OPINION=off "
                     ".venv/bin/python -m desk")


def test_post_rotate_runs_setup_rotate_borrower_and_prints_the_gate():
    calls, lines = [], []

    def run(*args):
        calls.append(args)
        return 0, ["M1               vaultId=V", "score gate       score(...) = 99, broker credential accepted"]
    D.post_rotate(run=run, load=lambda: {"accounts": {"borrower": "rNEW"}}, out=lines.append)
    assert calls == [("--rotate-borrower",)]
    assert lines == ["post: rotated borrower -> rNEW",
                     "post: score gate       score(...) = 99, broker credential accepted",
                     "post: stage live held draw = 30 XRP (borrower_agent.py default goal)"]
    assert not any(x.startswith("step ") for x in lines)  # not a 10th scored step


def test_post_rotate_failure_is_reported_not_raised():
    lines = []

    def run(*args):
        raise D.StepFail("setup.py --rotate-borrower exited 1")
    D.post_rotate(run=run, load=lambda: pytest.fail("no load after a failed rotation"), out=lines.append)
    assert lines and lines[0].startswith("post: rotate borrower FAIL StepFail")


def test_run_setup_passes_the_rotate_arg(monkeypatch):
    seen = []

    class P:
        returncode, stdout, stderr = 0, "score gate       ok\n", ""
    monkeypatch.setattr(D, "info", lambda m: None)
    code, lines = D.run_setup("--rotate-borrower", run=lambda cmd, **kw: seen.append(cmd) or P())
    assert seen == [[D.PY, "setup.py", "--rotate-borrower"]] and code == 0 and lines == ["score gate       ok"]


class FakeDesk:
    """Records operator posts and serves wait_for from a status table."""

    def __init__(self, after_approve="approved"):
        self.posts, self.waits, self.after = [], [], after_approve
        self.status = {}

    def post(self, path, body):
        self.posts.append(path)
        rid = path.split("/")[3]
        self.status[rid] = self.after
        return {"id": rid, "status": self.after}

    def wait(self, rid, statuses, timeout):
        self.waits.append((rid, timeout))
        assert "auto" in statuses and "refused" in statuses
        return {"id": rid, "status": self.status.get(rid, "expired"), "decision": "hold", "loanId": "L" + rid}


def test_held_step_is_approved_with_the_token_when_the_gate_is_off():
    desk, lines, seen = FakeDesk(), [], set()
    rec = D.settle({"id": "lr_0003", "status": "held", "reason": "second_opinion"}, seen, True,
                   out=lines.append, post=desk.post, wait=desk.wait)
    assert desk.posts == ["/v1/loan-requests/lr_0003/approve"] and rec["status"] == "approved"
    assert len(lines) == 1 and "approver gate off" in lines[0] and "operator token" in lines[0]
    assert seen == {"lr_0003"}


def test_held_step_waits_for_a_terminal_state_when_the_gate_is_on():
    desk, lines = FakeDesk(), []
    rec = D.settle({"id": "lr_0003", "status": "held", "reason": "over_auto_limit"}, set(), False,
                   out=lines.append, post=desk.post, wait=desk.wait)
    assert desk.posts == [] and desk.waits == [("lr_0003", D.HOLD_WAIT_S)] and rec["status"] == "expired"
    assert lines == []


def test_terminal_record_needs_no_desk_call():
    desk = FakeDesk()
    rec = {"id": "lr_0005", "status": "refused"}
    assert D.settle(rec, set(), True, post=desk.post, wait=desk.wait) is rec
    assert desk.posts == [] and desk.waits == []


def test_a_later_step_never_reuses_an_earlier_record():
    """Last live run: step 3 held, steps 4, 8 and 9 got lr_0003 back (same Account+Sequence)."""
    desk, seen = FakeDesk(), set()
    D.settle({"id": "lr_0003", "status": "held", "reason": "second_opinion"}, seen, True,
             out=lambda _: None, post=desk.post, wait=desk.wait)
    with pytest.raises(D.StepFail, match="earlier record lr_0003"):
        D.settle({"id": "lr_0003", "status": "held"}, seen, True, out=lambda _: None, post=desk.post, wait=desk.wait)
    assert desk.posts == ["/v1/loan-requests/lr_0003/approve"]  # approved once, never again


def test_failed_approve_falls_back_to_waiting():
    lines, waits = [], []

    def post(path, body):
        raise D.StepFail("desk 409 /approve: over_max_pending")
    rec = D.settle({"id": "lr_0004", "status": "held"}, set(), True, out=lines.append, post=post,
                   wait=lambda rid, statuses, timeout: waits.append(rid) or {"id": rid, "status": "expired"})
    assert waits == ["lr_0004"] and rec["status"] == "expired" and "waiting for a terminal state" in lines[1]
