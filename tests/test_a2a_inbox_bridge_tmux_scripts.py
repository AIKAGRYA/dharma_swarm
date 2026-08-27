from __future__ import annotations

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


def test_a2a_inbox_bridge_start_script_uses_receipt_bridge_not_ad_hoc_bus() -> None:
    text = (ROOT / "scripts/start_a2a_inbox_bridge_tmux.sh").read_text(encoding="utf-8")

    assert "scripts/runtime/a2a_inbox_bridge.py" in text
    assert "uv run --with nats-py" in text
    assert "PYTHONDONTWRITEBYTECODE=1" in text
    assert "python -B scripts/runtime/a2a_inbox_bridge.py" in text
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
    expected = (
        'RECEIPT_DIR="${DHARMA_STATE_DIR:-${DHARMA_HOME:-${HOME}/.dharma}}/'
        f'reports/a2a/{receipt_suffix}"'
    )

    assert expected in text
