from __future__ import annotations

import plistlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _program_argument_text(plist_path: Path) -> str:
    payload = plistlib.loads(plist_path.read_bytes())
    return " ".join(payload.get("ProgramArguments", []))


def test_swarm_launchd_template_sources_shared_runtime_loader() -> None:
    command = _program_argument_text(REPO_ROOT / "com.dharma.swarm.plist")

    assert "source scripts/load_runtime_env.sh" in command
    assert "source .env" not in command
    assert "agent_keys.env" not in command


def test_cron_launchd_template_sources_shared_runtime_loader() -> None:
    command = _program_argument_text(REPO_ROOT / "scripts/com.dharma.cron-daemon.plist")

    assert "source scripts/load_runtime_env.sh" in command
    assert "source .env" not in command
    assert "agent_keys.env" not in command


def test_dashboard_ui_uses_shared_runtime_loader() -> None:
    script = (REPO_ROOT / "scripts/run_dashboard_ui.sh").read_text(encoding="utf-8")

    assert "scripts/load_runtime_env.sh" in script
    assert "source \"$RUNTIME_ENV_HELPER\"" in script
    assert "set -a" not in script
    assert "source \"$envfile\"" not in script


def test_garden_launcher_has_no_zshrc_key_scrape_fallback() -> None:
    script = (REPO_ROOT / "run_garden.sh").read_text(encoding="utf-8")

    assert "scripts/load_runtime_env.sh" in script
    assert "grep -E '^export" not in script


def test_provider_status_refresh_uses_shared_runtime_loader() -> None:
    script = (REPO_ROOT / "scripts/refresh_provider_status.sh").read_text(encoding="utf-8")

    assert "scripts/load_runtime_env.sh" in script
    assert "source \"$RUNTIME_ENV_HELPER\"" in script
    assert script.index("source \"$RUNTIME_ENV_HELPER\"") < script.index("STATE_DIR=")
    assert '"$DKEYS_BIN" test' in script
    assert "scripts/check_provider_credits.py" in script
    assert "source .env" not in script
