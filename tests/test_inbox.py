from datetime import date

import pytest

from devlog.inbox import note_repo, write_note

TODAY = date(2026, 11, 27)


def test_a_note_is_added_under_todays_heading(tmp_path):
    inbox = tmp_path / "inbox.md"
    inbox.write_text("## 2026-11-26\n- typed by hand, no newline at the end")

    write_note(inbox, "chose FTS5 over embeddings", TODAY)

    assert inbox.read_text() == (
        "## 2026-11-26\n- typed by hand, no newline at the end\n\n"
        "## 2026-11-27\n- chose FTS5 over embeddings\n"
    )


def test_a_second_note_the_same_day_shares_the_heading(tmp_path):
    inbox = tmp_path / "inbox.md"

    write_note(inbox, "first", TODAY)
    write_note(inbox, "second", TODAY)

    assert inbox.read_text() == "## 2026-11-27\n- first\n- second\n"


def test_a_note_names_its_repo(tmp_path):
    inbox = tmp_path / "inbox.md"

    write_note(inbox, "chose FTS5 over embeddings", TODAY, repo="devlog")

    assert inbox.read_text() == "## 2026-11-27\n- [devlog] chose FTS5 over embeddings\n"


def test_a_note_of_several_lines_stays_one_note(tmp_path):
    inbox = tmp_path / "inbox.md"

    write_note(inbox, "chose FTS5\n\nkeyword search is enough\n", TODAY)

    assert inbox.read_text() == "## 2026-11-27\n- chose FTS5\n  keyword search is enough\n"


def test_a_note_belongs_to_the_repo_of_the_folder_it_is_written_in(tmp_path):
    repos = [tmp_path / "devlog", tmp_path / "bake-off"]

    assert note_repo(repos, tmp_path / "bake-off" / "src") == tmp_path / "bake-off"
    assert note_repo(repos, tmp_path) is None


def test_a_repo_that_is_not_configured_is_refused(tmp_path):
    with pytest.raises(ValueError, match="devlgo is not one of your repos"):
        note_repo([tmp_path / "devlog"], tmp_path, given="devlgo")
