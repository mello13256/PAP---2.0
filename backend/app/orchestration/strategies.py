"""Estratégias de colaboração: é isto que as experiências comparam.

Uma estratégia é configuração, não código: diz quem planeia, como se atribuem
tarefas, quem revê e com que limites. Os papéis são resolvidos contra a lista
de agentes participantes do run (por capacidades ou por posição).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class Assignment(StrEnum):
    CAPABILITY = "capability"  # agente com a capacidade pedida pela tarefa (desempate: menos carga)
    SECOND_AGENT = "second_agent"  # o 2.º participante implementa tudo
    FIRST_AGENT = "first_agent"  # um só agente faz tudo


class ReviewPolicy(StrEnum):
    OTHER = "other"  # um agente diferente do autor
    SELF = "self"  # o próprio autor revê (para comparar)
    FIRST_AGENT = "first_agent"  # o 1.º participante revê tudo
    NONE = "none"  # sem revisão


@dataclass(frozen=True)
class Limits:
    max_tasks: int = 8
    max_llm_calls: int = 120
    max_tool_steps: int = 10  # passos de ferramentas por execução de tarefa
    max_review_rounds: int = 2
    max_minutes: int = 60
    max_messages_per_task: int = 3  # send_message por agente e por tarefa


@dataclass(frozen=True)
class Strategy:
    key: str
    name: str
    description: str
    assignment: Assignment
    review: ReviewPolicy
    min_agents: int = 1
    limits: Limits = field(default_factory=Limits)

    def snapshot(self) -> dict:
        return asdict(self)


STRATEGIES: dict[str, Strategy] = {
    s.key: s
    for s in [
        Strategy(
            key="collaborative",
            name="Colaborativa",
            description="Planeia quem tem 'planning'; cada tarefa vai para o agente com a "
            "capacidade certa; outro agente revê.",
            assignment=Assignment.CAPABILITY,
            review=ReviewPolicy.OTHER,
            min_agents=2,
        ),
        Strategy(
            key="plan_implement_review",
            name="Planear → Implementar → Rever",
            description="O 1.º agente planeia e revê; o 2.º implementa todas as tarefas.",
            assignment=Assignment.SECOND_AGENT,
            review=ReviewPolicy.FIRST_AGENT,
            min_agents=2,
        ),
        Strategy(
            key="single",
            name="Agente sozinho (com auto-revisão)",
            description="Um único agente planeia, executa e revê o próprio trabalho.",
            assignment=Assignment.FIRST_AGENT,
            review=ReviewPolicy.SELF,
        ),
        Strategy(
            key="single_no_review",
            name="Agente sozinho (sem revisão)",
            description="Um único agente faz tudo, sem qualquer revisão. Linha de base.",
            assignment=Assignment.FIRST_AGENT,
            review=ReviewPolicy.NONE,
        ),
    ]
}
