from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from devlog.events import Event, read_events, write_events

COMMIT = {
    "source": "git",
    "repo": "devlog",
    "title": "feat: add config validation",
    "body": "2 files changed\nsrc/devlog/config.py",
    "link": "https://github.com/octocat/devlog/commit/abc123",
}


def test_events_survive_a_jsonl_round_trip(tmp_path):
    paris = timezone(timedelta(hours=1))
    events = [
        Event(time=datetime(2026, 11, 16, 9, 30, tzinfo=paris), **COMMIT),
        Event(
            time=datetime(2026, 11, 17, tzinfo=UTC), **COMMIT | {"repo": None, "body": "é\n\u2028"}
        ),
    ]

    write_events(events, tmp_path / "events.jsonl")

    assert read_events(tmp_path / "events.jsonl") == events


def test_event_without_timezone_is_rejected():
    with pytest.raises(ValidationError, match="timezone"):
        Event(time=datetime(2026, 11, 16, 9, 30), **COMMIT)
