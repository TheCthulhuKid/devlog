"""The Event contract every collector produces, and its JSONL file format."""

from collections.abc import Iterable
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Event(BaseModel):
    """One thing that happened during the week, in the same shape whatever its source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    time: AwareDatetime
    source: str = Field(min_length=1)
    repo: str | None
    title: str = Field(min_length=1)
    body: str
    link: str = Field(min_length=1)


def write_events(events: Iterable[Event], path: Path) -> None:
    """Write events to `path`, one JSON object per line."""
    path.write_text("".join(f"{event.model_dump_json()}\n" for event in events), encoding="utf-8")


def read_events(path: Path) -> list[Event]:
    """Read events written by `write_events`."""
    with path.open(encoding="utf-8") as lines:
        return [Event.model_validate_json(line) for line in lines]
