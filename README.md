# devlog

Turns a week of git history, GitHub activity and notes into an engineering journal entry.

Work in progress: so far the command collects a week's events; it does not write entries yet.

## Setup

```sh
uv sync --locked --group dev
```

## Configuration

devlog reads `~/.config/devlog/config.toml`, or the file given with `--config`. Paths may start with `~`.

```toml
github_user = "octocat"
journal = "~/notes/journal"            # the notes repo entries are written to; must exist
repos = ["~/projects/devlog"]          # git repos to read; each must exist
notes_paths = ["~/projects/devlog/PLAN.md"]  # optional: Markdown files or folders, such as plans
ignored_files = ["*.snap"]             # optional: extra patterns for files to leave out of commits
```

Lockfiles, minified files and other generated files are always left out of commits. Claude Code's
memory notes (`~/.claude/projects/*/memory/`) are never read, even inside a `notes_paths` folder.

## Inbox notes

Quick thoughts go in `inbox.md` in the journal folder. Each bullet under a date heading is one note; lines
after a bullet belong to it. A bullet with no date heading above it is an error, so no note is lost.

```markdown
## 2026-11-18
- Caching was a dead end
  Invalidation cost more than it saved.
- Ask about rate limits
```

## Usage

```sh
devlog collect                  # the last complete week (Monday to Sunday)
devlog collect --week 2026-W47  # a given ISO week
```

`collect` reads your commits, your GitHub pull requests, issues, reviews and comments (through the `gh`
command, which must be logged in), your inbox and your note files, and writes them, oldest first, to
`.devlog/<week>/events.jsonl` in the journal folder. A week runs from Monday 00:00 to the next Monday
00:00 in your local timezone. If any source fails, nothing is written.
