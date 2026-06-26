"""Candidate -> Semantic Commons owner-surface routing (fail-closed).

Pure consumer of the existing Semantic Commons reader (the naming/identity
SSOT). Resolves a candidate's domain/title/claim text to a canonical object and
its owner surface; persists ``owner_surface``, ``authority_level``, and
``semantic_route`` on the candidate and a routing receipt. When nothing
resolves, it FAILS CLOSED: routing_status becomes ``blocked`` with an explicit
``semantic_commons_unresolved`` marker rather than guessing an owner.

This adds no parallel naming scheme and never mutates the ontology
(``docs/ontology/`` is owned by the agent-admission-semantic-commons track).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dharma_swarm.semantic_commons import (
    SemanticCommons,
    load_semantic_commons,
    normalize_semantic_text,
)

from .paths import routing_receipt_path, routing_receipts_dir
from .schemas import IdeaSparkCandidate, utc_now_iso
from .store import append_candidate, update_lifecycle_receipt

ROUTING_RECEIPT_SCHEMA = "idea_spark_routing_receipt.v0"
UNRESOLVED_MARKER = "semantic_commons_unresolved"


@dataclass(frozen=True)
class SemanticRoute:
    correlation_id: str
    candidate_id: str
    resolved: bool
    canonical_target: str
    owner_surface: str
    lifecycle: str
    authority_level: str
    semantic_route: str
    matched_aliases: tuple[str, ...]
    evidence: dict[str, Any]
    blocker: str
    created_at: str = field(default_factory=utc_now_iso)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ROUTING_RECEIPT_SCHEMA,
            "correlation_id": self.correlation_id,
            "candidate_id": self.candidate_id,
            "resolved": self.resolved,
            "canonical_target": self.canonical_target,
            "owner_surface": self.owner_surface,
            "lifecycle": self.lifecycle,
            "authority_level": self.authority_level,
            "semantic_route": self.semantic_route,
            "matched_aliases": list(self.matched_aliases),
            "evidence": self.evidence,
            "blocker": self.blocker,
            "created_at": self.created_at,
        }


def _resolution_text(candidate: IdeaSparkCandidate) -> str:
    return " ".join(
        part for part in (candidate.domain, candidate.title, candidate.claim) if part
    ).strip()


def resolve_owner(
    candidate: IdeaSparkCandidate,
    commons: SemanticCommons,
    *,
    created_at: str | None = None,
) -> SemanticRoute:
    """Resolve a candidate to a canonical owner surface (no persistence)."""
    scope = commons.resolve_scope(_resolution_text(candidate))
    canonical_target = scope.canonical_targets[0] if scope.canonical_targets else ""
    if not canonical_target:
        # Exact-alias fallback on the narrow domain/title fields.
        for value in (candidate.domain, candidate.title):
            cid = commons.active_aliases.get(normalize_semantic_text(value))
            if cid:
                canonical_target = cid
                break

    obj = commons.objects_by_id.get(canonical_target) if canonical_target else None
    owner_surface = obj.owner_surface if obj else ""
    lifecycle = obj.lifecycle if obj else ""
    semantic_route = (obj.orientation_route if obj and obj.orientation_route else canonical_target)
    resolved = bool(owner_surface)
    blocker = "" if resolved else UNRESOLVED_MARKER

    return SemanticRoute(
        correlation_id=candidate.correlation_id,
        candidate_id=candidate.candidate_id,
        resolved=resolved,
        canonical_target=canonical_target,
        owner_surface=owner_surface,
        lifecycle=lifecycle,
        authority_level=candidate.authority_level,
        semantic_route=semantic_route,
        matched_aliases=scope.matched_aliases,
        evidence=scope.to_evidence(),
        blocker=blocker,
        created_at=created_at or utc_now_iso(),
    )


def _write_routing_receipt(route: SemanticRoute, state_root: Path | None) -> Path:
    routing_receipts_dir(state_root, ensure=True)
    path = routing_receipt_path(route.correlation_id, state_root)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(route.to_json_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def route_candidate(
    candidate: IdeaSparkCandidate,
    *,
    commons: SemanticCommons | None = None,
    state_root: Path | None = None,
    created_at: str | None = None,
    persist: bool = True,
) -> tuple[SemanticRoute, IdeaSparkCandidate]:
    """Route a candidate, persist the receipt + updated candidate + lifecycle."""
    resolver = commons or load_semantic_commons()
    route = resolve_owner(candidate, resolver, created_at=created_at)

    updated = candidate.model_copy(
        update={
            "owner_surface": route.owner_surface,
            "routing_status": "routed" if route.resolved else "blocked",
        }
    )

    if persist:
        _write_routing_receipt(route, state_root)
        append_candidate(updated, state_root)
        if route.resolved:
            update_lifecycle_receipt(
                candidate.correlation_id,
                state_root,
                status="routed",
                candidate_id=candidate.candidate_id,
                semantic_route=route.semantic_route,
                owner_surface=route.owner_surface,
            )
        else:
            update_lifecycle_receipt(
                candidate.correlation_id,
                state_root,
                candidate_id=candidate.candidate_id,
                blockers=[UNRESOLVED_MARKER],
            )

    return route, updated
