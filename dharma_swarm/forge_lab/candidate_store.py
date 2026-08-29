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

from dataclasses import asdict
import json
import os
from pathlib import Path
import stat
from typing import Any

from dharma_swarm.archive import ArchiveEntry, EvolutionArchive, FitnessScore
from dharma_swarm.forge_lab.candidate_envelope import TerminalDisposition
from dharma_swarm.forge_lab.freeform_explore import FreeformExploreEnvelope
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256

FORGE_LAB_ROW_SCHEMA = "forge_lab.candidate_row.v0"
CANDIDATE_EXPORT_SCHEMA = "forge_lab.candidate_export.v1"
TERMINAL_ROW_SCHEMA = "forge_lab.candidate_terminal.v1"
DLQ_OUTBOX_ROW_SCHEMA = "forge_lab.candidate_dlq_outbox.v1"
DLQ_DELIVERY_ROW_SCHEMA = "forge_lab.candidate_dlq_delivery.v1"
LIVE_LEASE_CONSUMPTION_SCHEMA = "forge_lab.live_lease_consumption.v1"

GRADED = "graded"
BLOCKED = "blocked"
ERRORED = "errored"
DUPLICATE = "duplicate"
TERMINAL = "terminal"
DLQ_PENDING = "dlq_pending"
DLQ_DELIVERED = "dlq_delivered"
LIVE_LEASE_CONSUMED = "live_lease_consumed"


class CandidateStoreError(RuntimeError):
    """Raised when an export or terminal transition is not safely recordable."""


