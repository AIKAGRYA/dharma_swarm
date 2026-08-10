"""Append-only candidate store — a thin wrap over EvolutionArchive.

Reuse Ledger: wraps ``archive.EvolutionArchive`` + its MerkleLog; never a new
JSONL lineage store, never a new hash chain. ``enforce_one_wire=False`` is an
explicit, RECORDED choice (the lab is its own fitness authority in shadow;
the governed ~/.dharma/evolution/archive.jsonl is never touched).

Row semantics:
- entry.id = content-addressed candidate_id (ids.candidate_id) — dedup is an
  identity property, not a policy.
- state ∈ {graded, blocked, errored, duplicate} lives in
  test_results["forge_lab"]["state"]. Only graded rows carry fitness-bearing
  status ("shadow"), so selection naturally sees only graded candidates while
  blocked/errored children persist as evidence (mycelial compost).
- The archive is never pruned. Ever.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any, TypeVar

from dharma_swarm.archive import (
    FITNESS_BEARING_STATUSES,
    ArchiveEntry,
    EvolutionArchive,
    FitnessScore,
)
from dharma_swarm.forge_lab.freeform_explore import FreeformExploreEnvelope
from dharma_swarm.forge_lab.ids import (
    candidate_id as candidate_id_for_genome,
    genome_digest,
    phenotype_digest,
    phenotype_id,
)
from dharma_swarm.merkle_log import MerkleLog

FORGE_LAB_ROW_SCHEMA = "forge_lab.candidate_row.v0"

GRADED = "graded"
BLOCKED = "blocked"
ERRORED = "errored"
DUPLICATE = "duplicate"

_T = TypeVar("_T")


class CandidateStore:
    def __init__(self, archive_path: Path | str, *, experiment_id: str, category: str = "agent_evolution") -> None:
        self.archive_path = Path(archive_path)
        self.experiment_id = experiment_id
        self.category = category
        # Non-governed path + explicit opt-out => One Wire never consulted;
        # recorded by experiment.py in run_manifest.archive_fitness_authority.
        self.archive = EvolutionArchive(path=self.archive_path, enforce_one_wire=False)

    async def _archive_io(self, operation: Callable[[], _T]) -> _T:
        """Run bounded append-only archive I/O without an implicit executor.

        ``EvolutionArchive`` uses the event loop's implicit executor for its
        append path.  On the deployed runtime that executor can strand the
        caller after the write has completed.  Forge rows are small and fsynced
        one at a time, so this adapter deliberately performs that bounded local
        operation inline and never leaves a background worker behind.
        """

        return operation()

    def _load_sync(self) -> None:
        self.archive._entries.clear()
        self.archive.grid.rebuild([])
        if not self.archive_path.exists():
            return
        with self.archive_path.open("r", encoding="utf-8") as stream:
            for line in stream:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    data = json.loads(stripped)
                    if isinstance(data.get("fitness"), dict):
                        data["fitness"] = FitnessScore(**data["fitness"])
                    entry = ArchiveEntry(**data)
                except (json.JSONDecodeError, ValueError, KeyError):
                    continue
                self.archive._entries[entry.id] = entry
                if entry.status in FITNESS_BEARING_STATUSES:
                    self.archive.grid.try_insert(entry)

    def _append_entry_sync(self, entry: ArchiveEntry) -> None:
        """Mirror EvolutionArchive.add_entry without its implicit executor."""

        self.archive._assert_fitness_authority(entry, operation="add_entry")
        if entry.parent_id:
            parent = self.archive._entries.get(entry.parent_id)
            if parent and parent.merkle_root:
                entry.parent_merkle_root = parent.merkle_root
        # MAP-Elites normally materializes this field after the legacy leaf is
        # appended. Materialize it first so the full Forge digest matches the
        # exact durable archive row.
        if entry.status in FITNESS_BEARING_STATUSES and not entry.feature_coords:
            entry.feature_coords = self.archive.grid.compute_feature_coords(entry)

        evidence_digest = self._entry_evidence_digest(entry)
        merkle_data = {
            "id": entry.id,
            "timestamp": entry.timestamp,
            "parent_id": entry.parent_id,
            "component": entry.component,
            "change_type": entry.change_type,
            "description": entry.description,
            "diff_hash": hashlib.sha256(entry.diff.encode()).hexdigest() if entry.diff else None,
            "fitness_weighted": entry.fitness.weighted(),
            "status": entry.status,
            "execution_profile": entry.execution_profile,
            "promotion_state": entry.promotion_state,
            # The legacy leaf fields stay intact; new Forge rows additionally
            # attest genome, task results, and component budget evidence.
            "forge_entry_digest": evidence_digest,
        }
        entry.merkle_root = self.archive.merkle_log.append(merkle_data)
        self.archive._entries[entry.id] = entry
        if entry.status in FITNESS_BEARING_STATUSES:
            self.archive.grid.try_insert(entry)

        self.archive_path.parent.mkdir(parents=True, exist_ok=True)
        with self.archive_path.open("a", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                stream.write(entry.model_dump_json() + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _evidence_digest(evidence: dict[str, Any]) -> str:
        evidence = dict(evidence)
        # The root is the result of hashing this evidence and must not recurse
        # into itself. Parent roots remain covered as lineage evidence.
        evidence.pop("merkle_root", None)
        return "sha256:" + hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @classmethod
    def _entry_evidence_digest(cls, entry: ArchiveEntry) -> str:
        return cls._evidence_digest(entry.model_dump(mode="json"))

    @staticmethod
    def _strict_json_object(raw: str, *, index: int) -> dict[str, Any]:
        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError(f"duplicate JSON key: {key}")
                value[key] = item
            return value

        try:
            value = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"malformed_archive_row:{index}:{exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"malformed_archive_row:{index}:row_must_be_an_object")
        return value

    def _read_durable_rows(self) -> list[tuple[dict[str, Any], ArchiveEntry]]:
        """Read the archive from its inode, never from the in-memory index.

        The shared lock makes this one coherent snapshot relative to Forge's
        exclusive append lock.  Exact top-level shape and duplicate JSON keys
        are enforced so Pydantic cannot silently discard hostile evidence.
        """

        if not self.archive_path.exists():
            return []
        flags = os.O_RDONLY | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(self.archive_path, flags)
        except OSError as exc:
            raise ValueError(f"archive_unreadable:{exc}") from exc
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError("archive_not_single_link_regular_file")
            fcntl.flock(descriptor, fcntl.LOCK_SH)
            try:
                with os.fdopen(os.dup(descriptor), "rb") as stream:
                    payload = stream.read()
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        except OSError as exc:
            raise ValueError(f"archive_read_failed:{exc}") from exc
        finally:
            os.close(descriptor)

        if not payload:
            return []
        if not payload.endswith(b"\n"):
            raise ValueError("archive_missing_terminal_newline")
        try:
            lines = payload.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise ValueError(f"archive_not_utf8:{exc}") from exc

        expected_keys = set(ArchiveEntry.model_fields)
        seen_ids: set[str] = set()
        rows: list[tuple[dict[str, Any], ArchiveEntry]] = []
        for index, line in enumerate(lines):
            if not line.strip():
                raise ValueError(f"malformed_archive_row:{index}:blank_row")
            raw = self._strict_json_object(line, index=index)
            if set(raw) != expected_keys:
                missing = sorted(expected_keys - set(raw))
                extra = sorted(set(raw) - expected_keys)
                raise ValueError(
                    f"archive_row_shape_mismatch:{index}:missing={missing}:extra={extra}"
                )
            try:
                entry = ArchiveEntry.model_validate(raw)
            except ValueError as exc:
                raise ValueError(f"malformed_archive_row:{index}:{exc}") from exc
            if entry.id in seen_ids:
                raise ValueError(f"duplicate_archive_candidate_id:{index}:{entry.id}")
            seen_ids.add(entry.id)
            rows.append((raw, entry))
        return rows

    @staticmethod
    def _verify_graded_identity(entry: ArchiveEntry, *, index: int) -> str | None:
        row = CandidateStore._row(entry)
        if row.get("schema") != FORGE_LAB_ROW_SCHEMA:
            return f"graded_row_schema_mismatch:{index}:{entry.id}"
        genome = row.get("genome")
        if not isinstance(genome, dict):
            return f"graded_genome_invalid:{index}:{entry.id}"
        expected_candidate_id = candidate_id_for_genome(genome)
        if entry.id != expected_candidate_id or row.get("candidate_id") != expected_candidate_id:
            return f"candidate_id_mismatch:{index}:{entry.id}"
        expected_genome_digest = genome_digest(genome)
        if row.get("genome_sha256") != expected_genome_digest:
            return f"genome_digest_mismatch:{index}:{entry.id}"
        executed = row.get("executed_genome_fields")
        if (
            not isinstance(executed, list)
            or not executed
            or any(not isinstance(field, str) or not field for field in executed)
            or len(set(executed)) != len(executed)
        ):
            return f"executed_fields_invalid:{index}:{entry.id}"
        try:
            expected_phenotype_id = phenotype_id(genome, executed_fields=executed)
            expected_phenotype_digest = phenotype_digest(genome, executed_fields=executed)
        except (TypeError, ValueError) as exc:
            return f"phenotype_evidence_invalid:{index}:{entry.id}:{exc}"
        if row.get("phenotype_id") != expected_phenotype_id:
            return f"phenotype_id_mismatch:{index}:{entry.id}"
        if row.get("phenotype_sha256") != expected_phenotype_digest:
            return f"phenotype_digest_mismatch:{index}:{entry.id}"
        return None

    def _verify_row_semantics(self, entry: ArchiveEntry, *, index: int) -> str | None:
        row = self._row(entry)
        state = row.get("state")
        if row.get("schema") != FORGE_LAB_ROW_SCHEMA:
            return f"forge_row_schema_mismatch:{index}:{entry.id}"
        if state not in {GRADED, BLOCKED, ERRORED, DUPLICATE}:
            return f"forge_row_state_invalid:{index}:{entry.id}"
        if row.get("category") != self.category or entry.experiment_id != self.experiment_id:
            return f"forge_row_scope_mismatch:{index}:{entry.id}"
        fitness_bearing = entry.status in FITNESS_BEARING_STATUSES
        if fitness_bearing != (state == GRADED):
            return f"forge_row_fitness_state_mismatch:{index}:{entry.id}"
        if state == GRADED:
            return self._verify_graded_identity(entry, index=index)
        return None

    def verify_evidence_merkle(self) -> tuple[bool, str]:
        """Verify the independently re-read archive and its full evidence chain."""

        try:
            rows = self._read_durable_rows()
        except ValueError as exc:
            return False, str(exc)
        # A new object forces a fresh read of the durable Merkle file.  Using
        # ``self.archive.merkle_log`` here would miss same-instance disk edits.
        try:
            durable_merkle = MerkleLog(self.archive_path.parent / "merkle_log.json")
        except (OSError, ValueError) as exc:
            return False, f"merkle_log_unreadable:{exc}"
        chain_ok, chain_info = durable_merkle.verify_chain()
        if not chain_ok:
            return False, f"chain_broken:{chain_info}"
        if len(rows) != durable_merkle.get_chain_length():
            return False, "archive_entry_count_differs_from_merkle_count"
        for index, (raw, entry) in enumerate(rows):
            try:
                leaf = durable_merkle.leaf_at(index)
            except (IndexError, KeyError, TypeError):
                return False, f"missing_merkle_leaf:{index}"
            claimed = leaf.get("forge_entry_digest") if isinstance(leaf, dict) else None
            if claimed != self._evidence_digest(raw):
                return False, f"forge_evidence_digest_mismatch:{index}:{entry.id}"
            if entry.merkle_root != durable_merkle.hashes[index].hex():
                return False, f"entry_merkle_root_mismatch:{index}:{entry.id}"
            semantic_failure = self._verify_row_semantics(entry, index=index)
            if semantic_failure:
                return False, semantic_failure
        return True, f"verified_full_forge_evidence:{len(rows)}"

    async def load(self) -> None:
        await self._archive_io(self._load_sync)

    async def has(self, candidate_id: str) -> bool:
        return await self.archive.get_entry(candidate_id) is not None

    async def graded_entries(self) -> list[ArchiveEntry]:
        return [e for e in self.archive._entries.values() if self._row(e).get("state") == GRADED]

    def n_children_map(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self.archive._entries.values():
            if entry.parent_id:
                counts[entry.parent_id] = counts.get(entry.parent_id, 0) + 1
        return counts

    @staticmethod
    def _row(entry: ArchiveEntry) -> dict[str, Any]:
        row = entry.test_results.get("forge_lab")
        return row if isinstance(row, dict) else {}

    async def append_graded(
        self,
        *,
        candidate_id: str,
        genome: dict[str, Any],
        parent_id: str | None,
        generation: int,
        loop_iteration: int,
        role: str,
        pass_rate: float,
        per_task: list[dict[str, Any]],
        budget: dict[str, Any],
        tier: str,
        executed_fields: tuple[str, ...],
        ignored_fields: tuple[str, ...],
        envelope: FreeformExploreEnvelope,
        mutation_notes: str = "",
        model: str = "",
        tokens_used: int = 0,
    ) -> ArchiveEntry:
        expected_candidate_id = candidate_id_for_genome(genome)
        if candidate_id != expected_candidate_id:
            raise ValueError(
                f"candidate_id does not match full genome digest: "
                f"expected {expected_candidate_id}, got {candidate_id}"
            )
        executed = tuple(executed_fields)
        candidate_phenotype_id = phenotype_id(genome, executed_fields=executed)
        candidate_phenotype_digest = phenotype_digest(genome, executed_fields=executed)
        entry = ArchiveEntry(
            id=candidate_id,
            parent_id=parent_id,
            component=f"forge_lab::{genome.get('arm_kind', 'unknown')}",
            change_type="explore_seed" if role == "seed_baseline" else "explore_candidate",
            description=mutation_notes or genome.get("notes", ""),
            fitness=FitnessScore(correctness=max(0.0, min(1.0, pass_rate))),
            status="shadow",
            experiment_id=self.experiment_id,
            model=model,
            tokens_used=tokens_used,
            test_results={
                "forge_lab": {
                    "schema": FORGE_LAB_ROW_SCHEMA,
                    "state": GRADED,
                    "category": self.category,
                    "candidate_id": candidate_id,
                    "genome": genome,
                    "genome_sha256": genome_digest(genome),
                    "phenotype_id": candidate_phenotype_id,
                    "phenotype_sha256": candidate_phenotype_digest,
                    "generation": generation,
                    "loop_iteration": loop_iteration,
                    "role": role,
                    "pass_rate": pass_rate,
                    "per_task": per_task,
                    "behavior": {
                        "solved_task_ids": sorted(
                            str(r.get("task_id")) for r in per_task if r.get("resolved")
                        )
                    },
                    "budget": budget,
                    "tier": tier,
                    "executed_genome_fields": list(executed),
                    "ignored_genome_fields": list(ignored_fields),
                    "envelope": asdict(envelope),
                }
            },
        )
        await self._archive_io(lambda: self._append_entry_sync(entry))
        return entry

    async def _append_non_graded(
        self,
        state: str,
        *,
        candidate_id: str,
        genome: Any,
        parent_id: str | None,
        generation: int,
        loop_iteration: int,
        reasons: list[str],
        raw_output: str = "",
    ) -> ArchiveEntry:
        entry = ArchiveEntry(
            id=candidate_id,
            parent_id=parent_id,
            component="forge_lab::non_graded",
            change_type=f"explore_{state}",
            description="; ".join(reasons)[:500],
            status="proposed",  # never fitness-bearing => invisible to selection
            experiment_id=self.experiment_id,
            test_results={
                "forge_lab": {
                    "schema": FORGE_LAB_ROW_SCHEMA,
                    "state": state,
                    "category": self.category,
                    "genome": genome,
                    "generation": generation,
                    "loop_iteration": loop_iteration,
                    "reasons": reasons,
                    "raw_output": raw_output[:20000],
                }
            },
        )
        await self._archive_io(lambda: self._append_entry_sync(entry))
        return entry

    async def append_blocked(self, **kw: Any) -> ArchiveEntry:
        return await self._append_non_graded(BLOCKED, **kw)

    async def append_errored(self, **kw: Any) -> ArchiveEntry:
        return await self._append_non_graded(ERRORED, **kw)

    async def append_duplicate(self, **kw: Any) -> ArchiveEntry:
        return await self._append_non_graded(DUPLICATE, **kw)


__all__ = ["CandidateStore", "GRADED", "BLOCKED", "ERRORED", "DUPLICATE", "FORGE_LAB_ROW_SCHEMA"]
