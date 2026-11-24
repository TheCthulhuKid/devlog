from pathlib import Path

from devlog.events import read_events
from devlog.threads import group_events

FIXTURES = Path(__file__).parent / "fixtures"
RATE_LIMIT_COMMITS = {
    "feat: count requests per api key",
    "refactor: switch to a sliding window",
    "test: pass the clock into the limiter",
    "feat: answer 429 with retry-after",
}
RUNNER_COMMITS = {
    "feat: add a retrieval-only baseline",
    "fix: score ties as half a win",
    "feat: add a reranking stage",
    "revert: remove the reranking stage",
}
NOTE = "Fixed window lets a burst through at the boundary"


def thread_of(week: str, title: str) -> set[str]:
    threads = group_events(read_events(FIXTURES / f"{week}.jsonl"))
    [thread] = [thread for thread in threads if title in {event.title for event in thread.events}]
    return {event.title for event in thread.events}


def test_commits_on_one_branch_form_one_thread():
    thread = thread_of("week_feature_branch", "feat: count requests per api key")

    assert thread >= RATE_LIMIT_COMMITS


def test_pr_and_the_issue_it_references_share_a_thread():
    thread = thread_of("week_feature_branch", "Opened PR #15: Rate limit redirects per API key")

    assert "Opened issue #14: Bots hammer the redirect endpoint" in thread


def test_commits_touching_the_same_files_share_a_thread():
    assert thread_of("week_two_repos", "feat: add a retrieval-only baseline") >= RUNNER_COMMITS


def test_unrelated_note_gets_its_own_thread():
    assert thread_of("week_feature_branch", NOTE) == {NOTE}


def test_unrelated_work_on_main_stays_apart():
    thread = thread_of("week_two_repos", "fix: undo keeps the names typed since")

    assert "feat: fold the initiative tracker" not in thread
