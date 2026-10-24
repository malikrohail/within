import pytest
from fastapi.testclient import TestClient
from xrpl.wallet import Wallet

from merchants import good, rogue

PAY_TO = Wallet.create().classic_address


@pytest.mark.parametrize("app_module,path,price,tag", [
    (good, "/lookup", "1000", 20260601),
    (good, "/infer", "50000", 20260602),
    (good, "/dataset", "5000000", 20260603),
    (rogue, "/lookup", "1000", 20260609),
])
def test_paid_path_returns_402_with_requirements(app_module, path, price, tag):
    client = TestClient(app_module.create_app(PAY_TO))
    resp = client.get(path)
    assert resp.status_code == 402
    body = resp.json()
    assert body["x402Version"] == 2
    req = body["accepts"][0]
    assert req["scheme"] == "exact"
    assert req["network"] == "xrpl:1"
    assert req["asset"] == "XRP"
    assert req["payTo"] == PAY_TO
    assert req["amount"] == price
    assert req["extra"]["sourceTag"] == tag
    assert len(req["extra"]["invoiceId"]) > 0
    assert resp.headers["PAYMENT-REQUIRED"]


def test_invoice_ids_are_fresh_per_request():
    client = TestClient(good.create_app(PAY_TO))
    a = client.get("/lookup").json()["accepts"][0]["extra"]["invoiceId"]
    b = client.get("/lookup").json()["accepts"][0]["extra"]["invoiceId"]
    assert a != b


@pytest.mark.parametrize("app_module", [good, rogue])
def test_health_is_free(app_module):
    resp = TestClient(app_module.create_app(PAY_TO)).get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "payTo": PAY_TO}
