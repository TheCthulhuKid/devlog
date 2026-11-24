# devlog

Turns a week of git history, GitHub activity and notes into an engineering journal entry.

Work in progress: so far the command collects a week's events and writes a draft entry from them.

## Setup

```sh
uv sync --locked --group dev
```

To have git refuse a commit that fails the Ruff lint or format check, turn on the repo's hook once
per clone:

```sh
git config core.hooksPath .githooks
```

## Configuration

devlog reads `~/.config/devlog/config.toml`, or the file given with `--config`. Paths may start with `~`.

```toml
github_user = "octocat"
journal = "~/notes/journal"            # the notes repo entries are written to; must exist
repos = ["~/projects/devlog"]          # git repos to read; each must exist
notes_paths = ["~/projects/devlog/PLAN.md"]  # optional: Markdown files or folders, such as plans
ignored_files = ["*.snap"]             # optional: extra patterns for files to leave out of commits
model = "claude-opus-5-5"              # optional: the Claude model that writes drafts (the default)
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
devlog draft --week 2026-W47    # write that week's draft entry from its collected events
```

`collect` reads your commits, your GitHub pull requests, issues, reviews and comments (through the `gh`
command, which must be logged in), your inbox and your note files, and writes them, oldest first, to
`.devlog/<week>/events.jsonl` in the journal folder. A week runs from Monday 00:00 to the next Monday
00:00 in your local timezone. If any source fails, nothing is written.

`draft` groups the week's events into threads of work, asks Claude to summarise each one, and writes the
entry to `.devlog/<week>/draft.md` in the journal folder. It needs the week's `events.jsonl`, so run
`collect` first, and an Anthropic API key in the `ANTHROPIC_API_KEY` environment variable. Each thread
is one paid API request, or a few when the model reads a diff or a file. Four threads are summarised at
a time, and a line such as `12/54 threads summarised` is printed as each one finishes.

Each summary is saved in `.devlog/<week>/summaries/` as soon as it is made, so running `draft` again only
pays for threads that are new or whose events changed, and a run that stops halfway keeps what it has
done. Changing the summary prompt or the `model` asks for every thread again. Saved summaries are never
deleted; remove the folder to start the week afresh. `draft` ends by printing the tokens the run spent,
such as `tokens: 412,300 in (0 from cache), 96,150 out`; a run that reused every summary spends none.

A week's threads claim more than anyone rereads, so when they make more than 15 claims, one more
request asks Claude to pick about 15 for the entry. It picks by number: the claims are printed as the
thread summaries wrote them. `draft` prints how many were kept, and the rest are in
`.devlog/<week>/unselected.md`, written as entry lines under their kind so one can be pasted back. If
the pick fails, the draft holds every claim and the command exits with status 1.

Every statement in the draft names the commit, pull request or note behind it. Evidence on GitHub is
a link; evidence with no web page (a note, or a commit from a repo with no GitHub remote) is named in
code style instead. A statement is left out when it cites no evidence, or evidence from outside its own
thread. `draft` prints how many were dropped and lists them in `.devlog/<week>/dropped.md`. Both
reports are rewritten on every run. A thread the model could not summarise is skipped and listed there too, and the
command then exits with status 1.
