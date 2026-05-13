"""Read-only bridge for Go source-inventory receipts.

This module parses aggregate receipts emitted by the bounded source mouths:

* ``tools/security_advisory_ingestor_go``
* ``tools/ai_frontier_ingestor_go``
* ``tools/agent_infra_ingestor_go``
* ``tools/practitioner_signal_ingestor_go``

It exposes typed views over configured sources, reachability metadata, body
hashes, and trust envelope fields. It does not write canonical state, create
WorkPackets, dispatch agents, mutate ontology/runtime databases, or summarize
social/commentary content into routing facts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GO_EVIDENCE_SCHEMA_V0 = "go_evidence_receipt.v0"

SUPPORTED_SOURCE_RECEIPTS: dict[str, tuple[str, str]] = {
    "security_advisory_ingestor_go": (
        "local://security-advisory-inventory",
        "security_advisory_inventory.v0",
    ),
    "ai_frontier_ingestor_go": (
        "local://ai-frontier-inventory",
        "ai_frontier_inventory.v0",
    ),
    "agent_infra_ingestor_go": (
        "local://agent-infra-inventory",
        "agent_infra_inventory.v0",
    ),
    "practitioner_signal_ingestor_go": (
        "local://practitioner-signal-inventory",
        "practitioner_signal_inventory.v0",
    ),
}


class GoSourceInventoryBridgeError(ValueError):
    """Raised when a Go source-inventory receipt cannot be parsed."""


@dataclass(frozen=True)
class TrustEnvelope:
    origin_attestation: str
    corroboration_count: int
    freshness_window: str
    license_compatibility: str
    hallucination_risk_class: str
    routing_class: str
    claims_self_reported: bool = False
    social_raw: bool = False
    human_review_required: bool = False


@dataclass(frozen=True)
class ProbePolicy:
    external_network: bool
    timeout_ms: int
    max_body_bytes: int
    allowed_hosts: tuple[str, ...]
    raw_payload_storage: str


@dataclass(frozen=True)
class SourceObservation:
    id: str
    title: str
    url: str
    host: str
    kind: str
    publisher: str
    topic_tags: tuple[str, ...]
    license_compatibility: str
    freshness_window: str
    origin_attestation: str
    hallucination_risk_class: str
    routing_class: str
    corroboration_count: int
    fetched: bool
    reachable: bool
    status_code: int | None
    content_type: str = ""
    body_bytes: int = 0
    body_sha256: str = ""
    error: str = ""
    claims_self_reported: bool = False
    social_raw: bool = False
    human_review_required: bool = False


@dataclass(frozen=True)
class InventorySummary:
    source_count: int
    fetched_count: int
    reachable_count: int
    rejected_count: int


@dataclass(frozen=True)
class SourceRejection:
    id: str
    url: str
    reason: str


@dataclass(frozen=True)
class SourceInventoryPayload:
    ingest_schema: str
    probe_policy: ProbePolicy
    sources: tuple[SourceObservation, ...]
    summary: InventorySummary
    rejections: tuple[SourceRejection, ...] = ()


@dataclass(frozen=True)
class GoSourceInventoryReceipt:
    receipt_id: str
    correlation_id: str
    source: str
    source_url: str
    observed_at: str
    content_hash: str
    event_uid: str
    schema_version: str
    status: str
    payload: SourceInventoryPayload
    trust_envelope: TrustEnvelope | None = None
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
            raise GoSourceInventoryBridgeError(
                "GoSourceInventoryReceipt missing required identity fields"
            )
        if self.schema_version != GO_EVIDENCE_SCHEMA_V0:
            raise GoSourceInventoryBridgeError(
                f"unsupported Go evidence schema: {self.schema_version}"
            )
        if self.source not in SUPPORTED_SOURCE_RECEIPTS:
            raise GoSourceInventoryBridgeError(f"unsupported source inventory: {self.source}")
        expected_url, expected_schema = SUPPORTED_SOURCE_RECEIPTS[self.source]
        if self.source_url != expected_url:
            raise GoSourceInventoryBridgeError(
                f"unsupported receipt source_url: {self.source_url}"
            )
        if self.payload.ingest_schema != expected_schema:
            raise GoSourceInventoryBridgeError(
                f"unsupported source inventory schema: {self.payload.ingest_schema}"
            )
        if self.status not in {"accepted", "rejected"}:
            raise GoSourceInventoryBridgeError(f"unsupported receipt status: {self.status}")
        if self.status == "rejected" and not self.rejected_reason:
            raise GoSourceInventoryBridgeError("rejected receipt must carry rejected_reason")

    @property
    def reachable_sources(self) -> tuple[SourceObservation, ...]:
        return tuple(source for source in self.payload.sources if source.reachable)

    @property
    def human_only_sources(self) -> tuple[SourceObservation, ...]:
        return tuple(source for source in self.payload.sources if source.routing_class == "human_only")

    @property
    def social_sources(self) -> tuple[SourceObservation, ...]:
        return tuple(source for source in self.payload.sources if source.social_raw)


def load_go_source_inventory_receipt(path: Path) -> GoSourceInventoryReceipt:
    raw = json.loads(path.read_text(encoding="utf-8"))
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise GoSourceInventoryBridgeError("Go source inventory payload must be an object")
    source = str(raw.get("source", ""))
    if source not in SUPPORTED_SOURCE_RECEIPTS:
        raise GoSourceInventoryBridgeError(f"unsupported source inventory: {source!r}")
    return GoSourceInventoryReceipt(
        receipt_id=str(raw.get("receipt_id", "")),
        correlation_id=str(raw.get("correlation_id", "")),
        source=source,
        source_url=str(raw.get("source_url", "")),
        observed_at=str(raw.get("observed_at", "")),
        content_hash=str(raw.get("content_hash", "")),
        event_uid=str(raw.get("event_uid", "")),
        schema_version=str(raw.get("schema_version", "")),
        status=str(raw.get("status", "")),
        rejected_reason=str(raw.get("rejected_reason", "")),
        trust_envelope=_parse_optional_trust(raw.get("trust_envelope")),
        payload=_parse_payload(payload),
    )


def _parse_optional_trust(raw: Any) -> TrustEnvelope | None:
    if raw is None:
        return None
    item = _dict(raw, "trust_envelope")
    return TrustEnvelope(
        origin_attestation=str(item.get("origin_attestation", "")),
        corroboration_count=int(item.get("corroboration_count", 0)),
        freshness_window=str(item.get("freshness_window", "")),
        license_compatibility=str(item.get("license_compatibility", "")),
        hallucination_risk_class=str(item.get("hallucination_risk_class", "")),
        routing_class=str(item.get("routing_class", "")),
        claims_self_reported=bool(item.get("claims_self_reported")),
        social_raw=bool(item.get("social_raw")),
        human_review_required=bool(item.get("human_review_required")),
    )


def _parse_payload(raw: dict[str, Any]) -> SourceInventoryPayload:
    return SourceInventoryPayload(
        ingest_schema=str(raw.get("ingest_schema", "")),
        probe_policy=_parse_policy(_dict(raw.get("probe_policy"), "probe_policy")),
        sources=tuple(_parse_source(item) for item in _list(raw.get("sources"), "sources")),
        summary=_parse_summary(_dict(raw.get("summary"), "summary")),
        rejections=tuple(
            _parse_rejection(item)
            for item in _list(raw.get("rejections", []), "rejections")
        ),
    )


def _parse_policy(raw: dict[str, Any]) -> ProbePolicy:
    return ProbePolicy(
        external_network=bool(raw.get("external_network")),
        timeout_ms=int(raw.get("timeout_ms", 0)),
        max_body_bytes=int(raw.get("max_body_bytes", 0)),
        allowed_hosts=tuple(str(item) for item in _list(raw.get("allowed_hosts"), "allowed_hosts")),
        raw_payload_storage=str(raw.get("raw_payload_storage", "")),
    )


def _parse_source(raw: Any) -> SourceObservation:
    item = _dict(raw, "source")
    status = item.get("status_code")
    return SourceObservation(
        id=str(item.get("id", "")),
        title=str(item.get("title", "")),
        url=str(item.get("url", "")),
        host=str(item.get("host", "")),
        kind=str(item.get("kind", "")),
        publisher=str(item.get("publisher", "")),
        topic_tags=tuple(str(tag) for tag in _list(item.get("topic_tags"), "topic_tags")),
        license_compatibility=str(item.get("license_compatibility", "")),
        freshness_window=str(item.get("freshness_window", "")),
        origin_attestation=str(item.get("origin_attestation", "")),
        hallucination_risk_class=str(item.get("hallucination_risk_class", "")),
        routing_class=str(item.get("routing_class", "")),
        corroboration_count=int(item.get("corroboration_count", 0)),
        fetched=bool(item.get("fetched")),
        reachable=bool(item.get("reachable")),
        status_code=int(status) if status is not None else None,
        content_type=str(item.get("content_type", "")),
        body_bytes=int(item.get("body_bytes", 0)),
        body_sha256=str(item.get("body_sha256", "")),
        error=str(item.get("error", "")),
        claims_self_reported=bool(item.get("claims_self_reported")),
        social_raw=bool(item.get("social_raw")),
        human_review_required=bool(item.get("human_review_required")),
    )


def _parse_summary(raw: dict[str, Any]) -> InventorySummary:
    return InventorySummary(
        source_count=int(raw.get("source_count", 0)),
        fetched_count=int(raw.get("fetched_count", 0)),
        reachable_count=int(raw.get("reachable_count", 0)),
        rejected_count=int(raw.get("rejected_count", 0)),
    )


def _parse_rejection(raw: Any) -> SourceRejection:
    item = _dict(raw, "rejection")
    return SourceRejection(
        id=str(item.get("id", "")),
        url=str(item.get("url", "")),
        reason=str(item.get("reason", "")),
    )


def _dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GoSourceInventoryBridgeError(f"{field} must be a JSON object")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise GoSourceInventoryBridgeError(f"{field} must be a JSON array")
    return value
