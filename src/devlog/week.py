"""ISO weeks, written like `2026-W47`, and the time they cover."""

import re
from datetime import date, datetime, time, timedelta, tzinfo

_WEEK_PATTERN = re.compile(r"(\d{4})-W(\d{2})")


def week_bounds(week: str, tz: tzinfo | None = None) -> tuple[datetime, datetime]:
    """Return Monday 00:00 of an ISO week such as `2026-W47`, and the following Monday 00:00.

    The times are in `tz`, or in the machine's local timezone when it is not given.
    """
    match = _WEEK_PATTERN.fullmatch(week)
    if match is None:
        raise ValueError(f"{week!r} is not an ISO week like 2026-W47")
    year, number = map(int, match.groups())
    monday = date.fromisocalendar(year, number, 1)
    start, end = (
        datetime.combine(day, time.min, tz).astimezone(tz)
        for day in (monday, monday + timedelta(weeks=1))
    )
    return start, end


def last_complete_week(today: date) -> str:
    """Return the ISO week before the one `today` falls in."""
    year, number, _ = (today - timedelta(weeks=1)).isocalendar()
    return f"{year}-W{number:02d}"
