"""AgentRuntime: um agente (configuração) + um provider (transporte).

É o ÚNICO ponto por onde passam todas as chamadas a LLMs, por isso é aqui que:
- se aplica o system prompt e os parâmetros do agente;
- se repetem pedidos que falharam por erros transitórios (com backoff exponencial);
- se aplica o timeout;
- se regista cada tentativa como métrica (``llm_calls``).
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from app.db.types import utcnow
from app.metrics.models import CallPurpose
from app.providers.base import (
    ChatMessage,
    GenerationRequest,
    GenerationResult,
    LLMProvider,
    ProviderError,
    ProviderErrorKind,
    StreamCompleted,
    StreamEvent,
    ToolChoice,
    ToolSpec,
    Usage,
)
from app.providers.pricing import PricingTable

if TYPE_CHECKING:
    from app.agents.models import Agent

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """Cópia imutável da configuração de um agente, independente da sessão da BD."""

    id: uuid.UUID | None
    name: str
    provider: str
    model: str
    system_prompt: str = ""
    temperature: float | None = None
    max_output_tokens: int = 8192
    capabilities: tuple[str, ...] = ()

    @classmethod
    def from_model(cls, agent: Agent) -> AgentSpec:
        config = agent.config or {}
        return cls(
            id=agent.id,
            name=agent.name,
            provider=agent.provider,
            model=agent.model,
            system_prompt=agent.system_prompt,
            temperature=config.get("temperature"),
            max_output_tokens=int(config.get("max_output_tokens", 8192)),
            capabilities=tuple(agent.capabilities or ()),
        )


@dataclass(frozen=True, slots=True)
class CallContext:
    """Para que serve a chamada (usado nas métricas)."""

    purpose: CallPurpose
    run_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class CallRecord:
    agent_id: uuid.UUID | None
    run_id: uuid.UUID | None
    task_id: uuid.UUID | None
    provider: str
    model: str
    purpose: CallPurpose
    usage: Usage
    latency_ms: int
    success: bool
    error_type: str | None
    estimated_cost_usd: float | None
    started_at: datetime


class CallRecorder(Protocol):
    async def record(self, record: CallRecord) -> None: ...


@dataclass
class InMemoryCallRecorder:
    records: list[CallRecord] = field(default_factory=list)

    async def record(self, record: CallRecord) -> None:
        self.records.append(record)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_s: float = 1.0
    max_delay_s: float = 30.0
    # Tempo máximo SEM receber nenhum evento do modelo (não é o tempo total).
    idle_timeout_s: float = 120.0

    def delay_for(self, attempt: int) -> float:
        """Backoff exponencial com um pouco de aleatoriedade: 1s, 2s, 4s, ..."""
        delay = min(self.max_delay_s, self.base_delay_s * 2 ** (attempt - 1))
        return delay + random.uniform(0, self.base_delay_s / 2)


class AgentRuntime:
    def __init__(
        self,
        spec: AgentSpec,
        provider: LLMProvider,
        *,
        recorder: CallRecorder,
        pricing: PricingTable,
        retry: RetryPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.spec = spec
        self.provider = provider
        self._recorder = recorder
        self._pricing = pricing
        self._retry = retry or RetryPolicy()
        self._sleep = sleep

    def build_request(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolSpec] = (),
        tool_choice: ToolChoice | None = None,
        system_extra: str | None = None,
    ) -> GenerationRequest:
        system_parts = [p for p in (self.spec.system_prompt, system_extra) if p]
        return GenerationRequest(
            model=self.spec.model,
            messages=tuple(messages),
            system="\n\n".join(system_parts) or None,
            tools=tuple(tools),
            tool_choice=tool_choice or ToolChoice(),
            temperature=self.spec.temperature,
            max_output_tokens=self.spec.max_output_tokens,
        )

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        context: CallContext,
        tools: Sequence[ToolSpec] = (),
        tool_choice: ToolChoice | None = None,
        system_extra: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        request = self.build_request(
            messages, tools=tools, tool_choice=tool_choice, system_extra=system_extra
        )
        attempt = 0
        while True:
            attempt += 1
            started_at = utcnow()
            t0 = time.perf_counter()
            emitted_any = False
            try:
                async for event in self._stream_with_idle_timeout(request):
                    emitted_any = True
                    if isinstance(event, StreamCompleted):
                        await self._record(context, started_at, t0, result=event.result)
                    yield event
                return
            except ProviderError as exc:
                await self._record(context, started_at, t0, error=exc)
                # Só repetimos se nada tiver sido enviado ainda: caso contrário a UI
                # já mostrou parte da resposta e repetir duplicaria texto.
                if exc.retryable and not emitted_any and attempt < self._retry.max_attempts:
                    delay = self._retry.delay_for(attempt)
                    logger.warning(
                        "%s: %s (tentativa %d/%d); nova tentativa em %.1fs",
                        self.spec.name,
                        exc.kind,
                        attempt,
                        self._retry.max_attempts,
                        delay,
                    )
                    await self._sleep(delay)
                    continue
                raise

    async def generate(
        self,
        messages: Sequence[ChatMessage],
        *,
        context: CallContext,
        tools: Sequence[ToolSpec] = (),
        tool_choice: ToolChoice | None = None,
        system_extra: str | None = None,
    ) -> GenerationResult:
        async for event in self.stream(
            messages,
            context=context,
            tools=tools,
            tool_choice=tool_choice,
            system_extra=system_extra,
        ):
            if isinstance(event, StreamCompleted):
                return event.result
        raise AssertionError("unreachable: stream() garante StreamCompleted ou exceção")

    async def _stream_with_idle_timeout(
        self, request: GenerationRequest
    ) -> AsyncIterator[StreamEvent]:
        """Envolve o stream do provider: timeout entre eventos e erros normalizados."""
        iterator = aiter(self.provider.stream(request))
        completed = False
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        anext(iterator), timeout=self._retry.idle_timeout_s
                    )
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    raise ProviderError(
                        ProviderErrorKind.TIMEOUT,
                        f"Sem resposta há {self._retry.idle_timeout_s:.0f}s",
                        provider=self.provider.name,
                    ) from None
                except ProviderError:
                    raise
                except Exception as exc:  # erro inesperado de um SDK: normalizar
                    raise ProviderError(
                        ProviderErrorKind.UNKNOWN,
                        f"{type(exc).__name__}: {exc}",
                        provider=self.provider.name,
                    ) from exc
                if isinstance(event, StreamCompleted):
                    completed = True
                yield event
        finally:
            aclose = getattr(iterator, "aclose", None)
            if aclose is not None:
                await aclose()
        if not completed:
            raise ProviderError(
                ProviderErrorKind.INVALID_OUTPUT,
                "O stream terminou sem resultado final",
                provider=self.provider.name,
            )

    async def _record(
        self,
        context: CallContext,
        started_at: datetime,
        t0: float,
        *,
        result: GenerationResult | None = None,
        error: ProviderError | None = None,
    ) -> None:
        usage = result.usage if result else Usage()
        model = result.model if result else self.spec.model
        record = CallRecord(
            agent_id=self.spec.id,
            run_id=context.run_id,
            task_id=context.task_id,
            provider=self.spec.provider,
            model=model,
            purpose=context.purpose,
            usage=usage,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            success=error is None,
            error_type=str(error.kind) if error else None,
            estimated_cost_usd=(
                self._pricing.estimate(self.spec.provider, model, usage) if result else None
            ),
            started_at=started_at,
        )
        try:
            await self._recorder.record(record)
        except Exception:  # as métricas nunca devem fazer falhar uma tarefa
            logger.exception("Falha ao registar métrica da chamada")
