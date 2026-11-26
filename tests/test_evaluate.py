import pytest
from gitrepo import commit, git

from devlog.collectors.base import run_command
from devlog.evaluate import (
    LinkStatus,
    check_links,
    count_marks,
    evaluate_week,
    score_sheet,
)


def head(repo) -> str:
    return run_command(["git", "-C", str(repo), "rev-parse", "HEAD"]).strip()


def cited(repo, sha: str) -> str:
    link = f"https://github.com/octocat/{repo.name}/commit/{sha}"
    return f"- Chose a sliding window. ([{sha[:7]}]({link}))"


def test_link_to_a_missing_commit_is_reported_broken(repo):
    commit(repo, "Add rate limit", "limit.py")

    [checked] = check_links(cited(repo, "0" * 40), [repo], run_command)

    assert (checked.label, checked.status) == ("0000000", LinkStatus.BROKEN)


def test_a_commit_no_remote_holds_is_reported_not_pushed(repo):
    commit(repo, "Add rate limit", "limit.py")
    pushed = head(repo)
    git(repo, "update-ref", "refs/remotes/origin/main", pushed)
    commit(repo, "Tune the limit", "tune.py")
    entry = f"{cited(repo, pushed)}\n- Tuned it. (`{head(repo)[:7]}`)"

    statuses = [link.status for link in check_links(entry, [repo], run_command)]

    assert statuses == [LinkStatus.OK, LinkStatus.NOT_PUSHED]


def test_score_sheet_lists_gold_decisions_with_no_match():
    gold = (
        "## Decisions\n\n- Use a sliding window (abc1234, then 1234abc)\n- Drop Redis (def5678)\n"
    )
    chosen = "- Chose a sliding window. ([abc1234](https://github.com/octocat/api/commit/abc1234f))"
    generated = f"## Decisions\n\n{chosen}\n- Kept counts in memory. (`9999999`)\n"

    sheet = score_sheet(gold, generated)

    assert (
        "- [ ] Use a sliding window (abc1234, then 1234abc)\n"
        f"  - [ ] {chosen.removeprefix('- ')}\n"
        "- [ ] Drop Redis (def5678)\n"
        "  - no match\n"
    ) in sheet
    assert sheet.endswith(
        "## Generated decisions not in gold\n\n- [ ] Kept counts in memory. (`9999999`)\n"
    )


def test_marks_on_a_sheet_are_counted():
    sheet = (
        "## Gold decisions\n\n"
        "- [matched] Use a sliding window (abc1234)\n"
        "  - [ ] Chose a sliding window.\n"
        "  - [wrong] Chose Redis.\n"
        "- [ ] Drop Redis (def5678)\n"
        "  - no match\n\n"
        "## Generated decisions not in gold\n\n"
        "- [extra] Kept counts in memory.\n"
    )

    assert count_marks(sheet) == {"matched": 1, "wrong": 1, "unmarked": 1, "extra": 1}


def test_a_misspelt_mark_is_refused():
    with pytest.raises(ValueError, match="mised"):
        count_marks("- [mised] Drop Redis (def5678)\n")


def test_a_marked_sheet_is_not_replaced(tmp_path):
    week = tmp_path / ".devlog" / "2026-W45"
    week.mkdir(parents=True)
    (week / "draft.md").write_text("## Decisions\n\n- Chose a sliding window.\n")
    (tmp_path / "gold").mkdir()
    (tmp_path / "gold" / "2026-W45.md").write_text("## Decisions\n\n- Drop Redis (def5678)\n")

    sheet = evaluate_week("2026-W45", tmp_path, [], run_command).sheet
    sheet.write_text(sheet.read_text().replace("- [ ] Drop", "- [missed] Drop"))
    marks = evaluate_week("2026-W45", tmp_path, [], run_command).marks

    assert marks == {"missed": 1, "unmarked": 1}
