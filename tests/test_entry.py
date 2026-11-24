from datetime import UTC, datetime

from devlog.entry import assemble_entry
from devlog.events import Event
from devlog.summarise import Claim, ClaimKind, ThreadSummary
from devlog.templates import load
from devlog.threads import Thread

WEEK = "2026-W47"
PR = "https://github.com/octocat/shortener/pull/15"
COMMIT = "https://github.com/octocat/shortener/commit/0101010101010101010101010101010101010101"
NOTE = "inbox.md#2026-11-17"
WHAT_CHANGED = "Redirects are rate limited per API key."
WHY = "One client made 40k requests in an hour."


def summarised(*claims: Claim) -> tuple[Thread, ThreadSummary]:
    opened = Event(
        time=datetime(2026, 11, 17, tzinfo=UTC),
        source="github",
        repo="shortener",
        title="Opened PR #15: rate limit redirects",
        body="",
        link=PR,
    )
    thread = Thread(id="shortener-1", repo="shortener", events=(opened,))
    return thread, ThreadSummary(what_changed=WHAT_CHANGED, why=WHY, claims=claims)


def test_each_claim_lands_in_its_section_with_its_links():
    decision = Claim(text="Chose a sliding window.", kind=ClaimKind.DECISION, evidence=(PR, COMMIT))
    lesson = Claim(text="Fixed windows leak.", kind=ClaimKind.LESSON, evidence=(NOTE,))

    entry = assemble_entry(WEEK, [summarised(decision, lesson)], "$decisions|$lessons")

    decisions, lessons = entry.split("|")
    assert decisions == f"- Chose a sliding window. ([#15]({PR}), [0101010]({COMMIT}))"
    assert lessons == f"- Fixed windows leak. ([inbox.md#2026-11-17]({NOTE}))"


def test_section_with_no_claims_says_nothing_this_week():
    assert assemble_entry(WEEK, [summarised()], "$dead_ends") == "Nothing this week."


def test_each_thread_gets_a_line_saying_what_changed_and_why():
    entry = assemble_entry(WEEK, [summarised()], "$threads")

    assert entry == f"- **shortener:** {WHAT_CHANGED} {WHY}"


def test_entry_shows_the_week_from_monday_to_sunday():
    assert assemble_entry(WEEK, [], "$week $start $end") == "2026-W47 2026-11-16 2026-11-22"


def test_entry_template_has_a_place_for_every_field():
    claims = [Claim(text=f"A {kind} claim.", kind=kind, evidence=(PR,)) for kind in ClaimKind]

    entry = assemble_entry(WEEK, [summarised(*claims)], load("entry.md"))

    expected = [WEEK, "2026-11-16", "2026-11-22", WHAT_CHANGED, *(claim.text for claim in claims)]
    assert [text for text in expected if text not in entry] == []
