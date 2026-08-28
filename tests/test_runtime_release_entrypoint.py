from __future__ import annotations

import sys
import types
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


def test_entrypoint_forwards_only_semantic_responder_arguments(monkeypatch) -> None:
    called: list[list[str]] = []
    monkeypatch.setenv("DHARMA_RELEASE_ROOT", str(REPO_ROOT))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runtime-release",
            "codex-composer-semantic-responder",
            "loop",
            "--interval-s",
            "60",
            "--limit",
            "1",
        ],
    )
    monkeypatch.setattr(
        "scripts.runtime.codex_composer_semantic_responder.main",
        lambda args: called.append(args) or 9,
    )

    result = runtime_release_entrypoint.main()

    assert result == 9
    assert called == [["loop", "--interval-s", "60", "--limit", "1"]]


def test_entrypoint_forwards_only_governed_patch_responder_arguments(
    monkeypatch,
) -> None:
    called: list[list[str]] = []
    module_name = "scripts.runtime.governed_patch_responder"
    module = types.ModuleType(module_name)
    module.main = lambda args: called.append(args) or 10  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module_name, module)
    monkeypatch.setenv("DHARMA_RELEASE_ROOT", str(REPO_ROOT))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runtime-release",
            "governed-patch-responder",
            "once",
            "--packet-id",
            "packet-1",
            "--delivery-record",
            "delivery.json",
        ],
    )

    result = runtime_release_entrypoint.main()

    assert result == 10
    assert called == [
        [
            "once",
            "--packet-id",
            "packet-1",
            "--delivery-record",
            "delivery.json",
        ]
    ]


def test_entrypoint_rejects_mismatched_release_before_responder_dispatch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    called: list[list[str]] = []
    module_name = "scripts.runtime.governed_patch_responder"
    module = types.ModuleType(module_name)
    module.main = lambda args: called.append(args) or 10  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module_name, module)
    monkeypatch.setenv("DHARMA_RELEASE_ROOT", str(tmp_path))
    monkeypatch.setattr(
        sys,
        "argv",
        ["runtime-release", "governed-patch-responder", "serve"],
    )

    with pytest.raises(SystemExit, match="installed package does not match"):
        runtime_release_entrypoint.main()

    assert called == []


@pytest.mark.parametrize(
    ("command", "module_name"),
    (
        (
            "governed-patch-foundry-verifier",
            "scripts.runtime.governed_patch_foundry_verifier",
        ),
        (
            "governed-patch-vibe-verifier",
            "scripts.runtime.governed_patch_vibe_verifier",
        ),
    ),
)
def test_entrypoint_forwards_only_governed_verifier_arguments(
    monkeypatch,
    command: str,
    module_name: str,
) -> None:
    called: list[list[str]] = []
    module = types.ModuleType(module_name)
    module.main = lambda args: called.append(args) or 11  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module_name, module)
    monkeypatch.setenv("DHARMA_RELEASE_ROOT", str(REPO_ROOT))
    monkeypatch.setattr(
        sys,
        "argv",
        ["runtime-release", command, "--once", "bundle.json"],
    )

    result = runtime_release_entrypoint.main()

    assert result == 11
    assert called == [["--once", "bundle.json"]]


def test_entrypoint_leaves_responder_argument_validation_to_responder(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DHARMA_RELEASE_ROOT", str(REPO_ROOT))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runtime-release",
            "codex-composer-semantic-responder",
            "arbitrary.module",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        runtime_release_entrypoint.main()

    assert exc_info.value.code == 2


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
