"""Provider para qualquer API compatível com a Chat Completions API da OpenAI.

Uma só classe serve vários fornecedores, porque todos implementam o mesmo
protocolo HTTP (ver docs/decisoes-tecnicas.md, DT-01):

    OpenAI        https://api.openai.com/v1           (pago)
    Ollama        http://127.0.0.1:11434/v1           (local, gratuito — ex.: IBM Granite)
    GitHub Models https://models.github.ai/inference  (gratuito com limites)
    Gemini        .../v1beta/openai/                  (gratuito com limites)
    Groq          https://api.groq.com/openai/v1      (gratuito com limites)

Usamos a Chat Completions API (e não APIs mais recentes e exclusivas da OpenAI)
precisamente porque é o denominador comum que todos estes fornecedores suportam.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

import openai
from openai import AsyncOpenAI

from app.providers.base import (
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
    parse_tool_arguments,
)
from app.providers.text_tool_calls import extract_tool_calls


@dataclass(frozen=True, slots=True)
class OpenAICompatibleOptions:
    # Os modelos recentes da OpenAI exigem "max_completion_tokens"; a maioria dos
    # endpoints compatíveis só conhece "max_tokens".
    max_tokens_param: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    # Pedir a contagem de tokens no fim do stream (stream_options.include_usage).
    stream_usage: bool = True
    supports_tools: bool = True
    # Converter em chamadas reais o JSON de ferramentas escrito no texto (ex.: Granite).
    recover_text_tool_calls: bool = True
    # Timeout HTTP (o AgentRuntime tem o seu próprio timeout de inatividade).
    timeout_s: float = 600.0


@dataclass
class _PartialToolCall:
    id: str
    name: str
    arguments: str = ""


_FINISH_REASONS = {
    "stop": StopReason.END,
    "tool_calls": StopReason.TOOL_USE,
    "function_call": StopReason.TOOL_USE,
    "length": StopReason.MAX_TOKENS,
}


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        name: str,
        *,
        api_key: str,
        base_url: str | None = None,
        options: OpenAICompatibleOptions | None = None,
        http_client: Any | None = None,
    ) -> None:
        self.name = name
        self._options = options or OpenAICompatibleOptions()
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            # As novas tentativas são feitas pelo AgentRuntime (e ficam nas métricas).
            max_retries=0,
            timeout=self._options.timeout_s,
            http_client=http_client,
        )

    # ------------------------------------------------------------------ API

    async def stream(self, request: GenerationRequest) -> AsyncIterator[StreamEvent]:
        params = self._build_params(request)
        try:
            response = await self._client.chat.completions.create(**params)
            async for event in self._consume(response, request):
                yield event
        except openai.OpenAIError as exc:
            raise _map_error(exc, self.name) from exc

    async def list_models(self) -> list[str] | None:
        try:
            page = await self._client.models.list()
        except openai.OpenAIError as exc:
            raise _map_error(exc, self.name) from exc
        return sorted(model.id for model in page.data)

    def get_model_info(self, model: str) -> ModelInfo:
        return ModelInfo(
            provider=self.name, model=model, supports_tools=self._options.supports_tools
        )

    # ------------------------------------------------------ pedido → OpenAI

    def _build_params(self, request: GenerationRequest) -> dict[str, Any]:
        if request.tools and not self._options.supports_tools:
            raise ProviderError(
                ProviderErrorKind.BAD_REQUEST,
                "Este fornecedor está configurado sem suporte a ferramentas",
                provider=self.name,
            )
        params: dict[str, Any] = {
            "model": request.model,
            "messages": _convert_messages(request, _tool_instruction(request)),
            "stream": True,
            self._options.max_tokens_param: request.max_output_tokens,
        }
        if self._options.stream_usage:
            params["stream_options"] = {"include_usage": True}
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]
            params["tool_choice"] = _convert_tool_choice(request)
        return params

    # ----------------------------------------------------- OpenAI → eventos

    async def _consume(
        self, response: AsyncIterator[Any], request: GenerationRequest
    ) -> AsyncIterator[StreamEvent]:
        text_parts: list[str] = []
        partial_calls: dict[int, _PartialToolCall] = {}
        finish_reason: str | None = None
        usage = Usage()
        model = request.model

        async for chunk in response:
            if chunk.model:
                model = chunk.model
            if chunk.usage is not None:
                usage = Usage(chunk.usage.prompt_tokens, chunk.usage.completion_tokens)
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            if delta is not None and delta.content:
                text_parts.append(delta.content)
                yield TextDelta(delta.content)

            for tc in (delta.tool_calls if delta is not None else None) or []:
                index = tc.index if tc.index is not None else len(partial_calls)
                function = tc.function
                partial = partial_calls.get(index)
                if partial is None:
                    partial = _PartialToolCall(
                        id=tc.id or f"call_{index}",
                        name=(function.name if function else None) or "",
                    )
                    partial_calls[index] = partial
                    yield ToolCallStarted(partial.id, partial.name)
                elif function is not None and function.name and not partial.name:
                    partial.name = function.name
                if function is not None and function.arguments:
                    partial.arguments += function.arguments
                    yield ToolCallArgumentsDelta(partial.id, function.arguments)

            if choice.finish_reason:
                finish_reason = choice.finish_reason

        calls: list[ToolCall] = []
        for index in sorted(partial_calls):
            partial = partial_calls[index]
            call = ToolCall(
                id=partial.id,
                name=partial.name,
                arguments=parse_tool_arguments(partial.arguments, provider=self.name),
            )
            calls.append(call)
            yield ToolCallCompleted(call)

        text = "".join(text_parts)
        from_text = False
        if not calls and request.tools and self._options.recover_text_tool_calls:
            calls = extract_tool_calls(text, (tool.name for tool in request.tools))
            from_text = bool(calls)
            for call in calls:
                yield ToolCallStarted(call.id, call.name)
                yield ToolCallCompleted(call)

        stop_reason = _FINISH_REASONS.get(finish_reason or "", StopReason.OTHER)
        if calls:
            # Alguns servidores (ex.: Ollama) indicam "stop" mesmo quando pedem ferramentas.
            stop_reason = StopReason.TOOL_USE

        yield StreamCompleted(
            GenerationResult(
                text=text,
                tool_calls=tuple(calls),
                usage=usage,
                stop_reason=stop_reason,
                model=model,
                tool_calls_from_text=from_text,
            )
        )


# ---------------------------------------------------------------- conversões


def _tool_instruction(request: GenerationRequest) -> str | None:
    """Instrução explícita quando uma ferramenta é obrigatória.

    Alguns servidores compatíveis (observado no Ollama) ignoram ``tool_choice``.
    Repetir o pedido no system prompt não prejudica quem o respeita e ajuda quem
    o ignora. Ver DT-07.
    """
    if not request.tools:
        return None
    choice = request.tool_choice
    if choice.mode is ToolChoiceMode.SPECIFIC and choice.name:
        return (
            f"Nesta resposta tens de chamar a ferramenta `{choice.name}`. "
            "Não respondas apenas com texto."
        )
    if choice.mode is ToolChoiceMode.REQUIRED:
        return "Nesta resposta tens de chamar uma das ferramentas disponíveis."
    return None


def _convert_messages(
    request: GenerationRequest, extra_system: str | None = None
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    system = "\n\n".join(p for p in (request.system, extra_system) if p)
    if system:
        messages.append({"role": "system", "content": system})
    for message in request.messages:
        if message.role is Role.USER:
            messages.append({"role": "user", "content": message.content})
        elif message.role is Role.ASSISTANT:
            item: dict[str, Any] = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                item["content"] = message.content or None
                item["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False),
                        },
                    }
                    for call in message.tool_calls
                ]
            messages.append(item)
        elif message.role is Role.TOOL:
            content = f"ERRO: {message.content}" if message.is_error else message.content
            messages.append(
                {"role": "tool", "tool_call_id": message.tool_call_id, "content": content}
            )
    return messages


def _convert_tool_choice(request: GenerationRequest) -> Any:
    choice = request.tool_choice
    if choice.mode is ToolChoiceMode.SPECIFIC and choice.name:
        return {"type": "function", "function": {"name": choice.name}}
    return {
        ToolChoiceMode.AUTO: "auto",
        ToolChoiceMode.REQUIRED: "required",
        ToolChoiceMode.NONE: "none",
    }.get(choice.mode, "auto")


def _map_error(exc: openai.OpenAIError, provider: str) -> ProviderError:
    # A ordem importa: APITimeoutError é uma subclasse de APIConnectionError.
    if isinstance(exc, openai.APITimeoutError):
        kind = ProviderErrorKind.TIMEOUT
    elif isinstance(exc, openai.APIConnectionError):
        kind = ProviderErrorKind.UNAVAILABLE
    elif isinstance(exc, openai.AuthenticationError | openai.PermissionDeniedError):
        kind = ProviderErrorKind.AUTHENTICATION
    elif isinstance(exc, openai.RateLimitError):
        kind = ProviderErrorKind.RATE_LIMIT
    elif isinstance(exc, openai.APIStatusError):
        if exc.status_code >= 500:
            kind = ProviderErrorKind.UNAVAILABLE
        elif exc.status_code == 408:
            kind = ProviderErrorKind.TIMEOUT
        elif exc.status_code in (400, 404, 413, 422):
            kind = ProviderErrorKind.BAD_REQUEST
        else:
            kind = ProviderErrorKind.UNKNOWN
    else:
        kind = ProviderErrorKind.UNKNOWN
    detail = getattr(exc, "message", None) or str(exc)
    return ProviderError(kind, f"{provider}: {detail}"[:500], provider=provider)
