"""Tests for the read-only Go source-inventory bridge."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import dharma_swarm.operator_core.go_source_inventory_bridge as bridge_module
from dharma_swarm.operator_core.go_source_inventory_bridge import (
    GO_EVIDENCE_SCHEMA_V0,
    SUPPORTED_SOURCE_RECEIPTS,
    GoSourceInventoryBridgeError,
    load_go_source_inventory_receipt,
)

OBSERVED_AT = "2026-05-10T00:00:00Z"
CORRELATION_ID = "corr_source_inventory_bridge"


def _source(source: str = "security_advisory_ingestor_go") -> dict[str, object]:
    _, schema = SUPPORTED_SOURCE_RECEIPTS[source]
    return {
        "ingest_schema": schema,
        "probe_policy": {
            "external_network": True,
            "timeout_ms": 750,
            "max_body_bytes": 1048576,
            "allowed_hosts": ["www.cisa.gov"],
            "raw_payload_storage": "hash_only",
        },
        "sources": [
            {
                "id": "cisa_kev",
                "title": "CISA KEV",
                "url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
                "host": "www.cisa.gov",
                "kind": "json_feed",
                "publisher": "CISA",
                "topic_tags": ["security", "kev"],
                "license_compatibility": "open_government_data_review_required",
                "freshness_window": "24h",
                "origin_attestation": "unsigned",
                "hallucination_risk_class": "raw_data",
                "routing_class": "review",
                "corroboration_count": 1,
                "fetched": True,
                "reachable": True,
                "status_code": 200,
                "content_type": "application/json",
                "body_bytes": 23,
                "body_sha256": "sha256:abc",
                "human_review_required": True,
            }
        ],
        "summary": {
            "source_count": 1,
            "fetched_count": 1,
            "reachable_count": 1,
            "rejected_count": 0,
        },
    }


def _receipt(source: str = "security_advisory_ingestor_go", status: str = "accepted") -> dict[str, object]:
    source_url, _ = SUPPORTED_SOURCE_RECEIPTS[source]
    raw: dict[str, object] = {
        "receipt_id": "goev_source_inventory",
        "correlation_id": CORRELATION_ID,
        "source": source,
        "source_url": source_url,
        "observed_at": OBSERVED_AT,
        "content_hash": "sha256:abc",
        "event_uid": "evt_source_inventory",
        "schema_version": GO_EVIDENCE_SCHEMA_V0,
        "status": status,
        "trust_envelope": {
            "origin_attestation": "unsigned",
            "corroboration_count": 1,
            "freshness_window": "24h",
            "license_compatibility": "mixed_review_required",
            "hallucination_risk_class": "raw_data",
            "routing_class": "review",
            "human_review_required": True,
        },
        "payload": _source(source),
    }
    if status == "rejected":
        payload = dict(raw["payload"])  # type: ignore[arg-type]
        payload["sources"] = []
        payload["summary"] = {
            "source_count": 0,
            "fetched_count": 0,
            "reachable_count": 0,
            "rejected_count": 1,
        }
        payload["rejections"] = [
            {
                "id": "bad_source",
                "url": "http://example.com/feed",
                "reason": "insecure_external_http",
            }
        ]
        raw["payload"] = payload
        raw["rejected_reason"] = "insecure_external_http:http://example.com/feed"
    return raw


def _write_receipt(tmp_path: Path, raw: dict[str, object]) -> Path:
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_loads_security_source_inventory(tmp_path: Path) -> None:
    receipt = load_go_source_inventory_receipt(_write_receipt(tmp_path, _receipt()))
    assert receipt.status == "accepted"
    assert receipt.payload.summary.source_count == 1
    assert receipt.reachable_sources[0].id == "cisa_kev"
    assert receipt.trust_envelope is not None
    assert receipt.trust_envelope.routing_class == "review"
    assert receipt.payload.probe_policy.raw_payload_storage == "hash_only"


def test_loads_social_source_inventory(tmp_path: Path) -> None:
    raw = _receipt("practitioner_signal_ingestor_go")
    payload = raw["payload"]
    assert isinstance(payload, dict)
    payload["sources"][0]["id"] = "reddit_localllama"  # type: ignore[index]
    payload["sources"][0]["routing_class"] = "human_only"  # type: ignore[index]
    payload["sources"][0]["social_raw"] = True  # type: ignore[index]
    receipt = load_go_source_inventory_receipt(_write_receipt(tmp_path, raw))
    assert receipt.human_only_sources[0].id == "reddit_localllama"
    assert receipt.social_sources[0].social_raw is True


def test_loads_rejected_source_inventory(tmp_path: Path) -> None:
    receipt = load_go_source_inventory_receipt(_write_receipt(tmp_path, _receipt(status="rejected")))
    assert receipt.status == "rejected"
    assert receipt.payload.summary.rejected_count == 1
    assert receipt.payload.rejections[0].reason == "insecure_external_http"
    assert receipt.reachable_sources == ()


def test_rejects_unknown_source(tmp_path: Path) -> None:
    raw = _receipt()
    raw["source"] = "unknown_source"
    with pytest.raises(GoSourceInventoryBridgeError):
        load_go_source_inventory_receipt(_write_receipt(tmp_path, raw))


def test_bridge_stays_read_only() -> None:
    module_path = Path(bridge_module.__file__ or "")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden_import_fragments = (
        "ontology",
        "runtime_db",
        "record_evidence_receipt",
        "closure_v0",
        "NextDecision",
    )
    for module_name in imported_modules:
        for token in forbidden_import_fragments:
            assert token not in module_name
