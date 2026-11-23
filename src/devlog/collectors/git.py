"""Collects the user's commits from local git repositories."""

import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from devlog.collectors.base import Runner
from devlog.events import Event

_RECORD, _FIELD = "\x1e", "\x1f"
_LOG_FORMAT = f"--format=%x1e{'%x1f'.join(['%H', '%aI', '%s', '%b', ''])}"
DEFAULT_IGNORED_FILES = (
    "*.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "go.sum",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*_pb2.py",
    "*.pb.go",
    "dist/**",
    "node_modules/**",
)
_GITHUB_REMOTE = re.compile(
    r"(?:https://github\.com/|(?:ssh://)?git@github\.com[:/])(?P<slug>[^/]+/[^/]+?)(?:\.git)?/?"
)


class GitCollector:
    """One event per non-merge commit the repo's configured user authored, on any branch.

    Files matching `ignored_files` (globs, at any depth) are left out, and so is a commit that
    touches nothing else.
    """

    def __init__(
        self,
        repos: Sequence[Path],
        run: Runner,
        ignored_files: Sequence[str] = DEFAULT_IGNORED_FILES,
    ) -> None:
        self._repos = repos
        self._run = run
        self._excludes = [f":(exclude,glob)**/{pattern}" for pattern in ignored_files]

    def collect(self, start: datetime, end: datetime) -> list[Event]:
        """Return the commits authored in `start <= time < end`, across all repos."""
        events = [event for repo in self._repos for event in self._repo_events(repo, start)]
        return [event for event in events if start <= event.time < end]

    def _git(self, repo: Path, *args: str) -> str:
        return self._run(["git", "-C", str(repo), "-c", "core.quotePath=false", *args])

    def _repo_events(self, repo: Path, start: datetime) -> list[Event]:
        author = self._git(repo, "config", "user.email").strip()
        link_prefix = _link_prefix(repo.name, self._git(repo, "ls-remote", "--get-url", "origin"))
        log = self._git(
            repo,
            "log",
            "--branches",
            "--remotes",
            "--no-merges",
            "--no-renames",
            "--numstat",
            f"--author={author}",
            f"--since={start.isoformat()}",
            _LOG_FORMAT,
            "--",
            *self._excludes,
        )
        return [_event(record, repo.name, link_prefix) for record in log.split(_RECORD)[1:]]


def _link_prefix(repo_name: str, remote: str) -> str:
    match = _GITHUB_REMOTE.fullmatch(remote.strip())
    if match is None:
        return f"{repo_name}@"
    return f"https://github.com/{match['slug']}/commit/"


def _event(record: str, repo_name: str, link_prefix: str) -> Event:
    sha, authored, subject, message, numstat = record.split(_FIELD)
    changes = [line.split("\t", maxsplit=2) for line in numstat.splitlines() if line]
    return Event(
        time=datetime.fromisoformat(authored),
        source="git",
        repo=repo_name,
        title=subject or "(no commit message)",
        body="\n\n".join(part for part in (message.strip(), _stats(changes)) if part),
        link=f"{link_prefix}{sha}",
        files=tuple(path for _, _, path in changes),
    )


def _stats(changes: Sequence[Sequence[str]]) -> str:
    files = [f"{path} (+{added} -{deleted})" for added, deleted, path in changes]
    return "\n".join([f"Files changed: {len(files)}", *files])
