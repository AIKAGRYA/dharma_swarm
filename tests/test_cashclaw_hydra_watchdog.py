from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


def _watchdog_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "revenue" / "cashclaw_hydra_watchdog.py"
    spec = importlib.util.spec_from_file_location("cashclaw_hydra_watchdog", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_watchdog_status_detects_running_incomplete_audit(tmp_path, monkeypatch):
    watchdog = _watchdog_module()
    (tmp_path / "objective_audit.json").write_text(
        json.dumps(
            {
                "status": "running_or_incomplete",
                "complete": False,
                "requirements": [
                    {"requirement": "loop_launched", "passed": True},
                    {"requirement": "overnight_duration", "passed": False},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "summaries.json").write_text(
        json.dumps([{"cycle": 1, "timestamp": "2026-05-31T09:00:00+00:00"}]) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "operator_revenue_lease_requests.json").write_text(
        json.dumps(
            {
                "status": "draft_only_not_granted",
                "external_side_effects_performed": False,
                "requests": [{"lease_id": "lease-1"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "lease_packet_quality_audit.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "passed": True,
                "lease_request_count": 1,
                "latest_cycle": 1,
                "latest_cycle_timestamp": "2026-05-31T09:00:00+00:00",
                "packet_results": [{"passed": True}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    live_dir = tmp_path / "cycle_001" / "live_intake"
    live_dir.mkdir(parents=True)
    (live_dir / "source_items.json").write_text(
        json.dumps(
            [
                {"source_type": "github", "source_config_id": "github-bounty-open-updated"},
                {"source_type": "hacker_news", "source_config_id": "hn-ai-agent-market-search"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (live_dir / "pattern_cards.json").write_text(
        json.dumps(
            [
                {
                    "source_type": "github",
                    "what_is_being_built": "AI employee installation for one recurring workflow",
                    "buyer_pain": "needs OpenClaw cron agent",
                    "buyer_segment": "operators",
                    "tool_stack": ["OpenClaw", "cron"],
                    "risks": [],
                },
                {
                    "source_type": "hacker_news",
                    "what_is_being_built": "workflow automation",
                    "buyer_pain": "Claude workflow agent",
                    "buyer_segment": "builders",
                    "tool_stack": ["Claude"],
                    "risks": ["non_cash_or_token_reward"],
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(watchdog, "_matching_processes", lambda _: ["123 cashclaw_revenue_hydra.py --run-root x"])
    monkeypatch.setattr(watchdog, "_minutes_since_timestamp", lambda _: 12.0)

    status = watchdog.build_watchdog_status(
        run_root=tmp_path,
        process_substring="cashclaw_revenue_hydra.py",
        check_number=1,
    )

    assert status["hydra_process_running"] is True
    assert status["objective_complete"] is False
    assert status["objective_holds"] == ["overnight_duration"]
    assert status["alerts"] == []
    assert status["lease_request_count"] == 1
    assert status["lease_packet_quality"]["passed"] is True
    assert status["source_signal_summary"]["source_type_count"] == 2
    assert status["source_signal_summary"]["agent_market_signal_count"] == 2
    assert status["source_signal_summary"]["ai_employee_signal_count"] >= 1


def test_watchdog_writes_status_files_and_alerts_on_missing_process(tmp_path, monkeypatch):
    watchdog = _watchdog_module()
    (tmp_path / "objective_audit.json").write_text(
        json.dumps(
            {
                "status": "running_or_incomplete",
                "complete": False,
                "requirements": [{"requirement": "overnight_duration", "passed": False}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "summaries.json").write_text(json.dumps([{"timestamp": "2026-05-31T09:00:00+00:00"}]) + "\n", encoding="utf-8")
    (tmp_path / "operator_revenue_lease_requests.json").write_text(
        json.dumps({"status": "draft_only_not_granted", "external_side_effects_performed": False, "requests": []}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(watchdog, "_matching_processes", lambda _: [])
    monkeypatch.setattr(watchdog, "_minutes_since_timestamp", lambda _: 50.0)

    status = watchdog.build_watchdog_status(
        run_root=tmp_path,
        process_substring="cashclaw_revenue_hydra.py",
        check_number=2,
    )
    watchdog.write_watchdog_status(tmp_path, status)

    assert "hydra_process_missing_before_objective_complete" in status["alerts"]
    assert "latest_cycle_stale_over_45m" in status["alerts"]
    assert (tmp_path / "watchdog_status.json").exists()
    assert (tmp_path / "watchdog_status.md").exists()
    assert (tmp_path / "watchdog_history.jsonl").exists()
    assert "Source Signals" in (tmp_path / "watchdog_status.md").read_text(encoding="utf-8")


def test_watchdog_alerts_on_stale_or_failed_lease_packet_quality(tmp_path, monkeypatch):
    watchdog = _watchdog_module()
    (tmp_path / "objective_audit.json").write_text(
        json.dumps({"status": "running_or_incomplete", "complete": False, "requirements": []}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "summaries.json").write_text(
        json.dumps([{"cycle": 2, "timestamp": "2026-05-31T10:00:00+00:00"}]) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "operator_revenue_lease_requests.json").write_text(
        json.dumps(
            {
                "status": "draft_only_not_granted",
                "external_side_effects_performed": False,
                "requests": [{"lease_id": "lease-1"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "lease_packet_quality_audit.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "passed": True,
                "lease_request_count": 1,
                "latest_cycle": 1,
                "latest_cycle_timestamp": "2026-05-31T09:00:00+00:00",
                "packet_results": [{"passed": True}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(watchdog, "_matching_processes", lambda _: ["123 cashclaw_revenue_hydra.py --run-root x"])
    monkeypatch.setattr(watchdog, "_minutes_since_timestamp", lambda _: 5.0)

    status = watchdog.build_watchdog_status(
        run_root=tmp_path,
        process_substring="cashclaw_revenue_hydra.py",
        check_number=1,
    )

    assert "lease_packet_quality_audit_stale_cycle" in status["alerts"]
    assert status["lease_packet_quality"]["alert"] == "lease_packet_quality_audit_stale_cycle"


def test_matching_processes_falls_back_to_ps_when_pgrep_is_empty(monkeypatch):
    watchdog = _watchdog_module()

    def fake_run(command, check, text, capture_output):
        assert check is False
        assert text is True
        assert capture_output is True
        if command[:2] == ["pgrep", "-fl"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="sysmond service not found")
        if command == ["ps", "-axo", "pid=,command="]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "123 python3 scripts/revenue/cashclaw_revenue_hydra.py --run-root x\n"
                    "456 python3 scripts/revenue/cashclaw_hydra_watchdog.py --process-substring cashclaw_revenue_hydra.py\n"
                ),
                stderr="",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(watchdog.subprocess, "run", fake_run)

    assert watchdog._matching_processes("cashclaw_revenue_hydra.py") == [
        "123 python3 scripts/revenue/cashclaw_revenue_hydra.py --run-root x"
    ]


def test_matching_processes_falls_back_to_tmux_session_when_process_table_unavailable(monkeypatch):
    watchdog = _watchdog_module()

    def fake_run(command, check, text, capture_output):
        assert check is False
        assert text is True
        assert capture_output is True
        if command[:2] == ["pgrep", "-fl"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="sysmond service not found")
        if command == ["ps", "-axo", "pid=,command="]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="sysmond service not found")
        if command == ["tmux", "has-session", "-t", "cashclaw-scrappy-v2-hydra"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
        if command == ["tmux", "has-session", "-t", "cashclaw_revenue_hydra"]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(watchdog.subprocess, "run", fake_run)

    assert watchdog._matching_processes("cashclaw_revenue_hydra.py") == [
        "tmux session cashclaw_revenue_hydra active; process table unavailable"
    ]


def test_matching_processes_falls_back_to_scrappy_v2_tmux_session(monkeypatch):
    watchdog = _watchdog_module()

    def fake_run(command, check, text, capture_output):
        assert check is False
        assert text is True
        assert capture_output is True
        if command[:2] == ["pgrep", "-fl"]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="sysmond service not found")
        if command == ["ps", "-axo", "pid=,command="]:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="sysmond service not found")
        if command == ["tmux", "has-session", "-t", "cashclaw-scrappy-v2-hydra"]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(watchdog.subprocess, "run", fake_run)

    assert watchdog._matching_processes("cashclaw_revenue_hydra.py") == [
        "tmux session cashclaw-scrappy-v2-hydra active; process table unavailable"
    ]
