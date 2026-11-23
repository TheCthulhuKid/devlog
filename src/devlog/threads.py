"""Work threads: a week's events grouped into pieces of work, without any LLM."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from devlog.events import Event


class Thread(BaseModel):
    """The events of one piece of work, with what ties them together."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    repo: str | None
    events: tuple[Event, ...] = Field(min_length=1)
    branches: tuple[str, ...] = ()
    issue_refs: tuple[int, ...] = ()
    files: tuple[str, ...] = ()


def group_events(events: Sequence[Event]) -> list[Thread]:
    """Group a week's events into threads by repo, branch, issue references and file overlap.

    Every event belongs to exactly one thread, and thread ids are unique within the week.
    """
    raise NotImplementedError
