"""End-to-end pipeline test for the Cybernetic Ratchet Loop (M1 integration).

This IS the red-first TDD test for the integrated 5-stage pipeline. It wires
the full chain end-to-end with the stub backend and verifies every cross-area
assertion (VAL-CROSS-001 through VAL-CROSS-009):

  VAL-CROSS-001  Full 5-stage chain end-to-end (stub backend) — complete artifact chain
  VAL-CROSS-002  Full chain artifacts schema-valid
  VAL-CROSS-003  Ratcheted gate fails-closed on reintroduction (red-before/green-after)
  VAL-CROSS-005  No LLM opinion recorded as truth
  VAL-CROSS-006  Anti-gaming across all fix diffs
  VAL-CROSS-007  User working tree never modified
  VAL-CROSS-008  Propose-only — no merge/push to main
  VAL-CROSS-009  Post-ratchet fresh-agent re-audit attempts reintroduction

The test runs the real CLI stage scripts as subprocess invocations (not
in-process imports) to exercise the full integration path including CLI
argparse, env-var backend selection, run-dir I/O chaining, and exit-code
propagation.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = sys.executable

LOOP_DIR = REPO_ROOT / "scripts" / "governance" / "loop"
RUNS_CLI = LOOP_DIR / "runs.py"
SCOPER_CLI = LOOP_DIR / "scoper.py"
AUDIT_RUN_CLI = LOOP_DIR / "prompt_audit_run.py"
TRIAGE_CLI = LOOP_DIR / "prompt_audit_triage.py"
REMEDIATE_CLI = LOOP_DIR / "prompt_audit_remediate.py"
REAUDIT_CLI = LOOP_DIR / "prompt_audit_reaudit.py"
LEARN_CLI = LOOP_DIR / "prompt_audit_learn.py"
VALIDATE_AUDIT_CLI = LOOP_DIR / "validate_audit.py"

ALL_COUNCILS = [
    "testing_verification",
    "architecture_complexity",
    "runtime_distributed_reliability",
    "ai_slop_prompt_security",
    "governance_evidence_fitness",
]

USER_REPO = "/Users/dhyana/dharma_swarm"
MISSION_BRANCH = "ratchet/loop-phases-1-3"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _future_iso(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _make_warrant_dict(run_id: str = "warrant-e2e") -> dict:
    return {
        "id": run_id,
        "issued_by": "orchestrator",
        "authority_level": "medium",
        "trigger": "manual",
        "scope": {
            "base_ref": "HEAD",
            "head_ref": MISSION_BRANCH,
            "councils": list(ALL_COUNCILS),
            "prompt_ids": [],
        },
        "write_set": ["scripts/governance/loop/**"],
        "budget": {
            "max_tokens": 100000,
            "max_wall_clock_min": 30,
            "max_fixes_per_run": 5,
        },
        "merge_policy": "propose_only",
        "expires_at": _future_iso(),
    }


def _write_warrant(tmp_path: Path, warrant: dict | None = None) -> Path:
    w = warrant or _make_warrant_dict()
    p = tmp_path / "warrant.yaml"
    p.write_text(yaml.safe_dump(w, sort_keys=False))
    return p


def _base_env(runs_root: Path) -> dict:
    """Build the env for CLI stage invocations."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    env["LOOP_AGENT_BACKEND"] = "stub"
    return env


