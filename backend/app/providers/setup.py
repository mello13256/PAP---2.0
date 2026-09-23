"""Construção do registry de providers a partir da configuração."""

from __future__ import annotations

from app.core.config import Settings
from app.providers.fake_provider import FakeProvider
from app.providers.registry import ProviderRegistry


def build_registry(settings: Settings) -> ProviderRegistry:
    registry = ProviderRegistry()
    # O provider simulado está sempre disponível (testes e ensaios sem gastar pedidos).
    registry.register("fake", FakeProvider())
    # Os providers reais (OpenAI, Anthropic, Ollama, ...) são registados nas fases 5 e 6,
    # apenas quando a respetiva chave/URL está configurada.
    return registry