class CandidateStore:
    def __init__(self, archive_path: Path | str, *, experiment_id: str, category: str = "agent_evolution") -> None:
        self.archive_path = Path(archive_path)
        self.experiment_id = experiment_id
        self.category = category
        # Non-governed path + explicit opt-out => One Wire never consulted;
        # recorded by experiment.py in run_manifest.archive_fitness_authority.
        self.archive = EvolutionArchive(path=self.archive_path, enforce_one_wire=False)

    async def load(self) -> None:
        await self.archive.load()

    async def has(self, candidate_id: str) -> bool:
        return await self.archive.get_entry(candidate_id) is not None

    async def graded_entries(self) -> list[ArchiveEntry]:
        return [e for e in self.archive._entries.values() if self._row(e).get("state") == GRADED]

    async def export_candidate(self, candidate_id: str) -> dict[str, Any]:
        """Return a deterministic, digest-bound export of one graded row.

        Runtime archive timestamps and Merkle roots are deliberately excluded;
        the export binds only lineage, genome, executed evaluation, accounting,
        and the original RSI envelope. Repeated export of the same row is byte
        stable under canonical JSON serialization.
        """

        entry = await self.archive.get_entry(candidate_id)
        if entry is None:
            raise CandidateStoreError(f"candidate does not exist: {candidate_id}")
        row = self._row(entry)
        if row.get("state") != GRADED:
            raise CandidateStoreError(f"candidate is not graded: {candidate_id}")
        record = {
            "schema": CANDIDATE_EXPORT_SCHEMA,
            "candidate_id": entry.id,
            "parent_id": entry.parent_id,
            "experiment_id": entry.experiment_id,
            "component": entry.component,
            "genome": row.get("genome"),
            "generation": row.get("generation"),
            "loop_iteration": row.get("loop_iteration"),
            "role": row.get("role"),
            "pass_rate": row.get("pass_rate"),
            "per_task": row.get("per_task"),
            "budget": row.get("budget"),
            "tier": row.get("tier"),
            "executed_genome_fields": row.get("executed_genome_fields"),
            "ignored_genome_fields": row.get("ignored_genome_fields"),
            "source_envelope": row.get("envelope"),
        }
        # Round-trip prevents aliases to the archive's in-memory nested dicts.
        detached = json.loads(json.dumps(record, sort_keys=True, separators=(",", ":")))
        return {
            **detached,
            "record_sha256": canonical_sha256(detached),
        }

    async def append_terminal_disposition(
        self,
        *,
        candidate_id: str,
        envelope_id: str,
        disposition: TerminalDisposition,
        attempt: int,
        fence: int,
        transport_receipt_id: str = "",
        evaluation_receipt_sha256: str = "",
        promotion_decision_sha256: str = "",
        allow_external_candidate: bool = False,
    ) -> ArchiveEntry:
        """Persist exactly one final disposition for an envelope, idempotently."""

        if not disposition.state.final:
            raise CandidateStoreError("submitted is not a terminal disposition")
        if len(envelope_id) != 64 or any(ch not in "0123456789abcdef" for ch in envelope_id):
            raise CandidateStoreError("envelope_id must be a lowercase SHA-256 digest")
        if attempt < 1 or fence < 1:
            raise CandidateStoreError("terminal attempt and fence must be positive")
        candidate = await self.archive.get_entry(candidate_id)
        if candidate is None and not allow_external_candidate:
            raise CandidateStoreError(f"candidate does not exist: {candidate_id}")
        payload = {
            "schema": TERMINAL_ROW_SCHEMA,
            "state": TERMINAL,
            "candidate_id": candidate_id,
            "envelope_id": envelope_id,
            "attempt": int(attempt),
            "fence": int(fence),
            "disposition": disposition.to_dict(),
            "transport_receipt_id": str(transport_receipt_id),
            "evaluation_receipt_sha256": str(evaluation_receipt_sha256),
            "promotion_decision_sha256": str(promotion_decision_sha256),
        }
        existing_rows = await self.terminal_dispositions(
            candidate_id=candidate_id,
            envelope_id=envelope_id,
        )
        if existing_rows:
            if existing_rows[-1]["terminal"] == payload:
                existing = await self.archive.get_entry(existing_rows[-1]["entry_id"])
                if existing is not None:
                    return existing
            raise CandidateStoreError(
                f"envelope already has a different terminal disposition: {envelope_id}"
            )
        entry_id = "term_" + canonical_sha256(payload)[:24]
        existing = await self.archive.get_entry(entry_id)
        if existing is not None:
            return existing
        entry = ArchiveEntry(
            id=entry_id,
            timestamp=disposition.at.replace("Z", "+00:00"),
            parent_id=candidate_id if candidate is not None else None,
            component="forge_lab::candidate_terminal",
            change_type=f"candidate_{disposition.state.value}",
            description=disposition.reason_code,
            status="proposed",
            experiment_id=self.experiment_id,
            test_results={"forge_lab": payload},
        )
        await self.archive.add_entry(entry)
        return entry

    async def terminal_dispositions(
        self,
        *,
        candidate_id: str,
        envelope_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for entry in self.archive._entries.values():
            row = self._row(entry)
            if row.get("state") != TERMINAL or row.get("candidate_id") != candidate_id:
                continue
            if envelope_id is not None and row.get("envelope_id") != envelope_id:
                continue
            rows.append({"entry_id": entry.id, "terminal": json.loads(json.dumps(row))})
        rows.sort(
            key=lambda item: (
                int(item["terminal"].get("fence") or 0),
                int(item["terminal"].get("attempt") or 0),
                str(item["terminal"].get("disposition", {}).get("at") or ""),
                item["entry_id"],
            )
        )
        return rows

    async def latest_terminal(
        self,
        *,
        candidate_id: str,
        envelope_id: str,
    ) -> dict[str, Any] | None:
        rows = await self.terminal_dispositions(
            candidate_id=candidate_id,
            envelope_id=envelope_id,
        )
        return rows[-1] if rows else None

    async def append_dlq_outbox(
        self,
        *,
        candidate_id: str,
        envelope_id: str,
        message_id: str,
        subject: str,
        wire: dict[str, Any],
        headers: dict[str, str],
        attempt: int,
        fence: int,
        created_at: str,
        disposition: TerminalDisposition | None,
    ) -> dict[str, Any]:
        """Durably stage an exact DLQ write before contacting JetStream."""

        if len(envelope_id) != 64 or any(ch not in "0123456789abcdef" for ch in envelope_id):
            raise CandidateStoreError("DLQ envelope_id must be a lowercase SHA-256 digest")
        if attempt < 1 or fence < 1:
            raise CandidateStoreError("DLQ attempt and fence must be positive")
        detached_wire = json.loads(json.dumps(wire, sort_keys=True, separators=(",", ":")))
        detached_headers = json.loads(json.dumps(headers, sort_keys=True, separators=(",", ":")))
        body = detached_wire.get("payload")
        if not isinstance(body, dict):
            raise CandidateStoreError("DLQ wire payload is invalid")
        original_sha256 = str(body.get("original_sha256") or "")
        reason_code = str(body.get("reason_code") or "")
        if (
            len(original_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in original_sha256)
            or not reason_code
        ):
            raise CandidateStoreError("DLQ source identity is invalid")
        identity = {
            "candidate_id": str(candidate_id),
            "envelope_id": envelope_id,
            "message_id": str(message_id),
            "subject": str(subject),
            "original_sha256": original_sha256,
            "reason_code": reason_code,
        }
        outbox_id = "dlqo_" + canonical_sha256(identity)[:24]
        payload = {
            "schema": DLQ_OUTBOX_ROW_SCHEMA,
            "state": DLQ_PENDING,
            "outbox_id": outbox_id,
            **identity,
            "wire_sha256": canonical_sha256(detached_wire),
            "wire": detached_wire,
            "headers": detached_headers,
            "attempt": int(attempt),
            "fence": int(fence),
            "created_at": str(created_at),
            "disposition": disposition.to_dict() if disposition else None,
        }
        existing = await self.archive.get_entry(outbox_id)
        if existing is not None:
            row = self._row(existing)
            if any(row.get(name) != value for name, value in identity.items()):
                raise CandidateStoreError(f"DLQ outbox identity conflict: {outbox_id}")
            # Delivery count, observed time, and the diagnostic exception can
            # change on source redelivery. The first durable row is canonical.
            return json.loads(json.dumps(row))
        candidate = await self.archive.get_entry(candidate_id)
        entry = ArchiveEntry(
            id=outbox_id,
            timestamp=created_at.replace("Z", "+00:00"),
            parent_id=candidate_id if candidate is not None else None,
            component="forge_lab::candidate_dlq_outbox",
            change_type="candidate_dlq_pending",
            description=str(detached_wire.get("payload", {}).get("reason_code") or "candidate DLQ pending"),
            status="proposed",
            experiment_id=self.experiment_id,
            test_results={"forge_lab": payload},
        )
        await self.archive.add_entry(entry)
        return json.loads(json.dumps(payload))

    async def mark_dlq_delivered(
        self,
        *,
        outbox_id: str,
        stream: str,
        seq: int,
        delivered_at: str,
    ) -> dict[str, Any]:
        """Append an idempotent delivery receipt for one durable outbox row."""

        pending = await self.archive.get_entry(outbox_id)
        if pending is None or self._row(pending).get("state") != DLQ_PENDING:
            raise CandidateStoreError(f"DLQ outbox does not exist: {outbox_id}")
        prior = await self.dlq_delivery(outbox_id=outbox_id)
        if prior is not None:
            return prior
        payload = {
            "schema": DLQ_DELIVERY_ROW_SCHEMA,
            "state": DLQ_DELIVERED,
            "outbox_id": outbox_id,
            "stream": str(stream),
            "seq": int(seq),
            "delivered_at": str(delivered_at),
        }
        entry_id = "dlqd_" + canonical_sha256({"outbox_id": outbox_id})[:24]
        existing = await self.archive.get_entry(entry_id)
        if existing is None:
            await self.archive.add_entry(
                ArchiveEntry(
                    id=entry_id,
                    timestamp=delivered_at.replace("Z", "+00:00"),
                    parent_id=outbox_id,
                    component="forge_lab::candidate_dlq_delivery",
                    change_type="candidate_dlq_delivered",
                    description=f"{stream}:{seq}",
                    status="proposed",
                    experiment_id=self.experiment_id,
                    test_results={"forge_lab": payload},
                )
            )
        return json.loads(json.dumps(payload))

    async def dlq_delivery(self, *, outbox_id: str) -> dict[str, Any] | None:
        """Return the first durable delivery receipt for an outbox identity."""

        entry_id = "dlqd_" + canonical_sha256({"outbox_id": outbox_id})[:24]
        entry = await self.archive.get_entry(entry_id)
        if entry is None:
            return None
        row = self._row(entry)
        if row.get("state") != DLQ_DELIVERED or row.get("outbox_id") != outbox_id:
            raise CandidateStoreError(f"DLQ delivery identity conflict: {outbox_id}")
        return json.loads(json.dumps(row))

    async def consume_live_lease_once(
        self,
        *,
        authority_id: str,
        lease_id: str,
        candidate_id: str,
        envelope_id: str,
        fence: int,
        required_scope: str,
        expires_at: str,
        verifier_receipt_sha256: str,
        consumed_at: str,
    ) -> bool:
        """Durably consume a live grant once before issuing live authorization."""

        identity = {
            "authority_id": str(authority_id),
            "lease_id": str(lease_id),
            "required_scope": str(required_scope),
        }
        entry_id = "leasec_" + canonical_sha256(identity)[:24]
        payload = {
            "schema": LIVE_LEASE_CONSUMPTION_SCHEMA,
            "state": LIVE_LEASE_CONSUMED,
            **identity,
            "candidate_id": str(candidate_id),
            "envelope_id": str(envelope_id),
            "fence": int(fence),
            "expires_at": str(expires_at),
            "verifier_receipt_sha256": str(verifier_receipt_sha256),
            "consumed_at": str(consumed_at),
        }
        if (
            len(envelope_id) != 64
            or any(ch not in "0123456789abcdef" for ch in envelope_id)
            or len(verifier_receipt_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in verifier_receipt_sha256)
            or fence < 1
        ):
            raise CandidateStoreError("live lease consumption binding is invalid")
        existing = await self.archive.get_entry(entry_id)
        if existing is not None:
            row = self._row(existing)
            if row.get("schema") != LIVE_LEASE_CONSUMPTION_SCHEMA:
                raise CandidateStoreError("live lease consumption identity conflict")
            return False
        token_directory = self.archive_path.with_name(self.archive_path.name + ".live-leases")
        try:
            token_directory.mkdir(mode=0o700, parents=False, exist_ok=True)
            directory_meta = token_directory.lstat()
        except OSError as exc:
            raise CandidateStoreError("live lease token directory is unavailable") from exc
        if (
            stat.S_ISLNK(directory_meta.st_mode)
            or not stat.S_ISDIR(directory_meta.st_mode)
            or directory_meta.st_uid not in {0, os.geteuid()}
            or directory_meta.st_mode & 0o077
        ):
            raise CandidateStoreError("live lease token directory is unsafe")
        token_path = token_directory / f"{entry_id}.json"
        encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
        descriptor: int | None = None
        try:
            descriptor = os.open(
                token_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
        except FileExistsError:
            try:
                token_meta = token_path.lstat()
                if (
                    stat.S_ISLNK(token_meta.st_mode)
                    or not stat.S_ISREG(token_meta.st_mode)
                    or token_meta.st_uid not in {0, os.geteuid()}
                    or token_meta.st_nlink != 1
                    or token_meta.st_mode & 0o077
                ):
                    raise CandidateStoreError("live lease token is unsafe")
                prior = json.loads(token_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise CandidateStoreError("live lease token is corrupted") from exc
            stable_fields = set(payload) - {"consumed_at"}
            if any(prior.get(name) != payload.get(name) for name in stable_fields):
                raise CandidateStoreError("live lease token binding conflict")
            return False
        except OSError as exc:
            raise CandidateStoreError("live lease atomic consumption failed") from exc
        try:
            offset = 0
            while offset < len(encoded):
                offset += os.write(descriptor, encoded[offset:])
            os.fsync(descriptor)
        except OSError as exc:
            raise CandidateStoreError("live lease token persistence failed") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
        directory_fd = os.open(token_directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        await self.archive.add_entry(
            ArchiveEntry(
                id=entry_id,
                timestamp=consumed_at.replace("Z", "+00:00"),
                parent_id=None,
                component="forge_lab::live_lease_consumption",
                change_type="operator_live_lease_consumed",
                description=f"{authority_id}:{lease_id}",
                status="proposed",
                experiment_id=self.experiment_id,
                test_results={"forge_lab": payload},
            )
        )
        return True

    async def pending_dlq_outbox(self) -> list[dict[str, Any]]:
        delivered = {
            str(self._row(entry).get("outbox_id"))
            for entry in self.archive._entries.values()
            if self._row(entry).get("state") == DLQ_DELIVERED
        }
        pending = [
            json.loads(json.dumps(self._row(entry)))
            for entry in self.archive._entries.values()
            if self._row(entry).get("state") == DLQ_PENDING and entry.id not in delivered
        ]
        pending.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("outbox_id") or "")))
        return pending

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
                    "genome": genome,
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
                    "executed_genome_fields": list(executed_fields),
                    "ignored_genome_fields": list(ignored_fields),
                    "envelope": asdict(envelope),
                }
            },
        )
        await self.archive.add_entry(entry)
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
        await self.archive.add_entry(entry)
        return entry

    async def append_blocked(self, **kw: Any) -> ArchiveEntry:
        return await self._append_non_graded(BLOCKED, **kw)

    async def append_errored(self, **kw: Any) -> ArchiveEntry:
        return await self._append_non_graded(ERRORED, **kw)

    async def append_duplicate(self, **kw: Any) -> ArchiveEntry:
        return await self._append_non_graded(DUPLICATE, **kw)


__all__ = [
    "CandidateStore",
    "CandidateStoreError",
    "GRADED",
    "BLOCKED",
    "ERRORED",
    "DUPLICATE",
    "TERMINAL",
    "DLQ_PENDING",
    "DLQ_DELIVERED",
    "LIVE_LEASE_CONSUMED",
    "FORGE_LAB_ROW_SCHEMA",
    "CANDIDATE_EXPORT_SCHEMA",
    "TERMINAL_ROW_SCHEMA",
    "DLQ_OUTBOX_ROW_SCHEMA",
    "DLQ_DELIVERY_ROW_SCHEMA",
    "LIVE_LEASE_CONSUMPTION_SCHEMA",
]
