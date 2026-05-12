from __future__ import annotations

import json
import os
from pathlib import Path

from dharma_swarm.world_radar_go_bridge import run_world_radar_go_once


def test_world_radar_go_bridge_skips_when_no_inputs(tmp_path: Path) -> None:
    result = run_world_radar_go_once(state_dir=tmp_path, module_dir=tmp_path)

    assert result.success is True
    assert result.skipped is True


def test_world_radar_go_bridge_merges_manual_drop_and_writes_board(tmp_path: Path) -> None:
    state = tmp_path / "state"
    manual = state / "meta" / "world_operator_drops.jsonl"
    manual.parent.mkdir(parents=True)
    manual.write_text(
        json.dumps(
            {
                "id": "manual_subq",
                "source": "operator_ig_drop",
                "source_url": "https://subq.ai/",
                "title": "SubQ claims subquadratic long-context LLM for coding agents",
                "description": "OpenAI-compatible API and coding-agent workflow launch.",
                "keywords": ["SubQ", "subquadratic", "long context", "coding agents"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    fake_go = _fake_go(tmp_path)
    result = run_world_radar_go_once(
        state_dir=state,
        module_dir=tmp_path,
        go_cmd=str(fake_go),
    )

    assert result.success is True
    assert result.skipped is False
    assert result.emitted_rows == 1
    assert os.path.exists(result.output_path)
    assert os.path.exists(result.brief_path)
    board = json.loads(Path(result.board_path).read_text(encoding="utf-8"))
    assert board["signals"][0]["title"].startswith("SubQ claims")
    assert board["signals"][0]["source_url"] == "https://subq.ai/"
    assert board["signals"][0]["uncertainty"] in {"self_reported", "unverified", "corroborated"}
    brief = Path(result.brief_path).read_text(encoding="utf-8")
    assert "World Signal Brief" in brief


def test_world_radar_go_bridge_runs_gated_scout(tmp_path: Path) -> None:
    state = tmp_path / "state"
    fake_go = _fake_go(tmp_path)

    result = run_world_radar_go_once(
        state_dir=state,
        module_dir=tmp_path,
        scout_module_dir=tmp_path,
        go_cmd=str(fake_go),
        scout_fetch=True,
    )

    assert result.success is True
    assert result.scout_skipped is False
    assert result.scout_rows == 1
    assert result.health_path
    raw = (state / "meta" / "world_radar_observations.jsonl").read_text(encoding="utf-8")
    assert "Scout-discovered coding agent API launch" in raw


def _fake_go(tmp_path: Path) -> Path:
    fake_go = tmp_path / "go"
    fake_go.write_text(
        "#!/bin/sh\n"
        "out=''\n"
        "health=''\n"
        "fetch=0\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = '--output' ]; then shift; out=\"$1\"; fi\n"
        "  if [ \"$1\" = '--health-output' ]; then shift; health=\"$1\"; fi\n"
        "  if [ \"$1\" = '--fetch' ]; then fetch=1; fi\n"
        "  shift\n"
        "done\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "if [ \"$fetch\" = '1' ]; then\n"
        "  printf '%s\\n' '{\"id\":\"scout_signal\",\"source\":\"world_scout_go:product_company\",\"source_url\":\"https://example.com/scout\",\"title\":\"Scout-discovered coding agent API launch\",\"description\":\"agent api benchmark launch\",\"keywords\":[\"agent\",\"api\",\"benchmark\"]}' > \"$out\"\n"
        "  if [ -n \"$health\" ]; then mkdir -p \"$(dirname \"$health\")\"; printf '%s\\n' '{\"observed_at\":\"2026-05-12T00:00:00Z\",\"fetch_enabled\":true,\"source_count\":6,\"reachable_count\":6,\"item_count\":1,\"sources\":[]}' > \"$health\"; fi\n"
        "else\n"
        "  printf '%s\\n' '{\"id\":\"world_subq\",\"source\":\"world_radar_go\",\"source_url\":\"https://subq.ai/\",\"category\":\"model_release\",\"title\":\"SubQ claims subquadratic long-context LLM for coding agents\",\"relevance_score\":0.98,\"keywords\":[\"SubQ\",\"coding agents\"],\"description\":\"External launch signal.\",\"metadata\":{\"advancement_pressure\":\"research and prototype\",\"adjacent_search_queries\":[\"SubQ competitors\"],\"strategic_moves\":[\"teardown\"]}}' > \"$out\"\n"
        "fi\n",
        encoding="utf-8",
    )
    fake_go.chmod(fake_go.stat().st_mode | 0o111)
    return fake_go
