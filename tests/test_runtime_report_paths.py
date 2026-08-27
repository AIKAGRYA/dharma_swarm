from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from dharma_swarm.daemon_config import runtime_report_dir


def test_runtime_report_dir_honors_state_authority(monkeypatch, tmp_path: Path) -> None:
    state_root = tmp_path / "runtime-state"
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state_root))
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path / "lower-priority-home"))

    assert runtime_report_dir("a2a", "send_receipts") == (
        state_root / "reports" / "a2a" / "send_receipts"
    )


@pytest.mark.parametrize("parts", [("..", "repo"), ("/tmp", "receipts")])
def test_runtime_report_dir_rejects_authority_escape(parts: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="below the Dharma report root"):
        runtime_report_dir(*parts)


def test_runtime_receipt_defaults_are_outside_the_repository(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    state_root = tmp_path / "runtime-state"
    probe = textwrap.dedent(
        """\
        from pathlib import Path

        from api.routers import control_surface
        from dharma_swarm.daemon_config import runtime_report_dir
        from scripts.runtime import (
            a2a_domain_reply_artifact,
            a2a_domain_reply_worker,
            a2a_inbox_bridge,
            a2a_reply_capture,
            a2a_send,
            codex_composer_semantic_inbox_drain,
            codex_composer_semantic_responder,
            model_critic_runner,
            palantir_pilot_a2a_worker,
        )

        report_root = runtime_report_dir()
        repo_root = Path.cwd()
        defaults = (
            a2a_send.DEFAULT_RECEIPT_DIR,
            a2a_inbox_bridge.DEFAULT_RECEIPT_DIR,
            a2a_reply_capture.DEFAULT_SEND_RECEIPT_ROOT,
            a2a_reply_capture.DEFAULT_REPLY_RECEIPT_ROOT,
            a2a_domain_reply_worker.DEFAULT_RECEIPT_DIR,
            a2a_domain_reply_artifact.DEFAULT_ARTIFACT_RECEIPT_DIR,
            codex_composer_semantic_inbox_drain.DEFAULT_DRAIN_RECEIPT_DIR,
            codex_composer_semantic_inbox_drain.DEFAULT_SEMANTIC_RECEIPT_DIR,
            codex_composer_semantic_responder.DEFAULT_SEND_RECEIPT_ROOT,
            model_critic_runner.DEFAULT_OUT_DIR,
            palantir_pilot_a2a_worker.DEFAULT_RECEIPT_DIR,
            control_surface._A2A_SEND_RECEIPT_ROOT,
            control_surface._A2A_INBOX_BRIDGE_RECEIPT_ROOT,
            control_surface._A2A_DOMAIN_REPLY_RECEIPT_ROOT,
            control_surface._A2A_REPLY_RECEIPT_ROOT,
            control_surface._SEMANTIC_RECEIPT_ROOT,
        )

        for path in defaults:
            assert path.is_relative_to(report_root), (path, report_root)
            assert not path.is_relative_to(repo_root), (path, repo_root)
        """
    )
    env = os.environ.copy()
    env.update(
        {
            "DHARMA_STATE_DIR": str(state_root),
            "DHARMA_HOME": str(tmp_path / "lower-priority-home"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
