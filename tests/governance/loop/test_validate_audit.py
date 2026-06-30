"""Tests for scripts/governance/loop/validate_audit.py — the hard run-abort gate.

Covers VAL-SCHEMA-001..004 (valid audit passes; invalid JSON aborts with exit 2
and a structured error; missing required field fails; invalid enum fails) and
VAL-AUDIT-004 (zero-findings audit is valid).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = "/Users/dhyana/dharma_swarm/.venv/bin/python"
VALIDATE_AUDIT = REPO_ROOT / "scripts" / "governance" / "loop" / "validate_audit.py"
SCHEMA_PATH = REPO_ROOT / "schemas" / "expert_audit_output.schema.json"

# A minimal schema-conformant audit document used as the green-path baseline.
VALID_AUDIT = {
    "prompt_id": "TV-01",
    "council_id": "testing_verification",
    "run_id": "run-test-001",
    "operator": "tester",
    "model": "stub",
    "repo_path": "/tmp/ds_loop",
    "git_ref": "ratchet/loop-phases-1-3",
    "timestamp_utc": "2026-06-26T00:00:00Z",
    "mode": "weekly",
    "scope": {
        "files_examined": ["tests/conftest.py"],
        "commands_run": [
            {"command": "pytest --collect-only -q", "cwd": "/tmp/ds_loop", "exit_code": 0, "key_output": "100 tests"}
        ],
        "commands_not_run": [
            {"command": "pytest -x", "reason": "out of scope"}
        ],
    },
    "summary": {"verdict": "pass", "confidence": "high", "evidence_floor": "E2_tested"},
    "findings": [
        {
            "id": "F-001",
            "title": "Collection drift",
            "severity": "medium",
            "evidence_level": "E2_tested",
            "confidence": "high",
            "files": ["tests/conftest.py"],
            "line_refs": ["10"],
            "observed": "two skipped tests",
            "inferred": "masking a green illusion",
            "risk": "false green",
            "failure_class": "GREEN_SUITE_FROM_SKIPS",
            "recommendation": "remove skips",
            "verification": "re-run without skips",
            "evidence_refs": [0],
        }
    ],
    "not_proven": [],
    "open_questions": [],
    "follow_up_issues": [],
}


def _run_cli(audit_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [VENV_PYTHON, str(VALIDATE_AUDIT), str(audit_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
    )


def _write_audit(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "audit.json"
    p.write_text(json.dumps(doc))
    return p


def test_schema_file_exists_and_is_valid_json_schema():
    assert SCHEMA_PATH.exists(), "ported schema must exist in the repo"
    import jsonschema

    with SCHEMA_PATH.open() as f:
        schema = json.load(f)
    jsonschema.Draft202012Validator.check_schema(schema)


# --- importable function (unit-level) ---


def test_validate_audit_function_returns_ok_for_valid_doc(tmp_path):
    from scripts.governance.loop.validate_audit import validate_audit_doc

    result = validate_audit_doc(VALID_AUDIT)
    assert result.valid is True
    assert result.errors == []


def test_validate_audit_function_reports_invalid_enum(tmp_path):
    from scripts.governance.loop.validate_audit import validate_audit_doc

    bad = json.loads(json.dumps(VALID_AUDIT))
    bad["findings"][0]["severity"] = "catastrophic"  # not in enum
    result = validate_audit_doc(bad)
    assert result.valid is False
    assert result.errors, "structured errors must be populated"
    joined = json.dumps(result.errors)
    assert "severity" in joined or "catastrophic" in joined


# --- CLI black-box exit codes (matches VAL-SCHEMA-001..004, VAL-AUDIT-004) ---


def test_cli_valid_audit_exits_zero(tmp_path):
    audit = _write_audit(tmp_path, VALID_AUDIT)
    proc = _run_cli(audit)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"


def test_cli_zero_findings_audit_exits_zero(tmp_path):
    zero = json.loads(json.dumps(VALID_AUDIT))
    zero["findings"] = []
    zero["summary"]["evidence_floor"] = "E0_none"
    zero["scope"]["commands_run"] = []
    audit = _write_audit(tmp_path, zero)
    proc = _run_cli(audit)
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"


def test_cli_wrong_type_field_exits_two_with_structured_error(tmp_path):
    bad = json.loads(json.dumps(VALID_AUDIT))
    bad["findings"] = "not-an-array"  # wrong type
    audit = _write_audit(tmp_path, bad)
    proc = _run_cli(audit)
    assert proc.returncode == 2, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    out = proc.stdout + proc.stderr
    # structured error: JSON object or a clear field path
    assert "findings" in out, f"error must name the violating field: {out!r}"


def test_cli_missing_required_field_exits_two(tmp_path):
    bad = json.loads(json.dumps(VALID_AUDIT))
    del bad["findings"]  # missing required top-level field
    audit = _write_audit(tmp_path, bad)
    proc = _run_cli(audit)
    assert proc.returncode == 2, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    out = proc.stdout + proc.stderr
    assert "findings" in out, f"error must name the missing field: {out!r}"


def test_cli_invalid_severity_enum_exits_two(tmp_path):
    bad = json.loads(json.dumps(VALID_AUDIT))
    bad["findings"][0]["severity"] = "trivial"  # not low|medium|high|critical
    audit = _write_audit(tmp_path, bad)
    proc = _run_cli(audit)
    assert proc.returncode == 2, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    out = proc.stdout + proc.stderr
    assert "severity" in out or "trivial" in out, f"error must name the enum field: {out!r}"


def test_cli_invalid_evidence_level_enum_exits_two(tmp_path):
    bad = json.loads(json.dumps(VALID_AUDIT))
    bad["findings"][0]["evidence_level"] = "E5_imagined"  # not E0..E4
    audit = _write_audit(tmp_path, bad)
    proc = _run_cli(audit)
    assert proc.returncode == 2, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    out = proc.stdout + proc.stderr
    assert "evidence_level" in out or "E5_imagined" in out, f"error must name the enum field: {out!r}"


def test_e2_summary_requires_command_receipt(tmp_path):
    """E2+ summary floors cannot claim tested evidence without commands_run."""
    bad = json.loads(json.dumps(VALID_AUDIT))
    bad["scope"]["commands_run"] = []
    audit = _write_audit(tmp_path, bad)
    proc = _run_cli(audit)
    assert proc.returncode == 2
    out = proc.stdout + proc.stderr
    assert "commands_run" in out and "evidence_floor" in out


def test_e2_finding_requires_evidence_refs(tmp_path):
    """E2+ findings must bind to replayable command receipts."""
    bad = json.loads(json.dumps(VALID_AUDIT))
    bad["findings"][0].pop("evidence_refs")
    audit = _write_audit(tmp_path, bad)
    proc = _run_cli(audit)
    assert proc.returncode == 2
    out = proc.stdout + proc.stderr
    assert "evidence_refs" in out


def test_e2_finding_rejects_out_of_range_evidence_ref(tmp_path):
    bad = json.loads(json.dumps(VALID_AUDIT))
    bad["findings"][0]["evidence_refs"] = [99]
    audit = _write_audit(tmp_path, bad)
    proc = _run_cli(audit)
    assert proc.returncode == 2
    out = proc.stdout + proc.stderr
    assert "evidence_refs" in out or "commands_run" in out


@pytest.mark.parametrize(
    "field",
    ["confidence", "files", "line_refs", "inferred", "risk", "failure_class", "verification"],
)
def test_finding_architecture_fields_required(tmp_path, field):
    bad = json.loads(json.dumps(VALID_AUDIT))
    bad["findings"][0].pop(field)
    audit = _write_audit(tmp_path, bad)
    proc = _run_cli(audit)
    assert proc.returncode == 2
    out = proc.stdout + proc.stderr
    assert field in out


def test_cli_missing_file_exits_two(tmp_path):
    proc = _run_cli(tmp_path / "does-not-exist.json")
    assert proc.returncode == 2
    out = proc.stdout + proc.stderr
    assert "exist" in out.lower() or "not found" in out.lower() or "no such" in out.lower(), out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
