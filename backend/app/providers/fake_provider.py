"""Provider simulado e determinístico.

Usado nos testes automáticos e para desenvolver sem gastar pedidos de APIs
reais. NÃO é usado para fingir resultados na aplicação: um agente "fake" aparece
sempre identificado como tal.

Funciona com um *guião*: uma lista de respostas pré-definidas (ou uma função que
decide a resposta a partir do pedido). O texto é enviado aos bocados, tal como
num stream real.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from app.providers.base import (
    GenerationRequest,
    GenerationResult,
    LLMProvider,
    ProviderError,
    StopReason,
    StreamCompleted,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallArgumentsDelta,
    ToolCallCompleted,
    ToolCallStarted,
    Usage,
)


@dataclass
class FakeResponse:
    text: str = ""
    tool_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    error: ProviderError | None = None  # simula uma falha da API


Responder = Callable[[GenerationRequest], FakeResponse]


def _approx_tokens(text: str) -> int:
    return max(1, len(text.split()))


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(
        self,
        script: Iterable[FakeResponse] | Responder | None = None,
        *,
        chunk_size: int = 12,
        delay_s: float = 0.0,
    ) -> None:
        if script is None:
            self._responder: Responder = lambda _req: FakeResponse(text="OK")
        elif callable(script):
            self._responder = script
        else:
            responses = iter(list(script))

            def next_response(_req: GenerationRequest) -> FakeResponse:
                try:
                    return next(responses)
                except StopIteration:
                    raise AssertionError("FakeProvider: o guião acabou") from None

            self._responder = next_response

        self._chunk_size = chunk_size
        self._delay_s = delay_s
        self._ids = itertools.count(1)
        self.requests: list[GenerationRequest] = []  # para os testes inspecionarem

    async def stream(self, request: GenerationRequest) -> AsyncIterator[StreamEvent]:
        self.requests.append(request)
        response = self._responder(request)
        if response.error is not None:
            raise response.error

        for start in range(0, len(response.text), self._chunk_size):
            if self._delay_s:
                await asyncio.sleep(self._delay_s)
            yield TextDelta(response.text[start : start + self._chunk_size])

        calls: list[ToolCall] = []
        for name, arguments in response.tool_calls:
            call = ToolCall(id=f"fake_call_{next(self._ids)}", name=name, arguments=arguments)
            yield ToolCallStarted(call.id, call.name)
            yield ToolCallArgumentsDelta(call.id, json.dumps(arguments))
            yield ToolCallCompleted(call)
            calls.append(call)

        prompt_text = (request.system or "") + " ".join(m.content for m in request.messages)
        output_text = response.text + "".join(json.dumps(a) for _, a in response.tool_calls)
        yield StreamCompleted(
            GenerationResult(
                text=response.text,
                tool_calls=tuple(calls),
                usage=Usage(_approx_tokens(prompt_text), _approx_tokens(output_text)),
                stop_reason=StopReason.TOOL_USE if calls else StopReason.END,
                model=request.model,
            )
        )
