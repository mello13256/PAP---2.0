"""Testes do AnthropicProvider contra um servidor HTTP simulado (SDK oficial verdadeiro)."""

import json

import httpx2
import pytest

from app.providers.anthropic_provider import AnthropicOptions, AnthropicProvider
from app.providers.base import (
    ChatMessage,
    GenerationRequest,
    ProviderError,
    ProviderErrorKind,
    StopReason,
    TextDelta,
    ToolCall,
    ToolCallArgumentsDelta,
    ToolCallStarted,
    ToolChoice,
    ToolSpec,
)

WRITE_FILE = ToolSpec(
    name="write_file",
    description="Escreve um ficheiro",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    },
)


def _sse(events: list[dict]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def _message_start(input_tokens: int = 20) -> dict:
    return {
        "type": "message_start",
        "message": {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-test",
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": input_tokens, "output_tokens": 1},
        },
    }


def _text_block(index: int, *parts: str) -> list[dict]:
    return [
        {
            "type": "content_block_start",
            "index": index,
            "content_block": {"type": "text", "text": ""},
        },
        *(
            {
                "type": "content_block_delta",
                "index": index,
                "delta": {"type": "text_delta", "text": p},
            }
            for p in parts
        ),
        {"type": "content_block_stop", "index": index},
    ]


def _thinking_block(index: int) -> list[dict]:
    return [
        {
            "type": "content_block_start",
            "index": index,
            "content_block": {"type": "thinking", "thinking": "", "signature": ""},
        },
        {
            "type": "content_block_delta",
            "index": index,
            "delta": {"type": "signature_delta", "signature": "assinatura-opaca"},
        },
        {"type": "content_block_stop", "index": index},
    ]


def _tool_block(index: int, tool_id: str, name: str, *json_parts: str) -> list[dict]:
    return [
        {
            "type": "content_block_start",
            "index": index,
            "content_block": {"type": "tool_use", "id": tool_id, "name": name, "input": {}},
        },
        *(
            {
                "type": "content_block_delta",
                "index": index,
                "delta": {"type": "input_json_delta", "partial_json": p},
            }
            for p in json_parts
        ),
        {"type": "content_block_stop", "index": index},
    ]


def _end(stop_reason: str, output_tokens: int = 10) -> list[dict]:
    return [
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": output_tokens},
        },
        {"type": "message_stop"},
    ]


class FakeServer:
    def __init__(self, *responses: httpx2.Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content) if request.content else {})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _stream(events: list[dict]) -> httpx2.Response:
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=_sse(events))


def _provider(server: FakeServer, **options) -> AnthropicProvider:
    return AnthropicProvider(
        api_key="test-key",
        base_url="http://anthropic.test",
        options=AnthropicOptions(**options),
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(server)),
    )


def _request(**kwargs) -> GenerationRequest:
    defaults = {
        "model": "claude-test",
        "messages": (ChatMessage.user("Revê a proposta"),),
        "system": "És o revisor.",
        "temperature": 0.2,
        "max_output_tokens": 1000,
    }
    return GenerationRequest(**{**defaults, **kwargs})


async def test_text_streaming_usage_and_request_format() -> None:
    server = FakeServer(
        _stream(
            [_message_start(25), *_text_block(0, "Revendo ", "a proposta..."), *_end("end_turn", 7)]
        )
    )
    events = [e async for e in _provider(server).stream(_request())]

    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Revendo ", "a proposta..."]
    result = events[-1].result
    assert result.text == "Revendo a proposta..."
    assert result.stop_reason is StopReason.END
    assert (result.usage.input_tokens, result.usage.output_tokens) == (25, 7)
    assert result.model == "claude-test"

    sent = server.requests[0]
    assert sent["system"] == "És o revisor."
    assert sent["max_tokens"] == 1000
    assert sent["stream"] is True
    assert "temperature" not in sent  # rejeitada pelos modelos atuais e pelo SDK 1.x
    assert sent["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "Revê a proposta"}]}
    ]


async def test_tool_use_is_streamed_and_assembled() -> None:
    server = FakeServer(
        _stream(
            [
                _message_start(),
                *_text_block(0, "Vou criar o ficheiro."),
                *_tool_block(
                    1, "toolu_1", "write_file", '{"path": "src/', 'api.py", "content": "x"}'
                ),
                *_end("tool_use"),
            ]
        )
    )
    events = [e async for e in _provider(server).stream(_request(tools=(WRITE_FILE,)))]

    assert any(isinstance(e, ToolCallStarted) and e.id == "toolu_1" for e in events)
    fragments = [e for e in events if isinstance(e, ToolCallArgumentsDelta)]
    assert {e.id for e in fragments} == {"toolu_1"} and len(fragments) == 2
    result = events[-1].result
    assert result.stop_reason is StopReason.TOOL_USE
    assert result.tool_calls == (
        ToolCall("toolu_1", "write_file", {"path": "src/api.py", "content": "x"}),
    )
    tool = server.requests[0]["tools"][0]
    assert tool["input_schema"] == WRITE_FILE.parameters
    assert tool["eager_input_streaming"] is True


