"""Exact read-only adapters from injected canonical owners into Helm context."""
from __future__ import annotations
import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import InitVar, dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
import importlib
import inspect
import re
import threading
from types import MappingProxyType
from typing import Any
from dharma_swarm.helm_route_truth_evaluator import RouteVerification
from dharma_swarm.helm_route_truth_types import MAX_ROUTE_VERIFICATION_TTL
from .helm_context import (
    AuthorityModality, AuthorityStamp, HELM_CONTEXT_REGIONS, HELM_NAVIGATION, MAX_HELM_CONTEXT_COLLECTION_ITEMS, HelmContextEnvelope, HelmContextError, HelmProjection,
    HelmUIState, JsonValue, OperatorActionDescriptor, ProjectionStatus, format_rfc3339, parse_rfc3339, seal_helm_context,
)
_WINDOW = MAX_HELM_CONTEXT_COLLECTION_ITEMS // 2
_OWNER_TYPE_PATHS = {"task_board": ("dharma_swarm.task_board:TaskBoard",), "runtime_state": ("dharma_swarm.runtime_state:RuntimeStateStore",), "session_store": ("dharma_swarm.operator_core.session_store:SessionStore",), "swarm": ("dharma_swarm.swarm:SwarmManager", "dharma_swarm.agent_runner:AgentPool"), "a2a": ("dharma_swarm.a2a.contact_registry:ContactRegistry",), "evolution": ("dharma_swarm.archive:EvolutionArchive",)}
_WORKSPACE_KEYS = {"workspace_path", "workspace", "repository", "repository_identity", "remote", "branch", "head", "upstream", "ahead", "behind", "staged", "unstaged", "untracked"}
_BRIDGE_KEYS = {"bridge_status", "active_session_id", "active_phase", "requested_provider_id", "requested_model_id", "served_provider_id", "served_model_id", "served_identity_source", "served_identity_observed_at", "route_evidence_expires_at", "route_evidence_freshness", "route_receipt_ref", "route_receipt_sha256", "route_verifier_id", "route_verifier_version", "route_evidence_synthetic", "route_verdict", "route_verdict_reason", "route_exact_model_proven", "route_seat_id", "route_verification_evaluated_at"}
_OWNER_NAMES = {"workspace": "TerminalBridge", "bridge_session": "TerminalBridge", "ui": "NihongaShell", "mission_control": "MissionControl", "task_board": "TaskBoard", "runtime_state": "RuntimeStateStore", "session": "SessionStore", "receipts": "RuntimeStateStore", "swarm": "SwarmManager", "a2a": "A2AContactRegistry", "evolution": "EvolutionArchive", "actions": "TerminalBridge"}
_SOURCE_NAMES = {"workspace": "TerminalBridge.workspace_inventory", "bridge_session": "terminal_bridge.session_runtime", "ui": "helm.context.request.ui", "mission_control": "MissionControl.get_snapshot", "task_board": "TaskBoard.list_tasks", "runtime_state": "RuntimeStateStore.read_projection", "session": "SessionStore.list_sessions", "receipts": "RuntimeStateStore.read_recent_receipts", "swarm": "SwarmManager.status", "a2a": "A2AContactRegistry.list_all", "evolution": "EvolutionArchive.list_entries", "actions": "terminal_bridge.action_projection"}
_BRIDGE_SNAPSHOT_AUTHORITY = object()
@dataclass(slots=True)
class HelmContextSources:
    workspace_state: HelmBridgeSnapshot | Mapping[str, Any] | None = None
    bridge_session_state: HelmBridgeSnapshot | Mapping[str, Any] | None = None
    mission_control: object | None = None
    task_board: object | None = None
    runtime_state: object | None = None
    session_store: object | None = None
    swarm: object | None = None
    a2a: object | None = None
    evolution: object | None = None
    operator_actions: Sequence[OperatorActionDescriptor] = ()
    mission_id: str | None = None
@dataclass(frozen=True, slots=True)
class HelmBridgeSnapshot:
    region: str
    data: Mapping[str, Any]
    route_verification: RouteVerification | None = None
    canonical_requested_provider: str | None = None
    _bridge_authority: InitVar[object | None] = None
    def __post_init__(self, _bridge_authority: object | None) -> None:
        if _bridge_authority is not _BRIDGE_SNAPSHOT_AUTHORITY or self.region not in {"workspace", "bridge_session"} or not isinstance(self.data, Mapping) or self.region == "workspace" and (self.route_verification is not None or self.canonical_requested_provider is not None):
            raise HelmContextError("bridge snapshot was not issued by its owner")
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))
def _issue_helm_bridge_snapshot(region: str, data: Mapping[str, Any], route_verification: RouteVerification | None = None, canonical_requested_provider: str | None = None) -> HelmBridgeSnapshot:
    return HelmBridgeSnapshot(region, data, route_verification, canonical_requested_provider, _BRIDGE_SNAPSHOT_AUTHORITY)
