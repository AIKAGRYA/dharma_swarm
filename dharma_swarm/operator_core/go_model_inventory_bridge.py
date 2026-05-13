"""Read-only bridge for local model inventory receipts emitted by Go.

This module parses aggregate receipts produced by
``tools/local_model_inventory_go`` and exposes typed views over runtime
reachability, discovered model IDs, binary presence, and summary counts. It
does not write canonical state, make routing decisions, mutate ontology or
runtime databases, or import decision surfaces.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GO_EVIDENCE_SCHEMA_V0 = "go_evidence_receipt.v0"
LOCAL_MODEL_INVENTORY_SCHEMA_V0 = "local_model_inventory.v0"
LOCAL_MODEL_INVENTORY_SCHEMA_V1 = "local_model_inventory.v1"
SUPPORTED_LOCAL_MODEL_INVENTORY_SCHEMAS = {
    LOCAL_MODEL_INVENTORY_SCHEMA_V0,
    LOCAL_MODEL_INVENTORY_SCHEMA_V1,
}
LOCAL_MODEL_INVENTORY_SOURCE = "local_model_inventory_go"
LOCAL_MODEL_INVENTORY_SOURCE_URL = "local://model-runtime-inventory"


class GoModelInventoryBridgeError(ValueError):
    """Raised when a Go local-model inventory receipt cannot be parsed."""


@dataclass(frozen=True)
class ProbePolicy:
    loopback_only: bool
    timeout_ms: int
    external_network: bool
    allowed_hosts: tuple[str, ...]


@dataclass(frozen=True)
class HostInfo:
    goos: str
    goarch: str


@dataclass(frozen=True)
class BinaryPresence:
    name: str
    present: bool
    path: str = ""


@dataclass(frozen=True)
class EnvironmentFact:
    name: str
    present: bool
    value_class: str


@dataclass(frozen=True)
class DiscoveredModel:
    id: str


@dataclass(frozen=True)
class RuntimeExposure:
    loopback_url: bool
    remote_host_observed: bool = False
    remote_host_class: str = ""
    cloud_offload_observed: bool = False
    cloud_offload_enabled: bool = False
    auth_observed: bool = False
    telemetry_observed: bool = False
    license_observed: bool = False


@dataclass(frozen=True)
class RuntimeInventory:
    name: str
    kind: str
    url: str
    reachable: bool
    status_code: int | None
    models: tuple[DiscoveredModel, ...]
    exposure: RuntimeExposure
    error: str = ""


@dataclass(frozen=True)
class InventorySummary:
    runtime_count: int
    reachable_count: int
    model_count: int
    rejected_count: int


@dataclass(frozen=True)
class RuntimeRejection:
    name: str
    url: str
    reason: str


@dataclass(frozen=True)
class LocalModelInventoryPayload:
    inventory_schema: str
    probe_policy: ProbePolicy
    host: HostInfo
    binaries: tuple[BinaryPresence, ...]
    environment: tuple[EnvironmentFact, ...]
    runtimes: tuple[RuntimeInventory, ...]
    summary: InventorySummary
    rejections: tuple[RuntimeRejection, ...] = ()

    def __post_init__(self) -> None:
        if self.inventory_schema not in SUPPORTED_LOCAL_MODEL_INVENTORY_SCHEMAS:
            raise GoModelInventoryBridgeError(
                f"unsupported local model inventory schema: {self.inventory_schema}"
            )
        if not self.probe_policy.loopback_only:
            raise GoModelInventoryBridgeError("inventory receipt must be loopback-only")
        if self.probe_policy.external_network:
            raise GoModelInventoryBridgeError("inventory receipt must not use external network")


@dataclass(frozen=True)
class GoModelInventoryReceipt:
    receipt_id: str
    correlation_id: str
    source: str
    source_url: str
    observed_at: str
    content_hash: str
    event_uid: str
    schema_version: str
    status: str
    payload: LocalModelInventoryPayload
    rejected_reason: str = ""

    def __post_init__(self) -> None:
        required = (
            self.receipt_id,
            self.correlation_id,
            self.source,
            self.source_url,
            self.observed_at,
            self.content_hash,
            self.event_uid,
            self.schema_version,
            self.status,
        )
        if not all(required):
            raise GoModelInventoryBridgeError(
                "GoModelInventoryReceipt missing required identity fields"
            )
        if self.schema_version != GO_EVIDENCE_SCHEMA_V0:
            raise GoModelInventoryBridgeError(
                f"unsupported Go evidence schema: {self.schema_version}"
            )
        if self.source != LOCAL_MODEL_INVENTORY_SOURCE:
            raise GoModelInventoryBridgeError(f"unsupported receipt source: {self.source}")
        if self.source_url != LOCAL_MODEL_INVENTORY_SOURCE_URL:
            raise GoModelInventoryBridgeError(
                f"unsupported receipt source_url: {self.source_url}"
            )
        if self.status not in {"accepted", "rejected"}:
            raise GoModelInventoryBridgeError(f"unsupported receipt status: {self.status}")
        if self.status == "rejected" and not self.rejected_reason:
            raise GoModelInventoryBridgeError("rejected receipt must carry rejected_reason")

    @property
    def reachable_runtimes(self) -> tuple[RuntimeInventory, ...]:
        return tuple(runtime for runtime in self.payload.runtimes if runtime.reachable)

    @property
    def discovered_models(self) -> tuple[DiscoveredModel, ...]:
        models: list[DiscoveredModel] = []
        for runtime in self.payload.runtimes:
            models.extend(runtime.models)
        return tuple(models)

    @property
    def present_binaries(self) -> tuple[BinaryPresence, ...]:
        return tuple(binary for binary in self.payload.binaries if binary.present)

    @property
    def present_environment(self) -> tuple[EnvironmentFact, ...]:
        return tuple(env for env in self.payload.environment if env.present)


def load_go_model_inventory_receipt(path: Path) -> GoModelInventoryReceipt:
    """Read a JSON receipt produced by local_model_inventory_go."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise GoModelInventoryBridgeError(
            "Go model inventory receipt payload must be a JSON object"
        )
    return GoModelInventoryReceipt(
        receipt_id=str(raw.get("receipt_id", "")),
        correlation_id=str(raw.get("correlation_id", "")),
        source=str(raw.get("source", "")),
        source_url=str(raw.get("source_url", "")),
        observed_at=str(raw.get("observed_at", "")),
        content_hash=str(raw.get("content_hash", "")),
        event_uid=str(raw.get("event_uid", "")),
        schema_version=str(raw.get("schema_version", "")),
        status=str(raw.get("status", "")),
        rejected_reason=str(raw.get("rejected_reason", "")),
        payload=_parse_payload(payload),
    )


