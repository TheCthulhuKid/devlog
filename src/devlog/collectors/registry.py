"""The one place collectors are registered, and running them together."""

from collections.abc import Sequence
from datetime import datetime

from devlog.collectors.base import Collector, Runner, run_command
from devlog.collectors.git import DEFAULT_IGNORED_FILES, AgentsFileCollector, GitCollector
from devlog.collectors.github import GitHubCollector
from devlog.collectors.notes import InboxCollector, NoteFilesCollector
from devlog.config import Config
from devlog.events import Event

INBOX_NAME = "inbox.md"


def build_collectors(config: Config, run: Runner = run_command) -> list[Collector]:
    """Return every collector, set up from the user's config."""
    return [
        GitCollector(config.repos, run, (*DEFAULT_IGNORED_FILES, *config.ignored_files)),
        AgentsFileCollector(config.repos, run),
        GitHubCollector(config.github_user, run),
        InboxCollector(config.journal / INBOX_NAME),
        NoteFilesCollector(config.notes_paths, config.repos),
    ]


def collect_events(collectors: Sequence[Collector], start: datetime, end: datetime) -> list[Event]:
    """Run every collector for `start <= time < end` and return their events, oldest first."""
    events = [event for collector in collectors for event in collector.collect(start, end)]
    return sorted(events, key=lambda event: event.time)
