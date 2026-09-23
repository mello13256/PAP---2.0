"""Abstração comum a todos os fornecedores de LLM.

Esta camada NÃO conhece a base de dados, os agentes, nem as tarefas: só sabe
enviar um pedido a um modelo e devolver a resposta num formato normalizado.

Todas as diferenças entre APIs (formato das mensagens, como se declaram
ferramentas, onde vêm os tokens, nomes dos erros) ficam dentro de cada
implementação concreta. O resto da aplicação só vê os tipos deste ficheiro.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# --------------------------------------------------------------------------- #
# Mensagens e ferramentas
# --------------------------------------------------------------------------- #


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"  # resultado de uma ferramenta, devolvido ao modelo


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Um pedido do modelo para executar uma ferramenta."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()  # só em mensagens ASSISTANT
    tool_call_id: str | None = None  # só em mensagens TOOL
    is_error: bool = False  # só em mensagens TOOL: a ferramenta falhou

    @classmethod
    def user(cls, content: str) -> ChatMessage:
        return cls(Role.USER, content)

    @classmethod
    def assistant(cls, content: str, tool_calls: tuple[ToolCall, ...] = ()) -> ChatMessage:
        return cls(Role.ASSISTANT, content, tool_calls=tool_calls)

    @classmethod
    def tool_result(cls, tool_call_id: str, content: str, *, is_error: bool = False) -> ChatMessage:
        return cls(Role.TOOL, content, tool_call_id=tool_call_id, is_error=is_error)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Declaração de uma ferramenta: nome, descrição e JSON Schema dos argumentos."""

    name: str
    description: str
    parameters: dict[str, Any]


class ToolChoiceMode(StrEnum):
    AUTO = "auto"  # o modelo decide se usa ferramentas
    REQUIRED = "required"  # tem de usar alguma ferramenta
    NONE = "none"  # não pode usar ferramentas
    SPECIFIC = "specific"  # tem de usar a ferramenta indicada


@dataclass(frozen=True, slots=True)
class ToolChoice:
    mode: ToolChoiceMode = ToolChoiceMode.AUTO
    name: str | None = None

    @classmethod
    def force(cls, name: str) -> ToolChoice:
        return cls(ToolChoiceMode.SPECIFIC, name)


# --------------------------------------------------------------------------- #
# Pedido e resposta
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    model: str
    messages: tuple[ChatMessage, ...]
    system: str | None = None
    tools: tuple[ToolSpec, ...] = ()
    tool_choice: ToolChoice = field(default_factory=ToolChoice)
    temperature: float | None = None
    max_output_tokens: int = 2048


@dataclass(frozen=True, slots=True)
class Usage:
    """Tokens usados. ``None`` quando o fornecedor não os indica."""

    input_tokens: int | None = None
    output_tokens: int | None = None


class StopReason(StrEnum):
    END = "end"  # o modelo terminou naturalmente
    TOOL_USE = "tool_use"  # parou para pedir ferramentas
    MAX_TOKENS = "max_tokens"  # atingiu o limite de tokens de saída
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class GenerationResult:
    text: str
    tool_calls: tuple[ToolCall, ...]
    usage: Usage
    stop_reason: StopReason
    model: str  # modelo efetivamente usado (pode diferir do pedido)


@dataclass(frozen=True, slots=True)
class ModelInfo:
    provider: str
    model: str
    context_window: int | None = None
    supports_tools: bool = True
    supports_streaming: bool = True


# --------------------------------------------------------------------------- #
# Eventos de streaming
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class ToolCallStarted:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class ToolCallArgumentsDelta:
    id: str
    delta: str  # fragmento do JSON dos argumentos


@dataclass(frozen=True, slots=True)
class ToolCallCompleted:
    tool_call: ToolCall


@dataclass(frozen=True, slots=True)
class StreamCompleted:
    """Último evento de qualquer stream: contém a resposta completa."""

    result: GenerationResult


StreamEvent = (
    TextDelta | ToolCallStarted | ToolCallArgumentsDelta | ToolCallCompleted | StreamCompleted
)


# --------------------------------------------------------------------------- #
# Erros
# --------------------------------------------------------------------------- #


class ProviderErrorKind(StrEnum):
    AUTHENTICATION = "authentication"  # chave inválida / em falta
    RATE_LIMIT = "rate_limit"  # demasiados pedidos (429)
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"  # servidor em baixo / 5xx / sem ligação
    BAD_REQUEST = "bad_request"  # pedido inválido (400)
    INVALID_OUTPUT = "invalid_output"  # resposta que não conseguimos interpretar
    UNKNOWN = "unknown"


_RETRYABLE = {
    ProviderErrorKind.RATE_LIMIT,
    ProviderErrorKind.TIMEOUT,
    ProviderErrorKind.UNAVAILABLE,
}


class ProviderError(Exception):
    """Erro normalizado: a aplicação nunca vê exceções específicas de um SDK."""

    def __init__(self, kind: ProviderErrorKind, message: str, *, provider: str = "") -> None:
        super().__init__(message)
        self.kind = kind
        self.provider = provider

    @property
    def retryable(self) -> bool:
        """Erros transitórios: vale a pena tentar outra vez depois de esperar."""
        return self.kind in _RETRYABLE


# --------------------------------------------------------------------------- #
# Interface
# --------------------------------------------------------------------------- #


class LLMProvider(ABC):
    """Interface que todos os fornecedores implementam.

    Uma implementação só é obrigada a fornecer ``stream()``: ``generate()``
    consome o stream e devolve o resultado final.
    """

    # Chave no registry. Pode ser definida por instância: a mesma classe
    # OpenAICompatibleProvider serve "openai", "ollama", "gemini", ...
    name: str = "base"

    @abstractmethod
    def stream(self, request: GenerationRequest) -> AsyncIterator[StreamEvent]:
        """Gera a resposta progressivamente. O último evento é sempre ``StreamCompleted``."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        async for event in self.stream(request):
            if isinstance(event, StreamCompleted):
                return event.result
        raise ProviderError(
            ProviderErrorKind.INVALID_OUTPUT, "O stream terminou sem resultado", provider=self.name
        )

    async def count_tokens(self, request: GenerationRequest) -> int | None:
        """Contagem de tokens de entrada, se o fornecedor a disponibilizar."""
        return None

    def get_model_info(self, model: str) -> ModelInfo:
        return ModelInfo(provider=self.name, model=model)

    async def list_models(self) -> list[str] | None:
        """Modelos disponíveis, se o fornecedor permitir listá-los."""
        return None


def parse_tool_arguments(raw: str, *, provider: str) -> dict[str, Any]:
    """Converte o JSON dos argumentos de uma ferramenta, com erro normalizado."""
    if not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError(
            ProviderErrorKind.INVALID_OUTPUT,
            f"Argumentos da ferramenta não são JSON válido: {exc}",
            provider=provider,
        ) from exc
    if not isinstance(value, dict):
        raise ProviderError(
            ProviderErrorKind.INVALID_OUTPUT,
            "Argumentos da ferramenta devem ser um objeto JSON",
            provider=provider,
        )
    return value
