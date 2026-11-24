import json

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

from devlog.llm import AnthropicClient, LLMError, Tool


class Summary(BaseModel):
    what_changed: str


class Commit(BaseModel):
    link: str


TOOL_CALL = {"type": "tool_use", "id": "toolu_1", "name": "read_diff", "input": {"link": "abc123"}}


def client_answering(stop_reason: str, *texts: str) -> AnthropicClient:
    return client_replying(stop_reason, [{"type": "text", "text": text} for text in texts])


def client_replying(stop_reason: str, content: list[dict]) -> AnthropicClient:
    message = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    transport = httpx2.MockTransport(lambda request: httpx2.Response(200, json=message))
    http_client = anthropic.DefaultHttpxClient(transport=transport)
    sdk = anthropic.Anthropic(api_key="test", http_client=http_client, max_retries=0)
    return AnthropicClient(sdk, "claude-opus-5-5")


def test_adapter_returns_the_parsed_structured_output():
    client = client_answering("end_turn", json.dumps({"what_changed": "Added retries."}))

    answer = client.complete("You summarise work.", "Summarise this thread.", Summary)

    assert answer == Summary(what_changed="Added retries.")


def test_a_refusal_is_an_error_not_an_empty_answer():
    client = client_answering("refusal")

    with pytest.raises(LLMError, match="refusal"):
        client.complete("You summarise work.", "Summarise this thread.", Summary)


def test_tool_calls_stop_at_the_cap():
    client = client_replying("tool_use", [TOOL_CALL])
    runs = []

    def read_diff(commit: Commit) -> str:
        runs.append(commit)
        return "a diff"

    tool = Tool("read_diff", "The diff of a commit.", Commit, read_diff)
    with pytest.raises(LLMError, match="tool_use"):
        client.complete("You summarise work.", "Summarise this thread.", Summary, [tool])

    assert len(runs) == 8


def test_a_failing_tool_fails_the_answer():
    client = client_replying("tool_use", [TOOL_CALL])

    def read_diff(commit: Commit) -> str:
        raise RuntimeError("git failed")

    tool = Tool("read_diff", "The diff of a commit.", Commit, read_diff)
    with pytest.raises(LLMError, match="a tool failed"):
        client.complete("You summarise work.", "Summarise this thread.", Summary, [tool])
