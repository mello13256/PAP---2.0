"""Provider para a API Messages da Anthropic (modelos Claude), com o SDK oficial.

Diferenças em relação à API compatível com a OpenAI, tratadas aqui dentro:

- O system prompt é um parâmetro próprio (``system``), não uma mensagem.
- Os resultados de ferramentas são blocos ``tool_result`` dentro de uma mensagem
  do utilizador; vários resultados seguidos vão numa ÚNICA mensagem.
- Os modelos atuais "pensam" antes de responder (blocos ``thinking``). Numa
  sequência de chamadas a ferramentas esses blocos têm de ser reenviados sem
  alterações. Por isso guardamos o conteúdo original em ``provider_payload``.
- Os modelos atuais rejeitam ``temperature`` (e o SDK 1.x já nem aceita o
  parâmetro), por isso a temperatura configurada num agente Claude é ignorada.
- Alguns modelos rejeitam forçar uma ferramenta específica. Por defeito, "tens de
  usar a ferramenta X" é pedido por instrução (com ``tool_choice=auto``), o que
  funciona em todos.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import anthropic
from anthropic import AsyncAnthropic

from app.providers.base import (
    ChatMessage,
    GenerationRequest,
    GenerationResult,
    LLMProvider,
    ModelInfo,
    ProviderError,
    ProviderErrorKind,
    Role,
    StopReason,
    StreamCompleted,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallArgumentsDelta,
    ToolCallCompleted,
    ToolCallStarted,
    ToolChoiceMode,
    Usage,
)


@dataclass(frozen=True, slots=True)
class AnthropicOptions:
    # False: "usa a ferramenta X" é pedido por instrução (compatível com todos os modelos).
    force_tool_choice: bool = False
    # Os argumentos das ferramentas chegam à medida que são gerados (ficheiros longos).
    # A validação dos argumentos fica do nosso lado (ver orquestrador).
    eager_input_streaming: bool = True
    timeout_s: float = 600.0


_STOP_REASONS = {
    "end_turn": StopReason.END,
    "stop_sequence": StopReason.END,
    "tool_use": StopReason.TOOL_USE,
    "max_tokens": StopReason.MAX_TOKENS,
    "refusal": StopReason.REFUSAL,
}


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None = None,
        options: AnthropicOptions | None = None,
        http_client: Any | None = None,
    ) -> None:
        self._options = options or AnthropicOptions()
        self._client = AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
            max_retries=0,  # as novas tentativas são do AgentRuntime (ficam nas métricas)
            timeout=self._options.timeout_s,
            http_client=http_client,
        )

    # ------------------------------------------------------------------ API

    async def stream(self, request: GenerationRequest) -> AsyncIterator[StreamEvent]:
        params = self._build_params(request)
        current_tool_id = ""
        try:
            async with self._client.messages.stream(**params) as stream:
                async for event in stream:
                    if event.type == "text":
                        yield TextDelta(event.text)
                    elif (
                        event.type == "content_block_start"
                        and event.content_block.type == "tool_use"
                    ):
                        current_tool_id = event.content_block.id
                        yield ToolCallStarted(current_tool_id, event.content_block.name)
                    elif event.type == "input_json" and event.partial_json:
                        yield ToolCallArgumentsDelta(current_tool_id, event.partial_json)
                message = await stream.get_final_message()
        except anthropic.APIError as exc:
            raise _map_error(exc) from exc
        except ValueError as exc:  # JSON de argumentos que o SDK não conseguiu interpretar
            raise ProviderError(
                ProviderErrorKind.INVALID_OUTPUT,
                f"anthropic: argumentos de ferramenta inválidos: {exc}",
                provider=self.name,
            ) from exc

        calls: list[ToolCall] = []
        for block in message.content:
            if block.type != "tool_use":
                continue
            if not isinstance(block.input, dict):
                raise ProviderError(
                    ProviderErrorKind.INVALID_OUTPUT,
                    "anthropic: argumentos da ferramenta devem ser um objeto JSON",
                    provider=self.name,
                )
            call = ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
            calls.append(call)
            yield ToolCallCompleted(call)

        usage = message.usage
        input_tokens = (
            usage.input_tokens
            + (usage.cache_creation_input_tokens or 0)
            + (usage.cache_read_input_tokens or 0)
        )
        yield StreamCompleted(
            GenerationResult(
                text="".join(b.text for b in message.content if b.type == "text"),
                tool_calls=tuple(calls),
                usage=Usage(input_tokens, usage.output_tokens),
                stop_reason=_STOP_REASONS.get(message.stop_reason or "", StopReason.OTHER),
                model=message.model,
                provider_payload={"provider": self.name, "content": list(message.content)},
            )
        )

    async def count_tokens(self, request: GenerationRequest) -> int | None:
        params = self._build_params(request)
        params.pop("max_tokens", None)
        try:
            result = await self._client.messages.count_tokens(**params)
        except anthropic.APIError as exc:
            raise _map_error(exc) from exc
        return result.input_tokens

    async def list_models(self) -> list[str] | None:
        try:
            return sorted([model.id async for model in self._client.models.list()])
        except anthropic.APIError as exc:
            raise _map_error(exc) from exc

    def get_model_info(self, model: str) -> ModelInfo:
        return ModelInfo(provider=self.name, model=model, supports_tools=True)

    # ------------------------------------------------------ pedido → Anthropic

    def _build_params(self, request: GenerationRequest) -> dict[str, Any]:
        system_parts = [request.system] if request.system else []
        params: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_output_tokens,
            "messages": self._convert_messages(request.messages),
        }
        if request.tools:
            params["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters,
                    **(
                        {"eager_input_streaming": True}
                        if self._options.eager_input_streaming
                        else {}
                    ),
                }
                for tool in request.tools
            ]
            choice = request.tool_choice
            if choice.mode is ToolChoiceMode.NONE:
                params["tool_choice"] = {"type": "none"}
            elif choice.mode in (ToolChoiceMode.REQUIRED, ToolChoiceMode.SPECIFIC):
                if self._options.force_tool_choice:
                    params["tool_choice"] = (
                        {"type": "tool", "name": choice.name}
                        if choice.mode is ToolChoiceMode.SPECIFIC and choice.name
                        else {"type": "any"}
                    )
                else:
                    params["tool_choice"] = {"type": "auto"}
                    system_parts.append(
                        f"Nesta resposta tens de chamar a ferramenta `{choice.name}`."
                        if choice.mode is ToolChoiceMode.SPECIFIC and choice.name
                        else "Nesta resposta tens de chamar uma das ferramentas disponíveis."
                    )

        if system_parts:
            params["system"] = "\n\n".join(system_parts)
        return params

    def _convert_messages(self, messages: tuple[ChatMessage, ...]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []

        def append(role: str, blocks: list[Any]) -> None:
            # A API exige alternância user/assistant: mensagens seguidas do mesmo
            # papel (ex.: vários tool_result) são fundidas numa só.
            if converted and converted[-1]["role"] == role:
                converted[-1]["content"].extend(blocks)
            else:
                converted.append({"role": role, "content": list(blocks)})

        for message in messages:
            if message.role is Role.USER:
                append("user", [{"type": "text", "text": message.content}])
            elif message.role is Role.TOOL:
                append(
                    "user",
                    [
                        {
                            "type": "tool_result",
                            "tool_use_id": message.tool_call_id,
                            "content": message.content,
                            "is_error": message.is_error,
                        }
                    ],
                )
            elif message.role is Role.ASSISTANT:
                payload = message.provider_payload
                if isinstance(payload, dict) and payload.get("provider") == self.name:
                    # Conteúdo original (inclui blocos de thinking): reenviado sem alterações.
                    append("assistant", list(payload["content"]))
                    continue
                blocks: list[dict[str, Any]] = []
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
                blocks.extend(
                    {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                    for c in message.tool_calls
                )
                append("assistant", blocks or [{"type": "text", "text": "(sem conteúdo)"}])
        return converted


def _map_error(exc: anthropic.APIError) -> ProviderError:
    # Do mais específico para o mais genérico (APITimeoutError ⊂ APIConnectionError).
    if isinstance(exc, anthropic.APITimeoutError):
        kind = ProviderErrorKind.TIMEOUT
    elif isinstance(exc, anthropic.APIConnectionError):
        kind = ProviderErrorKind.UNAVAILABLE
    elif isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        kind = ProviderErrorKind.AUTHENTICATION
    elif isinstance(exc, anthropic.RateLimitError):
        kind = ProviderErrorKind.RATE_LIMIT
    elif isinstance(
        exc,
        anthropic.BadRequestError | anthropic.NotFoundError | anthropic.UnprocessableEntityError,
    ):
        kind = ProviderErrorKind.BAD_REQUEST
    elif isinstance(exc, anthropic.InternalServerError):
        kind = ProviderErrorKind.UNAVAILABLE  # inclui 529 "overloaded"
    elif isinstance(exc, anthropic.APIStatusError):
        if exc.status_code == 402:
            kind = ProviderErrorKind.QUOTA
        elif exc.status_code == 408:
            kind = ProviderErrorKind.TIMEOUT
        elif exc.status_code >= 500:
            kind = ProviderErrorKind.UNAVAILABLE
        else:
            kind = ProviderErrorKind.UNKNOWN
    else:
        kind = ProviderErrorKind.UNKNOWN
    return ProviderError(kind, f"anthropic: {exc.message}"[:500], provider="anthropic")
