from datetime import UTC, date, datetime

from devlog.week import last_complete_week, week_bounds


def test_week_runs_from_monday_midnight_to_the_next_monday():
    start, end = datetime(2026, 11, 16, tzinfo=UTC), datetime(2026, 11, 23, tzinfo=UTC)

    assert week_bounds("2026-W47", UTC) == (start, end)


def test_default_week_is_the_last_complete_one():
    sunday = date(2026, 11, 22)

    assert last_complete_week(sunday) == "2026-W46"
