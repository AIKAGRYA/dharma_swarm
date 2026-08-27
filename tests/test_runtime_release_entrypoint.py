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

    result = runtime_release_entrypoint.main()

    assert called == [True]
    assert result == 0
    assert sys.path[0] == str(REPO_ROOT)


def test_entrypoint_rejects_a_different_release_root(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DHARMA_RELEASE_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["runtime-release", "orchestrate-live"])

    with pytest.raises(SystemExit, match="installed package does not match"):
        runtime_release_entrypoint.main()


def test_entrypoint_forwards_only_bridge_arguments(monkeypatch) -> None:
    called: list[list[str]] = []
    monkeypatch.setenv("DHARMA_RELEASE_ROOT", str(REPO_ROOT))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runtime-release",
            "a2a-inbox-bridge",
            "--agent-uid",
            "codex_composer",
            "--consumer",
            "codex_composer_inbox",
        ],
    )
    monkeypatch.setattr(
        "scripts.runtime.a2a_inbox_bridge.main",
        lambda args: called.append(args) or 7,
    )

    result = runtime_release_entrypoint.main()

    assert result == 7
    assert called == [
        [
            "--agent-uid",
            "codex_composer",
            "--consumer",
            "codex_composer_inbox",
        ]
    ]


def test_entrypoint_rejects_unknown_commands(monkeypatch) -> None:
    monkeypatch.setenv("DHARMA_RELEASE_ROOT", str(REPO_ROOT))
    monkeypatch.setattr(sys, "argv", ["runtime-release", "cron", "daemon"])

    with pytest.raises(SystemExit, match="supported commands"):
        runtime_release_entrypoint.main()


def test_entrypoint_rejects_orchestrate_arguments(monkeypatch) -> None:
    monkeypatch.setenv("DHARMA_RELEASE_ROOT", str(REPO_ROOT))
    monkeypatch.setattr(
        sys,
        "argv",
        ["runtime-release", "orchestrate-live", "--background"],
    )

    with pytest.raises(SystemExit, match="accepts no arguments"):
        runtime_release_entrypoint.main()
