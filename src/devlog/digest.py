"""Digests the week's threads: one line per repo for the entry, not one per thread."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from devlog.entry import thread_line, work_line
from devlog.llm import LLMClient, LLMError
from devlog.summarise import ThreadSummary
from devlog.templates import load
from devlog.threads import Thread


class RepoDigest(BaseModel):
    """What a week's threads in one repo amounted to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str


def digest_threads(
    summarised: Sequence[tuple[Thread, ThreadSummary]], llm: LLMClient
) -> tuple[list[str], list[str]]:
    """Return the entry's lines for the week's work, one per repo, and a report of failures.

    A repo with one thread keeps that thread's line. A repo the LLM fails on keeps all its
    thread lines, and the report has a line saying why.
    """
    by_repo: dict[str | None, list[str]] = {}
    for thread, summary in summarised:
        by_repo.setdefault(thread.repo, []).append(thread_line(thread, summary))

    lines, report = [], []
    for repo, threads in by_repo.items():
        try:
            lines += _digested(repo, threads, llm)
        except LLMError as error:
            lines += threads
            report.append(f"- {repo or 'notes'}: not digested ({error})")
    return lines, report


def _digested(repo: str | None, threads: list[str], llm: LLMClient) -> list[str]:
    if len(threads) == 1:
        return threads
    digest = llm.complete(load("digest.prompt.md"), "\n".join(threads), RepoDigest)
    # The line is one item of a list, which a line break would cut in two.
    return [work_line(repo, " ".join(digest.text.split()))]