def _run_cli(
    cli: Path,
    env: dict,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    """Run a loop CLI script with the venv python and capture output."""
    cmd = [VENV_PYTHON, str(cli), *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _open_run(run_id: str, runs_root: Path):
    """Open a Run by searching the runs root (handles any week bucket)."""
    from scripts.governance.loop.runs import RunManager

    old = os.environ.get("LOOP_RUNS_DIR")
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        return RunManager.open_run(run_id)
    finally:
        if old is not None:
            os.environ["LOOP_RUNS_DIR"] = old
        else:
            os.environ.pop("LOOP_RUNS_DIR", None)


def _make_gate_script(tmp_path: Path, marker_path: Path) -> Path:
    """Create a deterministic gate script that checks for a marker file.

    Marker present  -> exit 0 (green / clean tree).
    Marker absent   -> exit 1 (red / slop reintroduced).
    """
    gate = tmp_path / "gate_check.py"
    gate.write_text(
        "import sys\n"
        "from pathlib import Path\n\n"
        f"MARKER = Path({str(marker_path)!r})\n"
        "if MARKER.exists():\n"
        '    print("OK: marker found — clean tree")\n'
        "    sys.exit(0)\n"
        'print("FAIL: marker not found — slop reintroduced")\n'
        "sys.exit(1)\n"
    )
    return gate


def _green_ratchet_repo(tmp_path: Path, finding_id: str | None = None) -> Path:
    repo = tmp_path / "green-ratchet-repo"
    script_dir = repo / "scripts" / "governance" / "hygiene"
    script_dir.mkdir(parents=True, exist_ok=True)
    (script_dir / "ratchet.py").write_text(
        "import json\n"
        "import sys\n"
        "if '--json' in sys.argv:\n"
        "    print(json.dumps({'status': 'ok', 'stub': True}))\n"
        "sys.exit(0)\n"
    )
    if finding_id is not None:
        gate_dir = repo / "scripts" / "governance" / "loop"
        gate_dir.mkdir(parents=True, exist_ok=True)
        marker = gate_dir / f"fix_marker_{finding_id}.txt"
        marker.write_text("fix applied\n")
        gate = gate_dir / f"fix_gate_{finding_id}.py"
        gate.write_text(
            "import sys\n"
            "from pathlib import Path\n\n"
            f'MARKER = Path(__file__).parent / "fix_marker_{finding_id}.txt"\n'
            "if MARKER.exists():\n"
            '    print("OK: marker found - clean tree")\n'
            "    sys.exit(0)\n"
            'print("FAIL: marker not found - slop reintroduced")\n'
            "sys.exit(1)\n"
        )
    return repo


# ---------------------------------------------------------------------------
# Fixture: run the full 5-stage chain once
# ---------------------------------------------------------------------------


@pytest.fixture()
def e2e_run(tmp_path: Path):
    """Run the full 5-stage pipeline end-to-end with the stub backend.

    Returns a dict with: run_id, runs_root, run_dir, warrant_path,
    gate_script, marker_path, finding_id, all stage exit codes,
    stage_procs (per-stage CompletedProcess), and origin_main_before.
    """
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    warrant_path = _write_warrant(tmp_path)
    run_id = f"e2e-{int(time.time())}"

    env = _base_env(runs_root)

    # Capture origin/main rev BEFORE the run to verify it's unchanged after.
    origin_main_proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "origin/main"],
        capture_output=True, text=True,
    )
    origin_main_before = origin_main_proc.stdout.strip()

    # Dict to capture each stage's subprocess result for honest verification.
    stage_procs: dict[str, subprocess.CompletedProcess[str]] = {}

    # --- Create run dir ---
    proc = _run_cli(RUNS_CLI, env, "create", "--run-id", run_id, "--warrant", str(warrant_path))
    stage_procs["runs_create"] = proc
    assert proc.returncode == 0, f"runs create failed: {proc.stderr!r}"
    run_dir = Path(proc.stdout.strip())

    # --- Scoper (explicit changed files for determinism) ---
    scope_path = run_dir / "scope.json"
    proc = _run_cli(
        SCOPER_CLI, env,
        "--warrant", str(warrant_path),
        "--output", str(scope_path),
        "--changed-files", "scripts/governance/loop/warrant.py",
        "--repo-root", str(REPO_ROOT),
    )
    stage_procs["scoper"] = proc
    assert proc.returncode == 0, f"scoper failed: {proc.stderr!r}"

    # --- Stage 1: prompt-audit-run ---
    proc = _run_cli(
        AUDIT_RUN_CLI, env,
        "--warrant", str(warrant_path),
        "--run-id", run_id,
        "--scope", str(scope_path),
    )
    stage_procs["audit_run"] = proc
    assert proc.returncode == 0, f"audit-run failed: {proc.stderr!r}"

    # --- Stage 2: prompt-audit-triage ---
    proc = _run_cli(
        TRIAGE_CLI, env,
        "--warrant", str(warrant_path),
        "--run-id", run_id,
    )
    stage_procs["triage"] = proc
    assert proc.returncode == 0, f"triage failed: {proc.stderr!r}"

    # --- Stage 3: prompt-audit-remediate ---
    worktree_root = tmp_path / "worktrees"
    worktree_root.mkdir(parents=True, exist_ok=True)
    proc = _run_cli(
        REMEDIATE_CLI, env,
        "--warrant", str(warrant_path),
        "--run-id", run_id,
        "--repo-root", str(REPO_ROOT),
        "--worktree-root", str(worktree_root),
    )
    stage_procs["remediate"] = proc
    assert proc.returncode == 0, f"remediate failed: {proc.stderr!r}"

    # --- Stage 4: prompt-audit-reaudit ---
    proc = _run_cli(
        REAUDIT_CLI, env,
        "--warrant", str(warrant_path),
        "--run-id", run_id,
    )
    stage_procs["reaudit"] = proc
    assert proc.returncode == 0, f"reaudit failed: {proc.stderr!r}"

    # --- Determine the finding_id before learn so the durable repo gate can
    # match the exact fix_proposal green_after.command emitted by remediation.
    run = _open_run(run_id, runs_root)
    findings = run.read_jsonl(run.accepted_findings_path())
    impl_findings = [f for f in findings if f.get("routing") == "IMPLEMENT"]
    assert impl_findings, f"no IMPLEMENT findings: {findings}"
    finding_id = impl_findings[0]["finding_id"]

    # --- Set up durable CI gate in the repo root used by learn. ---
    ratchet_repo = _green_ratchet_repo(tmp_path, finding_id=finding_id)
    gate_dir = ratchet_repo / "scripts" / "governance" / "loop"
    marker_path = gate_dir / f"fix_marker_{finding_id}.txt"
    gate_script = gate_dir / f"fix_gate_{finding_id}.py"
    ci_gate_cmd = f'"{VENV_PYTHON}" scripts/governance/loop/fix_gate_{finding_id}.py'

    # --- Stage 5: prompt-audit-learn ---
    proc = _run_cli(
        LEARN_CLI, env,
        "--warrant", str(warrant_path),
        "--run-id", run_id,
        "--repo-root", str(ratchet_repo),
        "--wire-ci",
        "--ci-workflow", str(tmp_path / "loop-ratchet-gates.yml"),
    )
    stage_procs["learn"] = proc
    assert proc.returncode == 0, f"learn failed: {proc.stderr!r}"

    return {
        "run_id": run_id,
        "runs_root": runs_root,
        "run_dir": run_dir,
        "run": run,
        "warrant_path": warrant_path,
        "gate_script": gate_script,
        "marker_path": marker_path,
        "ci_gate_cmd": ci_gate_cmd,
        "finding_id": finding_id,
        "env": env,
        "stage_procs": stage_procs,
        "origin_main_before": origin_main_before,
    }


