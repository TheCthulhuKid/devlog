import json
from datetime import UTC, datetime

from devlog.collectors.github import GitHubCollector
from devlog.events import Event

WEEK = (datetime(2026, 11, 16, tzinfo=UTC), datetime(2026, 11, 23, tzinfo=UTC))
PULL_REQUEST = {
    "number": 12,
    "title": "Retry on timeout",
    "body": "The API drops idle connections.",
    "url": "https://github.com/octocat/devlog/pull/12",
    "repository": {"name": "devlog", "nameWithOwner": "octocat/devlog"},
    "isPullRequest": True,
    "state": "open",
    "createdAt": "2026-11-17T08:30:00Z",
    "closedAt": "0001-01-01T00:00:00Z",
}


def collect(*items: dict) -> list[Event]:
    return GitHubCollector("octocat", lambda args: json.dumps(items)).collect(*WEEK)


def test_opened_pr_becomes_an_event_with_its_description():
    assert collect(PULL_REQUEST) == [
        Event(
            time=datetime(2026, 11, 17, 8, 30, tzinfo=UTC),
            source="github",
            repo="devlog",
            title="Opened PR #12: Retry on timeout",
            body="The API drops idle connections.",
            link="https://github.com/octocat/devlog/pull/12",
        )
    ]


def test_issue_opened_earlier_and_closed_this_week_is_reported_as_closed():
    issue = PULL_REQUEST | {
        "isPullRequest": False,
        "state": "closed",
        "createdAt": "2026-11-02T10:00:00Z",
        "closedAt": "2026-11-20T16:00:00Z",
    }

    assert [event.title for event in collect(issue)] == ["Closed issue #12: Retry on timeout"]
