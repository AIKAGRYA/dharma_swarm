from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.world_radar_go_bridge import run_world_radar_go_once


def test_world_radar_bridge_promotes_operator_drop(monkeypatch, tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    meta = state / "meta"
    meta.mkdir(parents=True)
    (meta / "world_operator_drops.jsonl").write_text(
        json.dumps(
            {
                "id": "drop-1",
                "source": "operator_drop",
                "title": "SubQ agent infrastructure startup",
                "description": "Agentic coding runtime benchmark and market signal.",
                "url": "https://subq.ai/",
                "keywords": ["agentic", "startup"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_ingestor(**kwargs):
        input_path = kwargs["input_path"]
        rows = [json.loads(line) for line in input_path.read_text().splitlines()]
        for row in rows:
            row.update(
                {
                    "source": "operator_drop",
                    "raw_source": "operator_drop",
                    "category": "company",
                    "relevance_score": 0.92,
                    "metadata": {
                        "raw_source": "operator_drop",
                        "url": row["url"],
                        "iteration_steps": [f"step {idx}" for idx in range(10)],
                    },
                }
            )
        kwargs["output_path"].write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )
        return rows, None

    monkeypatch.setattr("dharma_swarm.world_radar_go_bridge._run_go_ingestor", fake_ingestor)

    result = run_world_radar_go_once(state_dir=state, scout_fetch=False)

    assert result.ok is True
    assert result.promotion_ready == 1
    assert Path(result.board_path).exists()
    inbox = (meta / "world_zeitgeist_inbox.jsonl").read_text()
    assert "SubQ agent infrastructure startup" in inbox
    assert "promotion_ready" in inbox


def test_world_radar_bridge_incubates_single_source(monkeypatch, tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    meta = state / "meta"
    meta.mkdir(parents=True)
    (meta / "world_scout_observations.jsonl").write_text(
        json.dumps(
            {
                "id": "hn-1",
                "source": "hacker_news",
                "title": "Single public source world signal",
                "description": "Agentic runtime discussion.",
                "url": "https://news.ycombinator.com/item?id=42",
                "keywords": ["agentic"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_ingestor(**kwargs):
        row = json.loads(kwargs["input_path"].read_text().splitlines()[0])
        row.update(
            {
                "source": "world_scout",
                "raw_source": "hacker_news",
                "category": "company",
                "relevance_score": 0.76,
                "metadata": {"raw_source": "hacker_news", "url": row["url"]},
            }
        )
        kwargs["output_path"].write_text(json.dumps(row) + "\n", encoding="utf-8")
        return [row], None

    monkeypatch.setattr("dharma_swarm.world_radar_go_bridge._run_go_ingestor", fake_ingestor)

    result = run_world_radar_go_once(state_dir=state, scout_fetch=False)

    assert result.promotion_ready == 0
    assert result.incubations_written == 2
    assert list((meta / "world_radar" / "incubations").glob("*.md"))