def _exact(value: Mapping[str, Any], keys: set[str], label: str) -> None:
    if set(value) != keys:
        raise HelmContextError(f"{label} keys are not exact")
def _field(row: Mapping[str, Any], key: str, kind: type, label: str, nullable: bool = False) -> Any:
    value = row[key]
    if nullable and value is None:
        return None
    if type(value) is not kind or (kind is int and value < 0):
        raise HelmContextError(f"{label}.{key} has invalid type")
    return value
def _timestamp(row: Mapping[str, Any], key: str, label: str, nullable: bool = False) -> None:
    value = _field(row, key, str, label, nullable)
    if value is not None:
        parse_rfc3339(value, field_name=f"{label}.{key}")
def _item_validator(keys: tuple[str, ...], *, ints: tuple[str, ...] = (), nullable: tuple[str, ...] = (), timestamps: tuple[str, ...] = ()) -> Callable[[Mapping[str, Any], str], None]:
    def validate(row: Mapping[str, Any], label: str) -> None:
        _exact(row, set(keys), label)
        for key in keys:
            if key in timestamps:
                _timestamp(row, key, label, key in nullable)
            else:
                _field(row, key, int if key in ints else str, label, key in nullable)
    return validate
_MISSION_ITEM = _item_validator(("mission_id", "title", "status", "updated_at"), nullable=("updated_at",), timestamps=("updated_at",))
_TASK_ITEM = _item_validator(("task_id", "title", "status", "priority", "assigned_to", "depends_on_count", "blocked_by_count", "updated_at"), ints=("depends_on_count", "blocked_by_count"), nullable=("assigned_to",), timestamps=("updated_at",))
_RUNTIME_ITEM = _item_validator(("session_id", "status", "current_task_id", "active_bundle_id", "updated_at", "source_runtime_epoch"), nullable=("current_task_id", "active_bundle_id", "source_runtime_epoch"), timestamps=("updated_at",))
_SESSION_ITEM = _item_validator(("session_id", "status", "title", "provider_id", "model_id", "total_turns", "updated_at", "runtime_owner_id"), ints=("total_turns",), nullable=("updated_at", "runtime_owner_id"), timestamps=("updated_at",))
_RECEIPT_ITEM = _item_validator(("receipt_id", "receipt_type", "status", "run_id", "task_id", "agent_id", "created_at"), timestamps=("created_at",))
_AGENT_ITEM = _item_validator(("agent_id", "name", "role", "status", "current_task", "provider", "model", "last_heartbeat"), nullable=("current_task", "last_heartbeat"), timestamps=("last_heartbeat",))
_CONTACT_ITEM = _item_validator(("agent_uid", "kind", "display_name", "capability_count"), ints=("capability_count",))
_EVOLUTION_ITEM = _item_validator(("entry_id", "timestamp", "parent_id", "component", "change_type", "spec_ref", "commit_hash", "evidence_tier", "promotion_state", "status", "agent_id", "model", "tokens_used", "gates_passed_count", "gates_failed_count"), ints=("tokens_used", "gates_passed_count", "gates_failed_count"), nullable=("parent_id", "spec_ref", "commit_hash"), timestamps=("timestamp",))
def _collection(value: Any, label: str, validator: Callable[[Mapping[str, Any], str], None]) -> None:
    if not isinstance(value, Mapping):
        raise HelmContextError(f"{label} must be an object")
    _exact(value, {"items", "total", "truncated"}, label)
    items = value["items"]
    if not isinstance(items, Sequence) or isinstance(items, str | bytes):
        raise HelmContextError(f"{label}.items must be a list")
    _field(value, "total", int, label)
    _field(value, "truncated", bool, label)
    if value["total"] < len(items) or value["truncated"] is not (value["total"] > len(items)):
        raise HelmContextError(f"{label} collection counts are inconsistent")
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise HelmContextError(f"{label}.items[{index}] must be an object")
        validator(item, f"{label}.items[{index}]")
def _validate_action(row: Mapping[str, Any], label: str) -> None:
    keys = {"action_id", "label", "owner", "effects", "risk", "requires_approval", "reversible", "cancel_action_id"}
    _exact(row, keys, label)
    effects = row["effects"]
    if not isinstance(effects, Sequence) or isinstance(effects, str | bytes):
        raise HelmContextError(f"{label}.effects must be a list")
    action = OperatorActionDescriptor(row["action_id"], row["label"], row["owner"], tuple(effects), row["risk"], row["requires_approval"], row["reversible"], row["cancel_action_id"])
    if row != action.to_dict():
        raise HelmContextError(f"{label} is not canonical")
