import pytest

import llm


@pytest.fixture(autouse=True)
def _no_real_model_api(monkeypatch, tmp_path):
    """lending/.env may hold ANTHROPIC_API_KEY: no test may reach the paid API or write the real cost ledger."""
    monkeypatch.setattr(llm, "_api_key", lambda: None)
    monkeypatch.setattr(llm, "COST_PATH", tmp_path / "llm_cost.jsonl")
    monkeypatch.setattr(llm, "LOG_PATH", tmp_path / "llm.jsonl")
    monkeypatch.delenv("LLM_BUDGET_USD", raising=False)
