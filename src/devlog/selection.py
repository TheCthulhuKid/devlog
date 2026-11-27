"""Picks the week's claims: of everything the threads claimed, the few worth rereading."""

import itertools
from collections.abc import Sequence
from string import Template

from pydantic import BaseModel, ConfigDict

from devlog.entry import thread_line
from devlog.llm import LLMClient, LLMError
from devlog.summarise import Claim, ThreadSummary
from devlog.templates import load
from devlog.threads import Thread

TARGET = 20


class Selection(BaseModel):
    """The numbers of the claims to keep, as they were listed for the LLM."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    keep: tuple[int, ...]


class RejectedPick(LLMError):
    """The model's pick cannot be used. `system` and `prompt` are the request it answered."""

    def __init__(self, message: str, system: str, prompt: str) -> None:
        super().__init__(message)
        self.system = system
        self.prompt = prompt


def select_claims(
    summarised: Sequence[tuple[Thread, ThreadSummary]], llm: LLMClient
) -> tuple[list[tuple[Thread, ThreadSummary]], list[Claim]]:
    """Return `summarised` with only the claims the LLM picks for the week, and those left out.

    Claims are picked by number, so their text and evidence stay as they were. A week with no
    more than `TARGET` claims is returned whole, without asking the LLM.
    Raises `RejectedPick` when the LLM picks nothing or a number that was not listed.
    """
    numbers = itertools.count(1)
    numbered = [
        (thread, summary, [(next(numbers), claim) for claim in summary.claims])
        for thread, summary in summarised
    ]
    total = next(numbers) - 1
    if total <= TARGET:
        return list(summarised), []

    system = Template(load("selection.prompt.md")).substitute(target=TARGET)
    listing = "\n\n".join(_listed(*item) for item in numbered)
    keep = set(llm.complete(system, listing, Selection).keep)
    if not keep:
        raise RejectedPick("the model picked no claims", system, listing)
    if unlisted := sorted(keep - set(range(1, total + 1))):
        message = f"the model picked claims that were not listed: {unlisted}"
        raise RejectedPick(message, system, listing)

    kept = [
        (
            thread,
            summary.model_copy(
                update={"claims": tuple(claim for number, claim in claims if number in keep)}
            ),
        )
        for thread, summary, claims in numbered
    ]
    left_out = [
        claim for _, _, claims in numbered for number, claim in claims if number not in keep
    ]
    return kept, left_out


def _listed(thread: Thread, summary: ThreadSummary, claims: Sequence[tuple[int, Claim]]) -> str:
    lines = [f"{number}. [{claim.kind}] {claim.text}" for number, claim in claims]
    return "\n".join([thread_line(thread, summary), *lines])
