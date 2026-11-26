import threading
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from devlog.collectors.base import run_command
from devlog.digest import RepoDigest
from devlog.drafts import EntryEditedError, UnknownEvidenceError, draft_week, sample_week
from devlog.events import Event, write_events
from devlog.llm import LLMError, Usage
from devlog.selection import TARGET, Selection
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
MANY = SUMMARY.model_copy(
    update={
        "claims": tuple(
            Claim(text=f"Claim {number}.", kind=ClaimKind.DECISION, evidence=(PR,))
            for number in range(1, TARGET + 2)
        )
    }
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

    entry = result.draft.read_text()
    assert "Chose a sliding window." in entry
    assert "Redis would be faster." not in entry
    assert result.dropped == 1
    assert "Redis would be faster. (no evidence)" in result.report.read_text()


def test_draft_is_kept_beside_the_editable_entry(journal):
    write_events([opened("shortener", PR)], journal / ".devlog" / WEEK / "events.jsonl")

    result = draft_week(WEEK, journal, [], FakeLLM(), run_command)

    assert result.draft == journal / ".devlog" / WEEK / "draft.md"
    assert result.entry == journal / "entries" / f"{WEEK}.md"
    assert result.entry.read_text() == result.draft.read_text()


def test_an_edited_entry_is_not_overwritten(journal):
    events_file = journal / ".devlog" / WEEK / "events.jsonl"
    write_events([opened("shortener", PR)], events_file)
    entry = draft_week(WEEK, journal, [], FakeLLM(), run_command).entry
    entry.write_text("My own words.")
    write_events([opened("shortener", PR), opened("billing", BILLING_PR)], events_file)

    def complete(system, prompt, output, tools):
        raise AssertionError("the LLM was asked before the draft was refused")

    with pytest.raises(EntryEditedError, match="--overwrite"):
        draft_week(WEEK, journal, [], fake(complete), run_command)

    assert entry.read_text() == "My own words."


def test_an_untouched_entry_is_replaced_by_a_new_draft(journal):
    events_file = journal / ".devlog" / WEEK / "events.jsonl"
    write_events([opened("shortener", PR)], events_file)
    draft_week(WEEK, journal, [], FakeLLM(), run_command)
    write_events([opened("shortener", PR), opened("billing", BILLING_PR)], events_file)

    result = draft_week(WEEK, journal, [], FakeLLM(), run_command)

    assert "billing" in result.entry.read_text()


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


def test_an_interrupt_cancels_the_threads_not_yet_started(journal):
    events = [opened(f"repo{n}", f"https://github.com/octocat/repo{n}/pull/1") for n in range(20)]
    write_events(events, journal / ".devlog" / WEEK / "events.jsonl")
    interrupted = threading.Event()
    asked = []

    def complete(system, prompt, output, tools):
        asked.append(prompt)
        if len(asked) > 1:
            interrupted.wait(timeout=5)
        return SUMMARY

    def interrupt(done, total):
        interrupted.set()
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        draft_week(WEEK, journal, [], fake(complete), run_command, interrupt)

    assert len(asked) < len(events)


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


def test_draft_keeps_only_the_selected_claims_and_lists_the_rest(journal):
    write_events([opened("shortener", PR)], journal / ".devlog" / WEEK / "events.jsonl")

    def complete(system, prompt, output, tools=()):
        return Selection(keep=(1,)) if output is Selection else MANY

    result = draft_week(WEEK, journal, [], fake(complete), run_command)

    assert (result.kept, result.left_out) == (1, TARGET)
    assert "Claim 1." in result.entry.read_text()
    assert "Claim 2." not in result.entry.read_text()
    assert f"- Claim 2. ([#15]({PR}))" in result.unselected.read_text()


def test_draft_keeps_every_claim_when_selection_fails(journal):
    write_events([opened("shortener", PR)], journal / ".devlog" / WEEK / "events.jsonl")

    def complete(system, prompt, output, tools=()):
        if output is Selection:
            raise LLMError("the model refused")
        return MANY

    result = draft_week(WEEK, journal, [], fake(complete), run_command)

    assert result.selection_failed
    assert f"Claim {TARGET + 1}." in result.entry.read_text()
    assert "claims not selected (the model refused)" in result.report.read_text()


def test_draft_shows_a_digest_per_repo_and_keeps_every_thread_line_in_a_file(journal):
    events = [opened("shortener", PR), opened("shortener", PR.replace("15", "16"))]
    write_events(events, journal / ".devlog" / WEEK / "events.jsonl")

    def complete(system, prompt, output, tools=()):
        return RepoDigest(text="Rate limiting landed.") if output is RepoDigest else SUMMARY

    result = draft_week(WEEK, journal, [], fake(complete), run_command)

    entry = result.entry.read_text()
    assert "- **shortener:** Rate limiting landed." in entry
    assert SUMMARY.what_changed not in entry
    assert result.threads.read_text().count(SUMMARY.what_changed) == 2


def test_sample_summarises_only_the_threads_holding_the_evidence(journal):
    events = [opened("shortener", PR), opened("billing", BILLING_PR)]
    write_events(events, journal / ".devlog" / WEEK / "events.jsonl")
    asked = []

    def complete(system, prompt, output, tools=()):
        asked.append(prompt)
        return SUMMARY

    text = sample_week(WEEK, journal, [], fake(complete), run_command, ["shortener/pull/15"])

    assert len(asked) == 1
    assert "- Chose a sliding window." in text
    assert not (journal / ".devlog" / WEEK / "draft.md").exists()


def test_sample_again_asks_even_when_an_answer_is_saved(journal):
    write_events([opened("shortener", PR)], journal / ".devlog" / WEEK / "events.jsonl")
    asked = []

    def complete(system, prompt, output, tools=()):
        asked.append(prompt)
        return SUMMARY

    for again in (False, False, True):
        sample_week(WEEK, journal, [], fake(complete), run_command, ["pull/15"], again=again)

    assert len(asked) == 2


def test_sample_refuses_evidence_no_thread_holds(journal):
    write_events([opened("shortener", PR)], journal / ".devlog" / WEEK / "events.jsonl")

    with pytest.raises(UnknownEvidenceError, match="abc1234"):
        sample_week(WEEK, journal, [], FakeLLM(), run_command, ["abc1234"])
