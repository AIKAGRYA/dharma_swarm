from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "governance" / "morning_cockpit.py"


def _load_module():
    name = "morning_cockpit"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_morning_cockpit_writes_brief_and_manifest(tmp_path, monkeypatch):
    mc = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    agentops_report = repo / "reports" / "agentops" / "job" / "run" / "report.json"
    kaizen_report = repo / "reports" / "kaizen" / "job" / "kaizen_review.json"
    agentops_report.parent.mkdir(parents=True)
    kaizen_report.parent.mkdir(parents=True)
    agentops_report.write_text("{}", encoding="utf-8")
    kaizen_report.write_text("{}", encoding="utf-8")

    def fake_run_command(name, command, *, cwd):
        if name == "operator-ground-truth":
            (repo / "reports" / "operator_ground_truth").mkdir(
                parents=True,
                exist_ok=True,
            )
            (repo / "reports" / "operator_ground_truth" / "latest.json").write_text(
                json.dumps(
                    {
                        "repo_cleanup_pressure": {
                            "worktree_count": 1,
                            "dirty_worktree_count": 0,
                            "dirty_hot_lane_count": 0,
                            "remote_branch_not_merged_count": 0,
                            "local_branch_merged_count": 0,
                            "top_cleanup_candidates": [],
                        },
                        "worktrees": [],
                    }
                ),
                encoding="utf-8",
            )
        if name == "docops-report":
            (repo / "reports" / "docops").mkdir(parents=True, exist_ok=True)
            (repo / "reports" / "docops" / "check.json").write_text(
                json.dumps({"passed": True, "failure_count": 0, "warning_count": 0}),
                encoding="utf-8",
            )
            (repo / "reports" / "docops" / "corpus_inventory.json").write_text(
                json.dumps({}),
                encoding="utf-8",
            )
        return mc.CommandResult(name=name, command=command, exit_code=0)

    monkeypatch.setattr(mc, "_run_command", fake_run_command)
    config = mc.MorningCockpitConfig(
        repo_root=repo,
        operator_ground_truth_output=repo / "reports" / "operator_ground_truth" / "latest.json",
        docops_report_output=repo / "reports" / "docops" / "check.json",
        docops_inventory_output=repo / "reports" / "docops" / "corpus_inventory.json",
        docops_inventory_markdown=repo / "reports" / "docops" / "corpus_inventory.md",
        brief_output=repo / "reports" / "daily_operating_brief" / "today.md",
        manifest_output=repo / "reports" / "morning_cockpit" / "latest.json",
        agentops_reports_dir=repo / "reports" / "agentops",
        kaizen_reports_dir=repo / "reports" / "kaizen",
        now=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )

    manifest = mc.run_morning_cockpit(config)

    assert manifest["passed"] is True
    assert manifest["missing_major_sources"] == []
    assert config.brief_output.exists()
    assert config.manifest_output.exists()
    assert "Daily Operating Brief" in config.brief_output.read_text(encoding="utf-8")


def test_morning_cockpit_strict_marks_missing_major_sources(tmp_path, monkeypatch):
    mc = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()

    def fake_run_command(name, command, *, cwd):
        return mc.CommandResult(name=name, command=command, exit_code=0)

    monkeypatch.setattr(mc, "_run_command", fake_run_command)
    config = mc.MorningCockpitConfig(
        repo_root=repo,
        operator_ground_truth_output=repo / "reports" / "operator_ground_truth" / "latest.json",
        docops_report_output=repo / "reports" / "docops" / "check.json",
        docops_inventory_output=repo / "reports" / "docops" / "corpus_inventory.json",
        docops_inventory_markdown=repo / "reports" / "docops" / "corpus_inventory.md",
        brief_output=repo / "reports" / "daily_operating_brief" / "today.md",
        manifest_output=repo / "reports" / "morning_cockpit" / "latest.json",
        agentops_reports_dir=repo / "reports" / "agentops",
        kaizen_reports_dir=repo / "reports" / "kaizen",
        fail_on_missing_major=True,
        now=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )

    manifest = mc.run_morning_cockpit(config)

    assert manifest["passed"] is False
    assert "operator_ground_truth" in manifest["missing_major_sources"]
    assert "agentops_reports" in manifest["missing_major_sources"]
    assert config.brief_output.exists()
