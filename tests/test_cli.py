from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from devlog.cli import main
from devlog.events import Event, read_events


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
