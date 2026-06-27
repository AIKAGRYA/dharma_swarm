from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_a2a_inbox_bridge_tmux_scripts_are_syntax_valid() -> None:
    for script in [
        "scripts/start_a2a_inbox_bridge_tmux.sh",
        "scripts/status_a2a_inbox_bridge_tmux.sh",
        "scripts/stop_a2a_inbox_bridge_tmux.sh",
        "scripts/start_a2a_inbox_bridge_fleet_launchd.sh",
        "scripts/status_a2a_inbox_bridge_fleet_launchd.sh",
        "scripts/stop_a2a_inbox_bridge_fleet_launchd.sh",
    ]:
        subprocess.run(["bash", "-n", str(ROOT / script)], check=True)


def test_a2a_inbox_bridge_start_script_uses_receipt_bridge_not_ad_hoc_bus() -> None:
    text = (ROOT / "scripts/start_a2a_inbox_bridge_tmux.sh").read_text(encoding="utf-8")

    assert "scripts/runtime/a2a_inbox_bridge.py" in text
    assert "uv run --with nats-py" in text
    assert "--loop --suppress-no-messages" in text
    assert "dharma_a2a_inbox_bridge_hermes_m5" in text


def test_a2a_inbox_bridge_status_script_reports_receipts_and_consumer() -> None:
    text = (ROOT / "scripts/status_a2a_inbox_bridge_tmux.sh").read_text(encoding="utf-8")

    assert "consumer info" in text
    assert "reports/a2a/inbox_bridge_receipts" in text
    assert "tmux capture-pane" in text


def test_a2a_inbox_bridge_fleet_launchd_scripts_keep_five_plus_agents_live() -> None:
    start = (ROOT / "scripts/start_a2a_inbox_bridge_fleet_launchd.sh").read_text(encoding="utf-8")
    status = (ROOT / "scripts/status_a2a_inbox_bridge_fleet_launchd.sh").read_text(encoding="utf-8")
    stop = (ROOT / "scripts/stop_a2a_inbox_bridge_fleet_launchd.sh").read_text(encoding="utf-8")

    for agent_uid in [
        "hermes-m5",
        "codex_composer",
        "fable_composer",
        "opus_composer",
        "devin-roaming-2987d222",
        "perplexity-computer",
    ]:
        assert agent_uid in start
        assert agent_uid in status
        assert agent_uid in stop

    assert start.count("com.dharma.a2a-inbox-bridge.") >= 6
    assert "scripts/runtime/a2a_inbox_bridge.py" in start
    assert "KeepAlive" in start
    assert "launchctl bootstrap" in start
    assert "launchctl kickstart -k" in start
    assert "consumer info" in status
    assert "bridge_heartbeats" in status
    assert "launchctl bootout" in stop
