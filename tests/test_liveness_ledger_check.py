"""Tests for scripts/governance/liveness_ledger_check.py (replay verifier).

Fixture chains are written through the same spine appender the daemon uses
(dharma_swarm.spine.receipt.append_machine_receipt), so the checker is
exercised against real chain bytes, never a hand-rolled imitation of the
digest formula.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

import liveness_ledger_check as check  # noqa: E402

from dharma_swarm.spine.receipt import (  # noqa: E402
    VerifiedMachineReceipt,
    append_machine_receipt,
)

NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)


def _append_row(
    ledger: Path,
    *,
    boot_id: str,
    produced_at: datetime,
    running: list[str] | None = None,
    abandoned: list[str] | None = None,
) -> None:
    receipt = VerifiedMachineReceipt(
        generated_by="dharma_swarm.orchestrate_live.append_liveness_ledger_row",
        produced_at=produced_at.isoformat(),
        attributes={
            "kind": "loop_liveness",
            "boot_id": boot_id,
            "pid": 4242,
            "running": sorted(running or ["swarm", "pulse"]),
            "restart_counts": {},
            "abandoned": sorted(abandoned or []),
        },
    )
    append_machine_receipt(receipt, path=ledger)


def _hourly_chain(ledger: Path, *, hours: int, boot_id: str, end: datetime) -> None:
    for offset in range(hours, 0, -1):
        _append_row(ledger, boot_id=boot_id, produced_at=end - timedelta(hours=offset))


def test_absent_ledger_is_needs_host_and_exit_zero(tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "missing.jsonl"
    report = check.evaluate(ledger, now=NOW)
    assert report["status"] == "needs_host"
    assert main_exit(ledger) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "needs_host"


def main_exit(ledger: Path, *extra: str) -> int:
    return check.main(["--ledger", str(ledger), *extra])


def test_valid_hourly_chain_passes_coverage_and_boot_assertions(tmp_path: Path) -> None:
    ledger = tmp_path / "liveness_ledger.jsonl"
    _hourly_chain(ledger, hours=25, boot_id="boot_aaaa", end=NOW)
    report = check.evaluate(
        ledger,
        window_hours=48.0,
        min_rows=24,
        expect_boot_ids=1,
        max_gap_hours=2.0,
        max_age_hours=2.0,
        now=NOW,
    )
    assert report["errors"] == []
    assert report["status"] == "ok"
    assert report["rows_in_window"] == 25
    assert report["boot_ids_in_window"] == ["boot_aaaa"]
    assert report["boot_id_transitions"] == 0


def test_restart_window_counts_distinct_boot_ids(tmp_path: Path) -> None:
    ledger = tmp_path / "liveness_ledger.jsonl"
    _hourly_chain(ledger, hours=4, boot_id="boot_aaaa", end=NOW - timedelta(hours=4))
    _hourly_chain(ledger, hours=4, boot_id="boot_bbbb", end=NOW)
    ok = check.evaluate(ledger, window_hours=24.0, expect_boot_ids=2, now=NOW)
    assert ok["status"] == "ok"
    assert ok["boot_id_transitions"] == 1
    wrong = check.evaluate(ledger, window_hours=24.0, expect_boot_ids=1, now=NOW)
    assert wrong["status"] == "fail"
    assert any("boot identity" in error for error in wrong["errors"])


def test_gap_inside_window_fails_when_bounded(tmp_path: Path) -> None:
    ledger = tmp_path / "liveness_ledger.jsonl"
    _append_row(ledger, boot_id="boot_aaaa", produced_at=NOW - timedelta(hours=8))
    _append_row(ledger, boot_id="boot_aaaa", produced_at=NOW - timedelta(hours=1))
    report = check.evaluate(ledger, window_hours=24.0, max_gap_hours=2.0, now=NOW)
    assert report["status"] == "fail"
    assert any("went dark" in error for error in report["errors"])


def test_stale_producer_fails_when_age_bounded(tmp_path: Path) -> None:
    ledger = tmp_path / "liveness_ledger.jsonl"
    _append_row(ledger, boot_id="boot_aaaa", produced_at=NOW - timedelta(hours=9))
    report = check.evaluate(ledger, window_hours=24.0, max_age_hours=2.0, now=NOW)
    assert report["status"] == "fail"
    assert any("staleness" in error for error in report["errors"])


def test_negative_control_tampered_row_breaks_the_chain(tmp_path: Path) -> None:
    """A row whose recorded facts were edited after the fact must not verify.

    This is the property the overwrite-in-place snapshot could never give:
    the old loop_liveness.json could be rewritten arbitrarily and nothing
    would notice.
    """
    ledger = tmp_path / "liveness_ledger.jsonl"
    _hourly_chain(ledger, hours=3, boot_id="boot_aaaa", end=NOW)
    lines = ledger.read_text(encoding="utf-8").splitlines()
    doctored = json.loads(lines[1])
    doctored["attributes"]["running"] = ["everything-fine"]
    lines[1] = json.dumps(doctored, sort_keys=True, separators=(",", ":"))
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = check.evaluate(ledger, now=NOW)
    assert report["status"] == "fail"
    assert any("chain replay failed" in error for error in report["errors"])
    assert main_exit(ledger) == 1


def test_min_rows_short_window_fails(tmp_path: Path, capsys) -> None:
    ledger = tmp_path / "liveness_ledger.jsonl"
    _hourly_chain(ledger, hours=3, boot_id="boot_aaaa", end=NOW)
    report = check.evaluate(ledger, window_hours=24.0, min_rows=24, now=NOW)
    assert report["status"] == "fail"
    assert any("coverage" in error for error in report["errors"])
    assert main_exit(ledger, "--min-rows", "24") == 1
    capsys.readouterr()
