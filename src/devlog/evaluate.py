"""Evaluates a generated entry: whether its evidence exists, and how it compares with gold."""

import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from devlog.collectors.base import Runner

_GITHUB_COMMIT = re.compile(r"\(https://github\.com/[^/\s]+/([^/\s]+)/commit/([0-9a-f]{7,40})\)")
_LOCAL_COMMIT = re.compile(r"`([0-9a-f]{7})`(?=[,)])")


class LinkStatus(StrEnum):
    """What became of a commit an entry cites."""

    OK = "ok"
    NOT_PUSHED = "not pushed"
    BROKEN = "broken"


@dataclass(frozen=True)
class CheckedLink:
    """A commit an entry cites, by its short hash, and whether it was found."""

    label: str
    status: LinkStatus


def check_links(entry: str, repos: Sequence[Path], run: Runner) -> list[CheckedLink]:
    """Return every commit `entry` cites, in the order cited, with whether `repos` hold it.

    A GitHub link is looked up in the repo of that name. A commit cited by its hash alone has
    no link, so every repo is searched. A commit no remote branch holds is `NOT_PUSHED`: its
    GitHub link is dead, or it never had one.
    """
    cited: dict[str, list[Path]] = {}
    for name, sha in _GITHUB_COMMIT.findall(entry):
        cited.setdefault(sha, [repo for repo in repos if repo.name == name])
    for sha in _LOCAL_COMMIT.findall(entry):
        cited.setdefault(sha, list(repos))
    return [CheckedLink(sha[:7], _status(sha, among, run)) for sha, among in cited.items()]


def _status(sha: str, repos: Sequence[Path], run: Runner) -> LinkStatus:
    for repo in repos:
        if _holds(repo, sha, run):
            return LinkStatus.OK if _pushed(repo, sha, run) else LinkStatus.NOT_PUSHED
    return LinkStatus.BROKEN


def _holds(repo: Path, sha: str, run: Runner) -> bool:
    try:
        run(["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"])
    except subprocess.CalledProcessError:
        return False
    return True


def _pushed(repo: Path, sha: str, run: Runner) -> bool:
    return bool(run(["git", "-C", str(repo), "branch", "--remotes", "--contains", sha]).strip())
