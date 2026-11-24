"""Drafts a week's entry: its events in, a draft entry and a report of dropped claims out."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from devlog.collectors.base import Runner
from devlog.entry import assemble_entry, drop_unsupported
from devlog.events import read_events
from devlog.llm import LLMClient, LLMError
from devlog.summarise import ThreadSummary, summarise_thread
from devlog.templates import load
from devlog.threads import Thread, group_events


@dataclass(frozen=True)
class DraftResult:
    """Where the draft and its report were written, and what was left out."""

    entry: Path
    report: Path
    dropped: int
    failed: int


def draft_week(
    week: str, journal: Path, repos: Sequence[Path], llm: LLMClient, run: Runner
) -> DraftResult:
    """Write the draft entry for `week` and the report of what was left out of it."""
    folder = journal / ".devlog" / week

    events_file = folder / "events.jsonl"
    if not events_file.exists():
        raise FileNotFoundError(f"no events for {week}: run `devlog collect --week {week}` first")

    threads = group_events(read_events(events_file))

    summarised, failures = _summarise_all(threads, llm, repos, run)
    kept, dropped = drop_unsupported(summarised)

    entry_file = folder / "draft.md"
    entry_file.write_text(assemble_entry(week, kept, load("entry.md")), encoding="utf-8")

    report_file = folder / "dropped.md"
    lines = [*failures, *dropped]
    report_file.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")

    return DraftResult(
        entry=entry_file, report=report_file, dropped=len(dropped), failed=len(failures)
    )


def _summarise_all(
    threads: Sequence[Thread], llm: LLMClient, repos: Sequence[Path], run: Runner
) -> tuple[list[tuple[Thread, ThreadSummary]], list[str]]:
    summarised, failures = [], []
    for thread in threads:
        try:
            summarised.append((thread, summarise_thread(thread, llm, repos, run)))
        except LLMError as error:
            failures.append(f"- {thread.id}: not summarised ({error})")
    return summarised, failures
