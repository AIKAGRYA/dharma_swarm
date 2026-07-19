# spine: memoizes EvidenceReceipt by idempotency key (owner: runtime_state) — no new store
"""Fenced, effectively-once ``invoke_agent`` wrapper for DharmaGraph Phase 0b.
Memoizable completions replay; other claims use strictly increasing ownership
tokens and CAS reclaim without touching A2A's independent path."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import UUID

from dharma_swarm.graph.effects import EffectsProvider, LiveEffects
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity
from dharma_swarm.spine.invoke import AgentInvoker
from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.spine.routing import RoutingDecision

logger = logging.getLogger(__name__)

__all__ = [
    "DuplicateDispatchInFlight",
    "DurableInvoker",
    "claim_idempotency_key",
    "derive_graph_side_effect_key",
    "persist_evidence_receipt",
    "receipt_from_dict",
    "wrap_invoker",
]

# Idempotency-record metadata keys owned by this module.
_META_RECEIPT = "receipt"
_META_RESULT_JSON = "result_json"
_META_RESULT_OMITTED = "result_omitted_reason"
_META_OPERATION_HASH = "operation_hash"

# Cap on memoized result payloads stored in idempotency_records.metadata_json.
_RESULT_JSON_CAP = 100_000

# Receipt attributes stamped when a dispatch runs fail-open (no idempotency
# fence). They make each unfenced consequential call COUNTABLE so the decision
# to fail closed can be driven by measured blind-spot frequency rather than
# guessed at (KEEL pre-1004 hardening: observe before fencing). Purely additive
# — behaviour is unchanged; only two attributes are added to the returned
# receipt.
_ATTR_UNPROTECTED = "unprotected_dispatch"
_ATTR_UNPROTECTED_REASON = "unprotected_reason"


def _mark_unprotected(receipt: EvidenceReceipt, reason: str) -> EvidenceReceipt:
    """Tag ``receipt`` as an unfenced (fail-open) dispatch, non-destructively."""
    return dataclasses.replace(
        receipt,
        attributes={
            **receipt.attributes,
            _ATTR_UNPROTECTED: True,
            _ATTR_UNPROTECTED_REASON: reason,
        },
    )


def claim_idempotency_key(side_effect_key: str) -> str:
    """The deterministic idempotency key every dispatcher of a side effect
    claims under, regardless of its own (possibly re-minted) identity key.

    Bounded-length and collision-resistant so the
    (idempotency_key, side_effect_key) primary key becomes one shared row
    per side effect — the atomic claim Codex review asked for."""
    digest = hashlib.sha256(side_effect_key.encode("utf-8")).hexdigest()
    return f"sek_{digest}"


def _encode_memo_result(result: Any) -> dict[str, Any]:
    """Memoize a run result preserving its TYPE, or omit it explicitly.

    JSON-serializable results (str/dict/list/int/...) round-trip exactly via
    ``result_json``. Results that are not JSON-serializable or exceed the
    cap are NOT stored at all — a truncated or stringified replay would
    silently corrupt the dispatch return contract — and the omission is
    recorded with an explicit reason so the memo hit can surface it.
    """
    try:
        encoded = json.dumps(result)
    except (TypeError, ValueError):
        return {_META_RESULT_OMITTED: "not_json_serializable"}
    if len(encoded) > _RESULT_JSON_CAP:
        return {_META_RESULT_OMITTED: "exceeds_result_cap"}
    return {_META_RESULT_JSON: encoded}


def _decode_memo_result(metadata: dict[str, Any]) -> Any:
    """Inverse of ``_encode_memo_result`` (None when absent or omitted)."""
    encoded = metadata.get(_META_RESULT_JSON)
    if isinstance(encoded, str):
        try:
            return json.loads(encoded)
        except (TypeError, ValueError):
            return None
    return None


class DuplicateDispatchInFlight(RuntimeError):
    """A concurrent dispatch already holds this side-effect key.

    Raised by the losing invoker so it fails visibly through the caller's
    normal failure/retry handling instead of double-calling the provider.
    """

    def __init__(self, side_effect_key: str) -> None:
        super().__init__(
            f"dispatch already in flight for side_effect_key={side_effect_key!r}; "
            "refusing to double-execute"
        )
        self.side_effect_key = side_effect_key


def derive_graph_side_effect_key(
    run_id: str, superstep: int, node_id: str, retry_count: int
) -> str:
    """Deterministic side-effect key for a graph-run dispatch (Phase 3 form).

    ``sha256(run_id:superstep:node_id:retry_count)`` — retries increment
    ``retry_count`` and therefore derive a NEW key (each retry is its own
    side effect); replays of the same attempt derive the SAME key.
    """
    digest = hashlib.sha256(
        f"{run_id}:{superstep}:{node_id}:{retry_count}".encode("utf-8")
    ).hexdigest()
    return f"invoke_agent:graph:{digest}"


def receipt_from_dict(payload: dict[str, Any]) -> EvidenceReceipt:
    """Rebuild an ``EvidenceReceipt`` from its ``to_dict()`` serialization.

    Unknown keys are ignored so older/newer receipt blobs stay readable.
    """
    fields = {f.name for f in dataclasses.fields(EvidenceReceipt)}
    data: dict[str, Any] = {k: v for k, v in payload.items() if k in fields}
    if isinstance(data.get("receipt_id"), str):
        data["receipt_id"] = UUID(data["receipt_id"])
    if isinstance(data.get("routing_decision_id"), str):
        data["routing_decision_id"] = UUID(data["routing_decision_id"])
    for key in ("started_at", "finished_at"):
        value = data.get(key)
        if isinstance(value, str):
            data[key] = datetime.fromisoformat(value)
    if not isinstance(data.get("attributes"), dict):
        data["attributes"] = {}
    return EvidenceReceipt(**data)


async def persist_evidence_receipt(
    receipt: EvidenceReceipt,
    store: Any,
    *,
    task_id: str,
    machine_receipt_path: Path | None = None,
) -> bool:
    """Persist a dispatch receipt projection and chain anchor, fail-open.

    Extracted verbatim from ``orchestrator._run_task_via_spine`` (module at
    its line-budget ceiling): writes to the SAME store the delegation-run
    writer used (the configurable ``db_path``, never a hardcoded default),
    with a SHORT explicit lock budget — the interpreter default busy_timeout
    (5000ms) would stall the dispatch coroutine up to ~5s when a sync fleet
    writer holds the WAL write lock; 2s bounds the tail latency. A
    persistence error must never break dispatch (the receipt stays in
    memory; the gap shows up as a warning + non-incrementing witness).
    """
    projection_ok = False
    try:
        import aiosqlite

        from dharma_swarm.spine.persistence import (
            ensure_receipt_column,
            persist_receipt,
        )

        db_path = getattr(store, "db_path", None)
        if db_path is None:
            raise RuntimeError("no runtime-state store available for receipt persistence")
        async with aiosqlite.connect(db_path, timeout=2.0) as db:
            await db.execute("PRAGMA busy_timeout=2000")
            await ensure_receipt_column(db)
            await persist_receipt(receipt, db)
        projection_ok = True
    except (
        ModuleNotFoundError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        sqlite3.Error,
    ):
        logger.warning(
            "spine: EvidenceReceipt produced but NOT persisted (task_id=%s)",
            task_id,
            exc_info=True,
        )
        projection_ok = False
    chain_ok = _append_dispatch_receipt_to_machine_chain(
        receipt,
        path=_machine_receipt_path_for_store(store, machine_receipt_path),
    )
    return projection_ok and chain_ok


def _machine_receipt_path_for_store(
    store: Any,
    override: Path | None,
) -> Path | None:
    """Keep pytest stores from writing to the operator's real witness path."""
    if override is not None:
        return override
    db_path = getattr(store, "db_path", None)
    if db_path is None:
        return None
    path = Path(db_path).expanduser()
    from dharma_swarm.spine.receipt import DEFAULT_MACHINE_RECEIPT_PATH

    dharma_root = DEFAULT_MACHINE_RECEIPT_PATH.expanduser().parent.parent
    try:
        path.relative_to(dharma_root)
        return None
    except ValueError:
        return path.with_name("claim_evidence_receipts.jsonl")


