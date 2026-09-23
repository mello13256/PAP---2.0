import asyncio
import uuid

import pytest

from app.agents.runtime import (
    AgentRuntime,
    AgentSpec,
    CallContext,
    InMemoryCallRecorder,
    RetryPolicy,
)
from app.metrics.models import CallPurpose
from app.providers.base import (
    ChatMessage,
    LLMProvider,
    ProviderError,
    ProviderErrorKind,
    StreamCompleted,
    TextDelta,
)
from app.providers.fake_provider import FakeProvider, FakeResponse
from app.providers.pricing import ModelPrice, PricingTable

SPEC = AgentSpec(
    id=uuid.uuid4(),
    name="Claude",
    provider="fake",
    model="fake-model",
    system_prompt="És um engenheiro de software cuidadoso.",
    temperature=0.2,
    max_output_tokens=500,
)
CTX = CallContext(purpose=CallPurpose.EXECUTE, run_id=None, task_id=None)
MESSAGES = [ChatMessage.user("Implementa o backend")]


def _runtime(provider, recorder=None, *, sleeps=None, pricing=None, **retry) -> AgentRuntime:
    async def fake_sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    return AgentRuntime(
        SPEC,
        provider,
        recorder=recorder or InMemoryCallRecorder(),
        pricing=pricing or PricingTable(free_providers={"fake"}),
        retry=RetryPolicy(**retry),
        sleep=fake_sleep,
    )


def _rate_limited() -> FakeResponse:
    return FakeResponse(error=ProviderError(ProviderErrorKind.RATE_LIMIT, "429"))


async def test_agent_configuration_is_applied_to_the_request() -> None:
    provider = FakeProvider([FakeResponse(text="ok")])
    await _runtime(provider).generate(MESSAGES, context=CTX, system_extra="Tarefa T3.")

    request = provider.requests[0]
    assert request.model == "fake-model"
    assert request.temperature == 0.2
    assert request.max_output_tokens == 500
    assert request.system == "És um engenheiro de software cuidadoso.\n\nTarefa T3."


async def test_successful_call_is_recorded_with_tokens_and_cost() -> None:
    recorder = InMemoryCallRecorder()
    run_id = uuid.uuid4()
    await _runtime(FakeProvider([FakeResponse(text="três palavras aqui")]), recorder).generate(
        MESSAGES, context=CallContext(CallPurpose.REVIEW, run_id=run_id)
    )

    [record] = recorder.records
    assert record.success and record.error_type is None
    assert record.run_id == run_id and record.agent_id == SPEC.id
    assert record.purpose is CallPurpose.REVIEW
    assert record.usage.output_tokens == 3
    assert record.estimated_cost_usd == 0.0  # provider gratuito
    assert record.latency_ms >= 0


async def test_transient_errors_are_retried_with_backoff() -> None:
    recorder, sleeps = InMemoryCallRecorder(), []
    provider = FakeProvider([_rate_limited(), _rate_limited(), FakeResponse(text="finalmente")])
    result = await _runtime(provider, recorder, sleeps=sleeps, base_delay_s=1.0).generate(
        MESSAGES, context=CTX
    )

    assert result.text == "finalmente"
    # Cada tentativa conta como uma chamada à API (duas falhadas, uma com sucesso).
    assert [r.success for r in recorder.records] == [False, False, True]
    assert recorder.records[0].error_type == "rate_limit"
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0]  # backoff exponencial


async def test_gives_up_after_max_attempts() -> None:
    recorder = InMemoryCallRecorder()
    provider = FakeProvider([_rate_limited()] * 3)
    with pytest.raises(ProviderError) as info:
        await _runtime(provider, recorder, max_attempts=3).generate(MESSAGES, context=CTX)
    assert info.value.kind is ProviderErrorKind.RATE_LIMIT
    assert len(recorder.records) == 3


async def test_non_transient_errors_are_not_retried() -> None:
    recorder = InMemoryCallRecorder()
    provider = FakeProvider(
        [FakeResponse(error=ProviderError(ProviderErrorKind.AUTHENTICATION, "chave inválida"))]
    )
    with pytest.raises(ProviderError):
        await _runtime(provider, recorder).generate(MESSAGES, context=CTX)
    assert len(recorder.records) == 1


class _FailsMidStream(LLMProvider):
    name = "flaky"

    def __init__(self) -> None:
        self.calls = 0

    async def stream(self, request):
        self.calls += 1
        yield TextDelta("Comecei a responder...")
        raise ProviderError(ProviderErrorKind.UNAVAILABLE, "ligação perdida")


async def test_no_retry_after_partial_output() -> None:
    # Se parte da resposta já foi mostrada, repetir duplicaria texto na interface.
    provider = _FailsMidStream()
    with pytest.raises(ProviderError):
        await _runtime(provider).generate(MESSAGES, context=CTX)
    assert provider.calls == 1


class _Hangs(LLMProvider):
    name = "hangs"

    async def stream(self, request):
        await asyncio.sleep(10)
        yield TextDelta("nunca chega")


async def test_idle_timeout_becomes_a_timeout_error() -> None:
    recorder = InMemoryCallRecorder()
    with pytest.raises(ProviderError) as info:
        await _runtime(_Hangs(), recorder, idle_timeout_s=0.05, max_attempts=1).generate(
            MESSAGES, context=CTX
        )
    assert info.value.kind is ProviderErrorKind.TIMEOUT
    assert recorder.records[0].error_type == "timeout"


class _Crashes(LLMProvider):
    name = "crashes"

    async def stream(self, request):
        raise RuntimeError("bug no SDK")
        yield  # pragma: no cover


async def test_unexpected_exceptions_are_normalized() -> None:
    with pytest.raises(ProviderError) as info:
        await _runtime(_Crashes()).generate(MESSAGES, context=CTX)
    assert info.value.kind is ProviderErrorKind.UNKNOWN


async def test_stream_forwards_events_to_the_caller() -> None:
    runtime = _runtime(FakeProvider([FakeResponse(text="Revendo a proposta...")], chunk_size=4))
    events = [e async for e in runtime.stream(MESSAGES, context=CTX)]
    assert "".join(e.text for e in events if isinstance(e, TextDelta)) == "Revendo a proposta..."
    assert isinstance(events[-1], StreamCompleted)


async def test_cost_is_estimated_from_pricing_table() -> None:
    pricing = PricingTable({"paid/fake-model": ModelPrice(1.0, 2.0)})
    spec_paid = AgentSpec(id=None, name="X", provider="paid", model="fake-model")
    recorder = InMemoryCallRecorder()
    runtime = AgentRuntime(
        spec_paid,
        FakeProvider([FakeResponse(text="a b c d")]),
        recorder=recorder,
        pricing=pricing,
    )
    await runtime.generate(MESSAGES, context=CTX)
    record = recorder.records[0]
    expected = (record.usage.input_tokens * 1.0 + record.usage.output_tokens * 2.0) / 1_000_000
    assert record.estimated_cost_usd == pytest.approx(expected)