def _parse_payload(raw: dict[str, Any]) -> LocalModelInventoryPayload:
    return LocalModelInventoryPayload(
        inventory_schema=str(raw.get("inventory_schema", "")),
        probe_policy=_parse_probe_policy(_dict(raw.get("probe_policy"), "probe_policy")),
        host=_parse_host(_dict(raw.get("host"), "host")),
        binaries=tuple(_parse_binary(item) for item in _list(raw.get("binaries"), "binaries")),
        environment=tuple(
            _parse_environment(item)
            for item in _list(raw.get("environment", []), "environment")
        ),
        runtimes=tuple(_parse_runtime(item) for item in _list(raw.get("runtimes"), "runtimes")),
        summary=_parse_summary(_dict(raw.get("summary"), "summary")),
        rejections=tuple(
            _parse_rejection(item) for item in _list(raw.get("rejections", []), "rejections")
        ),
    )


def _parse_probe_policy(raw: dict[str, Any]) -> ProbePolicy:
    return ProbePolicy(
        loopback_only=bool(raw.get("loopback_only")),
        timeout_ms=int(raw.get("timeout_ms", 0)),
        external_network=bool(raw.get("external_network")),
        allowed_hosts=tuple(str(item) for item in _list(raw.get("allowed_hosts"), "allowed_hosts")),
    )


def _parse_host(raw: dict[str, Any]) -> HostInfo:
    return HostInfo(goos=str(raw.get("goos", "")), goarch=str(raw.get("goarch", "")))


def _parse_binary(raw: Any) -> BinaryPresence:
    item = _dict(raw, "binary")
    return BinaryPresence(
        name=str(item.get("name", "")),
        present=bool(item.get("present")),
        path=str(item.get("path", "")),
    )


def _parse_environment(raw: Any) -> EnvironmentFact:
    item = _dict(raw, "environment")
    return EnvironmentFact(
        name=str(item.get("name", "")),
        present=bool(item.get("present")),
        value_class=str(item.get("value_class", "")),
    )


def _parse_runtime(raw: Any) -> RuntimeInventory:
    item = _dict(raw, "runtime")
    status = item.get("status_code")
    return RuntimeInventory(
        name=str(item.get("name", "")),
        kind=str(item.get("kind", "")),
        url=str(item.get("url", "")),
        reachable=bool(item.get("reachable")),
        status_code=int(status) if status is not None else None,
        models=tuple(_parse_model(model) for model in _list(item.get("models"), "models")),
        exposure=_parse_exposure(_dict(item.get("exposure", {}), "exposure")),
        error=str(item.get("error", "")),
    )


def _parse_exposure(raw: dict[str, Any]) -> RuntimeExposure:
    return RuntimeExposure(
        loopback_url=bool(raw.get("loopback_url")),
        remote_host_observed=bool(raw.get("remote_host_observed")),
        remote_host_class=str(raw.get("remote_host_class", "")),
        cloud_offload_observed=bool(raw.get("cloud_offload_observed")),
        cloud_offload_enabled=bool(raw.get("cloud_offload_enabled")),
        auth_observed=bool(raw.get("auth_observed")),
        telemetry_observed=bool(raw.get("telemetry_observed")),
        license_observed=bool(raw.get("license_observed")),
    )


def _parse_model(raw: Any) -> DiscoveredModel:
    item = _dict(raw, "model")
    return DiscoveredModel(id=str(item.get("id", "")))


def _parse_summary(raw: dict[str, Any]) -> InventorySummary:
    return InventorySummary(
        runtime_count=int(raw.get("runtime_count", 0)),
        reachable_count=int(raw.get("reachable_count", 0)),
        model_count=int(raw.get("model_count", 0)),
        rejected_count=int(raw.get("rejected_count", 0)),
    )


def _parse_rejection(raw: Any) -> RuntimeRejection:
    item = _dict(raw, "rejection")
    return RuntimeRejection(
        name=str(item.get("name", "")),
        url=str(item.get("url", "")),
        reason=str(item.get("reason", "")),
    )


def _dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GoModelInventoryBridgeError(f"{field} must be a JSON object")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise GoModelInventoryBridgeError(f"{field} must be a JSON array")
    return value
