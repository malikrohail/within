"""vet_merchant.py against an in-memory fake of the wallet's v1.4 merchant routes."""
import pytest
from dotenv import dotenv_values
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from merchants.common import load_merchants
from scripts import vet_merchant
from tests.serve import serve

ISSUER = "rIssuerXXXXXXXXXXXXXXXXXXXXXXXXXXX"
GOOD = load_merchants()["good"]["address"]
ROGUE = load_merchants()["rogue"]["address"]


def fake_wallet(accept_after=None, existing=None, listed_after_post=False):
    """accept_after: the merchant accepts after this many GET /v1/merchants (None = never).
    listed_after_post: GET /v1/merchants shows nothing until the first POST."""
    app = FastAPI()
    app.state.posted = []
    rows = {m["address"]: dict(m) for m in existing or []}
    gets = {"n": 0}

    @app.get("/v1/policy")
    def policy():
        return {"perTxCapDrops": "100000", "allowedMerchants": [], "credentialIssuer": ISSUER,
                "credentialType": "x402-merchant"}

    @app.post("/v1/merchants")
    def vet(body: dict):
        app.state.posted.append(body["address"])
        if body["address"] in rows:
            return JSONResponse(status_code=409, content={"reason": "credential_exists"})
        rows[body["address"]] = {"address": body["address"], "accepted": False, "txHash": "CC" * 32}
        return {"txHash": "CC" * 32}

    @app.get("/v1/merchants")
    def merchants():
        if listed_after_post and not app.state.posted:
            return []
        gets["n"] += 1
        if accept_after is not None and gets["n"] > accept_after:
            for row in rows.values():
                row["accepted"] = True
        return list(rows.values())

    return app


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("MERCHANT_SEED=sKeepMe\nCREDENTIAL_ISSUER=rOld\n")
    monkeypatch.setattr(vet_merchant, "ENV_PATH", path)
    monkeypatch.setattr(vet_merchant, "POLL_SECONDS", 0.05)
    return path


def test_vets_good_merchant_writes_env_and_waits_for_accept(env, capsys):
    app = fake_wallet(accept_after=2)
    with serve(app) as url:
        assert vet_merchant.main(["--wallet", url, "--timeout", "5"]) == 0
    assert app.state.posted == [GOOD]
    values = dotenv_values(env)
    assert values == {"MERCHANT_SEED": "sKeepMe", "CREDENTIAL_ISSUER": ISSUER, "CREDENTIAL_TYPE": "x402-merchant"}
    out = capsys.readouterr().out
    assert f"CredentialCreate {'CC' * 32} https://testnet.xrpl.org/transactions/{'CC' * 32}" in out
    assert "sKeepMe" not in out


def test_already_accepted_exits_without_post(capsys):
    app = fake_wallet(existing=[{"address": GOOD, "accepted": True, "txHash": "DD" * 32}])
    with serve(app) as url:
        assert vet_merchant.main(["--wallet", url]) == 0
    assert app.state.posted == []
    assert "already vetted" in capsys.readouterr().out


def test_409_on_post_still_waits_for_accept():
    # The credential exists but the wallet's listing lags behind it, so the script POSTs and gets 409.
    app = fake_wallet(accept_after=1, existing=[{"address": GOOD, "accepted": False, "txHash": "EE" * 32}],
                      listed_after_post=True)
    with serve(app) as url:
        assert vet_merchant.main(["--wallet", url, "--timeout", "5"]) == 0
    assert app.state.posted == [GOOD]


def test_times_out_with_exit_1_when_never_accepted(capsys):
    app = fake_wallet(accept_after=None)
    with serve(app) as url:
        assert vet_merchant.main(["--wallet", url, "--timeout", "0.3"]) == 1
    assert app.state.posted == [GOOD]
    assert "timed out" in capsys.readouterr().err


def test_never_vets_rogue():
    app = fake_wallet(accept_after=0)
    with serve(app) as url:
        vet_merchant.main(["--wallet", url, "--timeout", "2"])
        vet_merchant.main(["--wallet", url, "--timeout", "2"])
    assert ROGUE not in app.state.posted
    assert set(app.state.posted) == {GOOD}
