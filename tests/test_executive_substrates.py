from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.executive_substrates import (
    build_memory_pressure_snapshot,
    build_role_ecology_snapshot,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def test_role_ecology_snapshot_detects_seeded_and_active_agents(tmp_path: Path):
    state_dir = tmp_path / ".dharma"
    state_dir.mkdir()
    (state_dir / "context" / "distilled").mkdir(parents=True)
    (state_dir / "context" / "distilled" / "builder_distilled.md").write_text("builder summary")

    now = datetime.now(timezone.utc).timestamp()
    _write_jsonl(
        state_dir / "cost_log.jsonl",
        [
            {
                "timestamp": now,
                "agent_name": "builder",
                "source": "agent_runner",
                "execution_mode": "persistent_agent",
            },
            {
                "timestamp": now,
                "agent_name": "cyber-opus",
                "source": "swarm.coordination_synthesis",
                "execution_mode": "persistent_agent",
            },
        ],
    )
    _write_jsonl(
        state_dir / "stigmergy" / "marks.jsonl",
        [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": "builder",
                "file_path": "task:abc123",
            }
        ],
    )

    snap = build_role_ecology_snapshot(state_dir=state_dir)
    by_name = {a.name: a for a in snap.agents}

    assert snap.seeded_agents >= 4
    assert snap.active_agents_72h >= 2
    assert by_name["builder"].distill_exists is True
    assert by_name["builder"].cost_calls_72h == 1
    assert by_name["cyber-opus"].active_72h is True
    assert "architect" in snap.underexpressed_roles or "validator" in snap.underexpressed_roles


def test_memory_pressure_snapshot_detects_promises_and_loops(tmp_path: Path):
    state_dir = tmp_path / ".dharma"
    (state_dir / "context" / "distilled").mkdir(parents=True)
    (state_dir / "shared").mkdir(parents=True)
    (state_dir / "artifacts" / "research").mkdir(parents=True)
    (state_dir / "cron_logs").mkdir(parents=True)
    (state_dir / "context" / "distilled" / "researcher_distilled.md").write_text("researcher summary")
    (state_dir / "vectors.db").write_bytes(b"x" * 4096)

    for name in [
        "aaa_synthesize_disagreement_eval_probe_task.md",
        "bbb_synthesize_disagreement_eval_probe_task.md",
        "ccc_synthesize_disagreement_eval_probe_task.md",
        "ddd_synthesize_disagreement_follow_up_latent.md",
    ]:
        (state_dir / "shared" / name).write_text("content")

    (state_dir / "artifacts" / "research" / "brief.md").write_text("artifact")
    (state_dir / "cron_logs" / "2026-04-14_00-30_heartbeat.md").write_text(
        "- { promise: \"Run R_V experiment\", status: \"not started\" }\n"
        "- { promise: \"Connect with Laukkonen\", status: \"blocked — after paper on arXiv\" }\n"
    )
    _write_jsonl(
        state_dir / "stigmergy" / "marks.jsonl",
        [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": "shakti-pulse",
                "file_path": "gauntlet.py",
                "salience": 1.0,
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": "builder",
                "file_path": "gauntlet.py",
                "salience": 0.8,
            },
        ],
    )

    snap = build_memory_pressure_snapshot(state_dir=state_dir)

    assert "researcher" in snap.distilled_roles
    assert any("Run R_V experiment" in line for line in snap.unresolved_promises)
    assert any(item.startswith("eval_probe_loop:") for item in snap.repeated_loop_signatures)
    assert any("gauntlet.py" in item for item in snap.top_stigmergy_hotspots)
    assert snap.memory_health["vectors_db_exists"] is True

