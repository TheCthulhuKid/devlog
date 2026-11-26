# A sample journal

`journal/` holds one real week, 2026-W46, as devlog left it in the journal folder. That week's
work was all in one public repo, [bake-off](https://github.com/TheCthulhuKid/bake-off), which
compares three agent frameworks on the same issue-triage task, so every link can be followed.

| File | What it is |
| --- | --- |
| `journal/.devlog/2026-W46/draft.md` | the entry as `devlog draft` wrote it, untouched |
| `journal/.devlog/2026-W46/threads.md` | the line of every thread the week's events were grouped into |
| `journal/entries/2026-W46.md` | the entry after editing: one decision cut, two added |
| `journal/gold/2026-W46.md` | the entry written by hand, from memory, before the draft was read |
| `journal/.devlog/2026-W46/scores.md` | the score sheet from `devlog evaluate`, with its marks |

The week's `events.jsonl` and the saved summaries are left out: they are the raw input and the
model's raw answers, and add nothing a reader can't see in the repo itself.

For this week `devlog stats` gives 6 lines drafted, 5 kept, 1 removed and 2 added, an edit rate
of 17%. `devlog evaluate` found all 9 cited commits on a remote branch; of the two decisions in
the gold entry the draft has neither, and its four own decisions are true but not in gold. The
gold entry's "Dead ends" and "Lessons learned" are empty.