def _append_dispatch_receipt_to_machine_chain(
    receipt: EvidenceReceipt,
    *,
    path: Path | None = None,
) -> bool:
    """Append dispatch evidence to the existing machine chain, fail-open."""
    try:
        from dharma_swarm.graph.receipt_chain import (
            append_dispatch_receipt_to_machine_chain,
        )

        side_effect_key = str(receipt.attributes.get("side_effect_key", "") or "")
        append_dispatch_receipt_to_machine_chain(
            receipt,
            path=path,
            side_effect_key=side_effect_key,
        )
        return True
    except (OSError, RuntimeError, TypeError, ValueError):
        logger.warning(
            "spine: EvidenceReceipt produced but NOT hash-chained"
            " (receipt_id=%s)",
            receipt.receipt_id,
            exc_info=True,
        )
        return False


class DurableInvoker:
    """``AgentInvoker`` wrapper adding memo-check + begin/complete idempotency.

    Contract-compatible per ``spine/invoke.py`` (wrapper invokers doing
    arbitrary pre/post work are explicitly permitted — zero signature
    changes). After the call, ``memo_hit`` reports whether the provider was
    skipped and ``memo_result`` carries the memoized result text (or ``None``
    if the prior attempt's result was not recoverable).
    """

    def __init__(
        self,
        inner: AgentInvoker,
        *,
        store: Any,
        identity: ExecutionIdentity | dict[str, Any] | None,
        side_effect_key: str,
        stale_after_seconds: Optional[float] = None,
        result_provider: Optional[Callable[[], Any]] = None,
        effects: Optional[EffectsProvider] = None,
    ) -> None:
        self._inner = inner
        self._store = store
        self._identity = identity
        self._side_effect_key = side_effect_key
        self._stale_after_seconds = stale_after_seconds
        self._result_provider = result_provider
        self._effects: EffectsProvider = effects or LiveEffects()
        self.memo_hit: bool = False
        self.memo_result: Any = None
        # Set when a completed claim's result was deliberately not memoized
        # ("not_json_serializable" / "exceeds_result_cap") — the memo is
        # DECLINED and the provider re-executes rather than replaying a
        # null/corrupted result.
        self.memo_result_omitted: Optional[str] = None
        # Count of fail-open audit-write failures (memo-hit receipt /
        # complete / memo decode). Observable state so operators and tests
        # can assert the happy path never swallowed anything.
        self.audit_failures: int = 0

    # -- identity -----------------------------------------------------------

    def _resolve_identity(self, task: dict[str, Any], agent_id: str) -> ExecutionIdentity:
        raw = self._identity
        if isinstance(raw, ExecutionIdentity):
            return raw.require_for_dispatch()
        task_id = str(task.get("id", "") or task.get("task_id", "") or "")
        identity = ExecutionIdentity.from_metadata(
            {"execution_identity": dict(raw)} if isinstance(raw, dict) else None,
            task_id=task_id,
            agent_id=agent_id,
        )
        if identity is None:
            raise MissingExecutionIdentity(
                "durable_invoker requires a task_id to derive ExecutionIdentity"
            )
        return identity.require_for_dispatch()

    # -- memo sources (read-only over runtime_state-owned tables) ------------

    async def _prior_receipt_from_delegation_runs(
        self, task_id: str, run_id: str, idempotency_key: str
    ) -> EvidenceReceipt | None:
        """Fallback memo source for the exact completed delegation run.

        Trusted ONLY when the persisted receipt explicitly names OUR
        side_effect_key — a receipt with missing/malformed attributes is
        rejected outright, because a task with multiple agent dispatches or
        retries may have rewritten the row with ANOTHER dispatch's receipt.
        """
        import aiosqlite

        db_path = getattr(self._store, "db_path", None)
        if db_path is None or not task_id or not run_id or not idempotency_key:
            return None
        try:
            async with aiosqlite.connect(db_path, timeout=2.0) as db:
                await db.execute("PRAGMA busy_timeout=2000")
                row = await (
                    await db.execute(
                        "SELECT receipt_json FROM delegation_runs"
                        " WHERE task_id = ? AND run_id = ?"
                        " AND receipt_json IS NOT NULL AND receipt_json != '' LIMIT 1",
                        (task_id, run_id),
                    )
                ).fetchone()
        except Exception:
            return None
        if row is None or not row[0]:
            return None
        try:
            blob = json.loads(row[0])
            if not isinstance(blob, dict):
                return None
            attributes = blob.get("attributes")
            if (
                not isinstance(attributes, dict)
                or str(attributes.get("side_effect_key", "")) != self._side_effect_key
                or str(attributes.get("run_id", "")) != run_id
                or str(attributes.get("idempotency_key", "")) != idempotency_key
            ):
                return None
            return receipt_from_dict(blob)
        except Exception:
            return None

    async def _memo_from_record(self, record: Any, task_id: str) -> EvidenceReceipt | None:
        record_run_id = str(getattr(record, "run_id", "") or "")
        record_idempotency_key = str(
            getattr(record, "idempotency_key", "") or ""
        )
        metadata = getattr(record, "metadata", None) or {}
        blob = metadata.get(_META_RECEIPT)
        if isinstance(blob, dict):
            try:
                attributes = blob.get("attributes")
                if (
                    str(blob.get("task_id", "")) == task_id
                    and isinstance(attributes, dict)
                    and str(attributes.get("run_id", "")) == record_run_id
                    and str(attributes.get("idempotency_key", ""))
                    == record_idempotency_key
                    and str(attributes.get("side_effect_key", ""))
                    == self._side_effect_key
                ):
                    return receipt_from_dict(blob)
            except Exception:
                self.audit_failures += 1
                logger.warning(
                    "durable_invoker: completed record for %s has unreadable"
                    " receipt metadata; trying delegation_runs fallback",
                    self._side_effect_key,
                )
        return await self._prior_receipt_from_delegation_runs(
            task_id, record_run_id, record_idempotency_key
        )

    def _started_record_is_stale(self, record: Any) -> bool:
        """True when an in-flight record's holder is presumed dead."""
        if self._stale_after_seconds is None:
            return False
        updated = getattr(record, "updated_at", None)
        if not isinstance(updated, datetime):
            return False
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        # The wrapper's OWN clock decides takeover (injectable via
        # graph.effects) so a simulated run can drive stale takeover
        # deterministically even though the store stale-marks on wall time.
        age = (self._effects.now() - updated).total_seconds()
        return age >= self._stale_after_seconds

    # -- the wrapped call -----------------------------------------------------

    async def __call__(
        self,
        task: dict[str, Any],
        agent_id: str,
        context_id: str,
        routing: RoutingDecision,
    ) -> EvidenceReceipt:
        capable = self._store is not None and getattr(
            self._store, "db_path", None
        ) is not None and all(
            hasattr(self._store, attr)
            for attr in (
                "init_db",
                "try_begin_idempotent_side_effect_with_token",
                "try_reclaim_idempotent_side_effect_with_token",
                "complete_idempotent_side_effect",
                "get_idempotency_record",
            )
        )
        if not capable:
            # Fail-open: idempotency needs the runtime-state store; dispatch
            # must never break for lack of it (existing spine doctrine).
            logger.warning(
                "durable_invoker: no capable runtime-state store; executing"
                " WITHOUT idempotency (side_effect_key=%s)",
                self._side_effect_key,
            )
            receipt = await self._inner(
                task=task, agent_id=agent_id, context_id=context_id, routing=routing
            )
            return _mark_unprotected(receipt, "no_capable_store")
        try:
            identity = self._resolve_identity(task, agent_id)
        except MissingExecutionIdentity:
            logger.warning(
                "durable_invoker: incomplete ExecutionIdentity; executing"
                " WITHOUT idempotency (side_effect_key=%s)",
                self._side_effect_key,
            )
            receipt = await self._inner(
                task=task, agent_id=agent_id, context_id=context_id, routing=routing
            )
            return _mark_unprotected(receipt, "incomplete_identity")

        task_id = str(task.get("id", "") or identity.task_id)
        operation_hash = hashlib.sha256(
            f"invoke_agent:{task_id}:{agent_id}".encode("utf-8")
        ).hexdigest()
        # The claim identity: same audit fields (run/task/trace/claim ids),
        # but a DETERMINISTIC idempotency_key derived from the side-effect
        # key. Every dispatcher — including a crash-requeued one with a
        # re-minted ExecutionIdentity — races on the SAME
        # (idempotency_key, side_effect_key) primary-key row, so the
        # cross-identity overlap is resolved by the store's atomic
        # INSERT OR IGNORE, and memo lookups are PK gets (no table scan).
        claim = identity.with_updates(
            idempotency_key=claim_idempotency_key(self._side_effect_key)
        )
        claim_token: datetime | None = None

        # 1) Memo check: a completed claim row replays the prior receipt.
        memo = await self._check_memo(task_id, claim)
        if memo is not None:
            return memo

        # 2) Atomic begin on the deterministic claim row (concurrency safety
        #    across processes AND re-minted identities). Infrastructure
        #    errors fail open (dispatch availability doctrine) — loudly,
        #    never silently.
        begin_metadata = {_META_OPERATION_HASH: operation_hash, "task_id": task_id}
        try:
            claim_token = await self._store.try_begin_idempotent_side_effect_with_token(
                claim,
                self._side_effect_key,
                metadata=begin_metadata,
                stale_after_seconds=self._stale_after_seconds,
                ownership_time=self._effects.now(),
            )
        except Exception:
            logger.warning(
                "durable_invoker: idempotency begin failed for %s; executing"
                " WITHOUT idempotency",
                self._side_effect_key,
                exc_info=True,
            )
            receipt = await self._inner(
                task=task, agent_id=agent_id, context_id=context_id, routing=routing
            )
            return _mark_unprotected(receipt, "idempotency_begin_failed")
        if claim_token is None:
            try:
                record = await self._store.get_idempotency_record(
                    claim.idempotency_key, self._side_effect_key
                )
            except Exception:
                logger.warning(
                    "durable_invoker: record fetch failed for %s after lost"
                    " begin; treating as retryable",
                    self._side_effect_key,
                    exc_info=True,
                )
                record = None
            status = getattr(record, "status", "") if record is not None else ""
            if status == "completed":
                memo = await self._check_memo(task_id, claim)
                if memo is not None:
                    return memo
                # Completed but NOT replayable (result omitted, or receipt
                # unrecoverable) — loudly logged by _check_memo. The
                # re-execution must still be exactly-once: CAS-reclaim the
                # completed row; concurrent decliners lose cleanly.
                claim_token = await self._reclaim_or_lose(
                    claim, expected_status="completed", record=record
                )
            elif status == "started" and not self._started_record_is_stale(record):
                # The store already stale-marks dead holders on its own
                # (wall) clock; the wrapper re-checks with ITS clock so a
                # simulated run can drive stale takeover deterministically.
                # A record still fresh on both clocks is a live concurrent
                # duplicate — lose cleanly.
                raise DuplicateDispatchInFlight(self._side_effect_key)
            elif record is not None:
                # stale / failed / started-but-stale: the prior holder is
                # dead or the prior attempt failed. TAKEOVER MUST BE ATOMIC:
                # N concurrent recovery workers all reach this branch; the
                # CAS re-claim lets exactly one flip the row back to
                # 'started' — losers refuse to double-call the provider.
                claim_token = await self._reclaim_or_lose(
                    claim, expected_status=status, record=record
                )
            # record fetch failed (None): fail-open, execute below (logged).

        # 3) Execute the provider call.
        try:
            receipt = await self._inner(
                task=task, agent_id=agent_id, context_id=context_id, routing=routing
            )
        except Exception:
            # Never falsely complete: mark failed so a retry re-executes.
            await self._complete_fail_open(
                claim,
                status="failed",
                result_receipt_id="",
                metadata={_META_OPERATION_HASH: operation_hash},
                claim_token=claim_token,
            )
            raise

        # The wrapper, not the provider-facing invoker, owns execution
        # identity. Bind the receipt to the exact attempt before it can enter
        # either the idempotency record or delegation_runs projection.
        receipt = dataclasses.replace(
            receipt,
            trace_id=identity.trace_id,
            task_id=task_id,
            claim_id=identity.claim_id,
            attributes={
                **receipt.attributes,
                "run_id": identity.run_id,
                "idempotency_key": claim.idempotency_key,
                "dispatch_idempotency_key": identity.idempotency_key,
                "side_effect_key": self._side_effect_key,
            },
        )

        # 4) Complete the record; memoize the receipt (and result text) so a
        #    later replay can return them without a provider call.
        complete_metadata: dict[str, Any] = {
            _META_OPERATION_HASH: operation_hash,
            _META_RECEIPT: receipt.to_dict(),
            _META_RESULT_JSON: None, _META_RESULT_OMITTED: None,
        }
        if receipt.status == "ok" and self._result_provider is not None:
            try:
                result = self._result_provider()
            except Exception:
                result = None
            if result is not None:
                complete_metadata.update(_encode_memo_result(result))
        await self._complete_fail_open(
            claim,
            status="completed" if receipt.status == "ok" else "failed",
            result_receipt_id=str(receipt.receipt_id),
            metadata=complete_metadata,
            claim_token=claim_token,
        )
        if claim_token is None:
            # Begin lost the claim AND the record was unrecoverable: the
            # provider ran with no fence and the completion above was refused.
            return _mark_unprotected(receipt, "begin_lost_unreclaimed")
        return receipt

    async def _reclaim_or_lose(
        self,
        claim: ExecutionIdentity,
        *,
        expected_status: str,
        record: Any = None,
    ) -> datetime:
        """CAS-reclaim an observed token or refuse stale/ABA execution."""
        if record is None or not isinstance(getattr(record, "updated_at", None), datetime):
            raise DuplicateDispatchInFlight(self._side_effect_key)
        try:
            token = await self._store.try_reclaim_idempotent_side_effect_with_token(
                claim,
                self._side_effect_key,
                expected_status=expected_status,
                expected_updated_at=record.updated_at,
                ownership_time=self._effects.now(),
            )
        except Exception:
            logger.warning(
                "durable_invoker: reclaim failed for %s; refusing to execute"
                " without a claim",
                self._side_effect_key,
                exc_info=True,
            )
            token = None
        if token is None:
            raise DuplicateDispatchInFlight(self._side_effect_key)
        return token

    async def _check_memo(
        self,
        task_id: str,
        claim: ExecutionIdentity,
    ) -> EvidenceReceipt | None:
        """PK lookup on the deterministic claim row; memo on completion."""
        try:
            record = await self._store.get_idempotency_record(
                claim.idempotency_key, self._side_effect_key
            )
        except Exception:
            logger.warning(
                "durable_invoker: memo probe failed for %s; proceeding to begin",
                self._side_effect_key,
                exc_info=True,
            )
            return None
        if record is None or getattr(record, "status", "") != "completed":
            return None
        metadata = getattr(record, "metadata", None) or {}
        omitted = metadata.get(_META_RESULT_OMITTED)
        if omitted:
            # The prior attempt's result could not be memoized (oversized /
            # non-JSON). Replaying the receipt would complete the task with
            # a null result — silently corrupting the dispatch return
            # contract — so DECLINE the memo and re-execute the provider:
            # exactly-once holds whenever the result is memoizable;
            # availability wins when it is not.
            self.memo_result_omitted = str(omitted)
            logger.info(
                "durable_invoker: declining memo replay for %s (%s);"
                " re-executing provider",
                self._side_effect_key,
                omitted,
            )
            return None
        receipt = await self._memo_from_record(record, task_id)
        if receipt is None:
            logger.warning(
                "durable_invoker: completed idempotency record for %s but no"
                " recoverable receipt; refusing memo, will re-verify via begin",
                self._side_effect_key,
            )
            return None
        self.memo_hit = True
        self.memo_result = _decode_memo_result(metadata)
        try:
            await self._store.record_idempotency_consumed(
                claim,
                self._side_effect_key,
                status="memo_hit",
                payload={
                    "result_receipt_id": str(getattr(record, "result_receipt_id", "") or "")
                },
            )
        except Exception:
            self.audit_failures += 1
            logger.debug("durable_invoker: memo_hit audit receipt failed", exc_info=True)
        return receipt

    async def _complete_fail_open(
        self,
        identity: ExecutionIdentity,
        *,
        status: str,
        result_receipt_id: str,
        metadata: dict[str, Any],
        claim_token: datetime | None,
    ) -> None:
        if claim_token is None:
            self.audit_failures += 1
            logger.warning(
                "durable_invoker: refusing unfenced completion for %s",
                self._side_effect_key,
            )
            return
        try:
            await self._store.complete_idempotent_side_effect(
                identity,
                self._side_effect_key,
                status=status,
                result_receipt_id=result_receipt_id,
                metadata=metadata,
                expected_updated_at=claim_token,
            )
        except Exception:
            # Fail-open on the audit write, but loudly: a missing completion
            # means the next attempt re-executes (safe direction — provider
            # work is lost, never silently doubled-and-hidden).
            self.audit_failures += 1
            logger.warning(
                "durable_invoker: complete_idempotent_side_effect failed for %s"
                " (status=%s)",
                self._side_effect_key,
                status,
                exc_info=True,
            )


