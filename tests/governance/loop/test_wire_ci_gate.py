"""Tests for Phase 3 CI ratchet workflow wiring."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from scripts.governance.loop.runs import Run

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = "/Users/dhyana/dharma_swarm/.venv/bin/python"
WIRE_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "wire_ci_gate.py"
LEARN_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "prompt_audit_learn.py"
RUNS_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "runs.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "loop-ratchet-gates.yml"

ALL_COUNCILS = [
    "testing_verification",
    "architecture_complexity",
    "runtime_distributed_reliability",
    "ai_slop_prompt_security",
    "governance_evidence_fitness",
]


def _future_iso(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _workflow_steps(doc: dict) -> list[dict]:
    return doc["jobs"]["loop-ratchet-gates"]["steps"]


def test_default_workflow_file_is_valid_and_has_required_triggers():
    doc = _load_yaml(WORKFLOW)

    assert "jobs" in doc
    assert "loop-ratchet-gates" in doc["jobs"]
    triggers = doc["on"]
    assert "push" in triggers
    assert "pull_request" in triggers
    assert "merge_group" in triggers


def test_default_workflow_has_full_cheap_tier_and_phase0_gates():
    doc = _load_yaml(WORKFLOW)
    step_text = "\n".join(
        f"{step.get('name', '')}\n{step.get('run', '')}" for step in _workflow_steps(doc)
    )

    required = [
        "pytest --collect-only -q --strict-markers",
        "check_hygiene_integrity.py",
        "check_test_hygiene.py",
        "check_module_budget.py",
        "repo_xray.py",
        "make governance-all",
        "Phase-0 F1 marker strictness",
        "Phase-0 F2 property collection",
        "Phase-0 F3 importorskip allowlist",
    ]
    for needle in required:
        assert needle in step_text


def test_wire_ci_gate_adds_new_gate_step(tmp_path):
    workflow = tmp_path / "loop-ratchet-gates.yml"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)

    proc = subprocess.run(
        [
            VENV_PYTHON,
            str(WIRE_CLI),
            "--workflow",
            str(workflow),
            "--gate-id",
            "F-NEW-GATE",
            "--name",
            "New gate",
            "--run",
            "python scripts/governance/new_gate.py",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode == 0, proc.stderr
    doc = _load_yaml(workflow)
    steps = _workflow_steps(doc)
    assert any(step.get("id") == "ratchet_f_new_gate" for step in steps)
    assert any(step.get("run") == "python scripts/governance/new_gate.py" for step in steps)


def test_wire_ci_gate_validates_yaml_after_write_and_fails_on_malformed(tmp_path):
    workflow = tmp_path / "broken.yml"
    workflow.write_text("name: broken\n'on': [\n")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)

    proc = subprocess.run(
        [
            VENV_PYTHON,
            str(WIRE_CLI),
            "--workflow",
            str(workflow),
            "--gate-id",
            "F-BROKEN",
            "--name",
            "Broken gate",
            "--run",
            "true",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode == 2
    assert "YAML" in proc.stderr or "yaml" in proc.stderr


def _make_warrant_dict() -> dict:
    return {
        "id": "wire-learn-test",
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


def _make_finding() -> dict:
    return {
        "finding_id": "F-WIRE-CI",
        "prompt_id": "TV-01",
        "council_id": "testing_verification",
        "title": "wire CI finding",
        "severity": "medium",
        "evidence_level": "E2_tested",
        "failure_class": "WIRE_CI_FINDING",
        "routing": "IMPLEMENT",
        "must_gate": True,
        "recurrence_score": 2,
        "recurrence_within_run": True,
        "files": ["scripts/governance/loop/wire_ci_gate.py"],
        "observed": "wire_ci_gate must be connected to learn",
        "recommendation": "wire gate into CI",
        "audit_path": "audit/TV-01.json",
    }


def _make_fix_proposal(run_id: str) -> dict:
    return {
        "fix_proposal": {
            "run_id": run_id,
            "finding_id": "F-WIRE-CI",
            "write_set_used": ["scripts/governance/loop/**"],
            "patch_ref": "fix/F-WIRE-CI",
            "red_before": {"command": "true", "exit_code": 1, "key_output": "red"},
            "green_after": {"command": "true", "exit_code": 0, "key_output": "green"},
            "proof_mode": "synthetic",
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


def _make_verdict(run_id: str) -> dict:
    return {
        "verifier_verdict": {
            "run_id": run_id,
            "finding_id": "F-WIRE-CI",
            "verifier_model": "stub",
            "model_independence": "not_proven",
            "falsification_attempts": [
                {"attempt": "check red/green", "result": "pass", "evidence": "exit codes"}
            ],
            "anti_gaming_checklist": {},
            "verdict": "confirmed",
            "evidence": [],
            "routing": "ADVANCE",
        }
    }


def test_prompt_audit_learn_wire_ci_flag_updates_workflow(tmp_path):
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    run_id = "wire-learn-001"
    warrant = tmp_path / "warrant.yaml"
    warrant.write_text(yaml.safe_dump(_make_warrant_dict(), sort_keys=False))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)

    proc = subprocess.run(
        [VENV_PYTHON, str(RUNS_CLI), "create", "--run-id", run_id, "--warrant", str(warrant)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr

    run = Run(Path(proc.stdout.strip()))
    finding = _make_finding()
    run.write_jsonl(run.accepted_findings_path(), [finding])
    run.write_yaml(run.fix_proposal_path("F-WIRE-CI"), _make_fix_proposal(run_id))
    run.write_yaml(run.verifier_verdict_path("F-WIRE-CI"), _make_verdict(run_id))

    workflow = tmp_path / "loop-ratchet-gates.yml"
    proc = subprocess.run(
        [
            VENV_PYTHON,
            str(LEARN_CLI),
            "--warrant",
            str(warrant),
            "--run-id",
            run_id,
            "--ci-gate",
            "true",
            "--wire-ci",
            "--ci-workflow",
            str(workflow),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode == 0, proc.stderr
    doc = _load_yaml(workflow)
    assert any(step.get("id") == "ratchet_f_wire_ci" for step in _workflow_steps(doc))
    assert list(run.receipts_dir.glob("ci_wire_receipt_F-WIRE-CI.json"))
