import json
from datetime import UTC, datetime

from devlog.collectors.github import GitHubCollector
from devlog.events import Event

WEEK = (datetime(2026, 11, 16, tzinfo=UTC), datetime(2026, 11, 23, tzinfo=UTC))
PULL_REQUEST = {
    "id": "PR_1",
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


REVIEW = {
    "occurredAt": "2026-11-18T14:00:00Z",
    "repository": {"name": "hello-world"},
    "pullRequest": {"number": 7, "title": "Cache lookups"},
    "pullRequestReview": {
        "url": "https://github.com/monalisa/hello-world/pull/7#pullrequestreview-1",
        "state": "CHANGES_REQUESTED",
        "body": "Close, but the cache never expires.",
        "comments": {"nodes": [{"path": "cache.py", "body": "Needs a TTL."}]},
    },
}
COMMENT = {
    "createdAt": "2026-11-19T11:00:00Z",
    "updatedAt": "2026-11-19T11:00:00Z",
    "url": "https://github.com/octocat/devlog/pull/12#issuecomment-1",
    "body": "Rebased on main.",
    "repository": {"name": "devlog"},
    "issue": {"number": 12, "title": "Retry on timeout"},
}


def collect(authored=(), reviews=(), comments=()) -> list[Event]:
    last_page = {"hasNextPage": False}
    reviews_page = {"pullRequestReviewContributions": {"pageInfo": last_page, "nodes": reviews}}
    user = {
        "contributionsCollection": reviews_page,
        "issueComments": {"pageInfo": last_page, "nodes": comments},
    }

    branches = [{"id": "PR_1", "headRefName": "retries"}]

    def run(args):
        data = {"user": user, "nodes": branches}
        return json.dumps(authored if args[1] == "search" else {"data": data})

    return GitHubCollector("octocat", run).collect(*WEEK)


def test_opened_pr_becomes_an_event_with_its_description():
    assert collect(authored=[PULL_REQUEST]) == [
        Event(
            time=datetime(2026, 11, 17, 8, 30, tzinfo=UTC),
            source="github",
            repo="devlog",
            title="Opened PR #12: Retry on timeout",
            body="The API drops idle connections.",
            link="https://github.com/octocat/devlog/pull/12",
            branch="retries",
        )
    ]


def test_issue_opened_earlier_and_closed_this_week_is_reported_as_closed():
    issue = PULL_REQUEST | {
        "isPullRequest": False,
        "state": "closed",
        "createdAt": "2026-11-02T10:00:00Z",
        "closedAt": "2026-11-20T16:00:00Z",
    }

    assert [event.title for event in collect(authored=[issue])] == [
        "Closed issue #12: Retry on timeout"
    ]


def test_review_on_someone_elses_pr_becomes_an_event():
    assert collect(reviews=[REVIEW]) == [
        Event(
            time=datetime(2026, 11, 18, 14, tzinfo=UTC),
            source="github",
            repo="hello-world",
            title="Reviewed PR #7: Cache lookups (changes requested)",
            body="Close, but the cache never expires.\n\ncache.py: Needs a TTL.",
            link="https://github.com/monalisa/hello-world/pull/7#pullrequestreview-1",
        )
    ]


def test_comment_on_your_own_pr_is_a_separate_event_with_its_own_link():
    events = collect(authored=[PULL_REQUEST], comments=[COMMENT])

    assert [(event.title, event.link) for event in events] == [
        ("Opened PR #12: Retry on timeout", "https://github.com/octocat/devlog/pull/12"),
        (
            "Commented on #12: Retry on timeout",
            "https://github.com/octocat/devlog/pull/12#issuecomment-1",
        ),
    ]
