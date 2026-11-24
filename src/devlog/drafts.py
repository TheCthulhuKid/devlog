"""Drafts a week's entry: its events in, a draft entry and a report of dropped claims out."""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from devlog.collectors.base import Runner
from devlog.entry import assemble_entry, drop_unsupported
from devlog.events import read_events
from devlog.llm import LLMClient, LLMError
from devlog.summarise import ThreadSummary, summarise_thread
from devlog.templates import load
from devlog.threads import Thread, group_events

Progress = Callable[[int, int], None]

# Enough to cut a week's wait several times over without running into the API's rate limit.
_WORKERS = 4


@dataclass(frozen=True)
class DraftResult:
    """Where the draft and its report were written, and what was left out."""

    entry: Path
    report: Path
    dropped: int
    failed: int


def draft_week(
    week: str,
    journal: Path,
    repos: Sequence[Path],
    llm: LLMClient,
    run: Runner,
    progress: Progress = lambda done, total: None,
) -> DraftResult:
    """Write the draft entry for `week` and the report of what was left out of it.

    Threads are summarised several at a time. `progress` is called after each one with how many
    are done and how many there are.
    """
    folder = journal / ".devlog" / week

    events_file = folder / "events.jsonl"
    if not events_file.exists():
        raise FileNotFoundError(f"no events for {week}: run `devlog collect --week {week}` first")

    threads = group_events(read_events(events_file))

    summarised, failures = _summarise_all(threads, llm, repos, run, progress)
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
    threads: Sequence[Thread],
    llm: LLMClient,
    repos: Sequence[Path],
    run: Runner,
    progress: Progress,
) -> tuple[list[tuple[Thread, ThreadSummary]], list[str]]:
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        futures = {
            pool.submit(summarise_thread, thread, llm, repos, run): thread for thread in threads
        }
        for done, future in enumerate(as_completed(futures), start=1):
            error = future.exception()
            # Anything but a failed answer is fatal: don't pay for the threads not yet started.
            if error is not None and not isinstance(error, LLMError):
                pool.shutdown(cancel_futures=True)
                raise error
            progress(done, len(threads))

    summarised, failures = [], []
    for future, thread in futures.items():
        try:
            summarised.append((thread, future.result()))
        except LLMError as error:
            failures.append(f"- {thread.id}: not summarised ({error})")
    return summarised, failures
