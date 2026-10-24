import copy
import json

import pytest

import policy
from policy import BAD, DEFAULT_POLICY, GOOD_LARGE, GOOD_SMALL, decide, score, score_breakdown

XRP = 1_000_000
VAULT = {"assetsTotalDrops": str(180 * XRP), "loansOutstandingDrops": "0", "debtTotalDrops": "0",
         "coverDrops": str(20 * XRP)}


def ev(base=GOOD_SMALL, ledger=None, declared=None, bank="keep"):
    e = copy.deepcopy(base)
    e["ledger"].update(ledger or {})
    e["declared"].update(declared or {})
    if bank != "keep":
        e["bank"] = bank
    return e


# ---------------------------------------------------------------- calibration
@pytest.mark.parametrize("fixture,L,D,total", [(GOOD_SMALL, 85, 85, 85), (GOOD_LARGE, 75, 70, 75), (BAD, 20, 20, 20)])
def test_calibration(fixture, L, D, total):
    b = score_breakdown(fixture)
    assert (b["ledger"]["score"], b["declared"]["score"], b["total"]) == (L, D, total)
    assert b["weights"] == {"ledger": 90, "bank": 0, "declared": 10}
    assert b["bank"] is None and b["capped"] is None
    assert score(fixture) == total


def test_aliases():
    assert policy.EV_SEEDED is GOOD_SMALL and policy.EV_SEEDED_ONE_LOAN is GOOD_LARGE and policy.EV_FRESH_DEBT is BAD


@pytest.mark.parametrize("fixture,principal,decision,reason", [
    (GOOD_SMALL, 10 * XRP, "auto", None),
    (GOOD_LARGE, 60 * XRP, "hold", "over_auto_limit"),
    (BAD, 10 * XRP, "refuse", "score_too_low"),
])
def test_demo_decisions(fixture, principal, decision, reason):
    d = decide({"principalDrops": str(principal), "evidence": fixture}, VAULT, DEFAULT_POLICY)
    assert (d["decision"], d["reason"]) == (decision, reason)
    assert d["score"] == score(fixture) and d["breakdown"]["total"] == d["score"]


# ---------------------------------------------------------------- weights / redistribution
GOOD_BANK = {"connected": True, "institution": "ins_109508", "days": 90, "avgMonthlyInflowUsd": 6000.0,
             "avgBalanceUsd": 2500.0, "inflowOutflowRatio": 1.2, "nsfCount": 0}


def test_bank_present_uses_60_30_10():
    b = score_breakdown(ev(bank=GOOD_BANK))
    assert b["weights"] == {"ledger": 60, "bank": 30, "declared": 10}
    assert b["bank"]["score"] == 100
    assert b["total"] == (60 * 85 + 30 * 100 + 10 * 85 + 50) // 100 == 90


def test_bank_none_redistributes_to_ledger():
    assert score_breakdown(ev(bank=None))["weights"] == {"ledger": 90, "bank": 0, "declared": 10}
    assert score_breakdown(ev(bank={"connected": False}))["bank"] is None


@pytest.mark.parametrize("bank,points", [
    (dict(GOOD_BANK), 100),
    (dict(GOOD_BANK, avgMonthlyInflowUsd=1000.0, inflowOutflowRatio=1.0, avgBalanceUsd=500.0), 15 + 15 + 10 + 20),
    (dict(GOOD_BANK, avgMonthlyInflowUsd=999.99, inflowOutflowRatio=0.99, avgBalanceUsd=499.0, nsfCount=1), 0),
    (dict(GOOD_BANK, avgMonthlyInflowUsd=5000.0, inflowOutflowRatio=1.10, avgBalanceUsd=2000.0), 100),
])
def test_bank_rules(bank, points):
    assert score_breakdown(ev(bank=bank))["bank"]["score"] == points


def test_integer_rounding_half_up():
    # L=85, D=40 -> 90*85 + 10*40 = 8050 -> (8050+50)//100 = 81 (half rounds up)
    e = ev(declared={"principalDrops": str(10 * XRP), "existingDebtDrops": str(70 * XRP), "purpose": "x",
                     "termSeconds": 7200})
    b = score_breakdown(e)
    assert (b["ledger"]["score"], b["declared"]["score"]) == (85, 40)
    assert b["total"] == 81  # 80.5 -> 81


# ---------------------------------------------------------------- ledger rule boundaries
@pytest.mark.parametrize("field,value,rule_points", [
    ("activeDays", 20, 20), ("activeDays", 19, 10), ("activeDays", 10, 10), ("activeDays", 9, 0),
    ("inboundVolumeDrops", str(50 * XRP), 20), ("inboundVolumeDrops", str(50 * XRP - 1), 10),
    ("inboundVolumeDrops", str(20 * XRP), 10), ("inboundVolumeDrops", str(20 * XRP - 1), 0),
    ("distinctPayers", 4, 15), ("distinctPayers", 3, 7), ("distinctPayers", 2, 7), ("distinctPayers", 1, 0),
    ("topPayerSharePct", 40.0, 10), ("topPayerSharePct", 40.1, 5), ("topPayerSharePct", 70.0, 5),
    ("topPayerSharePct", 70.1, 0),
    ("activeLoans", 0, 10), ("activeLoans", 2, 0),
    ("hasAcceptedCredential", True, 15), ("hasAcceptedCredential", False, 0),
])
def test_ledger_rule_boundaries(field, value, rule_points):
    rules = {r["rule"]: r["points"] for r in score_breakdown(ev(ledger={field: value}))["ledger"]["rules"]}
    assert rules[field] == rule_points


