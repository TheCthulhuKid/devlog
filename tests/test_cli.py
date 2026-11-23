from datetime import date

from devlog.cli import main


def test_collect_defaults_to_last_week_of_the_configured_repos(tmp_path, capsys):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        f'github_user = "octocat"\njournal = "{tmp_path}"\nrepos = ["{tmp_path}"]\n'
    )

    main(["--config", str(config_file), "collect"], today=date(2026, 11, 23))

    assert capsys.readouterr().out == "2026-W47: 2026-11-16 to 2026-11-22, repos: 1\n"
