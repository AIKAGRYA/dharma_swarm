from __future__ import annotations

import sys
from pathlib import Path

import pytest

from dharma_swarm import runtime_release_entrypoint


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_entrypoint_binds_scripts_to_the_admitted_release(monkeypatch) -> None:
    called: list[bool] = []
    monkeypatch.setenv("DHARMA_RELEASE_ROOT", str(REPO_ROOT))
    monkeypatch.setattr(sys, "argv", ["runtime-release", "orchestrate-live"])
    monkeypatch.setattr("dharma_swarm.dgc_cli.main", lambda: called.append(True))
    monkeypatch.setattr(
        sys,
        "path",
        [entry for entry in sys.path if entry != str(REPO_ROOT)],
    )

    runtime_release_entrypoint.main()

    assert called == [True]
    assert sys.path[0] == str(REPO_ROOT)


def test_entrypoint_rejects_a_different_release_root(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DHARMA_RELEASE_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["runtime-release", "orchestrate-live"])

    with pytest.raises(SystemExit, match="installed package does not match"):
        runtime_release_entrypoint.main()


def test_entrypoint_rejects_non_live_commands(monkeypatch) -> None:
    monkeypatch.setenv("DHARMA_RELEASE_ROOT", str(REPO_ROOT))
    monkeypatch.setattr(sys, "argv", ["runtime-release", "cron", "daemon"])

    with pytest.raises(SystemExit, match="only orchestrate-live"):
        runtime_release_entrypoint.main()