def wrap_invoker(
    inner: AgentInvoker,
    *,
    store: Any,
    identity: ExecutionIdentity | dict[str, Any] | None,
    side_effect_key: str,
    stale_after_seconds: Optional[float] = None,
    result_provider: Optional[Callable[[], Any]] = None,
    effects: Optional[EffectsProvider] = None,
) -> DurableInvoker:
    """Wrap an ``AgentInvoker`` with memo-check + begin/complete idempotency.

    Parameters
    ----------
    inner:
        The real execution backend (e.g. the orchestrator's ``_orch_invoker``).
    store:
        The ``RuntimeStateStore`` (or ``None`` — fail-open passthrough).
    identity:
        An ``ExecutionIdentity``, its dict form (``td.metadata
        ["execution_identity"]``), or ``None`` (fail-open passthrough).
    side_effect_key:
        Deterministic key for this dispatch (flat form
        ``invoke_agent:{task_id}:{agent_id}``, or
        ``derive_graph_side_effect_key(...)`` for graph runs).
    stale_after_seconds:
        Age after which a ``started`` record is presumed dead and taken over
        (crash-resume). ``None`` means in-flight records never go stale.
    result_provider:
        Zero-arg callable returning the run result AFTER the inner call (the
        orchestrator's ``captured["result"]``); memoized alongside the
        receipt so a replay can return it.
    effects:
        Injectable clock/rng/dispatch-order provider (``graph.effects``);
        defaults to ``LiveEffects``. Simulated runs pass ``SimulatedEffects``
        so staleness decisions replay deterministically from a seed.
    """
    if not side_effect_key:
        raise ValueError("side_effect_key is required")
    return DurableInvoker(
        inner,
        store=store,
        identity=identity,
        side_effect_key=side_effect_key,
        stale_after_seconds=stale_after_seconds,
        result_provider=result_provider,
        effects=effects,
    )
