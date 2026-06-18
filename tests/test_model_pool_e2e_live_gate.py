"""Guards for model-pool E2E live-call opt-in behavior."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_model_pool_e2e_live_mode_requires_env_gate(monkeypatch) -> None:
    monkeypatch.delenv("DHARMA_LIVE_MODEL_E2E", raising=False)
    repo = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("DHARMA_LIVE_MODEL_E2E", None)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify/model_pool_e2e.py",
            "--live",
            "--no-refresh",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 2
    assert "DHARMA_LIVE_MODEL_E2E=1" in result.stdout


def test_model_routing_live_probe_requires_env_gate(monkeypatch) -> None:
    monkeypatch.delenv("DHARMA_LIVE_MODEL_E2E", raising=False)
    repo = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("DHARMA_LIVE_MODEL_E2E", None)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify/model_routing_live_probe.py",
            "--live",
            "--no-refresh",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 2
    assert "DHARMA_LIVE_MODEL_E2E=1" in result.stdout
