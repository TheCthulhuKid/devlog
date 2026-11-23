# devlog

Turns a week of git history, GitHub activity and notes into an engineering journal entry.

Work in progress: so far the command only reads its config and works out the week.

## Setup

```sh
uv sync --locked --group dev
```

## Configuration

devlog reads `~/.config/devlog/config.toml`, or the file given with `--config`. Paths may start with `~`.

```toml
github_user = "octocat"
journal = "~/notes/journal"            # the notes repo entries are written to
repos = ["~/projects/devlog"]          # git repos to read; each must exist
notes_paths = ["~/.claude/plans"]      # optional: plan files and session notes
```

## Usage

```sh
devlog collect                  # the last complete week (Monday to Sunday)
devlog collect --week 2026-W47  # a given ISO week
```
