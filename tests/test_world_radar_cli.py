from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.world_radar_cli import append_operator_drop, main


def test_append_operator_drop_writes_world_feed(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"

    path = append_operator_drop(
        title="SubQ managed agent runtime",
        url="https://example.com/subq",
        note="Operator saw this in the public world.",
        tags=("agentic", "runtime"),
        state_dir=state,
    )

    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["source"] == "operator_drop"
    assert row["source_type"] == "operator_drop"
    assert row["url"] == "https://example.com/subq"
    assert row["keywords"] == ["agentic", "runtime"]


def test_world_radar_cli_drop(tmp_path: Path, capsys) -> None:
    state = tmp_path / ".dharma"

    rc = main(
        [
            "drop",
            "--title",
            "Public launch signal",
            "--url",
            "https://example.com/launch",
            "--note",
            "Worth tracking",
            "--tag",
            "startup",
            "--state-dir",
            str(state),
        ]
    )

    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("world_operator_drops.jsonl")
    assert (state / "meta" / "world_operator_drops.jsonl").exists()
