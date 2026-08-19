"""Terminal-friendly changelog output."""

from pathlib import Path


CHANGELOG_PATH = Path(__file__).resolve().parents[2] / "CHANGELOG.md"


def print_changelog() -> None:
    try:
        print(CHANGELOG_PATH.read_text(encoding="utf-8"))
    except OSError as error:
        print(f"Unable to read changelog: {error}")
