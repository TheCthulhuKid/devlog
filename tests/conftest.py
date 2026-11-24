import pytest
from gitrepo import git


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "octocat@example.com")
    git(tmp_path, "config", "user.name", "Octo Cat")
    return tmp_path