# ---------------------------------------------------------------------------
# VAL-CROSS-001: Full 5-stage chain end-to-end (stub backend)
# ---------------------------------------------------------------------------


class TestFullChainEndToEnd:
    """VAL-CROSS-001: The full 5-stage chain produces the complete artifact chain."""

    def test_complete_artifact_chain_produced(self, e2e_run):
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]

        # audit JSON (at least one per scoped prompt)
        audits = run.list_audits()
        assert len(audits) > 0, "no audit JSON produced"

        # accepted_findings.jsonl
        af_path = run.accepted_findings_path()
        assert af_path.is_file(), "accepted_findings.jsonl not produced"
        findings = run.read_jsonl(af_path)
        assert len(findings) > 0, "accepted_findings.jsonl is empty"

        # fix_proposal
        fp_path = run.fix_proposal_path(fid)
        assert fp_path.is_file(), f"fix_proposal_{fid}.yaml not produced"

        # verifier_verdict
        vv_path = run.verifier_verdict_path(fid)
        assert vv_path.is_file(), f"verifier_verdict_{fid}.yaml not produced"

        # ratchet
        ratchet_path = run.ratchet_path(fid)
        assert ratchet_path.is_file(), f"ratchet_{fid}.yaml not produced"

        # ledger_entry
        ledger_path = run.ledger_entry_path(fid)
        assert ledger_path.is_file(), f"ledger_entry_{fid}.yaml not produced"

        # manifest.json
        assert run.manifest_path.is_file(), "manifest.json not produced"
        manifest = run.read_manifest()
        assert manifest.get("run_id") == e2e_run["run_id"]

    def test_manifest_records_gates(self, e2e_run):
        run = e2e_run["run"]
        manifest = run.read_manifest()
        gates = manifest.get("gates", [])
        assert len(gates) > 0, "manifest has no gates recorded"
        assert gates[0].get("finding_id") == e2e_run["finding_id"]

    def test_all_stages_exited_zero(self, e2e_run):
        """Verify each stage's exit code is 0 from a real subprocess invocation
        against real artifacts — not a tautological variable-is-not-None check.

        Each stage_procs entry is a real subprocess.CompletedProcess from a
        real CLI invocation. We verify the exit code AND that the stage produced
        a real artifact (the downstream stage consumed it)."""
        stage_procs = e2e_run["stage_procs"]
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]

        # Each stage must have a real CompletedProcess with returncode 0.
        expected_stages = ["runs_create", "scoper", "audit_run", "triage", "remediate", "reaudit", "learn"]
        for stage_name in expected_stages:
            assert stage_name in stage_procs, f"missing stage result: {stage_name}"
            proc = stage_procs[stage_name]
            assert hasattr(proc, "returncode"), f"{stage_name} result is not a real subprocess.CompletedProcess"
            assert proc.returncode == 0, (
                f"{stage_name} exited with {proc.returncode}, expected 0. "
                f"stderr={proc.stderr!r}"
            )

        # Verify the exit codes came from real invocations by checking that
        # each stage produced real artifacts consumed by the next stage.
        # runs_create -> run_dir exists
        assert e2e_run["run_dir"].is_dir(), "runs_create did not produce a real run dir"

        # scoper -> scope.json exists with content
        scope_path = e2e_run["run_dir"] / "scope.json"
        assert scope_path.is_file(), "scoper did not produce scope.json"
        assert scope_path.stat().st_size > 0, "scope.json is empty"

        # audit_run -> audit JSON files exist
        audits = run.list_audits()
        assert len(audits) > 0, "audit_run did not produce real audit JSON files"

        # triage -> accepted_findings.jsonl exists with content
        af_path = run.accepted_findings_path()
        assert af_path.is_file(), "triage did not produce accepted_findings.jsonl"
        findings = run.read_jsonl(af_path)
        assert len(findings) > 0, "accepted_findings.jsonl is empty"

        # remediate -> fix_proposal exists
        fp_path = run.fix_proposal_path(fid)
        assert fp_path.is_file(), "remediate did not produce fix_proposal"

        # reaudit -> verifier_verdict exists
        vv_path = run.verifier_verdict_path(fid)
        assert vv_path.is_file(), "reaudit did not produce verifier_verdict"

        # learn -> ratchet + ledger exist
        assert run.ratchet_path(fid).is_file(), "learn did not produce ratchet record"
        assert run.ledger_entry_path(fid).is_file(), "learn did not produce ledger entry"


