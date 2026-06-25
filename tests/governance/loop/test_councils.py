"""Tests for scripts/governance/loop/councils.py — council_id+prompt_id resolver.

Covers the resolver behavior: a known council_id + prompt_id resolves to the
correct ported PROMPTS.md path; an unknown council_id or prompt_id is rejected.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = "/Users/dhyana/dharma_swarm/.venv/bin/python"
COUNCILS_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "councils.py"

KNOWN = {
    "testing_verification": "01_testing_verification",
    "architecture_complexity": "02_architecture_complexity",
    "runtime_distributed_reliability": "03_runtime_distributed_reliability",
    "ai_slop_prompt_security": "04_ai_slop_prompt_security",
    "governance_evidence_fitness": "05_governance_evidence_fitness",
}

# A few known prompt_ids drawn from PROMPT_INDEX.md.
KNOWN_PROMPTS = {
    "testing_verification": ["TV-01", "TV-08"],
    "architecture_complexity": ["AC-01"],
    "runtime_distributed_reliability": ["RDR-10"],
    "ai_slop_prompt_security": ["APS-01", "APS-02"],
    "governance_evidence_fitness": ["GEF-02"],
}


# --- importable function ---


def test_resolve_known_council_and_prompt_returns_prompts_path():
    from scripts.governance.loop.councils import resolve_prompt_path

    path = resolve_prompt_path("testing_verification", "TV-01")
    assert path is not None
    assert path.name == "PROMPTS.md"
    assert path.parent.name == "01_testing_verification"
    assert path.exists()


@pytest.mark.parametrize("council_id,prompt_id", [
    (c, p) for c, prompts in KNOWN_PROMPTS.items() for p in prompts
])
def test_resolve_all_known_councils_and_prompts(council_id, prompt_id):
    from scripts.governance.loop.councils import resolve_prompt_path

    path = resolve_prompt_path(council_id, prompt_id)
    assert path is not None
    assert path.exists()
    assert path.parent.name == KNOWN[council_id]


def test_resolve_unknown_council_returns_none():
    from scripts.governance.loop.councils import resolve_prompt_path

    assert resolve_prompt_path("nope_council", "TV-01") is None


def test_resolve_unknown_prompt_in_known_council_returns_none():
    from scripts.governance.loop.councils import resolve_prompt_path

    # a prompt_id that does not appear in the council's PROMPTS.md
    assert resolve_prompt_path("testing_verification", "ZZ-99") is None


def test_council_dir_resolver():
    from scripts.governance.loop.councils import resolve_council_dir

    d = resolve_council_dir("governance_evidence_fitness")
    assert d is not None
    assert d.name == "05_governance_evidence_fitness"
    assert (d / "PROMPTS.md").exists()


def test_list_councils_covers_all_five():
    from scripts.governance.loop.councils import list_councils

    ids = list_councils()
    assert set(ids) == set(KNOWN)


# --- CLI ---


def test_cli_resolve_known_prints_path_exit_zero():
    proc = subprocess.run(
        [VENV_PYTHON, str(COUNCILS_CLI), "resolve", "testing_verification", "TV-01"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert "PROMPTS.md" in proc.stdout
    assert "01_testing_verification" in proc.stdout


def test_cli_resolve_unknown_council_exits_two():
    proc = subprocess.run(
        [VENV_PYTHON, str(COUNCILS_CLI), "resolve", "nope_council", "TV-01"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 2


def test_cli_list_councils_exit_zero():
    proc = subprocess.run(
        [VENV_PYTHON, str(COUNCILS_CLI), "list"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    for cid in KNOWN:
        assert cid in proc.stdout


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
