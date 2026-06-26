"""Retrieval probe — reconstruct the whole lifecycle chain by correlation_id.

Authoritative, deterministic, no-network: reads the append-only lifecycle
receipt + input receipt + candidate from the state root (the owners), not a
vector projection. Supports four probe handles required by the spec:
correlation_id, source text, candidate title, and semantic route. Each probe
returns the input receipt, candidate, staged/trusted atom refs, memory receipt
ids, proposal/task/bet refs, implementation receipt, and blockers.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schemas import (
    IdeaSparkCandidate,
    OperatorInputLifecycleReceipt,
    OperatorInputReceipt,
)
from .store import (
    load_candidates,
    load_lifecycle_receipt,
    read_input_receipt,
)
from .paths import lifecycle_receipts_dir


@dataclass(frozen=True)
class LifecycleProbeResult:
    retrieval_probe_id: str
    correlation_id: str
    found: bool
    lifecycle: OperatorInputLifecycleReceipt | None = None
    input_receipt: OperatorInputReceipt | None = None
    candidate: IdeaSparkCandidate | None = None
    matched_by: str = ""
    blockers: list[str] = field(default_factory=list)

    def to_summary(self) -> dict[str, Any]:
        lifecycle = self.lifecycle
        return {
            "retrieval_probe_id": self.retrieval_probe_id,
            "correlation_id": self.correlation_id,
            "found": self.found,
            "matched_by": self.matched_by,
            "input_id": lifecycle.input_id if lifecycle else "",
            "candidate_id": lifecycle.candidate_id if lifecycle else "",
            "chetana_staged_atom_id": lifecycle.chetana_staged_atom_id if lifecycle else "",
            "chetana_trusted_atom_id": lifecycle.chetana_trusted_atom_id if lifecycle else "",
            "memory_write_receipt_id": lifecycle.memory_write_receipt_id if lifecycle else "",
            "memory_canonical_receipt_id": lifecycle.memory_canonical_receipt_id if lifecycle else "",
            "semantic_route": lifecycle.semantic_route if lifecycle else "",
            "owner_surface": lifecycle.owner_surface if lifecycle else "",
            "proposal_id": lifecycle.proposal_id if lifecycle else "",
            "task_id": lifecycle.task_id if lifecycle else "",
            "bet_id": lifecycle.bet_id if lifecycle else "",
            "implementation_receipt_id": lifecycle.implementation_receipt_id if lifecycle else "",
            "status": lifecycle.status if lifecycle else "",
            "blockers": list(self.blockers),
        }


def _probe_id(correlation_id: str, mode: str, query: str) -> str:
    digest = hashlib.sha256(f"{correlation_id}|{mode}|{query}".encode("utf-8")).hexdigest()
    return f"probe_{digest[:16]}"


def probe_by_correlation_id(
    correlation_id: str,
    state_root: Path | None = None,
    *,
    matched_by: str = "correlation_id",
    query: str = "",
) -> LifecycleProbeResult:
    """Reconstruct the chain for one correlation_id."""
    lifecycle = load_lifecycle_receipt(correlation_id, state_root)
    probe_id = _probe_id(correlation_id, matched_by, query or correlation_id)
    if lifecycle is None:
        return LifecycleProbeResult(
            retrieval_probe_id=probe_id,
            correlation_id=correlation_id,
            found=False,
            matched_by=matched_by,
            blockers=["lifecycle_receipt_not_found"],
        )
    input_receipt = (
        read_input_receipt(lifecycle.input_id, state_root) if lifecycle.input_id else None
    )
    candidate = None
    if lifecycle.candidate_id:
        for cand in load_candidates(state_root):
            if cand.candidate_id == lifecycle.candidate_id:
                candidate = cand
                break
    return LifecycleProbeResult(
        retrieval_probe_id=probe_id,
        correlation_id=correlation_id,
        found=True,
        lifecycle=lifecycle,
        input_receipt=input_receipt,
        candidate=candidate,
        matched_by=matched_by,
        blockers=list(lifecycle.blockers),
    )


def _correlation_ids(state_root: Path | None) -> list[str]:
    directory = lifecycle_receipts_dir(state_root)
    if not directory.exists():
        return []
    return sorted(path.stem for path in directory.glob("*.json"))


def probe_by_text(
    query: str,
    state_root: Path | None = None,
) -> list[LifecycleProbeResult]:
    """Find lifecycles whose candidate title/claim/source refs contain ``query``."""
    needle = query.strip().lower()
    if not needle:
        return []
    results: list[LifecycleProbeResult] = []
    for candidate in load_candidates(state_root):
        haystack = " ".join(
            [candidate.title, candidate.claim, *candidate.source_refs]
        ).lower()
        if needle in haystack:
            results.append(
                probe_by_correlation_id(
                    candidate.correlation_id, state_root, matched_by="source_text", query=query
                )
            )
    return results


def probe_by_title(
    title: str,
    state_root: Path | None = None,
) -> list[LifecycleProbeResult]:
    needle = title.strip().lower()
    if not needle:
        return []
    results: list[LifecycleProbeResult] = []
    for candidate in load_candidates(state_root):
        if needle in candidate.title.lower():
            results.append(
                probe_by_correlation_id(
                    candidate.correlation_id, state_root, matched_by="candidate_title", query=title
                )
            )
    return results


def probe_by_semantic_route(
    semantic_route: str,
    state_root: Path | None = None,
) -> list[LifecycleProbeResult]:
    needle = semantic_route.strip().lower()
    if not needle:
        return []
    results: list[LifecycleProbeResult] = []
    for correlation_id in _correlation_ids(state_root):
        lifecycle = load_lifecycle_receipt(correlation_id, state_root)
        if lifecycle is None:
            continue
        if needle in lifecycle.semantic_route.lower() or needle in lifecycle.owner_surface.lower():
            results.append(
                probe_by_correlation_id(
                    correlation_id, state_root, matched_by="semantic_route", query=semantic_route
                )
            )
    return results


def retrieve(
    *,
    correlation_id: str | None = None,
    text: str | None = None,
    title: str | None = None,
    semantic_route: str | None = None,
    state_root: Path | None = None,
) -> list[LifecycleProbeResult]:
    """Unified probe across all four handles (de-duplicated by correlation_id)."""
    results: list[LifecycleProbeResult] = []
    seen: set[str] = set()

    def _add(items: list[LifecycleProbeResult]) -> None:
        for item in items:
            if item.found and item.correlation_id not in seen:
                seen.add(item.correlation_id)
                results.append(item)

    if correlation_id:
        _add([probe_by_correlation_id(correlation_id, state_root)])
    if text:
        _add(probe_by_text(text, state_root))
    if title:
        _add(probe_by_title(title, state_root))
    if semantic_route:
        _add(probe_by_semantic_route(semantic_route, state_root))
    return results