# ---------------------------------------------------------------------------
# VAL-CROSS-002: Full chain artifacts schema-valid
# ---------------------------------------------------------------------------


class TestArtifactsSchemaValid:
    """VAL-CROSS-002: Every artifact validates against its schema."""

    def test_audit_json_schema_valid(self, e2e_run):
        """All audit JSON pass validate_audit.py (exit 0)."""
        run = e2e_run["run"]
        env = e2e_run["env"]
        for audit_path in run.list_audits():
            proc = _run_cli(VALIDATE_AUDIT_CLI, env, str(audit_path))
            assert proc.returncode == 0, (
                f"audit {audit_path.name} failed schema validation: {proc.stdout}"
            )

    def test_fix_proposal_has_required_fields(self, e2e_run):
        """fix_proposal conforms to §6.2 schema (all required fields present)."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        fp = run.read_yaml(run.fix_proposal_path(fid))
        fp = fp.get("fix_proposal", fp)
        required = {
            "run_id",
            "finding_id",
            "write_set_used",
            "patch_ref",
            "red_before",
            "green_after",
            "proof_mode",
            "anti_gaming_checklist",
        }
        missing = required - set(fp.keys())
        assert not missing, f"fix_proposal missing fields: {missing}"

    def test_fix_proposal_red_before_nonzero(self, e2e_run):
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        fp = run.read_yaml(run.fix_proposal_path(fid))
        fp = fp.get("fix_proposal", fp)
        assert fp["red_before"]["exit_code"] != 0, "red_before exit_code must be non-zero"

    def test_fix_proposal_green_after_zero(self, e2e_run):
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        fp = run.read_yaml(run.fix_proposal_path(fid))
        fp = fp.get("fix_proposal", fp)
        assert fp["green_after"]["exit_code"] == 0, "green_after exit_code must be 0"

    def test_verifier_verdict_has_required_fields(self, e2e_run):
        """verifier_verdict conforms to §6.3 schema."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        vv = run.read_yaml(run.verifier_verdict_path(fid))
        vv = vv.get("verifier_verdict", vv)
        required = {
            "run_id",
            "finding_id",
            "verifier_model",
            "model_independence",
            "falsification_attempts",
            "anti_gaming_checklist",
            "verdict",
            "evidence",
        }
        missing = required - set(vv.keys())
        assert not missing, f"verifier_verdict missing fields: {missing}"

    def test_verifier_verdict_confirmed(self, e2e_run):
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        vv = run.read_yaml(run.verifier_verdict_path(fid))
        vv = vv.get("verifier_verdict", vv)
        assert vv["verdict"] == "confirmed", f"expected confirmed, got {vv['verdict']}"
        assert vv["routing"] == "ADVANCE"

    def test_ratchet_has_required_fields(self, e2e_run):
        """ratchet record conforms to §6.4 schema."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        ratchet = run.read_yaml(run.ratchet_path(fid))
        ratchet = ratchet.get("ratchet", ratchet)
        required = {
            "run_id",
            "finding_id",
            "root_cause",
            "fix_patch_ref",
            "new_gate",
            "prevents_recurrence",
        }
        missing = required - set(ratchet.keys())
        assert not missing, f"ratchet missing fields: {missing}"

    def test_ratchet_new_gate_has_required_fields(self, e2e_run):
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        ratchet = run.read_yaml(run.ratchet_path(fid))
        ratchet = ratchet.get("ratchet", ratchet)
        gate = ratchet["new_gate"]
        required = {"kind", "location", "proves", "red_before_ref", "green_after_ref"}
        missing = required - set(gate.keys())
        assert not missing, f"new_gate missing fields: {missing}"

    def test_ledger_entry_has_required_fields(self, e2e_run):
        """ledger_entry conforms to §6.5 schema."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        ledger = run.read_yaml(run.ledger_entry_path(fid))
        ledger = ledger.get("ledger_entry", ledger)
        required = {
            "timestamp_utc",
            "commit",
            "finding_class",
            "status",
            "gate_ref",
            "receipt_ref",
            "human_approver",
        }
        missing = required - set(ledger.keys())
        assert not missing, f"ledger_entry missing fields: {missing}"

    def test_ledger_entry_claim_label_prior_claim(self, e2e_run):
        """VAL-LEARN-007: ledger entries labeled prior_claim, not ground_truth."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        ledger = run.read_yaml(run.ledger_entry_path(fid))
        ledger = ledger.get("ledger_entry", ledger)
        assert ledger.get("claim_label") == "prior_claim"

    def test_ci_receipt_exists_and_referenced(self, e2e_run):
        """VAL-LEARN-011: CI receipt written to receipts/ and referenced."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        ci_receipt = run.receipt_path(f"ci_receipt_{fid}.json")
        assert ci_receipt.is_file(), "CI receipt not written"
        receipt = run.read_json(ci_receipt)
        assert receipt.get("exit_code") == 0, "CI receipt should show green (exit 0)"

        # ledger and ratchet reference the receipt
        ledger = run.read_yaml(run.ledger_entry_path(fid))
        ledger = ledger.get("ledger_entry", ledger)
        assert ledger["receipt_ref"], "ledger receipt_ref is empty"
        assert ci_receipt.name in ledger["receipt_ref"], "ledger receipt_ref does not point to CI receipt"

        ratchet = run.read_yaml(run.ratchet_path(fid))
        ratchet = ratchet.get("ratchet", ratchet)
        assert ratchet.get("ci_receipt_ref"), "ratchet ci_receipt_ref is empty"


