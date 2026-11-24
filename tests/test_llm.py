import json

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

from devlog.llm import AnthropicClient, LLMError


class Summary(BaseModel):
    what_changed: str


def client_answering(stop_reason: str, *texts: str) -> AnthropicClient:
    message = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text} for text in texts],
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
