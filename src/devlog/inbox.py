"""Writes a note into the inbox file, in the format the user types by hand."""

import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path

_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$", re.MULTILINE)


def note_repo(repos: Sequence[Path], folder: Path, given: str | None = None) -> Path | None:
    """Return the repo a note is about: the one named `given`, or the one that holds `folder`."""
    if given is None:
        return next((repo for repo in repos if folder.is_relative_to(repo)), None)
    named = {repo.name: repo for repo in repos}
    if given not in named:
        raise ValueError(f"{given} is not one of your repos: {', '.join(named)}")
    return named[given]


def write_note(
    inbox: Path, note: str, day: date, repo: str | None = None, branch: str | None = None
) -> None:
    """Append `note` to the inbox under the heading of the `day`, adding the heading if needed.

    Raises `ValueError` if a note is empty or a branch without a repo is given.
    """
    existing = inbox.read_text(encoding="utf-8") if inbox.exists() else ""
    addition = _addition(existing, _bullet(note, _prefix(repo, branch)), day)
    with inbox.open("a", encoding="utf-8") as file:
        file.write(addition)


def _addition(existing: str, bullet: str, day: date) -> str:
    day_iso = day.isoformat()
    if _last_heading(existing) == day_iso:
        return _newlines(existing, 1) + bullet
    return _newlines(existing, 2) + f"## {day_iso}\n{bullet}"


def _last_heading(text: str) -> str | None:
    headings = _HEADING.findall(text)
    return headings[-1] if headings else None


def _newlines(existing: str, wanted: int) -> str:
    """Return the newlines still missing for a non-empty `existing` to end with `wanted`."""
    if not existing:
        return ""
    present = len(existing) - len(existing.rstrip("\n"))
    return "\n" * max(wanted - present, 0)


def _prefix(repo: str | None, branch: str | None) -> str:
    if branch and not repo:
        raise ValueError(f"the branch {branch} needs a repo")
    if not repo:
        return ""
    return f"[{repo} {branch}] " if branch else f"[{repo}] "


def _bullet(note: str, prefix: str) -> str:
    lines = [line.strip() for line in note.splitlines() if line.strip()]
    if not lines:
        raise ValueError("the note is empty")
    return f"- {prefix}" + "\n  ".join(lines) + "\n"
