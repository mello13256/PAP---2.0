"""Estimativa de custos.

Os preços mudam com frequência, por isso NÃO estão escritos no código: vêm do
ficheiro ``backend/pricing.json`` (preço em USD por milhão de tokens), que deve
ser preenchido com os valores oficiais em vigor.

- Modelo com preço conhecido → custo estimado.
- Fornecedor gratuito/local (ex.: Ollama) → 0.
- Preço desconhecido → ``None`` (a UI mostra "—" em vez de inventar um valor).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.providers.base import Usage

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ModelPrice:
    input_per_mtok: float
    output_per_mtok: float


class PricingTable:
    def __init__(
        self,
        prices: dict[str, ModelPrice] | None = None,
        free_providers: set[str] | None = None,
    ) -> None:
        self._prices = prices or {}
        self._free = free_providers or set()

    @classmethod
    def from_file(cls, path: Path) -> PricingTable:
        if not path.exists():
            return cls(free_providers={"fake", "ollama"})
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            prices = {
                key: ModelPrice(float(v["input_per_mtok"]), float(v["output_per_mtok"]))
                for key, v in data.get("models", {}).items()
            }
            free = set(data.get("free_providers", [])) | {"fake"}
        except (ValueError, KeyError, TypeError):
            logger.exception("pricing.json inválido; custos ficam por estimar")
            return cls(free_providers={"fake", "ollama"})
        return cls(prices, free)

    def estimate(self, provider: str, model: str, usage: Usage) -> float | None:
        if provider in self._free:
            return 0.0
        price = self._prices.get(f"{provider}/{model}")
        if price is None or usage.input_tokens is None or usage.output_tokens is None:
            return None
        cost = (
            usage.input_tokens * price.input_per_mtok + usage.output_tokens * price.output_per_mtok
        ) / 1_000_000
        return round(cost, 6)
