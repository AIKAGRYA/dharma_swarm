"""Tests for scripts/governance/loop/runs.py — runs/YYYY-WW/<run_id>/ orchestration.

Covers VAL-RUNS-001..004:
  001  run dir structure created (audit, fixes, verdicts, ratchet, ledger, receipts)
  002  manifest.json written (warrant ref, scope, findings, gates, DoD checklist)
  003  stages read/write from run dir, chaining correctly
  004  runs root configurable via LOOP_RUNS_DIR env var
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = sys.executable
RUNS_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "runs.py"

DEFAULT_RUNS_ROOT = "/Users/dhyana/Desktop/complexity_code_testing_prompts/runs"

REQUIRED_SUBDIRS = ("audit", "fixes", "verdicts", "ratchet", "ledger", "receipts")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run_cli(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run the runs.py CLI with PYTHONPATH=. and return the completed process."""
    full_env = os.environ.copy()
    full_env["PYTHONPATH"] = str(REPO_ROOT)
    if env:
        full_env.update(env)
    return subprocess.run(
        [VENV_PYTHON, str(RUNS_CLI), *args],
        capture_output=True,
        text=True,
        env=full_env,
    )


def _make_warrant_dict(run_id: str = "warrant-test-001") -> dict:
    future = (datetime.now(timezone.utc) + timedelta_days(7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": run_id,
        "issued_by": "orchestrator",
        "authority_level": "medium",
        "trigger": "manual",
        "scope": {
            "base_ref": "origin/main",
            "head_ref": "ratchet/loop-phases-1-3",
            "councils": ["testing_verification"],
            "prompt_ids": ["TV-01"],
        },
        "write_set": ["scripts/governance/loop/runs.py", "tests/governance/loop/test_runs.py"],
        "budget": {"max_tokens": 100000, "max_wall_clock_min": 30, "max_fixes_per_run": 5},
        "merge_policy": "propose_only",
        "expires_at": future,
    }


def timedelta_days(days: int):
    from datetime import timedelta

    return timedelta(days=days)


def _write_warrant(tmp_path: Path, warrant: dict | None = None) -> Path:
    w = warrant or _make_warrant_dict()
    p = tmp_path / "warrant.yaml"
    p.write_text(yaml.safe_dump(w, sort_keys=False))
    return p


def _import_runs():
    """Import the runs module fresh (so env overrides take effect per-test)."""
    import importlib

    mod = importlib.import_module("scripts.governance.loop.runs")
    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# VAL-RUNS-001: run dir structure created
# ---------------------------------------------------------------------------


class TestRunDirStructure:
    """VAL-RUNS-001: runs.py creates runs/YYYY-WW/<run_id>/ with subdirs."""

    def test_create_run_makes_all_subdirs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="test-run-001")
        assert run.run_dir.is_dir()
        for sub in REQUIRED_SUBDIRS:
            assert (run.run_dir / sub).is_dir(), f"missing subdir: {sub}"

    def test_create_run_under_week_bucket(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="test-run-002")
        # run_dir parent must be a YYYY-WW bucket under the runs root
        week_bucket = run.run_dir.parent.name
        assert week_bucket == runs.current_week_bucket()
        assert run.run_dir.parent.parent == tmp_path

    def test_create_run_id_single_use_by_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="test-run-003")
        with pytest.raises(FileExistsError):
            runs.RunManager.create_run(run_id="test-run-003")
        for sub in REQUIRED_SUBDIRS:
            assert (run.run_dir / sub).is_dir()

    def test_create_run_resume_existing_requires_explicit_flag(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="test-run-resume")
        marker = run.audit_dir / "stale.json"
        marker.write_text("{}\n")
        resumed = runs.RunManager.create_run(run_id="test-run-resume", resume=True)
        assert resumed.run_dir == run.run_dir
        assert marker.exists(), "resume mode may keep existing artifacts"

    def test_cli_create_subdirs(self, tmp_path):
        env = {"LOOP_RUNS_DIR": str(tmp_path)}
        res = _run_cli("create", "--run-id", "cli-run-001", env=env)
        assert res.returncode == 0, res.stderr
        # locate the created run dir
        week = res.stdout.strip().split("/")[-2] if "/" in res.stdout.strip() else None
        # The CLI prints the run dir path; find it under tmp_path
        run_dirs = list(tmp_path.glob("*/*"))
        assert len(run_dirs) >= 1
        created = tmp_path / "cli-run-001"
        # search for the run_id dir
        found = list(tmp_path.rglob("cli-run-001"))
        assert found, f"run dir not created under {tmp_path}"
        for sub in REQUIRED_SUBDIRS:
            assert (found[0] / sub).is_dir(), f"CLI missing subdir: {sub}"

    def test_cli_create_duplicate_requires_resume(self, tmp_path):
        env = {"LOOP_RUNS_DIR": str(tmp_path)}
        first = _run_cli("create", "--run-id", "cli-run-dupe", env=env)
        assert first.returncode == 0, first.stderr
        second = _run_cli("create", "--run-id", "cli-run-dupe", env=env)
        assert second.returncode == 2
        assert "already exists" in second.stderr
        resumed = _run_cli("create", "--run-id", "cli-run-dupe", "--resume", env=env)
        assert resumed.returncode == 0, resumed.stderr


