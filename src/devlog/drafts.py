"""Drafts a week's entry: its events in, a draft entry and a report of dropped claims out."""

from collections import Counter
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
from devlog.summarise import Claim, ClaimKind, ThreadSummary, summarise_thread
from devlog.templates import load
from devlog.threads import Thread, group_events

Progress = Callable[[int, int], None]

_WORKERS = 4


class EntryEditedError(Exception):
    """The week's entry was edited after it was drafted, so a new draft would lose the edits."""


class UnknownEvidenceError(Exception):
    """No thread of the week holds the evidence asked for."""


@dataclass(frozen=True)
class DraftResult:
    """Where the draft, the entry to edit and the reports were written, and what was left out."""

    draft: Path
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
    overwrite: bool = False,
) -> DraftResult:
    """Write the draft entry for `week`, a copy of it to edit, and the reports of what was left out.

    The copy is `entries/<week>.md` in the journal. If it has been edited since the last draft,
    `EntryEditedError` is raised before the LLM is asked anything, unless `overwrite` is set.

    Threads are summarised several at a time. `progress` is called after each one with how many
    are done and how many there are. Each summary is saved in the week's folder as it is made,
    so a later run only asks the LLM about threads that are new or have changed. The entry holds
    the claims picked for the week, or all of them if picking fails, and one line per repo for
    the week's work; the line of every thread goes to a file beside it.
    """
    folder = journal / ".devlog" / week

    threads = _week_threads(folder, week)

    draft_file = folder / "draft.md"
    entry_file = journal / "entries" / f"{week}.md"
    if not overwrite and _edited(entry_file, draft_file):
        raise EntryEditedError(
            f"{entry_file} was edited after it was drafted: pass `--overwrite` to replace it"
        )

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

    text = assemble_entry(week, kept, load("entry.md"), work)
    draft_file.write_text(text, encoding="utf-8")
    entry_file.parent.mkdir(exist_ok=True)
    entry_file.write_text(text, encoding="utf-8")

    threads_file = folder / "threads.md"
    thread_lines = [thread_line(thread, summary) for thread, summary in supported]
    threads_file.write_text("".join(f"{line}\n" for line in thread_lines), encoding="utf-8")

    unselected_file = folder / "unselected.md"
    unselected_file.write_text(list_claims(left_out), encoding="utf-8")

    report_file = folder / "dropped.md"
    lines = [*failures, *not_selected, *undigested, *dropped]
    report_file.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")

    return DraftResult(
        draft=draft_file,
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


def sample_week(
    week: str,
    journal: Path,
    repos: Sequence[Path],
    llm: LLMClient,
    run: Runner,
    evidence: Sequence[str],
    progress: Progress = lambda done, total: None,
    again: bool = False,
) -> str:
    """Return what the summary prompt makes of the threads of `week` that hold `evidence`.

    A thread is chosen when a link of one of its events contains one of the `evidence` texts,
    such as a commit hash copied from a claim. Each chosen thread is shown with its line and its
    supported claims; threads that failed and claims that were dropped are listed at the end.
    Only saved answers are written, so the week's draft and entry stay as they are.

    With `again`, every chosen thread is asked afresh and its answer is not saved, so the same
    prompt can be run several times to see how much its answers vary.

    Raises `UnknownEvidenceError` for evidence that no thread holds.
    """
    folder = journal / ".devlog" / week
    threads = _week_threads(folder, week)

    unknown = [text for text in evidence if not any(_holds(thread, text) for thread in threads)]
    if unknown:
        raise UnknownEvidenceError(f"no thread of {week} holds: {', '.join(unknown)}")

    chosen = [thread for thread in threads if any(_holds(thread, text) for text in evidence)]

    if not again:
        llm = SavedAnswers(llm, folder / "summaries")
    summarised, failures = _summarise_all(chosen, llm, repos, run, progress)
    supported, dropped = drop_unsupported(summarised)
    blocks = [
        f"# {thread.id}\n{thread_line(thread, summary)}\n\n{list_claims(summary.claims)}".rstrip()
        for thread, summary in supported
    ]
    return "\n\n".join([*blocks, *failures, *dropped])


def pick_week(
    week: str,
    journal: Path,
    repos: Sequence[Path],
    llm: LLMClient,
    run: Runner,
    progress: Progress = lambda done, total: None,
    again: bool = False,
) -> str:
    """Return the claims the pick keeps for `week`, and how many of each kind it kept.

    The threads are summarised as for a draft, so their saved summaries are reused. Nothing
    else is written: the week's draft, entry and reports stay as they are.

    With `again`, the pick is asked afresh and its answer is not saved, so the same prompt
    can be run several times to see how much its picks vary.
    """
    folder = journal / ".devlog" / week
    threads = _week_threads(folder, week)

    saved = SavedAnswers(llm, folder / "summaries")
    summarised, failures = _summarise_all(threads, saved, repos, run, progress)
    supported, _ = drop_unsupported(summarised)
    kept, left_out = select_claims(supported, llm if again else saved)

    claims = [claim for _, summary in kept for claim in summary.claims]
    return "\n".join([list_claims(claims), *failures, _kept_counts(claims, left_out)])


def _holds(thread: Thread, text: str) -> bool:
    return any(text in event.link for event in thread.events)


def _kept_counts(kept: Sequence[Claim], left_out: Sequence[Claim]) -> str:
    kept_kinds = Counter(claim.kind for claim in kept)
    all_kinds = kept_kinds + Counter(claim.kind for claim in left_out)
    kinds = ", ".join(
        f"{kind} {kept_kinds[kind]} of {all_kinds[kind]}" for kind in ClaimKind if all_kinds[kind]
    )
    return f"kept {len(kept)} of {len(kept) + len(left_out)}: {kinds}"


def _edited(entry_file: Path, draft_file: Path) -> bool:
    if not entry_file.exists():
        return False
    # If no draft exists, it is mine
    if not draft_file.exists():
        return True
    return entry_file.read_text(encoding="utf-8") != draft_file.read_text(encoding="utf-8")


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
        try:
            for done, future in enumerate(as_completed(futures), start=1):
                error = future.exception()
                # Anything but a failed answer is fatal: don't pay for the threads not yet started.
                if error is not None and not isinstance(error, LLMError):
                    raise error
                progress(done, len(threads))
        except BaseException:
            pool.shutdown(cancel_futures=True)
            raise

    summarised, failures = [], []
    for future, thread in futures.items():
        try:
            summarised.append((thread, future.result()))
        except LLMError as error:
            failures.append(f"- {thread.id}: not summarised ({error})")
    return summarised, failures


def _week_threads(folder: Path, week: str) -> list[Thread]:
    events_file = folder / "events.jsonl"
    if not events_file.exists():
        raise FileNotFoundError(f"no events for {week}: run `devlog collect --week {week}` first")
    return group_events(read_events(events_file))
