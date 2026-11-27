"""Writes a note into the inbox file, in the format the user types by hand."""

import re
from datetime import date
from pathlib import Path

_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$", re.MULTILINE)


def write_note(inbox: Path, note: str, day: date, repo: str | None = None) -> None:
    """Append `note` to the inbox under the heading of the `day`, adding the heading if needed."""
    existing = inbox.read_text(encoding="utf-8") if inbox.exists() else ""
    with inbox.open("a", encoding="utf-8") as file:
        file.write(_addition(existing, note, day, repo))


def _addition(existing: str, note: str, day: date, repo: str | None) -> str:
    bullet = f"- [{repo}] {note}\n" if repo else f"- {note}\n"
    day_iso = day.isoformat()
    if _last_heading(existing) == day_iso:
        return _newlines(existing, 1) + bullet
    return _newlines(existing, 2) + f"## {day_iso}\n{bullet}"


def _last_heading(text: str) -> str | None:
    headings = _HEADING.findall(text)
    return headings[-1] if headings else None


def _newlines(existing: str, wanted: int) -> str:
    """Return the newlines still missing for a non-empty `existing` to end with `wanted`"""
    if not existing:
        return ""
    present = len(existing) - len(existing.rstrip("\n"))
    return "\n" * max(wanted - present, 0)
