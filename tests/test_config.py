import pytest
from pydantic import ValidationError

from devlog.config import load_config


def test_config_with_a_missing_repo_path_is_rejected(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        f'github_user = "octocat"\njournal = "{tmp_path}"\nrepos = ["{tmp_path}/missing"]\n'
    )

    with pytest.raises(ValidationError, match="missing is not a directory"):
        load_config(config_file)
