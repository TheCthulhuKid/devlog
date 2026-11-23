"""ISO weeks, written like `2026-W47`, and the dates they cover."""

import re
from datetime import date, timedelta

_WEEK_PATTERN = re.compile(r"(\d{4})-W(\d{2})")


def week_range(week: str) -> tuple[date, date]:
    """Return the Monday and the Sunday of an ISO week such as `2026-W47`."""
    match = _WEEK_PATTERN.fullmatch(week)
    if match is None:
        raise ValueError(f"{week!r} is not an ISO week like 2026-W47")
    year, number = map(int, match.groups())
    monday = date.fromisocalendar(year, number, 1)
    return monday, monday + timedelta(days=6)


def last_complete_week(today: date) -> str:
    """Return the ISO week before the one `today` falls in."""
    year, number, _ = (today - timedelta(weeks=1)).isocalendar()
    return f"{year}-W{number:02d}"
