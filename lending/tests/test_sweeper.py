"""Offline tests for sweeper.py: a fake ledger, a fake desk, no devnet."""
import json

import common
import sweeper as S

BORROWER = "rBorrowerXXXXXXXXXXXXXXXXXXXXXXXXX"
PAYER = "rPayerYYYYYYYYYYYYYYYYYYYYYYYYYYYYY"
NOW = 1_800_000_000
XRP = 1_000_000
RESERVE = 1 * XRP + 2 * 200_000
FEE = 12


def memo(type_="invoice", data=None):
    data = {"invoice": "INV-1", "date": "2026-10-24"} if data is None else data
    return {"Memo": {"MemoType": type_.encode().hex().upper(),
                     "MemoData": json.dumps(data).encode().hex().upper()}}


def income(h, drops=5 * XRP, li=101, memos=None, sender=PAYER):
    return {"hash": h, "ledger_index": li, "validated": True,
            "tx_json": {"TransactionType": "Payment", "Account": sender, "Destination": BORROWER,
                        "DeliverMax": str(drops), "Memos": [memo()] if memos is None else memos},
            "meta": {"TransactionResult": "tesSUCCESS", "delivered_amount": str(drops), "AffectedNodes": []}}


def loan(lid, due=NOW + 30, remaining=3, periodic=3_333_334, status="active"):
    return {"loanId": lid, "borrower": BORROWER, "periodicPaymentDrops": str(periodic),
            "nextPaymentDue": due, "paymentRemaining": remaining, "status": status}


class FakeLedger:
    borrower = BORROWER

    def __init__(self, entries=(), loans=(), balance=50 * XRP, tip=100):
        self.entries, self.loans, self.balance, self.tip = list(entries), list(loans), balance, tip
        self.pays, self.fail_next = [], 0

    def _maybe_fail(self):
        if self.fail_next:
            self.fail_next -= 1
            raise S.LedgerError("devnet unreachable")

    def account_tx(self, since):
        self._maybe_fail()
        latest = max([self.tip] + [e["ledger_index"] for e in self.entries])
        return [e for e in self.entries if e["ledger_index"] > since], latest

    def loans_of(self):
        self._maybe_fail()
        return list(self.loans)

    def balance_and_reserve(self):
        self._maybe_fail()
        return self.balance, RESERVE

    def fee_drops(self):
        return FEE

    def loan_pay(self, loan_id, drops):
        self.pays.append((loan_id, drops))
        self.balance -= drops
        return {"hash": f"PAY{len(self.pays)}", "engineResult": "tesSUCCESS", "validated": True, "ledgerIndex": 120}


class FakeDesk:
    def __init__(self, down=False):
        self.down, self.posts = down, []

    def post_sweep(self, rec):
        if self.down:
            raise ConnectionError("desk down")
        self.posts.append(rec)


def started(tmp_path, ledger, desk):
    """State after the first run pinned the cursor at the tip (ledger 100)."""
    state = S.load_state(tmp_path / "state.json")
    S.sweep_once(state, ledger, desk, NOW, tmp_path / "sweeps.jsonl")
    assert state["cursor"] == 100
    return state


def test_first_run_ignores_history(tmp_path):
    led = FakeLedger(entries=[income("OLD", li=50)], loans=[loan("L1")])
    started(tmp_path, led, FakeDesk())
    assert led.pays == []


def test_classifier():
    assert S.x402_income(income("A"), BORROWER)["drops"] == 5 * XRP
    assert S.x402_income(income("B", memos=[memo("x402")]), BORROWER)
    assert S.x402_income(income("C", memos=[]), BORROWER) is None
    assert S.x402_income(income("D", memos=[memo("note")]), BORROWER) is None
    bad = memo()
    bad["Memo"]["MemoData"] = "ZZ"
    assert S.x402_income(income("E", memos=[bad]), BORROWER) is None
    assert S.x402_income(income("F", sender="rht5xsioM3iix1hx4i2zJX2WJ1JDTwLGJe"), BORROWER) is None
    failed = income("G")
    failed["meta"]["TransactionResult"] = "tecUNFUNDED_PAYMENT"
    assert S.x402_income(failed, BORROWER) is None


