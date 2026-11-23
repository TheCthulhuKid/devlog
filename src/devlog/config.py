"""The user's configuration: which repos, notes and journal devlog works with."""

import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict

DEFAULT_CONFIG_PATH = Path("~/.config/devlog/config.toml")


def _existing_directory(path: Path) -> Path:
    if not path.is_dir():
        raise ValueError(f"{path} is not a directory")
    return path.resolve()


UserPath = Annotated[Path, AfterValidator(Path.expanduser)]
RepoPath = Annotated[UserPath, AfterValidator(_existing_directory)]


class Config(BaseModel):
    """Settings read from the config file. Paths may start with `~`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    github_user: str
    journal: UserPath
    repos: tuple[RepoPath, ...]
    notes_paths: tuple[UserPath, ...] = ()


def load_config(path: Path) -> Config:
    """Read and validate the TOML config file at `path`."""
    with path.expanduser().open("rb") as file:
        return Config.model_validate(tomllib.load(file))
