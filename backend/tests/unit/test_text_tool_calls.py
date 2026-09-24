from app.providers.text_tool_calls import extract_tool_calls

GRANITE_REAL_OUTPUT = """```python
{
  "function_call": {
    "name": "submit_answer",
    "arguments": {
      "answer": "Lisboa",
      "confidence": 1.0
    }
  }
}
```"""


def test_real_granite_output_is_recovered() -> None:
    [call] = extract_tool_calls(GRANITE_REAL_OUTPUT, ["submit_answer"])
    assert call.name == "submit_answer"
    assert call.arguments == {"answer": "Lisboa", "confidence": 1.0}


def test_plain_name_arguments_format_inside_prose() -> None:
    text = 'Vou entregar: {"name": "write_file", "arguments": {"path": "a.py", "content": "x"}} fim'
    [call] = extract_tool_calls(text, ["write_file"])
    assert call.arguments["path"] == "a.py"


def test_arguments_as_json_string_and_lists() -> None:
    text = '[{"name": "a", "arguments": "{\\"x\\": 1}"}, {"name": "b", "parameters": {"y": 2}}]'
    calls = extract_tool_calls(text, ["a", "b"])
    assert [(c.name, c.arguments) for c in calls] == [("a", {"x": 1}), ("b", {"y": 2})]


def test_undeclared_tools_are_ignored() -> None:
    # Segurança: o modelo não pode "inventar" ferramentas que não lhe foram dadas.
    text = '{"name": "delete_everything", "arguments": {}}'
    assert extract_tool_calls(text, ["submit_answer"]) == []


def test_normal_text_and_non_object_arguments() -> None:
    assert extract_tool_calls("A capital é Lisboa. {não é json}", ["submit_answer"]) == []
    assert (
        extract_tool_calls('{"name": "submit_answer", "arguments": [1]}', ["submit_answer"]) == []
    )


def test_no_declared_tools_means_no_recovery() -> None:
    assert extract_tool_calls(GRANITE_REAL_OUTPUT, []) == []