def validate_helm_region_data(region: str, data: Mapping[str, Any]) -> None:
    label = f"{region}.data"
    if region == "workspace":
        _exact(data, _WORKSPACE_KEYS, label)
        for key in ("workspace_path", "workspace", "repository"):
            _field(data, key, str, label)
        for key in ("repository_identity", "remote", "branch", "head", "upstream"):
            _field(data, key, str, label, True)
        for key in ("ahead", "behind", "staged", "unstaged", "untracked"):
            _field(data, key, int, label, True)
        path = data["workspace_path"]
        if not all(data[key] for key in ("workspace_path", "workspace", "repository")) or not path.startswith("/") or path.endswith("/") or "//" in path or any(part in {".", ".."} for part in path.split("/")) or path.rsplit("/", 1)[-1] != data["workspace"]:
            raise HelmContextError("workspace path is not canonical")
        return
    if region == "bridge_session":
        _exact(data, _BRIDGE_KEYS, label)
        if data["bridge_status"] != "connected":
            raise HelmContextError("bridge status is invalid")
        for key in ("active_session_id", "requested_provider_id", "requested_model_id", "served_provider_id", "served_model_id", "route_receipt_ref", "route_receipt_sha256", "route_verifier_id", "route_verifier_version", "route_seat_id"):
            _field(data, key, str, label, True)
        for key in ("served_identity_observed_at", "route_evidence_expires_at", "route_verification_evaluated_at"):
            _timestamp(data, key, label, True)
        _field(data, "route_evidence_synthetic", bool, label, True)
        _field(data, "route_exact_model_proven", bool, label)
        _field(data, "route_verdict_reason", str, label)
        if data["active_phase"] not in {None, "starting", "streaming", "finalizing", "cancelling", "complete"} or data["active_phase"] is not None and not data["active_session_id"] or data["served_identity_source"] not in {"unavailable", "provider_response_via_route_evaluator"} or data["route_evidence_freshness"] not in {"unavailable", "selected_route_mismatch", "invalid", "expired", "fresh"} or data["route_verdict"] not in {"ON_CALL", "UNKNOWN", "REJECTED", "CLOCK_SKEW"}:
            raise HelmContextError("bridge route enums are invalid")
        requested = (data["requested_provider_id"], data["requested_model_id"])
        identity = (data["served_provider_id"], data["served_model_id"], data["served_identity_observed_at"])
        identifiers = (data["active_session_id"], *requested, data["served_provider_id"], data["served_model_id"], data["route_receipt_ref"], data["route_verifier_id"], data["route_verifier_version"], data["route_seat_id"])
        if any(value == "" for value in identifiers) or not data["route_verdict_reason"]:
            raise HelmContextError("bridge identity contains an empty identifier")
        if sum(value is not None for value in requested) not in {0, 2} or sum(value is not None for value in identity) not in {0, 3}:
            raise HelmContextError("bridge route identity is incomplete")
        has_identity = all(bool(value) for value in identity)
        if (data["served_identity_source"] == "provider_response_via_route_evaluator") != has_identity:
            raise HelmContextError("served identity source is inconsistent")
        evidence_fields = (data["route_evidence_expires_at"], data["route_receipt_ref"], data["route_receipt_sha256"], data["route_verifier_id"], data["route_verifier_version"], data["route_evidence_synthetic"])
        if data["route_receipt_sha256"] is not None and re.fullmatch(r"[0-9a-f]{64}", data["route_receipt_sha256"]) is None:
            raise HelmContextError("route receipt digest is malformed")
        if has_identity and data["route_evidence_freshness"] not in {"fresh", "expired"} or not has_identity and (any(value is not None for value in evidence_fields) or (data["route_seat_id"] is None) != (data["route_verification_evaluated_at"] is None)) or data["route_evidence_freshness"] in {"fresh", "expired"} and (
            not has_identity or not all(value is not None for value in evidence_fields)
            or data["route_seat_id"] is None or data["route_verification_evaluated_at"] is None
        ):
            raise HelmContextError("route evidence is incomplete")
        exact = data["route_exact_model_proven"]
        proven = data["route_verdict"] == "ON_CALL"
        if exact != proven or exact and (
            data["route_evidence_freshness"] != "fresh"
            or data["route_evidence_synthetic"] is not False
            or data["route_verdict_reason"] != "verified"
        ):
            raise HelmContextError("exact route claim lacks evaluator proof")
        return
    if region == "ui":
        _exact(data, {"face", "place", "facet", "overlay", "keyboard_focus", "navigation"}, label)
        ui = HelmUIState(data["face"], data["place"], data["facet"], data["overlay"], data["keyboard_focus"], HELM_NAVIGATION)
        if data != ui.to_dict():
            raise HelmContextError("UI navigation is not canonical")
        return
    if region == "actions":
        _exact(data, {"actions"}, label)
        _collection(data["actions"], f"{label}.actions", _validate_action)
        return
    if region == "mission_control":
        _exact(data, {"mission"}, label)
        if not isinstance(data["mission"], Mapping):
            raise HelmContextError("mission must be an object")
        _MISSION_ITEM(data["mission"], f"{label}.mission")
        return
    collections = {
        "task_board": ("tasks", _TASK_ITEM), "runtime_state": ("sessions", _RUNTIME_ITEM),
        "session": ("sessions", _SESSION_ITEM), "receipts": ("receipts", _RECEIPT_ITEM),
        "a2a": ("contacts", _CONTACT_ITEM), "evolution": ("entries", _EVOLUTION_ITEM),
    }
    if region in collections:
        key, validator = collections[region]
        _exact(data, {key}, label)
        _collection(data[key], f"{label}.{key}", validator)
        return
    if region == "swarm":
        keys = {"agents", "tasks_pending", "tasks_running", "tasks_completed", "tasks_failed", "source_runtime_epoch"}
        _exact(data, keys, label)
        _collection(data["agents"], f"{label}.agents", _AGENT_ITEM)
        for key in ("tasks_pending", "tasks_running", "tasks_completed", "tasks_failed"):
            _field(data, key, int, label)
        _field(data, "source_runtime_epoch", str, label, True)
