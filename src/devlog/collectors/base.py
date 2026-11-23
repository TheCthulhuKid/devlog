"""The protocol every collector implements."""

from datetime import datetime
from typing import Protocol

from devlog.events import Event


class Collector(Protocol):
    """Gathers the events of one source."""

    def collect(self, start: datetime, end: datetime) -> list[Event]:
        """Return the events with `start <= time < end`. Both bounds are timezone-aware."""
        ...
