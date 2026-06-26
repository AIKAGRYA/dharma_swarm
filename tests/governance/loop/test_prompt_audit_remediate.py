"""Tests for scripts/governance/loop/prompt_audit_remediate.py — Stage 3 (Implementer).

Covers VAL-REMEDIATE-001..013:
  001  isolated worktree off base_ref
  002  write-set enforced (file outside warrant rejected)
  003  red-before required (non-zero exit on unfixed)
  004  green-after required (zero exit on fixed)
  005  proof_mode recorded (natural|synthetic|none)
  006  no proof routes to DEFER
  007  anti-gaming checklist on fix diff
  008  fix_proposal.yaml produced (§6.2 schema)
  009  user working tree never touched
  010  worktree creation failure aborts gracefully
  011  worktree cleaned up after stage
  012  anti-gaming violation REJECTS fix (non-zero exit, archived)
  013  checklist includes fix_addresses_root_cause
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = "/Users/dhyana/dharma_swarm/.venv/bin/python"
REMEDIATE_CLI = REPO_ROOT / "scripts" / "governance" "loop" / "prompt_audit_remediate.py"
REMEDIATE_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "prompt_audit_remediate.py"
RUNS_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "runs.py"

ALL_COUNCILS = [
    "testing_verification",
    "architecture_complexity",
    "runtime_distributed_reliability",
    "ai_slop_prompt_security",
    "governance_evidence_fitness",
]

USER_REPO = "/Users/dhyana/dharma_swarm"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _future_iso(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_warrant_dict(
    base_ref: str = "HEAD",
    write_set: list[str] | None = None,
    run_id: str = "warrant-remediate-test",
) -> dict:
    if write_set is None:
        write_set = ["scripts/governance/loop/**"]
    return {
        "id": run_id,
        "issued_by": "orchestrator",
        "authority_level": "medium",
        "trigger": "manual",
        "scope": {
            "base_ref": base_ref,
            "head_ref": "ratchet/loop-phases-1-3",
            "councils": list(ALL_COUNCILS),
            "prompt_ids": [],
        },
        "write_set": write_set,
        "budget": {"max_tokens": 100000, "max_wall_clock_min": 30, "max_fixes_per_run": 5},
        "merge_policy": "propose_only",
        "expires_at": _future_iso(),
    }


def _write_warrant(tmp_path: Path, warrant: dict | None = None) -> Path:
    w = warrant or _make_warrant_dict()
    p = tmp_path / "warrant.yaml"
    p.write_text(yaml.safe_dump(w, sort_keys=False))
    return p


def _make_finding(
    fid: str = "F-001",
    routing: str = "IMPLEMENT",
    evidence_level: str = "E2_tested",
    failure_class: str = "SLOP_MARKER_DRIFT",
    files: list[str] | None = None,
) -> dict:
    return {
        "finding_id": fid,
        "prompt_id": "TV-01",
        "council_id": "testing_verification",
        "title": "test finding",
        "severity": "medium",
        "evidence_level": evidence_level,
        "failure_class": failure_class,
        "routing": routing,
        "must_gate": False,
        "recurrence_score": 0,
        "recurrence_within_run": False,
        "files": files or [],
        "observed": "stub observation",
        "recommendation": "stub recommendation",
        "audit_path": "audit/TV-01.json",
    }


def _make_temp_repo(tmp_path: Path) -> Path:
    """Create a temp git repo with one commit so worktree creation works."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("# temp repo\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True, capture_output=True)
    return repo


