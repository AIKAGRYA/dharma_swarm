"""Typed ontology links for Loom revelation artifacts.

Outcome sources get hard schema links. Signal sources are cited in content
until the ontology grows a KnowledgeArtifact-to-Signal link.
"""

from __future__ import annotations

from dharma_swarm.ontology import OntologyObj
from dharma_swarm.ontology_action_gateway import OntologyActionGateway


def link_revelation_sources(
    gateway: OntologyActionGateway,
    *,
    artifact: OntologyObj,
    source: OntologyObj,
    witness: OntologyObj,
    created_by: str = "wiki_loom",
) -> None:
    """Attach all currently valid ontology links for a Loom revelation."""
    if artifact.type_name != "KnowledgeArtifact":
        raise ValueError("artifact must be a KnowledgeArtifact")
    if witness.type_name != "WitnessLog":
        raise ValueError("witness must be a WitnessLog")

    if source.type_name == "Outcome":
        gateway.link_or_fail(
            "derived_from",
            artifact.id,
            source.id,
            created_by=created_by,
            metadata={"loom_source_type": source.type_name},
        )
    elif source.type_name != "Signal":
        raise ValueError(f"unsupported Loom source type: {source.type_name}")

    gateway.link_or_fail(
        "cites_witness",
        artifact.id,
        witness.id,
        created_by=created_by,
        metadata={"loom_source_type": source.type_name, "loom_source_id": source.id},
    )
