"""Registo de providers disponíveis.

É o ÚNICO sítio da aplicação onde nomes de fornecedores ("openai", "ollama", ...)
são associados a implementações. Os agentes guardam apenas a chave (string).

Adicionar um fornecedor novo = registar aqui uma instância. O orquestrador não muda.
"""

from __future__ import annotations

from app.core.errors import AppError
from app.providers.base import LLMProvider


class UnknownProviderError(AppError):
    status_code = 400
    code = "unknown_provider"


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, key: str, provider: LLMProvider) -> None:
        if key in self._providers:
            raise ValueError(f"Provider '{key}' já registado")
        self._providers[key] = provider

    def get(self, key: str) -> LLMProvider:
        try:
            return self._providers[key]
        except KeyError:
            raise UnknownProviderError(
                f"Provider '{key}' não está disponível (falta configurar a chave?)"
            ) from None

    def available(self) -> list[str]:
        return sorted(self._providers)

    def __contains__(self, key: str) -> bool:
        return key in self._providers
