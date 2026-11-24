"""The LLM the journal is written with, behind a protocol so nothing else depends on a provider."""

import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass
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


class LLMClient(Protocol):
    """Answers one prompt with a validated instance of the requested model."""

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
        self._model = model

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
            response = self._client.beta.messages.tool_runner(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                betas=[_FALLBACK_BETA],
                fallbacks="default",
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=output,
                tools=[runnable(tool) for tool in tools],
                max_iterations=_MAX_TOOL_CALLS + 2,
                thread=False,
            ).until_done()
        except ValidationError as error:
            raise LLMError("the model's answer was cut short or did not fit the schema") from error

        if failures:
            raise LLMError("a tool failed while the model was answering") from failures[0]

        if response.stop_reason != "end_turn" or response.parsed_output is None:
            raise LLMError(f"the model stopped without a complete answer: {response.stop_reason}")
        return response.parsed_output
