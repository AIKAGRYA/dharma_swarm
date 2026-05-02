"""Unified memory lattice facade over runtime events, recall, and facts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.chetana.governance import gate_check_atom
from dharma_swarm.chetana.provenance import GateCheckRecord
from dharma_swarm.engine.event_memory import EventMemoryStore
from dharma_swarm.engine.hybrid_retriever import HybridRetriever
from dharma_swarm.engine.unified_index import UnifiedIndex
from dharma_swarm.event_log import EventLog
from dharma_swarm.memory import StrangeLoopMemory
from dharma_swarm.models import MemoryEntry, MemoryLayer
from dharma_swarm.policy_compiler import PolicyCompiler, PolicyDecision
from dharma_swarm.register_disciplines import (
    DisciplineResult,
    make_register_mark,
    write_register_mark,
)
from dharma_swarm.runtime_contract import RuntimeEnvelope
from dharma_swarm.runtime_state import (
    ContextBundleRecord,
    MemoryEdge,
    MemoryFact,
    RuntimeStateStore,
)


@dataclass(frozen=True)
class MemoryRecallHit:
    record_id: str
    source_kind: str
    text: str
    score: float
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdmissionResult:
    accepted: bool
    object_id: str | None
    object_kind: str
    gate_check: GateCheckRecord
    policy_decision: PolicyDecision | None
    rationale: str
    admitted_at: str


@dataclass(frozen=True)
class RetrievalAdmissionPolicy:
    """Policy for what enters the compiled memory context.

    Enforcement scope (current):
      - ``max_tokens`` — capped at compile time via the bundle's token budget.
      - ``min_confidence`` — facts below threshold are dropped post-fetch from
        ``injected_fact_ids`` / ``citation_handles`` and tracked under
        ``policy_dropped_fact_ids`` in bundle metadata.
      - ``max_age_days`` — same post-fetch drop semantics keyed off the fact's
        ``valid_from``.
      - ``source_scope`` — same post-fetch drop semantics keyed off ``fact_kind``
        prefixes.
      - ``require_axiom_signature`` — same post-fetch drop semantics requiring
        ``provenance.admission.axiom_signature`` to be present and non-empty.

    Enforcement scope (NOT yet wired — scaffolding for follow-up slice):
      - ``min_truth_state`` — ``ContextCompiler.compile_bundle`` currently
        hardcodes ``truth_state="promoted"``; relaxing this requires extending
        the compiler signature and is deferred. Tighter-than-promoted (e.g.
        require ``trusted``) is also not yet enforced.
      - ``allow_contradicting_within_session`` — populated by Slice 5b
        contradiction detector but does not yet feed back to drop facts.
      - ``drop_superseded`` — same.

    The honest contract: this policy filters at the metadata/citation level for
    every field listed under "Enforcement scope (current)". The bundle's
    rendered_text may still contain facts the policy would drop, until full
    compile-bundle integration lands. Metadata-level drops are sufficient for
    citation-rate telemetry; render-level drops await the next slice.
    """

    min_truth_state: str = "candidate"
    min_confidence: float = 0.0
    max_age_days: int | None = None
    allow_contradicting_within_session: bool = False
    max_tokens: int = 4000
    source_scope: frozenset[str] = frozenset()
    require_axiom_signature: bool = False
    drop_superseded: bool = True

    @classmethod
    def default(cls) -> "RetrievalAdmissionPolicy":
        return cls()

    @classmethod
    def strict(cls) -> "RetrievalAdmissionPolicy":
        return cls(
            min_truth_state="promoted",
            min_confidence=0.6,
            max_age_days=90,
            drop_superseded=True,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "min_truth_state": self.min_truth_state,
            "min_confidence": self.min_confidence,
            "max_age_days": self.max_age_days,
            "allow_contradicting_within_session": self.allow_contradicting_within_session,
            "max_tokens": self.max_tokens,
            "source_scope": sorted(self.source_scope),
            "require_axiom_signature": self.require_axiom_signature,
            "drop_superseded": self.drop_superseded,
        }


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(data: Any) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _gate_record_id(record: GateCheckRecord) -> str:
    return _sha256(record.model_dump(mode="json"))[:24]


def _policy_payload(decision: PolicyDecision | None) -> dict[str, Any] | None:
    if decision is None:
        return None
    return decision.model_dump(mode="json")


def _make_gate_record(
    *,
    result: str = "ALLOW",
    rationale: str | None = None,
    gates_warned: list[str] | None = None,
    gates_blocked: list[str] | None = None,
    policy_checked: bool = False,
) -> GateCheckRecord:
    """Build an audit-honest GateCheckRecord.

    ``policy_checked`` must be True only when a real policy was compiled and
    evaluated. Otherwise ``gates_passed`` stays empty regardless of result —
    claiming a gate ran when none did is misleading audit metadata.
    """
    if policy_checked and result == "ALLOW":
        gates_passed = ["memory_lattice.policy"]
    else:
        gates_passed = []
    return GateCheckRecord(
        result=result,  # type: ignore[arg-type]
        gates_passed=gates_passed,
        gates_warned=list(gates_warned or []),
        gates_blocked=list(gates_blocked or []),
        rationale=rationale,
        checked_at=_utc_iso(),
    )


class MemoryLattice:
    """Coordinate evidence, facts, retrieval, and strange-loop memory."""

    def __init__(
        self,
        *,
        db_path: Path | str | None = None,
        event_log_dir: Path | str | None = None,
    ) -> None:
        self.runtime_state = RuntimeStateStore(db_path)
        self.event_store = EventMemoryStore(self.runtime_state.db_path)
        self.index = UnifiedIndex(self.runtime_state.db_path)
        self.retriever = HybridRetriever(self.index)
        self.strange_loop = StrangeLoopMemory(self.runtime_state.db_path)
        self.event_log = EventLog(event_log_dir)

    def _index_memory_fact(self, fact: MemoryFact) -> None:
        self.index.index_document(
            "memory_fact",
            f"memory://{fact.fact_id}",
            fact.text,
            {
                **fact.metadata,
                "fact_id": fact.fact_id,
                "fact_kind": fact.fact_kind,
                "truth_state": fact.truth_state,
                "session_id": fact.session_id,
                "task_id": fact.task_id,
                "source_event_id": fact.source_event_id,
                "source_artifact_id": fact.source_artifact_id,
                "confidence": fact.confidence,
            },
        )

    def _policy_from_context(self, context: Any) -> Any:
        if not isinstance(context, dict):
            return None
        policy = context.get("policy") or context.get("compiled_policy")
        if policy is not None and hasattr(policy, "check_action"):
            return policy
        if "kernel_principles" in context or "accepted_claims" in context:
            return PolicyCompiler().compile(
                kernel_principles=context.get("kernel_principles") or {},
                accepted_claims=context.get("accepted_claims") or [],
                context=str(context.get("policy_context", "memory admission")),
            )
        return None

    def _check_policy(
        self,
        *,
        action: str,
        context: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> PolicyDecision | None:
        policy = self._policy_from_context(context)
        if policy is None:
            return None
        return policy.check_action(
            action,
            context=str(context.get("description", "")) if isinstance(context, dict) else "",
            action_metadata=dict(metadata or {}),
        )

    @staticmethod
    def _admission_provenance(
        *,
        admitter: str,
        admitted_at: str,
        gate_check: GateCheckRecord,
        policy_decision: PolicyDecision | None,
        metadata: dict[str, Any] | None = None,
        axiom_signature: str = "",
    ) -> dict[str, Any]:
        normalized_metadata = dict(metadata or {})
        return {
            "version": 1,
            "admitted_at": admitted_at,
            "admitter": admitter,
            "gate_check_id": _gate_record_id(gate_check),
            "gate_result": gate_check.result,
            "axiom_signature": axiom_signature,
            "policy_decision": _policy_payload(policy_decision),
            "request_metadata_hash": _sha256(normalized_metadata)[:24],
        }

    @staticmethod
    def _resolve_retrieval_policy(
        policy: RetrievalAdmissionPolicy | dict[str, Any] | None,
        membrane_policy: str,
    ) -> RetrievalAdmissionPolicy:
        if isinstance(policy, RetrievalAdmissionPolicy):
            return policy
        if isinstance(policy, dict):
            values = dict(policy)
            if "source_scope" in values and not isinstance(values["source_scope"], frozenset):
                values["source_scope"] = frozenset(values["source_scope"] or [])
            return RetrievalAdmissionPolicy(**values)
        if membrane_policy == "strict":
            return RetrievalAdmissionPolicy.strict()
        return RetrievalAdmissionPolicy.default()

    @staticmethod
    def _fact_ids_from_source_refs(source_refs: list[str]) -> list[str]:
        fact_ids: list[str] = []
        for ref in source_refs:
            if ref.startswith("memory://"):
                fact_ids.append(ref.removeprefix("memory://"))
        return fact_ids

    @staticmethod
    def _fact_records_from_bundle(bundle: ContextBundleRecord) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for section in bundle.sections:
            if section.get("name") != "Durable Facts":
                continue
            refs = [ref for ref in bundle.source_refs if str(ref).startswith("memory://")]
            lines = str(section.get("content", "")).splitlines()
            for idx, line in enumerate(lines):
                fact_id = refs[idx].removeprefix("memory://") if idx < len(refs) else f"fact-{idx}"
                records.append({"id": fact_id, "text": line})
        return records

    async def init_db(self) -> None:
        await self.runtime_state.init_db()
        await self.event_store.init_db()
        await self.strange_loop.init_db()

    async def close(self) -> None:
        await self.strange_loop.close()

    async def ingest_runtime_envelope(
        self,
        envelope: RuntimeEnvelope | dict[str, Any],
        *,
        write_jsonl: bool = True,
    ) -> bool:
        inserted = await self.event_store.ingest_envelope(envelope)
        if inserted and write_jsonl:
            self.event_log.append_envelope(envelope)
        return inserted

    async def remember(
        self,
        content: str,
        layer: MemoryLayer,
        *,
        source: str = "agent",
        tags: list[str] | None = None,
        development_marker: bool = False,
        bypass_fitness: bool = False,
    ) -> MemoryEntry:
        entry = await self.strange_loop.remember(
            content,
            layer,
            source=source,
            tags=tags,
            development_marker=development_marker,
            bypass_fitness=bypass_fitness,
        )
        if layer != MemoryLayer.IMMEDIATE:
            self.index.index_document(
                "strange_loop",
                f"strangeloop://{entry.id}",
                entry.content,
                {
                    "memory_layer": entry.layer.value,
                    "memory_tags": list(entry.tags),
                    "memory_source": entry.source,
                    "development_marker": entry.development_marker,
                    "witness_quality": entry.witness_quality,
                    "recorded_at": entry.timestamp.isoformat(),
                },
            )
        return entry

    async def admit_register_mark(
        self,
        *,
        discipline: str,
        subject_id: str,
        severity: str,
        rationale: str,
        plane: str = "operator",
        metadata: dict[str, Any] | None = None,
        context: Any = None,
    ) -> AdmissionResult:
        admitted_at = _utc_iso()
        policy_decision = self._check_policy(
            action="memory.write_register_mark",
            context=context,
            metadata={
                "discipline": discipline,
                "subject_id": subject_id,
                "severity": severity,
                **(metadata or {}),
            },
        )
        if policy_decision is not None and not policy_decision.allowed:
            gate_check = _make_gate_record(
                result="BLOCK",
                rationale=policy_decision.reason or "policy blocked register mark",
                gates_blocked=["policy"],
            )
            return AdmissionResult(
                accepted=False,
                object_id=None,
                object_kind="register_mark",
                gate_check=gate_check,
                policy_decision=policy_decision,
                rationale=gate_check.rationale or "",
                admitted_at=admitted_at,
            )

        result = DisciplineResult(
            flagged=severity in {"warn", "hold", "block"},
            confidence=float((metadata or {}).get("confidence", 1.0)),
            explanation=rationale,
            markers=list((metadata or {}).get("markers", [])),
            discipline=discipline,
        )
        mark = make_register_mark(
            result,
            plane=plane,
            subject_id=subject_id,
            severity=severity,
            links={
                "admission": self._admission_provenance(
                    admitter="MemoryLattice.admit_register_mark",
                    admitted_at=admitted_at,
                    gate_check=_make_gate_record(
                        rationale=(
                            "policy allowed register mark"
                            if policy_decision is not None
                            else "no policy configured; default-allow register mark"
                        ),
                        policy_checked=policy_decision is not None,
                    ),
                    policy_decision=policy_decision,
                    metadata=metadata,
                )
            },
        )
        ok = write_register_mark(mark)
        gate_check = _make_gate_record(
            result="ALLOW" if ok else "BLOCK",
            rationale="register mark written" if ok else "register mark write failed or suppressed",
            gates_blocked=[] if ok else ["register_write"],
            policy_checked=policy_decision is not None,
        )
        return AdmissionResult(
            accepted=ok,
            object_id=mark.mark_id if ok else None,
            object_kind="register_mark",
            gate_check=gate_check,
            policy_decision=policy_decision,
            rationale=gate_check.rationale or "",
            admitted_at=admitted_at,
        )

    async def always_on_context(self, max_chars: int = 3000) -> str:
        return await self.strange_loop.get_context(max_chars=max_chars)

    def index_document(
        self,
        source_kind: str,
        source_path: str,
        text: str,
        metadata: dict[str, Any],
    ) -> str:
        return self.index.index_document(source_kind, source_path, text, metadata)

    def index_note_file(
        self,
        path: Path,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        return self.index.index_note_file(path, metadata=metadata)

    async def record_fact(
        self,
        text: str,
        *,
        fact_kind: str = "fact",
        truth_state: str = "candidate",
        confidence: float = 0.5,
        session_id: str = "",
        task_id: str = "",
        source_event_id: str = "",
        source_artifact_id: str = "",
        metadata: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> MemoryFact:
        fact = MemoryFact(
            fact_id=self.runtime_state.new_fact_id(),
            fact_kind=fact_kind,
            truth_state=truth_state,
            text=text,
            confidence=float(confidence),
            session_id=session_id,
            task_id=task_id,
            source_event_id=source_event_id,
            source_artifact_id=source_artifact_id,
            provenance=dict(provenance or {}),
            metadata=dict(metadata or {}),
        )
        saved = await self.runtime_state.record_memory_fact(fact)
        self._index_memory_fact(saved)
        return saved

    async def admit_memory_fact(
        self,
        fact: MemoryFact,
        *,
        action: str = "memory.write_fact",
        context: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> AdmissionResult:
        admitted_at = _utc_iso()
        request_metadata = {
            "fact_id": fact.fact_id,
            "fact_kind": fact.fact_kind,
            "truth_state": fact.truth_state,
            **(metadata or {}),
        }
        policy_decision = self._check_policy(
            action=action,
            context=context,
            metadata=request_metadata,
        )
        if policy_decision is not None and not policy_decision.allowed:
            gate_check = _make_gate_record(
                result="BLOCK",
                rationale=policy_decision.reason or "policy blocked memory fact",
                gates_blocked=["policy"],
            )
            return AdmissionResult(
                accepted=False,
                object_id=None,
                object_kind="fact",
                gate_check=gate_check,
                policy_decision=policy_decision,
                rationale=gate_check.rationale or "",
                admitted_at=admitted_at,
            )

        if policy_decision is not None:
            allow_rationale = "policy allowed memory fact"
        else:
            allow_rationale = "no policy configured; default-allow memory fact"
        gate_check = _make_gate_record(
            rationale=allow_rationale,
            policy_checked=policy_decision is not None,
        )
        admitted = replace(
            fact,
            provenance={
                **fact.provenance,
                "admission": self._admission_provenance(
                    admitter="MemoryLattice.admit_memory_fact",
                    admitted_at=admitted_at,
                    gate_check=gate_check,
                    policy_decision=policy_decision,
                    metadata=request_metadata,
                ),
            },
            updated_at=datetime.now(timezone.utc),
        )
        saved = await self.runtime_state.record_memory_fact(admitted)
        self._index_memory_fact(saved)
        return AdmissionResult(
            accepted=True,
            object_id=saved.fact_id,
            object_kind="fact",
            gate_check=gate_check,
            policy_decision=policy_decision,
            rationale=gate_check.rationale or "",
            admitted_at=admitted_at,
        )

    async def admit_memory_edge(
        self,
        edge: MemoryEdge,
        *,
        action: str = "memory.write_edge",
        context: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> AdmissionResult:
        admitted_at = _utc_iso()
        request_metadata = {
            "edge_id": edge.edge_id,
            "relation": edge.relation,
            **(metadata or {}),
        }
        policy_decision = self._check_policy(
            action=action,
            context=context,
            metadata=request_metadata,
        )
        if policy_decision is not None and not policy_decision.allowed:
            gate_check = _make_gate_record(
                result="BLOCK",
                rationale=policy_decision.reason or "policy blocked memory edge",
                gates_blocked=["policy"],
            )
            return AdmissionResult(
                accepted=False,
                object_id=None,
                object_kind="edge",
                gate_check=gate_check,
                policy_decision=policy_decision,
                rationale=gate_check.rationale or "",
                admitted_at=admitted_at,
            )

        if policy_decision is not None:
            allow_rationale = "policy allowed memory edge"
        else:
            allow_rationale = "no policy configured; default-allow memory edge"
        gate_check = _make_gate_record(
            rationale=allow_rationale,
            policy_checked=policy_decision is not None,
        )
        admitted = replace(
            edge,
            metadata={
                **edge.metadata,
                "admission": self._admission_provenance(
                    admitter="MemoryLattice.admit_memory_edge",
                    admitted_at=admitted_at,
                    gate_check=gate_check,
                    policy_decision=policy_decision,
                    metadata=request_metadata,
                ),
            },
        )
        saved = await self.runtime_state.record_memory_edge(admitted)
        return AdmissionResult(
            accepted=True,
            object_id=saved.edge_id,
            object_kind="edge",
            gate_check=gate_check,
            policy_decision=policy_decision,
            rationale=gate_check.rationale or "",
            admitted_at=admitted_at,
        )

    async def admit_chetana_atom(
        self,
        atom_content: str,
        atom_title: str,
        *,
        requested_action: str = "promote",
        metadata: dict[str, Any] | None = None,
    ) -> AdmissionResult:
        admitted_at = _utc_iso()
        request_metadata = dict(metadata or {})
        governance = gate_check_atom(
            atom_content=atom_content,
            atom_title=atom_title,
            requested_action=requested_action,
            metadata=request_metadata,
        )
        atom_id = str(request_metadata.get("atom_id") or _sha256({
            "title": atom_title,
            "content": atom_content,
        })[:24])
        return AdmissionResult(
            accepted=governance.can_promote,
            object_id=atom_id if governance.can_promote else None,
            object_kind="atom",
            gate_check=governance.record,
            policy_decision=None,
            rationale=governance.record.rationale or "",
            admitted_at=admitted_at,
        )

    async def promote_fact(
        self,
        fact_id: str,
        *,
        truth_state: str = "promoted",
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryFact:
        updated = await self.runtime_state.update_memory_fact_truth(
            fact_id,
            truth_state=truth_state,
            confidence=confidence,
            metadata=metadata,
        )
        self._index_memory_fact(updated)
        return updated

    async def compile_memory_context(
        self,
        *,
        session_id: str,
        task_id: str = "",
        token_budget: int = 1200,
        membrane_policy: str = "default",
        **kwargs: Any,
    ) -> ContextBundleRecord:
        from dharma_swarm.context_compiler import ContextCompiler
        from dharma_swarm.retrieval.contradiction_detector import detect_contradictions
        from dharma_swarm.retrieval.retrieval_effect_logger import (
            RetrievalEffect,
            citation_handle_for_fact_id,
            log_effect,
            new_effect_id,
            now_iso,
        )

        retrieval_policy = self._resolve_retrieval_policy(
            kwargs.pop("retrieval_policy", None),
            membrane_policy,
        )
        effect_log_path = kwargs.pop("retrieval_effect_path", None)
        effective_token_budget = min(int(token_budget), int(retrieval_policy.max_tokens))
        metadata = {
            **dict(kwargs.pop("metadata", {}) or {}),
            "membrane_policy": membrane_policy,
            "retrieval_policy": retrieval_policy.as_dict(),
            "compiled_by": "MemoryLattice.compile_memory_context",
        }
        compiler = ContextCompiler(
            runtime_state=self.runtime_state,
            memory_lattice=self,
        )
        bundle = await compiler.compile_bundle(
            session_id=session_id,
            task_id=task_id,
            token_budget=effective_token_budget,
            metadata=metadata,
            **kwargs,
        )
        fact_ids = self._fact_ids_from_source_refs(bundle.source_refs)
        kept_fact_ids, drop_records = await self._apply_retrieval_policy(
            fact_ids, retrieval_policy
        )
        contradictions = detect_contradictions(self._fact_records_from_bundle(bundle))
        contradiction_tuples = [
            (item.left_id, item.right_id, item.reason)
            for item in contradictions
        ]
        effect = RetrievalEffect(
            effect_id=new_effect_id(),
            session_id=session_id,
            task_id=task_id,
            injected_fact_ids=kept_fact_ids,
            citation_handles=[citation_handle_for_fact_id(fid) for fid in kept_fact_ids],
            policy_used=retrieval_policy.as_dict(),
            token_budget=effective_token_budget,
            actual_tokens=max(1, len(bundle.rendered_text) // 4) if bundle.rendered_text else 0,
            contradictions_dropped=[],
            ts=now_iso(),
        )
        log_effect(effect, path=effect_log_path)
        updated = replace(
            bundle,
            metadata={
                **bundle.metadata,
                "retrieval_effect_id": effect.effect_id,
                "retrieval_fact_ids": kept_fact_ids,
                "citation_handles": effect.citation_handles,
                "contradictions_detected": contradiction_tuples,
                "policy_dropped_fact_ids": [r["fact_id"] for r in drop_records],
                "policy_drop_reasons": drop_records,
                "policy_enforcement_level": "metadata-only-pending-render-integration",
            },
        )
        return await self.runtime_state.record_context_bundle(updated)

    async def _apply_retrieval_policy(
        self,
        fact_ids: list[str],
        policy: RetrievalAdmissionPolicy,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Drop fact IDs that fail the policy from the injected list.

        Filters at the metadata level: ``min_confidence``, ``max_age_days``,
        ``source_scope``, ``require_axiom_signature``. Returns the kept IDs and
        a parallel list of drop records ``{fact_id, reason}``. The bundle's
        rendered text is NOT trimmed — that integration is deferred — but
        downstream telemetry will see the policy-honored injected list.
        """
        if not fact_ids:
            return [], []
        kept: list[str] = []
        drops: list[dict[str, Any]] = []
        cutoff_iso: str | None = None
        if policy.max_age_days is not None and policy.max_age_days >= 0:
            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=policy.max_age_days)
            cutoff_iso = cutoff_dt.isoformat()
        scopes = tuple(policy.source_scope) if policy.source_scope else ()
        for fact_id in fact_ids:
            fact = await self.runtime_state.get_memory_fact(fact_id)
            if fact is None:
                drops.append({"fact_id": fact_id, "reason": "not_found"})
                continue
            if fact.confidence < policy.min_confidence:
                drops.append({"fact_id": fact_id, "reason": "min_confidence"})
                continue
            if scopes and not any(fact.fact_kind == s or fact.fact_kind.startswith(f"{s}.") for s in scopes):
                drops.append({"fact_id": fact_id, "reason": "source_scope"})
                continue
            if cutoff_iso is not None:
                valid_from = (fact.valid_from or "").strip()
                if valid_from and valid_from < cutoff_iso:
                    drops.append({"fact_id": fact_id, "reason": "max_age_days"})
                    continue
            if policy.require_axiom_signature:
                admission = (fact.provenance or {}).get("admission") if isinstance(fact.provenance, dict) else None
                axiom_sig = (admission or {}).get("axiom_signature", "") if isinstance(admission, dict) else ""
                if not axiom_sig:
                    drops.append({"fact_id": fact_id, "reason": "require_axiom_signature"})
                    continue
            kept.append(fact_id)
        return kept, drops

    async def replay_session(self, session_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        return await self.event_store.replay_session(session_id, limit=limit)

    async def replay_trace(self, trace_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        return await self.event_store.replay_trace(trace_id, limit=limit)

    async def recall(
        self,
        query: str,
        *,
        limit: int = 10,
        session_id: str | None = None,
        task_id: str | None = None,
        truth_state: str | None = None,
        consumer: str | None = None,
    ) -> list[MemoryRecallHit]:
        filters: dict[str, Any] = {}
        if session_id:
            filters["session_id"] = session_id
        if task_id:
            filters["task_id"] = task_id
        if truth_state:
            filters["truth_state"] = truth_state
        hits = self.retriever.search(
            query,
            limit=limit,
            filters=filters or None,
            consumer=consumer,
        )
        return [
            MemoryRecallHit(
                record_id=hit.record.record_id,
                source_kind=str(hit.record.metadata.get("source_kind", "unknown")),
                text=hit.record.text,
                score=float(hit.score),
                created_at=hit.record.created_at,
                metadata=dict(hit.record.metadata),
                evidence=dict(hit.evidence),
            )
            for hit in hits
        ]