async def test_forced_tool_becomes_auto_plus_instruction_by_default() -> None:
    server = FakeServer(_stream([_message_start(), *_text_block(0, "ok"), *_end("end_turn")]))
    await _provider(server).generate(
        _request(tools=(WRITE_FILE,), tool_choice=ToolChoice.force("write_file"))
    )
    sent = server.requests[0]
    assert sent["tool_choice"] == {"type": "auto"}
    assert "`write_file`" in sent["system"]


async def test_forced_tool_choice_option() -> None:
    server = FakeServer(_stream([_message_start(), *_text_block(0, "ok"), *_end("end_turn")]))
    await _provider(server, force_tool_choice=True).generate(
        _request(tools=(WRITE_FILE,), tool_choice=ToolChoice.force("write_file"))
    )
    assert server.requests[0]["tool_choice"] == {"type": "tool", "name": "write_file"}


async def test_thinking_blocks_are_sent_back_unchanged_in_tool_loops() -> None:
    first = _stream(
        [
            _message_start(),
            *_thinking_block(0),
            *_tool_block(1, "toolu_1", "write_file", '{"path": "a.py", "content": "x"}'),
            *_end("tool_use"),
        ]
    )
    second = _stream([_message_start(), *_text_block(0, "Feito."), *_end("end_turn")])
    server = FakeServer(first, second)
    provider = _provider(server)

    result = await provider.generate(_request(tools=(WRITE_FILE,)))
    history = (
        ChatMessage.user("Cria a.py"),
        ChatMessage.from_result(result),
        ChatMessage.tool_result("toolu_1", "versão 1 criada"),
        ChatMessage.tool_result("toolu_2", "caminho inválido", is_error=True),
    )
    await provider.generate(_request(messages=history, tools=(WRITE_FILE,)))

    messages = server.requests[1]["messages"]
    assistant = messages[1]
    assert assistant["role"] == "assistant"
    assert assistant["content"][0]["type"] == "thinking"
    assert assistant["content"][0]["signature"] == "assinatura-opaca"
    assert assistant["content"][1]["type"] == "tool_use"
    # Os dois resultados vão numa única mensagem do utilizador.
    assert len(messages) == 3
    assert [b["type"] for b in messages[2]["content"]] == ["tool_result", "tool_result"]
    assert messages[2]["content"][1]["is_error"] is True


async def test_history_from_another_provider_is_rebuilt() -> None:
    server = FakeServer(_stream([_message_start(), *_text_block(0, "ok"), *_end("end_turn")]))
    history = (
        ChatMessage.user("olá"),
        ChatMessage.assistant("", (ToolCall("call_x", "write_file", {"path": "b.py"}),)),
        ChatMessage.tool_result("call_x", "ok"),
    )
    await _provider(server).generate(_request(messages=history))
    assistant = server.requests[0]["messages"][1]
    assert assistant["content"] == [
        {"type": "tool_use", "id": "call_x", "name": "write_file", "input": {"path": "b.py"}}
    ]


@pytest.mark.parametrize(
    ("stop", "expected"),
    [("max_tokens", StopReason.MAX_TOKENS), ("refusal", StopReason.REFUSAL)],
)
async def test_stop_reasons(stop: str, expected: StopReason) -> None:
    server = FakeServer(_stream([_message_start(), *_text_block(0, "..."), *_end(stop)]))
    assert (await _provider(server).generate(_request())).stop_reason is expected


@pytest.mark.parametrize(
    ("status", "error_type", "kind"),
    [
        (401, "authentication_error", ProviderErrorKind.AUTHENTICATION),
        (403, "permission_error", ProviderErrorKind.AUTHENTICATION),
        (402, "billing_error", ProviderErrorKind.QUOTA),
        (404, "not_found_error", ProviderErrorKind.BAD_REQUEST),
        (429, "rate_limit_error", ProviderErrorKind.RATE_LIMIT),
        (529, "overloaded_error", ProviderErrorKind.UNAVAILABLE),
    ],
)
async def test_http_errors_are_normalized(status: int, error_type: str, kind) -> None:
    body = {"type": "error", "error": {"type": error_type, "message": "falhou"}}
    server = FakeServer(httpx2.Response(status, json=body))
    with pytest.raises(ProviderError) as info:
        await _provider(server).generate(_request())
    assert info.value.kind is kind
    assert info.value.provider == "anthropic"


async def test_connection_error_is_unavailable() -> None:
    server = FakeServer(httpx2.ConnectError("sem rede"))
    with pytest.raises(ProviderError) as info:
        await _provider(server).generate(_request())
    assert info.value.kind is ProviderErrorKind.UNAVAILABLE
    assert info.value.retryable


async def test_count_tokens() -> None:
    server = FakeServer(httpx2.Response(200, json={"input_tokens": 42}))
    assert await _provider(server).count_tokens(_request()) == 42
    assert "max_tokens" not in server.requests[0]
