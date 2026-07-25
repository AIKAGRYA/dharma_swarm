"""Contract tests for scripts/governance/substrate_audit.py.

Fast by design: only the ruff lane runs (subset via --tools); the full
five-tool sweep is an operator/CI action, not a unit-test cost.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "governance" / "substrate_audit.py"
BASELINE = REPO_ROOT / "reports" / "governance" / "substrate_baseline.json"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_unknown_tool_exits_2():
    result = _run("--tools", "nonexistent")
    assert result.returncode == 2
    assert "unknown tools" in result.stderr


def test_advisory_default_exits_zero_even_with_findings():
    result = _run("--tools", "ruff")
    assert result.returncode == 0, result.stderr
    assert "ruff_total" in result.stdout


def test_baseline_is_committed_and_versioned():
    assert BASELINE.exists(), "run: make substrate-baseline"
    payload = json.loads(BASELINE.read_text())
    assert payload["schema"] == "dharma_swarm.substrate_baseline.v1"
    assert isinstance(payload["counts"], dict) and payload["counts"]


def test_strict_regression_detected(tmp_path, monkeypatch):
    """A fabricated zero-count baseline must trip --strict (counts > 0 exist)."""
    fake = tmp_path / "substrate_baseline.json"
    fake.write_text(json.dumps({
        "schema": "dharma_swarm.substrate_baseline.v1",
        "tools": ["ruff"],
        "counts": {"ruff_total": 0},
    }))
    src = SCRIPT.read_text()
    patched = tmp_path / "substrate_audit.py"
    patched.write_text(
        src.replace(
            'BASELINE = REPO_ROOT / "reports" / "governance" / "substrate_baseline.json"',
            f'BASELINE = Path({str(fake)!r})',
        )
    )
    result = subprocess.run(
        [sys.executable, str(patched), "--tools", "ruff", "--strict"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "RATCHET REGRESSION" in result.stdout
