"""Summarises one work thread with the LLM: what changed, why, and claims with their evidence."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from devlog.events import Event
from devlog.llm import LLMClient
from devlog.threads import Thread

_SYSTEM = """\
You help a developer write their weekly engineering journal. You are given the events of one \
thread of work: commits, pull requests, comments and notes.

Say what changed and why, then list the claims worth recording: decisions (with the alternatives \
that were rejected, when the events show them), dead ends, lessons, open questions and next steps.

Every claim must list in `evidence` the links of the events that support it, copied exactly as \
given. Leave out anything the events do not support; a short, well-supported summary is better \
than a complete-looking one."""


class ClaimKind(StrEnum):
    DECISION = "decision"
    DEAD_END = "dead_end"
    LESSON = "lesson"
    OPEN_QUESTION = "open_question"
    NEXT_STEP = "next_step"


class Claim(BaseModel):
    """One statement for the journal, with the links of the events that support it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    kind: ClaimKind
    evidence: tuple[str, ...]


class ThreadSummary(BaseModel):
    """What the LLM made of one thread."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    what_changed: str
    why: str
    claims: tuple[Claim, ...]


def summarise_thread(thread: Thread, llm: LLMClient) -> ThreadSummary:
    """Ask the LLM to summarise `thread`, showing it every event."""
    prompt = "\n\n".join(_render(event) for event in thread.events)
    return llm.complete(_SYSTEM, prompt, ThreadSummary)


def _render(event: Event) -> str:
    lines = [
        f"## {event.title}",
        f"time: {event.time.isoformat()}",
        f"source: {event.source}",
        f"link: {event.link}",
    ]
    return "\n".join([*lines, "", event.body] if event.body else lines)
