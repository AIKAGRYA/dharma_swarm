from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_SCRIPTS = [
    "scripts/status_terminal_tui_tmux.sh",
    "scripts/status_composer_background_loop_tmux.sh",
    "scripts/status_composer_console_tmux.sh",
]


def test_tmux_status_scripts_are_syntax_valid() -> None:
    for script in STATUS_SCRIPTS:
        subprocess.run(["bash", "-n", str(ROOT / script)], check=True)


def test_tmux_status_scripts_label_stopped_session_logs_as_historical() -> None:
    for script in STATUS_SCRIPTS:
        text = (ROOT / script).read_text(encoding="utf-8")

        assert "SESSION_RUNNING=0" in text
        assert "historical; not liveness proof" in text
        assert "because session is NOT RUNNING" in text
        assert 'if [[ "${SESSION_RUNNING}" == "1" ]]' in text


def test_composer_background_status_labels_all_persisted_artifacts_as_historical() -> None:
    text = (ROOT / "scripts/status_composer_background_loop_tmux.sh").read_text(
        encoding="utf-8"
    )

    assert "evidence_heading" in text
    assert 'evidence_heading "Run dir"' in text
    assert 'evidence_heading "Heartbeat"' in text
    assert 'evidence_heading "Recent receipts"' in text
    assert 'evidence_heading "Recent log"' in text
