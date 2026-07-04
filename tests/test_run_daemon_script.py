from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


RUN_DAEMON_SCRIPT = Path(__file__).resolve().parents[1] / "run_daemon.sh"


def test_run_daemon_sources_runtime_env_helper() -> None:
    script = RUN_DAEMON_SCRIPT.read_text(encoding="utf-8")

    assert "scripts/load_runtime_env.sh" in script
    assert "source \"$RUNTIME_ENV_HELPER\"" in script
    assert "source \"$DAEMON_ENV\"" not in script


def test_run_daemon_prepends_common_binary_dirs_to_path() -> None:
    script = RUN_DAEMON_SCRIPT.read_text(encoding="utf-8")

    assert ".npm-global/bin" in script
    assert "/opt/homebrew/bin" in script
    assert "/usr/local/bin" in script
