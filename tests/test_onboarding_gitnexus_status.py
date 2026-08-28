"""Canonical, non-admission GitNexus status projection for compact onboarding."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.operator_core.onboarding import cli, gitnexus_status, render


REPO_ROOT = Path(__file__).resolve().parents[1]
ONBOARD_SCRIPT = REPO_ROOT / "scripts" / "governance" / "agent_onboard.py"


def _load_compatibility_shim() -> Any:
    spec = importlib.util.spec_from_file_location(
        "agent_onboard_gitnexus_status_contract",
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
                "branch": "test/onboarding-gitnexus",
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
        "extensions": {"gitnexus": status},
    }


def test_makefile_observes_gitnexus_without_gating_onboard() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "gitnexus-status:" in makefile
    assert "gitnexus-ensure:" in makefile
    assert "scripts/governance/gitnexus_ensure.py --status" in makefile
    assert "scripts/governance/gitnexus_ensure.py --ensure" in makefile
    onboard = makefile.split("onboard:\n", 1)[1].split("\n\n", 1)[0]
    assert "gitnexus-ensure" not in onboard
    assert "agent_onboard.py" in onboard


def test_ensure_upserts_stale_toml_without_touching_ready_pin(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "gitnexus_ensure_under_test",
        REPO_ROOT / "scripts" / "governance" / "gitnexus_ensure.py",
    )
    assert spec is not None and spec.loader is not None
    ensure = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ensure)

    ready = tmp_path / "ready.toml"
    ready.write_text(
        '[mcp_servers.gitnexus]\ncommand = "gitnexus"\nargs = ["mcp"]\n',
        encoding="utf-8",
    )
    assert (
        ensure._upsert_toml_section(
            ready, "mcp_servers.gitnexus", ensure._GROK_STANZA
        )
        is False
    )
    stale = tmp_path / "stale.toml"
    stale.write_text(
        '[cli]\ninstaller = "internal"\n\n'
        '[mcp_servers.gitnexus]\ncommand = "npx"\nargs = ["-y", "gitnexus@1.4.0", "mcp"]\n',
        encoding="utf-8",
    )
    assert (
        ensure._upsert_toml_section(
            stale, "mcp_servers.gitnexus", ensure._GROK_STANZA
        )
        is True
    )
    text = stale.read_text(encoding="utf-8")
    assert 'command = "gitnexus"' in text
    assert "gitnexus@1.4.0" not in text
    assert '[cli]' in text


def test_canonical_spec_contract_links_shim_and_collector() -> None:
    shim = _load_compatibility_shim()

    assert (
        gitnexus_status.SPEC_PATH
        == shim.GITNEXUS_SPEC_PATH
        == "docs/ops/AGENT_ONBOARDING.md"
    )
    assert gitnexus_status.PINNED_VERSION == "1.6.9"


def test_classify_mcp_pin_detects_stale_npx_and_global_binary() -> None:
    assert (
        gitnexus_status.classify_mcp_pin("npx", ["-y", "gitnexus@1.4.0", "mcp"])
        == "npx_stale"
    )
    assert (
        gitnexus_status.classify_mcp_pin("npx", ["-y", "gitnexus@1.6.9", "mcp"])
        == "npx_pinned"
    )
    assert (
        gitnexus_status.classify_mcp_pin("/Users/x/.npm-global/bin/gitnexus", ["mcp"])
        == "global_binary"
    )
    assert gitnexus_status.classify_mcp_pin("", []) == "missing"


def test_collection_reads_local_cli_mcp_and_index_meta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    binary = home / ".npm-global" / "bin" / "gitnexus"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    package = home / ".npm-global" / "lib" / "node_modules" / "gitnexus" / "package.json"
    package.parent.mkdir(parents=True)
    package.write_text(json.dumps({"version": "1.6.9"}), encoding="utf-8")
    (home / ".grok").mkdir()
    (home / ".grok" / "config.toml").write_text(
        '[mcp_servers.gitnexus]\ncommand = "gitnexus"\nargs = ["mcp"]\n',
        encoding="utf-8",
    )
    meta = repo / ".gitnexus" / "meta.json"
    meta.parent.mkdir(parents=True)
    meta.write_text(
        json.dumps(
            {
                "lastCommit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "schemaVersion": 5,
                "stats": {"nodes": 12},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(gitnexus_status, "shutil_which", lambda _name: None)
    monkeypatch.setattr(gitnexus_status, "_git_head", lambda _root: "aaaaaaaaaaaaaaaa")

    status = gitnexus_status.collect_gitnexus_status(home=home, repo_root=repo)

    assert status["schema"] == "dharma_swarm.onboard_gitnexus.v1"
    assert status["authority"] == "local_observation_only"
    assert status["probe_scope"] == "local_cli_mcp_and_index_meta_only"
    assert status["cli_present"] is True
    assert status["cli_version"] == "1.6.9"
    assert status["version_matches_pin"] is True
    assert status["mcp_wired"] is True
    assert status["index_present"] is True
    assert status["index_matches_head"] is True
    assert status["index_schema_version"] == 5
    assert status["index_node_count"] == 12
    assert status["live_mcp_claimed"] is False
    assert status["analyze_claimed"] is False


def test_collection_does_not_open_network_or_ladybug(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gitnexus_status, "shutil_which", lambda _name: None)

    def boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("gitnexus onboard collector must stay local")

    monkeypatch.setattr("socket.create_connection", boom)
    monkeypatch.setattr("urllib.request.urlopen", boom)

    status = gitnexus_status.collect_gitnexus_status(
        home=tmp_path / "empty-home",
        repo_root=tmp_path / "empty-repo",
    )
    assert status["cli_present"] is False
    assert status["mcp_wired"] is False
    assert status["index_present"] is False
    assert status["live_mcp_claimed"] is False
    assert status["analyze_claimed"] is False


def test_human_renderer_names_status_and_no_handshake_claim(tmp_path: Path) -> None:
    status = gitnexus_status.collect_gitnexus_status(
        home=tmp_path / "home",
        repo_root=tmp_path / "repo",
    )
    output = render.render_compact(_receipt(status))
    assert "GITNEXUS — LOCAL OBSERVATION ONLY" in output
    assert "No live MCP handshake or analyze is claimed." in output
    assert len(output.splitlines()) <= render.HUMAN_MAX_LINES


def test_json_renderer_projects_gitnexus_status(tmp_path: Path) -> None:
    status = gitnexus_status.collect_gitnexus_status(
        home=tmp_path / "home",
        repo_root=tmp_path / "repo",
    )
    projection = render.machine_projection(_receipt(status))
    assert projection["gitnexus"] == status
    assert projection["gitnexus"]["spec_path"] == "docs/ops/AGENT_ONBOARDING.md"
    assert projection["gitnexus"]["live_mcp_claimed"] is False


def test_gitnexus_observation_does_not_change_typed_exit_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = gitnexus_status.collect_gitnexus_status(
        home=tmp_path / "home",
        repo_root=tmp_path / "repo",
    )

    def run_with_wired(wired: bool, ops_name: str) -> tuple[int, str]:
        projection = {**base, "mcp_wired": wired}
        monkeypatch.setattr(
            cli.gitnexus_status,
            "collect_gitnexus_status",
            lambda: projection,
        )
        monkeypatch.setenv("DHARMA_OPS_DIR", str(tmp_path / ops_name))
        exit_code = cli.assemble_and_run(["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["gitnexus"]["mcp_wired"] is wired
        return exit_code, payload["verdict"]

    missing = run_with_wired(False, "ops-unwired")
    wired = run_with_wired(True, "ops-wired")
    assert missing == wired


def test_real_cli_projects_gitnexus_status_in_human_and_json_modes(
    tmp_path: Path,
) -> None:
    environment = {
        **os.environ,
        "DHARMA_OPS_DIR": str(tmp_path / "ops"),
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
    assert payload["gitnexus"]["schema"] == "dharma_swarm.onboard_gitnexus.v1"
    assert payload["gitnexus"]["live_mcp_claimed"] is False
    assert payload["gitnexus"]["analyze_claimed"] is False
    assert payload["gitnexus"]["pinned_version"] == "1.6.9"
    assert "GITNEXUS — LOCAL OBSERVATION ONLY" in human_result.stdout
    assert "No live MCP handshake or analyze is claimed." in human_result.stdout
