"""Private trusted-write helpers shared by promote() and approve_atom().

Moved verbatim out of ``chetana/promote.py`` (PR #1135 repair round) to keep
that module inside the repo's 500-line budget. These helpers are part of the
promotion pipeline's implementation, not an API: ``promote.py`` is the only
importer, and the underscore names are preserved so its call sites and the
pipeline's behavior are byte-for-byte unchanged.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import staging as staging_mod
from ..daemon_config import dharma_state_dir
from .provenance import ReviewStatus, compute_axiom_signature_v2


def _resign_v2(schema, body: str, kernel_signature: str):
    """Replace provenance.axiom_signature with the v2 signature of this atom."""
    sig = compute_axiom_signature_v2(schema, body, kernel_signature)
    return schema.model_copy(
        update={"provenance": schema.provenance.model_copy(update={"axiom_signature": sig})}
    )


def _admit_to_manifest(trusted_path: Path, notes: list[str]) -> None:
    """Admit a freshly approved file into the signed wiki trust manifest.

    Only appends to an already-valid manifest: creating a fresh manifest here
    would implicitly demote every legacy page to untrusted. Failure is
    recorded, never raised — approval stands; searchability is the
    recoverable part (re-run OP-3 signing).
    """
    try:
        from .manifest import (
            load_manifest,
            manifest_entry_for_file,
            manifest_path_for_root,
            write_manifest,
        )

        root = trusted_path.parent
        manifest = load_manifest(root)
        if not manifest.valid:
            notes.append(
                "manifest admission skipped: no valid signed manifest at "
                f"{root} (run OP-3 signing; approved file stays outside the "
                "manifest until then)"
            )
            return
        entries = dict(manifest.entries)
        entry = manifest_entry_for_file(
            trusted_path,
            root=root,
            tier="trusted",
            reasons=("chetana.approve_atom",),
        )
        entries[entry.path] = entry
        write_manifest(
            tuple(entries[key] for key in sorted(entries)),
            manifest_file=manifest_path_for_root(root),
        )
        notes.append(f"manifest admitted {entry.path} (tier=trusted)")
    except Exception as e:
        notes.append(
            f"manifest admission failed: {type(e).__name__}: {e} — approved "
            "file stays outside the manifest until OP-3 re-sign"
        )


def _auto_ingest_file(trusted_path: Path, notes: list[str]) -> None:
    """Best-effort vector ingest of ONE approved file (never the whole dir)."""
    try:
        from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts

        receipt = ingest_wiki_concepts(
            state_dir=_wiki_vector_state_dir_for_trusted_path(trusted_path),
            wiki_concepts_dir=trusted_path,
        )
        notes.append(
            "wiki-vector ingest: "
            f"discovered={receipt.discovered_files}, "
            f"inserted={receipt.backfill.get('inserted_rows')}, "
            f"indexed={receipt.sync_index.get('indexed_rows')}, "
            f"reembedded={receipt.reembed.get('upserted_rows')}"
        )
    except Exception as e:
        notes.append(f"wiki-vector ingest failed: {type(e).__name__}: {e}")


def _require_staged_path(path: Path) -> None:
    """Require promote inputs to originate from the configured staging root."""
    staging_root = staging_mod.STAGING_ROOT.resolve()
    try:
        path.relative_to(staging_root)
    except ValueError as exc:
        raise ValueError(
            f"refusing to promote path outside chetana staging root: {path} "
            f"(staging root: {staging_root})"
        ) from exc


def _wiki_vector_auto_ingest_enabled(review_status: ReviewStatus | None) -> bool:
    # Hard gate: non-approved content never reaches the vector projection,
    # regardless of env. The env flag only opts approved atoms out.
    if review_status != "approved":
        return False
    value = os.environ.get("DHARMA_WIKI_VECTOR_AUTO_INGEST", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _wiki_vector_state_dir_for_trusted_path(path: Path) -> Path:
    for parent in (path, *path.parents):
        if parent.name == ".dharma":
            return parent
    try:
        return path.parent.parent.parent
    except IndexError:
        return dharma_state_dir()
