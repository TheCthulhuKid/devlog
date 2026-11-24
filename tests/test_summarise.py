from pathlib import Path

from gitrepo import collect_all, commit

from devlog.collectors.base import run_command
from devlog.events import read_events
from devlog.summarise import Claim, ClaimKind, ThreadSummary, summarise_thread
from devlog.threads import group_events

FIXTURES = Path(__file__).parent / "fixtures"
SUMMARY = ThreadSummary(
    what_changed="Redirects are rate limited per API key.",
    why="One client made 40k requests in an hour.",
    claims=(
        Claim(
            text="Chose a sliding window over a fixed one.",
            kind=ClaimKind.DECISION,
            evidence=("https://github.com/octocat/shortener/pull/15",),
        ),
    ),
)


class ScriptedLLM:
    def __init__(self, answer: ThreadSummary, calls: dict[str, dict] | None = None) -> None:
        self.answer = answer
        self.calls = calls or {}
        self.prompts: list[str] = []
        self.tool_results: list[str] = []

    def complete(self, system: str, prompt: str, output: type, tools=()) -> ThreadSummary:
        self.prompts.append(prompt)
        for tool in tools:
            if tool.name in self.calls:
                self.tool_results.append(tool.run(tool.input(**self.calls[tool.name])))
        return self.answer


def test_thread_events_are_all_given_to_the_model():
    events = read_events(FIXTURES / "week_feature_branch.jsonl")
    thread = max(group_events(events), key=lambda thread: len(thread.events))
    llm = ScriptedLLM(SUMMARY)

    assert summarise_thread(thread, llm, [], run_command) == SUMMARY
    [prompt] = llm.prompts
    assert all(event.link in prompt and event.title in prompt for event in thread.events)
    assert "The fixed window allowed twice the limit across a boundary." in prompt


def test_agent_can_read_a_diff_from_its_own_thread(repo):
    commit(repo, "fix: retry on timeout", "src/client.py")
    [thread] = group_events(collect_all(repo))
    llm = ScriptedLLM(SUMMARY, {"read_diff": {"commit": thread.events[0].link}})

    summarise_thread(thread, llm, [repo], run_command)

    [diff] = llm.tool_results
    assert "+++ b/src/client.py" in diff and "+fix: retry on timeout" in diff


def test_diff_request_outside_the_thread_is_refused(repo):
    commit(repo, "fix: retry on timeout", "src/client.py")
    commit(repo, "docs: describe the billing export", "docs/billing.md")
    other, own = collect_all(repo)
    [thread] = group_events([own])
    llm = ScriptedLLM(SUMMARY, {"read_diff": {"commit": other.link}})

    summarise_thread(thread, llm, [repo], run_command)

    assert llm.tool_results == ["Refused: that is not the link of a commit in this thread."]