# ---------------------------------------------------------------------------
# VAL-RUNS-002: manifest.json written
# ---------------------------------------------------------------------------


class TestManifest:
    """VAL-RUNS-002: manifest.json with warrant ref, scope, findings, gates, DoD checklist."""

    def test_manifest_written_on_create(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        warrant = _make_warrant_dict()
        scope = {
            "sentinel_prompt_ids": ["TV-01"],
            "selected_prompt_ids": ["TV-01"],
            "changed_files": [],
        }
        run = runs.RunManager.create_run(
            run_id="manifest-run-001",
            warrant= warrant,
            scope=scope,
        )
        manifest_path = run.run_dir / "manifest.json"
        assert manifest_path.is_file()
        manifest = json.loads(manifest_path.read_text())
        # required top-level fields
        assert manifest["run_id"] == "manifest-run-001"
        assert "warrant" in manifest
        assert manifest["warrant"]["id"] == "warrant-test-001"
        assert "scope" in manifest
        assert "findings" in manifest
        assert "gates" in manifest
        assert "dod_checklist" in manifest
        assert "timestamps" in manifest
        assert "created_utc" in manifest["timestamps"]

    def test_manifest_warrant_ref_records_authority_and_refs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        warrant = _make_warrant_dict()
        run = runs.RunManager.create_run(run_id="manifest-run-002", warrant=warrant)
        manifest = run.read_manifest()
        assert manifest["warrant"]["id"] == warrant["id"]
        assert manifest["warrant"]["authority_level"] == warrant["authority_level"]
        assert manifest["warrant"]["merge_policy"] == "propose_only"

    def test_manifest_findings_and_gates_updatable(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="manifest-run-003")
        run.add_finding("F-001")
        run.add_gate({"finding": "F-001", "class": "MARKER_DRIFT", "proof_mode": "natural"})
        manifest = run.read_manifest()
        assert "F-001" in manifest["findings"]
        assert any(g["finding"] == "F-001" for g in manifest["gates"])

    def test_manifest_dod_checklist_settable(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="manifest-run-004")
        run.set_dod_checklist({"1_subdirs_created": "met", "2_manifest_written": "met"})
        manifest = run.read_manifest()
        assert manifest["dod_checklist"]["1_subdirs_created"] == "met"

    def test_manifest_updated_utc_on_update(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="manifest-run-005")
        first = run.read_manifest()["timestamps"]["created_utc"]
        run.add_finding("F-X")
        second = run.read_manifest()
        assert "updated_utc" in second["timestamps"]


# ---------------------------------------------------------------------------
# VAL-RUNS-003: stages read/write from run dir, chaining correctly
# ---------------------------------------------------------------------------


class TestStageIO:
    """VAL-RUNS-003: stage I/O helpers chain artifacts through the run dir."""

    def test_audit_write_and_read_back(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="io-run-001")
        audit_path = run.audit_path("TV-01")
        assert audit_path.parent.name == "audit"
        audit_doc = {"prompt_id": "TV-01", "findings": []}
        run.write_json(audit_path, audit_doc)
        assert audit_path.is_file()
        loaded = run.read_json(audit_path)
        assert loaded == audit_doc

    def test_list_audits_returns_all(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="io-run-002")
        for pid in ("TV-01", "TV-08", "APS-01"):
            run.write_json(run.audit_path(pid), {"prompt_id": pid, "findings": []})
        audits = run.list_audits()
        assert len(audits) == 3
        ids = sorted(json.loads(p.read_text())["prompt_id"] for p in audits)
        assert ids == ["APS-01", "TV-01", "TV-08"]

    def test_stage_chain_artifacts_in_sequence(self, tmp_path, monkeypatch):
        """Stage N reads stage N-1's output from the run dir (chaining)."""
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="io-chain-001")

        # Stage 1 -> audit
        run.write_json(run.audit_path("TV-01"), {"prompt_id": "TV-01", "findings": [{"id": "F-1"}]})
        # Stage 2 -> accepted_findings (reads audits)
        audits = run.list_audits()
        assert len(audits) == 1
        run.write_jsonl(run.accepted_findings_path(), [{"id": "F-1", "routing": "IMPLEMENT"}])
        # Stage 3 -> fix_proposal (reads accepted_findings)
        af = run.read_jsonl(run.accepted_findings_path())
        assert af[0]["id"] == "F-1"
        run.write_yaml(run.fix_proposal_path("F-1"), {"finding_id": "F-1", "proof_mode": "natural"})
        # Stage 4 -> verifier_verdict (reads fix_proposal)
        fp = run.read_yaml(run.fix_proposal_path("F-1"))
        assert fp["finding_id"] == "F-1"
        run.write_yaml(run.verifier_verdict_path("F-1"), {"finding_id": "F-1", "verdict": "confirmed"})
        # Stage 5 -> ratchet + ledger (reads verdict)
        vv = run.read_yaml(run.verifier_verdict_path("F-1"))
        assert vv["verdict"] == "confirmed"
        run.write_yaml(run.ratchet_path("F-1"), {"finding_id": "F-1", "new_gate": {"kind": "ci_gate"}})
        run.write_yaml(run.ledger_entry_path("F-1"), {"finding_class": "MARKER_DRIFT", "status": "gated"})

        # All artifacts present in the run dir
        assert run.audit_path("TV-01").is_file()
        assert run.accepted_findings_path().is_file()
        assert run.fix_proposal_path("F-1").is_file()
        assert run.verifier_verdict_path("F-1").is_file()
        assert run.ratchet_path("F-1").is_file()
        assert run.ledger_entry_path("F-1").is_file()
        # ledger entry is under the ledger subdir
        assert run.ledger_entry_path("F-1").parent.name == "ledger"
        # ratchet under ratchet subdir
        assert run.ratchet_path("F-1").parent.name == "ratchet"
        # fix_proposal under fixes subdir
        assert run.fix_proposal_path("F-1").parent.name == "fixes"
        # verdict under verdicts subdir
        assert run.verifier_verdict_path("F-1").parent.name == "verdicts"

    def test_receipt_path_under_receipts_subdir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="io-run-003")
        rp = run.receipt_path("ci_receipt_green.txt")
        assert rp.parent.name == "receipts"
        rp.write_text("EXIT=0\n")
        assert rp.is_file()

    def test_scope_path_at_run_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="io-run-004")
        sp = run.scope_path()
        assert sp.parent == run.run_dir
        run.write_json(sp, {"selected_prompt_ids": ["TV-01"]})
        assert sp.is_file()


