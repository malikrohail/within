"""Rogue merchant on :8002 (not on the wallet allowlist). Run: python -m merchants.rogue"""
from fastapi import FastAPI

from merchants.common import add_paid_path, run

PRICE_DROPS = 1000
SOURCE_TAG = 20260609


def create_app(pay_to: str) -> FastAPI:
    app = FastAPI(title="rogue merchant")
    add_paid_path(app, path="/lookup", price=PRICE_DROPS, source_tag=SOURCE_TAG, pay_to=pay_to,
                  description="Property comps lookup (unverified vendor)")

    @app.get("/lookup")
    async def lookup():
        return {"address": "123 Main St", "comps": [{"price": 999999}]}

    @app.get("/health")
    async def health():
        return {"ok": True, "payTo": pay_to}

    return app


if __name__ == "__main__":
    run("rogue", create_app)
