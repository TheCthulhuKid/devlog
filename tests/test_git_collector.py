from datetime import UTC, datetime
from pathlib import Path

from gitrepo import ALWAYS, collect_all, commit, git

from devlog.collectors.base import run_command
from devlog.collectors.git import AgentsFileCollector, GitCollector, read_diff
from devlog.events import Event

WEEK = (datetime(2026, 11, 16, tzinfo=UTC), datetime(2026, 11, 23, tzinfo=UTC))


def collect(log: str) -> list[Event]:
    outputs = {
        "config": "octocat@example.com\n",
        "ls-remote": "git@github.com:octocat/devlog.git\n",
        "remote": "origin\n",
        "log": log,
    }
    collector = GitCollector([Path("/work/devlog")], lambda args: outputs[args[5]])
    return collector.collect(*WEEK)


def test_commit_becomes_an_event_with_stats_and_files():
    log = (
        "\x1eabc123\x1f2026-11-17T09:30:00+01:00\x1forigin/retries\x1ffix: retry on timeout\x1f"
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
            files=("src/client.py", "tests/test_client.py"),
            branch="retries",
        )
    ]


def test_commits_outside_the_range_are_left_out():
    log = (
        "\x1eaaa\x1f2026-11-23T00:00:00+00:00\x1fmain\x1fnext week\x1f\x1f\n\n1\t0\ta.py\n"
        "\x1ebbb\x1f2026-11-22T23:59:00+00:00\x1fmain\x1fthis week\x1f\x1f\n\n1\t0\ta.py\n"
        "\x1eccc\x1f2026-11-15T23:59:00+00:00\x1fmain\x1frebased\x1f\x1f\n\n1\t0\ta.py\n"
    )

    assert [event.title for event in collect(log)] == ["this week"]


def test_lockfiles_are_left_out_of_changed_files(repo):
    commit(repo, "feat: add app", "src/app.py", "uv.lock")

    assert [event.files for event in collect_all(repo)] == [("src/app.py",)]


def test_commit_touching_only_generated_files_is_skipped(repo):
    commit(repo, "feat: add app", "src/app.py")
    commit(repo, "chore: rebuild", "uv.lock", "web/dist/app.min.js")

    assert [event.title for event in collect_all(repo)] == ["feat: add app"]


def test_a_commit_by_a_similar_email_is_left_out(repo):
    commit(repo, "feat: add app", "src/app.py")
    git(repo, "config", "user.email", "cat@example.com")

    assert collect_all(repo) == []


def test_commit_on_a_feature_branch_records_that_branch(repo):
    commit(repo, "feat: add app", "src/app.py")
    git(repo, "checkout", "--quiet", "-b", "retries")
    commit(repo, "fix: retry on timeout", "src/client.py")

    branches = {event.title: event.branch for event in collect_all(repo)}
    assert branches == {"feat: add app": "main", "fix: retry on timeout": "retries"}


def test_agents_md_change_becomes_a_note_event(repo):
    commit(repo, "feat: add app", "src/app.py")
    commit(repo, "docs: never commit for the user", "AGENTS.md", "src/app.py")

    [event] = AgentsFileCollector([repo], run_command).collect(*ALWAYS)
    assert (event.source, event.title) == (
        "notes",
        "AGENTS.md changed: docs: never commit for the user",
    )
    assert "+docs: never commit for the user" in event.body
    assert "src/app.py" not in event.body


def test_long_diff_is_cut_with_a_marker():
    diff = "+added line\n" * 100_000

    shown = read_diff(lambda args: diff, Path("/work/devlog"), "abc123")

    assert len(shown) < len(diff)
    assert diff.startswith(shown[: shown.rindex("\n")])
    assert shown.endswith(f"of {len(diff)} characters]")
