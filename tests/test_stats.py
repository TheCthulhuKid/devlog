import json

from devlog.stats import compare_entries, journal_stats, total

DRAFT = """# Week 2026-W47

## Decisions

- Redirects are rate limited per API key. (`0101010`)
- Limits are stored in Redis. (`0202020`)

## Lessons learned

- A fixed window lets a client burst at its edge. (`0303030`)

## Notes

"""


def test_untouched_draft_has_zero_edit_rate():
    edits = compare_entries(DRAFT, DRAFT)

    assert total(edits).edit_rate == 0
    assert total(edits).added == 0


def test_rewritten_section_shows_in_that_sections_rate():
    final = DRAFT.replace("Limits are stored in Redis.", "Limits live in Redis, not Postgres.")

    decisions, lessons, notes = compare_entries(DRAFT, final)

    assert (decisions.edit_rate, decisions.removed, decisions.added) == (0.5, 1, 1)
    assert lessons.edit_rate == 0
    assert notes.edit_rate is None


def test_a_second_stats_run_keeps_one_row_per_week(tmp_path):
    (tmp_path / ".devlog" / "2026-W47").mkdir(parents=True)
    (tmp_path / ".devlog" / "2026-W47" / "draft.md").write_text(DRAFT, encoding="utf-8")
    (tmp_path / "entries").mkdir()
    (tmp_path / "entries" / "2026-W47.md").write_text(DRAFT, encoding="utf-8")

    journal_stats(tmp_path)
    journal_stats(tmp_path)

    metrics = (tmp_path / ".devlog" / "metrics.jsonl").read_text(encoding="utf-8")
    (row,) = [json.loads(line) for line in metrics.splitlines()]
    assert (row["week"], row["drafted"], row["edit_rate"]) == ("2026-W47", 3, 0)
