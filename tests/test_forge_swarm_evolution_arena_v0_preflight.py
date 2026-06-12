from __future__ import annotations

import json
from pathlib import Path

from scripts.runtime.forge_swarm_evolution_arena_v0_preflight import run_preflight, write_readiness_packet


def test_write_readiness_packet_preserves_terminal_decision_packet(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "swarm_lift_report.json").write_text(
        json.dumps({"status": "blocked_with_evidence"}),
        encoding="utf-8",
    )
    (run_dir / "decision_packet.md").write_text("terminal closeout\n", encoding="utf-8")
    report = {
        "closeout_state": "preflight_ready",
        "measurement_mode_allowed": True,
        "task_pack_gate": {"status": "green"},
        "roster_gate": {"status": "green"},
    }

    write_readiness_packet(run_dir, "2026-06-06T00:00:00Z", report)

    assert (run_dir / "decision_packet.md").read_text(encoding="utf-8") == "terminal closeout\n"
    assert "Preflight Decision" in (run_dir / "preflight_decision_packet.md").read_text(encoding="utf-8")


def test_run_preflight_preserves_roi_history_after_terminal_closeout(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "swarm_lift_report.json").write_text(
        json.dumps({"status": "blocked_with_evidence"}),
        encoding="utf-8",
    )
    original_roi = json.dumps({"schema_version": "forge_roi_governor.v1", "state": "red"}) + "\n"
    (run_dir / "roi_governor.jsonl").write_text(original_roi, encoding="utf-8")

    report = run_preflight(
        run_dir=run_dir,
        repo_root=tmp_path,
        generated_at="2026-06-06T00:00:00Z",
        write_packet=True,
    )

    assert (run_dir / "roi_governor.jsonl").read_text(encoding="utf-8") == original_roi
    assert report["terminal_closeout_present"] is True
    assert report["next_action"] == "terminal closeout exists; preserve measurement decision packet"
