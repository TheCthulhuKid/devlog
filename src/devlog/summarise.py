"""Summarises one work thread with the LLM: what changed, why, and claims with their evidence."""

from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from devlog.collectors.base import Runner
from devlog.collectors.git import commit_sha, read_diff, read_file
from devlog.events import Event
from devlog.llm import LLMClient, Tool
from devlog.templates import load
from devlog.threads import Thread

_NOT_IN_THREAD = "Refused: that is not the link of a commit in this thread."


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


class BaseRequest(BaseModel):
    commit: str = Field(description="The link of a commit event in this thread, copied exactly.")


class DiffRequest(BaseRequest): ...


class FileRequest(BaseRequest):
    path: str = Field(description="The file's path from the repo root.")


def thread_tools(thread: Thread, repos: Sequence[Path], run: Runner) -> list[Tool]:
    """Return the tools for `thread`: they read only its own commits, in configured repos."""
    paths = {repo.name: repo for repo in repos}
    commits = {
        event.link: (paths[event.repo], commit_sha(event.link))
        for event in thread.events
        if event.source == "git" and event.repo in paths
    }

    def diff(request: DiffRequest) -> str:
        if request.commit not in commits:
            return _NOT_IN_THREAD
        return read_diff(run, *commits[request.commit])

    def file(request: FileRequest) -> str:
        if request.commit not in commits:
            return _NOT_IN_THREAD
        try:
            return read_file(run, *commits[request.commit], request.path)
        except FileNotFoundError:
            return f"There is no file {request.path} in that commit."

    return [
        Tool("read_diff", "The full diff of one commit of this thread.", DiffRequest, diff),
        Tool("read_file", "One file as it was at a commit of this thread.", FileRequest, file),
    ]


def summarise_thread(
    thread: Thread, llm: LLMClient, repos: Sequence[Path], run: Runner
) -> ThreadSummary:
    """Ask the LLM to summarise `thread`, showing it every event and letting it read commits."""
    prompt = "\n\n".join(_render(event) for event in thread.events)
    return llm.complete(
        load("summary.prompt.md"), prompt, ThreadSummary, thread_tools(thread, repos, run)
    )


def _render(event: Event) -> str:
    lines = [
        f"## {event.title}",
        f"time: {event.time.isoformat()}",
        f"source: {event.source}",
        f"link: {event.link}",
    ]
    return "\n".join([*lines, "", event.body] if event.body else lines)
