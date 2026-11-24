"""The LLM the journal is written with, behind a protocol so nothing else depends on a provider."""

import hashlib
import itertools
import json
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import anthropic
from anthropic.lib.tools import BetaFunctionTool
from pydantic import BaseModel, ValidationError

_MAX_TOKENS = 16000
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_MAX_TOOL_CALLS = 8
_NO_CALLS_LEFT = "Refused: no tool calls are left for this answer. Answer with what you have."


class LLMError(RuntimeError):
    """The model did not return a complete answer."""


@dataclass(frozen=True)
class Tool:
    """Anything the model might call while answering: `run` gets a validated `input` instance."""

    name: str
    description: str
    input: type[BaseModel]
    run: Callable[[Any], str]


@dataclass(frozen=True)
class Usage:
    """Tokens spent: `input` counts everything sent, of which `cached` was read from the cache."""

    input: int = 0
    cached: int = 0
    output: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input + other.input, self.cached + other.cached, self.output + other.output
        )


class LLMClient(Protocol):
    """Answers one prompt with a validated instance of the requested model."""

    @property
    def model(self) -> str:
        """The id of the model that answers."""
        ...

    @property
    def usage(self) -> Usage:
        """The tokens this client has spent so far, over all its answers."""
        ...

    def complete[T: BaseModel](
        self, system: str, prompt: str, output: type[T], tools: Sequence[Tool] = ()
    ) -> T:
        """Return the model's answer to `prompt`, parsed and validated as `output`.

        The model may call `tools` first, up to a fixed number of calls per answer.
        """
        ...


class AnthropicClient:
    """An `LLMClient` backed by the Anthropic API.

    If the model declines a request, the API retries it on Anthropic's recommended fallback model.
    """

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self._client = client
        self.model = model
        self._usage = Usage()
        self._lock = threading.Lock()

    @property
    def usage(self) -> Usage:
        """The tokens this client has spent so far, over all its answers."""
        return self._usage

    def complete[T: BaseModel](
        self, system: str, prompt: str, output: type[T], tools: Sequence[Tool] = ()
    ) -> T:
        """Return the model's answer to `prompt`, parsed and validated as `output`.

        The model may call `tools` first, up to a fixed number of calls per answer.
        """
        calls = itertools.count(1)
        failures: list[Exception] = []

        def runnable(tool: Tool) -> BetaFunctionTool:
            def call(**arguments: Any) -> str:
                if next(calls) > _MAX_TOOL_CALLS:
                    return _NO_CALLS_LEFT
                request = tool.input(**arguments)
                try:
                    return tool.run(request)
                except Exception as error:
                    failures.append(error)
                    raise

            return BetaFunctionTool(
                call, name=tool.name, description=tool.description, input_schema=tool.input
            )

        try:
            runner = self._client.beta.messages.tool_runner(
                model=self.model,
                max_tokens=_MAX_TOKENS,
                betas=[_FALLBACK_BETA],
                fallbacks="default",
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=output,
                tools=[runnable(tool) for tool in tools],
                max_iterations=_MAX_TOOL_CALLS + 2,
                thread=False,
            )
            # One message per request: an answer costs a request for each round of tool calls.
            for message in runner:
                self._spend(message.usage)
            response = runner.until_done()
        except ValidationError as error:
            raise LLMError("the model's answer was cut short or did not fit the schema") from error

        if failures:
            raise LLMError("a tool failed while the model was answering") from failures[0]

        if response.stop_reason != "end_turn" or response.parsed_output is None:
            raise LLMError(f"the model stopped without a complete answer: {response.stop_reason}")
        return response.parsed_output

    def _spend(self, usage: anthropic.types.beta.BetaUsage) -> None:
        cached = usage.cache_read_input_tokens or 0
        written = usage.cache_creation_input_tokens or 0
        spent = Usage(usage.input_tokens + cached + written, cached, usage.output_tokens)
        with self._lock:
            self._usage += spent


class SavedAnswers:
    """An `LLMClient` that keeps each answer of `llm` in `folder` and only asks for new ones.

    An answer is reused while the model, the system prompt, the prompt and the shape of the
    answer are all unchanged. Nothing is ever deleted from `folder`.
    """

    def __init__(self, llm: LLMClient, folder: Path) -> None:
        self._llm = llm
        self._folder = folder

    @property
    def model(self) -> str:
        """The id of the model that answers."""
        return self._llm.model

    @property
    def usage(self) -> Usage:
        """The tokens spent on the answers that were not already saved."""
        return self._llm.usage

    def complete[T: BaseModel](
        self, system: str, prompt: str, output: type[T], tools: Sequence[Tool] = ()
    ) -> T:
        """Return the saved answer to `prompt`, or ask `llm` and save what it answers."""
        schema = json.dumps(output.model_json_schema(), sort_keys=True)
        key = hashlib.sha256("\0".join((self.model, system, prompt, schema)).encode())
        file = self._folder / f"{key.hexdigest()[:32]}.json"
        if file.exists():
            return output.model_validate_json(file.read_text(encoding="utf-8"))
        answer = self._llm.complete(system, prompt, output, tools)
        self._folder.mkdir(parents=True, exist_ok=True)
        # Written under another name first, so a run killed mid-write leaves no half answer.
        unfinished = file.with_suffix(".tmp")
        unfinished.write_text(answer.model_dump_json(), encoding="utf-8")
        unfinished.replace(file)
        return answer


def connect_anthropic(model: str) -> AnthropicClient:
    """Return a client for `model`. The SDK reads the key from `ANTHROPIC_API_KEY`."""
    return AnthropicClient(anthropic.Anthropic(), model)
