"""Tests for scripts/governance/loop/scoper.py — deterministic git-diff to prompts.

Covers VAL-SCOPE-001..006:
  001  sentinels always selected (regardless of diff)
  002  changed files mapped to relevant diff-mapped prompts + rationale
  003  diff-mapped prompts capped at 3-5 (sentinels additional)
  004  deterministic: same diff -> identical scope.json
  005  empty diff selects only the 6 sentinels (0 diff-mapped), exit 0
  006  scope filtered by warrant.scope.councils[] (no out-of-scope councils)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = "/Users/dhyana/dharma_swarm/.venv/bin/python"
SCOPER_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "scoper.py"

SENTINELS = ["TV-01", "TV-08", "APS-01", "APS-02", "RDR-10", "GEF-02"]

# A warrant that authorizes all five councils (so sentinels are never filtered).
ALL_COUNCILS = [
    "testing_verification",
    "architecture_complexity",
    "runtime_distributed_reliability",
    "ai_slop_prompt_security",
    "governance_evidence_fitness",
]

VALID_WARRANT: dict = {
    "id": "warrant-scoper-test",
    "issued_by": "orchestrator",
    "authority_level": "medium",
    "trigger": "manual",
    "scope": {
        "base_ref": "origin/main",
        "head_ref": "ratchet/loop-phases-1-3",
        "councils": list(ALL_COUNCILS),
        "prompt_ids": [],
    },
    "write_set": ["scripts/governance/loop/scoper.py"],
    "budget": {"max_tokens": 100000, "max_wall_clock_min": 30, "max_fixes_per_run": 5},
    "merge_policy": "propose_only",
    "expires_at": "2099-01-01T00:00:00Z",
}


def _write_warrant(tmp_path: Path, doc: dict, name: str = "warrant.yaml") -> Path:
    p = tmp_path / name
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    return p


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [VENV_PYTHON, str(SCOPER_CLI), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
    )


# ---------------------------------------------------------------------------
# Unit tests (import the module directly)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def scoper():
    sys.path.insert(0, str(REPO_ROOT))
    import importlib

    mod = importlib.import_module("scripts.governance.loop.scoper")
    importlib.reload(mod)
    return mod


def test_sentinels_always_selected_with_diff(scoper):
    """VAL-SCOPE-001: all 6 sentinels present regardless of diff."""
    scope = scoper.select_prompts(
        changed_files=["dharma_swarm/providers.py"],
        warrant_councils=list(ALL_COUNCILS),
    )
    for sid in SENTINELS:
        assert sid in scope["selected_prompt_ids"], f"sentinel {sid} missing"
    assert set(SENTINELS).issubset(set(scope["sentinel_prompt_ids"]))


def test_sentinels_always_selected_empty_diff(scoper):
    """VAL-SCOPE-001: sentinels present even with empty diff."""
    scope = scoper.select_prompts(
        changed_files=[],
        warrant_councils=list(ALL_COUNCILS),
    )
    for sid in SENTINELS:
        assert sid in scope["selected_prompt_ids"], f"sentinel {sid} missing"


def test_changed_files_mapped_to_relevant_prompts(scoper):
    """VAL-SCOPE-002: changed files map to relevant diff-mapped prompts + rationale."""
    scope = scoper.select_prompts(
        changed_files=["dharma_swarm/providers.py", "tests/test_providers.py"],
        warrant_councils=list(ALL_COUNCILS),
    )
    diff_mapped = scope["diff_mapped_prompt_ids"]
    # providers.py + tests should map to *some* diff-mapped prompts
    assert len(diff_mapped) > 0, "expected non-empty diff-mapped prompts"
    # rationale present and references the changed files
    rationale_files = {entry["file"] for entry in scope["rationale"]}
    assert "dharma_swarm/providers.py" in rationale_files
    assert "tests/test_providers.py" in rationale_files
    # each rationale entry lists prompt_ids
    for entry in scope["rationale"]:
        assert isinstance(entry["prompt_ids"], list)


def test_diff_mapped_prompt_cap(scoper):
    """VAL-SCOPE-003: diff-mapped prompts capped at 5 (sentinels additional)."""
    # A broad diff touching many areas to generate many candidate prompts.
    broad_diff = [
        "dharma_swarm/providers.py",
        "dharma_swarm/a2a/a2a_bridge.py",
        "dharma_swarm/orchestrator.py",
        "dharma_swarm/evolution.py",
        "dharma_swarm/memory_kernel/kernel.py",
        "dharma_swarm/telos_gates.py",
        "dharma_swarm/handoff.py",
        "dharma_swarm/vsm_channels.py",
        "dharma_swarm/stigmergy.py",
        "tests/test_cascade.py",
        "scripts/governance/check_import_provenance.py",
        ".github/workflows/ci.yml",
        "docs/governance/ACTIVE_TRACK.yaml",
        "pyproject.toml",
    ]
    scope = scoper.select_prompts(
        changed_files=broad_diff,
        warrant_councils=list(ALL_COUNCILS),
    )
    diff_mapped = scope["diff_mapped_prompt_ids"]
    assert len(diff_mapped) <= 5, f"diff-mapped cap exceeded: {diff_mapped}"
    # sentinels are additional (not counted in the cap)
    selected = scope["selected_prompt_ids"]
    for sid in SENTINELS:
        assert sid in selected


def test_deterministic_output_same_input(scoper):
    """VAL-SCOPE-004: same changed_files -> identical scope.json."""
    diff = ["dharma_swarm/providers.py", "dharma_swarm/a2a/a2a_bridge.py"]
    s1 = scoper.select_prompts(changed_files=list(diff), warrant_councils=list(ALL_COUNCILS))
    s2 = scoper.select_prompts(changed_files=list(diff), warrant_councils=list(ALL_COUNCILS))
    # Order of changed_files input should not matter for the selected set.
    s3 = scoper.select_prompts(
        changed_files=list(reversed(diff)), warrant_councils=list(ALL_COUNCILS)
    )
    assert json.dumps(s1, sort_keys=True) == json.dumps(s2, sort_keys=True)
    assert json.dumps(s1, sort_keys=True) == json.dumps(s3, sort_keys=True)


def test_empty_diff_selects_only_sentinels(scoper):
    """VAL-SCOPE-005: empty diff -> only 6 sentinels, 0 diff-mapped."""
    scope = scoper.select_prompts(
        changed_files=[],
        warrant_councils=list(ALL_COUNCILS),
    )
    assert scope["diff_mapped_prompt_ids"] == []
    assert set(scope["selected_prompt_ids"]) == set(SENTINELS)
    assert len(scope["selected_prompt_ids"]) == 6


def test_scope_filtered_by_warrant_councils(scoper):
    """VAL-SCOPE-006: no prompts from councils outside the warrant scope."""
    # Warrant allows only testing_verification + architecture_complexity.
    restricted = ["testing_verification", "architecture_complexity"]
    # Diff touches files that would map to RDR (runtime) and APS (slop) prompts.
    diff = ["dharma_swarm/providers.py", "dharma_swarm/a2a/a2a_bridge.py"]
    scope = scoper.select_prompts(
        changed_files=diff,
        warrant_councils=restricted,
    )
    # Every selected prompt must belong to an allowed council.
    for pid in scope["selected_prompt_ids"]:
        council = scoper.prompt_to_council(pid)
        assert council in restricted, f"prompt {pid} (council {council}) outside warrant scope"


def test_sentinels_filtered_when_council_excluded(scoper):
    """VAL-SCOPE-006 (edge): a sentinel whose council is excluded is filtered out.

    The warrant council filter applies to sentinels too — no prompt outside the
    warrant's council scope is selected, even a sentinel.
    """
    # Only testing_verification -> sentinels TV-01/TV-08 kept; APS/RDR/GEF dropped.
    scope = scoper.select_prompts(
        changed_files=[],
        warrant_councils=["testing_verification"],
    )
    assert "TV-01" in scope["selected_prompt_ids"]
    assert "TV-08" in scope["selected_prompt_ids"]
    for excluded in ["APS-01", "APS-02", "RDR-10", "GEF-02"]:
        assert excluded not in scope["selected_prompt_ids"]


def test_council_paths_resolved(scoper):
    """scope.json includes council_paths mapping prompt_id -> PROMPTS.md path."""
    scope = scoper.select_prompts(
        changed_files=[],
        warrant_councils=list(ALL_COUNCILS),
    )
    paths = scope["council_paths"]
    for sid in SENTINELS:
        assert sid in paths, f"sentinel {sid} missing council path"
        p = Path(paths[sid])
        assert p.name == "PROMPTS.md"
        assert p.exists(), f"council path does not exist: {p}"


def test_changed_files_recorded(scoper):
    """scope.json records the changed_files list."""
    diff = ["dharma_swarm/providers.py", "tests/test_providers.py"]
    scope = scoper.select_prompts(
        changed_files=diff,
        warrant_councils=list(ALL_COUNCILS),
    )
    assert set(scope["changed_files"]) == set(diff)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_cli_help_exits_zero():
    res = _run_cli(["--help"])
    assert res.returncode == 0
    assert "usage" in res.stdout.lower()


def test_cli_writes_scope_json(tmp_path):
    """CLI: --warrant + --output writes a valid scope.json (exit 0)."""
    warrant = _write_warrant(tmp_path, VALID_WARRANT)
    out = tmp_path / "scope.json"
    res = _run_cli([
        "--warrant", str(warrant),
        "--output", str(out),
        "--changed-files", "dharma_swarm/providers.py", "tests/test_providers.py",
    ])
    assert res.returncode == 0, f"stderr: {res.stderr}"
    assert out.is_file()
    data = json.loads(out.read_text())
    for sid in SENTINELS:
        assert sid in data["selected_prompt_ids"]
    assert len(data["diff_mapped_prompt_ids"]) > 0


def test_cli_empty_diff_sentinels_only(tmp_path):
    """CLI: empty diff -> only sentinels, exit 0 (VAL-SCOPE-005)."""
    warrant = _write_warrant(tmp_path, VALID_WARRANT)
    out = tmp_path / "scope.json"
    res = _run_cli([
        "--warrant", str(warrant),
        "--output", str(out),
        "--changed-files",
    ])
    assert res.returncode == 0, f"stderr: {res.stderr}"
    data = json.loads(out.read_text())
    assert data["diff_mapped_prompt_ids"] == []
    assert set(data["selected_prompt_ids"]) == set(SENTINELS)


def test_cli_deterministic_two_runs(tmp_path):
    """CLI: two runs with same input produce identical scope.json (VAL-SCOPE-004)."""
    warrant = _write_warrant(tmp_path, VALID_WARRANT)
    out1 = tmp_path / "scope_a.json"
    out2 = tmp_path / "scope_b.json"
    args = [
        "--warrant", str(warrant),
        "--changed-files", "dharma_swarm/providers.py", "dharma_swarm/a2a/a2a_bridge.py",
    ]
    res1 = _run_cli([*args, "--output", str(out1)])
    res2 = _run_cli([*args, "--output", str(out2)])
    assert res1.returncode == 0
    assert res2.returncode == 0
    assert out1.read_text() == out2.read_text()
