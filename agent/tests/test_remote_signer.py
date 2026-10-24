import base64
import hashlib
import json
import socket

import pytest
import requests
from fastapi.testclient import TestClient
from x402_xrpl.types import PaymentPayload, PaymentRequirements, ResourceInfo
from xrpl.core.binarycodec import decode
from xrpl.wallet import Wallet

import remote_signer
from merchants import good
from merchants.common import ensure_seeds
from remote_signer import PolicyRefused, WalletError, make_session, make_wallet_header_factory, paid_get
from tests import stub_wallet
from tests.serve import serve

PAY_TO = Wallet.create().classic_address


def _requirements(path="/lookup"):
    body = TestClient(good.create_app(PAY_TO)).get(path).json()
    return PaymentRequirements.from_dict(body["accepts"][0]), ResourceInfo.from_dict(body["resource"])


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


def _fake_wallet(monkeypatch, status, body):
    calls = []

    def post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse(status, body)

    def get(url, timeout=None):
        return FakeResponse(200, {"holdTimeoutSeconds": 90})

    monkeypatch.setattr(remote_signer.requests, "post", post)
    monkeypatch.setattr(remote_signer.requests, "get", get)
    return calls


@pytest.mark.parametrize("status,body", [
    (403, {"decision": "refused", "requestId": "r1", "reason": "merchant_not_allowed"}),
    (403, {"decision": "refused", "requestId": "r2", "reason": "daily_budget_exceeded"}),
    (403, {"decision": "refused", "requestId": "r3", "reason": "denied_on_device"}),
    (408, {"decision": "expired", "requestId": "r4", "reason": "hold_timeout"}),
    (503, {"reason": "device_unavailable"}),
])
def test_refusal_statuses_raise_policy_refused(monkeypatch, status, body):
    _fake_wallet(monkeypatch, status, body)
    reqs, resource = _requirements()
    factory = make_wallet_header_factory("http://wallet.test")
    with pytest.raises(PolicyRefused) as info:
        factory(reqs, resource=resource)
    assert info.value.reason == body["reason"]
    assert info.value.request_id == body.get("requestId")
    assert info.value.status == status
    assert factory.last_error is info.value


@pytest.mark.parametrize("status", [400, 500])
def test_other_statuses_raise_wallet_error(monkeypatch, status):
    _fake_wallet(monkeypatch, status, {"reason": "bad"})
    reqs, resource = _requirements()
    with pytest.raises(WalletError):
        make_wallet_header_factory("http://wallet.test")(reqs, resource=resource)


def test_request_body_and_timeout(monkeypatch):
    calls = _fake_wallet(monkeypatch, 403, {"reason": "merchant_not_allowed", "requestId": "x"})
    reqs, resource = _requirements("/infer")
    factory = make_wallet_header_factory("http://wallet.test/", purpose_getter=lambda: "classify kitchen photo")
    with pytest.raises(PolicyRefused):
        factory(reqs, resource=resource)
    assert calls == [{
        "url": "http://wallet.test/v1/pay",
        "json": {"requirements": reqs.to_dict(), "purpose": "classify kitchen photo", "resource": resource.to_dict()},
        "timeout": (5, 130),
    }]


def test_paid_get_reraises_refusal_that_the_session_swallows(monkeypatch):
    _fake_wallet(monkeypatch, 403, {"decision": "refused", "requestId": "r9", "reason": "merchant_not_allowed"})
    factory = make_wallet_header_factory("http://wallet.test")
    with serve(good.create_app(PAY_TO)) as merchant:
        session = make_session(factory)
        # The library catches the factory's exception and hands back the 402 ...
        assert session.get(f"{merchant}/lookup").status_code == 402
        # ... so paid_get is what surfaces it.
        with pytest.raises(PolicyRefused) as info:
            paid_get(session, factory, f"{merchant}/lookup")
    assert info.value.reason == "merchant_not_allowed"


def test_paid_get_reports_unreachable_wallet():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]
    factory = make_wallet_header_factory(f"http://127.0.0.1:{dead_port}")
    with serve(good.create_app(PAY_TO)) as merchant:
        with pytest.raises(WalletError, match="unreachable"):
            paid_get(make_session(factory), factory, f"{merchant}/lookup")


@pytest.mark.network
def test_header_carries_real_blob_from_stub_wallet():
    """Real round trip: the stub signs with a funded testnet seed via XRPLPresignedPaymentPayer."""
    stub_seed = ensure_seeds("STUB_SEED")["STUB_SEED"]
    reqs, resource = _requirements("/infer")
    with serve(stub_wallet.create_app(Wallet.from_seed(stub_seed), allowlist=[PAY_TO])) as wallet_url:
        factory = make_wallet_header_factory(wallet_url, purpose_getter=lambda: "classify kitchen photo")
        header = factory(reqs, resource=resource)
        listed = requests.get(f"{wallet_url}/v1/requests", timeout=5).json()

    body = factory.last_result
    assert body["decision"] == "auto" and body["signer"] == "hot"
    payload = PaymentPayload.from_dict(json.loads(base64.b64decode(header)))
    assert payload.x402_version == 2
    assert payload.payload["signedTxBlob"] == body["signedTxBlob"]
    assert payload.payload["invoiceId"] == reqs.invoice_id()
    assert payload.accepted.to_dict() == reqs.to_dict()
    assert payload.resource.to_dict() == resource.to_dict()

    tx = decode(body["signedTxBlob"])
    assert tx["TransactionType"] == "Payment"
    assert tx["Destination"] == PAY_TO
    assert tx["Amount"] == "50000"
    assert tx["SourceTag"] == 20260602
    assert tx["InvoiceID"] == hashlib.sha256(reqs.invoice_id().encode()).hexdigest().upper()

    assert listed[0]["purpose"] == "classify kitchen photo"
    assert listed[0]["status"] == "auto" and listed[0]["txHash"] == body["txHash"]
