"""Helpers for tests that need a real git repository; the `repo` fixture is in `conftest.py`."""

from datetime import UTC, datetime
from pathlib import Path

from devlog.collectors.base import run_command
from devlog.collectors.git import GitCollector
from devlog.events import Event

ALWAYS = (datetime(2000, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC))


def git(repo: Path, *args: str) -> None:
    run_command(["git", "-C", str(repo), "-c", "commit.gpgsign=false", *args])


def commit(repo: Path, message: str, *paths: str) -> None:
    for path in paths:
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(message)
    git(repo, "add", ".")
    git(repo, "commit", "--quiet", "--message", message)


def collect_all(repo: Path) -> list[Event]:
    return GitCollector([repo], run_command).collect(*ALWAYS)
