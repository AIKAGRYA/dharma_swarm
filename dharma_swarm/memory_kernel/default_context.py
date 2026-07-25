"""Default Memory Kernel context section helpers."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable

from dharma_swarm.context_compiler_utils import (
    ContextSection,
    dedupe_strings as _dedupe,
)
from dharma_swarm.memory_kernel import (
    MemoryContextBudget,
    MemoryContextPack,
    MemoryLane,
    MemoryQuery,
    MemoryScope,
    TruthState,
    preview_memory_pack,
)
from dharma_swarm.memory_kernel.topology_policy import (
    SUPERVISOR_SCOPED,
    isolation_legacy_enabled,
    resolve as resolve_isolation_semantics,
)

logger = logging.getLogger(__name__)


# Pre-typed isolation vocabulary, kept ONLY for the one-release
# DHARMA_MEMORY_KERNEL_ISOLATION_LEGACY=1 escape hatch. Remove with it.
_LEGACY_TOPOLOGY_MODES = {"swarm", "supervisor", "subagents_as_tools"}

# Ops kill switch for the ranked retrieval shadow. Default ON (the shadow
# phase exists to collect receipts); set to 0 only if shadow latency pushes
# bundle compiles toward the orchestrator timeout.
RANKED_SHADOW_ENV = "DHARMA_MEMORY_KERNEL_RANKED_SHADOW"


def _ranked_shadow_enabled() -> bool:
    raw = os.environ.get(RANKED_SHADOW_ENV, "1")
    return raw.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class MemoryKernelIsolationPolicy:
    applied: bool = False
    topology: str = ""
    agent_id: str = ""
    allowed_agent_ids: tuple[str, ...] = ()
    allowed_scopes: tuple[MemoryScope, ...] = ()
    allowed_memory_lanes: tuple[MemoryLane, ...] = ()
    semantics: str = ""
    warnings: tuple[str, ...] = ()

    def metadata(self) -> dict[str, Any]:
        return {
            "isolation_applied": self.applied,
            "isolation_topology": self.topology,
            "isolation_agent_id": self.agent_id,
            "isolation_semantics": self.semantics,
            "isolation_warnings": list(self.warnings),
            "allowed_agent_ids": list(self.allowed_agent_ids),
            "allowed_scopes": [item.value for item in self.allowed_scopes],
            "allowed_memory_lanes": [item.value for item in self.allowed_memory_lanes],
        }


def memory_kernel_isolation_policy_from_metadata(
    metadata: dict[str, Any] | None,
) -> MemoryKernelIsolationPolicy:
    """Derive the MemoryKernel read policy for one live agent context bundle.

    Every bundle gets an applied policy: known topologies map through
    ``topology_policy.ISOLATION_SEMANTICS``; unknown/missing topology fails
    closed to minimal shared allowances with a stamped warning.
    """

    source = metadata or {}
    if isolation_legacy_enabled():
        return _legacy_isolation_policy_from_metadata(source)

    raw_topology = (
        source.get("topology")
        or source.get("topology_mode")
        or source.get("topology_type")
    )
    topology = _clean_text(getattr(raw_topology, "value", raw_topology))
    semantics, warnings = resolve_isolation_semantics(raw_topology)
    agent_id = _clean_text(
        source.get("agent_id")
        or source.get("active_agent")
        or source.get("parent_agent_id")
    )
    explicit_agent_ids = _string_tuple(source.get("memory_kernel_allowed_agent_ids"))
    allowed_agent_ids = explicit_agent_ids or ((agent_id,) if agent_id else ())
    explicit_scopes = _memory_scope_tuple(source.get("memory_kernel_allowed_scopes"))
    explicit_lanes = _memory_lane_tuple(source.get("memory_kernel_allowed_memory_lanes"))
    # Explicit metadata allowances take precedence over the typed semantics
    # (pre-existing contract); stamp a warning so the semantics name in the
    # bundle metadata cannot silently claim what the allowances override.
    override_warnings = list(warnings)
    if explicit_scopes and explicit_scopes != semantics.allowed_scopes:
        override_warnings.append("explicit_scopes_override_topology_semantics")
    if explicit_lanes and explicit_lanes != semantics.allowed_memory_lanes:
        override_warnings.append("explicit_lanes_override_topology_semantics")

    return MemoryKernelIsolationPolicy(
        applied=True,
        topology=topology,
        agent_id=agent_id,
        allowed_agent_ids=allowed_agent_ids,
        allowed_scopes=explicit_scopes or semantics.allowed_scopes,
        allowed_memory_lanes=explicit_lanes or semantics.allowed_memory_lanes,
        semantics=semantics.name,
        warnings=tuple(override_warnings),
    )


def _legacy_isolation_policy_from_metadata(
    source: dict[str, Any],
) -> MemoryKernelIsolationPolicy:
    topology = _clean_text(
        source.get("topology")
        or source.get("topology_mode")
        or source.get("mode")
        or source.get("topology_type")
    )
    agent_id = _clean_text(
        source.get("agent_id")
        or source.get("active_agent")
        or source.get("parent_agent_id")
    )
    explicit_agent_ids = _string_tuple(source.get("memory_kernel_allowed_agent_ids"))
    allowed_agent_ids = explicit_agent_ids or ((agent_id,) if agent_id else ())
    explicit_scopes = _memory_scope_tuple(source.get("memory_kernel_allowed_scopes"))
    explicit_lanes = _memory_lane_tuple(source.get("memory_kernel_allowed_memory_lanes"))

    should_apply = (
        topology in _LEGACY_TOPOLOGY_MODES
        or bool(explicit_agent_ids)
        or bool(explicit_scopes)
        or bool(explicit_lanes)
    )
    if not should_apply:
        return MemoryKernelIsolationPolicy(
            topology=topology, agent_id=agent_id, semantics="legacy"
        )

    return MemoryKernelIsolationPolicy(
        applied=True,
        topology=topology,
        agent_id=agent_id,
        allowed_agent_ids=allowed_agent_ids,
        allowed_scopes=explicit_scopes or SUPERVISOR_SCOPED.allowed_scopes,
        allowed_memory_lanes=explicit_lanes or SUPERVISOR_SCOPED.allowed_memory_lanes,
        semantics="legacy",
    )


def build_memory_kernel_default_context(
    memory_kernel: Any,
    *,
    recall_query: str,
    token_budget: int,
    isolation_policy: MemoryKernelIsolationPolicy | None = None,
) -> tuple[ContextSection | None, dict[str, Any]]:
    if memory_kernel is None:
        return None, {"status": "not_configured"}

    resolved_isolation = isolation_policy or memory_kernel_isolation_policy_from_metadata(
        None
    )
    isolation_mode = "unrestricted" if isolation_legacy_enabled() else "scoped"
    # Budget construction stays inside the try: a bad token_budget must keep
    # the pre-shadow failure contract (section omitted, status "failed") —
    # never a raise out of the compile.
    try:
        atom_budget = max(4, min(24, int(token_budget) // 100))
        budget = MemoryContextBudget(
            max_candidate_atoms=atom_budget,
            max_admitted_atoms=max(1, min(8, atom_budget)),
            max_total_chars=max(600, min(2400, int(token_budget) * 2)),
            max_atom_chars=420,
            include_content=True,
            require_context_admissible=False,
            allow_projections=False,
            allow_high_risk=False,
            reject_stale=True,
            require_source_digest=True,
            require_source_row_key=True,
            block_tool_exposure=True,
            isolation_mode=isolation_mode,
            allowed_scopes=resolved_isolation.allowed_scopes,
            allowed_agent_ids=resolved_isolation.allowed_agent_ids,
            allowed_memory_lanes=resolved_isolation.allowed_memory_lanes,
            allowed_truth_states=(
                TruthState.OBSERVED,
                TruthState.CLAIMED,
                TruthState.CURATED,
                TruthState.CANONICAL,
            ),
        )
        pack = memory_kernel.preview_memory_pack(
            query=MemoryQuery(
                text_query=recall_query or None,
                limit_total=atom_budget,
                limit_per_surface=atom_budget,
                include_content=True,
                max_canon_risk=None,
                max_pii_risk=None,
                include_high_risk=False,
                include_projections=False,
                include_unsafe=False,
                require_source_digest=True,
                require_source_row_key=True,
            ),
            budget=budget,
        )
    except Exception as exc:
        logger.debug("Memory Kernel default context failed", exc_info=True)
        return None, {
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc)[:240],
        }

    metadata = memory_kernel_pack_metadata(pack)
    metadata["status"] = "used"
    metadata["query_present"] = bool(recall_query)
    metadata["text_query_applied"] = bool(recall_query)
    metadata.update(resolved_isolation.metadata())
    metadata.update(
        _ranked_retrieval_shadow(
            memory_kernel,
            recall_query=recall_query,
            legacy_pack=pack,
            budget=budget,
            top_k=atom_budget,
        )
    )
    return (
        ContextSection(
            name="Memory Kernel",
            priority=4,
            content=format_memory_kernel_pack(pack),
            source_refs=memory_kernel_pack_source_refs(pack),
            metadata=metadata,
        ),
        metadata,
    )


def _ranked_retrieval_shadow(
    memory_kernel: Any,
    *,
    recall_query: str,
    legacy_pack: Any,
    budget: MemoryContextBudget,
    top_k: int,
) -> dict[str, Any]:
    """Run the ranked retrieval door in shadow and record divergence metrics.

    MEMORY_FIRST_TOKEN_SPEC sequencing: shadow -> receipts -> flip. The legacy
    scan keeps serving; this only stamps metadata. Any failure is captured as
    ``shadow_error`` — the shadow must never break bundle compilation.

    ``shadow_overlap_at_k`` is an UNREDACTED-IDENTITY-namespace metric only:
    legacy pack refs are stamped post-redaction (context_admission ``_safe_ref``
    turns any local path into ``<local_path_redacted>``), so file-path-backed
    identities can never match raw candidate paths and overlap deterministically
    under-counts for file-backed atoms. ``legacy_redacted_ref_count`` stamps how
    many legacy refs were blinded that way; PR-04b must not flip on overlap
    numbers alone (see adversarial review #106).
    """

    shadow: dict[str, Any] = {
        "memory_kernel_candidate_source": "legacy_scan+ranked_shadow",
        "shadow_overlap_at_k": None,
        "shadow_admitted_delta": None,
    }
    detail: dict[str, Any] = {"status": "unavailable", "top_k": top_k}
    shadow["ranked_shadow"] = detail

    if not _ranked_shadow_enabled():
        detail["status"] = "disabled"
        detail["reason"] = f"{RANKED_SHADOW_ENV}=0"
        return shadow
    query_door = getattr(memory_kernel, "query", None)
    atoms_door = getattr(memory_kernel, "atoms_for_candidates", None)
    if not callable(query_door) or not callable(atoms_door):
        detail["reason"] = "ranked_door_unavailable"
        return shadow
    if not (recall_query or "").strip():
        detail["status"] = "skipped"
        detail["reason"] = "empty_recall_query"
        return shadow

    shadow_t0 = time.perf_counter()
    try:
        # Shadow flags: skip the engine's own kernel-admission pass (we run
        # admission ourselves via atoms_for_candidates) and skip the sqlite
        # telemetry write — the shadow must not double kernel I/O per compile.
        result = query_door(
            recall_query,
            top_k=top_k,
            enable_memory_kernel=False,
            record_telemetry=False,
        )
        candidates = tuple(getattr(result, "candidates", ()) or ())
        shadow_atoms = tuple(atoms_door(candidates))
        shadow_pack = preview_memory_pack(shadow_atoms, budget=budget)
        legacy_keys, legacy_redacted_ref_count = _legacy_pack_identity_keys(
            legacy_pack
        )
        overlap_count = sum(
            1
            for candidate in candidates
            if _candidate_identity_keys(candidate) & legacy_keys
        )
        detail["status"] = "recorded"
        detail["candidate_count"] = len(candidates)
        detail["shadow_atom_count"] = len(shadow_atoms)
        detail["shadow_admitted_count"] = shadow_pack.admitted_count
        detail["legacy_candidate_count"] = int(
            getattr(legacy_pack, "candidate_count", 0) or 0
        )
        detail["legacy_admitted_count"] = int(
            getattr(legacy_pack, "admitted_count", 0) or 0
        )
        detail["overlap_count"] = overlap_count
        detail["overlap_key_namespace"] = "unredacted_identity_only"
        detail["legacy_identity_key_count"] = len(legacy_keys)
        detail["legacy_redacted_ref_count"] = legacy_redacted_ref_count
        detail["shadow_omission_reason_counts"] = _count_reasons(
            reason
            for item in shadow_pack.items
            if not item.admitted
            for reason in item.omission_reasons
        )
        shadow["shadow_overlap_at_k"] = (
            round(overlap_count / len(candidates), 4) if candidates else 0.0
        )
        shadow["shadow_admitted_delta"] = shadow_pack.admitted_count - int(
            getattr(legacy_pack, "admitted_count", 0) or 0
        )
    except Exception as exc:
        logger.debug("Ranked retrieval shadow failed", exc_info=True)
        detail["status"] = "error"
        shadow_error = f"{type(exc).__name__}: {str(exc)[:200]}"
        detail["shadow_error"] = shadow_error
        shadow["shadow_error"] = shadow_error
    detail["shadow_elapsed_ms"] = round((time.perf_counter() - shadow_t0) * 1000.0, 3)
    return shadow


# Pack items carry post-redaction refs; these sentinels are many-to-one and
# must never become identity keys (they would false-match across atoms).
_REDACTION_SENTINELS = frozenset(
    {"<local_path_redacted>", "<secret_like_redacted>"}
)


def _legacy_pack_identity_keys(pack: Any) -> tuple[set[str], int]:
    """Return (identity keys, count of refs blinded by redaction).

    Only ``atom_id`` is guaranteed pre-redaction; ``content_ref``/``source_refs``
    are post-redaction, so any file-path ref arrives as a sentinel and is
    counted instead of keyed — that count is the overlap metric's stamped
    blind spot.
    """

    keys: set[str] = set()
    redacted_ref_count = 0
    for item in getattr(pack, "items", ()) or ():
        values = (
            getattr(item, "atom_id", ""),
            getattr(item, "content_ref", ""),
            *tuple(getattr(item, "source_refs", ()) or ()),
        )
        for value in values:
            key = _clean_text(value)
            if not key:
                continue
            if key in _REDACTION_SENTINELS or "<local_path_redacted>" in key:
                redacted_ref_count += 1
                continue
            keys.add(key)
    return keys, redacted_ref_count


def _candidate_identity_keys(candidate: Any) -> set[str]:
    values = [
        getattr(candidate, "doc_id", ""),
        getattr(candidate, "source", ""),
    ]
    candidate_metadata = getattr(candidate, "metadata", None) or {}
    if isinstance(candidate_metadata, dict):
        for meta_key in ("atom_id", "source_path", "path"):
            values.append(candidate_metadata.get(meta_key, ""))
    return {key for key in (_clean_text(value) for value in values) if key}


def memory_kernel_pack_metadata(pack: MemoryContextPack) -> dict[str, Any]:
    return {
        "pack_id": pack.pack_id,
        "candidate_count": pack.candidate_count,
        "admitted_count": pack.admitted_count,
        "omitted_count": pack.omitted_count,
        "candidate_truncated": pack.candidate_truncated,
        "warnings": list(pack.warnings),
        "retrieval_telemetry": memory_kernel_retrieval_telemetry(pack),
    }


def memory_kernel_retrieval_telemetry(pack: MemoryContextPack) -> dict[str, Any]:
    admitted = [item for item in pack.items if item.admitted]
    omitted = [item for item in pack.items if not item.admitted]
    return {
        "candidate_count": pack.candidate_count,
        "admitted_count": pack.admitted_count,
        "omitted_count": pack.omitted_count,
        "candidate_truncated": pack.candidate_truncated,
        "admitted_surface_ids": _dedupe(item.surface_id for item in admitted),
        "omitted_surface_ids": _dedupe(item.surface_id for item in omitted),
        "selection_reason_counts": _count_reasons(
            reason for item in admitted for reason in item.selection_reasons
        ),
        "omission_reason_counts": _count_reasons(
            reason for item in omitted for reason in item.omission_reasons
        ),
        "warning_counts": _count_reasons(
            warning for item in pack.items for warning in getattr(item, "warnings", ())
        ),
    }


def memory_kernel_pack_source_refs(pack: MemoryContextPack) -> list[str]:
    refs: list[str] = []
    for item in pack.items:
        if not item.admitted:
            continue
        refs.append(f"memory_kernel:{item.surface_id}")
        refs.extend(item.source_refs)
    return _dedupe(refs)


def format_memory_kernel_pack(pack: MemoryContextPack) -> str:
    lines = [
        f"- pack_id={pack.pack_id}",
        f"- candidates={pack.candidate_count}",
        f"- admitted={pack.admitted_count}",
        f"- omitted={pack.omitted_count}",
    ]
    if pack.warnings:
        lines.append(f"- warnings={', '.join(str(item) for item in pack.warnings)}")

    admitted = [item for item in pack.items if item.admitted]
    if admitted:
        lines.extend(["", "Admitted atoms:"])
        for item in admitted[:8]:
            lines.append(
                "- "
                f"rank={item.rank} surface={item.surface_id} "
                f"type={_enum_value(item.atom_type)} truth={_enum_value(item.truth_state)} "
                f"authority={_enum_value(item.authority_level)}"
            )
            if item.selection_reasons:
                lines.append(f"  reasons={', '.join(item.selection_reasons)}")
            if item.content_snippet:
                lines.append(f"  snippet={_inline_context(item.content_snippet, 420)}")
    else:
        lines.extend(["", "Admitted atoms:", "- none"])

    omitted = [item for item in pack.items if not item.admitted]
    if omitted:
        lines.extend(["", "Omitted atoms:"])
        for item in omitted[:8]:
            lines.append(
                "- "
                f"surface={item.surface_id} type={_enum_value(item.atom_type)} "
                f"truth={_enum_value(item.truth_state)} "
                f"reasons={', '.join(item.omission_reasons)}"
            )
    return "\n".join(lines)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _inline_context(value: str, max_chars: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 14)].rstrip() + "...<truncated>"


def _count_reasons(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value).strip()
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, (list, tuple, set)):
        values = tuple(str(item) for item in value)
    else:
        values = ()
    return tuple(dict.fromkeys(item.strip() for item in values if item.strip()))


def _memory_scope_tuple(value: Any) -> tuple[MemoryScope, ...]:
    scopes: list[MemoryScope] = []
    for item in _string_tuple(value):
        try:
            scopes.append(MemoryScope(item))
        except ValueError:
            logger.debug("Ignoring unknown memory scope in isolation policy: %s", item)
    return tuple(dict.fromkeys(scopes))


def _memory_lane_tuple(value: Any) -> tuple[MemoryLane, ...]:
    lanes: list[MemoryLane] = []
    for item in _string_tuple(value):
        try:
            lanes.append(MemoryLane(item))
        except ValueError:
            logger.debug("Ignoring unknown memory lane in isolation policy: %s", item)
    return tuple(dict.fromkeys(lanes))
