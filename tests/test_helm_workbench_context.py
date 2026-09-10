"""Behavior at the generated-config and read-only backend boundaries."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.helm_desktop.config import DesktopConfig, DesktopError
from dharma_swarm.helm_desktop.workbench_context import (
    INSTRUCTIONS_PATH,
    prepare_workbench_context,
    workbench_context_config,
)
from dharma_swarm.helm_desktop.workbench_mcp import (
    WorkbenchMemory,
    _memory_kernel,
    create_workbench_mcp,
)


@pytest.fixture
def config(tmp_path: Path) -> DesktopConfig:
    repo = tmp_path / "source tree"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts/start_terminal_tui_tmux.sh").write_text("#!/bin/sh\n")
    (repo / "AGENTS.md").write_text("Follow CLAUDE.md.\n")
    (repo / "CLAUDE.md").write_text("Keep source and runtime state separate.\n")
    return DesktopConfig(repo, tmp_path / "private state")


def test_config_preview_does_not_write_or_start_backend(config: DesktopConfig) -> None:
    fragment = workbench_context_config(config)
    assert not config.state_dir.exists()
    assert set(fragment) == {"instructions", "mcp"}
    assert all(Path(path).is_absolute() for path in fragment["instructions"])
    backend = fragment["mcp"]["dharma"]
    assert backend["command"][-2:] == ["--repo-root", str(config.repo_root)]
    assert backend["environment"] == {
        "PYTHONPATH": str(config.repo_root), "PYTHONDONTWRITEBYTECODE": "1",
    }


def test_prepare_private_and_idempotent_without_global_config_changes(
    config: DesktopConfig, tmp_path: Path,
) -> None:
    global_config = tmp_path / "global opencode.json"
    global_config.write_text('{"model":"operator-selected"}\n')
    before = {path: path.read_bytes() for path in config.repo_root.rglob("*") if path.is_file()}
    fragment = prepare_workbench_context(config)
    generated = config.state_dir / INSTRUCTIONS_PATH
    first_stat = generated.stat()
    assert first_stat.st_mode & 0o777 == 0o600
    assert generated.parent.stat().st_mode & 0o777 == 0o700
    assert fragment["instructions"][0] == str(generated)
    assert str(config.repo_root) in generated.read_text()
    assert prepare_workbench_context(config) == fragment
    assert generated.stat().st_mtime_ns == first_stat.st_mtime_ns
    assert {path: path.read_bytes() for path in before} == before
    assert json.loads(global_config.read_text()) == {"model": "operator-selected"}


def test_venv_python_symlink_is_preserved(config: DesktopConfig, tmp_path: Path) -> None:
    python = tmp_path / "venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    fragment = workbench_context_config(config, python_executable=str(python))
    assert fragment["mcp"]["dharma"]["command"][0] == str(python)


@pytest.mark.parametrize("target", ["workbench", INSTRUCTIONS_PATH])
def test_prepare_refuses_symlink_escape(
    config: DesktopConfig, tmp_path: Path, target: str,
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    sentinel = other / "operator.md"
    sentinel.write_text("Keep this unchanged.\n")
    link = config.state_dir / target
    link.parent.mkdir(parents=True)
    link.symlink_to(other if target == "workbench" else sentinel)
    with pytest.raises(DesktopError, match="symlink"):
        prepare_workbench_context(config)
    assert sentinel.read_text() == "Keep this unchanged.\n"


def test_prepare_preserves_unowned_instruction_file(config: DesktopConfig) -> None:
    path = config.state_dir / INSTRUCTIONS_PATH
    path.parent.mkdir(parents=True)
    path.write_text("Operator customization.\n")
    with pytest.raises(DesktopError, match="unowned"):
        prepare_workbench_context(config)
    assert path.read_text() == "Operator customization.\n"


def test_repo_instruction_symlink_is_not_attached(config: DesktopConfig, tmp_path: Path) -> None:
    private = tmp_path / "private.md"
    private.write_text("Not repository instructions.\n")
    (config.repo_root / "CLAUDE.md").unlink()
    (config.repo_root / "CLAUDE.md").symlink_to(private)
    with pytest.raises(DesktopError, match="symlinks"):
        prepare_workbench_context(config)
    assert not config.state_dir.exists()


@pytest.fixture
def memory(config: DesktopConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WorkbenchMemory:
    from dharma_swarm.chetana import manifest

    signature = "f" * 64
    monkeypatch.setattr(manifest, "_resolve_kernel_signature", lambda: signature)
    manifest.clear_manifest_cache()
    home = tmp_path / "memory home"
    wiki = home / ".dharma/knowledge/wiki"
    wiki.mkdir(parents=True)
    pages = {
        "helm.md": "# Helm\n\nHelm has a keyboard workbench. API_KEY=fixture-secret-value\n",
        "mission.md": "# Mission\n\nMission completion needs observed evidence.\n",
        "unsigned.md": "# Helm\n\nUnsigned content must never enter the preview.\n",
    }
    for name, text in pages.items():
        (wiki / name).write_text(text)
    manifest.write_manifest(
        [manifest.manifest_entry_for_file(wiki / name, root=wiki, tier="gold")
         for name in ("helm.md", "mission.md")],
        manifest_file=wiki / "MANIFEST.jsonl", kernel_signature=signature,
    )
    yield WorkbenchMemory(config.repo_root, kernel_factory=lambda repo: _memory_kernel(repo, home=home))
    manifest.clear_manifest_cache()


def test_memory_uses_manifest_admission_redaction_and_preserves_truth_state(
    memory: WorkbenchMemory,
) -> None:
    result = memory.memory_context("Helm", limit=1)
    serialized = json.dumps(result)
    assert result["available"] is True
    assert result["read_only"] is True
    assert result["pack"]["admitted_count"] == 1
    admitted = [item for item in result["pack"]["items"] if item["admitted"]]
    assert "keyboard workbench" in admitted[0]["content_snippet"]
    assert admitted[0]["truth_state"] == "claimed"
    assert "fixture-secret-value" not in serialized
    assert "Unsigned content" not in serialized
    assert result["pack"]["total_selected_chars"] <= 4000


def test_memory_missing_state_is_observed_without_creating_it(
    config: DesktopConfig, tmp_path: Path,
) -> None:
    home = tmp_path / "absent memory home"
    memory = WorkbenchMemory(config.repo_root, kernel_factory=lambda repo: _memory_kernel(repo, home=home))
    result = memory.memory_context("helm")
    assert result["available"] is False
    assert result["pack"]["admitted_count"] == 0
    assert not home.exists()


@pytest.mark.parametrize("query,limit", [("a" * 513, 1), ("x\0y", 1), ("", 0), ("", 9), ("", True)])
def test_invalid_memory_requests_do_not_read_backend(
    config: DesktopConfig, query: str, limit: int,
) -> None:
    def forbidden(_: Path) -> Any:
        pytest.fail("invalid requests must not read memory")
    with pytest.raises(ValueError):
        WorkbenchMemory(config.repo_root, kernel_factory=forbidden).memory_context(query, limit)


@pytest.mark.asyncio
async def test_mcp_exposes_only_existing_reads_and_does_not_initialize_runtime(
    config: DesktopConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("mcp")
    from mcp.server.fastmcp.exceptions import ToolError
    from dharma_swarm.mission_control_mcp import MUTATION_TOOL_NAMES, READ_TOOL_NAMES

    state = tmp_path / "missing runtime"
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state))
    server = create_workbench_mcp(config.repo_root)
    tools = {tool.name: tool for tool in await server.list_tools()}
    assert set(tools) == {*READ_TOOL_NAMES, "memory_context"}
    assert all(tool.annotations.readOnlyHint for tool in tools.values())
    for name in MUTATION_TOOL_NAMES:
        with pytest.raises(ToolError):
            await server.call_tool(name, {})
    result = await server.call_tool("mission_get", {"mission_id": "missing"})
    structured = result[1] if isinstance(result, tuple) else result
    assert structured["ok"] is False
    assert not state.exists()


@pytest.mark.asyncio
async def test_configured_mcp_command_completes_stdio_handshake(tmp_path: Path) -> None:
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    repo = Path(__file__).resolve().parents[1]
    config = DesktopConfig(repo, tmp_path / "desktop")
    backend = workbench_context_config(config)["mcp"]["dharma"]
    state = tmp_path / "runtime absent"
    params = StdioServerParameters(
        command=backend["command"][0], args=backend["command"][1:],
        env={**backend["environment"], "DHARMA_STATE_DIR": str(state)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            assert {tool.name for tool in listed.tools} == {
                "mission_get", "mission_snapshot", "mission_list_tasks", "memory_context",
            }
            result = await session.call_tool("mission_get", {"mission_id": "absent"})
            assert result.structuredContent["ok"] is False
    assert not config.state_dir.exists()
    assert not state.exists()
