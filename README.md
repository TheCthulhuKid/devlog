# devlog

Turns a week of git history, GitHub activity and notes into an engineering journal entry.

Work in progress: so far the command collects a week's events, writes a draft entry from them and
measures how much of each draft you kept.

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
devlog sample --week 2026-W47 57bfef1 pull/15  # summarise only the threads holding this evidence
devlog sample --week 2026-W47 --again 57bfef1  # ask afresh, to see how much the answers vary
devlog stats                    # how much of each week's draft you kept
```

`collect` reads your commits, your GitHub pull requests, issues, reviews and comments (through the `gh`
command, which must be logged in), your inbox and your note files, and writes them, oldest first, to
`.devlog/<week>/events.jsonl` in the journal folder. A week runs from Monday 00:00 to the next Monday
00:00 in your local timezone. If any source fails, nothing is written.

A note file that git tracks in one of your `repos` is collected from its commits: one event for each
commit of yours that changes it, holding the change. Collecting a past week again finds the same
notes, but an edit is not seen until it is committed. A note file git does not track is collected in
the week it last changed, with its current text; once it is edited again, collecting the earlier
week no longer finds it.

`draft` groups the week's events into threads of work, asks Claude to summarise each one, and writes the
entry twice in the journal folder: to `.devlog/<week>/draft.md`, which stays as generated, and to
`entries/<week>.md`, which is yours to edit. Running `draft` again replaces both, unless you have
edited the entry: then it stops before asking Claude anything, and `--overwrite` replaces your edits
with the new draft. It needs the week's `events.jsonl`, so run
`collect` first, and an Anthropic API key in the `ANTHROPIC_API_KEY` environment variable. Each thread
is one paid API request, or a few when the model reads a diff or a file. Four threads are summarised at
a time, and a line such as `12/54 threads summarised` is printed as each one finishes.

Each summary is saved in `.devlog/<week>/summaries/` as soon as it is made, so running `draft` again only
pays for threads that are new or whose events changed, and a run that stops halfway keeps what it has
done. Changing the summary prompt or the `model` asks for every thread again. Saved summaries are never
deleted; remove the folder to start the week afresh. `draft` ends by printing the tokens the run spent,
such as `tokens: 412,300 in (0 from cache), 96,150 out`; a run that reused every summary spends none.

The entry opens with what the week's work was, one line per repo. A repo with several threads gets a
digest of them, written by one more request per such repo; a repo with one thread keeps that thread's
line. The line of every thread is in `.devlog/<week>/threads.md`. If a digest fails, the entry lists
that repo's threads instead and the command exits with status 1.

A week's threads claim more than anyone rereads, so when they make more than 20 claims, one more
request asks Claude to pick at most 20 for the entry. It picks by number: the claims are printed as the
thread summaries wrote them. `draft` prints how many were kept, and the rest are in
`.devlog/<week>/unselected.md`, written as entry lines under their kind so one can be pasted back. If
the pick fails, the draft holds every claim and the command exits with status 1.

Every statement in the draft names the commit, pull request or note behind it. Evidence on GitHub is
a link; evidence with no web page (a note, or a commit from a repo with no GitHub remote) is named in
code style instead. A statement is left out when it cites no evidence, or evidence from outside its own
thread. `draft` prints how many were dropped and lists them in `.devlog/<week>/dropped.md`. All
three files are rewritten on every run. A thread the model could not summarise is skipped and listed there too, and the
command then exits with status 1.

`sample` is for trying a change to the summary prompt without paying for the whole week. Give it one
or more pieces of evidence copied from claims, such as a commit hash or part of a link, and it
summarises only the threads that hold them. It prints each thread's line and claims, the threads and
claims `draft` would have left out, and the tokens spent. It writes no draft and no entry. The
summaries it makes are saved with the week's others, so a later `draft` does not pay for them again.
Evidence that no thread holds is an error.

`devlog pick --week 2026-W47` tries the selection prompt: it prints the claims the pick keeps and how
many of each kind, and writes no draft. The threads' saved summaries are reused, so only the pick is paid for.
With `--again` the pick is asked afresh and its answer is not saved, so the same prompt can be run several times.

The model does not give the same answer twice, so one run says little about a wording. With
`--again`, `sample` asks every chosen thread afresh instead of reusing its saved summary, and saves
nothing: run it two or three times and compare what is printed. Each run is paid for in full.

`stats` compares every week's `draft.md` with its entry and prints one row per week, oldest first:

```
week       drafted  kept  removed  added  edit rate
2026-W47        24    21        3      2        12%
```

The edit rate is the share of the draft's lines that are not in the entry: 1 - kept / drafted. Only
non-blank lines under a `## ` heading count, and a line is kept when the same section of the entry
holds it unchanged, so a reworded line counts as one removed and one added. Lines you add do not
move the rate, and neither does the `Nothing this week.` line of an empty section. A week with no
entry is left out. The same numbers, with each section's own, are written to `.devlog/metrics.jsonl`,
one line per week; the file is rewritten on every run.
