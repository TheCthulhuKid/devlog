"""Assembles the weekly entry: thread summaries placed into the entry template."""

import re
from collections.abc import Iterable, Sequence
from datetime import timedelta
from string import Template

from devlog.summarise import Claim, ClaimKind, ThreadSummary
from devlog.threads import Thread
from devlog.week import week_bounds

EMPTY = "Nothing this week."
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
    week: str,
    summarised: Sequence[tuple[Thread, ThreadSummary]],
    template: str,
    work: Sequence[str] | None = None,
) -> str:
    """Fill the entry `template` for `week` from each thread and its summary.

    `work` is the lines saying what the week's work was; without it, each thread gets a line.
    """
    start, end = week_bounds(week)
    if work is None:
        work = [thread_line(thread, summary) for thread, summary in summarised]
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
        threads=_block(work),
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


def list_claims(claims: Sequence[Claim]) -> str:
    """Return `claims` as entry lines under a heading for each kind, to paste into an entry."""
    blocks = []
    for kind in ClaimKind:
        lines = [_claim_line(claim) for claim in claims if claim.kind == kind]
        if lines:
            blocks.append("".join(f"{line}\n" for line in [f"## {kind}", *lines]))
    return "\n".join(blocks)


def _problem(claim: Claim, links: set[str]) -> str | None:
    if not claim.evidence:
        return "no evidence"
    unknown = [link for link in claim.evidence if link not in links]
    if unknown:
        return f"not in its thread: {', '.join(unknown)}"
    return None


def _block(lines: Iterable[str]) -> str:
    return "\n".join(lines) or EMPTY


def _label(link: str) -> str:
    if commit := _COMMIT.search(link):
        return commit[1]
    if numbered := _NUMBERED.search(link):
        return f"#{numbered[1]}"

    return link.rsplit("/", 1)[-1]


def _claim_line(claim: Claim) -> str:
    links = ", ".join(_evidence(link) for link in claim.evidence)
    return f"- {claim.text} ({links})"


def thread_line(thread: Thread, summary: ThreadSummary) -> str:
    """Return the entry's line for `thread`: its repo, what changed and why."""
    return work_line(thread.repo, f"{summary.what_changed} {summary.why}")


def work_line(repo: str | None, text: str) -> str:
    """Return the entry's line saying `text` about work in `repo`."""
    return f"- **{repo or 'notes'}:** {text}"


def _evidence(link: str) -> str:
    label = _label(link)
    # A local commit or a note has no page the entry could link to.
    if not link.startswith(("https://", "http://")):
        return f"`{label}`"
    return f"[{label}]({link})"
