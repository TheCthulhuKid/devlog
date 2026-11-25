"""The `devlog` command: parses arguments and prints results."""

import argparse
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path

from devlog.collectors.base import Collector, run_command
from devlog.collectors.registry import build_collectors, collect_events
from devlog.config import DEFAULT_CONFIG_PATH, Config, load_config
from devlog.drafts import DraftResult, EntryEditedError, draft_week
from devlog.events import write_events
from devlog.llm import LLMClient, connect_anthropic
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
    helps = {"collect": "gather a week's events", "draft": "write the week's draft entry"}
    parsers = {name: commands.add_parser(name, help=text) for name, text in helps.items()}
    for command in parsers.values():
        command.add_argument(
            "--week", help="ISO week such as 2026-W47 (default: last complete week)"
        )
    parsers["draft"].add_argument(
        "--overwrite", action="store_true", help="replace an entry you have edited"
    )
    return parser


def _collect(
    week: str, config: Config, collectors: Sequence[Collector], start: datetime, end: datetime
) -> int:
    events = collect_events(collectors, start, end)
    events_file = config.journal / ".devlog" / week / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    write_events(events, events_file)
    print(f"{week}: {len(events)} events written to {events_file}")
    for source, count in sorted(Counter(event.source for event in events).items()):
        print(f"  {source}: {count}")
    return 0


def _report_draft(week: str, result: DraftResult) -> int:
    print(f"{week}: draft written to {result.draft}")
    print(f"  entry to edit: {result.entry}")
    failed = " (selection failed)" if result.selection_failed else ""
    print(f"  claims kept: {result.kept} of {result.kept + result.left_out}{failed}")
    print(f"  claims left out: {result.unselected}")
    print(f"  claims dropped: {result.dropped}")
    print(f"  threads not summarised: {result.failed}")
    print(f"  repos not digested: {result.undigested}")
    print(f"  every thread: {result.threads}")
    usage = result.usage
    print(f"  tokens: {usage.input:,} in ({usage.cached:,} from cache), {usage.output:,} out")
    print(f"  details: {result.report}")
    return 1 if result.failed or result.selection_failed or result.undigested else 0


def _show_progress(done: int, total: int) -> None:
    print(f"  {done}/{total} threads summarised", file=sys.stderr)


def main(
    argv: Sequence[str] | None = None,
    *,
    today: date | None = None,
    build: Callable[[Config], Sequence[Collector]] = build_collectors,
    connect: Callable[[str], LLMClient] = connect_anthropic,
) -> int:
    """Run the command line. `today`, `build` and `connect` are only passed in by tests."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    week = args.week or last_complete_week(today or date.today())
    try:
        start, end = week_bounds(week)
        config = load_config(args.config)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.command == "collect":
        return _collect(week, config, build(config), start, end)
    try:
        result = draft_week(
            week,
            config.journal,
            config.repos,
            connect(config.model),
            run_command,
            _show_progress,
            overwrite=args.overwrite,
        )
    except (FileNotFoundError, EntryEditedError) as error:
        parser.error(str(error))
    return _report_draft(week, result)
