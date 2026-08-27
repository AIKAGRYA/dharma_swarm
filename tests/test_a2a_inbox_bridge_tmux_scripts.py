from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_a2a_inbox_bridge_tmux_scripts_are_syntax_valid() -> None:
    for script in [
        "scripts/start_a2a_inbox_bridge_tmux.sh",
        "scripts/status_a2a_inbox_bridge_tmux.sh",
        "scripts/stop_a2a_inbox_bridge_tmux.sh",
    ]:
        subprocess.run(["bash", "-n", str(ROOT / script)], check=True)


def test_a2a_inbox_bridge_start_script_uses_locked_release_interpreter() -> None:
    text = (ROOT / "scripts/start_a2a_inbox_bridge_tmux.sh").read_text(encoding="utf-8")

    assert "scripts/runtime/a2a_inbox_bridge.py" in text
    assert "uv run --with" not in text
    assert 'RUNTIME_PYTHON="${ROOT}/.venv/bin/python"' in text
    assert 'version("nats-py") != "2.15.0"' in text
    assert "uv sync --frozen --extra a2a-runtime" in text
    assert "PYTHONDONTWRITEBYTECODE=1" in text
    assert "'${RUNTIME_PYTHON}' -B scripts/runtime/a2a_inbox_bridge.py" in text
    assert "--loop --suppress-no-messages" in text
    assert "dharma_a2a_inbox_bridge_hermes_m5" in text


def test_a2a_inbox_bridge_status_script_reports_receipts_and_consumer() -> None:
    text = (ROOT / "scripts/status_a2a_inbox_bridge_tmux.sh").read_text(encoding="utf-8")

    assert "consumer info" in text
    assert "DHARMA_STATE_DIR" in text
    assert "reports/a2a/inbox_bridge_receipts" in text
    assert "tmux capture-pane" in text


@pytest.mark.parametrize(
    ("script", "receipt_suffix"),
    [
        ("scripts/status_a2a_inbox_bridge_tmux.sh", "inbox_bridge_receipts"),
        (
            "scripts/status_palantir_pilot_a2a_worker_tmux.sh",
            "palantir_pilot_worker_receipts",
        ),
    ],
)
def test_runtime_status_scripts_share_state_authority_precedence(
    script: str,
    receipt_suffix: str,
) -> None:
    text = (ROOT / script).read_text(encoding="utf-8")

    assert 'STATE_ROOT="${DHARMA_STATE_DIR:-${DHARMA_HOME:-${HOME}/.dharma}}"' in text
    assert '"~/"*) STATE_ROOT="${HOME}/${STATE_ROOT#\\~/}"' in text
    assert f'RECEIPT_DIR="${{STATE_ROOT}}/reports/a2a/{receipt_suffix}"' in text


@pytest.mark.parametrize(
    ("script", "receipt_suffix"),
    [
        ("scripts/status_a2a_inbox_bridge_tmux.sh", "inbox_bridge_receipts"),
        (
            "scripts/status_palantir_pilot_a2a_worker_tmux.sh",
            "palantir_pilot_worker_receipts",
        ),
    ],
)
def test_runtime_status_scripts_expand_documented_tilde_state_root(
    tmp_path: Path,
    script: str,
    receipt_suffix: str,
) -> None:
    home = tmp_path / "operator-home"
    receipt_dir = home / ".dharma" / "reports" / "a2a" / receipt_suffix
    receipt_dir.mkdir(parents=True)
    receipt = receipt_dir / "receipt.json"
    receipt.write_text("{}\n", encoding="utf-8")
    env = {
        **os.environ,
        "HOME": str(home),
        "DHARMA_STATE_DIR": "~/.dharma",
        "DHARMA_HOME": str(tmp_path / "must-not-win"),
        "SESSION_NAME": "test-status-script-no-live-session",
        "PATH": "/usr/bin:/bin",
    }

    completed = subprocess.run(
        ["bash", str(ROOT / script)],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert str(receipt) in completed.stdout