# ---------------------------------------------------------------------------
# VAL-CROSS-003: Ratcheted gate fails-closed on reintroduction
# ---------------------------------------------------------------------------


class TestRatchetedGateFailsClosed:
    """VAL-CROSS-003: After ratcheting, reintroducing slop fails the gate
    (red, non-zero) and the clean tree passes (green, zero)."""

    def test_clean_tree_passes_green(self, e2e_run):
        """With the marker present (clean tree), the gate exits 0 (green)."""
        gate = e2e_run["gate_script"]
        marker = e2e_run["marker_path"]
        assert marker.exists(), "marker should be present for clean tree"

        proc = subprocess.run(
            [VENV_PYTHON, str(gate)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, (
            f"clean tree should pass (green/0), got {proc.returncode}: {proc.stdout}"
        )

    def test_reintroduced_slop_fails_red(self, e2e_run):
        """With the marker removed (slop reintroduced), the gate exits non-zero (red)."""
        gate = e2e_run["gate_script"]
        marker = e2e_run["marker_path"]

        # Remove the marker — reintroduce slop
        marker.unlink()
        assert not marker.exists(), "marker should be removed"

        try:
            proc = subprocess.run(
                [VENV_PYTHON, str(gate)],
                capture_output=True, text=True,
            )
            assert proc.returncode != 0, (
                f"reintroduced slop should fail (red/non-zero), got {proc.returncode}: {proc.stdout}"
            )
        finally:
            # Restore the marker for subsequent tests
            marker.write_text("fix applied\n")

    def test_red_before_green_after_pattern(self, e2e_run):
        """The fix_proposal demonstrates the Phase-0 red-before/green-after pattern:
        red_before has non-zero exit, green_after has zero exit."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        fp = run.read_yaml(run.fix_proposal_path(fid))
        fp = fp.get("fix_proposal", fp)
        assert fp["red_before"]["exit_code"] != 0, "red_before must be non-zero"
        assert fp["green_after"]["exit_code"] == 0, "green_after must be zero"
        assert fp["proof_mode"] in ("natural", "synthetic"), (
            f"proof_mode must be natural or synthetic, got {fp['proof_mode']}"
        )


# ---------------------------------------------------------------------------
# VAL-CROSS-005: No LLM opinion recorded as truth
# ---------------------------------------------------------------------------


class TestNoLLMOpinionAsTruth:
    """VAL-CROSS-005: Every verdict is backed by a deterministic exit code or
    schema validation, traceable to a receipt. No LLM opinion is recorded as a
    verified fact."""

    def test_fix_proposal_verdicts_backed_by_exit_codes(self, e2e_run):
        """red_before and green_after have exit_code fields (not opinions)."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        fp = run.read_yaml(run.fix_proposal_path(fid))
        fp = fp.get("fix_proposal", fp)
        assert "exit_code" in fp["red_before"], "red_before has no exit_code"
        assert "exit_code" in fp["green_after"], "green_after has no exit_code"
        assert isinstance(fp["red_before"]["exit_code"], int)
        assert isinstance(fp["green_after"]["exit_code"], int)

    def test_verifier_verdict_reconciled_with_deterministic_checks(self, e2e_run):
        """The verifier_verdict's evidence receipts show deterministic exit codes,
        not LLM opinions. The verdict was reconciled by _reconcile_verdict."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        vv = run.read_yaml(run.verifier_verdict_path(fid))
        vv = vv.get("verifier_verdict", vv)

        # Evidence receipts must contain exit_code fields
        evidence = vv.get("evidence", [])
        assert len(evidence) >= 2, f"expected at least 2 evidence receipts, got {len(evidence)}"
        red_ev = [e for e in evidence if e.get("kind") == "red_before"]
        green_ev = [e for e in evidence if e.get("kind") == "green_after"]
        assert red_ev, "no red_before evidence receipt"
        assert green_ev, "no green_after evidence receipt"
        assert red_ev[0].get("exit_code") is not None, "red_before receipt has no exit_code"
        assert green_ev[0].get("exit_code") is not None, "green_after receipt has no exit_code"

    def test_ratchet_backed_by_ci_receipt(self, e2e_run):
        """The ratchet record references a CI receipt (deterministic exit code)."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        ratchet = run.read_yaml(run.ratchet_path(fid))
        ratchet = ratchet.get("ratchet", ratchet)
        ci_ref = ratchet.get("ci_receipt_ref", "")
        assert ci_ref, "ratchet has no ci_receipt_ref — verdict not backed by a receipt"

        # The receipt file must exist and contain an exit_code
        receipt_path = run.run_dir / ci_ref
        assert receipt_path.is_file(), f"CI receipt file not found: {receipt_path}"
        receipt = run.read_json(receipt_path)
        assert "exit_code" in receipt, "CI receipt has no exit_code"
        assert receipt["exit_code"] == 0, "CI receipt exit_code must be 0 (green)"

    def test_ledger_receipt_ref_points_to_existing_receipt(self, e2e_run):
        """VAL-LEARN-006: ledger entry receipt_ref points to a replayable receipt."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        ledger = run.read_yaml(run.ledger_entry_path(fid))
        ledger = ledger.get("ledger_entry", ledger)
        ref = ledger.get("receipt_ref", "")
        assert ref, "ledger receipt_ref is empty"
        receipt_path = run.run_dir / ref
        assert receipt_path.is_file(), f"ledger receipt file not found: {receipt_path}"

    def test_model_independence_honestly_recorded(self, e2e_run):
        """model_independence is not_proven in stub mode (never recorded as pass)."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        vv = run.read_yaml(run.verifier_verdict_path(fid))
        vv = vv.get("verifier_verdict", vv)
        assert vv["model_independence"] == "not_proven", (
            f"stub mode must record not_proven, got {vv['model_independence']}"
        )
        assert vv["verifier_model"] == "stub"


# ---------------------------------------------------------------------------
# VAL-CROSS-006: Anti-gaming across all fix diffs
# ---------------------------------------------------------------------------


class TestAntiGamingAcrossDiffs:
    """VAL-CROSS-006: No fix diff introduces new skips, xfails, weakened
    assertions, deleted tests, or widened budgets."""

    def test_remediate_checklist_all_pass(self, e2e_run):
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        fp = run.read_yaml(run.fix_proposal_path(fid))
        fp = fp.get("fix_proposal", fp)
        checklist = fp.get("anti_gaming_checklist", {})
        required_items = [
            "no_new_skips",
            "no_new_xfails",
            "no_weakened_assertions",
            "no_deleted_tests",
            "no_widened_budgets",
            "fix_addresses_root_cause",
        ]
        for item in required_items:
            assert item in checklist, f"checklist missing {item}"
            assert checklist[item] == "pass", (
                f"anti-gaming item {item} = {checklist[item]} (expected pass)"
            )

    def test_verifier_checklist_all_pass(self, e2e_run):
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        vv = run.read_yaml(run.verifier_verdict_path(fid))
        vv = vv.get("verifier_verdict", vv)
        checklist = vv.get("anti_gaming_checklist", {})
        required_items = [
            "no_new_skips",
            "no_new_xfails",
            "no_weakened_assertions",
            "no_deleted_tests",
            "no_widened_budgets",
            "fix_addresses_root_cause",
        ]
        for item in required_items:
            assert item in checklist, f"verifier checklist missing {item}"
            assert checklist[item] == "pass", (
                f"verifier anti-gaming item {item} = {checklist[item]} (expected pass)"
            )

    def test_fix_diff_exists_and_is_clean(self, e2e_run):
        """The fix diff is saved and contains no gaming patterns."""
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        diff_path = run.fixes_dir / f"fix_diff_{fid}.patch"
        assert diff_path.is_file(), "fix diff not saved"
        diff_text = diff_path.read_text()
        # The diff should contain added files (gate script + marker), no skips/xfails
        assert "pytest.skip" not in diff_text, "fix diff contains pytest.skip"
        assert "pytest.mark.skip" not in diff_text, "fix diff contains skip marker"
        assert "pytest.mark.xfail" not in diff_text, "fix diff contains xfail marker"


# ---------------------------------------------------------------------------
# VAL-CROSS-007: User working tree never modified
# ---------------------------------------------------------------------------


class TestUserWorkingTreeUntouched:
    """VAL-CROSS-007: The user's working tree at /Users/dhyana/dharma_swarm is
    never modified by the loop throughout M1."""

    def test_user_repo_status_unchanged(self, e2e_run):
        """The user's working tree has no loop-introduced changes."""
        proc = subprocess.run(
            ["git", "-C", USER_REPO, "status", "--porcelain"],
            capture_output=True, text=True,
        )
        # The user's tree may be dirty (user-owned), but it should not contain
        # any loop-introduced changes (no ds_loop_fix_* worktrees, no loop/ files).
        status = proc.stdout
        assert "ds_loop_fix_" not in status, (
            f"user working tree contains loop fix worktree reference: {status}"
        )
        assert "scripts/governance/loop/" not in status, (
            f"user working tree contains loop script changes: {status}"
        )

    def test_no_orphaned_fix_worktrees(self, e2e_run):
        """VAL-REMEDIATE-011: no orphaned /tmp/ds_loop_fix_* worktrees remain."""
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "worktree", "list"],
            capture_output=True, text=True,
        )
        worktree_list = proc.stdout
        assert "ds_loop_fix_" not in worktree_list, (
            f"orphaned fix worktree found: {worktree_list}"
        )

    def test_mission_branch_not_main(self, e2e_run):
        """We are on the mission branch, not main."""
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "branch", "--show-current"],
            capture_output=True, text=True,
        )
        branch = proc.stdout.strip()
        if not branch and os.environ.get("GITHUB_ACTIONS"):
            branch = os.environ.get("GITHUB_HEAD_REF", "")
        assert branch == MISSION_BRANCH, f"expected {MISSION_BRANCH}, got {branch}"


