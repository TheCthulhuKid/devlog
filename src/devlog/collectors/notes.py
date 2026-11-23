"""Collects notes: the inbox the user writes by hand, and Markdown files such as plans."""

import re
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime, time
from pathlib import Path

from devlog.events import Event

_HEADING = re.compile(r"#{1,6}\s+(?P<title>.*?)\s*")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_BULLET = re.compile(r"[-*+]\s+")
_NOTE_TIME = time(12)
_MAX_BODY = 4000
_TRUNCATED = "\n[truncated]"


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


class NoteFilesCollector:
    """One event per Markdown file under the given paths, placed at the time it last changed.

    The body is the file's current text, cut at a fixed length. A file inside one of `repos`
    belongs to that repo.
    """

    def __init__(self, paths: Sequence[Path], repos: Sequence[Path]) -> None:
        self._paths = paths
        self._repos = repos

    def collect(self, start: datetime, end: datetime) -> list[Event]:
        """Return an event for each file last changed in `start <= time < end`."""
        files = [file for path in self._paths for file in _markdown_files(path)]
        changes = [(file, datetime.fromtimestamp(file.stat().st_mtime, UTC)) for file in files]
        return [self._event(file, time) for file, time in changes if start <= time < end]

    def _event(self, file: Path, time: datetime) -> Event:
        text = file.read_text(encoding="utf-8")
        repo = next((repo.name for repo in self._repos if file.is_relative_to(repo)), None)
        return Event(
            time=time,
            source="notes",
            repo=repo,
            title=f"{file.name} changed",
            body=text if len(text) <= _MAX_BODY else text[:_MAX_BODY] + _TRUNCATED,
            link=str(file),
        )


def _markdown_files(path: Path) -> Iterator[Path]:
    if not path.exists():
        raise FileNotFoundError(f"notes path {path} does not exist")
    yield from sorted(path.rglob("*.md")) if path.is_dir() else [path]


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