def test_top_payer_share_zero_when_no_payments():
    rules = {r["rule"]: r["points"] for r in score_breakdown(BAD)["ledger"]["rules"]}
    assert rules["topPayerSharePct"] == 0


def test_ledger_rules_listed_in_breakdown():
    names = [r["rule"] for r in score_breakdown(GOOD_SMALL)["ledger"]["rules"]]
    assert names == ["activeDays", "inboundVolumeDrops", "distinctPayers", "topPayerSharePct", "activeLoans",
                     "pastDefaults", "hasAcceptedCredential"]
    assert all({"rule", "value", "points"} == set(r) for r in score_breakdown(GOOD_SMALL)["ledger"]["rules"])


def test_max_ledger_score_is_100():
    assert score_breakdown(ev(ledger={"hasAcceptedCredential": True}))["ledger"]["score"] == 100


# ---------------------------------------------------------------- declared rule boundaries (V = 40 XRP)
V = 40 * XRP


@pytest.mark.parametrize("principal,debt,p_pts,d_pts", [
    (V // 4, 0, 40, 40), (V // 4 + 1, 0, 25, 40), (V, 0, 25, 40), (V + 1, 0, 0, 40),
    (1, V * 3 // 10, 40, 25), (1, V * 3 // 10 + 1, 40, 10), (1, V, 40, 10), (1, V + 1, 40, 0),
])
def test_declared_ratio_boundaries(principal, debt, p_pts, d_pts):
    b = score_breakdown(ev(ledger={"inboundVolumeDrops": str(V)},
                           declared={"principalDrops": str(principal), "existingDebtDrops": str(debt)}))
    rules = {r["rule"]: r["points"] for r in b["declared"]["rules"]}
    assert (rules["principalToVolume"], rules["existingDebtToVolume"]) == (p_pts, d_pts)


@pytest.mark.parametrize("debt,d_pts", [("0", 40), ("1", 0)])
def test_declared_zero_volume(debt, d_pts):
    b = score_breakdown(ev(BAD, declared={"existingDebtDrops": debt}))
    rules = {r["rule"]: r["points"] for r in b["declared"]["rules"]}
    assert rules["principalToVolume"] == 0 and rules["existingDebtToVolume"] == d_pts


@pytest.mark.parametrize("purpose,term,pts", [
    ("inventory", 3600, 20), ("payroll", 270, 20), ("equipment", 3601, 10), ("receivables", 120, 20),
    ("vacation", 270, 10), (None, 7200, 0),
])
def test_declared_purpose_and_term(purpose, term, pts):
    b = score_breakdown(ev(declared={"purpose": purpose, "termSeconds": term}))
    rules = {r["rule"]: r["points"] for r in b["declared"]["rules"]}
    assert rules["purpose"] + rules["termSeconds"] == pts


def test_declared_uses_ledger_volume_not_self_report():
    e = ev(BAD)
    e["declared"]["monthlyRevenueDrops"] = str(1000 * XRP)  # ignored
    assert score(e) == 20


# ---------------------------------------------------------------- past default cap
def test_past_default_caps_at_35_and_refuses():
    e = ev(ledger={"pastDefaults": 1, "hasAcceptedCredential": True}, bank=GOOD_BANK)
    b = score_breakdown(e)
    assert b["capped"] == "past_default" and b["total"] == 35
    d = decide({"principalDrops": str(10 * XRP), "evidence": e}, VAULT, DEFAULT_POLICY)
    assert (d["decision"], d["reason"]) == ("refuse", "score_too_low")


def test_past_default_cap_does_not_raise_low_score():
    e = ev(BAD, ledger={"pastDefaults": 2})
    assert score(e) == (90 * 10 + 10 * 20 + 50) // 100 == 11


# ---------------------------------------------------------------- decision order
def fake_ev(total):
    return total if isinstance(total, dict) else {85: GOOD_SMALL, 75: GOOD_LARGE, 20: BAD}[total]


def understated(declared_xrp_drops, base=BAD):
    """Inline evidence: 10 XRP of on-ledger loan principal, `declared_xrp_drops` declared."""
    return ev(base, ledger={"activeLoans": 1, "loanPrincipalDrops": str(10 * XRP)},
              declared={"existingDebtDrops": str(declared_xrp_drops)})


@pytest.mark.parametrize("ev_total,principal,vault,pol,decision,reason", [
    # (0) declared debt below on-ledger loan principal: before the score, even if everything else is also wrong
    (understated(5 * XRP), 500 * XRP, {**VAULT, "assetsTotalDrops": "0"}, {}, "refuse", "declared_debt_understated"),
    (understated(10 * XRP - 11, GOOD_LARGE), 60 * XRP, VAULT, {}, "refuse", "declared_debt_understated"),
    (understated(10 * XRP - 10, GOOD_LARGE), 60 * XRP, VAULT, {}, "hold", "over_auto_limit"),  # within tolerance
    ({**GOOD_SMALL, "ledger": {k: v for k, v in GOOD_SMALL["ledger"].items() if k != "loanPrincipalDrops"}},
     10 * XRP, VAULT, {}, "auto", None),  # a record stored before the field existed reads it as 0
    # (1) score first, even if everything else is also wrong
    (20, 500 * XRP, {**VAULT, "assetsTotalDrops": "0"}, {}, "refuse", "score_too_low"),
    # (2) over max principal before utilization
    (85, 100 * XRP + 1, {**VAULT, "assetsTotalDrops": "0"}, {}, "refuse", "over_max_principal"),
    (85, 100 * XRP, VAULT, {"maxUtilizationPct": 50}, "refuse", "vault_utilization"),  # 100/180 = 55.6 %
    # (3) utilization: exactly 80 % allowed, above refused
    (85, 16 * XRP, {**VAULT, "assetsTotalDrops": str(20 * XRP)}, {}, "auto", None),
    (85, 16 * XRP + 1, {**VAULT, "assetsTotalDrops": str(20 * XRP)}, {}, "refuse", "vault_utilization"),
    (85, 10 * XRP, {**VAULT, "assetsTotalDrops": str(100 * XRP), "loansOutstandingDrops": str(71 * XRP)}, {},
     "refuse", "vault_utilization"),
    (85, 1, {**VAULT, "assetsTotalDrops": "0"}, {}, "refuse", "vault_utilization"),
    # (4) cover: cover/(debt+p) < 10 %
    (85, 10 * XRP, {**VAULT, "coverDrops": str(1 * XRP)}, {}, "auto", None),
    (85, 10 * XRP, {**VAULT, "coverDrops": str(1 * XRP - 1)}, {}, "refuse", "cover_below_minimum"),
    (85, 10 * XRP, {**VAULT, "coverDrops": str(2 * XRP), "debtTotalDrops": str(11 * XRP)}, {},
     "refuse", "cover_below_minimum"),
    # (5) auto vs hold
    (85, 20 * XRP, VAULT, {}, "auto", None),
    (85, 20 * XRP + 1, VAULT, {}, "hold", "over_auto_limit"),
    (75, 10 * XRP, VAULT, {}, "auto", None),
    (75, 10 * XRP, VAULT, {"minScoreAuto": 76}, "hold", "score_below_auto"),
    (75, 30 * XRP, VAULT, {"minScoreAuto": 76}, "hold", "over_auto_limit"),
    (75, 10 * XRP, VAULT, {"minScore": 76}, "refuse", "score_too_low"),
    (75, 10 * XRP, VAULT, {"minScore": 75, "minScoreAuto": 75}, "auto", None),
])
def test_decision_order(ev_total, principal, vault, pol, decision, reason):
    d = decide({"principalDrops": str(principal), "evidence": fake_ev(ev_total)}, vault, {**DEFAULT_POLICY, **pol})
    assert (d["decision"], d["reason"]) == (decision, reason)


# ---------------------------------------------------------------- policy file
def test_policy_json_matches_default():
    assert policy.load_policy() == DEFAULT_POLICY
    with open(policy.HERE / "policy.json") as f:
        assert json.load(f) == DEFAULT_POLICY


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "p.json"
    new = {**DEFAULT_POLICY, "minScore": 50}
    assert policy.save_policy(new, p) == new
    assert policy.load_policy(p) == new


@pytest.mark.parametrize("bad", [
    {k: v for k, v in DEFAULT_POLICY.items() if k != "minScore"},
    {**DEFAULT_POLICY, "extra": 1},
    {**DEFAULT_POLICY, "minScore": "40"},
    {**DEFAULT_POLICY, "maxPrincipalDrops": 100},
])
def test_save_rejects_bad_policy(tmp_path, bad):
    with pytest.raises(ValueError):
        policy.save_policy(bad, tmp_path / "p.json")
    assert not (tmp_path / "p.json").exists()


def test_policy_hash_is_canonical():
    import hashlib
    h = policy.policy_hash(DEFAULT_POLICY)
    canon = json.dumps(DEFAULT_POLICY, sort_keys=True, separators=(",", ":")).encode()
    assert h == hashlib.sha256(canon).hexdigest()[:16] and len(h) == 16
    assert policy.policy_hash(dict(reversed(list(DEFAULT_POLICY.items())))) == h   # key order is not provenance
    assert policy.policy_hash({**DEFAULT_POLICY, "minScore": 41}) != h
    assert policy.policy_hash(policy.load_policy()) == h                            # policy.json as shipped
