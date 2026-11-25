"""Compares a week's draft with its edited entry: the edit rate."""

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from devlog.entry import EMPTY

_HEADING = "## "


@dataclass(frozen=True)
class SectionEdits:
    """What became of one section of a draft in the edited entry, counted in lines."""

    section: str
    drafted: int
    kept: int
    added: int

    @property
    def removed(self) -> int:
        """The draft lines that are not in the edited entry."""
        return self.drafted - self.kept

    @property
    def edit_rate(self) -> float | None:
        """The share of draft lines not kept, or None when the draft had no lines here."""
        if not self.drafted:
            return None
        return self.removed / self.drafted


@dataclass(frozen=True)
class WeekEdits:
    """A week's draft compared with its edited entry, section by section."""

    week: str
    sections: list[SectionEdits]


def compare_entries(draft: str, final: str) -> list[SectionEdits]:
    """Return, for each section of `draft` or `final`, how many draft lines were kept and added."""
    before, after = _sections(draft), _sections(final)
    edits = []

    for section in before | after:
        drafted = Counter(before.get(section, []))
        edited = Counter(after.get(section, []))
        kept = (drafted & edited).total()
        edits.append(SectionEdits(section, drafted.total(), kept, edited.total() - kept))

    return edits


def total(edits: Sequence[SectionEdits]) -> SectionEdits:
    """Return the sum of `edits` as one row: the whole entry's lines drafted, kept and added."""
    return SectionEdits(
        section="All sections",
        drafted=sum(section.drafted for section in edits),
        kept=sum(section.kept for section in edits),
        added=sum(section.added for section in edits),
    )


def journal_stats(journal: Path) -> list[WeekEdits]:
    """Compare each week's draft in `journal` with its entry, oldest week first.

    A week whose entry does not exist is left out. The result is also written to
    `.devlog/metrics.jsonl`, one line per week, replacing what was there.
    """
    weeks = []
    for draft_file in sorted((journal / ".devlog").glob("*/draft.md")):
        week = draft_file.parent.name
        entry_file = journal / "entries" / f"{week}.md"
        if not entry_file.exists():
            continue
        draft = draft_file.read_text(encoding="utf-8")
        final = entry_file.read_text(encoding="utf-8")
        weeks.append(WeekEdits(week, compare_entries(draft, final)))

    rows = [_row(week) for week in weeks]
    metrics_file = journal / ".devlog" / "metrics.jsonl"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    metrics_file.write_text("".join(f"{json.dumps(row)}\n" for row in rows), encoding="utf-8")
    return weeks


def _row(week: WeekEdits) -> dict:
    numbers = _numbers(total(week.sections))
    del numbers["section"]
    return {"week": week.week, **numbers, "sections": [_numbers(s) for s in week.sections]}


def _numbers(edits: SectionEdits) -> dict:
    return {**asdict(edits), "removed": edits.removed, "edit_rate": edits.edit_rate}


def _sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(_HEADING):
            current = sections.setdefault(line.removeprefix(_HEADING), [])
        elif line and line != EMPTY and current is not None:
            current.append(line)
    return sections
