import os
from datetime import UTC, date, datetime

import pytest
from gitrepo import ALWAYS, commit

from devlog.collectors.base import run_command
from devlog.collectors.notes import InboxCollector, InboxError, NoteFilesCollector
from devlog.events import Event
from devlog.inbox import write_note
from devlog.threads import group_events

WEEK = (datetime(2026, 11, 16, tzinfo=UTC), datetime(2026, 11, 23, tzinfo=UTC))


def collect(tmp_path, text: str) -> list[Event]:
    inbox = tmp_path / "inbox.md"
    inbox.write_text(text)
    return InboxCollector(inbox, ["devlog"]).collect(*WEEK)


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


def test_a_written_note_is_collected_for_its_week(tmp_path):
    inbox = tmp_path / "inbox.md"
    write_note(inbox, "chose FTS5 over embeddings", date(2026, 11, 18), repo="devlog")

    [event] = InboxCollector(inbox, ["devlog"]).collect(*WEEK)
    assert (event.repo, event.title) == ("devlog", "chose FTS5 over embeddings")


def test_a_note_written_on_a_branch_joins_that_branchs_thread(tmp_path):
    inbox = tmp_path / "inbox.md"
    day, branch = date(2026, 11, 18), "forget-a-failed-pick"
    write_note(inbox, "a check argument would change 20 fakes", day, "devlog", branch)
    commit = Event(
        time=WEEK[0], source="git", repo="devlog", title="fix", body="", link="x", branch=branch
    )

    [note] = InboxCollector(inbox, ["devlog"]).collect(*WEEK)
    [thread] = group_events([commit, note])
    assert note.title == "a check argument would change 20 fakes"
    assert thread.events == (commit, note)


def test_a_bracket_that_is_no_repo_stays_in_the_note(tmp_path):
    [event] = collect(tmp_path, "## 2026-11-18\n- [WIP] retry the upload\n")

    assert (event.repo, event.title) == (None, "[WIP] retry the upload")


def test_a_tracked_note_file_is_still_collected_after_a_later_edit(repo):
    commit(repo, "docs: plan the retries", "PLAN.md", "src/app.py")
    (repo / "PLAN.md").write_text("edited the week after")

    [event] = NoteFilesCollector([repo / "PLAN.md"], [repo], run_command).collect(*ALWAYS)
    assert event.title == "Notes changed: docs: plan the retries"
    assert "+docs: plan the retries" in event.body
    assert "src/app.py" not in event.body


def test_an_untracked_note_file_is_placed_at_the_time_it_last_changed(repo):
    changed = datetime(2026, 11, 19, 15, tzinfo=UTC)
    for name, modified in (("PLAN.md", changed), ("old.md", datetime(2026, 11, 1, tzinfo=UTC))):
        (repo / name).write_text("Step 2: done")
        os.utime(repo / name, (modified.timestamp(), modified.timestamp()))

    assert NoteFilesCollector([repo], [repo], run_command).collect(*WEEK) == [
        Event(
            time=changed,
            source="notes",
            repo=repo.name,
            title="PLAN.md changed",
            body="Step 2: done",
            link=str(repo / "PLAN.md"),
        )
    ]


def test_claude_memory_notes_are_never_collected(tmp_path):
    memory = tmp_path / ".claude" / "projects" / "devlog" / "memory"
    memory.mkdir(parents=True)
    (memory / "about-the-user.md").write_text("personal")
    in_week = datetime(2026, 11, 19, tzinfo=UTC).timestamp()
    os.utime(memory / "about-the-user.md", (in_week, in_week))

    assert NoteFilesCollector([tmp_path], [], run_command).collect(*WEEK) == []
