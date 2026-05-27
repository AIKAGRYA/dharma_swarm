"""Ontology adapter for Darshan artifact bundles."""

from __future__ import annotations

import hashlib
from pathlib import Path

from dharma_swarm.ontology import OntologyObj, OntologyRegistry
from dharma_swarm.ontology_runtime import get_shared_registry, persist_shared_registry
from dharma_swarm.venture_cell.darshan.bundle import validate_bundle


def materialize_knowledge_artifact(
    bundle_path: Path,
    *,
    registry: OntologyRegistry | None = None,
    ontology_path: Path | None = None,
    persist: bool = True,
) -> OntologyObj:
    result = validate_bundle(bundle_path)
    if not result.valid:
        raise ValueError("; ".join(result.errors))
    manifest = result.manifest
    if manifest is None:
        raise ValueError("bundle manifest missing")

    article = result.bundle_path / "article.md"
    content = article.read_text(encoding="utf-8")
    reg = registry or get_shared_registry(path=ontology_path)
    obj, errors = reg.create_object(
        "KnowledgeArtifact",
        {
            "title": manifest.title,
            "artifact_type": "finding",
            "domain": "dharma_swarm",
            "content": content,
            "file_path": str(article),
            "provenance": str(result.bundle_path),
            "confidence": 0.72,
            "verified": False,
            "subtype": "darshan_artifact",
            "artifact_id": manifest.artifact_id,
            "season": manifest.season,
            "slug": manifest.slug,
            "cell_id": "DARSHAN",
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "source_pack_path": str(result.bundle_path / "source_pack.json"),
            "claim_ledger_path": str(result.bundle_path / "claim_ledger.json"),
            "decision_delta_path": str(result.bundle_path / "decision_delta.json"),
        },
        created_by="darshan_venture_cell",
    )
    if obj is None:
        raise ValueError("; ".join(errors))
    if persist and registry is None:
        persist_shared_registry(reg, path=ontology_path)
    return obj