def _setup_run_with_findings(
    tmp_path: Path,
    findings: list[dict],
    warrant: dict | None = None,
) -> tuple[Path, str, Path]:
    """Create a run dir with accepted_findings.jsonl. Returns (warrant_path, run_id, runs_root)."""
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    run_id = "remediate-test-001"
    w = warrant or _make_warrant_dict()
    warrant_path = tmp_path / "warrant.yaml"
    warrant_path.write_text(yaml.safe_dump(w, sort_keys=False))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    proc = subprocess.run(
        [VENV_PYTHON, str(RUNS_CLI), "create", "--run-id", run_id, "--warrant", str(warrant_path)],
        capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, f"runs create failed: {proc.stderr!r}"
    run_dir = Path(proc.stdout.strip())

    # Write accepted_findings.jsonl
    from scripts.governance.loop.runs import Run
    run = Run(run_dir)
    run.write_jsonl(run.accepted_findings_path(), findings)

    return warrant_path, run_id, runs_root


def _run_remediate_cli(
    warrant: Path,
    run_id: str,
    runs_root: Path,
    repo_root: Path,
    worktree_root: Path,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    env["LOOP_AGENT_BACKEND"] = "stub"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [
            VENV_PYTHON, str(REMEDIATE_CLI),
            "--warrant", str(warrant),
            "--run-id", run_id,
            "--repo-root", str(repo_root),
            "--worktree-root", str(worktree_root),
        ],
        capture_output=True, text=True, env=env,
    )


def _run_remediate_api(
    warrant_path: Path,
    run,
    implementer,
    repo_root: Path,
    worktree_root: Path,
) -> int:
    """Call run_remediate directly (for custom implementer tests)."""
    from scripts.governance.loop.prompt_audit_remediate import run_remediate
    return run_remediate(
        warrant_path=warrant_path,
        run=run,
        implementer=implementer,
        repo_root=repo_root,
        worktree_root=worktree_root,
    )


# ---------------------------------------------------------------------------
# VAL-REMEDIATE-001 + VAL-REMEDIATE-008 + VAL-REMEDIATE-011:
# Isolated worktree, fix_proposal produced, worktree cleaned up
# ---------------------------------------------------------------------------


def test_stub_produces_fix_proposal_and_cleans_up(tmp_path):
    """VAL-REMEDIATE-001/008/011: stub produces fix_proposal.yaml; worktree created and cleaned up."""
    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-STUB-001")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding])

    proc = _run_remediate_cli(warrant_path, run_id, runs_root, repo, wt_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    # fix_proposal written
    from scripts.governance.loop.runs import RunManager
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)
        fp_path = run.fix_proposal_path("F-STUB-001")
        assert fp_path.exists(), f"fix_proposal not written: {fp_path}"
        doc = yaml.safe_load(fp_path.read_text())
        # §6.2 schema fields
        fp = doc.get("fix_proposal", doc)
        assert fp["finding_id"] == "F-STUB-001"
        assert "write_set_used" in fp
        assert "patch_ref" in fp
        assert "red_before" in fp
        assert "green_after" in fp
        assert "proof_mode" in fp
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)

    # worktree cleaned up
    leftover = list(wt_root.glob("ds_loop_fix_*"))
    assert leftover == [], f"orphaned worktrees: {leftover}"


