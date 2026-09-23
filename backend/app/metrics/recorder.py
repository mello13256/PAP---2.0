from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.runtime import CallRecord
from app.metrics.models import LLMCall


class DatabaseCallRecorder:
    """Guarda cada chamada em ``llm_calls``.

    Usa uma sessão própria: a métrica fica registada mesmo que a operação que
    fez a chamada venha a falhar (e a sua transação seja revertida).
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def record(self, record: CallRecord) -> None:
        async with self._sessionmaker() as session:
            session.add(
                LLMCall(
                    run_id=record.run_id,
                    task_id=record.task_id,
                    agent_id=record.agent_id,
                    provider=record.provider,
                    model=record.model,
                    purpose=record.purpose,
                    input_tokens=record.usage.input_tokens,
                    output_tokens=record.usage.output_tokens,
                    latency_ms=record.latency_ms,
                    success=record.success,
                    error_type=record.error_type,
                    estimated_cost_usd=record.estimated_cost_usd,
                    started_at=record.started_at,
                )
            )
            await session.commit()
