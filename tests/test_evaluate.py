from gitrepo import commit, git

from devlog.collectors.base import run_command
from devlog.evaluate import LinkStatus, check_links, score_sheet


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