def validate_helm_region_authority(region: str, status: ProjectionStatus, authority: AuthorityStamp, synthetic: bool) -> None:
    canonical = (_OWNER_NAMES[region], f"{_SOURCE_NAMES[region]}:not_observed" if status is ProjectionStatus.UNAVAILABLE else _SOURCE_NAMES[region])
    allowed = {canonical} if not synthetic or status is ProjectionStatus.UNAVAILABLE else {("SyntheticHelmContextFixture", f"synthetic.{region}")}
    if not synthetic and region == "swarm" and status is not ProjectionStatus.UNAVAILABLE:
        allowed.add(("AgentPool", "AgentPool.list_agents"))
    if (authority.owner, authority.source) not in allowed:
        raise HelmContextError(f"projection {region} authority is not owner-issued")
def validate_helm_region_times(region: str, data: Mapping[str, Any], observed_at: datetime, current_at: datetime | None = None) -> None:
    current_at = current_at or observed_at
    def observation(value: Any, label: str) -> datetime | None:
        if value is None:
            return None
        instant = parse_rfc3339(value, field_name=label)
        if instant > observed_at:
            raise HelmContextError(f"{label} is in the future")
        return instant
    if region == "bridge_session":
        observed = observation(data["served_identity_observed_at"], "served_identity_observed_at")
        evaluated = observation(data["route_verification_evaluated_at"], "route_verification_evaluated_at")
        expiry = parse_rfc3339(data["route_evidence_expires_at"]) if data["route_evidence_expires_at"] else None
        if observed and evaluated and observed > evaluated:
            raise HelmContextError("route evidence follows its evaluation")
        if observed and expiry and (expiry <= observed or expiry - observed > MAX_ROUTE_VERIFICATION_TTL):
            raise HelmContextError("route evidence expiry is inconsistent")
        if data["route_evidence_freshness"] == "fresh" and (expiry is None or expiry <= current_at):
            raise HelmContextError("fresh route evidence is already expired")
        if data["route_evidence_freshness"] == "expired" and (expiry is None or expiry > current_at):
            raise HelmContextError("expired route evidence has not expired")
        return
    if region == "mission_control":
        observation(data["mission"]["updated_at"], "mission.updated_at")
        return
    collection_times = {"task_board": ("tasks", "updated_at"), "runtime_state": ("sessions", "updated_at"), "session": ("sessions", "updated_at"), "receipts": ("receipts", "created_at"), "swarm": ("agents", "last_heartbeat"), "evolution": ("entries", "timestamp")}
    if region in collection_times:
        collection, field = collection_times[region]
        for index, item in enumerate(data[collection]["items"]):
            observation(item[field], f"{region}.{collection}[{index}].{field}")
def _get(row: Any, key: str, default: Any = None) -> Any:
    return row.get(key, default) if isinstance(row, Mapping) else getattr(row, key, default)
def _text(row: Any, key: str, default: str = "", nullable: bool = False) -> str | None:
    value = _get(row, key, None if nullable else default)
    if value is None and nullable:
        return None
    if isinstance(value, Enum):
        value = value.value
    if not isinstance(value, str):
        raise HelmContextError(f"owner field {key} is not text")
    return value
def _integer(row: Any, key: str, default: int = 0) -> int:
    value = _get(row, key, default)
    if type(value) is not int or value < 0:
        raise HelmContextError(f"owner field {key} is not a nonnegative integer")
    return value
