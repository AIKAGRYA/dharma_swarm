"""Tests for scripts/governance/loop/prompt_audit_run.py — Stage 1 (Auditor).

Covers VAL-AUDIT-001..004:
  001  per-prompt audit JSON produced at runs/<run_id>/audit/<prompt_id>.json
  002  schema-invalid output hard-aborts (exit 2), no partial artifact for the invalid prompt
  003  stub backend produces schema-valid audit JSON for every scoped prompt (exit 0)
  004  zero-findings audit is valid (the run continues)
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
AUDIT_RUN_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "prompt_audit_run.py"
VALIDATE_AUDIT_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "validate_audit.py"
RUNS_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "runs.py"

ALL_COUNCILS = [
    "testing_verification",
    "architecture_complexity",
    "runtime_distributed_reliability",
    "ai_slop_prompt_security",
    "governance_evidence_fitness",
]

SENTINELS = ["TV-01", "TV-08", "APS-01", "APS-02", "RDR-10", "GEF-02"]


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


def _future_iso(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_warrant_dict(run_id: str = "warrant-audit-test") -> dict:
    return {
        "id": run_id,
        "issued_by": "orchestrator",
        "authority_level": "medium",
        "trigger": "manual",
        "scope": {
            "base_ref": "origin/main",
            "head_ref": "ratchet/loop-phases-1-3",
            "councils": list(ALL_COUNCILS),
            "prompt_ids": [],
        },
        "write_set": ["scripts/governance/loop/prompt_audit_run.py"],
        "budget": {"max_tokens": 100000, "max_wall_clock_min": 30, "max_fixes_per_run": 5},
        "merge_policy": "propose_only",
        "expires_at": _future_iso(),
    }


def _write_warrant(tmp_path: Path, warrant: dict | None = None) -> Path:
    w = warrant or _make_warrant_dict()
    p = tmp_path / "warrant.yaml"
    p.write_text(yaml.safe_dump(w, sort_keys=False))
    return p


def _make_scope(prompt_ids: list[str] | None = None) -> dict:
    pids = prompt_ids if prompt_ids is not None else list(SENTINELS)
    return {
        "sentinel_prompt_ids": list(SENTINELS),
        "diff_mapped_prompt_ids": [],
        "selected_prompt_ids": pids,
        "council_paths": {},
        "changed_files": [],
        "rationale": [],
        "warrant_councils": list(ALL_COUNCILS),
        "diff_mapped_cap": 5,
    }


def _setup_run(tmp_path: Path, prompt_ids: list[str] | None = None) -> tuple[Path, str]:
    """Create a run dir under a temp runs root and return (warrant_path, run_id)."""
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    run_id = "audit-run-test-001"
    warrant = _write_warrant(tmp_path)
    scope = _make_scope(prompt_ids)

    # Use the runs CLI to create the run dir + manifest.
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    proc = subprocess.run(
        [VENV_PYTHON, str(RUNS_CLI), "create", "--run-id", run_id,
         "--warrant", str(warrant), "--scope", str(_write_scope(tmp_path, scope))],
        capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, f"runs create failed: {proc.stderr!r}"

    # Write scope.json into the run dir.
    run_dir = Path(proc.stdout.strip())
    (run_dir / "scope.json").write_text(json.dumps(scope, indent=2, sort_keys=True) + "\n")
    return warrant, run_id


def _write_scope(tmp_path: Path, scope: dict) -> Path:
    p = tmp_path / "scope.json"
    p.write_text(json.dumps(scope, indent=2, sort_keys=True))
    return p


def _run_audit_cli(
    warrant: Path, run_id: str, runs_root: Path, extra_env: dict | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    env["LOOP_AGENT_BACKEND"] = "stub"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [VENV_PYTHON, str(AUDIT_RUN_CLI), "--warrant", str(warrant), "--run-id", run_id],
        capture_output=True, text=True, env=env,
    )


def _validate_audit(audit_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [VENV_PYTHON, str(VALIDATE_AUDIT_CLI), str(audit_path)],
        capture_output=True, text=True, env=env,
    )


# ---------------------------------------------------------------------------
# VAL-AUDIT-001 + VAL-AUDIT-003: stub backend produces per-prompt valid audits
# ---------------------------------------------------------------------------


def test_stub_backend_produces_audit_per_prompt(tmp_path):
    """VAL-AUDIT-001/003: one schema-valid audit JSON per scoped prompt, exit 0."""
    warrant, run_id = _setup_run(tmp_path)
    runs_root = tmp_path / "runs"

    proc = _run_audit_cli(warrant, run_id, runs_root)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"

    # Locate the run dir and verify one audit JSON per selected prompt.
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["LOOP_RUNS_DIR"] = str(runs_root)
    path_proc = subprocess.run(
        [VENV_PYTHON, str(RUNS_CLI), "path", "--run-id", run_id],
        capture_output=True, text=True, env=env,
    )
    run_dir = Path(path_proc.stdout.strip())
    audit_dir = run_dir / "audit"

    scope = json.loads((run_dir / "scope.json").read_text())
    for pid in scope["selected_prompt_ids"]:
        audit_path = audit_dir / f"{pid}.json"
        assert audit_path.exists(), f"audit JSON missing for prompt {pid}"
        vproc = _validate_audit(audit_path)
        assert vproc.returncode == 0, (
            f"audit for {pid} failed schema validation: {vproc.stdout!r} {vproc.stderr!r}"
        )


def test_stub_backend_exit_zero(tmp_path):
    """VAL-AUDIT-003: with LOOP_AGENT_BACKEND=stub, prompt-audit-run exits 0."""
    warrant, run_id = _setup_run(tmp_path)
    proc = _run_audit_cli(warrant, run_id, tmp_path / "runs")
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"


# ---------------------------------------------------------------------------
# VAL-AUDIT-002: schema-invalid output hard-aborts (exit 2, no partial artifact)
# ---------------------------------------------------------------------------


def test_invalid_backend_output_aborts_with_exit_2(tmp_path):
    """VAL-AUDIT-002: schema-invalid audit output -> exit 2, no artifact for the invalid prompt."""
    from scripts.governance.loop.agent_backend import AgentBackend
    from scripts.governance.loop.prompt_audit_run import run_audit
    from scripts.governance.loop.runs import RunManager
    from scripts.governance.loop.warrant import Warrant

    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        warrant_path = _write_warrant(tmp_path)
        warrant = Warrant.load_and_check(warrant_path)
        run = RunManager.create_run(run_id="invalid-backend-test", warrant=warrant.raw, scope=_make_scope())
        scope = _make_scope()
        (run.run_dir / "scope.json").write_text(json.dumps(scope, indent=2, sort_keys=True) + "\n")

        class InvalidBackend(AgentBackend):
            def audit(self, prompt_id, council_id, prompt_text, context):
                # Missing required fields -> schema-invalid.
                return {"prompt_id": prompt_id, "council_id": council_id}

        rc = run_audit(warrant_path, run, scope, backend=InvalidBackend())
        assert rc == 2, f"expected exit 2 for invalid output, got {rc}"

        # No audit JSON should exist for any prompt (the first invalid one aborts before writing).
        audit_files = list(run.audit_dir.glob("*.json"))
        assert audit_files == [], f"no partial artifacts expected, found: {audit_files}"
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


def test_invalid_output_aborts_no_partial_for_invalid_prompt(tmp_path):
    """VAL-AUDIT-002 variant: a valid prompt followed by an invalid one — the invalid
    prompt's artifact is NOT written, and the run aborts (exit 2)."""
    from scripts.governance.loop.agent_backend import AgentBackend
    from scripts.governance.loop.prompt_audit_run import run_audit
    from scripts.governance.loop.runs import RunManager
    from scripts.governance.loop.warrant import Warrant

    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        warrant_path = _write_warrant(tmp_path)
        warrant = Warrant.load_and_check(warrant_path)
        pids = ["TV-01", "TV-08"]
        scope = _make_scope(prompt_ids=pids)
        run = RunManager.create_run(run_id="mixed-valid-invalid", warrant=warrant.raw, scope=scope)
        (run.run_dir / "scope.json").write_text(json.dumps(scope, indent=2, sort_keys=True) + "\n")

        class MixedBackend(AgentBackend):
            def __init__(self):
                self._call = 0

            def audit(self, prompt_id, council_id, prompt_text, context):
                self._call += 1
                if self._call == 1:
                    # First prompt: valid (stub-like canned output).
                    from scripts.governance.loop.agent_backend import StubBackend
                    return StubBackend().audit(prompt_id, council_id, prompt_text, context)
                # Second prompt: invalid (missing required fields).
                return {"prompt_id": prompt_id}

        rc = run_audit(warrant_path, run, scope, backend=MixedBackend())
        assert rc == 2, f"expected exit 2, got {rc}"

        # The first (valid) prompt's audit may exist; the second (invalid) must NOT.
        assert not (run.audit_dir / "TV-08.json").exists(), (
            "no partial artifact for the invalid prompt (TV-08)"
        )
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# VAL-AUDIT-004: zero-findings audit is valid (run continues)
# ---------------------------------------------------------------------------


