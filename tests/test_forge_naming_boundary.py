"""Guard the naming boundary between Dharma Forge and the anti-slop mechanism."""
from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_DOC = REPO_ROOT / "docs/governance/FORGE_NAMING_BOUNDARY.md"
HISTORICAL_PREFIXES = (
    "reports/governance/cleanup_convergence_20260615_25/",
    "reports/governance/metabolization_sweep_final_report_2026-07-01.md",
    "reports/governance/metabolization_sweep_ledger.jsonl",
    "reports/governance/worktree_readiness_2026-06-30/",
    # 2026-07-01 metabolization sweep artifacts landed on main documenting
    # the legacy name's own removal; dated historical reports, not live use.
    "reports/governance/metabolization_sweep_final_report_2026-07-01.md",
    "reports/governance/metabolization_sweep_ledger.jsonl",
)


def _git_grep_fixed(terms: tuple[str, ...]) -> list[str]:
    args = ["git", "grep", "-lF"]
    for term in terms:
        args.extend(["-e", term])
    args.append("--")
    result = subprocess.run(
        args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 1:
        return []
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip() or "git grep failed")
    return [line for line in result.stdout.splitlines() if line.strip()]


def test_forge_boundary_doc_names_both_surfaces() -> None:
    text = BOUNDARY_DOC.read_text(encoding="utf-8")
    assert "Dharma Forge" in text
    assert "Pudgala Autopoiesis Protostar" in text
    assert "Forge Swarm Evolution Arena" in text
    assert "graded claim/evidence binding" in text


def test_old_pudgala_quality_name_is_not_reintroduced() -> None:
    legacy_terms = (
        "Pudgala " + "Forge",
        "pudgala-" + "forge",
        "anti-slop-pudgala-" + "forge",
    )
    offenders = [
        path
        for path in _git_grep_fixed(legacy_terms)
        if not path.startswith(HISTORICAL_PREFIXES)
    ]

    assert offenders == []