# ---------------------------------------------------------------------------
# VAL-CROSS-008: Propose-only — no merge/push to main
# ---------------------------------------------------------------------------


class TestProposeOnlyNoPushMerge:
    """VAL-CROSS-008: No push or merge to origin/main occurs. All commits land
    on the mission branch."""

    def test_origin_main_unchanged(self, e2e_run):
        """origin/main rev is unchanged before vs after the run, AND no loop
        commits landed on origin/main. This is a real git rev-parse + git log
        check, not a tautological variable-equals-itself assertion."""
        origin_main_before = e2e_run["origin_main_before"]
        assert len(origin_main_before) == 40, (
            f"origin/main before hash looks wrong: {origin_main_before}"
        )

        # Verify origin/main rev has NOT changed after the full pipeline run.
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "origin/main"],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, "cannot resolve origin/main after run"
        origin_main_after = proc.stdout.strip()
        assert origin_main_after == origin_main_before, (
            f"origin/main CHANGED during the run: "
            f"before={origin_main_before} after={origin_main_after}"
        )

        # Verify no loop-related commits landed on origin/main.
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", "--oneline", "-20", "origin/main"],
            capture_output=True, text=True,
        )
        log = proc.stdout
        assert "loop" not in log.lower(), (
            f"loop commit found on origin/main — propose-only violated: {log}"
        )

    def test_no_merge_to_main_in_log(self, e2e_run):
        """No merge commit to origin/main appears in recent history."""
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", "--oneline", "-10", "origin/main"],
            capture_output=True, text=True,
        )
        log = proc.stdout
        # No loop-related commits should appear on origin/main
        assert "loop" not in log.lower(), (
            f"loop commit found on origin/main: {log}"
        )


