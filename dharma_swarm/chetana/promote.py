"""chetana.promote — staged → trusted.

The single bottleneck through which all atoms must pass to become trusted.
Every promote call:

    1. Reads the staged atom (frontmatter + body).
    2. Validates the frontmatter against the chetana schema.
    3. Runs gate_check_atom() — telos gates on the body content.
    4. On BLOCK: writes a rejected-atom audit row, leaves the staged file alone.
    5. On WARN: writes the trusted atom with review_status='staged' (still needs human approval).
    6. On ALLOW with auto_promote=True: writes review_status='auto_promoted'.
    7. On ALLOW with auto_promote=False (default): writes review_status='staged'.
    8. Computes axiom_signature, sets provenance.promoted_at + promoted_by.
    9. Writes the trusted file to ~/.dharma/knowledge/wiki/concepts/<slug>.md
   10. Deletes the staging file iff write succeeded AND result != BLOCK.
   11. Returns PromoteResult with paths + decision.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import staging as staging_mod
from ..daemon_config import dharma_state_dir
from ..redaction import scan_text_for_write
from .cross_update import cross_update_trusted
from .governance import gate_check_atom
from .provenance import (
    GateResult,
    ReviewStatus,
    parse_frontmatter,
)
from .staging import quarantine_atom, write_trusted
from .stigmergy_emit import emit_mark
from .wiki_log import append_wiki_log

logger = logging.getLogger(__name__)


@dataclass
class PromoteResult:
    staged_path: Path
    trusted_path: Path | None
    decision: GateResult
    review_status: ReviewStatus | None
    rationale: str | None = None
    notes: list[str] = field(default_factory=list)


def promote(
    *,
    staged_path: Path,
    promoted_by: str = "chetana.promote",
    reviewer: str | None = None,
    auto_promote: bool = False,
    confidence_override: float | None = None,
) -> PromoteResult:
    """Promote a staged atom to the trusted wiki layer.

    See module docstring for the full state machine. Returns a PromoteResult
    even on BLOCK (with trusted_path=None and the rationale).
    """
    staged_path = Path(staged_path).resolve()
    if not staged_path.exists():
        raise FileNotFoundError(staged_path)
    _require_staged_path(staged_path)

    raw = staged_path.read_text(encoding="utf-8")
    schema, body = parse_frontmatter(raw)
    if schema is None:
        raise ValueError(
            f"staged atom has no chetana frontmatter: {staged_path} "
            f"(use chetana.ingest first)"
        )
    if schema.provenance is not None:
        raise ValueError(
            f"staged atom already has provenance set; refusing double-promote: {staged_path}"
        )
    if confidence_override is not None:
        schema = schema.model_copy(update={"confidence": confidence_override})

    # Secret/PII scan BEFORE gates so the gate check, axiom signature, and the
    # trusted write all see the exact body that persists. Scanner error =
    # quarantine lane; raw body never reaches the trusted projection.
    scan = scan_text_for_write(body)
    if scan.quarantined:
        rejected_path = quarantine_atom(staged_path)
        return PromoteResult(
            staged_path=staged_path,
            trusted_path=None,
            decision="BLOCK",
            review_status="rejected",
            rationale="redaction scan error — atom quarantined, raw body not persisted",
            notes=[f"redaction scanner failed; staged atom moved to {rejected_path}"],
        )
    redaction_notes: list[str] = []
    if scan.sensitive_count:
        body = scan.text
        if "pii_risk:high" not in schema.tags:
            schema = schema.model_copy(update={"tags": [*schema.tags, "pii_risk:high"]})
        redaction_notes.append(
            f"redaction: {scan.sensitive_count} sensitive span(s) redacted; pii_risk=high"
        )

    gov = gate_check_atom(
        atom_content=body,
        atom_title=schema.title,
        requested_action="chetana.promote",
        metadata={"atom_id": schema.atom_id, "atom_type": schema.type},
    )

    notes: list[str] = list(redaction_notes)
    if gov.result == "BLOCK":
        # Move to a rejected/ folder for audit, do NOT write to trusted.
        rejected_path = quarantine_atom(staged_path)
        notes.append(
            f"BLOCKED by gates {gov.record.gates_blocked}; staged atom moved to {rejected_path}"
        )
        return PromoteResult(
            staged_path=staged_path,
            trusted_path=None,
            decision="BLOCK",
            review_status="rejected",
            rationale=gov.record.rationale,
            notes=notes,
        )

    review_status: ReviewStatus
    if gov.result == "WARN":
        review_status = "staged"
    elif gov.result == "ALLOW":
        review_status = "auto_promoted" if auto_promote else "staged"
    else:  # pragma: no cover — defensive
        review_status = "staged"

    promoted_schema = schema.model_copy(
        update={
            "provenance": gov.to_provenance(
                promoted_by=promoted_by,
                review_status=review_status,
                reviewer=reviewer,
            )
        }
    )

    trusted_path = write_trusted(promoted_schema, body)
    notes.append(f"promoted ({gov.result}, review={review_status}) → {trusted_path}")
    try:
        log_path = append_wiki_log(
            operation="promote",
            title=schema.title,
            atom_path=trusted_path,
            atom_id=schema.atom_id,
        )
        notes.append(f"log appended → {log_path}")
    except OSError as e:
        notes.append(f"log append failed: {e}")
    try:
        cross = cross_update_trusted(trusted_path)
        notes.append(
            "cross-update: "
            f"backlinks={len(cross.backlinks_updated)}, "
            f"missing_related={len(cross.missing_related)}, "
            f"contradictions={len(cross.contradictions_flagged)}"
        )
    except Exception as e:
        notes.append(f"cross-update failed: {type(e).__name__}: {e}")

    if _wiki_vector_auto_ingest_enabled():
        try:
            from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts

            receipt = ingest_wiki_concepts(
                state_dir=_wiki_vector_state_dir_for_trusted_path(trusted_path),
                wiki_concepts_dir=trusted_path.parent,
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

    result = PromoteResult(
        staged_path=staged_path,
        trusted_path=trusted_path,
        decision=gov.result,
        review_status=review_status,
        rationale=gov.record.rationale,
        notes=notes,
    )

    # Best-effort stigmergy emit — never blocks promotion on failure.
    emit_mark(
        action="chetana.promote",
        content=f"{schema.title} | {result.decision}",
        connections=["chetana", "promote", schema.type, result.review_status or "staged"],
        salience=schema.confidence,
    )

    # Successful promote → remove the staged file.
    try:
        staged_path.unlink()
    except OSError as e:
        logger.warning("failed to unlink staged atom %s: %s", staged_path, e)

    return result


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


def _wiki_vector_auto_ingest_enabled() -> bool:
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
