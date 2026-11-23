from datetime import UTC, datetime
from pathlib import Path

from devlog.collectors.git import GitCollector
from devlog.events import Event

WEEK = (datetime(2026, 11, 16, tzinfo=UTC), datetime(2026, 11, 23, tzinfo=UTC))


def collect(log: str) -> list[Event]:
    outputs = {
        "config": "octocat@example.com\n",
        "ls-remote": "git@github.com:octocat/devlog.git\n",
        "log": log,
    }
    collector = GitCollector([Path("/work/devlog")], lambda args: outputs[args[5]])
    return collector.collect(*WEEK)


def test_commit_becomes_an_event_with_stats_and_files():
    log = (
        "\x1eabc123\x1f2026-11-17T09:30:00+01:00\x1ffix: retry on timeout\x1f"
        "The API drops idle connections.\n\x1f\n\n"
        "12\t3\tsrc/client.py\n4\t0\ttests/test_client.py\n"
    )

    assert collect(log) == [
        Event(
            time=datetime.fromisoformat("2026-11-17T09:30:00+01:00"),
            source="git",
            repo="devlog",
            title="fix: retry on timeout",
            body=(
                "The API drops idle connections.\n\n"
                "Files changed: 2\nsrc/client.py (+12 -3)\ntests/test_client.py (+4 -0)"
            ),
            link="https://github.com/octocat/devlog/commit/abc123",
        )
    ]


def test_commits_outside_the_range_are_left_out():
    log = (
        "\x1eaaa\x1f2026-11-23T00:00:00+00:00\x1fnext week\x1f\x1f\n\n1\t0\ta.py\n"
        "\x1ebbb\x1f2026-11-22T23:59:00+00:00\x1fthis week\x1f\x1f\n\n1\t0\ta.py\n"
        "\x1eccc\x1f2026-11-15T23:59:00+00:00\x1frebased from last week\x1f\x1f\n\n1\t0\ta.py\n"
    )

    assert [event.title for event in collect(log)] == ["this week"]
