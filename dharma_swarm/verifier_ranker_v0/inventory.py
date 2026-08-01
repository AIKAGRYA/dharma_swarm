"""Metadata-only data inventory for DharmaVerifier-Ranker v0."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir


@dataclass(frozen=True)
class SurfaceSpec:
    surface_id: str
    path: Path
    source_kind: str
    candidate_record_types: list[str]
    training_value: str
    leakage_risk: str
    default_decision: str
    notes: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def count_files(path: Path) -> int:
    if path.is_file():
        return 1
    if not path.exists():
        return 0
    return sum(1 for child in path.rglob("*") if child.is_file())


def total_bytes(path: Path) -> int:
    if path.is_file() and path.exists():
        return path.stat().st_size
    if not path.exists():
        return 0
    return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        files = [path]
    else:
        files = sorted(path.glob("*.jsonl"))
    total = 0
    for file_path in files:
        with file_path.open("rb") as handle:
            total += sum(1 for _ in handle)
    return total


def sqlite_table_counts(path: Path, tables: list[str]) -> dict[str, int | None]:
    if not path.exists():
        return {table: None for table in tables}
    counts: dict[str, int | None] = {}
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        for table in tables:
            try:
                row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()
            except sqlite3.Error:
                counts[table] = None
            else:
                counts[table] = int(row[0]) if row else None
    return counts


def sqlite_table_columns(path: Path, tables: list[str]) -> dict[str, list[str]]:
    if not path.exists():
        return {table: [] for table in tables}
    columns: dict[str, list[str]] = {}
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        for table in tables:
            try:
                rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            except sqlite3.Error:
                columns[table] = []
            else:
                columns[table] = [str(row[1]) for row in rows]
    return columns


def default_surfaces(repo_root: Path, dharma_home: Path, sis_docs: Path) -> list[SurfaceSpec]:
    return [
        SurfaceSpec(
            "repo_a2a_receipts",
            repo_root / "reports" / "a2a",
            "json_receipts",
            ["a2a_delivery", "artifact_ref", "claim_evidence"],
            "high",
            "medium",
            "metadata_and_redacted_content_only",
            "Contains transport receipts and reply artifacts; raw payload fields must be hashed/redacted.",
        ),
        SurfaceSpec(
            "repo_agentops_semantic_receipts",
            repo_root / "reports" / "agentops" / "semantic_receipts",
            "json_receipts",
            ["semantic_receipt", "verifier_outcome", "claim_evidence"],
            "high",
            "medium",
            "metadata_and_redacted_content_only",
            "Closest existing surface to verifier/ranker labels and council outcomes.",
        ),
        SurfaceSpec(
            "repo_deepseek_ml_lead_council",
            repo_root / "reports" / "agentops" / "deepseek_ml_lead_council",
            "strategy_receipts",
            ["human_or_council_label", "claim_evidence"],
            "medium",
            "low",
            "include_after_hash_lock",
            "Sanitized external ML lead response and council synthesis.",
        ),
        SurfaceSpec(
            "repo_sab_flywheel_receipts",
            repo_root / "reports" / "sab_first_six_agent_flywheel",
            "json_and_markdown_receipts",
            ["agent_event", "semantic_receipt", "a2a_delivery"],
            "medium",
            "medium",
            "metadata_and_redacted_content_only",
            "Useful for route/action/receipt quality labels; outreach text must remain redacted.",
        ),
        SurfaceSpec(
            "runtime_state_db",
            dharma_home / "state" / "runtime.db",
            "sqlite_metadata",
            ["provider_attempt", "routing_decision", "agent_event", "verifier_outcome"],
            "high",
            "medium",
            "schema_counts_and_selected_redacted_rows_only",
            "Provider attempts, routing decisions, runtime receipts, external outcomes, task claims.",
        ),
        SurfaceSpec(
            "a2a_messages_db",
            dharma_home / "db" / "messages.db",
            "sqlite_metadata",
            ["a2a_delivery", "artifact_ref"],
            "high",
            "high",
            "exclude_raw_message_bodies",
            "Message bodies are explicitly excluded for v0; only IDs, hashes, routing metadata, and timestamps are eligible.",
        ),
        SurfaceSpec(
            "generated_training_datasets",
            dharma_home / "datasets",
            "jsonl_training_corpus",
            ["agent_event"],
            "medium",
            "high",
            "quarantine_until_redacted_and_relabelled",
            "Existing chat-format datasets contain content fields and are not train-ready for this model without redaction.",
        ),
        SurfaceSpec(
            "forge_measurement_artifacts",
            dharma_home / "forge_v1",
            "measurement_artifacts",
            ["eval_result", "claim_evidence", "verifier_outcome"],
            "high",
            "medium",
            "metadata_and_redacted_content_only",
            "Forge outputs provide pass/fail, ranking, contamination, budget, and downstream-lift signals.",
        ),
        SurfaceSpec(
            "sis_docs",
            sis_docs,
            "evidence_docs",
            ["claim_evidence", "artifact_ref"],
            "medium",
            "medium",
            "hash_locked_references_only",
            "Use as evidence-reference metadata, not as unsupervised private text corpus.",
        ),
        SurfaceSpec(
            "repo_eval_and_validator_code",
            repo_root / "dharma_swarm",
            "code_surface",
            ["eval_result", "verifier_outcome"],
            "medium",
            "low",
            "use_as_baseline_reference_not_training_text",
            "Existing evaluator, semantic receipt, and rule scorer modules define deterministic baselines.",
        ),
        SurfaceSpec(
            "repo_generated_verification_reports",
            repo_root / "reports" / "generated" / "verification",
            "verification_reports",
            ["eval_result", "claim_evidence"],
            "medium",
            "medium",
            "metadata_and_redacted_content_only",
            "Generated verification reports can seed eval examples after redaction and source hash locking.",
        ),
        SurfaceSpec(
            "repo_governance_reports",
            repo_root / "reports" / "governance",
            "governance_reports",
            ["human_or_council_label", "eval_result", "claim_evidence"],
            "medium",
            "medium",
            "metadata_and_redacted_content_only",
            "Governance reports include baselines and scans; large generated reports require hash locks and redaction.",
        ),
        SurfaceSpec(
            "agent_memory_store",
            dharma_home / "agent_memory",
            "agent_memory",
            ["agent_event", "claim_evidence"],
            "low",
            "high",
            "exclude_content_hash_metadata_only",
            "Agent memories contain content fields; v0 may use ids, scopes, timestamps, and hashes only.",
        ),
        SurfaceSpec(
            "trace_archives",
            dharma_home / "traces",
            "trace_archives",
            ["agent_event", "artifact_ref"],
            "medium",
            "high",
            "quarantine_until_schema_and_redaction_review",
            "Trace archives are large and may contain raw interaction state; do not export content in v0.",
        ),
    ]


def build_inventory(
    *,
    repo_root: Path,
    dharma_home: Path | None = None,
    sis_docs: Path | None = None,
) -> dict[str, Any]:
    dharma_home = dharma_home or dharma_state_dir("DHARMA_HOME")
    sis_docs = sis_docs or Path.home() / "sis" / "docs"
    runtime_db = dharma_home / "state" / "runtime.db"
    messages_db = dharma_home / "db" / "messages.db"
    agent_memory_db = dharma_home / "agent_memory" / "memories.db"
    runtime_tables = [
        "provider_attempts",
        "routing_decisions",
        "runtime_receipts",
        "delegation_runs",
        "artifact_records",
        "external_outcomes",
        "task_claims",
        "model_routing_outcomes",
    ]
    message_tables = ["messages", "events", "artifacts", "subscriptions"]
    agent_memory_tables = ["memories", "shared_memories"]
    surfaces = []
    for spec in default_surfaces(repo_root, dharma_home, sis_docs):
        row: dict[str, Any] = {
            "surface_id": spec.surface_id,
            "path": str(spec.path),
            "exists": spec.path.exists(),
            "source_kind": spec.source_kind,
            "candidate_record_types": spec.candidate_record_types,
            "file_count": count_files(spec.path),
            "total_bytes": total_bytes(spec.path),
            "training_value": spec.training_value,
            "leakage_risk": spec.leakage_risk,
            "default_decision": spec.default_decision,
            "notes": spec.notes,
        }
        if spec.surface_id == "generated_training_datasets":
            row["jsonl_rows"] = count_jsonl_rows(spec.path)
        surfaces.append(row)

    return {
        "schema_version": "dharma.verifier_ranker_v0.data_inventory.v1",
        "inventory_scope": "metadata_only_no_raw_message_body_readout",
        "surfaces": surfaces,
        "sqlite_metadata": {
            "runtime_state_db": {
                "path": str(runtime_db),
                "exists": runtime_db.exists(),
                "sha256": sha256_file(runtime_db) if runtime_db.exists() else "",
                "table_counts": sqlite_table_counts(runtime_db, runtime_tables),
                "table_columns": sqlite_table_columns(runtime_db, runtime_tables),
            },
            "a2a_messages_db": {
                "path": str(messages_db),
                "exists": messages_db.exists(),
                "sha256": sha256_file(messages_db) if messages_db.exists() else "",
                "table_counts": sqlite_table_counts(messages_db, message_tables),
                "table_columns": sqlite_table_columns(messages_db, message_tables),
                "excluded_columns": {
                    "messages": ["body"],
                    "events": ["payload"],
                    "artifacts": ["content"],
                },
            },
            "agent_memory_db": {
                "path": str(agent_memory_db),
                "exists": agent_memory_db.exists(),
                "sha256": sha256_file(agent_memory_db) if agent_memory_db.exists() else "",
                "table_counts": sqlite_table_counts(agent_memory_db, agent_memory_tables),
                "table_columns": sqlite_table_columns(agent_memory_db, agent_memory_tables),
                "excluded_columns": {
                    "memories": ["content"],
                    "shared_memories": ["content"],
                },
            },
        },
    }
