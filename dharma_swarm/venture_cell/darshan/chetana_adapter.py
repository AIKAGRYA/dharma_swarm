"""Chetana staging adapter for Darshan bundles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.chetana.ingest import IngestResult, ingest
from dharma_swarm.venture_cell.darshan.bundle import validate_bundle


@dataclass(frozen=True)
class DarshanChetanaResult:
    staged_paths: list[Path]
    notes: list[str]


def ingest_bundle(bundle_path: Path) -> DarshanChetanaResult:
    result = validate_bundle(bundle_path)
    if not result.valid:
        raise ValueError("; ".join(result.errors))
    manifest = result.manifest
    if manifest is None:
        raise ValueError("bundle manifest missing")

    article = result.bundle_path / "article.md"
    source_pack = result.bundle_path / "source_pack.json"
    atom = ingest(
        source=article,
        source_kind="note",
        title=f"Darshan: {manifest.title}",
        atom_type="atomic",
        confidence=0.72,
        captured_by="dharma_swarm.venture_cell.darshan",
        tags=["darshan", "venture-cell", "after-the-feed"],
        related=[str(source_pack)],
    )
    return _to_result(atom)


def _to_result(result: IngestResult) -> DarshanChetanaResult:
    return DarshanChetanaResult(
        staged_paths=list(result.atoms),
        notes=list(result.notes),
    )
