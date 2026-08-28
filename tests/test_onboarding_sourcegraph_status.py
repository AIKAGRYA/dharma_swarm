"""Canonical, non-admission Sourcegraph status projection for compact onboarding."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.operator_core.onboarding import cli, render, sourcegraph_status


REPO_ROOT = Path(__file__).resolve().parents[1]
ONBOARD_SCRIPT = REPO_ROOT / "scripts" / "governance" / "agent_onboard.py"


def _load_compatibility_shim() -> Any:
    spec = importlib.util.spec_from_file_location(
        "agent_onboard_sourcegraph_status_contract",
        ONBOARD_SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _receipt(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_verdict": "READY",
        "exit_code": 0,
        "stable_core": {
            "repository": {
                "branch": "test/onboarding-sourcegraph",
                "head": "1" * 40,
            },
            "portfolio": {"tracks": []},
            "orientation": {
                "broken_register": {},
                "static_surfaces": {},
            },
            "required_reading": [],
        },
        "live_delta": {
            "repo_state": {
                "base": "origin/main",
                "dirty": False,
                "conflicted": False,
                "ahead": 0,
                "behind": 0,
            },
            "conditions": [],
            "toolchain": {},
            "projection_freshness": {},
        },
        "extensions": {"sourcegraph": status},
    }


def test_canonical_spec_contract_links_shim_and_collector() -> None:
    shim = _load_compatibility_shim()

    assert (
        sourcegraph_status.SPEC_PATH
        == shim.SOURCEGRAPH_SPEC_PATH
        == "docs/ops/CODEX_TOOLBELT_ONBOARDING.md"
    )


def test_collection_classifies_public_dotcom_without_reading_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sourcegraph_status, "shutil_which", lambda _name: None)
    status = sourcegraph_status.collect_sourcegraph_status(
        home=tmp_path,
        environ={
            "SRC_ENDPOINT": "https://sourcegraph.com",
            "SRC_ACCESS_TOKEN": "super-secret-token",
        },
    )

    assert status["schema"] == "dharma_swarm.onboard_sourcegraph.v1"
    assert status["authority"] == "local_observation_only"
    assert status["probe_scope"] == "local_cli_and_env_only"
    assert status["endpoint_kind"] == "public_dotcom"
    assert status["endpoint_host"] == "sourcegraph.com"
    assert status["token_present"] is True
    assert "keychain_present" in status
    assert status["search_scope"] == "public_only"
    assert status["live_search_claimed"] is False
    assert status["repo_index_claimed"] is False
    dumped = json.dumps(status)
    assert "super-secret-token" not in dumped


def test_collection_reads_endpoint_from_dharma_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sourcegraph_status, "shutil_which", lambda _name: None)
    monkeypatch.setattr(sourcegraph_status, "_keychain_present", lambda _endpoint: True)
    env_dir = tmp_path / ".dharma"
    env_dir.mkdir()
    (env_dir / "sourcegraph.env").write_text(
        "SRC_ENDPOINT=https://example.sourcegraph.app\n",
        encoding="utf-8",
    )

    status = sourcegraph_status.collect_sourcegraph_status(
        home=tmp_path,
        environ={},
    )

    assert status["env_file_present"] is True
    assert status["endpoint_kind"] == "workspace"
    assert status["endpoint_host"] == "example.sourcegraph.app"
    assert status["search_scope"] == "workspace_capable"
    assert "example.sourcegraph.app" in json.dumps(status)


def test_collection_marks_workspace_capable_from_sourcegraph_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sourcegraph_status, "shutil_which", lambda _name: None)
    cli_path = tmp_path / ".local" / "bin" / "src"
    cli_path.parent.mkdir(parents=True)
    cli_path.write_text("#!/bin/sh\n", encoding="utf-8")
    cli_path.chmod(0o755)

    status = sourcegraph_status.collect_sourcegraph_status(
        home=tmp_path,
        environ={
            "SRC_ENDPOINT": "https://aikagrya.sourcegraph.app",
            "SRC_ACCESS_TOKEN": "workspace-token",
        },
    )

    assert status["src_cli_present"] is True
    assert status["src_cli_path"] == "~/.local/bin/src"
    assert status["endpoint_kind"] == "workspace"
    assert status["search_scope"] == "workspace_capable"
    assert "workspace-token" not in json.dumps(status)


def test_collection_does_not_open_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sourcegraph_status, "shutil_which", lambda _name: None)

    def boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("sourcegraph onboard collector must stay local")

    monkeypatch.setattr("socket.create_connection", boom)
    monkeypatch.setattr("urllib.request.urlopen", boom)

    status = sourcegraph_status.collect_sourcegraph_status(
        home=tmp_path,
        environ={},
    )
    assert status["search_scope"] == "unconfigured"
    assert status["src_cli_present"] is False
    assert status["live_search_claimed"] is False


def test_human_renderer_names_status_and_no_index_claim(tmp_path: Path) -> None:
    status = sourcegraph_status.collect_sourcegraph_status(
        home=tmp_path,
        environ={"SRC_ENDPOINT": "https://sourcegraph.com"},
    )

    output = render.render_compact(_receipt(status))

    assert "SOURCEGRAPH — LOCAL OBSERVATION ONLY" in output
    assert "endpoint: public_dotcom (sourcegraph.com)" in output
    assert "no live search or repo-index claim." in output


def test_json_renderer_projects_sourcegraph_status(tmp_path: Path) -> None:
    status = sourcegraph_status.collect_sourcegraph_status(
        home=tmp_path,
        environ={},
    )

    projection = render.machine_projection(_receipt(status))

    assert projection["sourcegraph"] == status
    assert projection["sourcegraph"]["spec_path"] == (
        "docs/ops/CODEX_TOOLBELT_ONBOARDING.md"
    )
    assert projection["sourcegraph"]["live_search_claimed"] is False
    assert projection["sourcegraph"]["repo_index_claimed"] is False


def test_real_cli_projects_sourcegraph_status_in_human_and_json_modes(
    tmp_path: Path,
) -> None:
    environment = {
        **os.environ,
        "DHARMA_OPS_DIR": str(tmp_path / "ops"),
        "SRC_ENDPOINT": "https://sourcegraph.com",
        "SRC_ACCESS_TOKEN": "do-not-echo-this-token",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    json_result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT), "--json"],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    human_result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT)],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )

    payload = json.loads(json_result.stdout)
    assert json_result.returncode == human_result.returncode == payload["exit_code"]
    assert payload["sourcegraph"]["endpoint_kind"] == "public_dotcom"
    assert payload["sourcegraph"]["token_present"] is True
    assert payload["sourcegraph"]["repo_index_claimed"] is False
    assert "do-not-echo-this-token" not in json_result.stdout
    assert "do-not-echo-this-token" not in human_result.stdout
    assert "SOURCEGRAPH — LOCAL OBSERVATION ONLY" in human_result.stdout
    assert "no live search or repo-index claim." in human_result.stdout


def test_sourcegraph_observation_does_not_change_typed_exit_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = sourcegraph_status.collect_sourcegraph_status(home=tmp_path, environ={})

    def run_with_scope(scope: str, ops_name: str) -> tuple[int, str]:
        projection = {**base, "search_scope": scope}
        monkeypatch.setattr(
            cli.sourcegraph_status,
            "collect_sourcegraph_status",
            lambda: projection,
        )
        monkeypatch.setenv("DHARMA_OPS_DIR", str(tmp_path / ops_name))
        exit_code = cli.assemble_and_run(["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["sourcegraph"]["search_scope"] == scope
        return exit_code, payload["verdict"]

    public = run_with_scope("public_only", "ops-public")
    workspace = run_with_scope("workspace_capable", "ops-workspace")
    assert public == workspace
