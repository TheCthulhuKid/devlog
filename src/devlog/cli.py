"""The `devlog` command: parses arguments and prints results."""

import argparse
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from devlog.collectors.base import Collector
from devlog.collectors.registry import build_collectors, collect_events
from devlog.config import DEFAULT_CONFIG_PATH, Config, load_config
from devlog.events import write_events
from devlog.week import last_complete_week, week_bounds


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devlog", description="Write a weekly engineering journal."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="config file (default: %(default)s)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect", help="gather a week's events")
    collect.add_argument("--week", help="ISO week such as 2026-W47 (default: last complete week)")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    today: date | None = None,
    build: Callable[[Config], Sequence[Collector]] = build_collectors,
) -> int:
    """Run the command line. `today` and `build` are only passed in by tests."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    week = args.week or last_complete_week(today or date.today())
    try:
        start, end = week_bounds(week)
        config = load_config(args.config)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    events = collect_events(build(config), start, end)
    events_file = config.journal / ".devlog" / week / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    write_events(events, events_file)
    print(f"{week}: {len(events)} events written to {events_file}")
    for source, count in sorted(Counter(event.source for event in events).items()):
        print(f"  {source}: {count}")
    return 0
