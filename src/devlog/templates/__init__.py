"""The entry template and the prompts, read from this package."""

from importlib.resources import files


def load(name: str) -> str:
    """Return the text of the template or prompt file `name`."""
    return (files(__package__) / name).read_text(encoding="utf-8")
