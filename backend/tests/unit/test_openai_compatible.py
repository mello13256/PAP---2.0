"""Testes do OpenAICompatibleProvider contra um servidor HTTP simulado.

Usamos o SDK oficial verdadeiro; só a camada de rede é substituída por um
``MockTransport`` que devolve respostas no formato real da API (SSE).
"""

import json

import httpx2
import pytest

from app.providers.base import (
    ChatMessage,
    GenerationRequest,
    ProviderError,
    ProviderErrorKind,
    StopReason,
    StreamCompleted,
    TextDelta,
    ToolCall,
    ToolCallArgumentsDelta,
    ToolChoice,
    ToolSpec,
)
from app.providers.openai_compatible import OpenAICompatibleOptions, OpenAICompatibleProvider

WRITE_FILE = ToolSpec(
    name="write_file",
    description="Escreve um ficheiro no workspace",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    },
)


def _chunk(delta: dict | None = None, finish: str | None = None, usage: dict | None = None):
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "granite-test",
        "choices": [] if delta is None else [{"index": 0, "delta": delta, "finish_reason": finish}],
        **({"usage": usage} if usage else {}),
    }


def _sse(chunks: list[dict]) -> bytes:
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    return body.encode()


class FakeServer:
    """Regista os pedidos recebidos e devolve uma resposta pré-definida."""

    def __init__(self, response: httpx2.Response | Exception) -> None:
        self.response = response
        self.requests: list[dict] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content) if request.content else {})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _stream_response(chunks: list[dict]) -> httpx2.Response:
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=_sse(chunks))


def _provider(server: FakeServer, **options) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        "ollama",
        api_key="test-key",
        base_url="http://llm.test/v1",
        options=OpenAICompatibleOptions(**options),
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(server)),
    )


def _request(**kwargs) -> GenerationRequest:
    defaults = {
        "model": "granite-test",
        "messages": (ChatMessage.user("Analisa a tarefa"),),
        "system": "És o planner.",
        "temperature": 0.3,
        "max_output_tokens": 256,
    }
    return GenerationRequest(**{**defaults, **kwargs})


