"""Work threads: a week's events grouped into pieces of work, without any LLM."""

import re
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


Key = tuple[str, str, str | int]


def group_events(events: Sequence[Event]) -> list[Thread]:
    """Group a week's events into threads by repo, branch, issue references and file overlap.

    Every event belongs to exactly one thread, and thread ids are unique within the week.
    """
    groups: list[tuple[list[Event], set[Key]]] = []
    for event in events:
        keys = _keys(event)
        members = [event]
        merged_keys = set(keys)
        untouched = []
        for group in groups:
            group_members, group_keys = group
            if keys & group_keys:
                members += group_members
                merged_keys |= group_keys
            else:
                untouched.append(group)
        groups = [*untouched, (members, merged_keys)]
    return [
        _thread(number=number, members=members)
        for number, (members, _) in enumerate(groups, start=1)
    ]


def _keys(event: Event) -> set[Key]:
    keys: set[Key] = set()
    if not event.repo:
        return keys
    if event.branch and event.branch not in {"main", "master"}:
        keys.add((event.repo, "branch", event.branch))
    issues = re.findall(r"#(\d+)", f"{event.title}\n{event.body}")
    for issue in issues:
        keys.add((event.repo, "issue", int(issue)))
    for file in event.files:
        keys.add((event.repo, "file", file))
    return keys


def _thread(number: int, members: list[Event]) -> Thread:
    members = sorted(members, key=lambda event: event.time)
    return Thread(id=f"thread-{number}", repo=members[0].repo, events=tuple(members))
