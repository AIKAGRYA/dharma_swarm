"""chetana.promote — staged → pending → trusted.

The single bottleneck through which all atoms must pass to become trusted.
Every promote call:

    1. Reads the staged atom (frontmatter + body).
    2. Validates the frontmatter against the chetana schema.
    3. Runs gate_check_atom() — telos gates on the body content.
    4. On BLOCK: writes a rejected-atom audit row, leaves the staged file alone.
    5. On WARN: writes the atom with review_status='staged' (still needs human approval).
    6. On ALLOW with auto_promote=True: writes review_status='auto_promoted'.
    7. On ALLOW with auto_promote=False (default): writes review_status='staged'.
    8. Computes axiom_signature (v2: frontmatter + body), sets provenance.
    9. Writes the atom. Anything not review_status='approved' lands in the
       PENDING root (~/.dharma/knowledge/wiki/pending/), NEVER in the trusted
       projection (~/.dharma/knowledge/wiki/concepts/). Only approve_atom()
       moves an atom into the trusted dir.
   10. Deletes the staging file iff write succeeded AND result != BLOCK.
   11. Returns PromoteResult with paths + decision.

approve_atom() is the ONLY door into the trusted projection: it flips
review_status to 'approved', re-signs (v2 covers review_status), moves the file
from pending/staging into concepts/, and only then runs cross-update + the
vector auto-ingest (scoped to the approved file).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import staging as staging_mod
from ..daemon_config import dharma_state_dir
from .cross_update import cross_update_trusted
from .governance import current_kernel_signature, gate_check_atom
from .provenance import (
    SIGNATURE_V2_PREFIX,
    GateResult,
    ReviewStatus,
    assemble_atom,
    compute_axiom_signature_v2,
    now_iso,
    parse_frontmatter,
    signature_matches,
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

    gov = gate_check_atom(
        atom_content=body,
        atom_title=schema.title,
        requested_action="chetana.promote",
        metadata={"atom_id": schema.atom_id, "atom_type": schema.type},
    )

    notes: list[str] = []
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
    promoted_schema = _resign_v2(promoted_schema, body, gov.kernel_signature)

    # Non-approved atoms NEVER enter the trusted projection — they land in the
    # pending root and wait for approve_atom(). promote() can only produce
    # staged/auto_promoted, so this always routes to pending today; the guard
    # is on review_status so a future approved-at-promote path stays correct.
    pending = review_status != "approved"
    target_root = staging_mod.WIKI_PENDING_ROOT if pending else None
    trusted_path = write_trusted(promoted_schema, body, root=target_root)
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
    if pending:
        # Cross-update writes index/backlinks — the trusted projection. Staged
        # content must not appear there; deferred to approve_atom().
        notes.append("cross-update deferred until approval (atom is pending)")
    else:
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

    if _wiki_vector_auto_ingest_enabled(review_status):
        _auto_ingest_file(trusted_path, notes)
    elif pending:
        notes.append("wiki-vector ingest skipped (review_status != approved)")

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


@dataclass
class ApproveResult:
    decision: str  # APPROVED | ALREADY_APPROVED | REJECTED_PRIOR | BAD_STATE | NOT_FOUND | NEEDS_PROMOTE | PARSE_ERROR | SIGNATURE_MISMATCH | GATE_BLOCKED | COLLISION
    trusted_path: Path | None = None
    prior_status: str | None = None
    reviewer: str | None = None
    error: str | None = None
    notes: list[str] = field(default_factory=list)


def approve_atom(*, path: Path | str, reviewer: str) -> ApproveResult:
    """Human-explicit approval — the ONLY door into the trusted projection.

    Accepts a pending atom (wiki/pending/), a staged-with-provenance atom, or
    an already-trusted atom whose review_status is staged|auto_promoted.
    Before flipping anything it re-verifies the promote-time v2 signature
    (pending files are agent-writable — a body edited after promote must not
    ride an operator's approval into trusted) and re-runs the telos gates on
    the bytes actually being approved. Then it flips review_status →
    'approved', re-signs with v2 (which covers review_status), moves the file
    into the trusted dir, then runs cross-update + the (env-gated) vector
    auto-ingest scoped to this file.
    """
    if not reviewer or not str(reviewer).strip():
        return ApproveResult(
            decision="REJECTED", error="reviewer required for approve (no auto-approve)"
        )

    target = Path(path).expanduser()
    if not target.exists():
        # Resolve bare atom ids / slugs under staging first, then pending.
        # Only simple names: rglob raises NotImplementedError on absolute
        # patterns, and a path-shaped miss should be NOT_FOUND, not a search.
        raw = str(path)
        if not Path(raw).is_absolute() and "/" not in raw and os.sep not in raw:
            candidates: list[Path] = []
            if staging_mod.STAGING_ROOT.exists():
                candidates = list(staging_mod.STAGING_ROOT.rglob(f"{raw}.md"))
            if not candidates and staging_mod.WIKI_PENDING_ROOT.exists():
                candidates = list(staging_mod.WIKI_PENDING_ROOT.rglob(f"{raw}.md"))
            if candidates:
                target = candidates[0]
    if not target.exists():
        return ApproveResult(decision="NOT_FOUND", error=f"{path} not found")
    target = target.resolve()

    text = target.read_text(encoding="utf-8")
    try:
        schema, body = parse_frontmatter(text, source_path=str(target))
    except Exception as e:
        return ApproveResult(decision="PARSE_ERROR", error=f"parse failed: {e}")

    if schema is None or schema.provenance is None:
        return ApproveResult(
            decision="NEEDS_PROMOTE", error="atom has no provenance — promote first"
        )

    current_status = schema.provenance.review_status
    if current_status == "approved":
        return ApproveResult(
            decision="ALREADY_APPROVED",
            trusted_path=target,
            reviewer=schema.provenance.reviewer,
        )
    if current_status == "rejected":
        return ApproveResult(
            decision="REJECTED_PRIOR",
            trusted_path=target,
            error="atom was rejected; cannot approve a rejected atom",
        )
    if current_status not in ("staged", "auto_promoted"):
        return ApproveResult(
            decision="BAD_STATE",
            prior_status=current_status,
            error=f"unexpected review_status '{current_status}'",
        )

    # The pending file sat in an agent-writable dir since promote. Verify the
    # promote-time signature before trusting its bytes. v2 is required here:
    # promote() always signs v2 now, and the kernel signature is readable, so
    # accepting a recomputed v1 (body-only) sig would let tamper+downgrade
    # pass this boundary.
    kernel_sig = current_kernel_signature()
    stored_sig = schema.provenance.axiom_signature or ""
    if not stored_sig.startswith(SIGNATURE_V2_PREFIX):
        return ApproveResult(
            decision="SIGNATURE_MISMATCH",
            prior_status=current_status,
            error=(
                "stored axiom_signature is not v2; promote() signs v2 — "
                "refusing approval (possible v1 downgrade; re-promote the atom)"
            ),
        )
    if not signature_matches(stored_sig, schema, body, kernel_sig):
        return ApproveResult(
            decision="SIGNATURE_MISMATCH",
            prior_status=current_status,
            error=(
                "axiom_signature does not verify under the current kernel — "
                "content changed after promote (or the kernel rotated); re-promote"
            ),
        )

    # Signatures are forgeable by anything that can read the kernel manifest,
    # so re-run the gates on the exact bytes being approved — a body swapped
    # in after promote must face the same battery it dodged.
    gov = gate_check_atom(
        atom_content=body,
        atom_title=schema.title,
        requested_action="chetana.approve",
        metadata={"atom_id": schema.atom_id, "atom_type": schema.type},
    )
    if gov.result == "BLOCK":
        return ApproveResult(
            decision="GATE_BLOCKED",
            prior_status=current_status,
            error=(
                "telos gates BLOCK at approve: "
                f"{gov.record.rationale or gov.record.gates_blocked}"
            ),
        )

    approval_entry = {
        "event": "approve",
        "ts": now_iso(),
        "reviewer": reviewer,
        "prior_status": current_status,
    }
    new_provenance = schema.provenance.model_copy(
        update={
            "review_status": "approved",
            "reviewer": reviewer,
            "revival_chain": list(schema.provenance.revival_chain) + [approval_entry],
        }
    )
    new_schema = schema.model_copy(update={"provenance": new_provenance})
    # review_status changed → the v2 signature must be recomputed here, under
    # the current kernel; a bare on-disk flip breaks verification by design.
    new_schema = _resign_v2(new_schema, body, kernel_sig)

    notes: list[str] = []
    movable_roots = (staging_mod.STAGING_ROOT, staging_mod.WIKI_PENDING_ROOT)
    in_movable_root = False
    for root in movable_roots:
        try:
            target.relative_to(root.resolve())
            in_movable_root = True
            break
        except ValueError:
            continue

    if in_movable_root:
        try:
            trusted_path = write_trusted(new_schema, body)
        except FileExistsError as e:
            # Slug collision with an existing trusted/legacy page: fail closed,
            # leave the pending copy untouched for the operator to resolve.
            return ApproveResult(
                decision="COLLISION",
                prior_status=current_status,
                error=str(e),
                notes=[f"pending copy left untouched at {target}"],
            )
        # Bind the unlink to the exact bytes that were verified: if another
        # writer replaced the pending file after the read above, deleting the
        # path would destroy the newer, unverified atom (TOCTOU).
        try:
            if target.read_text(encoding="utf-8") != text:
                notes.append(
                    "pending file changed after verification; "
                    f"left in place at {target} (re-promote to approve the new bytes)"
                )
            else:
                target.unlink()
        except OSError as e:
            notes.append(f"failed to remove source file: {type(e).__name__}: {e}")
    else:
        # In-place approval is only legal inside the trusted projection —
        # approving a file at an arbitrary path would mint 'approved' status
        # for content that never enters concepts/.
        try:
            target.relative_to(staging_mod.TRUSTED_DEFAULT.resolve())
        except ValueError:
            return ApproveResult(
                decision="BAD_STATE",
                prior_status=current_status,
                error=(
                    f"refusing in-place approval outside the trusted dir: {target} "
                    f"(trusted root: {staging_mod.TRUSTED_DEFAULT}); move the atom "
                    "into staging/pending and re-promote"
                ),
            )
        trusted_path = target
        trusted_path.write_text(assemble_atom(new_schema, body), encoding="utf-8")

    try:
        log_path = append_wiki_log(
            operation="approve",
            title=new_schema.title,
            atom_path=trusted_path,
            atom_id=new_schema.atom_id,
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

    if _wiki_vector_auto_ingest_enabled("approved"):
        _auto_ingest_file(trusted_path, notes)

    emit_mark(
        action="chetana.approve",
        content=f"{new_schema.title} | APPROVED",
        connections=["chetana", "approve", new_schema.type, "approved"],
        salience=new_schema.confidence,
    )

    return ApproveResult(
        decision="APPROVED",
        trusted_path=trusted_path,
        prior_status=current_status,
        reviewer=reviewer,
        notes=notes,
    )


def _resign_v2(schema, body: str, kernel_signature: str):
    """Replace provenance.axiom_signature with the v2 signature of this atom."""
    sig = compute_axiom_signature_v2(schema, body, kernel_signature)
    return schema.model_copy(
        update={"provenance": schema.provenance.model_copy(update={"axiom_signature": sig})}
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