def test_worktree_is_isolated_path(tmp_path):
    """VAL-REMEDIATE-001: the fix worktree is at a /tmp-style path, not the user's tree."""
    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-ISO-001")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding])

    proc = _run_remediate_cli(warrant_path, run_id, runs_root, repo, wt_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    # The worktree root is under tmp_path (isolated), not USER_REPO
    assert str(wt_root) != USER_REPO
    assert str(wt_root).startswith(str(tmp_path))


# ---------------------------------------------------------------------------
# VAL-REMEDIATE-003 + VAL-REMEDIATE-004: red-before / green-after required
# ---------------------------------------------------------------------------


def test_red_before_nonzero_exit(tmp_path):
    """VAL-REMEDIATE-003: fix_proposal records red_before.exit_code != 0."""
    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-RED-001")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding])

    proc = _run_remediate_cli(warrant_path, run_id, runs_root, repo, wt_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    from scripts.governance.loop.runs import RunManager
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)
        doc = yaml.safe_load(run.fix_proposal_path("F-RED-001").read_text())
        fp = doc.get("fix_proposal", doc)
        assert fp["red_before"]["exit_code"] != 0, f"red_before must be non-zero: {fp['red_before']}"
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


def test_green_after_zero_exit(tmp_path):
    """VAL-REMEDIATE-004: fix_proposal records green_after.exit_code == 0."""
    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-GREEN-001")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding])

    proc = _run_remediate_cli(warrant_path, run_id, runs_root, repo, wt_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    from scripts.governance.loop.runs import RunManager
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)
        doc = yaml.safe_load(run.fix_proposal_path("F-GREEN-001").read_text())
        fp = doc.get("fix_proposal", doc)
        assert fp["green_after"]["exit_code"] == 0, f"green_after must be zero: {fp['green_after']}"
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


def test_no_red_before_rejects_fix(tmp_path):
    """VAL-REMEDIATE-003: if red-before is zero (no red), the fix is not accepted."""
    from scripts.governance.loop.prompt_audit_remediate import ImplementerBackend, ImplementerPlan
    from scripts.governance.loop.runs import RunManager

    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-NORED-001")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding])

    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)

        class NoRedImplementer(ImplementerBackend):
            def plan(self, finding, write_set):
                return ImplementerPlan(proof_mode="synthetic", gate_command=f'"{VENV_PYTHON}" -c "import sys; sys.exit(0)"')
            def setup_proof(self, worktree_path, finding):
                pass
            def apply_fix(self, worktree_path, finding):
                return []

        rc = _run_remediate_api(warrant_path, run, NoRedImplementer(), repo, wt_root)
        assert rc != 0, "no red-before (exit 0 on unfixed) should reject (non-zero exit)"
        # No fix_proposal written
        assert not run.fix_proposal_path("F-NORED-001").exists()
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


def test_no_green_after_rejects_fix(tmp_path):
    """VAL-REMEDIATE-004: if green-after is non-zero (no green), the fix is not accepted."""
    from scripts.governance.loop.prompt_audit_remediate import ImplementerBackend, ImplementerPlan
    from scripts.governance.loop.runs import RunManager

    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-NOGREEN-001")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding])

    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)

        class NoGreenImplementer(ImplementerBackend):
            def __init__(self):
                self._call = 0
            def plan(self, finding, write_set):
                return ImplementerPlan(proof_mode="synthetic", gate_command=f'"{VENV_PYTHON}" -c "import sys; sys.exit(1)"')
            def setup_proof(self, worktree_path, finding):
                pass
            def apply_fix(self, worktree_path, finding):
                return ["scripts/governance/loop/dummy.txt"]

        rc = _run_remediate_api(warrant_path, run, NoGreenImplementer(), repo, wt_root)
        assert rc != 0, "no green-after (non-zero on fixed) should reject"
        assert not run.fix_proposal_path("F-NOGREEN-001").exists()
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REMEDIATE-005: proof_mode recorded
# ---------------------------------------------------------------------------


def test_proof_mode_recorded(tmp_path):
    """VAL-REMEDIATE-005: fix_proposal records proof_mode as natural|synthetic|none."""
    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-PROOF-001")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding])

    proc = _run_remediate_cli(warrant_path, run_id, runs_root, repo, wt_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    from scripts.governance.loop.runs import RunManager
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)
        doc = yaml.safe_load(run.fix_proposal_path("F-PROOF-001").read_text())
        fp = doc.get("fix_proposal", doc)
        assert fp["proof_mode"] in ("natural", "synthetic", "none")
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REMEDIATE-006: no proof routes to DEFER
# ---------------------------------------------------------------------------


