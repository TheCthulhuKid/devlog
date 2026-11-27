"""Collects the user's GitHub activity through the `gh` command."""

import json
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from itertools import batched
from typing import Any

from devlog.collectors.base import Runner
from devlog.events import Event

_SEARCH_FIELDS = "id,number,title,body,url,repository,isPullRequest,state,createdAt,closedAt"
_SEARCH_LIMIT = 1000
_NODES_PER_QUERY = 100
_BRANCHES_QUERY = """
query($ids: [ID!]!) {
  nodes(ids: $ids) { ... on PullRequest { id headRefName } }
}
"""
_REVIEWS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      pullRequestReviewContributions(first: 100) {
        pageInfo { hasNextPage }
        nodes {
          occurredAt
          repository { name }
          pullRequest { number title }
          pullRequestReview { url state body comments(first: 50) { nodes { path body } } }
        }
      }
    }
  }
}
"""
_COMMENTS_QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    issueComments(first: 100, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { createdAt updatedAt url body repository { name } issue { number title } }
    }
  }
}
"""


class GitHubCollector:
    """Events for the pull requests and issues the user opened, closed, reviewed or commented on.

    An event for one of the user's own pull requests carries the branch it was opened from.
    """

    def __init__(self, user: str, run: Runner) -> None:
        self._user = user
        self._run = run

    def collect(self, start: datetime, end: datetime) -> list[Event]:
        """Return the user's GitHub events with `start <= time < end`."""
        events = [*self._authored(start, end), *self._reviews(start, end), *self._comments(start)]
        return [event for event in events if start <= event.time < end]

    def _authored(self, start: datetime, end: datetime) -> Iterator[Event]:
        output = self._run(
            [
                "gh",
                "search",
                "issues",
                "--include-prs",
                f"--author={self._user}",
                f"--updated=>={_utc(start)}",
                f"--limit={_SEARCH_LIMIT}",
                f"--json={_SEARCH_FIELDS}",
            ]
        )
        items = json.loads(output)
        if len(items) >= _SEARCH_LIMIT:
            raise _too_many("pull requests and issues")
        moments = [
            (item, action, time)
            for item in items
            for action, time in _moments(item)
            if start <= time < end
        ]
        branches = self._branches({item["id"] for item, _, _ in moments if item["isPullRequest"]})
        for item, action, time in moments:
            yield _authored_event(item, action, time, branches.get(item["id"]))

    def _branches(self, pull_request_ids: set[str]) -> dict[str, str]:
        branches: dict[str, str] = {}
        for ids in batched(sorted(pull_request_ids), _NODES_PER_QUERY):
            nodes = self._graphql(_BRANCHES_QUERY, [f"ids[]={node_id}" for node_id in ids])["nodes"]
            branches.update((node["id"], node["headRefName"]) for node in nodes)
        return branches

    def _reviews(self, start: datetime, end: datetime) -> Iterator[Event]:
        user = self._query(_REVIEWS_QUERY, {"from": _utc(start), "to": _utc(end)})
        page = user["contributionsCollection"]["pullRequestReviewContributions"]
        if page["pageInfo"]["hasNextPage"]:
            raise _too_many("reviews")
        yield from map(_review_event, page["nodes"])

    def _comments(self, start: datetime) -> Iterator[Event]:
        variables: dict[str, str] = {}
        while True:
            page = self._query(_COMMENTS_QUERY, variables)["issueComments"]
            yield from map(_comment_event, page["nodes"])
            reached_start = any(_time(node["updatedAt"]) < start for node in page["nodes"])
            if reached_start or not page["pageInfo"]["hasNextPage"]:
                return
            variables = {"after": page["pageInfo"]["endCursor"]}

    def _query(self, query: str, variables: dict[str, str]) -> dict[str, Any]:
        fields = {"login": self._user, **variables}
        arguments = [f"{name}={value}" for name, value in fields.items()]
        user: dict[str, Any] = self._graphql(query, arguments)["user"]
        return user

    def _graphql(self, query: str, fields: Sequence[str]) -> dict[str, Any]:
        arguments = [f"--raw-field={field}" for field in (f"query={query}", *fields)]
        data: dict[str, Any] = json.loads(self._run(["gh", "api", "graphql", *arguments]))["data"]
        return data


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _time(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp)


def _too_many(what: str) -> RuntimeError:
    return RuntimeError(f"GitHub has more {what} than one request returns, so some would be missed")


def _moments(item: dict[str, Any]) -> Iterator[tuple[str, datetime]]:
    yield "Opened", _time(item["createdAt"])
    if item["state"] != "open":
        yield item["state"].capitalize(), _time(item["closedAt"])


def _authored_event(item: dict[str, Any], action: str, time: datetime, branch: str | None) -> Event:
    kind = "PR" if item["isPullRequest"] else "issue"
    return Event(
        time=time,
        source="github",
        repo=item["repository"]["name"],
        title=f"{action} {kind} #{item['number']}: {item['title']}",
        body=item["body"],
        link=item["url"],
        branch=branch,
    )


def _review_event(node: dict[str, Any]) -> Event:
    review, pull_request = node["pullRequestReview"], node["pullRequest"]
    verdict = review["state"].lower().replace("_", " ")
    inline = [f"{comment['path']}: {comment['body']}" for comment in review["comments"]["nodes"]]
    return Event(
        time=_time(node["occurredAt"]),
        source="github",
        repo=node["repository"]["name"],
        title=f"Reviewed PR #{pull_request['number']}: {pull_request['title']} ({verdict})",
        body="\n\n".join(part for part in (review["body"], *inline) if part),
        link=review["url"],
    )


def _comment_event(node: dict[str, Any]) -> Event:
    return Event(
        time=_time(node["createdAt"]),
        source="github",
        repo=node["repository"]["name"],
        title=f"Commented on #{node['issue']['number']}: {node['issue']['title']}",
        body=node["body"],
        link=node["url"],
    )
