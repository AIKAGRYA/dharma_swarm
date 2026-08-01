"""Ranked governed-retrieval shadow for the default Memory Kernel context.

Split out of ``default_context.py`` (which owns the serving compile path) the
same way ``topology_policy.py`` was: this module only runs the ranked door in
shadow and stamps divergence receipts into bundle metadata. Nothing here
reaches prompt content.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Iterable

from dharma_swarm.memory_kernel.context_admission import (
    MemoryContextBudget,
    preview_memory_pack,
)

logger = logging.getLogger(__name__)


# Ops kill switch for the ranked retrieval shadow. Default ON (the shadow
# phase exists to collect receipts); set to 0 only if shadow latency pushes
# bundle compiles toward the orchestrator timeout.
RANKED_SHADOW_ENV = "DHARMA_MEMORY_KERNEL_RANKED_SHADOW"


def ranked_shadow_enabled() -> bool:
    raw = os.environ.get(RANKED_SHADOW_ENV, "1")
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def ranked_retrieval_shadow(
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

    if not ranked_shadow_enabled():
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
        detail["shadow_omission_reason_counts"] = count_reasons(
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
            key = clean_text(value)
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
    return {key for key in (clean_text(value) for value in values) if key}


def count_reasons(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value).strip()
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def clean_text(value: Any) -> str:
    return str(value or "").strip()
