"""Autonomous-build destruction guard.

Catches the M09 pattern (commit d7af817): a free-model autonomous build
ostensibly adding a feature but actually deleting most of a file. The
specific signature is the commit body containing "Autonomous build via"
plus a net-negative line delta on a non-trivial file.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Iterable

# Commit body marker injected by the dgc autonomous-build pipeline.
AUTONOMOUS_BUILD_MARKER = "Autonomous build via"

# Tag that lets a human explicitly authorize a structural delete by an agent.
STRUCTURAL_DELETE_TAG = "[structural-delete-approved]"

# Anything deleting more than this many lines is suspect when the author
# is non-human. Tuned to allow normal refactors while catching M09-class
# damage (which deleted 6602 lines in one commit).
DEFAULT_DELETION_BUDGET = 500

# Per-file ratio: deletes/(adds+deletes) above which we refuse autonomous
# commits unless explicitly tagged. d7af817 was ~99% (73 added, 6602 deleted).
DEFAULT_DESTRUCTION_RATIO = 0.50

# Cumulative deletion budget across ALL staged files. Defeats the shard-the-
# deletion-across-many-files bypass (49 lines × 140 files) that per-file
# thresholds miss. Tuned below the d7af817 total (6602) so M09-magnitude
# damage trips even if sharded.
DEFAULT_CUMULATIVE_BUDGET = 2000

# Absolute-delete floor for any commit (human or autonomous) when NOT marked
# with [structural-delete-approved]. Catches the case where an adversary
# omits the "Autonomous build via" marker to evade the autonomous-strict path.
# Tuned higher than normal refactor deletes but lower than d7af817 damage.
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
            # Binary diffs show "-\t-\t<path>"
            continue
        rows.append((path, adds, dels))
    return rows


def _read_commit_message(repo_root: Path, msg_file: str | None) -> str:
    """Read the prepared commit message (from commit-msg hook or COMMIT_EDITMSG)."""
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
    """Return (ok, message). Refuses autonomous commits that exceed the
    destruction budget without explicit approval.
    """
    repo_root = repo_root or Path.cwd()
    commit_msg = _read_commit_message(repo_root, commit_msg_file)

    # Override paths for legitimate structural work.
    if STRUCTURAL_DELETE_TAG in commit_msg:
        return True, "structural-delete-approved tag present — bypass"
    if os.environ.get("DHARMA_UPLIFT_BYPASS_DESTRUCTION", "").strip().lower() in {"1", "true", "yes"}:
        return True, "DHARMA_UPLIFT_BYPASS_DESTRUCTION env override"

    is_autonomous = AUTONOMOUS_BUILD_MARKER in commit_msg
    diff = _staged_diffstat(repo_root)

    if not diff:
        return True, "no staged file changes"

    total_dels = sum(d for _, _, d in diff)
    total_adds = sum(a for _, a, _ in diff)

    # RED-TEAM HARDENING (Strategy 2 - shard-deletion): cumulative-across-diff
    # accounting. Any commit (autonomous or human) with combined deletions
    # above the cumulative budget requires explicit [structural-delete-approved].
    if total_dels >= DEFAULT_CUMULATIVE_BUDGET:
        cum_ratio = total_dels / max(total_adds + total_dels, 1)
        return False, (
            "AUTONOMOUS-DESTRUCTION GUARD (cumulative) blocked the commit.\n"
            f"  Total staged deletions: {total_dels} lines across {len(diff)} files.\n"
            f"  Cumulative budget: {DEFAULT_CUMULATIVE_BUDGET}.\n"
            f"  Combined ratio: {cum_ratio:.0%}.\n"
            f"  Autonomous: {is_autonomous}.\n"
            f"  To override: add '{STRUCTURAL_DELETE_TAG}' to the commit message.\n"
            "  Background: this check defeats the shard-deletion bypass where an\n"
            "    agent deletes 49 lines × 140 files to stay under per-file limits."
        )

    # RED-TEAM HARDENING (Strategy 1 - omit marker): absolute hard cap catches
    # suspicious commits that LACK the autonomous marker to evade strict mode.
    if not is_autonomous and total_dels >= DEFAULT_HUMAN_HARD_CAP:
        return False, (
            "AUTONOMOUS-DESTRUCTION GUARD (hard-cap) blocked the commit.\n"
            f"  Total staged deletions: {total_dels} lines.\n"
            f"  Hard cap for unmarked commits: {DEFAULT_HUMAN_HARD_CAP}.\n"
            f"  To override: add '{STRUCTURAL_DELETE_TAG}' to the commit message.\n"
            "  Background: this check catches adversarial commits that omit\n"
            "    the 'Autonomous build via' marker to evade the strict path."
        )

    if not is_autonomous:
        big = [(p, a, d) for p, a, d in diff if d > 1000]
        if big:
            preview = ", ".join(f"{p} (-{d})" for p, _, d in big[:3])
            return True, (
                f"WARN (human commit): large deletion in {preview}. "
                "Consider tagging [structural-delete-approved] or splitting."
            )
        return True, "human commit — destruction guard advisory only"

    # Autonomous path — strict.
    offenders: list[str] = []
    for path, adds, dels in diff:
        if dels < 50:
            continue
        ratio = dels / max(adds + dels, 1)
        if dels >= deletion_budget or ratio >= destruction_ratio:
            offenders.append(
                f"{path}: +{adds} / -{dels} (ratio={ratio:.0%})"
            )

    if offenders:
        msg = (
            "AUTONOMOUS-DESTRUCTION GUARD blocked the commit.\n"
            f"  Marker: '{AUTONOMOUS_BUILD_MARKER}' present in commit body.\n"
            f"  Budget: {deletion_budget} lines deleted OR ratio >= {destruction_ratio:.0%}.\n"
            "  Offending files:\n    " + "\n    ".join(offenders)
            + f"\n  To override: add '{STRUCTURAL_DELETE_TAG}' to the commit message,\n"
            "    or set DHARMA_UPLIFT_BYPASS_DESTRUCTION=1.\n"
            "  Background: commit d7af817 (M09) deleted 6602 lines from dgc_cli.py\n"
            "    via gpt-oss-120b:free. This guard exists to catch that class of damage."
        )
        return False, msg

    return True, "autonomous commit within destruction budget"
