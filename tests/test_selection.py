from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from devlog.events import Event
from devlog.llm import LLMError, Usage
from devlog.selection import TARGET, Selection, select_claims
from devlog.summarise import Claim, ClaimKind, ThreadSummary
from devlog.threads import Thread

PR = "https://github.com/octocat/shortener/pull/15"


def summarised(repo: str, count: int) -> tuple[Thread, ThreadSummary]:
    opened = Event(
        time=datetime(2026, 11, 17, tzinfo=UTC),
        source="github",
        repo=repo,
        title="Opened a PR",
        body="",
        link=PR,
    )
    claims = tuple(
        Claim(text=f"{repo} claim {number}.", kind=ClaimKind.DECISION, evidence=(PR,))
        for number in range(1, count + 1)
    )
    thread = Thread(id=f"{repo}-1", repo=repo, events=(opened,))
    return thread, ThreadSummary(what_changed="Changed.", why="Needed.", claims=claims)


def fake(complete) -> SimpleNamespace:
    return SimpleNamespace(complete=complete, model="fake", usage=Usage())


def test_only_the_picked_claims_stay_with_text_and_evidence_unchanged():
    week = [summarised("shortener", TARGET), summarised("billing", 2)]

    def complete(system, prompt, output, tools=()):
        wanted = ("shortener claim 2.", "billing claim 1.")
        lines = [line for line in prompt.splitlines() if line.endswith(wanted)]
        return Selection(keep=tuple(int(line.split(".")[0]) for line in lines))

    kept, left_out = select_claims(week, fake(complete))

    assert kept[0][1].claims == (week[0][1].claims[1],)
    assert kept[1][1].claims == (week[1][1].claims[0],)
    assert len(left_out) == TARGET


def test_a_pick_that_was_not_listed_fails():
    week = [summarised("shortener", TARGET + 1)]

    def complete(system, prompt, output, tools=()):
        return Selection(keep=(1, TARGET + 2))

    with pytest.raises(LLMError, match=str(TARGET + 2)):
        select_claims(week, fake(complete))


def test_an_empty_pick_fails():
    week = [summarised("shortener", TARGET + 1)]

    with pytest.raises(LLMError, match="no claims"):
        select_claims(week, fake(lambda *args: Selection(keep=())))


def test_a_week_within_the_target_is_not_sent_to_the_llm():
    week = [summarised("shortener", TARGET)]

    def complete(system, prompt, output, tools=()):
        raise AssertionError("the LLM was asked")

    assert select_claims(week, fake(complete)) == (week, [])
