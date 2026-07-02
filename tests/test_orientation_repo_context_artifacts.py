from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ORIENTATION_REPORTS = (
    REPO_ROOT / "reports/orientation/repo_context.md",
    REPO_ROOT / "reports/orientation/repo_context.json",
)
MACHINE_PATH_MARKERS = ("/Users/dhyana", "/private/tmp")


def test_repo_context_artifacts_do_not_commit_machine_paths() -> None:
    for path in ORIENTATION_REPORTS:
        text = path.read_text(encoding="utf-8")
        for marker in MACHINE_PATH_MARKERS:
            assert marker not in text, f"{path.relative_to(REPO_ROOT)} contains {marker}"
