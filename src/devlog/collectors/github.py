"""Collects the user's GitHub pull requests and issues through the `gh` command."""

import json
from datetime import UTC, datetime
from typing import Any

from devlog.collectors.base import Runner
from devlog.events import Event

_FIELDS = "number,title,body,url,repository,isPullRequest,state,createdAt,closedAt"
_SEARCH_LIMIT = 1000


class GitHubCollector:
    """One event when a pull request or issue the user wrote is opened, one when it is closed."""

    def __init__(self, user: str, run: Runner) -> None:
        self._user = user
        self._run = run

    def collect(self, start: datetime, end: datetime) -> list[Event]:
        """Return the openings and closings with `start <= time < end`."""
        updated_since = start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        output = self._run(
            [
                "gh",
                "search",
                "issues",
                "--include-prs",
                f"--author={self._user}",
                f"--updated=>={updated_since}",
                f"--limit={_SEARCH_LIMIT}",
                f"--json={_FIELDS}",
            ]
        )
        items = json.loads(output)
        if len(items) >= _SEARCH_LIMIT:
            raise RuntimeError(
                f"gh returned {len(items)} results, its limit, so some may be missing; "
                "collect a more recent week"
            )
        events = [event for item in items for event in _events(item)]
        return [event for event in events if start <= event.time < end]


def _events(item: dict[str, Any]) -> list[Event]:
    kind = "PR" if item["isPullRequest"] else "issue"
    moments = [("Opened", item["createdAt"])]
    if item["state"] != "open":
        moments.append((item["state"].capitalize(), item["closedAt"]))
    return [
        Event(
            time=datetime.fromisoformat(moment),
            source="github",
            repo=item["repository"]["name"],
            title=f"{action} {kind} #{item['number']}: {item['title']}",
            body=item["body"],
            link=item["url"],
        )
        for action, moment in moments
    ]
