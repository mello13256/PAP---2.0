import json

import pytest

from app.providers.base import Usage
from app.providers.fake_provider import FakeProvider
from app.providers.pricing import PricingTable
from app.providers.registry import ProviderRegistry, UnknownProviderError


def test_unknown_price_is_none_not_invented() -> None:
    assert PricingTable().estimate("openai", "some-model", Usage(100, 100)) is None


def test_free_providers_cost_zero() -> None:
    table = PricingTable(free_providers={"ollama"})
    assert table.estimate("ollama", "granite", Usage(1000, 1000)) == 0.0


def test_missing_token_counts_give_no_estimate() -> None:
    table = PricingTable()
    assert table.estimate("x", "y", Usage(None, None)) is None


def test_pricing_file_is_loaded(tmp_path) -> None:
    path = tmp_path / "pricing.json"
    path.write_text(
        json.dumps(
            {
                "free_providers": ["ollama"],
                "models": {"openai/m": {"input_per_mtok": 2, "output_per_mtok": 8}},
            }
        )
    )
    table = PricingTable.from_file(path)
    assert table.estimate("openai", "m", Usage(1_000_000, 500_000)) == pytest.approx(6.0)
    assert table.estimate("ollama", "granite", Usage(5, 5)) == 0.0


def test_invalid_pricing_file_does_not_crash(tmp_path) -> None:
    path = tmp_path / "pricing.json"
    path.write_text("{isto não é json")
    assert PricingTable.from_file(path).estimate("a", "b", Usage(1, 1)) is None


def test_registry() -> None:
    registry = ProviderRegistry()
    registry.register("fake", FakeProvider())
    assert registry.available() == ["fake"]
    assert "fake" in registry
    with pytest.raises(ValueError):
        registry.register("fake", FakeProvider())
    with pytest.raises(UnknownProviderError):
        registry.get("gemini")
