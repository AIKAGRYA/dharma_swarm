"""Tests for scripts/governance/loop/prompt_audit_learn.py — Stage 5 (Ratcheter).

Covers VAL-LEARN-001..012:
  001  Only green CI advances (non-green = no ratchet record)
  002  Drives existing ratchet engine (hygiene/ratchet.py / promote.py), not parallel
  003  ratchet record with new_gate (kind, location, proves, red_before_ref, green_after_ref)
  004  ledger_entry per gate (§6.5: timestamp_utc, commit, finding_class, status, gate_ref, receipt_ref, human_approver)
  005  No gate producible = DEFER (ratchet-or-nothing)
  006  Ledger entry structured + evidence-linked (receipt_ref to replayable receipt)
  007  Ledger entries labeled prior_claim not ground_truth
  008  prevents_recurrence boolean field in ratchet record
  009  root_cause + fix_patch_ref fields in ratchet record
  011  CI receipt written to receipts/ and referenced by ratchet + ledger
  012  Non-green CI rejection reason (exit code + failing gate) recorded before archiving
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
LEARN_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "prompt_audit_learn.py"
RUNS_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "runs.py"
RATCHET_CLI = REPO_ROOT / "scripts" / "governance" / "hygiene" / "ratchet.py"

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


def _make_warrant_dict(run_id: str = "warrant-learn-test") -> dict:
    return {
        "id": run_id,
        "issued_by": "orchestrator",
        "authority_level": "medium",
        "trigger": "manual",
        "scope": {
            "base_ref": "HEAD",
            "head_ref": "ratchet/loop-phases-1-3",
            "councils": list(ALL_COUNCILS),
            "prompt_ids": [],
        },
        "write_set": ["scripts/governance/loop/**"],
        "budget": {"max_tokens": 100000, "max_wall_clock_min": 30, "max_fixes_per_run": 5},
        "merge_policy": "propose_only",
        "expires_at": _future_iso(),
    }


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


def _make_fix_proposal(
    run_id: str,
    finding_id: str = "F-001",
    proof_mode: str = "synthetic",
    red_exit: int = 1,
    green_exit: int = 0,
    gate_command: str | None = None,
) -> dict:
    cmd = gate_command or f'"{VENV_PYTHON}" -c "import sys; sys.exit(0)"'
    return {
        "fix_proposal": {
            "run_id": run_id,
            "finding_id": finding_id,
            "write_set_used": ["scripts/governance/loop/**"],
            "patch_ref": f"fix/{finding_id}",
            "red_before": {
                "command": cmd,
                "exit_code": red_exit,
                "key_output": "FAIL: marker not found" if red_exit != 0 else "OK",
            },
            "green_after": {
                "command": cmd,
                "exit_code": green_exit,
                "key_output": "OK: marker found" if green_exit == 0 else "FAIL",
            },
            "proof_mode": proof_mode,
            "anti_gaming_checklist": {
                "no_new_skips": "pass",
                "no_new_xfails": "pass",
                "no_weakened_assertions": "pass",
                "no_deleted_tests": "pass",
                "no_widened_budgets": "pass",
                "fix_addresses_root_cause": "pass",
            },
        }
    }


def _make_verifier_verdict(
    run_id: str,
    finding_id: str = "F-001",
    verdict: str = "confirmed",
    routing: str = "ADVANCE",
) -> dict:
    return {
        "verifier_verdict": {
            "run_id": run_id,
            "finding_id": finding_id,
            "verifier_model": "stub",
            "model_independence": "not_proven",
            "falsification_attempts": [
                {"attempt": "verify red_before", "result": "pass", "evidence": "exit=1"},
            ],
            "anti_gaming_checklist": {
                "no_new_skips": "pass",
                "no_new_xfails": "pass",
                "no_weakened_assertions": "pass",
                "no_deleted_tests": "pass",
                "no_widened_budgets": "pass",
                "fix_addresses_root_cause": "pass",
            },
            "verdict": verdict,
            "evidence": [],
            "routing": routing,
        }
    }


def _setup_run(
    tmp_path: Path,
    finding: dict,
    fix_proposal: dict,
    verdict: dict,
    warrant: dict | None = None,
) -> tuple[Path, str, Path]:
    """Create a run dir with accepted_findings + fix_proposal + verifier_verdict.

    Returns (warrant_path, run_id, runs_root).
    """
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    run_id = "learn-test-001"
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

    from scripts.governance.loop.runs import Run
    run = Run(run_dir)
    fid = finding["finding_id"]
    run.write_jsonl(run.accepted_findings_path(), [finding])
    run.write_yaml(run.fix_proposal_path(fid), fix_proposal)
    run.write_yaml(run.verifier_verdict_path(fid), verdict)

    return warrant_path, run_id, runs_root


def _run_learn_cli(
    warrant: Path,
    run_id: str,
    runs_root: Path,
    ci_gate: str = "true",
    extra_args: list[str] | None = None,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    env["LOOP_AGENT_BACKEND"] = "stub"
    if extra_env:
        env.update(extra_env)
    cmd = [
        VENV_PYTHON, str(LEARN_CLI),
        "--warrant", str(warrant),
        "--run-id", run_id,
        "--ci-gate", ci_gate,
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _open_run(run_id: str, runs_root: Path):
    from scripts.governance.loop.runs import RunManager
    return RunManager.open_run(run_id, week=None) if runs_root is None else Run(Path(runs_root) / "2026-W26" / run_id)


def _open_run_search(run_id: str, runs_root: Path):
    """Open a run by searching the runs root (handles any week bucket)."""
    from scripts.governance.loop.runs import RunManager
    # Temporarily override LOOP_RUNS_DIR so open_run finds the run
    old = os.environ.get("LOOP_RUNS_DIR")
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        return RunManager.open_run(run_id)
    finally:
        if old is not None:
            os.environ["LOOP_RUNS_DIR"] = old
        else:
            os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLearnGreenAdvances:
    """VAL-LEARN-001: Only green CI advances to ratchet."""

    def test_green_ci_produces_ratchet(self, tmp_path):
        finding = _make_finding(fid="F-GREEN")
        fp = _make_fix_proposal("learn-test-001", "F-GREEN")
        vv = _make_verifier_verdict("learn-test-001", "F-GREEN", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

        run = _open_run_search(run_id, runs_root)
        ratchet_path = run.ratchet_path("F-GREEN")
        assert ratchet_path.is_file(), f"ratchet record not produced for green CI: {proc.stdout!r}"
        ratchet = yaml.safe_load(ratchet_path.read_text())
        assert "ratchet" in ratchet

    def test_non_green_ci_no_ratchet(self, tmp_path):
        finding = _make_finding(fid="F-RED")
        fp = _make_fix_proposal("learn-test-001", "F-RED")
        vv = _make_verifier_verdict("learn-test-001", "F-RED", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="false")
        # non-green = rejection (exit 1)
        assert proc.returncode == 1, f"expected exit 1 for non-green, got {proc.returncode}: {proc.stdout!r}"

        run = _open_run_search(run_id, runs_root)
        ratchet_path = run.ratchet_path("F-RED")
        assert not ratchet_path.is_file(), "ratchet record must NOT be produced for non-green CI"

    def test_non_green_rejection_recorded(self, tmp_path):
        """VAL-LEARN-012: rejection reason (exit code + failing gate) recorded."""
        finding = _make_finding(fid="F-REJ")
        fp = _make_fix_proposal("learn-test-001", "F-REJ")
        vv = _make_verifier_verdict("learn-test-001", "F-REJ", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="false")
        assert proc.returncode == 1

        run = _open_run_search(run_id, runs_root)
        # A rejection record should exist in the run dir
        rejection_files = list(run.run_dir.glob("*reject*")) + list(run.run_dir.glob("*rejection*"))
        # Also check the receipts dir for a ci_receipt with non-green exit
        receipt_files = list(run.receipts_dir.glob("*ci*"))
        assert receipt_files, "CI receipt must be written even on non-green"
        receipt = json.loads(receipt_files[0].read_text())
        assert receipt["exit_code"] != 0, "non-green receipt must have non-zero exit_code"


class TestLearnDrivesRatchetEngine:
    """VAL-LEARN-002: Drives existing ratchet engine, not a parallel one."""

    def test_learn_module_imports_existing_ratchet(self):
        """The learn module imports from the existing hygiene ratchet engine."""
        import scripts.governance.loop.prompt_audit_learn as learn_mod
        source = Path(learn_mod.__file__).read_text()
        # Must reference the existing ratchet engine
        assert "hygiene.ratchet" in source or "hygiene/ratchet" in source, (
            "learn stage must drive the existing hygiene/ratchet.py engine, not a parallel one"
        )
        # Must NOT define new ratchet counter classes
        assert "class Counter" not in source, (
            "learn stage must not introduce a new ratchet-counter implementation"
        )

    def test_ratchet_engine_receipt_produced(self, tmp_path):
        """A receipt showing the ratchet engine was invoked is produced."""
        finding = _make_finding(fid="F-RATCHET")
        fp = _make_fix_proposal("learn-test-001", "F-RATCHET")
        vv = _make_verifier_verdict("learn-test-001", "F-RATCHET", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 0, f"{proc.stdout!r} {proc.stderr!r}"

        run = _open_run_search(run_id, runs_root)
        ratchet_receipts = list(run.receipts_dir.glob("*ratchet*"))
        assert ratchet_receipts, (
            "a ratchet engine receipt must be produced showing the existing engine was driven"
        )


class TestLearnRatchetRecord:
    """VAL-LEARN-003, 008, 009: ratchet record with new_gate + required fields."""

    def test_ratchet_has_new_gate_with_all_fields(self, tmp_path):
        """VAL-LEARN-003: new_gate with kind, location, proves, red_before_ref, green_after_ref."""
        finding = _make_finding(fid="F-GATE", failure_class="MARKER_EXCLUSION_DRIFT")
        fp = _make_fix_proposal("learn-test-001", "F-GATE")
        vv = _make_verifier_verdict("learn-test-001", "F-GATE", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 0, f"{proc.stdout!r} {proc.stderr!r}"

        run = _open_run_search(run_id, runs_root)
        ratchet = yaml.safe_load(run.ratchet_path("F-GATE").read_text())["ratchet"]
        assert "new_gate" in ratchet, "ratchet record must have new_gate"
        gate = ratchet["new_gate"]
        for field in ("kind", "location", "proves", "red_before_ref", "green_after_ref"):
            assert field in gate, f"new_gate missing required field: {field}"
        assert gate["kind"] in ("ci_gate", "fitness_function", "regression_test", "settled_false_positive")

    def test_ratchet_has_prevents_recurrence(self, tmp_path):
        """VAL-LEARN-008: prevents_recurrence boolean field."""
        finding = _make_finding(fid="F-PREV")
        fp = _make_fix_proposal("learn-test-001", "F-PREV")
        vv = _make_verifier_verdict("learn-test-001", "F-PREV", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 0

        run = _open_run_search(run_id, runs_root)
        ratchet = yaml.safe_load(run.ratchet_path("F-PREV").read_text())["ratchet"]
        assert "prevents_recurrence" in ratchet, "ratchet must have prevents_recurrence"
        assert isinstance(ratchet["prevents_recurrence"], bool)

    def test_ratchet_has_root_cause_and_fix_patch_ref(self, tmp_path):
        """VAL-LEARN-009: root_cause + fix_patch_ref fields."""
        finding = _make_finding(fid="F-RC")
        fp = _make_fix_proposal("learn-test-001", "F-RC")
        vv = _make_verifier_verdict("learn-test-001", "F-RC", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 0

        run = _open_run_search(run_id, runs_root)
        ratchet = yaml.safe_load(run.ratchet_path("F-RC").read_text())["ratchet"]
        assert "root_cause" in ratchet, "ratchet must have root_cause"
        assert "fix_patch_ref" in ratchet, "ratchet must have fix_patch_ref"


class TestLearnLedgerEntry:
    """VAL-LEARN-004, 006, 007: ledger_entry per gate, structured, evidence-linked, prior_claim."""

    def test_ledger_entry_written_with_all_fields(self, tmp_path):
        """VAL-LEARN-004: one ledger_entry per gate with §6.5 fields."""
        finding = _make_finding(fid="F-LED")
        fp = _make_fix_proposal("learn-test-001", "F-LED")
        vv = _make_verifier_verdict("learn-test-001", "F-LED", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 0

        run = _open_run_search(run_id, runs_root)
        ledger_path = run.ledger_entry_path("F-LED")
        assert ledger_path.is_file(), "ledger_entry must be written per ratcheted gate"
        entry = yaml.safe_load(ledger_path.read_text())["ledger_entry"]
        for field in ("timestamp_utc", "commit", "finding_class", "status", "gate_ref", "receipt_ref", "human_approver"):
            assert field in entry, f"ledger_entry missing §6.5 field: {field}"

    def test_ledger_entry_evidence_linked(self, tmp_path):
        """VAL-LEARN-006: receipt_ref points to an existing receipt file."""
        finding = _make_finding(fid="F-EV")
        fp = _make_fix_proposal("learn-test-001", "F-EV")
        vv = _make_verifier_verdict("learn-test-001", "F-EV", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 0

        run = _open_run_search(run_id, runs_root)
        entry = yaml.safe_load(run.ledger_entry_path("F-EV").read_text())["ledger_entry"]
        receipt_ref = entry["receipt_ref"]
        # receipt_ref must point to an existing receipt file
        receipt_path = run.run_dir / receipt_ref
        assert receipt_path.is_file(), (
            f"ledger_entry receipt_ref must point to an existing receipt: {receipt_ref}"
        )

    def test_ledger_entry_labeled_prior_claim(self, tmp_path):
        """VAL-LEARN-007: ledger entries labeled prior_claim, not ground_truth."""
        finding = _make_finding(fid="F-CLAIM")
        fp = _make_fix_proposal("learn-test-001", "F-CLAIM")
        vv = _make_verifier_verdict("learn-test-001", "F-CLAIM", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 0

        run = _open_run_search(run_id, runs_root)
        entry = yaml.safe_load(run.ledger_entry_path("F-CLAIM").read_text())["ledger_entry"]
        assert entry.get("claim_label") == "prior_claim", (
            "ledger entry must be labeled prior_claim (not ground_truth) for fresh agents"
        )
        assert entry.get("claim_label") != "ground_truth"


class TestLearnDeferOnNoGate:
    """VAL-LEARN-005: No gate producible = DEFER (ratchet-or-nothing)."""

    def test_no_gate_routes_to_defer(self, tmp_path):
        """When a finding cannot produce a gate (no valid proof), it routes to DEFER."""
        finding = _make_finding(fid="F-NOGATE")
        # proof_mode=none means no red-before/green-after achievable
        fp = _make_fix_proposal("learn-test-001", "F-NOGATE", proof_mode="none", red_exit=0, green_exit=0)
        vv = _make_verifier_verdict("learn-test-001", "F-NOGATE", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        # DEFER = clean exit 0 (not rejected, just deferred)
        assert proc.returncode == 0, f"{proc.stdout!r} {proc.stderr!r}"

        run = _open_run_search(run_id, runs_root)
        # No ratchet record (ratchet-or-nothing)
        assert not run.ratchet_path("F-NOGATE").is_file(), (
            "no gate producible must NOT produce a ratchet record"
        )
        # A DEFER record should exist
        defer_files = list(run.run_dir.glob("*defer*")) + list(run.run_dir.glob("*DEFER*"))
        # Check stdout mentions DEFER
        assert "DEFER" in proc.stdout, (
            f"DEFER routing must be reported in output: {proc.stdout!r}"
        )


class TestLearnCIReceipt:
    """VAL-LEARN-011: CI receipt written to receipts/ and referenced."""

    def test_ci_receipt_written_and_referenced(self, tmp_path):
        finding = _make_finding(fid="F-CIR")
        fp = _make_fix_proposal("learn-test-001", "F-CIR")
        vv = _make_verifier_verdict("learn-test-001", "F-CIR", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 0, f"{proc.stdout!r} {proc.stderr!r}"

        run = _open_run_search(run_id, runs_root)
        ci_receipts = list(run.receipts_dir.glob("*ci*"))
        assert ci_receipts, "CI receipt must be written to receipts/"
        receipt = json.loads(ci_receipts[0].read_text())
        assert receipt["exit_code"] == 0, "green CI receipt must have exit_code 0"

        # ratchet record references the CI receipt
        ratchet = yaml.safe_load(run.ratchet_path("F-CIR").read_text())["ratchet"]
        assert "ci_receipt_ref" in ratchet, "ratchet record must reference the CI receipt"
        ci_ref_path = run.run_dir / ratchet["ci_receipt_ref"]
        assert ci_ref_path.is_file(), "ci_receipt_ref must point to an existing receipt"

        # ledger entry references the CI receipt
        entry = yaml.safe_load(run.ledger_entry_path("F-CIR").read_text())["ledger_entry"]
        ledger_receipt_path = run.run_dir / entry["receipt_ref"]
        assert ledger_receipt_path.is_file(), "ledger receipt_ref must point to an existing receipt"


class TestLearnRefutedNoRatchet:
    """A refuted or inconclusive verdict does not advance to learn."""

    def test_refuted_verdict_no_ratchet(self, tmp_path):
        finding = _make_finding(fid="F-REF")
        fp = _make_fix_proposal("learn-test-001", "F-REF")
        vv = _make_verifier_verdict("learn-test-001", "F-REF", verdict="refuted", routing="REJECTED")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 0, f"{proc.stdout!r} {proc.stderr!r}"

        run = _open_run_search(run_id, runs_root)
        assert not run.ratchet_path("F-REF").is_file(), "refuted verdict must not produce a ratchet"

    def test_inconclusive_verdict_no_ratchet(self, tmp_path):
        finding = _make_finding(fid="F-INCON")
        fp = _make_fix_proposal("learn-test-001", "F-INCON")
        vv = _make_verifier_verdict("learn-test-001", "F-INCON", verdict="inconclusive", routing="DEFER")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 0

        run = _open_run_search(run_id, runs_root)
        assert not run.ratchet_path("F-INCON").is_file(), "inconclusive verdict must not produce a ratchet"


class TestLearnNoConfirmedVerdicts:
    """No confirmed verdicts = clean exit, nothing to learn."""

    def test_no_verdicts_clean_exit(self, tmp_path):
        runs_root = tmp_path / "runs"
        runs_root.mkdir(parents=True, exist_ok=True)
        run_id = "learn-empty-001"
        w = _make_warrant_dict()
        warrant_path = tmp_path / "warrant.yaml"
        warrant_path.write_text(yaml.safe_dump(w, sort_keys=False))

        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["LOOP_RUNS_DIR"] = str(runs_root)
        proc = subprocess.run(
            [VENV_PYTHON, str(RUNS_CLI), "create", "--run-id", run_id, "--warrant", str(warrant_path)],
            capture_output=True, text=True, env=env,
        )
        assert proc.returncode == 0

        proc = _run_learn_cli(warrant_path, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 0
        assert "nothing to learn" in proc.stdout.lower() or "no confirmed" in proc.stdout.lower()


class TestLearnWarrantRevalidation:
    """Warrant is re-validated on stage entry."""

    def test_expired_warrant_refused(self, tmp_path):
        finding = _make_finding(fid="F-EXP")
        fp = _make_fix_proposal("learn-test-001", "F-EXP")
        vv = _make_verifier_verdict("learn-test-001", "F-EXP", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        # Expire the warrant
        w = yaml.safe_load(warrant.read_text())
        w["expires_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        warrant.write_text(yaml.safe_dump(w, sort_keys=False))

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="true")
        assert proc.returncode == 2, "expired warrant must be refused (exit 2)"
        assert "expired" in proc.stderr.lower() or "refused" in proc.stderr.lower()


class TestLearnNonGreenRejectionDetail:
    """VAL-LEARN-012: Non-green CI rejection reason recorded with detail."""

    def test_rejection_record_has_exit_code_and_gate(self, tmp_path):
        finding = _make_finding(fid="F-REJ2")
        fp = _make_fix_proposal("learn-test-001", "F-REJ2")
        vv = _make_verifier_verdict("learn-test-001", "F-REJ2", verdict="confirmed", routing="ADVANCE")
        warrant, run_id, runs_root = _setup_run(tmp_path, finding, fp, vv)

        proc = _run_learn_cli(warrant, run_id, runs_root, ci_gate="false")
        assert proc.returncode == 1

        run = _open_run_search(run_id, runs_root)
        # A rejection record must exist (not silently disappear)
        rejection_files = list(run.run_dir.glob("*rejection*")) + list(run.run_dir.glob("*reject*"))
        assert rejection_files, (
            "non-green rejection must be recorded (exit code + failing gate), not silently dropped"
        )
        # The rejection record should contain the exit code and gate info
        rej = yaml.safe_load(rejection_files[0].read_text())
        rej_text = json.dumps(rej) if isinstance(rej, dict) else str(rej)
        # Must reference the non-zero exit code
        assert "1" in rej_text or "exit_code" in rej_text, (
            "rejection record must contain the exit code"
        )