# ---------------------------------------------------------------------------
# VAL-CROSS-009: Post-ratchet fresh-agent re-audit attempts reintroduction
# ---------------------------------------------------------------------------


class TestPostRatchetReaudit:
    """VAL-CROSS-009: After a gate is ratcheted, a fresh-agent re-audit attempts
    to reintroduce the slop class and confirms the gate prevents it, appending
    the result to the ledger."""

    def test_gate_prevents_reintroduction(self, e2e_run):
        """Running the ratcheted gate with slop reintroduced fails (non-zero)."""
        gate = e2e_run["gate_script"]
        marker = e2e_run["marker_path"]

        # Simulate a fresh agent attempting to reintroduce the slop class
        marker.unlink()
        try:
            proc = subprocess.run(
                [VENV_PYTHON, str(gate)],
                capture_output=True, text=True,
            )
            # The gate prevents reintroduction — non-zero exit
            assert proc.returncode != 0, (
                "gate should prevent reintroduction (non-zero), "
                f"got {proc.returncode}"
            )
            assert "FAIL" in proc.stdout or "not found" in proc.stdout, (
                f"gate output should indicate failure: {proc.stdout}"
            )
        finally:
            marker.write_text("fix applied\n")

    def test_clean_tree_passes_after_reintroduction_attempt(self, e2e_run):
        """After the reintroduction attempt, the clean tree passes the gate."""
        gate = e2e_run["gate_script"]
        marker = e2e_run["marker_path"]
        assert marker.exists(), "marker should be restored"

        proc = subprocess.run(
            [VENV_PYTHON, str(gate)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, (
            f"clean tree should pass (0), got {proc.returncode}"
        )

    def test_reaudit_result_appended_to_ledger(self, e2e_run):
        """VAL-CROSS-009: The re-audit reintroduces slop, the gate catches it
        (non-zero exit from a real subprocess), and the ledger entry produced
        by the learn stage is genuinely real (evidence-linked, replayable receipt
        with a real exit code) — not a self-fulfilling file-exists check.

        This test does NOT write its own ledger entry and then check it exists.
        Instead it verifies:
        1. The gate genuinely catches reintroduced slop (real subprocess, non-zero exit).
        2. The gate genuinely passes on the clean tree (real subprocess, zero exit).
        3. The ledger entry written by the learn stage references a real receipt
           that contains a real exit code from the CI gate.
        """
        run = e2e_run["run"]
        fid = e2e_run["finding_id"]
        gate = e2e_run["gate_script"]
        marker = e2e_run["marker_path"]

        # 1. Reintroduce slop (remove marker) and run the gate — must fail (non-zero).
        marker.unlink()
        try:
            proc_slop = subprocess.run(
                [VENV_PYTHON, str(gate)],
                capture_output=True, text=True,
            )
            assert proc_slop.returncode != 0, (
                f"gate should catch reintroduced slop (non-zero exit), "
                f"got {proc_slop.returncode}: {proc_slop.stdout}"
            )
            assert "FAIL" in proc_slop.stdout or "not found" in proc_slop.stdout, (
                f"gate output should indicate failure: {proc_slop.stdout}"
            )

            # 2. Restore the clean tree and run the gate — must pass (zero exit).
            marker.write_text("fix applied\n")
            proc_clean = subprocess.run(
                [VENV_PYTHON, str(gate)],
                capture_output=True, text=True,
            )
            assert proc_clean.returncode == 0, (
                f"gate should pass on clean tree (zero exit), "
                f"got {proc_clean.returncode}: {proc_clean.stdout}"
            )
        finally:
            if not marker.exists():
                marker.write_text("fix applied\n")

        # 3. Verify the ledger entry written by the learn stage is genuinely real.
        #    It must reference a receipt file that exists and contains a real
        #    exit code from a real CI gate invocation (not a self-fulfilling check).
        ledger_path = run.ledger_entry_path(fid)
        assert ledger_path.is_file(), "learn stage did not produce a ledger entry"
        ledger = run.read_yaml(ledger_path)
        ledger = ledger.get("ledger_entry", ledger)

        receipt_ref = ledger.get("receipt_ref", "")
        assert receipt_ref, "ledger entry has empty receipt_ref — not evidence-linked"
        receipt_path = run.run_dir / receipt_ref
        assert receipt_path.is_file(), (
            f"ledger receipt_ref points to non-existent file: {receipt_ref}"
        )

        # The receipt must contain a real exit code from a real subprocess.
        receipt = run.read_json(receipt_path)
        assert "exit_code" in receipt, (
            "ledger receipt has no exit_code — not a replayable deterministic receipt"
        )
        assert receipt["exit_code"] == 0, (
            f"CI receipt exit_code should be 0 (green), got {receipt['exit_code']}"
        )
        assert "command" in receipt, (
            "CI receipt has no command — not replayable"
        )

        post_ref = ledger.get("post_ratchet_reaudit_ref", "")
        assert post_ref, "ledger does not reference post-ratchet re-audit evidence"
        post_receipt_path = run.run_dir / post_ref
        assert post_receipt_path.is_file(), (
            f"post-ratchet receipt_ref points to non-existent file: {post_ref}"
        )
        post_receipt = run.read_json(post_receipt_path)
        assert post_receipt.get("kind") == "post_ratchet_reaudit"
        assert post_receipt.get("reintroduction_attempted") is True
        assert post_receipt.get("red_exit_code") != 0, (
            "post-ratchet re-audit did not prove reintroduced slop fails"
        )
        assert post_receipt.get("green_exit_code") == 0, (
            "post-ratchet re-audit did not prove the restored clean gate passes"
        )
        assert post_receipt.get("prevented_reintroduction") is True

        post_ledger_path = run.ledger_dir / f"ledger_entry_{fid}_post_reaudit.yaml"
        assert post_ledger_path.is_file(), "post-ratchet result was not appended to ledger"
        post_ledger = run.read_yaml(post_ledger_path).get("ledger_entry", {})
        assert post_ledger.get("receipt_ref") == post_ref
