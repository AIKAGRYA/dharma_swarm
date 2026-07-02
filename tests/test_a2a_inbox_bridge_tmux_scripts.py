from __future__ import annotations

import os
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

    assert "com.dharma.a2a.codex-composer-inbox-bridge" in start
    assert "com.dharma.a2a.codex-composer-inbox-bridge" in status
    assert "com.dharma.a2a.codex-composer-inbox-bridge" in stop
    assert "scripts/runtime/a2a_inbox_bridge.py" in start
    assert "KeepAlive" in start
    assert "INSTALL_LAUNCHD" in start
    assert "bootstrap" in start
    assert "kickstart -k" in start
    assert "No launchctl bootstrap/kickstart commands were run" in start
    assert "consumer info" in status
    assert "bridge_heartbeats" in status
    assert "CONFIRM_STOP" in stop
    assert "bootout" in stop
    assert "Dry-run only" in stop


def test_a2a_inbox_bridge_launchd_start_renders_codex_plan_without_launchctl(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plans"
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["PLAN_DIR"] = str(plan_dir)

    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/start_a2a_inbox_bridge_fleet_launchd.sh"),
            "--render-only",
            "--agent",
            "codex_composer",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    plist = plan_dir / "com.dharma.a2a.codex-composer-inbox-bridge.plist"
    plist_text = plist.read_text(encoding="utf-8")
    assert plist.exists()
    assert "<string>com.dharma.a2a.codex-composer-inbox-bridge</string>" in plist_text
    assert "<string>codex_composer</string>" in plist_text
    assert "<string>codex_composer_inbox</string>" in plist_text
    assert "<key>KeepAlive</key>" in plist_text
    assert "<key>RunAtLoad</key>" in plist_text
    assert "No launchctl bootstrap/kickstart commands were run" in result.stdout
    assert "started label=" not in result.stdout


def test_a2a_inbox_bridge_launchd_status_parses_launchctl_print(tmp_path: Path) -> None:
    home = tmp_path / "home"
    heartbeat_dir = home / ".dharma" / "a2a_bus" / "bridge_heartbeats"
    heartbeat_dir.mkdir(parents=True)
    (heartbeat_dir / "codex_composer.json").write_text(
        '{"status":"IDLE","timestamp":"2026-06-30T00:00:00Z"}\n',
        encoding="utf-8",
    )
    fake_launchctl = tmp_path / "launchctl"
    fake_launchctl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "print" && "${2:-}" == *"com.dharma.a2a.codex-composer-inbox-bridge" ]]; then
  printf 'state = running\\n'
  printf 'pid = 4242\\n'
  exit 0
fi
printf 'missing\\n' >&2
exit 113
""",
        encoding="utf-8",
    )
    fake_launchctl.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["LAUNCHCTL_BIN"] = str(fake_launchctl)
    env["NATS_BIN"] = str(tmp_path / "missing-nats")

    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/status_a2a_inbox_bridge_fleet_launchd.sh"),
            "--agent",
            "codex_composer",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "label=com.dharma.a2a.codex-composer-inbox-bridge" in result.stdout
    assert "launchd=loaded" in result.stdout
    assert "launchd_state=running" in result.stdout
    assert "launchd_pid=4242" in result.stdout
    assert "legacy_launchd=not_loaded" in result.stdout
    assert "heartbeat_status=IDLE" in result.stdout
    assert "nats_consumer=nats_cli_missing" in result.stdout
