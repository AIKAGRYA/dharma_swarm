"""Publish Loom artifacts through the gated KnowledgeArtifact action."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from dharma_swarm.ontology import OntologyObj
from dharma_swarm.ontology_action_gateway import (
    OntologyActionGateway,
    OntologyGatewayError,
)


class LoomPublisher:
    """Filesystem publisher for ontology-backed Loom pages."""

    def __init__(
        self,
        gateway: OntologyActionGateway,
        *,
        output_dir: str | Path,
        now_fn,
    ) -> None:
        self.gateway = gateway
        self.output_dir = Path(output_dir)
        self.now_fn = now_fn
        self._publishable_ids: set[str] = set()

    def mark_publishable(self, artifact_id: str) -> None:
        """Allow publishing only artifacts composed by the Loom builder."""
        self._publishable_ids.add(artifact_id)

    def publish(self, artifact: OntologyObj) -> Path:
        """Gate, write, and annotate a Loom artifact."""
        if artifact.id not in self._publishable_ids:
            raise OntologyGatewayError("publish requires a Loom-composed artifact")
        content = str(artifact.properties.get("content") or "").strip()
        if not content:
            raise OntologyGatewayError("Loom artifact content is empty")
        if "ontology://" not in content:
            raise OntologyGatewayError("Loom artifact has no ontology citation")

        now = self.now_fn()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{_slugify(str(artifact.properties.get('title') or artifact.id))}.md"
        self.gateway.execute_action_or_fail(
            "KnowledgeArtifact",
            "Publish",
            artifact.id,
            {"channel": "filesystem", "path": str(path)},
            executed_by="wiki_loom",
        )
        path.write_text(content + "\n", encoding="utf-8")
        self.gateway.update_object_or_fail(
            artifact.id,
            {
                "published_path": str(path),
                "published_at": now.isoformat(),
                "published_channel": "filesystem",
            },
            updated_by="wiki_loom",
        )
        return path


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug[:96] or "loom-revelation"
