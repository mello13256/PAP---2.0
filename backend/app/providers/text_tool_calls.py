"""Recuperação de chamadas a ferramentas escritas como texto.

Alguns modelos locais (observado com o IBM Granite no Ollama, ver
docs/registos/2026-09-24-primeiro-teste-ollama.md) "querem" chamar uma
ferramenta, mas escrevem a chamada em JSON no texto da resposta em vez de
usarem o mecanismo nativo de tool calling. Exemplo real:

    ```python
    {"function_call": {"name": "submit_answer", "arguments": {"answer": "Lisboa"}}}
    ```

Este módulo procura esses objetos JSON e converte-os em ``ToolCall``. Por
segurança só aceita chamadas a ferramentas **declaradas no pedido** e com
argumentos que sejam um objeto JSON. A validação dos argumentos em si
continua a ser feita por quem executa a ferramenta.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from typing import Any

from app.providers.base import ToolCall

_FENCE = re.compile(r"```[a-zA-Z0-9_-]*\s*\n(.*?)```", re.DOTALL)
_MAX_CALLS = 8


def _json_values(text: str) -> Iterator[Any]:
    """Todos os valores JSON (objetos ou listas) que aparecem no texto."""
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text):
        starts = [p for p in (text.find("{", index), text.find("[", index)) if p != -1]
        if not starts:
            return
        start = min(starts)
        try:
            value, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            index = start + 1
            continue
        yield value
        index = end


def _as_call(value: Any) -> tuple[str, Any] | None:
    if not isinstance(value, dict):
        return None
    for key in ("function_call", "function", "tool_call"):
        inner = value.get(key)
        if isinstance(inner, dict):
            value = inner
            break
    name = value.get("name") or value.get("tool")
    if not isinstance(name, str):
        return None
    arguments = next(
        (value[k] for k in ("arguments", "parameters", "args", "input") if k in value), {}
    )
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return None
    return name, arguments


def extract_tool_calls(text: str, allowed_names: Iterable[str]) -> list[ToolCall]:
    allowed = set(allowed_names)
    if not allowed or not text.strip():
        return []

    # Blocos ```...``` primeiro; se não houver, o texto todo.
    sources = _FENCE.findall(text) or [text]
    calls: list[ToolCall] = []
    for source in sources:
        for value in _json_values(source):
            items = value if isinstance(value, list) else [value]
            for item in items:
                parsed = _as_call(item)
                if parsed is None:
                    continue
                name, arguments = parsed
                if name in allowed and isinstance(arguments, dict):
                    calls.append(
                        ToolCall(id=f"text_call_{len(calls) + 1}", name=name, arguments=arguments)
                    )
                if len(calls) >= _MAX_CALLS:
                    return calls
    return calls
