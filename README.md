# devlog

Turns a week of git history, GitHub activity and notes into an engineering journal entry: what the
week's work was, the decisions made, the dead ends, the lessons and what is still open. Every
statement names the commit, pull request or note behind it, and a statement with no evidence is
left out.

I built it because I find it hard to look back on what I have done and learn from it, especially
when I work with a coding agent.

It is a command-line tool. `devlog collect` gathers the week's events, `devlog draft` asks Claude
to summarise them into an entry, you edit the entry, and `devlog stats` and `devlog evaluate`
measure how good the draft was.

## A sample entry

From the draft of 2026-W46, a week spent on a public repo:

> **Threads**
>
> - **bake-off:** An eval harness landed for comparing the PydanticAI, LangGraph and Anthropic
>   tool-runner implementations on quality, safety, cost and latency under the same run limits,
>   with provenance-stamped results showing which runs compare fairly. […]
>
> **Decisions**
>
> - Bake-off telemetry first kept the run deadline in a pydantic PrivateAttr on RunStats. It was
>   moved to its own ContextVar beside the stats so RunStats stays plain data that loads back from
>   a results file unchanged, and so code running in a copied context can see both.
>   ([47f360f](https://github.com/TheCthulhuKid/bake-off/commit/47f360fb348b1650d99d8e175164eeee646fc061))

The whole week is in [`examples/`](examples/README.md): the draft, the edited entry, the entry
written by hand and the score sheet.

## How good the drafts are

These numbers come from four past weeks, 2026-W43 to 2026-W46. For each one I first wrote an
entry by hand, from memory (the gold entry). Then the week was drafted, the draft was edited, and
its decisions were marked against the gold entry.

### How much of a draft is kept?

The edit rate is the share of a draft's lines that did not survive editing.

| Week | Drafted | Removed | Added | Edit rate |
| --- | ---: | ---: | ---: | ---: |
| 2026-W43 | 3 | 1 | 8 | 33% |
| 2026-W44 | 17 | 4 | 4 | 24% |
| 2026-W45 | 12 | 1 | 6 | 8% |
| 2026-W46 | 6 | 1 | 2 | 17% |
| Together | 38 | 7 | 20 | 18% |

Few lines were removed, but 20 were added to the 38 drafted. The edit rate does not count added
lines, so on its own it flatters the drafts.

### Does the evidence exist?

The drafts cite 29 commits, and all 29 exist in the repos. Of these, 28 are on a remote branch
and one was never pushed, so its link is dead. Links to pull requests are not checked yet.

### Do the drafts find the decisions that mattered?

No.

| Week | Gold decisions | Matched | Missed | Drafted decisions | Wrong | True, but not in gold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-W43 | 3 | 0 | 3 | 0 | 0 | 0 |
| 2026-W44 | 3 | 0 | 3 | 6 | 0 | 6 |
| 2026-W45 | 3 | 0 | 3 | 4 | 0 | 4 |
| 2026-W46 | 2 | 0 | 2 | 4 | 0 | 4 |
| Together | 11 | 0 | 11 | 14 | 0 | 14 |

None of the 11 decisions in the gold entries is in a draft. The 14 decisions the drafts do hold
were each checked against the commit they cite and are true, so the drafts are accurate about the
wrong things. They record how something was built (a tarball instead of a zip, a `ContextVar` for
a deadline). The gold entries record why the work took a direction (a browser version because a
terminal is unfamiliar to players, a rewrite because the first version was not my own). A commit
shows the first and rarely the second. In 2026-W43, 28 commits in one repo became a single thread
that produced no decision at all.

The measurement has two limits. The gold entries are short, and I wrote them a month later, when
I could hardly recall the dead ends and lessons, so only decisions are scored. And four weeks of
one person's work are a small sample.

Improving this is the first item on the [roadmap](#roadmap).

## Install

devlog needs Python 3.14 or later, `git`, and the GitHub CLI (`gh`), logged in. `draft` also
needs an Anthropic API key in the `ANTHROPIC_API_KEY` environment variable; a busy week of about
240 commits costs a few dollars.

```sh
uv tool install git+https://github.com/TheCthulhuKid/devlog
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
devlog pick --week 2026-W47     # try the selection prompt on that week's claims
devlog pick --week 2026-W47 --again  # ask the pick afresh, to see how much it varies
devlog stats                    # how much of each week's draft you kept
devlog evaluate --week 2026-W45 # check a draft's commits and score it against your gold entry
```

### collect

`collect` reads your commits, your GitHub pull requests, issues, reviews and comments (through the `gh`
command, which must be logged in), your inbox and your note files, and writes them, oldest first, to
`.devlog/<week>/events.jsonl` in the journal folder. A week runs from Monday 00:00 to the next Monday
00:00 in your local timezone. If any source fails, nothing is written.

A note file that git tracks in one of your `repos` is collected from its commits: one event for each
commit of yours that changes it, holding the change. Collecting a past week again finds the same
notes, but an edit is not seen until it is committed. A note file git does not track is collected in
the week it last changed, with its current text; once it is edited again, collecting the earlier
week no longer finds it.

### draft

`draft` groups the week's events into threads of work, asks Claude to summarise each one, and writes the
entry twice in the journal folder: to `.devlog/<week>/draft.md`, which stays as generated, and to
`entries/<week>.md`, which is yours to edit. Running `draft` again replaces both, unless you have
edited the entry: then it stops before asking Claude anything, and `--overwrite` replaces your edits
with the new draft. It needs the week's `events.jsonl`, so run `collect` first, and an Anthropic API
key in the `ANTHROPIC_API_KEY` environment variable. Each thread is one paid API request, or a few
when the model reads a diff or a file. Four threads are summarised at a time, and a line such as
`12/54 threads summarised` is printed as each one finishes.

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
three files are rewritten on every run. A thread the model could not summarise is skipped and
listed there too, and the command then exits with status 1.

### sample and pick

`sample` is for trying a change to the summary prompt without paying for the whole week. Give it one
or more pieces of evidence copied from claims, such as a commit hash or part of a link, and it
summarises only the threads that hold them. It prints each thread's line and claims, the threads and
claims `draft` would have left out, and the tokens spent. It writes no draft and no entry. The
summaries it makes are saved with the week's others, so a later `draft` does not pay for them again.
Evidence that no thread holds is an error.

The model does not give the same answer twice, so one run says little about a wording. With
`--again`, `sample` asks every chosen thread afresh instead of reusing its saved summary, and saves
nothing: run it two or three times and compare what is printed. Each run is paid for in full.

`pick` tries the selection prompt on a week's claims: it prints the claims the pick keeps and
how many of each kind, and writes no draft. The threads' saved summaries are reused, so only the
pick is paid for. With `--again` the pick is asked afresh and its answer is not saved, so the same
prompt can be run several times.

### stats

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

### evaluate

`evaluate` compares a week's draft with the entry you wrote for it by hand in
`gold/<week>.md`. It looks up every commit the draft cites in your repos and reports the ones that
are missing or not pushed, and exits with status 1 if one is missing. It also writes
`.devlog/<week>/scores.md`: each gold decision with the drafted decisions that cite one of its
commits, then the drafted decisions that cite none. Write `matched` or `missed` in the brackets of a
gold decision, and `wrong` or `extra` for a drafted one, and run the command again to see the
counts. The sheet is never replaced; delete it to start again.

## Roadmap

Not built yet, in the order planned:

1. Improve from the evaluation. One round of changes aimed at the result above, so that a draft
   gives the reason for a direction and not only the mechanism.
2. Questions about the week. From the threads, the model proposes two or three short questions
   (reverts, abandoned branches and work with no stated reason come first), and the answers are
   cited like any other evidence. This is the likeliest source of the reasons a commit does not
   hold.
3. Search past entries. `devlog search "channels"` prints the matching passages with their week.
4. Carry open questions forward. A question under "What's open?" appears in the next draft until
   evidence resolves it.
5. A monthly roll-up of the themes and skills practised, each linked to its weekly entries.
6. A weekly schedule: one command for the last complete week, safe to run twice, run by a
   scheduler.

## Development

```sh
uv sync --locked --group dev
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy
```

To have git refuse a commit that fails the Ruff lint or format check, turn on the repo's hook once
per clone:

```sh
git config core.hooksPath .githooks
```

## Licence

[MIT](LICENSE)
