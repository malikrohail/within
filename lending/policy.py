"""Deterministic underwriting policy (INTERFACES.md §4).

Pure functions, no I/O except load_policy/save_policy. No LLM, no bureaus.
score(evidence) -> 0..100 from three sub-scores:
  L ledger   (weight 60, or 90 when bank data is not connected)
  B bank     (weight 30, or 0 when bank is None)
  D declared (weight 10)
total = (wL*L + wB*B + wD*D + 50) // 100, capped at 35 when the ledger shows a past default.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
XRP = 1_000_000  # drops

DEFAULT_POLICY = {
    "maxAutoPrincipalDrops": "20000000",
    "maxPrincipalDrops": "100000000",
    "minScoreAuto": 70,
    "minScore": 40,
    "maxUtilizationPct": 80,
    "minCoverRatioPct": 10,
    "termSecondsMin": 120,
    "termSecondsMax": 86400,
    "interestRateBps": 800,
    "holdTimeoutSeconds": 120,
    "maxPendingDrops": "0",   # cap on held + in-flight principal (auth.pending_cap_exceeded); 0 = no cap
}

# Weights (percent).
WEIGHTS_WITH_BANK = {"ledger": 60, "bank": 30, "declared": 10}
WEIGHTS_NO_BANK = {"ledger": 90, "bank": 0, "declared": 10}
PAST_DEFAULT_CAP = 35

# Ledger rule thresholds.
ACTIVE_DAYS_HIGH, ACTIVE_DAYS_LOW = 20, 10
VOLUME_HIGH_DROPS, VOLUME_LOW_DROPS = 50 * XRP, 20 * XRP
PAYERS_HIGH, PAYERS_LOW = 4, 2
TOP_SHARE_GOOD_PCT, TOP_SHARE_OK_PCT = 40, 70

# Declared rule thresholds (ratios against LEDGER inbound volume, integer math).
PURPOSES = {"inventory", "payroll", "equipment", "receivables"}
TERM_SHORT_SECONDS = 3600
# declared_debt_understated: declared existingDebtDrops may sit at most this far under the on-ledger principal.
DEBT_TOLERANCE_DROPS = 10

# Bank rule thresholds (USD).
INFLOW_HIGH_USD, INFLOW_LOW_USD = 5000, 1000
RATIO_HIGH, RATIO_LOW = 1.10, 1.00
BALANCE_HIGH_USD, BALANCE_LOW_USD = 2000, 500


def _rule(rule, value, points):
    return {"rule": rule, "value": value, "points": points}


def _sub(rules):
    return {"score": sum(r["points"] for r in rules), "rules": rules}


def ledger_score(ledger: dict) -> dict:
    days = int(ledger.get("activeDays", 0))
    vol = int(ledger.get("inboundVolumeDrops", "0"))
    payers = int(ledger.get("distinctPayers", 0))
    count = int(ledger.get("inboundPaymentCount", 0))
    top = float(ledger.get("topPayerSharePct", 0.0))
    active = int(ledger.get("activeLoans", 0))
    defaults = int(ledger.get("pastDefaults", 0))
    cred = bool(ledger.get("hasAcceptedCredential", False))

    rules = [
        _rule("activeDays", days, 20 if days >= ACTIVE_DAYS_HIGH else 10 if days >= ACTIVE_DAYS_LOW else 0),
        _rule("inboundVolumeDrops", str(vol),
              20 if vol >= VOLUME_HIGH_DROPS else 10 if vol >= VOLUME_LOW_DROPS else 0),
        _rule("distinctPayers", payers, 15 if payers >= PAYERS_HIGH else 7 if payers >= PAYERS_LOW else 0),
        _rule("topPayerSharePct", top,
              0 if count == 0 else 10 if top <= TOP_SHARE_GOOD_PCT else 5 if top <= TOP_SHARE_OK_PCT else 0),
        _rule("activeLoans", active, 10 if active == 0 else 0),
        _rule("pastDefaults", defaults, 10 if defaults == 0 else 0),
        _rule("hasAcceptedCredential", cred, 15 if cred else 0),
    ]
    return _sub(rules)


def declared_score(declared: dict, ledger: dict) -> dict:
    v = int(ledger.get("inboundVolumeDrops", "0"))  # ledger volume, never self-reported revenue
    p = int(declared.get("principalDrops", "0"))
    debt = int(declared.get("existingDebtDrops", "0"))
    purpose = declared.get("purpose")
    term = int(declared.get("termSeconds", 0))

    if v == 0:
        p_pts = 0
    elif p * 4 <= v:  # p/V <= 0.25
        p_pts = 40
    elif p <= v:  # p/V <= 1.0
        p_pts = 25
    else:
        p_pts = 0

    if debt == 0:
        d_pts = 40
    elif v == 0:
        d_pts = 0
    elif debt * 10 <= v * 3:  # debt/V <= 0.30
        d_pts = 25
    elif debt <= v:  # debt/V <= 1.0
        d_pts = 10
    else:
        d_pts = 0

    rules = [
        _rule("principalToVolume", str(p), p_pts),
        _rule("existingDebtToVolume", str(debt), d_pts),
        _rule("purpose", purpose, 10 if purpose in PURPOSES else 0),
        _rule("termSeconds", term, 10 if 0 < term <= TERM_SHORT_SECONDS else 0),
    ]
    return _sub(rules)


def bank_score(bank: dict) -> dict:
    inflow = float(bank.get("avgMonthlyInflowUsd", 0.0))
    ratio = float(bank.get("inflowOutflowRatio", 0.0))
    bal = float(bank.get("avgBalanceUsd", 0.0))
    nsf = int(bank.get("nsfCount", 0))
    rules = [
        _rule("avgMonthlyInflowUsd", inflow, 30 if inflow >= INFLOW_HIGH_USD else 15 if inflow >= INFLOW_LOW_USD else 0),
        _rule("inflowOutflowRatio", ratio, 30 if ratio >= RATIO_HIGH else 15 if ratio >= RATIO_LOW else 0),
        _rule("avgBalanceUsd", bal, 20 if bal >= BALANCE_HIGH_USD else 10 if bal >= BALANCE_LOW_USD else 0),
        _rule("nsfCount", nsf, 20 if nsf == 0 else 0),
    ]
    return _sub(rules)


def score_breakdown(evidence: dict) -> dict:
    ledger = evidence.get("ledger") or {}
    bank = evidence.get("bank")
    if bank is not None and not bank.get("connected", True):
        bank = None
    L = ledger_score(ledger)
    D = declared_score(evidence.get("declared") or {}, ledger)
    B = bank_score(bank) if bank is not None else None
    w = WEIGHTS_WITH_BANK if B is not None else WEIGHTS_NO_BANK
    total = (w["ledger"] * L["score"] + w["bank"] * (B["score"] if B else 0) + w["declared"] * D["score"] + 50) // 100
    capped = None
    if int(ledger.get("pastDefaults", 0)) > 0:
        capped = "past_default"
        total = min(total, PAST_DEFAULT_CAP)
    return {"total": total, "weights": dict(w), "ledger": L, "bank": B, "declared": D, "capped": capped}


def score(evidence: dict) -> int:
    return score_breakdown(evidence)["total"]


def decide(request: dict, vault_state: dict, policy: dict) -> dict:
    """request carries "principalDrops" and "evidence"; returns {"decision","reason","score","breakdown"}."""
    breakdown = score_breakdown(request["evidence"])
    s = breakdown["total"]
    p = int(request["principalDrops"])
    assets = int(vault_state.get("assetsTotalDrops", "0"))
    outstanding = int(vault_state.get("loansOutstandingDrops", "0"))
    debt = int(vault_state.get("debtTotalDrops", "0"))
    cover = int(vault_state.get("coverDrops", "0"))

    def out(decision, reason):
        return {"decision": decision, "reason": reason, "score": s, "breakdown": breakdown}

    declared_debt = int((request["evidence"].get("declared") or {}).get("existingDebtDrops", "0"))
    ledger_principal = int((request["evidence"].get("ledger") or {}).get("loanPrincipalDrops", "0"))
    if declared_debt + DEBT_TOLERANCE_DROPS < ledger_principal:
        return out("refuse", "declared_debt_understated")
    if s < policy["minScore"]:
        return out("refuse", "score_too_low")
    if p > int(policy["maxPrincipalDrops"]):
        return out("refuse", "over_max_principal")
    if assets == 0 or (outstanding + p) * 100 > policy["maxUtilizationPct"] * assets:
        return out("refuse", "vault_utilization")
    if cover * 100 < policy["minCoverRatioPct"] * (debt + p):
        return out("refuse", "cover_below_minimum")
    if p <= int(policy["maxAutoPrincipalDrops"]) and s >= policy["minScoreAuto"]:
        return out("auto", None)
    if p > int(policy["maxAutoPrincipalDrops"]):
        return out("hold", "over_auto_limit")
    return out("hold", "score_below_auto")


def _path(path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else HERE / p


def _validate(policy: dict) -> dict:
    if isinstance(policy, dict):
        policy = {"maxPendingDrops": DEFAULT_POLICY["maxPendingDrops"], **policy}  # older editors omit it
    if not isinstance(policy, dict) or set(policy) != set(DEFAULT_POLICY):
        raise ValueError("policy keys must equal DEFAULT_POLICY keys")
    for k, v in DEFAULT_POLICY.items():
        if isinstance(v, str):
            if not isinstance(policy[k], str) or not policy[k].isdigit():
                raise ValueError(f"{k} must be a drops string")
        elif not isinstance(policy[k], int) or isinstance(policy[k], bool):
            raise ValueError(f"{k} must be an int")
    return policy


def load_policy(path="policy.json") -> dict:
    with open(_path(path)) as f:
        return _validate(json.load(f))


def policy_hash(policy: dict) -> str:
    """Provenance stamp: first 16 hex of sha256 over the canonical JSON (sorted keys, no spaces). Key order and file
    formatting do not change it; any value change does."""
    return hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def save_policy(policy: dict, path="policy.json") -> dict:
    policy = _validate(policy)  # write the filled dict, so the saved file and its hash match the next load
    with open(_path(path), "w") as f:
        json.dump(policy, f, indent=2)
        f.write("\n")
    return policy


# ---- Evidence fixtures (INTERFACES.md §4). Tests assert score == 85, 75, 20 exactly. ----
def _ledger(**kw):
    base = {"accountExists": True, "accountAgeLedgers": 5000, "inboundPaymentCount": 0,
            "inboundVolumeDrops": "0", "distinctPayers": 0, "topPayerSharePct": 0.0, "activeDays": 0,
            "activeLoans": 0, "loanDebtDrops": "0", "loanPrincipalDrops": "0", "pastDefaults": 0,
            "hasAcceptedCredential": False, "sampleTxHashes": []}
    base.update(kw)
    return base


_SEEDED = dict(activeDays=22, inboundPaymentCount=24, inboundVolumeDrops=str(61 * XRP),
               distinctPayers=5, topPayerSharePct=31.5)

GOOD_SMALL = {
    "borrower": "rGoodSmallFixture", "asOf": 1761300000, "windowDays": 30,
    "ledger": _ledger(**_SEEDED),
    "bank": None,
    "declared": {"purpose": "inventory", "principalDrops": str(10 * XRP), "termSeconds": 270,
                 "existingDebtDrops": str(5 * XRP)},
}
GOOD_LARGE = {
    "borrower": "rGoodSmallFixture", "asOf": 1761300000, "windowDays": 30,
    "ledger": _ledger(**_SEEDED, activeLoans=1, loanDebtDrops=str(10 * XRP), loanPrincipalDrops=str(10 * XRP)),
    "bank": None,
    "declared": {"purpose": "inventory", "principalDrops": str(60 * XRP), "termSeconds": 270,
                 "existingDebtDrops": str(15 * XRP)},
}
BAD = {
    "borrower": "rBadFreshFixture", "asOf": 1761300000, "windowDays": 30,
    "ledger": _ledger(accountAgeLedgers=50),
    "bank": None,
    "declared": {"purpose": "inventory", "principalDrops": str(10 * XRP), "termSeconds": 270,
                 "existingDebtDrops": str(30 * XRP)},
}

# Aliases for the names used in the N2 task text.
EV_SEEDED, EV_SEEDED_ONE_LOAN, EV_FRESH_DEBT = GOOD_SMALL, GOOD_LARGE, BAD
