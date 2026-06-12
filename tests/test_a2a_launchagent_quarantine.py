from __future__ import annotations

import json
from pathlib import Path

from scripts.runtime import a2a_launchagent_quarantine


def _write_audit(path: Path, *, launch_agents: Path, outside: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "dharma.a2a.daemon_wiring_audit.v1",
        "candidates": [
            {
                "label": "com.dharma.a2a.bad",
                "status": "FAIL",
                "path": str(launch_agents / "com.dharma.a2a.bad.plist"),
                "issues": [{"type": "missing_module_target"}],
                "program_arguments": ["/usr/bin/python3", "-m", "missing.module"],
                "working_directory": "/tmp/repo",
                "broker_scope": "missing",
            },
            {
                "label": "com.dharma.a2a.good",
                "status": "PASS",
                "path": str(launch_agents / "com.dharma.a2a.good.plist"),
                "issues": [],
            },
            {
                "label": "com.dharma.a2a.outside",
                "status": "FAIL",
                "path": str((outside or launch_agents.parent / "outside") / "bad.plist"),
                "issues": [{"type": "outside"}],
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_dry_run_selects_only_failing_plists_under_launch_agents(tmp_path: Path) -> None:
    launch_agents = tmp_path / "LaunchAgents"
    launch_agents.mkdir()
    bad = launch_agents / "com.dharma.a2a.bad.plist"
    good = launch_agents / "com.dharma.a2a.good.plist"
    bad.write_text("bad", encoding="utf-8")
    good.write_text("good", encoding="utf-8")
    audit = tmp_path / "audit.json"
    _write_audit(audit, launch_agents=launch_agents, outside=tmp_path / "outside")

    receipt = a2a_launchagent_quarantine.run_quarantine(
        audit_path=audit,
        launch_agents_dir=launch_agents,
        quarantine_root=tmp_path / "quarantine",
        receipt_dir=tmp_path / "receipts",
        labels=set(),
        statuses={"FAIL"},
        apply=False,
    )

    assert receipt["status"] == "DRY_RUN"
    assert receipt["candidate_labels"] == ["com.dharma.a2a.bad"]
    assert receipt["moved_count"] == 0
    assert bad.exists()
    assert good.exists()
    assert Path(receipt["receipt_path"]).is_file()
    skipped_reasons = {entry["reason"] for entry in receipt["skipped"]}
    assert "status_not_selected" in skipped_reasons
    assert "outside_launch_agents_dir" in skipped_reasons


def test_apply_moves_plist_and_leaves_pointer(tmp_path: Path) -> None:
    launch_agents = tmp_path / "LaunchAgents"
    launch_agents.mkdir()
    bad = launch_agents / "com.dharma.a2a.bad.plist"
    good = launch_agents / "com.dharma.a2a.good.plist"
    bad.write_text("bad", encoding="utf-8")
    good.write_text("good", encoding="utf-8")
    audit = tmp_path / "audit.json"
    _write_audit(audit, launch_agents=launch_agents)

    receipt = a2a_launchagent_quarantine.run_quarantine(
        audit_path=audit,
        launch_agents_dir=launch_agents,
        quarantine_root=tmp_path / "quarantine",
        receipt_dir=tmp_path / "receipts",
        labels=set(),
        statuses={"FAIL"},
        apply=True,
    )

    assert receipt["status"] == "APPLIED"
    assert receipt["moved_count"] == 1
    assert not bad.exists()
    assert good.exists()
    moved_to = Path(receipt["moved"][0]["to"])
    assert moved_to.is_file()
    assert moved_to.read_text(encoding="utf-8") == "bad"
    pointer = launch_agents / a2a_launchagent_quarantine.POINTER_NAME
    assert pointer.is_file()
    assert "A2A Runtime Spine" in pointer.read_text(encoding="utf-8")
    quarantine_readme = Path(receipt["quarantine_readme_path"])
    assert quarantine_readme.is_file()
    saved = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))
    assert saved["pointer_path"] == str(pointer)


def test_label_filter_limits_apply(tmp_path: Path) -> None:
    launch_agents = tmp_path / "LaunchAgents"
    launch_agents.mkdir()
    selected = launch_agents / "com.dharma.a2a.bad.plist"
    selected.write_text("bad", encoding="utf-8")
    audit = tmp_path / "audit.json"
    _write_audit(audit, launch_agents=launch_agents)

    receipt = a2a_launchagent_quarantine.run_quarantine(
        audit_path=audit,
        launch_agents_dir=launch_agents,
        quarantine_root=tmp_path / "quarantine",
        receipt_dir=tmp_path / "receipts",
        labels={"com.dharma.a2a.good"},
        statuses={"FAIL"},
        apply=True,
    )

    assert receipt["candidate_count"] == 0
    assert selected.exists()
