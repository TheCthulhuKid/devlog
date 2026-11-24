from pathlib import Path

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
    def __init__(self, answer: ThreadSummary) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def complete(self, system: str, prompt: str, output: type) -> ThreadSummary:
        self.prompts.append(prompt)
        return self.answer


def test_thread_events_are_all_given_to_the_model():
    events = read_events(FIXTURES / "week_feature_branch.jsonl")
    thread = max(group_events(events), key=lambda thread: len(thread.events))
    llm = ScriptedLLM(SUMMARY)

    assert summarise_thread(thread, llm) == SUMMARY
    [prompt] = llm.prompts
    assert all(event.link in prompt and event.title in prompt for event in thread.events)
    assert "The fixed window allowed twice the limit across a boundary." in prompt
