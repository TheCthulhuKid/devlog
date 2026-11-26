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
from devlog.drafts import (
    DraftResult,
    EntryEditedError,
    UnknownEvidenceError,
    draft_week,
    sample_week,
)
from devlog.events import write_events
from devlog.llm import LLMClient, Usage, connect_anthropic
from devlog.stats import journal_stats, total
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
    helps = {
        "collect": "gather a week's events",
        "draft": "write the week's draft entry",
        "sample": "try the summary prompt on a few of the week's threads",
        "stats": "show how much of each draft you kept",
    }
    parsers = {name: commands.add_parser(name, help=text) for name, text in helps.items()}
    for name in ("collect", "draft", "sample"):
        parsers[name].add_argument(
            "--week", help="ISO week such as 2026-W47 (default: last complete week)"
        )
    parsers["draft"].add_argument(
        "--overwrite", action="store_true", help="replace an entry you have edited"
    )
    parsers["sample"].add_argument(
        "--again",
        action="store_true",
        help="ask afresh instead of reusing saved answers, and save nothing",
    )
    parsers["sample"].add_argument(
        "evidence",
        nargs="+",
        help="a commit hash or part of a link, copied from a claim",
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
    print(f"  {_tokens(result.usage)}")
    print(f"  details: {result.report}")
    return 1 if result.failed or result.selection_failed or result.undigested else 0


def _stats(journal: Path) -> int:
    weeks = journal_stats(journal)
    if not weeks:
        print("no week has both a draft and an entry yet")
        return 0
    print(f"{'week':<10}{'drafted':>8}{'kept':>6}{'removed':>9}{'added':>7}{'edit rate':>11}")
    for week in weeks:
        row = total(week.sections)
        print(
            f"{week.week:<10}{row.drafted:>8}{row.kept:>6}{row.removed:>9}{row.added:>7}"
            f"{_percent(row.edit_rate):>11}"
        )
    return 0


def _percent(rate: float | None) -> str:
    return "-" if rate is None else f"{rate:.0%}"


def _show_progress(done: int, total: int) -> None:
    print(f"  {done}/{total} threads summarised", file=sys.stderr)


def _load(parser: argparse.ArgumentParser, path: Path) -> Config:
    try:
        return load_config(path)
    except (OSError, ValueError) as error:
        parser.error(str(error))


def _week(
    parser: argparse.ArgumentParser, given: str | None, today: date
) -> tuple[str, datetime, datetime]:
    week = given or last_complete_week(today)
    try:
        return week, *week_bounds(week)
    except ValueError as error:
        parser.error(str(error))


def _draft(
    parser: argparse.ArgumentParser, week: str, config: Config, llm: LLMClient, overwrite: bool
) -> int:
    try:
        result = draft_week(
            week, config.journal, config.repos, llm, run_command, _show_progress, overwrite
        )
    except (FileNotFoundError, EntryEditedError) as error:
        parser.error(str(error))
    return _report_draft(week, result)


def _sample(
    parser: argparse.ArgumentParser,
    week: str,
    config: Config,
    llm: LLMClient,
    evidence: Sequence[str],
    again: bool,
) -> int:
    try:
        text = sample_week(
            week, config.journal, config.repos, llm, run_command, evidence, _show_progress, again
        )
    except (FileNotFoundError, UnknownEvidenceError) as error:
        parser.error(str(error))
    print(text)
    print(_tokens(llm.usage))
    return 0


def _tokens(usage: Usage) -> str:
    return f"tokens: {usage.input:,} in ({usage.cached:,} from cache), {usage.output:,} out"


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
    config = _load(parser, args.config)
    if args.command == "stats":
        return _stats(config.journal)
    week, start, end = _week(parser, args.week, today or date.today())
    if args.command == "collect":
        return _collect(week, config, build(config), start, end)
    llm = connect(config.model)
    if args.command == "sample":
        return _sample(parser, week, config, llm, args.evidence, args.again)
    return _draft(parser, week, config, llm, args.overwrite)
