import json
import os
import subprocess
import sys
from pathlib import Path


def test_algedonic_triage_uses_dharma_state_dir(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "algedonic_triage.py"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    stream = state_dir / "algedonic_signals.jsonl"
    stream.write_text(
        json.dumps(
            {
                "kind": "test_signal",
                "severity": "info",
                "action": "record_only",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env={**os.environ, "DHARMA_STATE_DIR": str(state_dir)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert f"triaged 1 new signals -> {state_dir / 'triage'}" in result.stdout
    assert (state_dir / "triage" / "state.json").exists()
    assert (state_dir / "triage" / "seen_pairs.json").exists()
    assert not (tmp_path / ".dharma").exists()