def _iso(row: Any, key: str, nullable: bool = False) -> str | None:
    value = _get(row, key)
    if value is None and nullable:
        return None
    if isinstance(value, datetime):
        return format_rfc3339(value)
    if isinstance(value, str):
        return format_rfc3339(parse_rfc3339(value, field_name=key))
    raise HelmContextError(f"owner field {key} is not a timestamp")
def _count(row: Any, key: str) -> int:
    value = _get(row, key, ())
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise HelmContextError(f"owner field {key} is not a sequence")
    return len(value)
def _summaries(rows: Any, serializer: Callable[[Any], dict[str, JsonValue]], newest: bool = False) -> dict[str, JsonValue]:
    if not isinstance(rows, Sequence) or isinstance(rows, str | bytes):
        raise HelmContextError("owner collection is not a sequence")
    selected = rows[-_WINDOW:] if newest else rows[:_WINDOW]
    return {"items": [serializer(row) for row in selected], "total": len(rows), "truncated": len(rows) > len(selected)}
def _mission(row: Any) -> dict[str, JsonValue]:
    source = _get(row, "mission", row)
    return {"mission_id": _text(source, "mission_id", _text(source, "id")), "title": _text(source, "title"), "status": _text(source, "status"), "updated_at": _iso(row, "updated_at", True)}
def _task(row: Any) -> dict[str, JsonValue]:
    return {"task_id": _text(row, "id"), "title": _text(row, "title"), "status": _text(row, "status"), "priority": _text(row, "priority"), "assigned_to": _text(row, "assigned_to", nullable=True), "depends_on_count": _count(row, "depends_on"), "blocked_by_count": _count(row, "blocked_by"), "updated_at": _iso(row, "updated_at")}
def _runtime_session(row: Any) -> dict[str, JsonValue]:
    return {"session_id": _text(row, "session_id"), "status": _text(row, "status"), "current_task_id": _text(row, "current_task_id", nullable=True), "active_bundle_id": _text(row, "active_bundle_id", nullable=True), "updated_at": _iso(row, "updated_at"), "source_runtime_epoch": _text(row, "runtime_epoch", nullable=True)}
def _session(row: Any) -> dict[str, JsonValue]:
    return {"session_id": _text(row, "session_id"), "status": _text(row, "status"), "title": _text(row, "title"), "provider_id": _text(row, "provider_id"), "model_id": _text(row, "model_id"), "total_turns": _integer(row, "total_turns"), "updated_at": _iso(row, "updated_at", True), "runtime_owner_id": _text(row, "runtime_owner_id", nullable=True)}
def _receipt(row: Any) -> dict[str, JsonValue]:
    return {"receipt_id": _text(row, "receipt_id"), "receipt_type": _text(row, "receipt_type"), "status": _text(row, "status"), "run_id": _text(row, "run_id"), "task_id": _text(row, "task_id"), "agent_id": _text(row, "agent_id"), "created_at": _iso(row, "created_at")}
def _agent(row: Any) -> dict[str, JsonValue]:
    return {"agent_id": _text(row, "id", _text(row, "agent_id")), "name": _text(row, "name"), "role": _text(row, "role"), "status": _text(row, "status"), "current_task": _text(row, "current_task", nullable=True), "provider": _text(row, "provider"), "model": _text(row, "model"), "last_heartbeat": _iso(row, "last_heartbeat", True)}
def _contact(row: Any) -> dict[str, JsonValue]:
    return {"agent_uid": _text(row, "agent_uid"), "kind": _text(row, "kind"), "display_name": _text(row, "display_name"), "capability_count": _count(row, "capabilities")}
def _evolution(row: Any) -> dict[str, JsonValue]:
    return {"entry_id": _text(row, "id"), "timestamp": _iso(row, "timestamp"), "parent_id": _text(row, "parent_id", nullable=True), "component": _text(row, "component"), "change_type": _text(row, "change_type"), "spec_ref": _text(row, "spec_ref", nullable=True), "commit_hash": _text(row, "commit_hash", nullable=True), "evidence_tier": _text(row, "evidence_tier"), "promotion_state": _text(row, "promotion_state"), "status": _text(row, "status"), "agent_id": _text(row, "agent_id"), "model": _text(row, "model"), "tokens_used": _integer(row, "tokens_used"), "gates_passed_count": _count(row, "gates_passed"), "gates_failed_count": _count(row, "gates_failed")}
