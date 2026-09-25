"""Guião determinístico para simular uma equipa de agentes nos testes."""

from __future__ import annotations

from app.providers.base import GenerationRequest
from app.providers.fake_provider import FakeResponse

PLAN = {
    "tasks": [
        {
            "key": "T1",
            "title": "Definir arquitetura",
            "description": "Escrever docs/ARCHITECTURE.md",
            "acceptance_criteria": "Documento com as camadas",
            "required_capability": "architecture",
            "depends_on": [],
        },
        {
            "key": "T2",
            "title": "Implementar backend",
            "description": "Criar src/app.py",
            "acceptance_criteria": "Validar stock negativo",
            "required_capability": "coding",
            "depends_on": ["T1"],
        },
    ]
}

BUGGY = "def update(qty):\n    return qty\n"
FIXED = (
    "def update(qty):\n"
    "    if qty < 0:\n"
    "        raise ValueError('stock negativo')\n"
    "    return qty\n"
)


def team_script(request: GenerationRequest) -> FakeResponse:
    prompt = request.messages[0].content
    if "Divide o objetivo em tarefas" in prompt:
        return FakeResponse(text="Proponho duas tarefas.", tool_calls=[("submit_plan", PLAN)])
    if "Escreve o relatório final" in prompt:
        return FakeResponse(tool_calls=[("submit_result", {"summary": "Relatório: app criada."})])
    if "# Tarefa a rever: T1" in prompt:
        return FakeResponse(
            tool_calls=[
                (
                    "submit_review",
                    {
                        "verdict": "APPROVED",
                        "summary": "Arquitetura clara.",
                        "issues": [{"severity": "INFO", "description": "Podia ter diagrama."}],
                    },
                )
            ]
        )
    if "# Tarefa a rever: T2" in prompt:
        if "# Revisão anterior" not in prompt:
            return FakeResponse(
                tool_calls=[
                    (
                        "submit_review",
                        {
                            "verdict": "NEEDS_REVISION",
                            "summary": "Falta validação.",
                            "issues": [
                                {
                                    "severity": "MAJOR",
                                    "file": "src/app.py",
                                    "description": "Aceita stock negativo",
                                    "suggestion": "Validar qty >= 0",
                                }
                            ],
                        },
                    )
                ]
            )
        return FakeResponse(
            tool_calls=[
                (
                    "submit_review",
                    {
                        "verdict": "APPROVED",
                        "summary": "Corrigido.",
                        "issues": [],
                    },
                )
            ]
        )
    if "# A tua tarefa: T1" in prompt:
        return FakeResponse(
            text="Analisei a tarefa. Recomendo arquitetura REST.",
            tool_calls=[
                (
                    "write_file",
                    {
                        "path": "docs/ARCHITECTURE.md",
                        "content": "# Arquitetura\nREST",
                        "summary": "arquitetura",
                    },
                ),
                ("submit_result", {"summary": "Arquitetura definida."}),
            ],
        )
    if "# A tua tarefa: T2" in prompt:
        if "# Revisão a corrigir" in prompt:
            return FakeResponse(
                text="Vou corrigir.",
                tool_calls=[
                    (
                        "write_file",
                        {"path": "src/app.py", "content": FIXED, "summary": "validação"},
                    ),
                    ("submit_result", {"summary": "Validação adicionada."}),
                ],
            )
        return FakeResponse(
            tool_calls=[
                (
                    "write_file",
                    {"path": "src/app.py", "content": BUGGY, "summary": "primeira versão"},
                ),
                ("submit_result", {"summary": "Backend criado."}),
            ]
        )
    raise AssertionError(f"Prompt inesperado: {prompt[:200]}")
