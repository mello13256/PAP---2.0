"""O AgentRuntime, ligado à BD real, guarda cada chamada em llm_calls."""

from sqlalchemy import select

from app.agents.runtime import AgentRuntime, AgentSpec, CallContext
from app.metrics.models import CallPurpose, LLMCall
from app.providers.base import ChatMessage, ProviderError, ProviderErrorKind
from app.providers.fake_provider import FakeProvider, FakeResponse


async def test_calls_are_persisted(app) -> None:
    runtime = AgentRuntime(
        AgentSpec(id=None, name="Granite", provider="fake", model="fake-model"),
        FakeProvider(
            [
                FakeResponse(error=ProviderError(ProviderErrorKind.UNAVAILABLE, "503")),
                FakeResponse(text="Arquitetura REST proposta."),
            ]
        ),
        recorder=app.state.call_recorder,
        pricing=app.state.pricing,
        sleep=lambda _s: _noop(),
    )
    await runtime.generate(
        [ChatMessage.user("Propõe uma arquitetura")], context=CallContext(CallPurpose.PLAN)
    )

    async with app.state.db.sessionmaker() as session:
        calls = list(await session.scalars(select(LLMCall).order_by(LLMCall.started_at)))
    assert [c.success for c in calls] == [False, True]
    assert calls[0].error_type == "unavailable"
    assert calls[1].purpose is CallPurpose.PLAN
    assert calls[1].output_tokens == 3
    assert calls[1].estimated_cost_usd == 0.0


async def _noop() -> None:
    return None