def test_happy_path(tmp_path, capsys):
    led, desk = FakeLedger(loans=[loan("L1"), loan("L2", due=NOW + 10 * common.PAYMENT_INTERVAL)]), FakeDesk()
    state = started(tmp_path, led, desk)
    led.entries.append(income("INC1", li=105))
    recs = S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl")
    assert led.pays == [("L1", 3_333_334)]  # L2 is not due within one interval
    want = {"incomeHash": "INC1", "incomeDrops": "5000000", "payer": PAYER, "loanId": "L1", "loanPayHash": "PAY1",
            "drops": "3333334", "engineResult": "tesSUCCESS", "ledgerIndex": 120, "at": NOW}
    assert recs == [want] and desk.posts == [want]
    assert [json.loads(x) for x in (tmp_path / "sweeps.jsonl").read_text().splitlines()] == [want]
    assert state["cursor"] == 105 and state["pendingPosts"] == []
    assert "LoanPay 3.333 XRP on loan L1" in capsys.readouterr().out


def test_rule1_one_installment_per_loan_per_sweep(tmp_path):
    led, desk = FakeLedger(loans=[loan("L1"), loan("L2")]), FakeDesk()
    state = started(tmp_path, led, desk)
    led.entries += [income("INC1", li=101), income("INC2", li=102)]
    S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl")
    assert sorted(led.pays) == [("L1", 3_333_334), ("L2", 3_333_334)]
    assert set(state["done"]) == {"INC1", "INC2"}


def test_rule2_reserve_plus_two_xrp(tmp_path, capsys):
    # balance - installment - LoanPay fee = reserve + 2 XRP - 1 drop -> skip
    led, desk = FakeLedger(loans=[loan("L1")], balance=RESERVE + 2 * XRP + 3_333_334 + FEE - 1), FakeDesk()
    state = started(tmp_path, led, desk)
    led.entries.append(income("INC1"))
    assert S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl") == []
    assert led.pays == [] and desk.posts == []
    assert "skipped: balance below reserve + 2 XRP" in capsys.readouterr().out
    # exactly at the floor pays
    led2 = FakeLedger(loans=[loan("L1")], balance=RESERVE + 2 * XRP + 3_333_334 + FEE)
    st2 = started(tmp_path / "b", led2, desk)
    led2.entries.append(income("INC1"))
    S.sweep_once(st2, led2, desk, NOW, tmp_path / "b" / "sweeps.jsonl")
    assert led2.pays == [("L1", 3_333_334)]


def test_rule3_stops_after_three_consecutive_ledger_errors(tmp_path, capsys):
    led = FakeLedger(loans=[loan("L1")])
    started(tmp_path, led, FakeDesk())
    S.save_state(tmp_path / "state.json", {"borrower": BORROWER, "cursor": 100, "seen": {}, "done": [], "pendingPosts": []})
    led.fail_next = 3
    code = S.run(led, FakeDesk(), tmp_path / "state.json", tmp_path / "sweeps.jsonl",
                 sleep=lambda s: None, now=lambda: NOW, max_sweeps=10)
    out = capsys.readouterr().out
    assert code == 2 and "stopped after 3 consecutive ledger errors" in out and "devnet unreachable" in out
    # two errors then success resets the counter
    led.fail_next = 2
    assert S.run(led, FakeDesk(), tmp_path / "state.json", tmp_path / "sweeps.jsonl",
                 sleep=lambda s: None, now=lambda: NOW, max_sweeps=1) == 0
    led.fail_next = 1
    assert S.run(led, FakeDesk(), tmp_path / "state.json", tmp_path / "sweeps.jsonl", once=True,
                 now=lambda: NOW) == 1


def test_rule4_idempotent_on_income_across_restart(tmp_path):
    led, desk = FakeLedger(loans=[loan("L1")]), FakeDesk()
    sp, wp = tmp_path / "state.json", tmp_path / "sweeps.jsonl"
    assert S.run(led, desk, sp, wp, once=True, now=lambda: NOW) == 0  # pins cursor
    led.entries.append(income("INC1", li=101))
    assert S.run(led, desk, sp, wp, once=True, now=lambda: NOW) == 0
    assert led.pays == [("L1", 3_333_334)]
    # restart with the cursor rewound: the same income is served again, nothing is paid
    st = json.loads(sp.read_text())
    st["cursor"] = 100
    sp.write_text(json.dumps(st))
    assert S.run(led, desk, sp, wp, once=True, now=lambda: NOW) == 0
    assert led.pays == [("L1", 3_333_334)]


