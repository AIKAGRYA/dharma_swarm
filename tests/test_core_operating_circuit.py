from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from dharma_swarm.operator_core.operating_facts import (
    OperatingFactInputs,
    append_human_yds_rating,
    build_operating_fact_bundle,
    organ_state_facts,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


agentops = _load_script("run_agent_work_packet_core_proof", REPO_ROOT / "scripts/governance/run_agent_work_packet.py")
kaizen = _load_script("kaizen_review_from_agentops_core_proof", REPO_ROOT / "scripts/governance/kaizen_review_from_agentops.py")
system_map = _load_script("system_map_populator_core_proof", REPO_ROOT / "scripts/system_map_populator.py")


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _run(["git", "init"], cwd=repo).returncode == 0
    assert _run(["git", "config", "user.email", "core-loop@example.invalid"], cwd=repo).returncode == 0
    assert _run(["git", "config", "user.name", "Core Loop Test"], cwd=repo).returncode == 0
    (repo / "README.md").write_text("core loop proof\n", encoding="utf-8")
    assert _run(["git", "add", "README.md"], cwd=repo).returncode == 0
    assert _run(["git", "commit", "-m", "init"], cwd=repo).returncode == 0
    return repo


def _write_packet(tmp_path: Path, repo: Path) -> Path:
    packet = {
        "id": "core-operating-circuit-proof",
        "base_ref": "HEAD",
        "branch": "chore/core-operating-circuit-proof",
        "worktree": str(tmp_path / "worktree"),
        "intent": "Prove one bounded AgentOps leg for the core operating circuit.",
        "allowed_files": ["reports/agentops/**"],
        "forbidden_files": ["dharma_swarm/telos_gates.py", "dharma_swarm/dharma_kernel.py"],
        "gates": [{"name": "smoke", "command": f"{sys.executable} -c \"print('core loop ok')\""}],
        "commit": {"allowed": False, "message": "test(core): should not commit"},
        "approval": {"before_commit": True, "before_merge": True},
    }
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(packet), encoding="utf-8")
    return path


def _write_telic_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE objects (
                id TEXT PRIMARY KEY,
                type_name TEXT NOT NULL,
                properties TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        rows = [
            (
                "out_core_1",
                "Outcome",
                {"proposal_id": "proposal_core_1", "task_id": "task_core_1", "success": True},
                "2026-05-09T00:00:00Z",
            ),
            (
                "ve_core_1",
                "ValueEvent",
                {"outcome_id": "out_core_1", "composite_value": 0.91},
                "2026-05-09T00:01:00Z",
            ),
            (
                "contrib_core_1",
                "Contribution",
                {"value_event_id": "ve_core_1", "attributed_value": 0.91},
                "2026-05-09T00:02:00Z",
            ),
        ]
        conn.executemany(
            "INSERT INTO objects (id, type_name, properties, created_at) VALUES (?, ?, ?, ?)",
            [(obj_id, type_name, json.dumps(props), created_at) for obj_id, type_name, props, created_at in rows],
        )
        conn.commit()
    finally:
        conn.close()


def test_core_operating_circuit_binds_from_real_agentops_and_kaizen_artifacts(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    packet_path = _write_packet(tmp_path, repo)

    exit_code, report = agentops.execute_packet(packet_path, source_root=repo)

    assert exit_code == 0
    assert report is not None
    assert report["status"] == "passed"
    target_root = tmp_path / "worktree"
    report_paths = sorted((target_root / "reports" / "agentops").glob("**/report.json"))
    assert len(report_paths) == 1

    review = kaizen.build_kaizen_review(report_paths, review_id="core-loop-kaizen")
    kaizen_json, _ = kaizen.write_outputs(review, target_root / "reports" / "kaizen" / "core-loop-kaizen")
    assert kaizen_json.exists()
    assert review["next_work_packet_recommendation"]

    yds = tmp_path / "human_yds.jsonl"
    append_human_yds_rating(
        yds,
        artifact_uri=f"agentops://{report['job_id']}",
        rating="5.12a",
        human_note="bounded proof artifact is useful enough to bind the circuit test",
    )
    burn = tmp_path / "burn.jsonl"
    burn.write_text(json.dumps({"total_tokens": 12, "estimated_cost_usd": 0.01}) + "\n", encoding="utf-8")
    revenue = tmp_path / "revenue.md"
    revenue.write_text("- revenue wedge: core proof makes packaging safer\n", encoding="utf-8")
    telic_db = tmp_path / "ontology.db"
    _write_telic_db(telic_db)

    inputs = OperatingFactInputs(
        agentops_reports_dir=target_root / "reports" / "agentops",
        kaizen_reports_dir=target_root / "reports" / "kaizen",
        yds_ratings_path=yds,
        burn_report_path=burn,
        revenue_notes_path=revenue,
        telic_ontology_db_path=telic_db,
    )
    bundle = build_operating_fact_bundle(inputs)
    states = {fact.name: fact for fact in organ_state_facts(bundle)}

    assert bundle.missing_sources == ()
    assert states["agentops"].coherence_state == "bound"
    assert states["kaizen_review"].coherence_state == "bound"
    assert states["telic_value"].coherence_state == "bound"
    assert states["daily_operating_brief"].coherence_state == "bound"

    payload = system_map.build_system_map(
        repo_root=target_root,
        audit_dir=tmp_path / "audit",
        yds_ratings_path=yds,
        burn_report_path=burn,
        revenue_notes_path=revenue,
        telic_ontology_db_path=telic_db,
    )
    organs = {organ["name"]: organ for organ in payload["organs"]}

    assert organs["central_loop"]["coherence_state"] == "bound"
    assert "AgentOps -> KaizenReview -> Telic value -> Daily Brief" in organs["central_loop"]["observed_state"]
