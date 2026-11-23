# Fixture weeks

Synthetic events in the shape `devlog collect` writes, for writing and testing `group_events`. Load one
with `read_events(Path("tests/fixtures/week_feature_branch.jsonl"))`. Names, repos and links are made up.

The threads listed are what the fixture was built to contain, not a required answer.

## week_feature_branch.jsonl (13 events, one repo)

| Thread | Events | Tied together by |
|--------|--------|------------------|
| Rate limiting | issue #14 opened and closed; four commits on `rate-limit`; the AGENTS.md change in one of them; PR #15 opened, commented on and merged | branch, `#14` in a commit and in the PR, `#15`, shared files |
| Deploy docs | one commit on `main` touching `README.md` | nothing shared with the rest |
| Redirect fix | one commit on `main` touching `redirect.py` | nothing shared with the rest |
| Inbox note | "Fixed window lets a burst through" | no repo; related to rate limiting only by its text |

Things to notice: the PR's opened and merged events carry its branch, but the issue events and the
comment on the PR carry none; the AGENTS.md change has the same link as its
commit; the PR was opened before the last commit on the branch was authored.

## week_two_repos.jsonl (11 events, three repos)

| Thread | Events | Tied together by |
|--------|--------|------------------|
| bakeoff evaluation | four commits on `main` that all touch `eval/runner.py`, one of them a revert | file overlap only |
| bakeoff docs | one commit touching `docs/datasets.md` | nothing shared with the rest |
| gm-helper undo | two commits touching `src/gm/undo.py`; issue #31; `(#31)` in the second commit's title | file overlap, issue reference |
| gm-helper initiative screen | one commit | same repo and branch as the undo work, no shared files |
| Review elsewhere | a review on `hello-world`, a repo with no commits | nothing shared with the rest |
| Inbox note | "Reranker helps recall but doubles latency" | no repo |

Things to notice: everything is on `main`, so branch alone would merge unrelated work; the issue was
opened after the first undo commit.