def _canonicalize_sources(sources: HelmContextSources) -> tuple[HelmContextSources, dict[str, str]]:
    rejected: dict[str, str] = {}
    for name, type_paths in _OWNER_TYPE_PATHS.items():
        owner = getattr(sources, name)
        if owner is None:
            continue
        allowed: list[type] = []
        for type_path in type_paths:
            module_name, class_name = type_path.rsplit(":", 1)
            try:
                allowed.append(getattr(importlib.import_module(module_name), class_name))
            except Exception:
                continue
        if not allowed:
            rejected[name] = "owner_type_unavailable"
            continue
        if type(owner) not in tuple(allowed):
            rejected[name] = "noncanonical_owner_rejected"
    if sources.mission_control is not None:
        rejected["mission_control"] = "owner_contract_unavailable_on_stack"
    if sources.runtime_state is not None and "runtime_state" not in rejected:
        rejected["runtime_state"] = "pure_read_projection_unavailable"
    return replace(sources, **{name: None for name in rejected}), rejected
def _bridge_snapshot_data(value: object, runtime_epoch: str, synthetic: bool, region: str) -> Mapping[str, Any]:
    if synthetic:
        if isinstance(value, HelmBridgeSnapshot):
            return value.data
        if isinstance(value, Mapping):
            return value
        raise HelmContextError("synthetic bridge state must be an object")
    if type(value) is not HelmBridgeSnapshot or value.region != region:
        raise HelmContextError("production bridge state must be bridge-issued")
    data = value.data
    if region == "workspace":
        return data
    if data.get("route_exact_model_proven") is not True:
        return data
    from dharma_swarm.helm_route_truth_types import RouteVerdict, SanitizedRouteEvidence
    proof = value.route_verification
    if type(proof) is not RouteVerification or proof.verdict is not RouteVerdict.ON_CALL:
        raise HelmContextError("exact route state lacks evaluator-issued proof")
    evidence = proof.evidence
    if type(evidence) is not SanitizedRouteEvidence:
        raise HelmContextError("exact route state lacks sanitized evidence")
    expected = {
        "requested_model_id": evidence.requested_model, "served_provider_id": evidence.served_provider,
        "served_model_id": evidence.served_model, "served_identity_source": "provider_response_via_route_evaluator",
        "served_identity_observed_at": format_rfc3339(evidence.observed_at), "route_evidence_expires_at": format_rfc3339(evidence.expires_at),
        "route_receipt_ref": evidence.receipt_ref, "route_receipt_sha256": evidence.receipt_sha256,
        "route_verifier_id": evidence.verifier_id, "route_verifier_version": evidence.verifier_version,
        "route_evidence_synthetic": False, "route_verdict": "ON_CALL", "route_verdict_reason": proof.reason,
        "route_seat_id": proof.seat_id, "route_verification_evaluated_at": format_rfc3339(proof.evaluated_at),
    }
    if proof.runtime_epoch != runtime_epoch or evidence.runtime_epoch != runtime_epoch:
        raise HelmContextError("exact route proof has a runtime epoch mismatch")
    if value.canonical_requested_provider != evidence.requested_provider:
        raise HelmContextError("requested provider diverges from evaluator proof")
    if any(data.get(key) != expected_value for key, expected_value in expected.items()):
        raise HelmContextError("exact route state diverges from evaluator proof")
    return data
def _owner_observed(value: Any, fallback: datetime) -> datetime:
    for key in ("observed_at", "updated_at", "timestamp"):
        present = key in value if isinstance(value, Mapping) else hasattr(value, key)
        if not present:
            continue
        candidate = _get(value, key)
        if isinstance(candidate, str):
            return parse_rfc3339(candidate, field_name=f"owner.{key}")
        if not isinstance(candidate, datetime) or candidate.tzinfo is None or candidate.utcoffset() is None:
            raise HelmContextError("owner observation timestamp is malformed")
        return candidate.astimezone(timezone.utc)
    return fallback
def _owner_epoch(owner: Any, value: Any) -> str | None:
    for source, key in ((value, "runtime_epoch"), (owner, "runtime_epoch"), (owner, "_runtime_owner_id")):
        candidate = _get(source, key)
        if candidate is not None:
            if not isinstance(candidate, str) or not candidate:
                raise HelmContextError("owner runtime epoch is malformed")
            return candidate
    return None