def test_ledger_error_mid_income_does_not_repay(tmp_path):
    led, desk = FakeLedger(loans=[loan("L1"), loan("L2")]), FakeDesk()
    state = started(tmp_path, led, desk)
    led.entries.append(income("INC1", drops=10 * XRP, li=101))  # covers both installments
    real = led.balance_and_reserve
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 2:
            raise S.LedgerError("boom")
        return real()
    led.balance_and_reserve = flaky
    try:
        S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl")
    except S.LedgerError:
        pass
    assert led.pays == [("L1", 3_333_334)] and state["cursor"] == 100 and "INC1" not in state["done"]
    S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl")  # retry pays L2 only
    assert led.pays == [("L1", 3_333_334), ("L2", 3_333_334)] and "INC1" in state["done"]
    assert state["unspentIncomeDrops"] == 10 * XRP - 2 * 3_333_334  # the retry did not credit INC1 twice


def test_desk_down_never_blocks_paying(tmp_path, capsys):
    led, desk = FakeLedger(loans=[loan("L1")]), FakeDesk(down=True)
    state = started(tmp_path, led, desk)
    led.entries.append(income("INC1"))
    recs = S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl")
    assert led.pays == [("L1", 3_333_334)] and len(recs) == 1
    assert (tmp_path / "sweeps.jsonl").read_text().strip()
    assert state["pendingPosts"] == recs and "retry next sweep" in capsys.readouterr().out
    desk.down = False
    S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl")
    assert desk.posts == recs and state["pendingPosts"] == [] and led.pays == [("L1", 3_333_334)]


KILL_SCRIPT = """
import json, os, sys
import sweeper as S
from tests.test_sweeper import FakeLedger, FakeDesk, income, loan, NOW
sp, wp = sys.argv[1], sys.argv[2]
led = FakeLedger(entries=[income("INC1", li=101)], loans=[loan("L1")])
led.loan_pay = lambda loan_id, drops: os._exit(9)  # hard kill mid-submit: no finally, no save
S.run(led, FakeDesk(), sp, wp, once=True, now=lambda: NOW)
"""


