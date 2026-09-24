"""Constrói o AgentRuntime de um agente guardado na BD.

É aqui que a chave de provider guardada no agente ("ollama", "anthropic", ...)
é resolvida através do registry. Nenhum outro código faz esse mapeamento.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.models import Agent
from app.agents.runtime import AgentRuntime, AgentSpec, CallRecorder, RetryPolicy
from app.providers.pricing import PricingTable
from app.providers.registry import ProviderRegistry


@dataclass
class RuntimeFactory:
    registry: ProviderRegistry
    recorder: CallRecorder
    pricing: PricingTable
    retry: RetryPolicy | None = None

    def build(self, agent: Agent) -> AgentRuntime:
        return AgentRuntime(
            AgentSpec.from_model(agent),
            self.registry.get(agent.provider),
            recorder=self.recorder,
            pricing=self.pricing,
            retry=self.retry,
        )