# ---------------------------------------------------------------------------
# VAL-RUNS-004: runs root configurable via LOOP_RUNS_DIR
# ---------------------------------------------------------------------------


class TestRunsRootConfig:
    """VAL-RUNS-004: LOOP_RUNS_DIR overrides the default runs root."""

    def test_default_runs_root_is_desktop_suite(self, monkeypatch):
        monkeypatch.delenv("LOOP_RUNS_DIR", raising=False)
        runs = _import_runs()
        assert runs.runs_root() == DEFAULT_RUNS_ROOT

    def test_env_var_overrides_runs_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        assert runs.runs_root() == str(tmp_path)

    def test_create_run_uses_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        run = runs.RunManager.create_run(run_id="env-run-001")
        assert str(run.run_dir).startswith(str(tmp_path))

    def test_cli_respects_env_override(self, tmp_path):
        env = {"LOOP_RUNS_DIR": str(tmp_path)}
        res = _run_cli("create", "--run-id", "env-cli-run-001", env=env)
        assert res.returncode == 0, res.stderr
        found = list(tmp_path.rglob("env-cli-run-001"))
        assert found, "run dir not created under override root"
        # and NOT under the default root
        assert not (Path(DEFAULT_RUNS_ROOT) / "env-cli-run-001").exists()

    def test_open_existing_run_via_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOOP_RUNS_DIR", str(tmp_path))
        runs = _import_runs()
        created = runs.RunManager.create_run(run_id="reopen-run-001")
        # open by run_id only (resolves the week bucket)
        reopened = runs.RunManager.open_run("reopen-run-001")
        assert reopened.run_dir == created.run_dir


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


class TestCLISmoke:
    def test_help_exits_zero(self):
        res = _run_cli("--help")
        assert res.returncode == 0
        assert "runs" in res.stdout.lower() or "usage" in res.stdout.lower()

    def test_create_help(self):
        res = _run_cli("create", "--help")
        assert res.returncode == 0

    def test_path_help(self):
        res = _run_cli("path", "--help")
        assert res.returncode == 0

    def test_cli_path_prints_run_dir(self, tmp_path):
        env = {"LOOP_RUNS_DIR": str(tmp_path)}
        _run_cli("create", "--run-id", "path-run-001", env=env)
        res = _run_cli("path", "--run-id", "path-run-001", env=env)
        assert res.returncode == 0, res.stderr
        assert "path-run-001" in res.stdout