def test_proof_mode_none_routes_to_defer(tmp_path):
    """VAL-REMEDIATE-006: proof_mode=none routes to DEFER, not a fix."""
    from scripts.governance.loop.prompt_audit_remediate import ImplementerBackend, ImplementerPlan
    from scripts.governance.loop.runs import RunManager

    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-DEFER-001")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding])

    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)

        class NoneProofImplementer(ImplementerBackend):
            def plan(self, finding, write_set):
                return ImplementerPlan(proof_mode="none", gate_command="")
            def setup_proof(self, worktree_path, finding):
                pass
            def apply_fix(self, worktree_path, finding):
                return []

        rc = _run_remediate_api(warrant_path, run, NoneProofImplementer(), repo, wt_root)
        # DEFER is a clean exit (0) — the finding is tracked, not a failure
        assert rc == 0, f"proof_mode=none should route to DEFER cleanly, got exit {rc}"
        # No fix_proposal written
        assert not run.fix_proposal_path("F-DEFER-001").exists()
        # DEFER record should exist (check accepted_findings updated or a defer record)
        # The finding should be marked as DEFER in some artifact
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REMEDIATE-002: write-set enforced
# ---------------------------------------------------------------------------


def test_write_set_violation_rejected(tmp_path):
    """VAL-REMEDIATE-002: a fix touching a file outside the warrant write_set is rejected."""
    from scripts.governance.loop.prompt_audit_remediate import ImplementerBackend, ImplementerPlan
    from scripts.governance.loop.runs import RunManager

    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-WRITESET-001")
    warrant = _make_warrant_dict(write_set=["scripts/governance/loop/allowed/**"])
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding], warrant=warrant)

    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)

        class ViolatingImplementer(ImplementerBackend):
            def plan(self, finding, write_set):
                return ImplementerPlan(
                    proof_mode="synthetic",
                    gate_command=f'"{VENV_PYTHON}" -c "import sys; sys.exit(0 if True else 1)"',
                )
            def setup_proof(self, worktree_path, finding):
                pass
            def apply_fix(self, worktree_path, finding):
                # Write a file OUTSIDE the write_set
                target = worktree_path / "scripts" / "governance" / "loop" / "forbidden" / "fix.txt"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("fix content")
                return ["scripts/governance/loop/forbidden/fix.txt"]

        rc = _run_remediate_api(warrant_path, run, ViolatingImplementer(), repo, wt_root)
        assert rc != 0, "write-set violation should reject (non-zero exit)"
        assert not run.fix_proposal_path("F-WRITESET-001").exists()
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REMEDIATE-007 + VAL-REMEDIATE-012 + VAL-REMEDIATE-013:
# Anti-gaming checklist on fix diff; violation REJECTS; fix_addresses_root_cause
# ---------------------------------------------------------------------------


def test_anti_gaming_checklist_in_fix_proposal(tmp_path):
    """VAL-REMEDIATE-007: the fix_proposal includes the anti-gaming checklist results."""
    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-AG-001")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding])

    proc = _run_remediate_cli(warrant_path, run_id, runs_root, repo, wt_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    from scripts.governance.loop.runs import RunManager
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)
        doc = yaml.safe_load(run.fix_proposal_path("F-AG-001").read_text())
        fp = doc.get("fix_proposal", doc)
        assert "anti_gaming_checklist" in fp, f"missing anti_gaming_checklist in fix_proposal"
        checklist = fp["anti_gaming_checklist"]
        for item in ["no_new_skips", "no_new_xfails", "no_weakened_assertions",
                      "no_deleted_tests", "no_widened_budgets", "fix_addresses_root_cause"]:
            assert item in checklist, f"checklist missing {item}"
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


def test_fix_addresses_root_cause_in_checklist(tmp_path):
    """VAL-REMEDIATE-013: the remediate checklist includes fix_addresses_root_cause."""
    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-RC-001")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding])

    proc = _run_remediate_cli(warrant_path, run_id, runs_root, repo, wt_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    from scripts.governance.loop.runs import RunManager
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)
        doc = yaml.safe_load(run.fix_proposal_path("F-RC-001").read_text())
        fp = doc.get("fix_proposal", doc)
        assert "fix_addresses_root_cause" in fp["anti_gaming_checklist"]
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


