"""Collects the notes the user writes by hand."""

import re
from datetime import date, datetime, time
from pathlib import Path

from devlog.events import Event

_HEADING = re.compile(r"#{1,6}\s+(?P<title>.*?)\s*")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_BULLET = re.compile(r"[-*+]\s+")
_NOTE_TIME = time(12)


class InboxError(ValueError):
    """The inbox file has a note that cannot be dated."""


class InboxCollector:
    """One event per note in the inbox file: a bullet under a `## 2026-11-23` date heading.

    A note has no time of day, so its event is placed at noon in the timezone of the range.
    """

    def __init__(self, inbox: Path) -> None:
        self._inbox = inbox

    def collect(self, start: datetime, end: datetime) -> list[Event]:
        """Return the notes dated in `start <= time < end`. A missing inbox has no notes."""
        if not self._inbox.exists():
            return []
        events = [
            Event(
                time=datetime.combine(day, _NOTE_TIME, start.tzinfo),
                source="notes",
                repo=None,
                title=lines[0],
                body="\n".join(lines[1:]),
                link=f"{self._inbox.name}#{day}",
            )
            for day, lines in _dated_notes(self._inbox.read_text(encoding="utf-8"))
        ]
        return [event for event in events if start <= event.time < end]


def _dated_notes(text: str) -> list[tuple[date, list[str]]]:
    notes: list[tuple[date, list[str]]] = []
    day = None
    in_note = False
    for number, line in enumerate(text.splitlines(), start=1):
        heading = _HEADING.fullmatch(line)
        if heading:
            title = heading["title"]
            day = date.fromisoformat(title) if _DATE.fullmatch(title) else None
            in_note = False
            continue
        bullet = _BULLET.match(line)
        if bullet and day is None:
            raise InboxError(f"line {number}: this note has no date heading above it")
        if bullet or (day and not in_note and line.strip()):
            notes.append((day, [line[bullet.end() :] if bullet else line.strip()]))
            in_note = True
        elif in_note and line.strip():
            notes[-1][1].append(line.strip())
    return notes
