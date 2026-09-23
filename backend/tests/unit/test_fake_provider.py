from app.providers.base import (
    ChatMessage,
    GenerationRequest,
    ProviderError,
    ProviderErrorKind,
    StopReason,
    StreamCompleted,
    TextDelta,
    ToolCallCompleted,
    ToolCallStarted,
)
from app.providers.fake_provider import FakeProvider, FakeResponse


def _request(text: str = "olá") -> GenerationRequest:
    return GenerationRequest(model="fake-model", messages=(ChatMessage.user(text),))


async def test_stream_sends_text_in_chunks_and_ends_with_result() -> None:
    provider = FakeProvider([FakeResponse(text="Analisei a tarefa. Recomendo REST.")], chunk_size=5)
    events = [e async for e in provider.stream(_request())]

    deltas = [e.text for e in events if isinstance(e, TextDelta)]
    assert len(deltas) > 1
    assert "".join(deltas) == "Analisei a tarefa. Recomendo REST."
    assert isinstance(events[-1], StreamCompleted)
    assert events[-1].result.stop_reason is StopReason.END


async def test_tool_calls_are_streamed_and_collected() -> None:
    provider = FakeProvider(
        [FakeResponse(tool_calls=[("write_file", {"path": "src/api.py", "content": "x = 1"})])]
    )
    events = [e async for e in provider.stream(_request())]

    assert any(isinstance(e, ToolCallStarted) and e.name == "write_file" for e in events)
    completed = [e for e in events if isinstance(e, ToolCallCompleted)]
    assert completed[0].tool_call.arguments == {"path": "src/api.py", "content": "x = 1"}
    result = events[-1].result
    assert result.stop_reason is StopReason.TOOL_USE
    assert result.tool_calls[0].name == "write_file"


async def test_generate_returns_final_result_and_usage() -> None:
    provider = FakeProvider([FakeResponse(text="um dois três")])
    result = await provider.generate(_request())
    assert result.text == "um dois três"
    assert result.usage.output_tokens == 3
    assert result.model == "fake-model"


async def test_responder_function_sees_the_request() -> None:
    provider = FakeProvider(lambda req: FakeResponse(text=req.messages[-1].content.upper()))
    result = await provider.generate(_request("eco"))
    assert result.text == "ECO"
    assert provider.requests[0].messages[0].content == "eco"


async def test_scripted_errors_are_raised() -> None:
    provider = FakeProvider(
        [FakeResponse(error=ProviderError(ProviderErrorKind.RATE_LIMIT, "429"))]
    )
    try:
        await provider.generate(_request())
    except ProviderError as exc:
        assert exc.retryable
    else:
        raise AssertionError("devia ter falhado")
