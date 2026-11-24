from datetime import UTC, datetime
from types import SimpleNamespace

from devlog.digest import RepoDigest, digest_threads
from devlog.events import Event
from devlog.llm import LLMError, Usage
from devlog.summarise import ThreadSummary
from devlog.threads import Thread


def summarised(repo: str, number: int) -> tuple[Thread, ThreadSummary]:
    time = datetime(2026, 11, 17, tzinfo=UTC)
    opened = Event(time=time, source="github", repo=repo, title="Opened a PR", body="", link="x")
    thread = Thread(id=f"{repo}-{number}", repo=repo, events=(opened,))
    return thread, ThreadSummary(what_changed=f"Change {number}.", why="Needed.", claims=())


def fake(complete) -> SimpleNamespace:
    return SimpleNamespace(complete=complete, model="fake", usage=Usage())


WEEK = [summarised("shortener", 1), summarised("billing", 2), summarised("shortener", 3)]


def test_a_repo_with_several_threads_gets_one_digest_and_a_single_thread_keeps_its_line():
    def complete(system, prompt, output, tools=()):
        assert "Change 1." in prompt and "Change 3." in prompt
        return RepoDigest(text="Rate limiting\nlanded.")

    lines, report = digest_threads(WEEK, fake(complete))

    assert lines == ["- **shortener:** Rate limiting landed.", "- **billing:** Change 2. Needed."]
    assert report == []


def test_a_repo_whose_digest_fails_keeps_its_thread_lines():
    def complete(system, prompt, output, tools=()):
        raise LLMError("the model refused")

    lines, report = digest_threads(WEEK, fake(complete))

    assert lines[:2] == ["- **shortener:** Change 1. Needed.", "- **shortener:** Change 3. Needed."]
    assert report == ["- shortener: not digested (the model refused)"]