def test_anti_gaming_violation_rejects_fix(tmp_path):
    """VAL-REMEDIATE-012: an anti-gaming checklist failure REJECTS the fix (non-zero exit)."""
    from scripts.governance.loop.prompt_audit_remediate import ImplementerBackend, ImplementerPlan
    from scripts.governance.loop.runs import RunManager

    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-AGFAIL-001")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding])

    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)

        class GamedImplementer(ImplementerBackend):
            def plan(self, finding, write_set):
                return ImplementerPlan(
                    proof_mode="synthetic",
                    gate_command=f'"{VENV_PYTHON}" -c "import sys; sys.exit(0)"',
                )
            def setup_proof(self, worktree_path, finding):
                pass
            def apply_fix(self, worktree_path, finding):
                # Introduce a skip — anti-gaming violation
                target = worktree_path / "scripts" / "governance" / "loop" / "fix_test.py"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('import pytest\ndef test_x():\n    pytest.skip("gamed")\n')
                return ["scripts/governance/loop/fix_test.py"]

        # Need a gate that is red before and green after.
        # Use a gate that checks for the file's existence (red before, green after).
        class GamedImplementer2(ImplementerBackend):
            def plan(self, finding, write_set):
                gate = f'"{VENV_PYTHON}" -c "from pathlib import Path; import sys; sys.exit(0 if Path(\\"scripts/governance/loop/fix_test.py\\").exists() else 1)"'
                return ImplementerPlan(proof_mode="synthetic", gate_command=gate)
            def setup_proof(self, worktree_path, finding):
                pass
            def apply_fix(self, worktree_path, finding):
                target = worktree_path / "scripts" / "governance" / "loop" / "fix_test.py"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('import pytest\ndef test_x():\n    pytest.skip("gamed")\n')
                return ["scripts/governance/loop/fix_test.py"]

        rc = _run_remediate_api(warrant_path, run, GamedImplementer2(), repo, wt_root)
        assert rc != 0, "anti-gaming violation should REJECT (non-zero exit)"
        assert not run.fix_proposal_path("F-AGFAIL-001").exists()
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-REMEDIATE-009: user working tree never touched
# ---------------------------------------------------------------------------


def test_user_working_tree_untouched(tmp_path):
    """VAL-REMEDIATE-009: the user's working tree at /Users/dhyana/dharma_swarm is not modified."""
    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-USERTREE-001")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding])

    before = subprocess.run(
        ["git", "-C", USER_REPO, "status", "--porcelain"],
        capture_output=True, text=True,
    )
    before_branch = subprocess.run(
        ["git", "-C", USER_REPO, "branch", "--show-current"],
        capture_output=True, text=True,
    )

    proc = _run_remediate_cli(warrant_path, run_id, runs_root, repo, wt_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    after = subprocess.run(
        ["git", "-C", USER_REPO, "status", "--porcelain"],
        capture_output=True, text=True,
    )
    after_branch = subprocess.run(
        ["git", "-C", USER_REPO, "branch", "--show-current"],
        capture_output=True, text=True,
    )

    assert before.stdout == after.stdout, "user working tree status changed!"
    assert before_branch.stdout == after_branch.stdout, "user working tree branch changed!"


# ---------------------------------------------------------------------------
# VAL-REMEDIATE-010: worktree creation failure aborts gracefully
# ---------------------------------------------------------------------------


def test_worktree_creation_failure_aborts(tmp_path):
    """VAL-REMEDIATE-010: invalid base_ref → worktree creation fails → non-zero exit, no fix_proposal."""
    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-WTFAIL-001")
    warrant = _make_warrant_dict(base_ref="nonexistent-ref-xyz")
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding], warrant=warrant)

    proc = _run_remediate_cli(warrant_path, run_id, runs_root, repo, wt_root)
    assert proc.returncode != 0, "invalid base_ref should cause non-zero exit"
    output = proc.stdout + proc.stderr
    assert "worktree" in output.lower() or "error" in output.lower()

    # No fix_proposal written
    from scripts.governance.loop.runs import RunManager
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)
        assert not run.fix_proposal_path("F-WTFAIL-001").exists()
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)

    # No orphaned worktrees
    leftover = list(wt_root.glob("ds_loop_fix_*"))
    assert leftover == [], f"orphaned worktrees after failure: {leftover}"


