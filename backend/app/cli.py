"""Ferramentas de linha de comandos para verificar os providers.

Exemplos (dentro de backend/, com o ambiente virtual ativo):

    python -m app.cli providers
    python -m app.cli models --provider ollama
    python -m app.cli ping --provider ollama --model granite3.3:2b
    python -m app.cli ping --provider ollama --model granite3.3:2b --tools
    python -m app.cli run "Cria uma app de inventário"
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.agents.runtime import AgentRuntime, AgentSpec, CallContext, InMemoryCallRecorder
from app.core.config import BACKEND_DIR, get_settings
from app.metrics.models import CallPurpose
from app.providers.base import (
    ChatMessage,
    ProviderError,
    StreamCompleted,
    TextDelta,
    ToolCallCompleted,
    ToolChoice,
    ToolSpec,
)
from app.providers.pricing import PricingTable
from app.providers.setup import build_registry

_DEMO_TOOL = ToolSpec(
    name="submit_answer",
    description="Entrega a resposta final de forma estruturada.",
    parameters={
        "type": "object",
        "properties": {
            "answer": {"type": "string", "description": "A resposta"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["answer", "confidence"],
    },
)


async def _providers() -> int:
    for key in build_registry(get_settings()).available():
        print(key)
    return 0


async def _models(provider_key: str) -> int:
    provider = build_registry(get_settings()).get(provider_key)
    models = await provider.list_models()
    if models is None:
        print("Este provider não permite listar modelos.")
    else:
        print("\n".join(models) or "(nenhum modelo instalado)")
    return 0


async def _ping(provider_key: str, model: str, prompt: str, use_tools: bool) -> int:
    registry = build_registry(get_settings())
    recorder = InMemoryCallRecorder()
    runtime = AgentRuntime(
        AgentSpec(id=None, name=f"{provider_key}:{model}", provider=provider_key, model=model),
        registry.get(provider_key),
        recorder=recorder,
        pricing=PricingTable.from_file(BACKEND_DIR / "pricing.json"),
    )
    called_tool = False
    print(f"[{runtime.spec.name}] ", end="", flush=True)
    async for event in runtime.stream(
        [ChatMessage.user(prompt)],
        context=CallContext(CallPurpose.PING),
        tools=[_DEMO_TOOL] if use_tools else [],
        tool_choice=ToolChoice.force(_DEMO_TOOL.name) if use_tools else None,
    ):
        if isinstance(event, TextDelta):
            print(event.text, end="", flush=True)
        elif isinstance(event, ToolCallCompleted):
            called_tool = True
            print(f"\n→ ferramenta {event.tool_call.name}({event.tool_call.arguments})", end="")
        elif isinstance(event, StreamCompleted):
            print()
            if event.result.tool_calls_from_text:
                print("  (chamada recuperada do texto: o modelo escreveu-a em JSON)")

    if use_tools and not called_tool:
        print("  AVISO: o modelo respondeu com texto e NÃO chamou a ferramenta.")
    for record in recorder.records:
        cost = "—" if record.estimated_cost_usd is None else f"${record.estimated_cost_usd:.6f}"
        print(
            f"  sucesso={record.success}  tokens={record.usage.input_tokens}→"
            f"{record.usage.output_tokens}  latência={record.latency_ms}ms  custo={cost}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # acentos na consola do Windows

    parser = argparse.ArgumentParser(prog="python -m app.cli", description="MultiMind CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("providers", help="lista os providers configurados")
    models = sub.add_parser("models", help="lista os modelos de um provider")
    models.add_argument("--provider", required=True)
    ping = sub.add_parser("ping", help="envia uma mensagem de teste a um modelo")
    ping.add_argument("--provider", required=True)
    ping.add_argument("--model", required=True)
    ping.add_argument("--prompt", default=None)
    ping.add_argument("--tools", action="store_true", help="testa o uso de ferramentas")
    run = sub.add_parser("run", help="põe os agentes a trabalhar num objetivo (tempo real)")
    run.add_argument("objective", help='ex.: "Cria uma app de inventário"')
    run.add_argument(
        "--strategy",
        default="collaborative",
        help="collaborative | plan_implement_review | single | single_no_review",
    )
    run.add_argument("--agents", help="nomes dos agentes, por ordem, ex.: Granite,Qwen")
    run.add_argument(
        "--project", default="Terminal", help="nome do projeto (criado se não existir)"
    )
    run.add_argument("--email", help="conta a usar (se houver várias)")
    args = parser.parse_args(argv)

    if args.command == "run":
        from app.cli_run import main as run_main

        return run_main(args)

    try:
        if args.command == "providers":
            return asyncio.run(_providers())
        if args.command == "models":
            return asyncio.run(_models(args.provider))
        prompt = args.prompt or (
            "Qual é a capital de Portugal? Responde usando a ferramenta submit_answer."
            if args.tools
            else "Apresenta-te numa frase, em português."
        )
        return asyncio.run(_ping(args.provider, args.model, prompt, args.tools))
    except ProviderError as exc:
        print(f"\nERRO ({exc.kind}): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
