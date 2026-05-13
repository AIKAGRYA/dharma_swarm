"""Tests for the Go local model inventory bridge (G6)."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import dharma_swarm.operator_core.go_model_inventory_bridge as bridge_module
from dharma_swarm.operator_core.go_model_inventory_bridge import (
    GO_EVIDENCE_SCHEMA_V0,
    LOCAL_MODEL_INVENTORY_SCHEMA_V1,
    LOCAL_MODEL_INVENTORY_SOURCE,
    LOCAL_MODEL_INVENTORY_SOURCE_URL,
    GoModelInventoryBridgeError,
    GoModelInventoryReceipt,
    load_go_model_inventory_receipt,
)

OBSERVED_AT = "2026-05-10T00:00:00Z"
CORRELATION_ID = "corr_v0_local_model_inventory"


def _payload() -> dict[str, object]:
    return {
        "inventory_schema": LOCAL_MODEL_INVENTORY_SCHEMA_V1,
        "probe_policy": {
            "loopback_only": True,
            "timeout_ms": 750,
            "external_network": False,
            "allowed_hosts": ["127.0.0.1", "localhost", "[::1]"],
        },
        "host": {"goos": "darwin", "goarch": "arm64"},
        "binaries": [
            {"name": "ollama", "present": True, "path": "/usr/local/bin/ollama"},
            {"name": "vllm", "present": False, "path": ""},
        ],
        "runtimes": [
            {
                "name": "ollama",
                "kind": "ollama_tags",
                "url": "http://127.0.0.1:11434/api/tags",
                "reachable": True,
                "status_code": 200,
                "models": [{"id": "llama3.2:latest"}],
            },
            {
                "name": "vllm_openai",
                "kind": "openai_models",
                "url": "http://127.0.0.1:8000/v1/models",
                "reachable": False,
                "models": [],
                "error": "request_failed",
            },
        ],
        "summary": {
            "runtime_count": 2,
            "reachable_count": 1,
            "model_count": 1,
            "rejected_count": 0,
        },
    }


def _receipt(status: str = "accepted", **updates: object) -> dict[str, object]:
    raw: dict[str, object] = {
        "receipt_id": "goev_model_inventory",
        "correlation_id": CORRELATION_ID,
        "source": LOCAL_MODEL_INVENTORY_SOURCE,
        "source_url": LOCAL_MODEL_INVENTORY_SOURCE_URL,
        "observed_at": OBSERVED_AT,
        "content_hash": "sha256:abc",
        "event_uid": "evt_model_inventory",
        "schema_version": GO_EVIDENCE_SCHEMA_V0,
        "status": status,
        "payload": _payload(),
    }
    if status == "rejected":
        raw["rejected_reason"] = "non_loopback_url:http://192.0.2.10:8000/v1/models"
        payload = dict(raw["payload"])  # type: ignore[arg-type]
        payload["summary"] = {
            "runtime_count": 0,
            "reachable_count": 0,
            "model_count": 0,
            "rejected_count": 1,
        }
        payload["runtimes"] = []
        payload["rejections"] = [
            {
                "name": "bad",
                "url": "http://192.0.2.10:8000/v1/models",
                "reason": "non_loopback_url",
            }
        ]
        raw["payload"] = payload
    raw.update(updates)
    return raw


def _write_receipt(tmp_path: Path, raw: dict[str, object]) -> Path:
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_loads_accepted_inventory_receipt(tmp_path: Path) -> None:
    receipt = load_go_model_inventory_receipt(_write_receipt(tmp_path, _receipt()))
    assert receipt.status == "accepted"
    assert receipt.payload.summary.runtime_count == 2
    assert receipt.payload.summary.reachable_count == 1
    assert receipt.reachable_runtimes[0].name == "ollama"
    assert receipt.discovered_models[0].id == "llama3.2:latest"
    assert receipt.present_binaries[0].name == "ollama"
    assert receipt.payload.probe_policy.allowed_hosts == (
        "127.0.0.1",
        "localhost",
        "[::1]",
    )


def test_loads_rejected_inventory_receipt(tmp_path: Path) -> None:
    receipt = load_go_model_inventory_receipt(_write_receipt(tmp_path, _receipt("rejected")))
    assert receipt.status == "rejected"
    assert receipt.rejected_reason.startswith("non_loopback_url:")
    assert receipt.payload.summary.rejected_count == 1
    assert receipt.payload.rejections[0].reason == "non_loopback_url"
    assert receipt.reachable_runtimes == ()


def test_rejects_external_network_policy() -> None:
    payload = _payload()
    policy = dict(payload["probe_policy"])  # type: ignore[arg-type]
    policy["external_network"] = True
    payload["probe_policy"] = policy
    with pytest.raises(GoModelInventoryBridgeError):
        GoModelInventoryReceipt(
            receipt_id="goev_x",
            correlation_id=CORRELATION_ID,
            source=LOCAL_MODEL_INVENTORY_SOURCE,
            source_url=LOCAL_MODEL_INVENTORY_SOURCE_URL,
            observed_at=OBSERVED_AT,
            content_hash="sha256:abc",
            event_uid="evt_x",
            schema_version=GO_EVIDENCE_SCHEMA_V0,
            status="accepted",
            payload=bridge_module._parse_payload(payload),
        )


def test_rejects_wrong_source(tmp_path: Path) -> None:
    with pytest.raises(GoModelInventoryBridgeError):
        load_go_model_inventory_receipt(
            _write_receipt(tmp_path, _receipt(source="github_pull_request"))
        )


def test_receipt_shape_contains_no_secret_values(tmp_path: Path) -> None:
    raw = _receipt()
    rendered = json.dumps(raw).lower()
    assert "api_key" not in rendered
    assert "authorization" not in rendered
    assert "bearer" not in rendered
    assert "sk-" not in rendered
    receipt = load_go_model_inventory_receipt(_write_receipt(tmp_path, raw))
    assert receipt.payload.binaries[0].present is True
    assert receipt.payload.binaries[0].path == "/usr/local/bin/ollama"


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
