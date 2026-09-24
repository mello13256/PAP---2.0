"""Agentes criados automaticamente para cada utilizador novo.

Correspondem ao cenário de orçamento zero (DT-01): dois modelos locais de
famílias diferentes, via Ollama, mais um agente simulado (desativado) para
ensaios sem gastar recursos. Tudo é editável depois na aplicação.
"""

from __future__ import annotations

from app.agents.models import AgentCapability as Cap

_BASE_PROMPT = (
    "És um agente do MultiMind, uma plataforma onde vários modelos de linguagem "
    "colaboram. Trabalhas em equipa com outros agentes através de um orquestrador. "
    "Responde sempre em português de Portugal, de forma clara e objetiva. "
    "Quando discordares de outro agente, explica porquê com argumentos concretos."
)

DEFAULT_AGENTS: list[dict] = [
    {
        "name": "Granite",
        "provider": "ollama",
        "model": "granite3.3:8b",
        "capabilities": [
            Cap.PLANNING,
            Cap.ARCHITECTURE,
            Cap.REVIEW,
            Cap.DOCUMENTATION,
            Cap.SYNTHESIS,
        ],
        "system_prompt": _BASE_PROMPT
        + " O teu ponto forte é organizar o trabalho, rever com espírito crítico e sintetizar.",
        "config": {"temperature": 0.3, "max_output_tokens": 4096},
        "enabled": True,
    },
    {
        "name": "Qwen",
        "provider": "ollama",
        "model": "qwen3:8b",
        "capabilities": [Cap.CODING, Cap.TESTING, Cap.ARCHITECTURE, Cap.REVIEW],
        "system_prompt": _BASE_PROMPT
        + " O teu ponto forte é implementar código correto e escrever testes.",
        "config": {"temperature": 0.3, "max_output_tokens": 4096},
        "enabled": True,
    },
    {
        "name": "Simulado",
        "provider": "fake",
        "model": "fake-model",
        "capabilities": [c.value for c in Cap],
        "system_prompt": "Agente simulado, para ensaios. Não usa nenhum modelo real.",
        "config": {},
        "enabled": False,
    },
]
