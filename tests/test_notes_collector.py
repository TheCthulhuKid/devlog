from datetime import UTC, datetime

import pytest

from devlog.collectors.notes import InboxCollector, InboxError
from devlog.events import Event

WEEK = (datetime(2026, 11, 16, tzinfo=UTC), datetime(2026, 11, 23, tzinfo=UTC))


def collect(tmp_path, text: str) -> list[Event]:
    inbox = tmp_path / "inbox.md"
    inbox.write_text(text)
    return InboxCollector(inbox).collect(*WEEK)


def test_each_inbox_note_becomes_an_event_on_its_date(tmp_path):
    text = (
        "# Inbox\n\n## 2026-11-15\n- last week\n\n"
        "## 2026-11-18\n- Caching was a dead end\n  Invalidation cost more than it saved.\n"
        "- Ask about rate limits\n"
    )

    noon = datetime(2026, 11, 18, 12, tzinfo=UTC)
    link = "inbox.md#2026-11-18"
    assert collect(tmp_path, text) == [
        Event(
            time=noon,
            source="notes",
            repo=None,
            title="Caching was a dead end",
            body="Invalidation cost more than it saved.",
            link=link,
        ),
        Event(
            time=noon, source="notes", repo=None, title="Ask about rate limits", body="", link=link
        ),
    ]


def test_inbox_note_without_a_date_is_reported_not_dropped(tmp_path):
    with pytest.raises(InboxError, match="line 3"):
        collect(tmp_path, "# Inbox\n\n- a thought with no date\n")