def test_zero_findings_audit_is_valid(tmp_path):
    """VAL-AUDIT-004: an audit with findings:[] passes schema validation and the run continues."""
    from scripts.governance.loop.agent_backend import AgentBackend
    from scripts.governance.loop.prompt_audit_run import run_audit
    from scripts.governance.loop.runs import RunManager
    from scripts.governance.loop.warrant import Warrant
    from scripts.governance.loop.validate_audit import validate_audit_doc

    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    os.environ["LOOP_RUNS_DIR"] = str(runs_root)
    try:
        warrant_path = _write_warrant(tmp_path)
        warrant = Warrant.load_and_check(warrant_path)
        scope = _make_scope(prompt_ids=["TV-01"])
        run = RunManager.create_run(run_id="zero-findings-test", warrant=warrant.raw, scope=scope)
        (run.run_dir / "scope.json").write_text(json.dumps(scope, indent=2, sort_keys=True) + "\n")

        class ZeroFindingsBackend(AgentBackend):
            def audit(self, prompt_id, council_id, prompt_text, context):
                from scripts.governance.loop.agent_backend import StubBackend
                doc = StubBackend().audit(prompt_id, council_id, prompt_text, context)
                doc["findings"] = []
                doc["summary"]["verdict"] = "pass"
                return doc

        rc = run_audit(warrant_path, run, scope, backend=ZeroFindingsBackend())
        assert rc == 0, f"zero-findings audit should be valid (exit 0), got {rc}"

        audit_path = run.audit_path("TV-01")
        assert audit_path.exists()
        doc = json.loads(audit_path.read_text())
        assert doc["findings"] == []
        result = validate_audit_doc(doc)
        assert result.valid is True
    finally:
        os.environ.pop("LOOP_RUNS_DIR", None)


