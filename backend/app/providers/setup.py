"""Construção do registry de providers a partir da configuração.

Um fornecedor só é registado se estiver configurado (chave definida). Assim a
interface mostra apenas os fornecedores que podem realmente ser usados.
"""

from __future__ import annotations

from app.core.config import Settings
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.fake_provider import FakeProvider
from app.providers.openai_compatible import OpenAICompatibleOptions, OpenAICompatibleProvider
from app.providers.registry import ProviderRegistry


def build_registry(settings: Settings) -> ProviderRegistry:
    registry = ProviderRegistry()

    # Simulado: sempre disponível (testes e ensaios sem gastar pedidos).
    registry.register("fake", FakeProvider())

    if settings.openai_api_key:
        registry.register(
            "openai",
            OpenAICompatibleProvider(
                "openai",
                api_key=settings.openai_api_key.get_secret_value(),
                base_url=settings.openai_base_url,
                options=OpenAICompatibleOptions(max_tokens_param="max_completion_tokens"),
            ),
        )

    if settings.anthropic_api_key:
        registry.register(
            "anthropic",
            AnthropicProvider(api_key=settings.anthropic_api_key.get_secret_value()),
        )

    if settings.ollama_enabled:
        # Local: não precisa de chave (o SDK exige uma string qualquer).
        registry.register(
            "ollama",
            OpenAICompatibleProvider("ollama", api_key="ollama", base_url=settings.ollama_base_url),
        )

    free_tiers = [
        ("github_models", settings.github_models_token, settings.github_models_base_url),
        ("gemini", settings.gemini_api_key, settings.gemini_base_url),
        ("groq", settings.groq_api_key, settings.groq_base_url),
    ]
    for key, secret, base_url in free_tiers:
        if secret:
            registry.register(
                key,
                OpenAICompatibleProvider(key, api_key=secret.get_secret_value(), base_url=base_url),
            )

    return registry
