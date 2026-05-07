"""Convert ontology source objects into Loom revelation artifacts.

This module is intentionally ontology-native: it renders only resolvable
ontology citations and leaves writes to the gateway.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from textwrap import shorten

from dharma_swarm.ontology import OntologyObj


@dataclass(frozen=True)
class LoomAtom:
    """A small public/private page seed derived from one ontology source."""

    title: str
    content: str
    source_id: str
    source_type: str
    source_citation: str
    summary: str


def atomize_source(
    source: OntologyObj,
    *,
    artifact_id: str,
    witness_id: str,
    now: datetime,
) -> LoomAtom:
    """Build one Loom atom from a source object without mutating the registry."""
    if source.type_name == "Outcome":
        return _atomize_outcome(source, artifact_id=artifact_id, witness_id=witness_id, now=now)
    if source.type_name == "Signal":
        return _atomize_signal(source, artifact_id=artifact_id, witness_id=witness_id, now=now)
    raise ValueError(f"wiki_loom cannot atomize source type: {source.type_name}")


def _atomize_outcome(
    source: OntologyObj,
    *,
    artifact_id: str,
    witness_id: str,
    now: datetime,
) -> LoomAtom:
    props = source.properties
    task_id = str(props.get("task_id") or source.id)
    success = bool(props.get("success"))
    status = "completed" if success else "failed"
    summary = _clean_summary(str(props.get("result_summary") or props.get("error") or "No summary recorded."))
    title = f"Loom Revelation - {task_id}"
    source_citation = f"ontology://KnowledgeArtifact/{artifact_id}#cites/Outcome/{source.id}"
    content = _render_content(
        title=title,
        source_type="Outcome",
        source_id=source.id,
        source_citation=source_citation,
        witness_id=witness_id,
        now=now,
        summary=f"`{task_id}` {status}: {summary}",
    )
    return LoomAtom(
        title=title,
        content=content,
        source_id=source.id,
        source_type=source.type_name,
        source_citation=source_citation,
        summary=summary,
    )


def _atomize_signal(
    source: OntologyObj,
    *,
    artifact_id: str,
    witness_id: str,
    now: datetime,
) -> LoomAtom:
    props = source.properties
    signal_id = str(props.get("signal_id") or source.id)
    payload = _clean_summary(str(props.get("payload") or "No payload recorded."))
    title = f"Loom Revelation - {signal_id}"
    source_citation = f"ontology://KnowledgeArtifact/{artifact_id}#observes/Signal/{source.id}"
    content = _render_content(
        title=title,
        source_type="Signal",
        source_id=source.id,
        source_citation=source_citation,
        witness_id=witness_id,
        now=now,
        summary=payload,
    )
    return LoomAtom(
        title=title,
        content=content,
        source_id=source.id,
        source_type=source.type_name,
        source_citation=source_citation,
        summary=payload,
    )


def _render_content(
    *,
    title: str,
    source_type: str,
    source_id: str,
    source_citation: str,
    witness_id: str,
    now: datetime,
    summary: str,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"Generated: {now.isoformat()}",
        f"Source: `{source_type}/{source_id}`",
        f"Witness: `WitnessLog/{witness_id}`",
        "",
        "## Signal",
        "",
        f"- {summary} [{source_citation}]",
        "",
        "## Why It Matters",
        "",
        "- This page exists only because the source citation resolves inside the ontology.",
        "- If the source object disappears, this artifact is invalid.",
    ]
    return "\n".join(lines)


def _clean_summary(text: str) -> str:
    collapsed = " ".join(text.split())
    return shorten(collapsed, width=360, placeholder="...")
