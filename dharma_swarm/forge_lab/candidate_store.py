"""Append-only candidate store for Forge Lab EXPLORE runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from dharma_swarm.archive import ArchiveEntry, EvolutionArchive, FitnessScore
from dharma_swarm.forge_lab.freeform_explore import (
    FreeformExploreEnvelope,
    MEMBRANE_REQUIREMENTS,
)
from dharma_swarm.forge_lab.identity import candidate_id_for_genome

CandidateState = Literal["graded", "blocked", "errored", "duplicate"]
CandidateRole = Literal["seed_baseline", "candidate"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_membrane() -> dict[str, bool]:
    return {name: True for name in MEMBRANE_REQUIREMENTS}


@dataclass(frozen=True)
class CandidateRecord:
    candidate_id: str
    parent_id: str | None
    experiment_id: str
    category: str
    generation: int
    loop_iteration: int
    genome: dict[str, Any]
    state: CandidateState
    role: CandidateRole
    fitness: dict[str, Any] = field(default_factory=dict)
    behavior: dict[str, Any] = field(default_factory=dict)
    operator: str = ""
    raw_output: str = ""
    notes: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)
    benchmark_receipt: dict[str, Any] | None = None
    canonicalizer: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def weighted_fitness(self) -> float:
        return float(self.fitness.get("weighted", self.fitness.get("score", 0.0)) or 0.0)


class CandidateStore:
    """Single-writer facade over EvolutionArchive plus explicit lab records."""

    def __init__(self, archive_dir: Path | str) -> None:
        self.archive_dir = Path(archive_dir).expanduser()
        self.archive_path = self.archive_dir / "archive.jsonl"
        self.records_path = self.archive_dir / "candidate_records.jsonl"
        self.archive = EvolutionArchive(self.archive_path, enforce_one_wire=False)
        self._records: dict[str, CandidateRecord] = {}

    async def load(self) -> None:
        await self.archive.load()
        self._records.clear()
        if not self.records_path.exists():
            return
        for line in self.records_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            record = CandidateRecord(**data)
            self._records[record.candidate_id] = record

    def has_candidate(self, candidate_id: str) -> bool:
        return candidate_id in self._records

    def records(self) -> list[CandidateRecord]:
        return sorted(self._records.values(), key=lambda item: (item.generation, item.created_at, item.candidate_id))

    def graded_records(self) -> list[CandidateRecord]:
        return [record for record in self.records() if record.state == "graded"]

    async def append(
        self,
        *,
        genome: dict[str, Any],
        parent_id: str | None,
        experiment_id: str,
        category: str,
        generation: int,
        loop_iteration: int,
        state: CandidateState,
        role: CandidateRole = "candidate",
        fitness: dict[str, Any] | None = None,
        behavior: dict[str, Any] | None = None,
        operator: str = "",
        raw_output: str = "",
        notes: str = "",
        artifacts: dict[str, Any] | None = None,
        benchmark_receipt: dict[str, Any] | None = None,
    ) -> CandidateRecord:
        candidate_id, canonicalizer = candidate_id_for_genome(genome)
        # Only GRADED children dedupe to ``duplicate`` — that is the sole case
        # where the point is skipping an expensive regrade of a reached genome.
        # A ``blocked``/``errored`` child that happens to collide (e.g. a
        # malformed LLM proposal that fell back to the parent genome) must keep
        # its OWN honest identity and blocker, never be relabeled ``duplicate``.
        if candidate_id in self._records and state == "graded":
            return await self.append_duplicate(
                candidate_id=candidate_id,
                parent_id=parent_id,
                experiment_id=experiment_id,
                category=category,
                generation=generation,
                loop_iteration=loop_iteration,
                genome=genome,
                operator=operator,
            )
        if candidate_id in self._records and state != "duplicate":
            # Non-graded collision: derive a distinct id from the attempt so the
            # honest state/blocker survives instead of overwriting a prior row.
            candidate_id, canonicalizer = candidate_id_for_genome(
                {
                    "collided_genome_id": candidate_id,
                    "genome": genome,
                    "state": state,
                    "operator": operator,
                    "blocker": notes,
                    "generation": generation,
                    "loop_iteration": loop_iteration,
                }
            )

        record = CandidateRecord(
            candidate_id=candidate_id,
            parent_id=parent_id,
            experiment_id=experiment_id,
            category=category,
            generation=generation,
            loop_iteration=loop_iteration,
            genome=dict(genome),
            state=state,
            role=role,
            fitness=dict(fitness or {}),
            behavior=dict(behavior or {}),
            operator=operator,
            raw_output=raw_output,
            notes=notes,
            artifacts=dict(artifacts or {}),
            benchmark_receipt=benchmark_receipt,
            canonicalizer=canonicalizer,
        )
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self._append_record(record)
        self._records[record.candidate_id] = record
        await self._append_archive_entry(record)
        return record

    async def append_duplicate(
        self,
        *,
        candidate_id: str,
        parent_id: str | None,
        experiment_id: str,
        category: str,
        generation: int,
        loop_iteration: int,
        genome: dict[str, Any],
        operator: str,
    ) -> CandidateRecord:
        duplicate_genome = {
            "duplicate_of": candidate_id,
            "genome": genome,
            "duplicate_parent_id": parent_id,
            "loop_iteration": loop_iteration,
        }
        duplicate_id, canonicalizer = candidate_id_for_genome(duplicate_genome)
        record = CandidateRecord(
            candidate_id=duplicate_id,
            parent_id=parent_id,
            experiment_id=experiment_id,
            category=category,
            generation=generation,
            loop_iteration=loop_iteration,
            genome=duplicate_genome,
            state="duplicate",
            role="candidate",
            fitness={"score": 0.0, "weighted": 0.0},
            operator=operator,
            notes=f"reached existing genome {candidate_id}; skipped regrade",
            canonicalizer=canonicalizer,
        )
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self._append_record(record)
        self._records[record.candidate_id] = record
        return record

    def _append_record(self, record: CandidateRecord) -> None:
        with self.records_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), sort_keys=True, default=str) + "\n")

    async def _append_archive_entry(self, record: CandidateRecord) -> None:
        score = max(0.0, min(1.0, record.weighted_fitness))
        envelope = FreeformExploreEnvelope(
            candidate_id=record.candidate_id,
            parent_id=record.parent_id,
            experiment_id=record.experiment_id,
            category=record.category,
            raw_output=record.raw_output,
            notes=record.notes,
            artifacts=record.artifacts,
            benchmark_receipt=record.benchmark_receipt,
            membrane=safe_membrane(),
        )
        entry = ArchiveEntry(
            id=record.candidate_id,
            parent_id=record.parent_id,
            component=f"forge_lab.{record.category}",
            change_type=record.operator or "unknown",
            description=record.notes[:300] or f"Forge Lab {record.state} candidate",
            diff=json.dumps(record.genome, sort_keys=True, default=str),
            fitness=FitnessScore(
                correctness=score,
                dharmic_alignment=1.0 if envelope.is_membrane_safe() else 0.0,
                economic_value=0.0,
                elegance=float(record.fitness.get("structure", score) or 0.0),
                efficiency=float(record.fitness.get("efficiency", 0.5) or 0.5),
                safety=1.0 if record.state == "graded" else 0.0,
            ),
            test_results={
                "forge_lab_record": record.to_dict(),
                "freeform_envelope": {
                    "candidate_id": envelope.candidate_id,
                    "missing_membrane": envelope.missing_membrane_requirements(),
                },
            },
            experiment_id=record.experiment_id,
            evidence_tier=str((record.benchmark_receipt or {}).get("tier") or "explore"),
            promotion_state="candidate",
            status="evaluated" if record.state == "graded" else "proposed",
        )
        await self.archive.add_entry(entry)
