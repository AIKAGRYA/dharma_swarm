"""Tests for scripts/governance/loop/warrant.py — spec §4 warrant parser/validator/enforcer.

Covers VAL-WARRANT-001..008:
  001  valid warrant accepted (exit 0)
  002  expired warrant refused (non-zero + expired message)
  003  non-propose_only merge_policy refused (non-zero)
  004  write-set violation caught (file outside write_set = rejected, non-zero + path)
  005  missing required field fails (non-zero + named field)
  006  budget exceeded at runtime aborted (non-zero; excess deferred)
  007  re-validated on every stage entry (mid-run expiry refused at next stage)
  008  invalid authority_level enum fails (non-zero + enum error)
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = "/Users/dhyana/dharma_swarm/.venv/bin/python"
WARRANT_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "warrant.py"

REQUIRED_FIELDS = [
    "id",
    "issued_by",
    "authority_level",
    "trigger",
    "scope",
    "write_set",
    "budget",
    "merge_policy",
    "expires_at",
]

VALID_WARRANT: dict = {
    "id": "warrant-test-001",
    "issued_by": "orchestrator",
    "authority_level": "medium",
    "trigger": "manual",
    "scope": {
        "base_ref": "origin/main",
        "head_ref": "ratchet/loop-phases-1-3",
        "councils": ["testing_verification"],
        "prompt_ids": ["TV-01"],
    },
    "write_set": [
        "scripts/governance/loop/warrant.py",
        "tests/governance/loop/test_warrant.py",
    ],
    "budget": {
        "max_tokens": 100000,
        "max_wall_clock_min": 30,
        "max_fixes_per_run": 5,
    },
    "merge_policy": "propose_only",
    "expires_at": "2099-01-01T00:00:00Z",
}


def _write_warrant(tmp_path: Path, doc: dict, name: str = "warrant.yaml") -> Path:
    p = tmp_path / name
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    return p


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [VENV_PYTHON, str(WARRANT_CLI), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"},
    )


# ---------------------------------------------------------------------------
# Structural validation (importable)
# ---------------------------------------------------------------------------


def test_from_yaml_valid_warrant_returns_warrant(tmp_path):
    from scripts.governance.loop.warrant import Warrant

    p = _write_warrant(tmp_path, VALID_WARRANT)
    w = Warrant.from_yaml(p)
    assert w.id == "warrant-test-001"
    assert w.authority_level == "medium"
    assert w.merge_policy == "propose_only"
    assert w.write_set == [
        "scripts/governance/loop/warrant.py",
        "tests/governance/loop/test_warrant.py",
    ]
    assert w.budget["max_fixes_per_run"] == 5


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_field_raises_naming_field(tmp_path, field):
    from scripts.governance.loop.warrant import Warrant, WarrantValidationError

    bad = {**VALID_WARRANT}
    del bad[field]
    p = _write_warrant(tmp_path, bad)
    with pytest.raises(WarrantValidationError) as exc:
        Warrant.from_yaml(p)
    assert field in str(exc.value), f"error must name the missing field {field!r}: {exc.value!r}"


def test_invalid_authority_level_enum_raises(tmp_path):
    from scripts.governance.loop.warrant import Warrant, WarrantValidationError

    bad = {**VALID_WARRANT, "authority_level": "omnipotent"}
    p = _write_warrant(tmp_path, bad)
    with pytest.raises(WarrantValidationError) as exc:
        Warrant.from_yaml(p)
    msg = str(exc.value)
    assert "authority_level" in msg or "omnipotent" in msg, f"must name the enum field: {msg!r}"


def test_non_propose_only_merge_policy_raises(tmp_path):
    from scripts.governance.loop.warrant import Warrant, WarrantValidationError

    bad = {**VALID_WARRANT, "merge_policy": "auto_merge"}
    p = _write_warrant(tmp_path, bad)
    with pytest.raises(WarrantValidationError) as exc:
        Warrant.from_yaml(p)
    msg = str(exc.value)
    assert "merge_policy" in msg or "propose_only" in msg, f"must name merge_policy: {msg!r}"


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------


def test_is_expired_false_for_future_expiry(tmp_path):
    from scripts.governance.loop.warrant import Warrant

    p = _write_warrant(tmp_path, VALID_WARRANT)
    w = Warrant.from_yaml(p)
    assert w.is_expired() is False


def test_is_expired_true_for_past_expiry(tmp_path):
    from scripts.governance.loop.warrant import Warrant

    bad = {**VALID_WARRANT, "expires_at": "2000-01-01T00:00:00Z"}
    p = _write_warrant(tmp_path, bad)
    w = Warrant.from_yaml(p)
    assert w.is_expired() is True


def test_load_and_check_refuses_expired_warrant(tmp_path):
    from scripts.governance.loop.warrant import Warrant, WarrantExpiredError

    bad = {**VALID_WARRANT, "expires_at": "2000-01-01T00:00:00Z"}
    p = _write_warrant(tmp_path, bad)
    with pytest.raises(WarrantExpiredError):
        Warrant.load_and_check(p)


def test_load_and_check_accepts_unexpired_warrant(tmp_path):
    from scripts.governance.loop.warrant import Warrant

    p = _write_warrant(tmp_path, VALID_WARRANT)
    w = Warrant.load_and_check(p)
    assert w.id == "warrant-test-001"


# ---------------------------------------------------------------------------
# Write-set enforcement
# ---------------------------------------------------------------------------


def test_assert_write_set_accepts_in_set_path(tmp_path):
    from scripts.governance.loop.warrant import Warrant

    p = _write_warrant(tmp_path, VALID_WARRANT)
    w = Warrant.from_yaml(p)
    # should not raise
    w.assert_write_set("scripts/governance/loop/warrant.py")
    w.assert_write_set("tests/governance/loop/test_warrant.py")


def test_assert_write_set_rejects_out_of_set_path(tmp_path):
    from scripts.governance.loop.warrant import Warrant, WriteSetViolationError

    p = _write_warrant(tmp_path, VALID_WARRANT)
    w = Warrant.from_yaml(p)
    with pytest.raises(WriteSetViolationError) as exc:
        w.assert_write_set("dharma_swarm/secret.py")
    assert "dharma_swarm/secret.py" in str(exc.value), "must name the violating path"


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


def test_check_budget_under_limit_ok(tmp_path):
    from scripts.governance.loop.warrant import Warrant

    p = _write_warrant(tmp_path, VALID_WARRANT)
    w = Warrant.from_yaml(p)
    res = w.check_budget(used_fixes=3, used_tokens=1000, used_wall_clock_min=10)
    assert res.exceeded is False


def test_check_budget_max_fixes_exceeded(tmp_path):
    from scripts.governance.loop.warrant import Warrant

    p = _write_warrant(tmp_path, VALID_WARRANT)
    w = Warrant.from_yaml(p)
    res = w.check_budget(used_fixes=6, used_tokens=0, used_wall_clock_min=0)
    assert res.exceeded is True
    assert "max_fixes_per_run" in res.reason or "fixes" in res.reason.lower()


def test_check_budget_max_tokens_exceeded(tmp_path):
    from scripts.governance.loop.warrant import Warrant

    p = _write_warrant(tmp_path, VALID_WARRANT)
    w = Warrant.from_yaml(p)
    res = w.check_budget(used_fixes=0, used_tokens=200000, used_wall_clock_min=0)
    assert res.exceeded is True
    assert "max_tokens" in res.reason or "tokens" in res.reason.lower()


def test_check_budget_max_wall_clock_exceeded(tmp_path):
    from scripts.governance.loop.warrant import Warrant

    p = _write_warrant(tmp_path, VALID_WARRANT)
    w = Warrant.from_yaml(p)
    res = w.check_budget(used_fixes=0, used_tokens=0, used_wall_clock_min=31)
    assert res.exceeded is True
    assert "max_wall_clock_min" in res.reason or "wall" in res.reason.lower()


# ---------------------------------------------------------------------------
# Mid-run re-validation (VAL-WARRANT-007)
# ---------------------------------------------------------------------------


def test_mid_run_expiry_refused_at_next_stage_entry(tmp_path):
    """A warrant that was valid at trigger time but expires mid-run is refused
    when load_and_check is called at the next stage entry."""
    from scripts.governance.loop.warrant import Warrant, WarrantExpiredError

    # warrant valid now but expires in 1 second
    soon = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    doc = {**VALID_WARRANT, "expires_at": soon}
    p = _write_warrant(tmp_path, doc)

    # stage 1 entry: valid
    w = Warrant.load_and_check(p)
    assert w.id == "warrant-test-001"

    # wait until it expires
    import time

    time.sleep(1.5)

    # stage 2 entry: refused (mid-run expiry)
    with pytest.raises(WarrantExpiredError):
        Warrant.load_and_check(p)


# ---------------------------------------------------------------------------
# CLI black-box (matches VAL-WARRANT-001..008)
# ---------------------------------------------------------------------------


def test_cli_valid_warrant_exits_zero(tmp_path):
    """VAL-WARRANT-001: valid warrant accepted (exit 0)."""
    p = _write_warrant(tmp_path, VALID_WARRANT)
    proc = _run_cli(["validate", str(p)])
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"


def test_cli_expired_warrant_refused_nonzero_with_expired_message(tmp_path):
    """VAL-WARRANT-002: expired warrant refused (non-zero + expired message)."""
    bad = {**VALID_WARRANT, "expires_at": "2000-01-01T00:00:00Z"}
    p = _write_warrant(tmp_path, bad)
    proc = _run_cli(["validate", str(p)])
    assert proc.returncode != 0, f"must not exit 0: {proc.stdout!r}"
    out = (proc.stdout + proc.stderr).lower()
    assert "expired" in out, f"must contain an expired message: {out!r}"


def test_cli_non_propose_only_refused_nonzero(tmp_path):
    """VAL-WARRANT-003: non-propose_only merge_policy refused (non-zero)."""
    bad = {**VALID_WARRANT, "merge_policy": "auto_merge"}
    p = _write_warrant(tmp_path, bad)
    proc = _run_cli(["validate", str(p)])
    assert proc.returncode != 0, f"must not exit 0: {proc.stdout!r}"
    out = proc.stdout + proc.stderr
    assert "merge_policy" in out.lower() or "propose_only" in out.lower(), f"must name merge_policy: {out!r}"


def test_cli_write_set_violation_rejected_nonzero_with_path(tmp_path):
    """VAL-WARRANT-004: a file outside write_set is rejected (non-zero + path)."""
    p = _write_warrant(tmp_path, VALID_WARRANT)
    proc = _run_cli(["assert-write-set", str(p), "dharma_swarm/secret.py"])
    assert proc.returncode != 0, f"must not exit 0: {proc.stdout!r}"
    out = proc.stdout + proc.stderr
    assert "dharma_swarm/secret.py" in out, f"must name the violating path: {out!r}"


def test_cli_write_set_in_set_exits_zero(tmp_path):
    p = _write_warrant(tmp_path, VALID_WARRANT)
    proc = _run_cli(["assert-write-set", str(p), "scripts/governance/loop/warrant.py"])
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"


def test_cli_missing_required_field_nonzero_naming_field(tmp_path):
    """VAL-WARRANT-005: missing required field fails (non-zero + names field)."""
    bad = {**VALID_WARRANT}
    del bad["write_set"]
    p = _write_warrant(tmp_path, bad)
    proc = _run_cli(["validate", str(p)])
    assert proc.returncode != 0, f"must not exit 0: {proc.stdout!r}"
    out = proc.stdout + proc.stderr
    assert "write_set" in out, f"must name the missing field: {out!r}"


def test_cli_budget_exceeded_aborts_nonzero(tmp_path):
    """VAL-WARRANT-006: exceeding budget.max_fixes_per_run aborts (non-zero)."""
    p = _write_warrant(tmp_path, VALID_WARRANT)
    proc = _run_cli(["check-budget", str(p), "--used-fixes", "6"])
    assert proc.returncode != 0, f"must not exit 0: {proc.stdout!r}"
    out = (proc.stdout + proc.stderr).lower()
    assert "budget" in out or "fixes" in out, f"must mention budget/fixes: {out!r}"


def test_cli_budget_under_limit_exits_zero(tmp_path):
    p = _write_warrant(tmp_path, VALID_WARRANT)
    proc = _run_cli(["check-budget", str(p), "--used-fixes", "3", "--used-tokens", "1000", "--used-wall-clock-min", "10"])
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"


def test_cli_stage_entry_expired_refused_nonzero(tmp_path):
    """VAL-WARRANT-007: mid-run expiry refused at next stage entry (non-zero)."""
    bad = {**VALID_WARRANT, "expires_at": "2000-01-01T00:00:00Z"}
    p = _write_warrant(tmp_path, bad)
    proc = _run_cli(["stage-entry", str(p)])
    assert proc.returncode != 0, f"must not exit 0: {proc.stdout!r}"
    out = (proc.stdout + proc.stderr).lower()
    assert "expired" in out, f"must contain expired message: {out!r}"


def test_cli_stage_entry_unexpired_exits_zero(tmp_path):
    p = _write_warrant(tmp_path, VALID_WARRANT)
    proc = _run_cli(["stage-entry", str(p)])
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"


def test_cli_invalid_authority_level_enum_nonzero(tmp_path):
    """VAL-WARRANT-008: invalid authority_level enum fails (non-zero + enum error)."""
    bad = {**VALID_WARRANT, "authority_level": "omnipotent"}
    p = _write_warrant(tmp_path, bad)
    proc = _run_cli(["validate", str(p)])
    assert proc.returncode != 0, f"must not exit 0: {proc.stdout!r}"
    out = proc.stdout + proc.stderr
    assert "authority_level" in out or "omnipotent" in out, f"must name the enum field: {out!r}"


def test_cli_missing_file_exits_two(tmp_path):
    proc = _run_cli(["validate", str(tmp_path / "nope.yaml")])
    assert proc.returncode != 0
    out = (proc.stdout + proc.stderr).lower()
    assert "exist" in out or "not found" in out or "no such" in out, out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