async def test_text_is_streamed_and_usage_collected() -> None:
    server = FakeServer(
        _stream_response(
            [
                _chunk({"role": "assistant", "content": "Analisei "}),
                _chunk({"content": "a tarefa."}),
                _chunk({}, finish="stop"),
                _chunk(usage={"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16}),
            ]
        )
    )
    events = [e async for e in _provider(server).stream(_request())]

    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Analisei ", "a tarefa."]
    result = events[-1].result
    assert isinstance(events[-1], StreamCompleted)
    assert result.text == "Analisei a tarefa."
    assert result.stop_reason is StopReason.END
    assert (result.usage.input_tokens, result.usage.output_tokens) == (12, 4)
    assert result.model == "granite-test"


async def test_request_is_translated_to_the_openai_format() -> None:
    server = FakeServer(_stream_response([_chunk({"content": "ok"}, finish="stop")]))
    history = (
        ChatMessage.user("Cria o ficheiro"),
        ChatMessage.assistant("", (ToolCall("call_1", "write_file", {"path": "a.py"}),)),
        ChatMessage.tool_result("call_1", "caminho inválido", is_error=True),
    )
    await _provider(server).generate(
        _request(messages=history, tools=(WRITE_FILE,), tool_choice=ToolChoice.force("write_file"))
    )

    sent = server.requests[0]
    assert sent["model"] == "granite-test"
    assert sent["stream"] is True
    assert sent["stream_options"] == {"include_usage": True}
    assert sent["max_tokens"] == 256
    assert sent["temperature"] == 0.3
    assert sent["messages"][0] == {"role": "system", "content": "És o planner."}
    assert sent["messages"][2]["tool_calls"][0]["function"] == {
        "name": "write_file",
        "arguments": '{"path": "a.py"}',
    }
    assert sent["messages"][3] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "ERRO: caminho inválido",
    }
    assert sent["tools"][0]["function"]["name"] == "write_file"
    assert sent["tool_choice"] == {"type": "function", "function": {"name": "write_file"}}


async def test_max_completion_tokens_option() -> None:
    server = FakeServer(_stream_response([_chunk({"content": "ok"}, finish="stop")]))
    await _provider(server, max_tokens_param="max_completion_tokens").generate(_request())
    assert "max_tokens" not in server.requests[0]
    assert server.requests[0]["max_completion_tokens"] == 256


async def test_streamed_tool_call_fragments_are_assembled() -> None:
    first = {
        "tool_calls": [
            {
                "index": 0,
                "id": "call_abc",
                "type": "function",
                "function": {"name": "write_file", "arguments": '{"path": "src/'},
            }
        ]
    }
    second = {"tool_calls": [{"index": 0, "function": {"arguments": 'api.py", "content": "x"}'}}]}
    server = FakeServer(
        _stream_response([_chunk(first), _chunk(second), _chunk({}, finish="tool_calls")])
    )
    events = [e async for e in _provider(server).stream(_request(tools=(WRITE_FILE,)))]

    fragments = [e.delta for e in events if isinstance(e, ToolCallArgumentsDelta)]
    assert len(fragments) == 2
    result = events[-1].result
    assert result.stop_reason is StopReason.TOOL_USE
    assert result.tool_calls == (
        ToolCall("call_abc", "write_file", {"path": "src/api.py", "content": "x"}),
    )


async def test_tool_calls_with_finish_reason_stop_are_still_tool_use() -> None:
    # Comportamento observado em alguns servidores compatíveis (ex.: Ollama).
    delta = {
        "tool_calls": [
            {"index": 0, "id": "c1", "function": {"name": "submit_result", "arguments": "{}"}}
        ]
    }
    server = FakeServer(_stream_response([_chunk(delta, finish="stop")]))
    result = await _provider(server).generate(_request(tools=(WRITE_FILE,)))
    assert result.stop_reason is StopReason.TOOL_USE


async def test_invalid_tool_arguments_are_an_invalid_output_error() -> None:
    delta = {
        "tool_calls": [{"index": 0, "id": "c1", "function": {"name": "x", "arguments": "{nope"}}]
    }
    server = FakeServer(_stream_response([_chunk(delta, finish="tool_calls")]))
    with pytest.raises(ProviderError) as info:
        await _provider(server).generate(_request(tools=(WRITE_FILE,)))
    assert info.value.kind is ProviderErrorKind.INVALID_OUTPUT


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (401, ProviderErrorKind.AUTHENTICATION),
        (403, ProviderErrorKind.AUTHENTICATION),
        (429, ProviderErrorKind.RATE_LIMIT),
        (404, ProviderErrorKind.BAD_REQUEST),  # ex.: modelo não existe
        (400, ProviderErrorKind.BAD_REQUEST),
        (503, ProviderErrorKind.UNAVAILABLE),
    ],
)
async def test_http_errors_are_normalized(status: int, kind: ProviderErrorKind) -> None:
    server = FakeServer(httpx2.Response(status, json={"error": {"message": "falhou"}}))
    with pytest.raises(ProviderError) as info:
        await _provider(server).generate(_request())
    assert info.value.kind is kind
    assert info.value.provider == "ollama"


async def test_connection_refused_is_unavailable() -> None:
    # O que acontece quando o Ollama não está a correr.
    server = FakeServer(httpx2.ConnectError("Connection refused"))
    with pytest.raises(ProviderError) as info:
        await _provider(server).generate(_request())
    assert info.value.kind is ProviderErrorKind.UNAVAILABLE
    assert info.value.retryable


async def test_tools_rejected_when_provider_has_no_tool_support() -> None:
    server = FakeServer(_stream_response([]))
    with pytest.raises(ProviderError) as info:
        await _provider(server, supports_tools=False).generate(_request(tools=(WRITE_FILE,)))
    assert info.value.kind is ProviderErrorKind.BAD_REQUEST
    assert server.requests == []


async def test_list_models() -> None:
    server = FakeServer(
        httpx2.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"id": "llama3.2:3b", "object": "model", "created": 0, "owned_by": "x"},
                    {"id": "granite3.3:2b", "object": "model", "created": 0, "owned_by": "x"},
                ],
            },
        )
    )
    assert await _provider(server).list_models() == ["granite3.3:2b", "llama3.2:3b"]
