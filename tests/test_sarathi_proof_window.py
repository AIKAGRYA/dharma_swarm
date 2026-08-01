"""Operator proof-window runner (PR-S4): one command, fail-closed exit.

The runner is the Gate-9 runtime wrapper: it pins the propose-only dial,
persists briefs/records under the state root, refuses to PASS without the
operator-created kill-path receipt, ALWAYS judges the verdict against the full
14-cycle requirement, and exits non-zero on any non-pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "runtime"))

import sarathi_proof_window as runner  # noqa: E402

FULL = runner.REQUIRED_UNATTENDED_CYCLES  # 14


def _run(tmp_path: Path, cycles: int) -> tuple[int, dict]:
    code = runner.main(
        ["--cycles", str(cycles), "--state-root", str(tmp_path), "--json"]
    )
    report = json.loads(
        (tmp_path / "sarathi" / "proof_window_report.json").read_text()
    )
    return code, report


def _write_receipt(tmp_path: Path, **overrides) -> None:
    payload = {
        "verified": True,
        "verified_at": "2026-07-30T16:00:00+00:00",
        "method": "operator confirmed loop-emergency-stop from phone",
    }
    payload.update(overrides)
    path = tmp_path / "sarathi" / "kill_path_receipt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_short_run_without_receipt_fails_closed(tmp_path) -> None:
    code, report = _run(tmp_path, cycles=3)
    assert code == 1
    assert report["passed"] is False
    assert report["kill_path_verified"] is False
    assert report["cycles_run"] == 3
    assert report["required"] == FULL
    assert report["audit_findings_total"] == 0
    assert any("loop-emergency-stop" in f for f in report["failures"])
    briefs = sorted((tmp_path / "sarathi" / "briefs").glob("brief_cycle_*.md"))
    assert len(briefs) == 3
    assert "## Delegation ledger" in briefs[-1].read_text()


def test_undersized_run_cannot_pass_even_with_receipt(tmp_path) -> None:
    """Greptile/Codex P1: --cycles 1 + a valid receipt must NOT pass — the
    verdict threshold is always the full 14-cycle window."""
    _write_receipt(tmp_path)
    code, report = _run(tmp_path, cycles=1)
    assert code == 1
    assert report["passed"] is False
    assert report["kill_path_verified"] is True
    assert report["consecutive_clean"] == 1
    assert report["required"] == FULL


def test_full_window_with_valid_receipt_passes(tmp_path) -> None:
    _write_receipt(tmp_path)
    code, report = _run(tmp_path, cycles=FULL)
    assert code == 0
    assert report["passed"] is True
    assert report["kill_path_verified"] is True
    assert report["consecutive_clean"] == FULL
    assert report["kill_path_receipt"]["verified"] is True


def test_full_window_without_receipt_fails(tmp_path) -> None:
    code, report = _run(tmp_path, cycles=FULL)
    assert code == 1
    assert report["passed"] is False
    assert report["consecutive_clean"] == FULL  # cycles clean, but no kill path
    assert any("loop-emergency-stop" in f for f in report["failures"])


@pytest.mark.parametrize("bad_cap", ["nan", "inf", "-1"])
def test_nonfinite_or_negative_cap_is_rejected(tmp_path, bad_cap) -> None:
    """Greptile P1 on PR #1170: the proof-window --cap-usd must reject a
    non-finite/negative value at the CLI, mirroring the standing daemon. Left
    unvalidated, `--cap-usd nan` defeats the budget guard and certifies a
    passed:true 14-cycle proof — an invalid budget control gating dial
    advancement. parser.error exits nonzero and writes no proof report."""
    with pytest.raises(SystemExit):
        runner.main([
            "--cycles", str(FULL),
            "--state-root", str(tmp_path),
            "--cap-usd", bad_cap,
            "--json",
        ])
    assert not (tmp_path / "sarathi" / "proof_window_report.json").exists()


def test_responded_task_suppresses_reproposal_in_window(tmp_path) -> None:
    """Greptile P1 on PR #1170: a claimed/responded Sarathi task's persisted
    dedup key must suppress re-proposing the same backlog item during the proof
    window. The window deduplicates over ALL persisted tasks (list_tasks), not
    only currently-claimable ones (ready_tasks), matching the daemon."""
    from dharma_swarm.holon_system.sarathi.plan import (
        BootPack,
        build_plan,
        plan_dedup_key,
    )
    from dharma_swarm.holon_system.sarathi.roster import DEFAULT_ROSTER, load_roster
    from dharma_swarm.roaming_mailbox import RoamingMailbox

    item = {"kind": "review", "summary": "audit the blocked loops", "body": "walk them"}
    roster = load_roster() or DEFAULT_ROSTER
    [planned] = build_plan(BootPack(roster=roster, open_items=(item,)))

    mailbox = RoamingMailbox(queue_root=tmp_path / "sarathi" / "mailbox")
    task = mailbox.enqueue_task(
        recipient=planned.recipient,
        sender="sarathi",
        summary=item["summary"],
        body=item["body"],
        metadata={"sarathi": {"dedup_key": plan_dedup_key(planned)}},
    )
    # Drive it out of the ready set: claimed, then responded.
    mailbox.claim_task(task.task_id, claimed_by=planned.recipient)
    mailbox.respond_to_task(
        task_id=task.task_id, responder=planned.recipient, summary="done", body="done"
    )

    backlog = tmp_path / "backlog.json"
    backlog.write_text(json.dumps([item]))
    runner.main([
        "--cycles", "1",
        "--state-root", str(tmp_path),
        "--backlog", str(backlog),
        "--json",
    ])
    brief = sorted(
        (tmp_path / "sarathi" / "briefs").glob("brief_cycle_*.md")
    )[-1].read_text()
    # The item is deduped, not re-proposed: the ledger shows proposed=0 and no
    # proposed row for it (its summary appears only in the completed section).
    assert "proposed=0" in brief
    assert f"[proposed] {item['summary']}" not in brief


def test_receipt_requires_verified_timestamp_and_method(tmp_path) -> None:
    receipt_path = tmp_path / "sarathi" / "kill_path_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    # verified not True
    receipt_path.write_text(json.dumps({"verified": "yes-ish"}))
    assert runner.read_kill_path_receipt(tmp_path) is None
    # missing method
    receipt_path.write_text(
        json.dumps({"verified": True, "verified_at": "2026-07-30T16:00:00Z"})
    )
    assert runner.read_kill_path_receipt(tmp_path) is None
    # malformed timestamp
    receipt_path.write_text(
        json.dumps({"verified": True, "verified_at": "today", "method": "phone"})
    )
    assert runner.read_kill_path_receipt(tmp_path) is None
    # not JSON
    receipt_path.write_text("{not json")
    assert runner.read_kill_path_receipt(tmp_path) is None
    # complete + valid
    receipt_path.write_text(
        json.dumps(
            {"verified": True, "verified_at": "2026-07-30T16:00:00+00:00", "method": "phone"}
        )
    )
    assert runner.read_kill_path_receipt(tmp_path) is not None
