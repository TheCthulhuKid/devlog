"""Assembles the weekly entry: thread summaries placed into the entry template."""

import re
from collections.abc import Iterable, Sequence
from datetime import timedelta
from string import Template

from devlog.summarise import Claim, ClaimKind, ThreadSummary
from devlog.threads import Thread
from devlog.week import week_bounds

_EMPTY = "Nothing this week."
_FIELDS = {
    ClaimKind.DECISION: "decisions",
    ClaimKind.DEAD_END: "dead_ends",
    ClaimKind.LESSON: "lessons",
    ClaimKind.OPEN_QUESTION: "open_questions",
    ClaimKind.NEXT_STEP: "next_steps",
}

# The three link shapes the collectors produce (see collectors/git.py and github.py):
#   https://github.com/o/r/commit/<sha>   or   <repo>@<sha>   -> a commit
#   https://github.com/o/r/pull/15[#issuecomment-1]           -> a PR, issue or a comment on one
#   inbox.md#2026-11-17   or   /path/to/notes/file.md         -> a note
_COMMIT = re.compile(r"(?:/commit/|@)([0-9a-f]{7})[0-9a-f]*$")
_NUMBERED = re.compile(r"/(?:pull|issues)/(\d+)")


def assemble_entry(
    week: str, summarised: Sequence[tuple[Thread, ThreadSummary]], template: str
) -> str:
    """Fill the entry `template` for `week` from each thread and its summary."""
    start, end = week_bounds(week)
    threads = _block(_thread_line(thread, summary) for thread, summary in summarised)
    claims = [claim for _, summary in summarised for claim in summary.claims]
    sections = {
        field: _block(_claim_line(claim) for claim in claims if claim.kind == kind)
        for kind, field in _FIELDS.items()
    }
    return Template(template).substitute(
        sections,
        week=week,
        start=start.date(),
        end=(end - timedelta(days=1)).date(),
        threads=threads,
    )


def drop_unsupported(
    summarised: Sequence[tuple[Thread, ThreadSummary]],
) -> tuple[list[tuple[Thread, ThreadSummary]], list[str]]:
    """Return `summarised` without the claims its own thread does not support, and a report.

    A claim is kept only when it cites evidence and every link is one of its thread's event links.
    The report has one line for each claim dropped, saying why.
    """
    kept, report = [], []
    for thread, summary in summarised:
        links = {event.link for event in thread.events}
        checked = [(claim, _problem(claim, links)) for claim in summary.claims]
        claims = tuple(claim for claim, problem in checked if problem is None)
        kept.append((thread, summary.model_copy(update={"claims": claims})))
        report += [
            f"- {thread.id}: {claim.text} ({problem})" for claim, problem in checked if problem
        ]
    return kept, report


def _problem(claim: Claim, links: set[str]) -> str | None:
    if not claim.evidence:
        return "no evidence"
    unknown = [link for link in claim.evidence if link not in links]
    if unknown:
        return f"not in its thread: {', '.join(unknown)}"
    return None


def _block(lines: Iterable[str]) -> str:
    return "\n".join(lines) or _EMPTY


def _label(link: str) -> str:
    if commit := _COMMIT.search(link):
        return commit[1]
    if numbered := _NUMBERED.search(link):
        return f"#{numbered[1]}"

    return link.rsplit("/", 1)[-1]


def _claim_line(claim: Claim) -> str:
    links = ", ".join(f"[{_label(link)}]({link})" for link in claim.evidence)
    return f"- {claim.text} ({links})"


def _thread_line(thread: Thread, summary: ThreadSummary) -> str:
    return f"- **{thread.repo or 'notes'}:** {summary.what_changed} {summary.why}"
