from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

from dharma_swarm.daily_operating_brief import (
    WITA,
    build_daily_operating_brief,
    load_yds_ratings,
)


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _run(["git", "init"], cwd=repo).returncode == 0
    assert _run(["git", "config", "user.email", "test@example.invalid"], cwd=repo).returncode == 0
    assert _run(["git", "config", "user.name", "Test User"], cwd=repo).returncode == 0
    (repo / "README.md").write_text("# Repo\n", encoding="utf-8")
    assert _run(["git", "add", "README.md"], cwd=repo).returncode == 0
    assert _run(["git", "commit", "-m", "init"], cwd=repo).returncode == 0
    return repo


def _now() -> datetime:
    return datetime(2026, 5, 9, 4, 30, tzinfo=WITA)


def test_daily_operating_brief_composes_existing_signals(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    state = tmp_path / ".dharma"
    output = tmp_path / "briefs"

    (repo / "SWARM_HOT_ITEMS.md").write_text(
        "\n".join(
            [
                "# Hot Items",
                "",
                "## Current Verdict",
                "",
                "The repo has useful AgentOps substrate.",
                "",
                "## Hot Items",
                "",
                "- Keep dashboard/API expansion parked.",
                "- Make daily truth visible.",
            ]
        ),
        encoding="utf-8",
    )
    (repo / "ACTIVE_SURFACE_MANIFEST.yaml").write_text(
        "api:\n  status: active\nprojection:\n  status: projection\nfrozen:\n  status: frozen\n",
        encoding="utf-8",
    )
    runs = repo / ".dharma" / "agentops" / "runs"
    runs.mkdir(parents=True)
    (runs / "packet.json").write_text(
        json.dumps(
            {
                "packet_id": "agentops-v0",
                "status": "passed",
                "finished_at": "2026-05-09T00:00:00+00:00",
                "commands": [{"name": "tests", "exit_code": 0}],
                "violations": [],
            }
        ),
        encoding="utf-8",
    )

    state.mkdir()
    (state / "cost_log.jsonl").write_text(
        json.dumps(
            {
                "timestamp": _now().timestamp(),
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 1000,
                "output_tokens": 500,
                "estimated_cost_usd": 0.005,
                "tier": "T2",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    yds_dir = state / "ysd"
    yds_dir.mkdir()
    (yds_dir / "ledger.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-05-09T00:00:00+00:00",
                "target": "docs/governance/AGENTOPS.md",
                "grade": "5.13a",
                "note": "useful narrow substrate",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    artifacts = state / "artifacts"
    artifacts.mkdir()
    (artifacts / "aligned_revenue_engines_garden.md").write_text("ready\n", encoding="utf-8")

    brief = build_daily_operating_brief(
        repo_root=repo,
        state_dir=state,
        output_dir=output,
        now_fn=_now,
    )

    assert brief.path == output / "2026-05-09-operating.md"
    assert brief.path.exists()
    assert "# Daily Operating Brief - 2026-05-09" in brief.content
    assert "Dirty state:" in brief.content
    assert "active=1, frozen=1, projection=1" in brief.content
    assert "`agentops-v0` status=passed" in brief.content
    assert "1 call(s), $0.0050" in brief.content
    assert "`5.13a` docs/governance/AGENTOPS.md" in brief.content
    assert "Aligned revenue engines garden exists" in brief.content
    assert "Do not expand dashboard/API/autonomy surfaces" in brief.content


def test_daily_operating_brief_handles_missing_sources(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    state = tmp_path / ".dharma"
    brief = build_daily_operating_brief(
        repo_root=repo,
        state_dir=state,
        output_dir=tmp_path / "briefs",
        now_fn=_now,
    )

    assert "No AgentOps run reports found" in brief.content
    assert "No cost entries found" in brief.content
    assert "No human YDS ratings found" in brief.content
    assert "no local ontology database found" in brief.content
    assert "Register one human YDS rating" in brief.content


def test_daily_operating_brief_reads_ontology_counts_read_only(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    state = tmp_path / ".dharma"
    state.mkdir()
    db = state / "ontology.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE objects (id TEXT PRIMARY KEY, type_name TEXT NOT NULL)")
        conn.executemany(
            "INSERT INTO objects (id, type_name) VALUES (?, ?)",
            [
                ("outcome-1", "Outcome"),
                ("value-1", "ValueEvent"),
                ("value-2", "ValueEvent"),
                ("contribution-1", "Contribution"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    before = db.read_bytes()
    brief = build_daily_operating_brief(
        repo_root=repo,
        state_dir=state,
        output_dir=tmp_path / "briefs",
        now_fn=_now,
    )

    assert "Outcome=1, ValueEvent=2, Contribution=1" in brief.content
    assert db.read_bytes() == before


def test_yds_loader_accepts_jsonl_and_human_command_phrase(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "target": "artifact-a.md",
                        "grade": "5.12b",
                        "note": "solid",
                        "timestamp": "2026-05-09T00:00:00+00:00",
                    }
                ),
                "YDS: rate artifact-b.md 5.13a - rare useful clarity",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ratings = load_yds_ratings(ledger)

    assert [rating.target for rating in ratings] == ["artifact-a.md", "artifact-b.md"]
    assert ratings[1].grade == "5.13a"
    assert ratings[1].note == "rare useful clarity"
