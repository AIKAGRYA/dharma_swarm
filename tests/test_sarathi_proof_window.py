"""Operator proof-window runner (PR-S4): one command, fail-closed exit.

The runner is the Gate-9 runtime wrapper: it pins the propose-only dial,
persists briefs/records under the state root, refuses to PASS without the
operator-created kill-path receipt, and exits non-zero on any non-pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "runtime"))

import sarathi_proof_window as runner  # noqa: E402


def _run(tmp_path: Path, cycles: int = 3) -> tuple[int, dict]:
    code = runner.main(
        ["--cycles", str(cycles), "--state-root", str(tmp_path), "--json"]
    )
    report = json.loads(
        (tmp_path / "sarathi" / "proof_window_report.json").read_text()
    )
    return code, report


def test_window_without_kill_receipt_fails_closed(tmp_path) -> None:
    code, report = _run(tmp_path)
    assert code == 1
    assert report["passed"] is False
    assert report["kill_path_verified"] is False
    assert report["consecutive_clean"] == 3 == report["cycles_run"]
    assert report["audit_findings_total"] == 0
    assert any("loop-emergency-stop" in f for f in report["failures"])
    # Briefs and cycle records persisted under the state root.
    briefs = sorted((tmp_path / "sarathi" / "briefs").glob("brief_cycle_*.md"))
    assert len(briefs) == 3
    assert "## Delegation ledger" in briefs[-1].read_text()


def test_window_passes_only_with_operator_receipt(tmp_path) -> None:
    receipt_path = tmp_path / "sarathi" / "kill_path_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(
            {
                "verified": True,
                "verified_at": "2026-07-30T16:00:00+00:00",
                "method": "operator confirmed loop-emergency-stop from phone",
            }
        )
    )
    code, report = _run(tmp_path, cycles=2)
    assert code == 0
    assert report["passed"] is True
    assert report["kill_path_verified"] is True
    assert report["kill_path_receipt"]["verified"] is True


def test_invalid_receipt_is_no_receipt(tmp_path) -> None:
    receipt_path = tmp_path / "sarathi" / "kill_path_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps({"verified": "yes-ish"}))
    assert runner.read_kill_path_receipt(tmp_path) is None
    receipt_path.write_text("{not json")
    assert runner.read_kill_path_receipt(tmp_path) is None
