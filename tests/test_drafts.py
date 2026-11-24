import threading
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from devlog.collectors.base import run_command
from devlog.drafts import draft_week
from devlog.events import Event, write_events
from devlog.llm import LLMError, Usage
from devlog.summarise import Claim, ClaimKind, ThreadSummary

WEEK = "2026-W47"
PR = "https://github.com/octocat/shortener/pull/15"
BILLING_PR = "https://github.com/octocat/billing/pull/3"
SUMMARY = ThreadSummary(
    what_changed="Redirects are rate limited per API key.",
    why="One client made 40k requests in an hour.",
    claims=(
        Claim(text="Chose a sliding window.", kind=ClaimKind.DECISION, evidence=(PR,)),
        Claim(text="Redis would be faster.", kind=ClaimKind.LESSON, evidence=()),
    ),
)


class FakeLLM:
    model = "fake"
    usage = Usage()

    def __init__(self, fails_on: str | None = None) -> None:
        self.fails_on = fails_on

    def complete(self, system: str, prompt: str, output: type, tools=()) -> ThreadSummary:
        if self.fails_on and self.fails_on in prompt:
            raise LLMError("the model refused")
        return SUMMARY


def fake(complete) -> SimpleNamespace:
    return SimpleNamespace(complete=complete, model="fake", usage=Usage())


def opened(repo: str, link: str) -> Event:
    time = datetime(2026, 11, 17, tzinfo=UTC)
    return Event(
        time=time, source="github", repo=repo, title=f"Opened a PR in {repo}", body="", link=link
    )


@pytest.fixture
def journal(tmp_path):
    (tmp_path / ".devlog" / WEEK).mkdir(parents=True)
    return tmp_path


def test_draft_writes_the_entry_and_the_dropped_report(journal):
    write_events([opened("shortener", PR)], journal / ".devlog" / WEEK / "events.jsonl")

    result = draft_week(WEEK, journal, [], FakeLLM(), run_command)

    assert result.entry == journal / ".devlog" / WEEK / "draft.md"
    entry = result.entry.read_text()
    assert "Chose a sliding window." in entry
    assert "Redis would be faster." not in entry
    assert result.dropped == 1
    assert "Redis would be faster. (no evidence)" in result.report.read_text()


def test_a_thread_the_llm_fails_on_is_skipped_and_reported(journal):
    events = [opened("shortener", PR), opened("billing", BILLING_PR)]
    write_events(events, journal / ".devlog" / WEEK / "events.jsonl")

    result = draft_week(WEEK, journal, [], FakeLLM(fails_on="billing"), run_command)

    assert result.failed == 1
    assert "Chose a sliding window." in result.entry.read_text()
    assert "the model refused" in result.report.read_text()


def test_draft_without_events_says_to_collect_first(journal):
    with pytest.raises(FileNotFoundError, match="devlog collect --week 2026-W47"):
        draft_week(WEEK, journal, [], FakeLLM(), run_command)


def test_progress_is_reported_as_each_thread_finishes(journal):
    events = [opened("shortener", PR), opened("billing", BILLING_PR)]
    write_events(events, journal / ".devlog" / WEEK / "events.jsonl")
    seen = []

    draft_week(WEEK, journal, [], FakeLLM(), run_command, lambda done, total: seen.append(done))

    assert seen == [1, 2]


def test_entry_keeps_the_thread_order_when_a_later_thread_finishes_first(journal):
    events = [opened("shortener", PR), opened("billing", BILLING_PR)]
    write_events(events, journal / ".devlog" / WEEK / "events.jsonl")
    billing_done = threading.Event()

    def complete(system, prompt, output, tools):
        if "shortener" in prompt:
            billing_done.wait(timeout=5)
        billing_done.set()
        return SUMMARY.model_copy(update={"what_changed": prompt.splitlines()[0]})

    result = draft_week(WEEK, journal, [], fake(complete), run_command)

    entry = result.entry.read_text()
    assert entry.index("PR in shortener") < entry.index("PR in billing")


def test_an_error_that_is_not_a_failed_answer_stops_the_draft(journal):
    write_events([opened("shortener", PR)], journal / ".devlog" / WEEK / "events.jsonl")

    def complete(system, prompt, output, tools):
        raise ConnectionError("no network")

    with pytest.raises(ConnectionError, match="no network"):
        draft_week(WEEK, journal, [], fake(complete), run_command)


def test_rerun_only_pays_for_threads_not_yet_summarised(journal):
    events = [opened("shortener", PR), opened("billing", BILLING_PR)]
    write_events(events, journal / ".devlog" / WEEK / "events.jsonl")
    draft_week(WEEK, journal, [], FakeLLM(fails_on="billing"), run_command)
    asked = []

    def complete(system, prompt, output, tools):
        asked.append(prompt)
        return SUMMARY

    result = draft_week(WEEK, journal, [], fake(complete), run_command)

    assert result.failed == 0
    assert ["billing" in prompt for prompt in asked] == [True]
