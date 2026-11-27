from datetime import date

from devlog.inbox import write_note

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
