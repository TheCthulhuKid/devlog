"""Collects the user's commits, and their changes to AGENTS.md, from local git repositories."""

import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from devlog.collectors.base import Runner
from devlog.events import Event

_RECORD, _FIELD = "\x1e", "\x1f"
_LOG_FORMAT = f"--format=%x1e{'%x1f'.join(['%H', '%aI', '%S', '%s', '%b', ''])}"
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
_MAX_OUTPUT = 20_000  # This is a guess for the moment. May need tweaking.


class GitCollector:
    """One event per non-merge commit the repo's configured user authored, on any branch.

    An event's branch is the one git reached the commit through. That is the branch it was made
    on while that branch is unmerged, and a best guess afterwards.

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
        log_args = ("--no-renames", "--numstat", "--", *self._excludes)
        return [
            _commit_event(repo.name, commit)
            for repo in self._repos
            for commit in _commits(self._run, repo, start, end, *log_args)
        ]


class AgentsFileCollector:
    """One event per commit of the user's that changes an AGENTS.md, with the change as body."""

    def __init__(self, repos: Sequence[Path], run: Runner) -> None:
        self._repos = repos
        self._run = run

    def collect(self, start: datetime, end: datetime) -> list[Event]:
        """Return the AGENTS.md changes authored in `start <= time < end`, across all repos."""
        return [
            Event(
                time=commit.time,
                source="notes",
                repo=repo.name,
                title=f"AGENTS.md changed: {commit.subject}",
                body=commit.output.strip(),
                link=commit.link,
                branch=commit.branch,
            )
            for repo in self._repos
            for commit in _commits(
                self._run, repo, start, end, "--patch", "--", ":(glob)**/AGENTS.md"
            )
        ]


def read_diff(run: Runner, repo: Path, sha: str) -> str:
    """Return the diff of commit `sha`, cut at a fixed size."""
    return _cut(_git(run, repo, "show", "--format=", "--patch", sha))


def read_file(run: Runner, repo: Path, sha: str, path: str) -> str:
    """Return the file at `path` as it was in the commit `sha`, cut at a fixed size."""
    return _cut(_git(run, repo, "show", f"{sha}:{path}"))


def _git(run: Runner, repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), "-c", "core.quotePath=false", *args])


def _cut(text: str) -> str:
    if len(text) <= _MAX_OUTPUT:
        return text
    return f"{text[:_MAX_OUTPUT]}\n[cut: the first {_MAX_OUTPUT} of {len(text)} characters]"


class _Commit(NamedTuple):
    time: datetime
    link: str
    branch: str | None
    subject: str
    message: str
    output: str


def _commits(
    run: Runner, repo: Path, start: datetime, end: datetime, *log_args: str
) -> list[_Commit]:
    author = _git(run, repo, "config", "user.email").strip()
    link_prefix = _link_prefix(repo.name, _git(run, repo, "ls-remote", "--get-url", "origin"))
    remotes = _git(run, repo, "remote").split()
    log = _git(
        run,
        repo,
        "log",
        "--branches",
        "--exclude=*/HEAD",
        "--remotes",
        "--no-merges",
        f"--author={author}",
        f"--since={start.isoformat()}",
        _LOG_FORMAT,
        *log_args,
    )
    commits = [_commit(record, link_prefix, remotes) for record in log.split(_RECORD)[1:]]
    return [commit for commit in commits if start <= commit.time < end]


def _commit(record: str, link_prefix: str, remotes: Sequence[str]) -> _Commit:
    sha, authored, ref, subject, message, output = record.split(_FIELD)
    return _Commit(
        time=datetime.fromisoformat(authored),
        link=f"{link_prefix}{sha}",
        branch=_branch(ref, remotes),
        subject=subject or "(no commit message)",
        message=message.strip(),
        output=output,
    )


def _link_prefix(repo_name: str, remote: str) -> str:
    match = _GITHUB_REMOTE.fullmatch(remote.strip())
    if match is None:
        return f"{repo_name}@"
    return f"https://github.com/{match['slug']}/commit/"


def _branch(ref: str, remotes: Sequence[str]) -> str | None:
    prefixes = (f"{remote}/" for remote in remotes)
    prefix = next((prefix for prefix in prefixes if ref.startswith(prefix)), "")
    return ref.removeprefix(prefix) or None


def _commit_event(repo_name: str, commit: _Commit) -> Event:
    changes = [line.split("\t", maxsplit=2) for line in commit.output.splitlines() if line]
    return Event(
        time=commit.time,
        source="git",
        repo=repo_name,
        title=commit.subject,
        body="\n\n".join(part for part in (commit.message, _stats(changes)) if part),
        link=commit.link,
        files=tuple(path for _, _, path in changes),
        branch=commit.branch,
    )


def _stats(changes: Sequence[Sequence[str]]) -> str:
    files = [f"{path} (+{added} -{deleted})" for added, deleted, path in changes]
    return "\n".join([f"Files changed: {len(files)}", *files])
