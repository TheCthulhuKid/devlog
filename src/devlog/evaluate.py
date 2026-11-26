"""Evaluates a generated entry: whether its evidence exists, and how it compares with gold."""

import re
import subprocess
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from devlog.collectors.base import Runner
from devlog.entry import sections

MARKS = ("matched", "missed", "wrong", "extra")
UNMARKED = "unmarked"
_TO_MARK = re.compile(r"^( *)- \[ *(\w*) *\]", re.MULTILINE)
_GITHUB_COMMIT = re.compile(r"\(https://github\.com/[^/\s]+/([^/\s]+)/commit/([0-9a-f]{7,40})\)")
_LOCAL_COMMIT = re.compile(r"`([0-9a-f]{7})`(?=[,)])")
_DECISIONS = "Decisions"
_HOW_TO_MARK = (
    "Write a mark in each `[ ]`. A gold decision is `matched` or `missed`. A generated decision\n"
    "is `wrong` or `extra` (true, but not in gold); leave it empty when it is the match of the\n"
    "gold decision above it."
)
_TRAILING_BRACKETS = re.compile(r"\(([^()]*)\)$")
_SHORT_HASH = re.compile(r"\b[0-9a-f]{7}\b")


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


@dataclass(frozen=True)
class Evaluation:
    """What `evaluate_week` found: the cited commits, the score sheet and the marks on it."""

    links: list[CheckedLink]
    sheet: Path
    marks: Counter[str]


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


def score_sheet(gold: str, generated: str) -> str:
    """Return a sheet to mark: each decision of `gold` with the `generated` ones sharing a commit.

    A generated decision is listed under every gold decision it shares a commit with. Those
    that share none follow in a section of their own.
    """
    drafted = sections(generated).get(_DECISIONS, [])
    paired: set[str] = set()
    lines = [_HOW_TO_MARK, "", "## Gold decisions", ""]
    for decision in sections(gold).get(_DECISIONS, []):
        commits = _gold_commits(decision)
        matches = [line for line in drafted if commits & _cited_commits(line)]
        paired.update(matches)
        lines.append(_to_mark(decision))
        lines += [f"  {_to_mark(line)}" for line in matches] or ["  - no match"]
    rest = [_to_mark(line) for line in drafted if line not in paired]
    return "\n".join([*lines, "", "## Generated decisions not in gold", "", *rest]) + "\n"


def count_marks(sheet: str) -> Counter[str]:
    """Return how often each mark is on `sheet`, and how many decisions are still `UNMARKED`.

    An indented decision left empty is the match of the gold decision above it, so it is not
    counted. A mark that is not one of `MARKS` raises `ValueError`.
    """
    counts: Counter[str] = Counter()
    for indent, mark in _TO_MARK.findall(sheet):
        if mark and mark not in MARKS:
            raise ValueError(f"unknown mark `{mark}`: write one of {', '.join(MARKS)}")
        if mark or not indent:
            counts[mark or UNMARKED] += 1
    return counts


def evaluate_week(week: str, journal: Path, repos: Sequence[Path], run: Runner) -> Evaluation:
    """Check the commits the draft of `week` cites, and count the marks on its score sheet.

    The sheet is `.devlog/<week>/scores.md`. It is written from the gold entry and the draft
    when it does not exist, and never replaced, so marks are kept: delete it to start again.

    Raises `FileNotFoundError` when the week has no draft or no gold entry.
    """
    folder = journal / ".devlog" / week
    draft = _read(folder / "draft.md", f"run `devlog draft --week {week}` first")
    gold = _read(journal / "gold" / f"{week}.md", "write the gold entry first")

    sheet_file = folder / "scores.md"
    if not sheet_file.exists():
        sheet_file.write_text(score_sheet(gold, draft), encoding="utf-8")
    marks = count_marks(sheet_file.read_text(encoding="utf-8"))
    return Evaluation(check_links(draft, repos, run), sheet_file, marks)


def _read(file: Path, hint: str) -> str:
    if not file.exists():
        raise FileNotFoundError(f"{file} does not exist: {hint}")
    return file.read_text(encoding="utf-8")


def _to_mark(line: str) -> str:
    return f"- [ ] {line.removeprefix('- ')}"


def _gold_commits(line: str) -> set[str]:
    brackets = _TRAILING_BRACKETS.search(line)
    return set(_SHORT_HASH.findall(brackets[1])) if brackets else set()


def _cited_commits(line: str) -> set[str]:
    github = {sha[:7] for _, sha in _GITHUB_COMMIT.findall(line)}
    return github | set(_LOCAL_COMMIT.findall(line))


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
