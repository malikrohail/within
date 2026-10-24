"""Good merchant on :8001 (on the wallet allowlist). Run: python -m merchants.good"""
from fastapi import FastAPI

from merchants.common import add_paid_path, run

# path -> (price in drops, sourceTag, description)
PATHS = {
    "/lookup": (1000, 20260601, "Property comps lookup"),
    "/infer": (50000, 20260602, "Kitchen photo classification"),
    "/dataset": (5000000, 20260603, "Full MLS dataset export"),
}


def create_app(pay_to: str) -> FastAPI:
    app = FastAPI(title="good merchant")
    for path, (price, tag, description) in PATHS.items():
        add_paid_path(app, path=path, price=price, source_tag=tag, pay_to=pay_to, description=description)

    @app.get("/lookup")
    async def lookup():
        return {"address": "123 Main St", "comps": [{"price": 412000}, {"price": 398500}, {"price": 425750}]}

    @app.get("/infer")
    async def infer():
        return {"label": "kitchen", "confidence": 0.97}

    @app.get("/dataset")
    async def dataset():
        return {"dataset": "mls-full", "rows": 184233, "url": "https://example.invalid/mls-full.parquet"}

    @app.get("/health")
    async def health():
        return {"ok": True, "payTo": pay_to}

    return app


if __name__ == "__main__":
    run("good", create_app)
