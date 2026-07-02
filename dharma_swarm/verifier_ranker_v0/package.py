"""Package verification helpers for DharmaVerifier-Ranker v0 artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from dharma_swarm.verifier_ranker_v0.schemas import (
    GRAPH_RECORD_TYPES,
    GRAPH_SCHEMA_VERSION,
    MODEL_OUTPUT_SCHEMA,
    SEMANTIC_RECEIPT_GRAPH_SCHEMA,
)

REQUIRED_REPORTS = [
    "README.md",
    "DHARMA_SEMANTIC_RECEIPT_GRAPH_V0.schema.json",
    "DHARMA_VERIFIER_RANKER_OUTPUT_V0.schema.json",
    "DATA_INVENTORY_20260701.md",
    "DATA_INVENTORY_RECEIPT_20260701.json",
    "REDACTION_AND_PRIVACY_RULES_20260701.md",
    "LABEL_TAXONOMY_AND_GOLD_PLAN_20260701.md",
    "MODEL_ARCHITECTURE_AND_TRAINING_READINESS_20260701.md",
    "TRAINING_COMMAND_PLAN_20260701.md",
    "BASELINE_AND_EVAL_PLAN_20260701.md",
    "TOOL_RESOURCE_RESEARCH_20260701.md",
    "PROMOTION_AND_KILL_GATES_20260701.md",
    "MODEL_CARD_TEMPLATE_20260701.md",
    "MODEL_CARD_AND_PROMOTION_DECISION_20260701.md",
    "PACKAGE_MANIFEST_20260701.json",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def verify_json_schema_basics() -> list[str]:
    errors: list[str] = []
    if SEMANTIC_RECEIPT_GRAPH_SCHEMA.get("properties", {}).get("schema_version", {}).get("const") != GRAPH_SCHEMA_VERSION:
        errors.append("graph schema version const mismatch")
    graph_record_enum = (
        SEMANTIC_RECEIPT_GRAPH_SCHEMA.get("properties", {})
        .get("record_type", {})
        .get("enum", [])
    )
    missing_records = sorted(set(GRAPH_RECORD_TYPES) - set(graph_record_enum))
    if missing_records:
        errors.append(f"graph schema missing record types: {missing_records}")
    output_required = set(MODEL_OUTPUT_SCHEMA.get("required", []))
    expected_output_fields = {
        "verdict",
        "quality_score",
        "evidence_sufficiency",
        "claim_integrity_risk",
        "privacy_risk",
        "route_risk",
        "gate_failures",
        "missing_evidence",
        "next_required_action",
        "confidence",
        "rationale_refs",
    }
    if output_required != expected_output_fields:
        errors.append("model output schema required fields mismatch")
    verdict_enum = MODEL_OUTPUT_SCHEMA.get("properties", {}).get("verdict", {}).get("enum", [])
    expected_verdicts = ["approve", "revise", "block", "escalate", "insufficient_context"]
    if verdict_enum != expected_verdicts:
        errors.append("model output verdict enum mismatch")
    return errors


def build_manifest(package_dir: Path, *, extra_artifacts: list[Path] | None = None) -> dict[str, Any]:
    artifact_paths = [package_dir / name for name in REQUIRED_REPORTS if name != "PACKAGE_MANIFEST_20260701.json"]
    artifact_paths.extend(extra_artifacts or [])
    artifacts = {}
    missing = []
    for path in artifact_paths:
        if not path.exists():
            missing.append(str(path))
            continue
        artifacts[str(path)] = {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    schema_errors = verify_json_schema_basics()
    return {
        "schema_version": "dharma.verifier_ranker_v0.package_manifest.v1",
        "package_dir": str(package_dir),
        "status": "pass" if not missing and not schema_errors else "fail",
        "missing": missing,
        "schema_errors": schema_errors,
        "artifacts": artifacts,
    }


def write_manifest(package_dir: Path, *, extra_artifacts: list[Path] | None = None) -> Path:
    manifest = build_manifest(package_dir, extra_artifacts=extra_artifacts)
    out = package_dir / "PACKAGE_MANIFEST_20260701.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