async def run_bounded_sync(function: Callable[..., Any], *args: Any, timeout: float = 2.0, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    completed = threading.Event()
    outcome: list[tuple[Any, BaseException | None]] = []
    def invoke() -> None:
        try:
            result, error = function(*args, **kwargs), None
        except BaseException as exc:  # propagate owner failure without its text
            result, error = None, exc
        outcome.append((result, error))
        completed.set()
    threading.Thread(target=invoke, name="helm-context-read", daemon=True).start()
    deadline = loop.time() + timeout
    while not completed.is_set():
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise TimeoutError("bounded owner read timed out")
        await asyncio.sleep(min(0.005, remaining))
    result, error = outcome[0]
    if error is not None:
        raise error
    return result
async def _call(owner: Any, method: str, *args: Any, **kwargs: Any) -> Any:
    descriptor = inspect.getattr_static(type(owner), method, None)
    function = descriptor.__get__(owner, type(owner)) if hasattr(descriptor, "__get__") else descriptor
    if not callable(function):
        raise HelmContextError("owner read method unavailable")
    if inspect.iscoroutinefunction(function):
        return await asyncio.wait_for(function(*args, **kwargs), timeout=2.0)
    result = await run_bounded_sync(function, *args, **kwargs)
    return await asyncio.wait_for(result, timeout=2.0) if inspect.isawaitable(result) else result
def _stamp(region: str, status: ProjectionStatus, now: datetime, expiry: datetime | None, epoch: str, synthetic: bool = False, source: str | None = None, owner: str | None = None) -> AuthorityStamp:
    return AuthorityStamp(AuthorityModality(status.value), owner or ("SyntheticHelmContextFixture" if synthetic else _OWNER_NAMES[region]), source or (f"synthetic.{region}" if synthetic else _SOURCE_NAMES[region]), format_rfc3339(now), format_rfc3339(expiry) if expiry else None, epoch)
def _unavailable(region: str, now: datetime, epoch: str, reason: str) -> HelmProjection:
    authority = AuthorityStamp(AuthorityModality.UNKNOWN, _OWNER_NAMES[region], f"{_SOURCE_NAMES[region]}:not_observed", format_rfc3339(now), None, epoch)
    return HelmProjection(region, ProjectionStatus.UNAVAILABLE, authority, {}, reason)
def _available(region: str, data: Mapping[str, Any], now: datetime, ttl: timedelta, epoch: str, synthetic: bool = False, status: ProjectionStatus = ProjectionStatus.OBSERVED, source_epoch: str | None = None, source: str | None = None, owner: str | None = None) -> HelmProjection:
    actual_status = ProjectionStatus.CONFIGURED if synthetic else status
    actual_epoch = epoch if synthetic or actual_status is ProjectionStatus.CONFIGURED else source_epoch or ("unknown" if actual_status is ProjectionStatus.UNVERIFIED else epoch)
    if actual_status is ProjectionStatus.OBSERVED and actual_epoch != epoch:
        actual_status = ProjectionStatus.UNVERIFIED
    return HelmProjection(region, actual_status, _stamp(region, actual_status, now, now + ttl, actual_epoch, synthetic, source, owner), data)
async def _project_owners(sources: HelmContextSources, now: datetime, ttl: timedelta, epoch: str, synthetic: bool, clock: Callable[[], datetime]) -> list[HelmProjection]:
    output: list[HelmProjection] = []
    async def read(region: str, owner: Any, method: str, serializer: Callable[[Any], Mapping[str, Any]], *args: Any, status: ProjectionStatus = ProjectionStatus.OBSERVED, authority_owner: str | None = None, authority_source: str | None = None, **kwargs: Any) -> None:
        if owner is None:
            output.append(_unavailable(region, now, epoch, "owner_not_injected"))
            return
        try:
            value = await _call(owner, method, *args, **kwargs)
            read_now = clock()
            owner_observed = _owner_observed(value, read_now)
            if owner_observed > read_now:
                output.append(_unavailable(region, now, epoch, "owner_observation_in_future"))
                return
            effective = ProjectionStatus.STALE if status is ProjectionStatus.OBSERVED and owner_observed + ttl <= read_now else status
            stamp_time = read_now if synthetic else owner_observed
            data = serializer(value)
            validate_helm_region_times(region, data, stamp_time)
            output.append(_available(region, data, stamp_time, ttl, epoch, synthetic, effective, _owner_epoch(owner, value), authority_source, authority_owner))
        except HelmContextError:
            output.append(_unavailable(region, now, epoch, "owner_projection_invalid"))
        except Exception:
            output.append(_unavailable(region, now, epoch, "owner_read_or_projection_failed"))
    if sources.mission_control is None or not sources.mission_id:
        output.append(_unavailable("mission_control", now, epoch, "owner_not_injected" if sources.mission_control is None else "mission_not_selected"))
    else:
        await read("mission_control", sources.mission_control, "get_snapshot", lambda value: {"mission": _mission(value)}, sources.mission_id)
    if synthetic:
        await read("task_board", sources.task_board, "list_tasks", lambda value: {"tasks": _summaries(value, _task)}, limit=32)
    else:
        output.append(_unavailable("task_board", now, epoch, "pure_read_projection_unavailable"))
    if synthetic:
        await read("runtime_state", sources.runtime_state, "list_sessions_sync", lambda value: {"sessions": _summaries(value, _runtime_session)}, limit=32)
    else:
        output.append(_unavailable("runtime_state", now, epoch, "pure_read_projection_unavailable"))
    await read("session", sources.session_store, "list_sessions", lambda value: {"sessions": _summaries(value, _session, True)})
    if synthetic:
        await read("receipts", sources.runtime_state, "list_runtime_receipts", lambda value: {"receipts": _summaries(value, _receipt, True)}, limit=32)
    else:
        output.append(_unavailable("receipts", now, epoch, "recent_receipt_projection_unavailable"))
    if sources.swarm is None:
        output.append(_unavailable("swarm", now, epoch, "owner_not_injected"))
    elif not callable(getattr(type(sources.swarm), "status", None)):
        await read("swarm", sources.swarm, "list_agents", lambda value: {"agents": _summaries(value, _agent), "tasks_pending": 0, "tasks_running": 0, "tasks_completed": 0, "tasks_failed": 0, "source_runtime_epoch": None}, status=ProjectionStatus.UNVERIFIED, authority_owner="AgentPool", authority_source="AgentPool.list_agents")
    else:
        await read("swarm", sources.swarm, "status", lambda value: {"agents": _summaries(_get(value, "agents", ()), _agent), "tasks_pending": _integer(value, "tasks_pending"), "tasks_running": _integer(value, "tasks_running"), "tasks_completed": _integer(value, "tasks_completed"), "tasks_failed": _integer(value, "tasks_failed"), "source_runtime_epoch": _text(value, "runtime_epoch", nullable=True)}, status=ProjectionStatus.UNVERIFIED)
    await read("a2a", sources.a2a, "list_all", lambda value: {"contacts": _summaries(value, _contact)}, status=ProjectionStatus.CONFIGURED)
    await read("evolution", sources.evolution, "list_entries", lambda value: {"entries": _summaries(value, _evolution, True)})
    return output
async def build_helm_context(sources: HelmContextSources, *, ui: HelmUIState, runtime_epoch: str, now: datetime | None = None, ttl_seconds: int = 60, synthetic: bool = False, advance_clock: bool = False) -> HelmContextEnvelope:
    if not isinstance(sources, HelmContextSources) or not isinstance(ui, HelmUIState) or type(synthetic) is not bool or type(advance_clock) is not bool:
        raise HelmContextError("builder inputs are not typed")
    if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 3_600:
        raise HelmContextError("ttl_seconds must be between 1 and 3600")
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise HelmContextError("now must be timezone-aware")
    observed, ttl = observed.astimezone(timezone.utc), timedelta(seconds=ttl_seconds)
    started = asyncio.get_running_loop().time()
    def clock() -> datetime:
        return observed + timedelta(seconds=asyncio.get_running_loop().time() - started) if advance_clock or now is None else observed
    rejected: dict[str, str] = {}
    if not synthetic:
        sources, rejected = _canonicalize_sources(sources)
    projections: list[HelmProjection] = []
    for region, data, status in (("workspace", sources.workspace_state, ProjectionStatus.OBSERVED), ("bridge_session", sources.bridge_session_state, ProjectionStatus.OBSERVED), ("ui", ui.to_dict(), ProjectionStatus.CONFIGURED)):
        if data is None:
            projections.append(_unavailable(region, observed, runtime_epoch, f"{region}_projection_unavailable"))
        else:
            try:
                if region in {"workspace", "bridge_session"}:
                    data = _bridge_snapshot_data(data, runtime_epoch, synthetic, region)
                validate_helm_region_times(region, data, observed)
                projections.append(_available(region, data, observed, ttl, runtime_epoch, synthetic, status))
            except HelmContextError:
                projections.append(_unavailable(region, observed, runtime_epoch, "projection_invalid"))
    projections.extend(await _project_owners(sources, observed, ttl, runtime_epoch, synthetic, clock))
    actions = {"actions": {"items": [item.to_dict() for item in sources.operator_actions], "total": len(sources.operator_actions), "truncated": False}} if synthetic else None
    projections.append(_available("actions", actions, observed, ttl, runtime_epoch, True, ProjectionStatus.CONFIGURED) if actions is not None else _unavailable("actions", observed, runtime_epoch, "action_evaluator_not_integrated"))
    by_region = {projection.region: projection for projection in projections}
    affected = {"mission_control": ("mission_control",), "task_board": ("task_board",), "runtime_state": ("runtime_state", "receipts"), "session_store": ("session",), "swarm": ("swarm",), "a2a": ("a2a",), "evolution": ("evolution",)}
    for field, reason in rejected.items():
        for region in affected[field]:
            by_region[region] = _unavailable(region, observed, runtime_epoch, reason)
    if tuple(by_region) != HELM_CONTEXT_REGIONS:
        raise HelmContextError("builder projection order diverged from schema")
    generated = clock()
    return seal_helm_context(HelmContextEnvelope("dharma.helm.context.v1", format_rfc3339(generated), format_rfc3339(generated + ttl), runtime_epoch, synthetic, by_region))