# ---------------------------------------------------------------------------
# AgentBackend: StubBackend unit tests
# ---------------------------------------------------------------------------


def test_stub_backend_produces_schema_valid_output():
    """StubBackend.audit() returns a schema-valid audit dict."""
    from scripts.governance.loop.agent_backend import StubBackend
    from scripts.governance.loop.validate_audit import validate_audit_doc

    backend = StubBackend()
    doc = backend.audit("TV-01", "testing_verification", "prompt text", {"repo_path": "/tmp/ds_loop"})
    result = validate_audit_doc(doc)
    assert result.valid is True, f"stub output must be schema-valid: {result.errors}"


def test_stub_backend_output_has_correct_prompt_id():
    """StubBackend fills in the prompt_id and council_id from the invocation."""
    from scripts.governance.loop.agent_backend import StubBackend

    backend = StubBackend()
    doc = backend.audit("APS-01", "ai_slop_prompt_security", "prompt text", {})
    assert doc["prompt_id"] == "APS-01"
    assert doc["council_id"] == "ai_slop_prompt_security"


def test_get_backend_defaults_to_stub():
    """get_backend() with no arg and no env defaults to StubBackend."""
    from scripts.governance.loop.agent_backend import StubBackend, get_backend

    old = os.environ.pop("LOOP_AGENT_BACKEND", None)
    try:
        backend = get_backend()
        assert isinstance(backend, StubBackend)
    finally:
        if old is not None:
            os.environ["LOOP_AGENT_BACKEND"] = old


def test_get_backend_stub_via_env():
    """get_backend() with LOOP_AGENT_BACKEND=stub returns StubBackend."""
    from scripts.governance.loop.agent_backend import StubBackend, get_backend

    old = os.environ.get("LOOP_AGENT_BACKEND")
    os.environ["LOOP_AGENT_BACKEND"] = "stub"
    try:
        assert isinstance(get_backend(), StubBackend)
    finally:
        if old is None:
            os.environ.pop("LOOP_AGENT_BACKEND", None)
        else:
            os.environ["LOOP_AGENT_BACKEND"] = old


def test_get_backend_unimplemented_raises():
    """get_backend() with an unimplemented backend raises a clear error (M2 backends)."""
    from scripts.governance.loop.agent_backend import get_backend

    old = os.environ.get("LOOP_AGENT_BACKEND")
    os.environ["LOOP_AGENT_BACKEND"] = "droid"
    try:
        with pytest.raises((ValueError, NotImplementedError)):
            get_backend()
    finally:
        if old is None:
            os.environ.pop("LOOP_AGENT_BACKEND", None)
        else:
            os.environ["LOOP_AGENT_BACKEND"] = old


# ---------------------------------------------------------------------------
# Warrant re-validation on stage entry
# ---------------------------------------------------------------------------


def test_expired_warrant_aborts_stage_entry(tmp_path):
    """An expired warrant is refused at prompt-audit-run stage entry (exit 2)."""
    _, run_id = _setup_run(tmp_path)
    # Overwrite the warrant with an expired one AFTER setup (so _setup_run
    # doesn't clobber it with a valid warrant).
    expired = _make_warrant_dict()
    expired["expires_at"] = "2020-01-01T00:00:00Z"
    warrant_path = _write_warrant(tmp_path, expired)
    proc = _run_audit_cli(warrant_path, run_id, tmp_path / "runs")
    assert proc.returncode == 2, f"expired warrant should abort (exit 2): {proc.stdout!r}"
    assert "expired" in (proc.stdout + proc.stderr).lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
