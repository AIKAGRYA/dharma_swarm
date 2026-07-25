"""Wiki-to-vector ingestion seam for the governed memory door."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.redaction import scan_text_for_write


@dataclass(frozen=True)
class WikiVectorIngestReceipt:
    state_dir: str
    wiki_concepts_dir: str
    discovered_files: int
    backfill: dict[str, Any]
    sync_index: dict[str, Any]
    reembed: dict[str, Any]
    skipped_secret_files: int = 0
    scan_error_files: int = 0

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def ingest_wiki_concepts(
    *,
    state_dir: Path | None = None,
    wiki_concepts_dir: Path | None = None,
    dim: int = 128,
    max_files: int = 512,
    max_file_bytes: int = 1024 * 1024,
) -> WikiVectorIngestReceipt:
    """Ingest live wiki concepts into vector + compact retrieval projections."""

    resolved_state_dir = Path(state_dir or dharma_state_dir()).expanduser()
    resolved_wiki_dir = Path(
        wiki_concepts_dir
        or dharma_state_dir() / "knowledge" / "wiki" / "concepts"
    ).expanduser()

    from scripts.memory_retrieval_sync_index import sync_memory_retrieval_index
    from scripts.vector_store_backfill_memory_sources import (
        backfill_memory_sources,
        discover_text_files,
    )
    from scripts.vector_store_reembed_vec0 import reembed_queries

    text_paths = discover_text_files(
        (resolved_wiki_dir,),
        max_files=max_files,
        max_bytes=max_file_bytes,
    )
    # This boundary ingests source files by path, so flagged content cannot be
    # redacted in place: files with secret-shaped findings (or scan errors)
    # are excluded from the vector projection entirely — never persisted raw.
    # Contact/location PII passes: the trusted wiki is already promote-gated,
    # and chetana.promote now redacts new atoms before write_trusted.
    admitted_paths: list[Path] = []
    skipped_secret_files = 0
    scan_error_files = 0
    for text_path in text_paths:
        try:
            file_text = Path(text_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            scan_error_files += 1
            continue
        file_scan = scan_text_for_write(file_text)
        if file_scan.quarantined:
            scan_error_files += 1
            continue
        if file_scan.has_secret:
            skipped_secret_files += 1
            continue
        admitted_paths.append(Path(text_path))
    backfill = backfill_memory_sources(
        state_dir=resolved_state_dir,
        memory_jsonl_paths=(),
        agents_context_paths=(),
        text_file_paths=admitted_paths,
        state_path=resolved_state_dir / "vector_memory_sources_backfill_state.json",
        dim=dim,
        dry_run=False,
    )
    sync = sync_memory_retrieval_index(
        state_dir=resolved_state_dir,
        dim=dim,
        recent_row_window=1_000_000,
        full_scan=False,
    )
    reembed = reembed_queries(
        state_dir=resolved_state_dir,
        queries=(),
        limit_per_query=1,
        dim=dim,
        include_memory_retrieval_docs=True,
        memory_doc_limit=max(1_000, len(admitted_paths) * 4),
        replace_embedder_corpus=True,
        dry_run=False,
    )
    return WikiVectorIngestReceipt(
        state_dir=str(resolved_state_dir),
        wiki_concepts_dir=str(resolved_wiki_dir),
        discovered_files=len(text_paths),
        backfill=backfill.to_json(),
        sync_index=sync.to_json(),
        reembed=reembed.to_json(),
        skipped_secret_files=skipped_secret_files,
        scan_error_files=scan_error_files,
    )
