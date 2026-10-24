"""Merchant auto-accept loop with a fake XRPL client: no network, no transactions."""
from types import SimpleNamespace as NS

import pytest
from xrpl.models.transactions import CredentialAccept
from xrpl.wallet import Wallet

from merchants import common

ISSUER = Wallet.create().classic_address
TYPE_HEX = "x402-merchant".encode().hex().upper()


class FakeClient:
    def __init__(self, objects=None, error=None):
        self.objects, self.error, self.requests = objects or [], error, []

    def request(self, req):
        self.requests.append(req)
        if self.error:
            raise self.error
        return NS(result={"account_objects": self.objects})


@pytest.fixture
def submitted(monkeypatch):
    calls = []

    def fake_submit(tx, client, wallet):
        calls.append(tx)
        return NS(result={"hash": "CA" * 32})

    monkeypatch.setattr(common, "submit_and_wait", fake_submit)
    return calls


def _cred(issuer=ISSUER, type_hex=TYPE_HEX, flags=0):
    return {"LedgerEntryType": "Credential", "Issuer": issuer, "CredentialType": type_hex, "Flags": flags}


def test_pending_credential_is_accepted_once(submitted):
    wallet = Wallet.create()
    client = FakeClient([_cred()])
    assert common.accept_pending_credential(client, wallet, ISSUER, "x402-merchant") == "CA" * 32
    assert client.requests[0].account == wallet.classic_address
    assert client.requests[0].type == "credential"
    assert len(submitted) == 1
    tx = submitted[0]
    assert isinstance(tx, CredentialAccept)
    assert (tx.account, tx.issuer, tx.credential_type) == (wallet.classic_address, ISSUER, TYPE_HEX)


def test_lowercase_type_hex_from_ledger_still_matches(submitted):
    common.accept_pending_credential(FakeClient([_cred(type_hex=TYPE_HEX.lower())]), Wallet.create(), ISSUER, "x402-merchant")
    assert len(submitted) == 1


@pytest.mark.parametrize("obj", [
    _cred(flags=common.LSF_ACCEPTED),
    _cred(issuer=Wallet.create().classic_address),
    _cred(type_hex="other".encode().hex().upper()),
])
def test_accepted_or_foreign_credentials_send_no_tx(submitted, obj):
    assert common.accept_pending_credential(FakeClient([obj]), Wallet.create(), ISSUER, "x402-merchant") is None
    assert submitted == []


def test_tick_reads_issuer_from_env_file_and_logs_hash(submitted, monkeypatch, tmp_path, capsys):
    env = tmp_path / ".env"
    monkeypatch.setattr(common, "ENV_PATH", env)
    monkeypatch.delenv("CREDENTIAL_ISSUER", raising=False)
    monkeypatch.delenv("CREDENTIAL_TYPE", raising=False)
    client = FakeClient([_cred()])
    common._accept_tick(client, Wallet.create(), "good")
    assert client.requests == [] and submitted == []  # no issuer yet: nothing to look for
    env.write_text(f"CREDENTIAL_ISSUER={ISSUER}\n")
    common._accept_tick(client, Wallet.create(), "good")
    assert len(submitted) == 1
    assert f"tx={'CA' * 32}" in capsys.readouterr().out


def test_tick_survives_rpc_errors(submitted, monkeypatch, capsys):
    monkeypatch.setenv("CREDENTIAL_ISSUER", ISSUER)
    common._accept_tick(FakeClient(error=ConnectionError("rpc down")), Wallet.create(), "good")
    assert submitted == []
    assert "rpc down" in capsys.readouterr().out


def test_tick_survives_submit_errors(monkeypatch, capsys):
    monkeypatch.setenv("CREDENTIAL_ISSUER", ISSUER)

    def boom(tx, client, wallet):
        raise RuntimeError("tecNO_ENTRY")

    monkeypatch.setattr(common, "submit_and_wait", boom)
    common._accept_tick(FakeClient([_cred()]), Wallet.create(), "good")
    assert "tecNO_ENTRY" in capsys.readouterr().out
