"""The `devlog` command: parses arguments and prints results."""

import argparse
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from devlog.config import DEFAULT_CONFIG_PATH, load_config
from devlog.week import last_complete_week, week_range


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


def main(argv: Sequence[str] | None = None, *, today: date | None = None) -> int:
    """Run the command line. `today` is only passed in by tests."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    week = args.week or last_complete_week(today or date.today())
    try:
        start, end = week_range(week)
        config = load_config(args.config)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"{week}: {start} to {end}, repos: {len(config.repos)}")
    return 0
