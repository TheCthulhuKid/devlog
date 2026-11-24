"""Drafts a week's entry: its events in, a draft entry and a report of dropped claims out."""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from devlog.collectors.base import Runner
from devlog.digest import digest_threads
from devlog.entry import assemble_entry, drop_unsupported, list_claims, thread_line
from devlog.events import read_events
from devlog.llm import LLMClient, LLMError, SavedAnswers, Usage
from devlog.selection import select_claims
from devlog.summarise import ThreadSummary, summarise_thread
from devlog.templates import load
from devlog.threads import Thread, group_events

Progress = Callable[[int, int], None]

# Enough to cut a week's wait several times over without running into the API's rate limit.
_WORKERS = 4


@dataclass(frozen=True)
class DraftResult:
    """Where the draft and its reports were written, and what was left out."""

    entry: Path
    report: Path
    unselected: Path
    threads: Path
    kept: int
    left_out: int
    selection_failed: bool
    dropped: int
    failed: int
    undigested: int
    usage: Usage


def draft_week(
    week: str,
    journal: Path,
    repos: Sequence[Path],
    llm: LLMClient,
    run: Runner,
    progress: Progress = lambda done, total: None,
) -> DraftResult:
    """Write the draft entry for `week` and the reports of what was left out of it.

    Threads are summarised several at a time. `progress` is called after each one with how many
    are done and how many there are. Each summary is saved in the week's folder as it is made,
    so a later run only asks the LLM about threads that are new or have changed. The entry holds
    the claims picked for the week, or all of them if picking fails, and one line per repo for
    the week's work; the line of every thread goes to a file beside it.
    """
    folder = journal / ".devlog" / week

    events_file = folder / "events.jsonl"
    if not events_file.exists():
        raise FileNotFoundError(f"no events for {week}: run `devlog collect --week {week}` first")

    threads = group_events(read_events(events_file))
    llm = SavedAnswers(llm, folder / "summaries")

    summarised, failures = _summarise_all(threads, llm, repos, run, progress)
    supported, dropped = drop_unsupported(summarised)
    not_selected = []
    try:
        kept, left_out = select_claims(supported, llm)
    except LLMError as error:
        kept, left_out = supported, []
        not_selected.append(f"- week: claims not selected ({error})")

    work, undigested = digest_threads(supported, llm)

    entry_file = folder / "draft.md"
    entry_file.write_text(assemble_entry(week, kept, load("entry.md"), work), encoding="utf-8")

    threads_file = folder / "threads.md"
    thread_lines = [thread_line(thread, summary) for thread, summary in supported]
    threads_file.write_text("".join(f"{line}\n" for line in thread_lines), encoding="utf-8")

    unselected_file = folder / "unselected.md"
    unselected_file.write_text(list_claims(left_out), encoding="utf-8")

    report_file = folder / "dropped.md"
    lines = [*failures, *not_selected, *undigested, *dropped]
    report_file.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")

    return DraftResult(
        entry=entry_file,
        report=report_file,
        unselected=unselected_file,
        threads=threads_file,
        kept=sum(len(summary.claims) for _, summary in kept),
        left_out=len(left_out),
        selection_failed=bool(not_selected),
        dropped=len(dropped),
        failed=len(failures),
        undigested=len(undigested),
        usage=llm.usage,
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
