from __future__ import annotations

import os
from pathlib import Path

from dharma_swarm.world_radar_go_bridge import run_world_radar_go_once


def test_world_radar_go_bridge_skips_when_inbox_missing(tmp_path: Path) -> None:
    result = run_world_radar_go_once(state_dir=tmp_path, module_dir=tmp_path)

    assert result.success is True
    assert result.skipped is True


def test_world_radar_go_bridge_runs_go_command(tmp_path: Path) -> None:
    state = tmp_path / "state"
    raw = state / "meta" / "world_radar_observations.jsonl"
    raw.parent.mkdir(parents=True)
    raw.write_text(
        '{"title":"New coding agent API launch","description":"agent api benchmark"}\n',
        encoding="utf-8",
    )

    fake_go = tmp_path / "go"
    fake_go.write_text(
        "#!/bin/sh\n"
        "out=''\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = '--output' ]; then shift; out=\"$1\"; fi\n"
        "  shift\n"
        "done\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "printf '%s\\n' '{\"id\":\"world_test\",\"title\":\"World test\"}' > \"$out\"\n",
        encoding="utf-8",
    )
    fake_go.chmod(fake_go.stat().st_mode | 0o111)

    result = run_world_radar_go_once(
        state_dir=state,
        module_dir=tmp_path,
        go_cmd=str(fake_go),
    )

    assert result.success is True
    assert result.skipped is False
    assert result.emitted_rows == 1
    assert os.path.exists(result.output_path)
