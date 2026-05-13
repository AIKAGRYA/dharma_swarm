from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm import world_radar_go_bridge as bridge


def test_bridge_incubates_single_source_high_upside(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = tmp_path / ".dharma"
    meta = state / "meta"
    meta.mkdir(parents=True)
    (meta / "world_operator_drops.jsonl").write_text(
        json.dumps(
            {
                "id": "raw-1",
                "source": "HN",
                "source_id": "hn",
                "title": "SubQ long context coding agent launch",
                "description": "Subquadratic inference workflow for AI agents.",
                "url": "https://example.test/subq",
                "family": "agent_infra",
                "keywords": ["subquadratic", "long context"],
            }
        )
        + "\n"
    )

    def fake_go(tool_dir: Path, args: list[str], *, timeout_s: int) -> str:
        if tool_dir.name == "world_signal_ingestor_go":
            output_path = Path(args[args.index("--output") + 1])
            output_path.write_text(
                json.dumps(
                    {
                        "id": "signal-1",
                        "source": "HN",
                        "category": "agent_infra",
                        "title": "SubQ long context coding agent launch",
                        "description": "Subquadratic inference workflow.",
                        "relevance_score": 0.91,
                        "keywords": ["subquadratic", "agent"],
                        "url": "https://example.test/subq",
                        "metadata": {"raw_source": "hn"},
                    }
                )
                + "\n"
            )
        return ""

    monkeypatch.setattr(bridge, "_run_go_tool", fake_go)

    result = bridge.run_world_radar_go_once(state_dir=state, repo_root=tmp_path)

    assert result.ok
    assert result.promotion_ready == 0
    assert result.incubations_written == 1
    assert result.board_path.exists()
    assert (meta / "world_zeitgeist_inbox.jsonl").read_text() == ""
    assert list((meta / "world_radar" / "incubations").glob("*.md"))


def test_bridge_promotes_operator_drop_with_url(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = tmp_path / ".dharma"
    meta = state / "meta"
    meta.mkdir(parents=True)
    (meta / "world_operator_drops.jsonl").write_text(
        json.dumps(
            {
                "id": "raw-1",
                "source": "operator_drop",
                "source_id": "operator_drop",
                "title": "SubQ long context coding agent company",
                "description": "Subquadratic inference workflow for AI agents.",
                "url": "https://example.test/subq",
                "family": "agent_infra",
                "keywords": ["subquadratic", "long context"],
            }
        )
        + "\n"
    )

    def fake_go(tool_dir: Path, args: list[str], *, timeout_s: int) -> str:
        if tool_dir.name == "world_signal_ingestor_go":
            output_path = Path(args[args.index("--output") + 1])
            output_path.write_text(
                json.dumps(
                    {
                        "id": "signal-1",
                        "source": "operator_drop",
                        "category": "agent_infra",
                        "title": "SubQ long context coding agent company",
                        "description": "Subquadratic inference workflow.",
                        "relevance_score": 0.91,
                        "keywords": ["subquadratic", "agent"],
                        "url": "https://example.test/subq",
                        "metadata": {"raw_source": "operator_drop"},
                    }
                )
                + "\n"
            )
        return ""

    monkeypatch.setattr(bridge, "_run_go_tool", fake_go)

    result = bridge.run_world_radar_go_once(state_dir=state, repo_root=tmp_path)

    assert result.promotion_ready == 1
    inbox_rows = [json.loads(line) for line in (meta / "world_zeitgeist_inbox.jsonl").read_text().splitlines()]
    assert inbox_rows[0]["metadata"]["promotion_status"] == "promotion_ready"
