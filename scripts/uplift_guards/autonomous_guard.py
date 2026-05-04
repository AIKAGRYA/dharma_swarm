"""Autonomous-build destruction guard.

Catches the M09 pattern: a non-human autonomous build ostensibly adding a
feature but actually deleting most of a file.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

AUTONOMOUS_BUILD_MARKER = "Autonomous build via"
STRUCTURAL_DELETE_TAG = "[structural-delete-approved]"
DEFAULT_DELETION_BUDGET = 500
DEFAULT_DESTRUCTION_RATIO = 0.50
DEFAULT_CUMULATIVE_BUDGET = 2000
DEFAULT_HUMAN_HARD_CAP = 3000


def _staged_diffstat(repo_root: Path) -> list[tuple[str, int, int]]:
    """Return [(path, additions, deletions), ...] for staged changes."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--numstat"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )
    if result.returncode != 0:
        return []
    rows: list[tuple[str, int, int]] = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        adds_s, dels_s, path = parts
        try:
            adds = int(adds_s)
            dels = int(dels_s)
        except ValueError:
            continue
        rows.append((path, adds, dels))
    return rows


def _read_commit_message(repo_root: Path, msg_file: str | None) -> str:
    if msg_file:
        return Path(msg_file).read_text(errors="replace")
    candidate = repo_root / ".git" / "COMMIT_EDITMSG"
    if candidate.exists():
        return candidate.read_text(errors="replace")
    return ""


def check_autonomous_destruction(
    repo_root: Path | None = None,
    *,
    commit_msg_file: str | None = None,
    deletion_budget: int = DEFAULT_DELETION_BUDGET,
    destruction_ratio: float = DEFAULT_DESTRUCTION_RATIO,
) -> tuple[bool, str]:
    """Refuse destructive autonomous commits without explicit approval."""
    repo_root = repo_root or Path.cwd()
    commit_msg = _read_commit_message(repo_root, commit_msg_file)

    if STRUCTURAL_DELETE_TAG in commit_msg:
        return True, "structural-delete-approved tag present - bypass"
    if os.environ.get("DHARMA_UPLIFT_BYPASS_DESTRUCTION", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return True, "DHARMA_UPLIFT_BYPASS_DESTRUCTION env override"

    is_autonomous = AUTONOMOUS_BUILD_MARKER in commit_msg
    diff = _staged_diffstat(repo_root)
    if not diff:
        return True, "no staged file changes"

    total_dels = sum(deletions for _, _, deletions in diff)
    total_adds = sum(additions for _, additions, _ in diff)

    if total_dels >= DEFAULT_CUMULATIVE_BUDGET:
        cum_ratio = total_dels / max(total_adds + total_dels, 1)
        return False, (
            "AUTONOMOUS-DESTRUCTION GUARD (cumulative) blocked the commit.\n"
            f"  Total staged deletions: {total_dels} lines across {len(diff)} files.\n"
            f"  Cumulative budget: {DEFAULT_CUMULATIVE_BUDGET}.\n"
            f"  Combined ratio: {cum_ratio:.0%}.\n"
            f"  Autonomous: {is_autonomous}.\n"
            f"  To override: add '{STRUCTURAL_DELETE_TAG}' to the commit message."
        )

    if not is_autonomous and total_dels >= DEFAULT_HUMAN_HARD_CAP:
        return False, (
            "AUTONOMOUS-DESTRUCTION GUARD (hard-cap) blocked the commit.\n"
            f"  Total staged deletions: {total_dels} lines.\n"
            f"  Hard cap for unmarked commits: {DEFAULT_HUMAN_HARD_CAP}.\n"
            f"  To override: add '{STRUCTURAL_DELETE_TAG}' to the commit message."
        )

    if not is_autonomous:
        big = [(path, adds, dels) for path, adds, dels in diff if dels > 1000]
        if big:
            preview = ", ".join(f"{path} (-{dels})" for path, _, dels in big[:3])
            return True, (
                f"WARN (human commit): large deletion in {preview}. "
                "Consider tagging [structural-delete-approved] or splitting."
            )
        return True, "human commit - destruction guard advisory only"

    offenders: list[str] = []
    for path, adds, dels in diff:
        if dels < 50:
            continue
        ratio = dels / max(adds + dels, 1)
        if dels >= deletion_budget or ratio >= destruction_ratio:
            offenders.append(f"{path}: +{adds} / -{dels} (ratio={ratio:.0%})")

    if offenders:
        return False, (
            "AUTONOMOUS-DESTRUCTION GUARD blocked the commit.\n"
            f"  Marker: '{AUTONOMOUS_BUILD_MARKER}' present in commit body.\n"
            f"  Budget: {deletion_budget} lines deleted OR ratio >= "
            f"{destruction_ratio:.0%}.\n"
            "  Offending files:\n    "
            + "\n    ".join(offenders)
            + f"\n  To override: add '{STRUCTURAL_DELETE_TAG}' to the commit message,\n"
            "    or set DHARMA_UPLIFT_BYPASS_DESTRUCTION=1."
        )

    return True, "autonomous commit within destruction budget"
