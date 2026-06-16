"""Runtime reader for the Semantic Commons registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from dharma_swarm.engine.knowledge_store import KnowledgeRecord


REPO_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_ROOT = REPO_ROOT / "docs" / "ontology"
ACTIVE_LIFECYCLES = {"seed", "working", "preferred", "canonical"}


def normalize_semantic_text(value: Any) -> str:
    """Normalize display/API/path variants into one comparison key."""
    return re.sub(r"[\s_-]+", " ", str(value or "").lower()).strip()


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text()) or {}
    return payload if isinstance(payload, dict) else {}


def _as_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value if item is not None)
    if value:
        return (str(value),)
    return ()


def _source_matches(record_source: str, expected_source: str) -> bool:
    if not record_source or not expected_source:
        return False
    left = record_source.replace("\\", "/").strip()
    right = expected_source.replace("\\", "/").strip()
    return left == right or left.endswith(f"/{right}") or right.endswith(f"/{left}")


@dataclass(frozen=True, slots=True)
class SemanticObject:
    id: str
    canonical_name: str
    api_name: str
    lifecycle: str
    owner_surface: str
    authority_level: str
    source_path: str
    aliases: tuple[str, ...]
    orientation_route: str


@dataclass(frozen=True, slots=True)
class OrientationLayer:
    id: str
    source_kind: str
    source_paths: tuple[str, ...]
    search_allowed: bool


@dataclass(frozen=True, slots=True)
class RetrievalScope:
    query: str
    canonical_targets: tuple[str, ...] = ()
    matched_aliases: tuple[str, ...] = ()
    orientation_route: str = ""
    orientation_sources: tuple[str, ...] = ()
    exact_sources: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return bool(self.canonical_targets or self.orientation_sources or self.exact_sources)

    def to_evidence(self) -> dict[str, Any]:
        return {
            "structural_scope_first": True,
            "orientation_route": self.orientation_route or "unresolved",
            "canonical_targets": list(self.canonical_targets),
            "matched_aliases": list(self.matched_aliases),
            "orientation_sources": list(self.orientation_sources),
            "exact_sources": list(self.exact_sources),
        }


class SemanticCommons:
    """Read-only Semantic Commons helper for runtime retrieval and routing."""

    def __init__(
        self,
        *,
        objects: list[SemanticObject],
        active_aliases: dict[str, str],
        route_layers: dict[str, list[OrientationLayer]],
    ) -> None:
        self.objects_by_id = {obj.id: obj for obj in objects}
        self.active_aliases = active_aliases
        self.route_layers = route_layers

    @classmethod
    def load(cls, ontology_root: Path = ONTOLOGY_ROOT) -> "SemanticCommons":
        objects_payload = _load_yaml(ontology_root / "semantic_objects.yaml")
        aliases_payload = _load_yaml(ontology_root / "semantic_aliases.yaml")
        orientation_payload = _load_yaml(ontology_root / "session_orientation.yaml")

        objects: list[SemanticObject] = []
        for raw in objects_payload.get("objects", []) or []:
            if not isinstance(raw, dict):
                continue
            objects.append(
                SemanticObject(
                    id=str(raw.get("id", "")),
                    canonical_name=str(raw.get("canonical_name", "")),
                    api_name=str(raw.get("api_name", "")),
                    lifecycle=str(raw.get("lifecycle", "")),
                    owner_surface=str(raw.get("owner_surface", "")),
                    authority_level=str(raw.get("authority_level", "")),
                    source_path=str(raw.get("source_path", "")),
                    aliases=_as_tuple(raw.get("aliases", [])),
                    orientation_route=str(raw.get("orientation_route", "")),
                )
            )

        objects_by_id = {obj.id: obj for obj in objects}
        active_aliases: dict[str, str] = {}
        for obj in objects:
            if obj.lifecycle not in ACTIVE_LIFECYCLES:
                continue
            for alias in obj.aliases + (obj.id, obj.api_name, obj.source_path):
                key = normalize_semantic_text(alias)
                if key:
                    active_aliases[key] = obj.id

        for entry in aliases_payload.get("aliases", []) or []:
            if not isinstance(entry, dict) or entry.get("status") != "active":
                continue
            canonical_id = str(entry.get("canonical_id", ""))
            if canonical_id not in objects_by_id:
                continue
            key = normalize_semantic_text(entry.get("alias", ""))
            if key:
                active_aliases[key] = canonical_id

        route_layers: dict[str, list[OrientationLayer]] = {}
        for route in orientation_payload.get("routes", []) or []:
            if not isinstance(route, dict):
                continue
            route_id = str(route.get("id", ""))
            layers: list[OrientationLayer] = []
            for layer in route.get("layers", []) or []:
                if not isinstance(layer, dict):
                    continue
                layers.append(
                    OrientationLayer(
                        id=str(layer.get("id", "")),
                        source_kind=str(layer.get("source_kind", "")),
                        source_paths=_as_tuple(layer.get("source_paths", [])),
                        search_allowed=bool(layer.get("search_allowed", False)),
                    )
                )
            if route_id:
                route_layers[route_id] = layers

        return cls(
            objects=objects,
            active_aliases=active_aliases,
            route_layers=route_layers,
        )

    def resolve_scope(self, query: str) -> RetrievalScope:
        normalized_query = normalize_semantic_text(query)
        if not normalized_query:
            return RetrievalScope(query=query)

        matched_ids: list[str] = []
        matched_aliases: list[str] = []
        padded_query = f" {normalized_query} "
        for alias_key, canonical_id in self.active_aliases.items():
            if not alias_key:
                continue
            if alias_key == normalized_query or f" {alias_key} " in padded_query:
                if canonical_id not in matched_ids:
                    matched_ids.append(canonical_id)
                if alias_key not in matched_aliases:
                    matched_aliases.append(alias_key)

        matched_objects = [
            self.objects_by_id[obj_id]
            for obj_id in matched_ids
            if obj_id in self.objects_by_id
        ]
        orientation_route = next(
            (obj.orientation_route for obj in matched_objects if obj.orientation_route),
            "",
        )
        orientation_sources: list[str] = []
        for layer in self.route_layers.get(orientation_route, []):
            if layer.id in {"L0", "L1"}:
                orientation_sources.extend(layer.source_paths)

        exact_sources = [
            obj.source_path
            for obj in matched_objects
            if obj.source_path and obj.source_path not in orientation_sources
        ]
        return RetrievalScope(
            query=query,
            canonical_targets=tuple(matched_ids),
            matched_aliases=tuple(matched_aliases),
            orientation_route=orientation_route,
            orientation_sources=tuple(dict.fromkeys(orientation_sources)),
            exact_sources=tuple(dict.fromkeys(exact_sources)),
        )

    def record_source(self, record: KnowledgeRecord) -> str:
        metadata = record.metadata
        return str(
            metadata.get("source_path")
            or metadata.get("source_ref")
            or metadata.get("source")
            or metadata.get("event_id")
            or ""
        )

    def canonical_id_for_record(
        self,
        record: KnowledgeRecord,
        scope: RetrievalScope | None = None,
    ) -> str:
        metadata = record.metadata
        explicit = str(
            metadata.get("canonical_object_id")
            or metadata.get("canonical_target")
            or metadata.get("surface_id")
            or ""
        )
        if explicit in self.objects_by_id:
            return explicit

        source = self.record_source(record)
        for obj in self.objects_by_id.values():
            if _source_matches(source, obj.source_path) or _source_matches(source, obj.owner_surface):
                return obj.id

        if scope and any(_source_matches(source, path) for path in scope.orientation_sources):
            return "semobj.session_orientation"
        return ""

    def structural_score(self, record: KnowledgeRecord, scope: RetrievalScope) -> float:
        if not scope.active:
            return 0.0
        source = self.record_source(record)
        if any(_source_matches(source, path) for path in scope.orientation_sources):
            return 1.0
        return 0.0

    def exact_score(self, query: str, record: KnowledgeRecord, scope: RetrievalScope) -> float:
        if not scope.active:
            return 0.0
        source = self.record_source(record)
        canonical_id = self.canonical_id_for_record(record, scope)
        if canonical_id and canonical_id in scope.canonical_targets:
            return 1.0
        if any(_source_matches(source, path) for path in scope.exact_sources):
            return 0.9
        normalized_query = normalize_semantic_text(query)
        if any(target in normalized_query for target in scope.canonical_targets):
            return 0.6
        return 0.0

    def result_fields(
        self,
        record: KnowledgeRecord,
        scope: RetrievalScope,
        *,
        lane_scores: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        lane_scores = lane_scores or {}
        canonical_id = self.canonical_id_for_record(record, scope)
        obj = self.objects_by_id.get(canonical_id)
        metadata = record.metadata
        source_path = self.record_source(record)
        projection_status = self._projection_status(metadata, source_path)
        retrieval_lane = self._retrieval_lane(lane_scores)
        timestamp = self._timestamp(record)
        return {
            "canonical_target": canonical_id or "unknown",
            "authority_level": (obj.authority_level if obj else metadata.get("authority_level", "unknown")),
            "lifecycle_state": (obj.lifecycle if obj else metadata.get("lifecycle", "unknown")),
            "source_path": source_path or "unknown",
            "projection_canon_status": projection_status,
            "projection_canon_distinction": projection_status,
            "retrieval_lane": retrieval_lane,
            "timestamp": timestamp,
            "freshness_marker": str(metadata.get("stale_valid_until") or f"created_at:{timestamp}"),
            "selection_reason": self._selection_reason(retrieval_lane, canonical_id, scope),
            "repo_worktree_role": str(metadata.get("repo_worktree_role", "current_worktree")),
            "canonical_path": (obj.source_path if obj else source_path or "unknown"),
            "surface_id": canonical_id or source_path or "unknown",
            "review_state": str(metadata.get("review_state", "unreviewed")),
            "stale_valid_until": str(metadata.get("stale_valid_until", "unknown")),
        }

    def _projection_status(self, metadata: dict[str, Any], source_path: str) -> str:
        if (
            metadata.get("generated") is True
            or metadata.get("canon") is False
            or metadata.get("projection_of")
            or "semantic-commons/objects/" in source_path
        ):
            return "projection"
        return "canon"

    def _retrieval_lane(self, lane_scores: dict[str, float]) -> str:
        if lane_scores.get("orientation_route", 0) > 0:
            return "orientation_route"
        if lane_scores.get("exact_match", 0) > 0:
            return "exact_match"
        if lane_scores.get("lexical", 0) > 0:
            return "lexical_bm25_fts"
        if lane_scores.get("semantic", 0) > 0:
            return "vector_search"
        return "fusion"

    def _selection_reason(
        self,
        retrieval_lane: str,
        canonical_id: str,
        scope: RetrievalScope,
    ) -> str:
        if retrieval_lane == "orientation_route":
            return "matched L0/L1 SessionOrientation structural scope before recall"
        if retrieval_lane == "exact_match":
            return f"matched Semantic Commons target {canonical_id or 'unknown'}"
        if scope.active:
            return "ranked inside Semantic Commons structural scope"
        return "ranked by hybrid lexical/vector fusion"

    def _timestamp(self, record: KnowledgeRecord) -> str:
        created_at = record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return created_at.astimezone(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def load_semantic_commons() -> SemanticCommons:
    return SemanticCommons.load()
