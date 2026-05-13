from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm import world_radar_go_bridge as bridge


def test_world_radar_bridge_operator_drop_to_board(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = tmp_path / ".dharma"
    meta = state / "meta"
    meta.mkdir(parents=True)
    (meta / "world_operator_drops.jsonl").write_text(
        json.dumps(
            {
                "id": "drop-1",
                "source": "operator_drop",
                "source_id": "operator_drop",
                "title": "SubQ long context coding agent company",
                "description": "Subquadratic inference workflow for AI agents.",
                "url": "https://example.test/subq",
                "family": "agent_infra",
                "keywords": ["subquadratic", "long context"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_go(tool_dir: Path, args: list[str], *, timeout_s: int) -> str:
        if tool_dir.name == "world_signal_ingestor_go":
            input_path = Path(args[args.index("--input") + 1])
            output_path = Path(args[args.index("--output") + 1])
            raw = json.loads(input_path.read_text().splitlines()[0])
            output_path.write_text(
                json.dumps(
                    {
                        "id": "signal-1",
                        "source": "operator_drop",
                        "category": "agent_infra",
                        "title": raw["title"],
                        "description": raw["description"],
                        "relevance_score": 0.91,
                        "keywords": ["subquadratic", "agent"],
                        "url": raw["url"],
                        "metadata": {
                            "raw_source": "operator_drop",
                            "first_principles_questions": ["What primitive changed?"],
                            "iteration_steps": ["Verify source."],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        return ""

    monkeypatch.setattr(bridge, "_run_go_tool", fake_go)

    result = bridge.run_world_radar_go_once(
        state_dir=state,
        repo_root=tmp_path,
        scout_fetch=False,
        min_score=0.45,
    )

    assert result.ok
    assert result.raw_observations == 1
    assert result.emitted_signals == 1
    assert result.board_path.exists()
    assert result.brief_path.exists()
    assert (state / "world_feeds" / "world_signal_feed.jsonl").exists()
    assert (meta / "world_zeitgeist_inbox.jsonl").exists()
    board = json.loads(result.board_path.read_text())
    assert board["signal_count"] == 1
    assert board["movements"][0]["movement_id"] == "agent_infra:subquadratic"
    assert "World Signal Brief" in result.brief_path.read_text()


def test_world_radar_bridge_runs_gated_scout_when_enabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = tmp_path / ".dharma"

    def fake_go(tool_dir: Path, args: list[str], *, timeout_s: int) -> str:
        if tool_dir.name == "world_scout_go":
            output_path = Path(args[args.index("--output") + 1])
            health_path = Path(args[args.index("--health-output") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(
                    {
                        "id": "raw-1",
                        "source": "HN",
                        "source_id": "hn_agent_search",
                        "title": "Long context agent workflow",
                        "description": "Agent infrastructure signal.",
                        "family": "agent_infra",
                    }
                )
                + "\n"
            )
            health_path.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "source_id": "hn_agent_search",
                                "reachable": True,
                                "item_count": 1,
                            }
                        ]
                    }
                )
            )
        if tool_dir.name == "world_signal_ingestor_go":
            output_path = Path(args[args.index("--output") + 1])
            output_path.write_text(
                json.dumps(
                    {
                        "id": "signal-1",
                        "source": "HN",
                        "category": "agent_infra",
                        "title": "Long context agent workflow",
                        "description": "Agent infrastructure signal.",
                        "relevance_score": 0.72,
                        "keywords": ["long context", "agent"],
                        "metadata": {"raw_source": "hn_agent_search"},
                    }
                )
                + "\n"
            )
        return ""

    monkeypatch.setattr(bridge, "_run_go_tool", fake_go)

    result = bridge.run_world_radar_go_once(
        state_dir=state,
        repo_root=tmp_path,
        scout_fetch=True,
        min_score=0.45,
    )

    assert result.ok
    assert result.health_path.exists()
    assert json.loads(result.health_path.read_text())["sources"][0]["reachable"]