def test_rule4_hard_kill_during_loan_pay_does_not_repay(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    sp, wp = tmp_path / "state.json", tmp_path / "sweeps.jsonl"
    S.save_state(sp, {"borrower": BORROWER, "cursor": 100, "seen": {}, "done": [], "pendingPosts": []})
    lending = Path(S.__file__).resolve().parent
    proc = subprocess.run([sys.executable, "-c", KILL_SCRIPT, str(sp), str(wp)], cwd=lending,
                          env={**__import__("os").environ, "PYTHONPATH": str(lending)})
    assert proc.returncode == 9
    assert json.loads(sp.read_text())["seen"] == {"INC1": {"L1": "submitting"}}
    # restart: the same income is served again (cursor still 100) and L1 is still due; nothing is paid
    led = FakeLedger(entries=[income("INC1", li=101)], loans=[loan("L1")])
    assert S.run(led, FakeDesk(), sp, wp, once=True, now=lambda: NOW) == 0
    assert led.pays == []


# ---- sweeper review 008 (P1-P4) and follow-up nits --------------------------------------------------------
ATTACKER = "rAttackerZZZZZZZZZZZZZZZZZZZZZZZZZ"


def test_p3_one_drop_memo_pays_nothing(tmp_path):
    led, desk = FakeLedger(loans=[loan("L1")]), FakeDesk()
    state = started(tmp_path, led, desk)
    led.entries.append(income("T1", drops=1, sender=ATTACKER, memos=[memo("x402", {"k": 1})]))
    assert S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl") == []
    assert led.pays == [] and state["unspentIncomeDrops"] == 1


def test_p4_four_one_drop_memos_pay_nothing(tmp_path):
    led, desk = FakeLedger(loans=[loan("L1", periodic=20 * XRP)], balance=45 * XRP), FakeDesk()
    sp, wp = tmp_path / "state.json", tmp_path / "sweeps.jsonl"
    assert S.run(led, desk, sp, wp, once=True, now=lambda: NOW) == 0
    for i in range(1, 5):
        led.entries.append(income(f"D{i}", drops=1, li=100 + i, sender=ATTACKER))
        assert S.run(led, desk, sp, wp, once=True, now=lambda: NOW + 10 * i) == 0
    assert led.pays == [] and led.balance == 45 * XRP
    assert json.loads(sp.read_text())["unspentIncomeDrops"] == 4


def test_income_pays_once_and_keeps_the_rest_unspent(tmp_path):
    led, desk = FakeLedger(loans=[loan("L1")]), FakeDesk()
    state = started(tmp_path, led, desk)
    led.entries.append(income("INC1", drops=5 * XRP))
    S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl")
    assert led.pays == [("L1", 3_333_334)] and state["unspentIncomeDrops"] == 1_666_666  # 1.67 XRP left
    # the next sweep: no new income, the leftover 1.67 XRP cannot fund another 3.33 XRP installment
    S.sweep_once(state, led, desk, NOW + 10, tmp_path / "sweeps.jsonl")
    assert led.pays == [("L1", 3_333_334)]


def test_unspent_income_accumulates_to_an_installment(tmp_path):
    led, desk = FakeLedger(loans=[loan("L1")]), FakeDesk()
    state = started(tmp_path, led, desk)
    led.entries.append(income("A1", drops=2 * XRP, li=101))
    S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl")
    assert led.pays == []
    led.entries.append(income("A2", drops=2 * XRP, li=102))
    S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl")
    assert led.pays == [("L1", 3_333_334)] and state["unspentIncomeDrops"] == 4 * XRP - 3_333_334


LOCK_HOLDER = """
import sys, time
import sweeper as S
f = S.acquire_lock(sys.argv[1])
print("locked" if f else "busy", flush=True)
time.sleep(30)
"""


def test_p1_second_sweeper_exits_3_while_another_holds_the_lock(tmp_path, capsys):
    import os
    import subprocess
    import sys
    from pathlib import Path
    sp, wp = tmp_path / "state.json", tmp_path / "sweeps.jsonl"
    lending = Path(S.__file__).resolve().parent
    holder = subprocess.Popen([sys.executable, "-c", LOCK_HOLDER, str(sp)], cwd=lending, stdout=subprocess.PIPE,
                              text=True, env={**os.environ, "PYTHONPATH": str(lending)})
    try:
        assert holder.stdout.readline().strip() == "locked"
        led = FakeLedger(entries=[income("INC1", li=101)], loans=[loan("L1")])
        assert S.run(led, FakeDesk(), sp, wp, once=True, now=lambda: NOW) == 3
        assert "another sweeper holds the lock" in capsys.readouterr().out
        assert led.pays == [] and not sp.exists()
    finally:
        holder.kill()
        holder.wait()
    assert S.run(FakeLedger(), FakeDesk(), sp, wp, once=True, now=lambda: NOW) == 0  # lock released with the process


def test_p2_rotated_borrower_resets_state_at_the_tip(tmp_path, capsys):
    sp, wp = tmp_path / "state.json", tmp_path / "sweeps.jsonl"
    S.save_state(sp, {"borrower": "rOldBorrowerAAAAAAAAAAAAAAAAAAAAAA", "cursor": 100, "seen": {"OLD": {}},
                      "done": ["OLD"], "unspentIncomeDrops": 9 * XRP, "pendingPosts": []})
    led = FakeLedger(loans=[loan("LB")], tip=100)
    led.entries = [income(f"H{i}", drops=3 * XRP, li=100 + i) for i in range(1, 4)]  # seeded history after the cursor
    assert S.run(led, FakeDesk(), sp, wp, once=True, now=lambda: NOW) == 0
    st = json.loads(sp.read_text())
    assert led.pays == [] and st["borrower"] == BORROWER and st["cursor"] == 103
    assert st["seen"] == {} and st["done"] == [] and st["unspentIncomeDrops"] == 0
    out = capsys.readouterr().out
    assert "state reset" in out and f"watching {BORROWER} from ledger 103" in out


def _paid_once(tmp_path):
    led, desk = FakeLedger(loans=[loan("L1")]), FakeDesk()
    sp, wp = tmp_path / "state.json", tmp_path / "sweeps.jsonl"
    S.run(led, desk, sp, wp, once=True, now=lambda: NOW)
    led.entries.append(income("INC1", drops=10 * XRP, li=101))
    S.run(led, desk, sp, wp, once=True, now=lambda: NOW)
    assert led.pays == [("L1", 3_333_334)]
    return led, desk, sp, wp


def test_rule4_restart_done_guard_alone(tmp_path):
    led, desk, sp, wp = _paid_once(tmp_path)
    st = json.loads(sp.read_text())
    st.update(cursor=100, seen={})  # only `done` remembers INC1
    sp.write_text(json.dumps(st))
    S.run(led, desk, sp, wp, once=True, now=lambda: NOW)
    assert led.pays == [("L1", 3_333_334)]


def test_rule4_restart_seen_guard_alone(tmp_path):
    led, desk, sp, wp = _paid_once(tmp_path)
    st = json.loads(sp.read_text())
    st.update(cursor=100, done=[])  # only `seen` remembers INC1 (and that L1 was paid for it)
    sp.write_text(json.dumps(st))
    S.run(led, desk, sp, wp, once=True, now=lambda: NOW)
    assert led.pays == [("L1", 3_333_334)]
    assert json.loads(sp.read_text())["unspentIncomeDrops"] == 10 * XRP - 3_333_334  # not credited twice


def test_delivered_amount_unavailable_is_skipped_not_an_error(tmp_path):
    e = income("U1")
    e["meta"]["delivered_amount"] = "unavailable"
    assert S.x402_income(e, BORROWER) is None
    led, desk = FakeLedger(loans=[loan("L1")]), FakeDesk()
    state = started(tmp_path, led, desk)
    led.entries.append(e)
    assert S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl") == [] and led.pays == []


def test_failed_loan_pay_is_never_repaid_and_unvalidated_is_not_posted(tmp_path, capsys):
    led, desk = FakeLedger(loans=[loan("L1"), loan("L2")]), FakeDesk()
    state = started(tmp_path, led, desk)
    results = iter([("tecINSUFFICIENT_PAYMENT", True), ("timeout_waiting", False)] + [("tesSUCCESS", True)] * 2)

    def pay(loan_id, drops):
        led.pays.append((loan_id, drops))
        code, ok = next(results)
        return {"hash": f"PAY{len(led.pays)}", "engineResult": code, "validated": ok, "ledgerIndex": 120 if ok else None}
    led.loan_pay = pay
    led.entries.append(income("INC1", drops=10 * XRP))
    recs = S.sweep_once(state, led, desk, NOW, tmp_path / "sweeps.jsonl")
    assert [r["engineResult"] for r in recs] == ["tecINSUFFICIENT_PAYMENT", "timeout_waiting"]
    assert [p["loanPayHash"] for p in desk.posts] == ["PAY1"]  # the desk stores it as failed: <code>
    assert "FAILED tecINSUFFICIENT_PAYMENT" in capsys.readouterr().out
    led.entries.append(income("INC2", drops=10 * XRP, li=102))
    S.sweep_once(state, led, desk, NOW + 200, tmp_path / "sweeps.jsonl")  # next income: a new installment is fine
    assert state["seen"]["INC1"] == {"L1": "PAY1", "L2": "PAY2"}  # INC1 never re-pays either loan
    assert led.pays[2:] == [("L1", 3_333_334), ("L2", 3_333_334)]  # INC2 is new income


def test_http_desk_post_timeout_is_4s(monkeypatch):
    seen = {}

    class R:
        def raise_for_status(self):
            pass
    monkeypatch.setattr(S.requests, "post", lambda url, json, timeout: seen.update(timeout=timeout) or R())
    S.HttpDesk("http://x").post_sweep({"loanId": "L1"})
    assert seen["timeout"] == 4
