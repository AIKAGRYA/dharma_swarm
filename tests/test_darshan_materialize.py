from __future__ import annotations

import json
import asyncio
from pathlib import Path

import pytest

from dharma_swarm.ontology_runtime import reset_shared_registry
from dharma_swarm.task_board import TaskBoard
from dharma_swarm.venture_cell.darshan.bundle import create_bundle
from dharma_swarm.venture_cell.darshan.substrate import materialize_bundle


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    reset_shared_registry()
    yield home
    reset_shared_registry()


def test_materialize_bundle_writes_chetana_ontology_task_and_decision(fake_home: Path, tmp_path: Path) -> None:
    bundle_path = create_bundle(title="After the Feed", root=tmp_path / "artifacts")
    ontology_path = tmp_path / "ontology.db"
    task_db_path = tmp_path / "tasks.db"
    decision_log_path = tmp_path / "decisions.jsonl"

    result = materialize_bundle(
        bundle_path,
        ontology_path=ontology_path,
        task_db_path=task_db_path,
        decision_log_path=decision_log_path,
    )

    assert result.ontology_artifact_id
    assert result.task_id
    assert result.decision_id
    assert len(result.chetana.staged_paths) == 1
    assert result.handoff_path == bundle_path / "polsia_handoff.json"
    assert (bundle_path / "substrate_materialization.json").exists()
    assert ontology_path.exists()
    assert task_db_path.exists()
    assert decision_log_path.exists()

    materialized = json.loads(
        (bundle_path / "substrate_materialization.json").read_text(encoding="utf-8")
    )
    assert materialized["ontology_artifact_id"] == result.ontology_artifact_id
    assert materialized["task_id"] == result.task_id
    assert materialized["decision_id"] == result.decision_id


def test_materialize_bundle_creates_task_with_darshan_metadata(
    fake_home: Path,
    tmp_path: Path,
) -> None:
    bundle_path = create_bundle(title="Task Metadata", root=tmp_path / "artifacts")
    task_db_path = tmp_path / "tasks.db"

    result = materialize_bundle(
        bundle_path,
        ontology_path=tmp_path / "ontology.db",
        task_db_path=task_db_path,
        decision_log_path=tmp_path / "decisions.jsonl",
    )

    board = TaskBoard(task_db_path)
    task = asyncio.run(board.get(result.task_id))
    assert task is not None
    assert task.title == "Darshan follow-up: Task Metadata"
    assert task.metadata["cell_id"] == "DARSHAN"
    assert task.metadata["bundle_path"] == str(bundle_path.resolve())
