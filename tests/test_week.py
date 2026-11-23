from datetime import date

from devlog.week import last_complete_week, week_range


def test_week_range_runs_monday_to_sunday():
    assert week_range("2026-W47") == (date(2026, 11, 16), date(2026, 11, 22))


def test_default_week_is_the_last_complete_one():
    sunday = date(2026, 11, 22)

    assert last_complete_week(sunday) == "2026-W46"
