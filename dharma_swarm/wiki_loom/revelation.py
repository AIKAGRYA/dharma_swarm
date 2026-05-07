"""Build one ontology-backed Loom revelation from a source object."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dharma_swarm.ontology import OntologyObj
from dharma_swarm.ontology_action_gateway import OntologyActionGateway
from dharma_swarm.wiki_loom.atomizer import atomize_source
from dharma_swarm.wiki_loom.linker import link_revelation_sources
from dharma_swarm.wiki_loom.publisher import LoomPublisher

WITA = ZoneInfo("Asia/Makassar")


class LoomRevelationBuilder:
    """Compose and publish one citation-resolving Loom page."""

    def __init__(
        self,
        gateway: OntologyActionGateway,
        *,
        output_dir: str | Path,
        now_fn=None,
    ) -> None:
        self.gateway = gateway
        self.now_fn = now_fn or (lambda: datetime.now(WITA))
        self.publisher = LoomPublisher(gateway, output_dir=output_dir, now_fn=self.now_fn)

    def compose(self, source: OntologyObj) -> OntologyObj:
        """Create a WitnessLog and KnowledgeArtifact for a source object."""
        now = self.now_fn()
        witness = self.gateway.create_object_or_fail(
            "WitnessLog",
            {
                "observation": f"Loom revelation source review for {source.type_name}/{source.id}",
                "observer": "wiki_loom",
                "context": "wiki_loom_vertical_slice",
                "witness_quality": 1.0,
                "contraction_level": "L3",
            },
            created_by="wiki_loom",
        )
        artifact = self.gateway.create_object_or_fail(
            "KnowledgeArtifact",
            {
                "title": f"Loom Revelation - {source.type_name} {source.id[:8]}",
                "artifact_type": "finding",
                "domain": "dharma_swarm",
                "content": "",
                "provenance": f"wiki_loom:{source.type_name}/{source.id}",
                "confidence": 1.0,
                "verified": True,
                "audience": "dhyana",
            },
            created_by="wiki_loom",
        )
        atom = atomize_source(source, artifact_id=artifact.id, witness_id=witness.id, now=now)
        artifact = self.gateway.update_object_or_fail(
            artifact.id,
            {"title": atom.title, "content": atom.content},
            updated_by="wiki_loom",
        )
        link_revelation_sources(
            self.gateway,
            artifact=artifact,
            source=source,
            witness=witness,
        )
        self.publisher.mark_publishable(artifact.id)
        return artifact

    def publish(self, artifact: OntologyObj) -> Path:
        """Publish a composed Loom page."""
        return self.publisher.publish(artifact)


def build_and_publish_revelation(
    source: OntologyObj,
    *,
    gateway: OntologyActionGateway,
    output_dir: str | Path,
    now_fn=None,
) -> Path:
    """Convenience wrapper for the one-source Loom vertical slice."""
    builder = LoomRevelationBuilder(gateway, output_dir=output_dir, now_fn=now_fn)
    artifact = builder.compose(source)
    return builder.publish(artifact)
