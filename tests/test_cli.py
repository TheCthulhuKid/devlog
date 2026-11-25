from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from devlog.cli import main
from devlog.events import Event, read_events, write_events
from devlog.llm import LLMError, Usage
from devlog.summarise import Claim, ClaimKind, ThreadSummary

GUESS = Claim(text="Redis would be faster.", kind=ClaimKind.LESSON, evidence=())
SUMMARY = ThreadSummary(what_changed="Added a cache.", why="Slow redirects.", claims=(GUESS,))


def event(source: str, day: int) -> Event:
    time = datetime(2026, 11, day, tzinfo=UTC)
    return Event(time=time, source=source, repo=None, title=f"{source} {day}", body="", link="x")


def collector(*events: Event) -> SimpleNamespace:
    return SimpleNamespace(collect=lambda start, end: list(events))


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(f'github_user = "octocat"\njournal = "{tmp_path}"\nrepos = []\n')
    return path


@pytest.fixture
def week_folder(tmp_path):
    folder = tmp_path / ".devlog" / "2026-W47"
    folder.mkdir(parents=True)
    write_events([event("git", 17)], folder / "events.jsonl")
    return folder


def draft(config_file, complete, *options: str) -> int:
    llm = SimpleNamespace(complete=complete, model="fake", usage=Usage(1200, 0, 340))
    arguments = ["--config", str(config_file), "draft", "--week", "2026-W47", *options]
    return main(arguments, connect=lambda model: llm)


def test_collect_writes_all_sources_in_time_order(config_file, tmp_path, capsys):
    collectors = [collector(event("git", 20), event("git", 17)), collector(event("notes", 18))]

    main(
        ["--config", str(config_file), "collect"],
        today=date(2026, 11, 23),
        build=lambda config: collectors,
    )

    events_file = tmp_path / ".devlog" / "2026-W47" / "events.jsonl"
    assert [e.title for e in read_events(events_file)] == ["git 17", "notes 18", "git 20"]
    assert capsys.readouterr().out.splitlines()[1:] == ["  git: 2", "  notes: 1"]


def test_a_failing_collector_stops_the_run(config_file, tmp_path):
    def fail(start, end):
        raise RuntimeError("gh is not logged in")

    collectors = [collector(event("git", 17)), SimpleNamespace(collect=fail)]

    with pytest.raises(RuntimeError, match="gh is not logged in"):
        main(["--config", str(config_file), "collect"], build=lambda config: collectors)
    assert not (tmp_path / ".devlog").exists()


def test_draft_prints_where_the_entry_is_and_what_was_dropped(
    config_file, week_folder, tmp_path, capsys
):
    status = draft(config_file, lambda system, prompt, output, tools: SUMMARY)

    assert status == 0
    assert capsys.readouterr().out.splitlines() == [
        f"2026-W47: draft written to {week_folder / 'draft.md'}",
        f"  entry to edit: {tmp_path / 'entries' / '2026-W47.md'}",
        "  claims kept: 0 of 0",
        f"  claims left out: {week_folder / 'unselected.md'}",
        "  claims dropped: 1",
        "  threads not summarised: 0",
        "  repos not digested: 0",
        f"  every thread: {week_folder / 'threads.md'}",
        "  tokens: 1,200 in (0 from cache), 340 out",
        f"  details: {week_folder / 'dropped.md'}",
    ]


def test_draft_overwrite_replaces_an_edited_entry(config_file, week_folder, tmp_path):
    def complete(system, prompt, output, tools):
        return SUMMARY

    draft(config_file, complete)
    entry = tmp_path / "entries" / "2026-W47.md"
    entry.write_text("My own words.")

    with pytest.raises(SystemExit):
        draft(config_file, complete)
    assert draft(config_file, complete, "--overwrite") == 0
    assert entry.read_text() == (week_folder / "draft.md").read_text()


def test_draft_exits_with_1_when_a_thread_failed(config_file, week_folder):
    def refuse(system, prompt, output, tools):
        raise LLMError("the model refused")

    assert draft(config_file, refuse) == 1


def test_draft_shows_progress_apart_from_its_result(config_file, week_folder, capsys):
    draft(config_file, lambda system, prompt, output, tools: SUMMARY)

    assert capsys.readouterr().err == "  1/1 threads summarised\n"


def test_stats_prints_each_weeks_edit_rate(config_file, tmp_path, capsys):
    (tmp_path / ".devlog" / "2026-W47").mkdir(parents=True)
    draft_file = tmp_path / ".devlog" / "2026-W47" / "draft.md"
    draft_file.write_text("## Decisions\n\n- Use Redis.\n- Cache redirects.\n", encoding="utf-8")
    (tmp_path / "entries").mkdir()
    (tmp_path / "entries" / "2026-W47.md").write_text("## Decisions\n\n- Use Redis.\n")

    assert main(["--config", str(config_file), "stats"]) == 0

    week_row = capsys.readouterr().out.splitlines()[1]
    assert week_row.split() == ["2026-W47", "2", "1", "1", "0", "50%"]