# ---------------------------------------------------------------------------
# VAL-REMEDIATE-011: worktree cleaned up after stage (even on rejection)
# ---------------------------------------------------------------------------


def test_worktree_cleaned_up_on_rejection(tmp_path):
    """VAL-REMEDIATE-011: worktree is cleaned up even when the fix is rejected."""
    from scripts.governance.loop.prompt_audit_remediate import ImplementerBackend, ImplementerPlan
    from scripts.governance.loop.runs import RunManager

    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-CLEANUP-001")
    warrant = _make_warrant_dict(write_set=["scripts/governance/loop/allowed/**"])
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding], warrant=warrant)

    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)

        class ViolatingImplementer(ImplementerBackend):
            def plan(self, finding, write_set):
                gate = f'"{VENV_PYTHON}" -c "from pathlib import Path; import sys; sys.exit(0 if Path(\\"scripts/governance/loop/forbidden/fix.txt\\").exists() else 1)"'
                return ImplementerPlan(proof_mode="synthetic", gate_command=gate)
            def setup_proof(self, worktree_path, finding):
                pass
            def apply_fix(self, worktree_path, finding):
                target = worktree_path / "scripts" / "governance" / "loop" / "forbidden" / "fix.txt"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("fix")
                return ["scripts/governance/loop/forbidden/fix.txt"]

        rc = _run_remediate_api(warrant_path, run, ViolatingImplementer(), repo, wt_root)
        assert rc != 0, "write-set violation should reject"
        # Worktree cleaned up even on rejection
        leftover = list(wt_root.glob("ds_loop_fix_*"))
        assert leftover == [], f"orphaned worktrees after rejection: {leftover}"
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# All-findings-deferred: no fix_proposal artifacts
# ---------------------------------------------------------------------------


def test_all_deferred_no_fix_proposals(tmp_path):
    """When all findings route to DEFER (proof_mode=none), no fix_proposal artifacts are produced."""
    from scripts.governance.loop.prompt_audit_remediate import ImplementerBackend, ImplementerPlan
    from scripts.governance.loop.runs import RunManager

    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    findings = [_make_finding(fid="F-ALLDEFER-1"), _make_finding(fid="F-ALLDEFER-2")]
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, findings)

    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        run = RunManager.open_run(run_id)

        class NoneProofImplementer(ImplementerBackend):
            def plan(self, finding, write_set):
                return ImplementerPlan(proof_mode="none", gate_command="")
            def setup_proof(self, worktree_path, finding):
                pass
            def apply_fix(self, worktree_path, finding):
                return []

        rc = _run_remediate_api(warrant_path, run, NoneProofImplementer(), repo, wt_root)
        assert rc == 0, f"all-deferred should exit 0, got {rc}"
        assert run.list_fix_proposals() == []
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# Warrant re-validation on stage entry
# ---------------------------------------------------------------------------


def test_expired_warrant_aborts_stage_entry(tmp_path):
    """An expired warrant is refused at remediate stage entry (exit 2)."""
    repo = _make_temp_repo(tmp_path)
    wt_root = tmp_path / "worktrees"
    wt_root.mkdir()
    finding = _make_finding(fid="F-EXPIRED-001")
    warrant = _make_warrant_dict()
    warrant["expires_at"] = "2020-01-01T00:00:00Z"
    warrant_path, run_id, runs_root = _setup_run_with_findings(tmp_path, [finding], warrant=warrant)

    proc = _run_remediate_cli(warrant_path, run_id, runs_root, repo, wt_root)
    assert proc.returncode != 0
    output = proc.stdout + proc.stderr
    assert "expired" in output.lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
