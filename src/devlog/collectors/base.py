"""What collectors share: the protocol they implement and how they run commands."""

import subprocess
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Protocol

from devlog.events import Event

Runner = Callable[[Sequence[str]], str]


def run_command(args: Sequence[str]) -> str:
    """Run a command and return its output. A failing command raises `CalledProcessError`.

    Output that is not UTF-8 is kept, with a replacement character for each byte it can't decode.
    """
    result = subprocess.run(
        args, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return result.stdout


class Collector(Protocol):
    """Gathers the events of one source."""

    def collect(self, start: datetime, end: datetime) -> list[Event]:
        """Return the events with `start <= time < end`. Both bounds are timezone-aware."""
        ...
