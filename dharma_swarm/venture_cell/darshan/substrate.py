"""End-to-end substrate materialization for Darshan bundles."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.venture_cell.darshan.chetana_adapter import (
    DarshanChetanaResult,
    ingest_bundle,
)
from dharma_swarm.venture_cell.darshan.decision_adapter import record_decision_delta
from dharma_swarm.venture_cell.darshan.ontology_adapter import materialize_knowledge_artifact
from dharma_swarm.venture_cell.darshan.task_adapter import create_followup_task


@dataclass(frozen=True)
class DarshanMaterializeResult:
    bundle_path: Path
    chetana: DarshanChetanaResult
    ontology_artifact_id: str
    task_id: str
    decision_id: str
    handoff_path: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "bundle_path": str(self.bundle_path),
            "chetana_staged_paths": [str(path) for path in self.chetana.staged_paths],
            "ontology_artifact_id": self.ontology_artifact_id,
            "task_id": self.task_id,
            "decision_id": self.decision_id,
            "handoff_path": str(self.handoff_path),
        }


def materialize_bundle(
    bundle_path: Path,
    *,
    ontology_path: Path | None = None,
    task_db_path: Path | None = None,
    decision_log_path: Path | None = None,
) -> DarshanMaterializeResult:
    bundle_path = bundle_path.expanduser().resolve()
    chetana = ingest_bundle(bundle_path)
    artifact = materialize_knowledge_artifact(
        bundle_path,
        ontology_path=ontology_path,
    )
    task = asyncio.run(create_followup_task(bundle_path, db_path=task_db_path))
    decision = record_decision_delta(bundle_path, log_path=decision_log_path)
    result = DarshanMaterializeResult(
        bundle_path=bundle_path,
        chetana=chetana,
        ontology_artifact_id=artifact.id,
        task_id=task.id,
        decision_id=decision.decision_id,
        handoff_path=bundle_path / "polsia_handoff.json",
    )
    _write_materialization_result(bundle_path, result)
    return result


def _write_materialization_result(
    bundle_path: Path,
    result: DarshanMaterializeResult,
) -> None:
    path = bundle_path / "substrate_materialization.json"
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
