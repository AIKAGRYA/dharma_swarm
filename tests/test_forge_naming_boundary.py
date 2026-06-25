"""Guard the naming boundary between Dharma Forge and the anti-slop mechanism."""
from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_DOC = REPO_ROOT / "docs/governance/FORGE_NAMING_BOUNDARY.md"


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line.strip()]


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
    offenders: list[str] = []
    for path in _tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for term in legacy_terms:
            if term in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
                break

    assert offenders == []
