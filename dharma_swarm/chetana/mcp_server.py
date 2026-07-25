"""chetana.mcp_server — MCP server skeleton (stdio transport).

Exposes 9 tools to agents:

    chetana_ingest(source_text, source_kind, para_class) -> {atom_id, staging_path}
    chetana_promote(atom_id, confidence, requester) -> {gate_result, wiki_path, ...}
    chetana_query(question, filters) -> {hits, coverage, notes}
    chetana_gap_scan(focus_topic) -> {gaps, open_questions}
    chetana_decay_check() -> {stale_count, stale_atoms}
    chetana_palace_state() -> {pillar_rooms, total_atoms, coverage_gaps}
    chetana_verify(path, mode) -> {verdict, verdict_reasons, buckets, ...} [Slice 7]
    chetana_revive(path|all, apply, reviewer) -> {proposals, applied}    [Slice 7]
    chetana_approve(path, reviewer_token) -> {decision, trusted_path}    [Slice 7; token-gated]

This is a thin wrapper over the chetana package functions. The server is
launched via `python -m dharma_swarm.chetana.mcp_server` from an .mcp.json
entry. JSON-RPC over stdio per MCP spec.

The server is stub-level: it does not require the `mcp` Python package to
import. When that package is installed and imported successfully, the server
runs on it. Otherwise it prints a setup hint and exits non-zero.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import sys
from pathlib import Path

from .decay import scan_decay
from .gap_scan import gap_scan
from .graph_unifier import query as unified_query
from .ingest import ingest as ingest_fn
from .palace import render_palace
from .promote import promote as promote_fn
from .revival import (
    apply_revival as apply_revival_fn,
    find_due_atoms,
    propose_revival as propose_revival_fn,
)


logger = logging.getLogger(__name__)


def tool_ingest(
    source_text: str,
    source_kind: str = "note",
    title: str | None = None,
    para_class: str | None = None,
    confidence: float = 0.5,
    requester: str = "mcp_caller",
) -> dict:
    result = ingest_fn(
        source=source_text,
        source_kind=source_kind,  # type: ignore[arg-type]
        title=title,
        para_class=para_class,  # type: ignore[arg-type]
        confidence=confidence,
        captured_by=requester,
    )
    return {
        "staged_count": result.staged_count,
        "atoms": [str(p) for p in result.atoms],
        "notes": result.notes,
    }


def tool_promote(
    staged_path: str,
    confidence: float | None = None,
    requester: str = "mcp_caller",
) -> dict:
    # No auto_promote from MCP: unauthenticated agent callers must not be able
    # to mint auto_promoted atoms. Promoted atoms land in the pending root
    # until an operator approves them (chetana_approve, token-gated).
    result = promote_fn(
        staged_path=Path(staged_path),
        promoted_by=requester,
        confidence_override=confidence,
    )
    return {
        "decision": result.decision,
        "review_status": result.review_status,
        "trusted_path": str(result.trusted_path) if result.trusted_path else None,
        "rationale": result.rationale,
        "notes": result.notes,
    }


def tool_query(text: str, sources: list[str] | None = None, limit: int = 20) -> dict:
    result = unified_query(text, sources=sources, limit_per_source=limit)
    return {
        "query": result.query,
        "coverage": result.coverage,
        "hits": [
            {
                "source": h.source,
                "kind": h.kind,
                "id": h.id,
                "label": h.label,
            }
            for h in result.hits
        ],
        "notes": result.notes,
    }


def tool_gap_scan(focus_topic: str | None = None, min_occurrences: int = 2) -> dict:
    report = gap_scan(focus_topic=focus_topic, min_occurrences=min_occurrences)
    return {
        "scanned": report.scanned,
        "topic_gaps": [g.__dict__ for g in report.topic_gaps],
        "open_questions": [g.__dict__ for g in report.open_questions],
    }


def tool_decay_check(quarantine: bool = False, grace_days: int = 0) -> dict:
    report = scan_decay(quarantine=quarantine, grace_days=grace_days)
    return {
        "scanned": report.scanned,
        "stale_count": report.stale_count,
        "quarantined": [str(p) for p in report.quarantined],
        "stale_atoms": [
            {
                "path": str(a.path),
                "title": a.title,
                "stale_after": a.stale_after,
                "days_overdue": a.days_overdue,
                "confidence": a.confidence,
            }
            for a in report.stale
        ],
    }


def tool_palace_state() -> dict:
    out, snap = render_palace()
    return {
        "canvas_path": str(out),
        "coverage": snap.coverage,
        "total_atoms": len(snap.atoms),
    }


# ---------------------------------------------------------------------------
# Slice 7 of Plan v3 — verify, revive, approve
# ---------------------------------------------------------------------------
# These tools were exposed as CLI but missing from MCP. They route through the
# same underlying functions the CLI uses. No auto-approve without explicit
# reviewer (per v3 acceptance criteria).


def _current_kernel_signature() -> str:
    """Load the current kernel signature without nesting an event loop."""
    placeholder = "0" * 64
    try:
        from dharma_swarm.dharma_kernel import DharmaKernel, KernelGuard  # type: ignore

        kernel_path = KernelGuard().path
        text = kernel_path.read_text(encoding="utf-8")
        kernel = DharmaKernel.model_validate_json(text)
        if kernel.verify_integrity() and kernel.signature:
            return kernel.signature
    except Exception:
        pass
    return placeholder


def tool_verify(path: str | None = None, mode: str = "compat") -> dict:
    """Round-trip axiom signatures against the current kernel.

    Args:
        path: Optional atom path. If None or ".", verifies all trusted atoms.
        mode: "compat" (verdict fails only on zero-sig/schema-error — the
            legacy rule) or "production" (fail-closed: verdict also fails on
            no-provenance, kernel-drift, unapproved review_status, an
            approved atom on a forgeable v1 signature, an unavailable
            kernel, or an empty scan).

    Returns the five signature buckets (verified, zero-sig, kernel-drift,
    no-provenance, schema-error) plus the overlapping ``unapproved`` list,
    and a ``verdict`` field: "pass" | "fail" with ``verdict_reasons``.
    ``buckets["unapproved"]`` overlaps the five disjoint buckets — never sum
    the bucket lists for a total.
    """
    from .provenance import production_verdict, scan_verify_targets
    from .staging import list_trusted

    if mode not in {"compat", "production"}:
        raise ValueError(f"unknown verify mode: {mode!r} (expected 'compat' or 'production')")

    current_kernel_sig = _current_kernel_signature()

    projection_empty = False
    if path and path != ".":
        targets = [Path(path).expanduser().resolve()]
    else:
        targets = list_trusted()
        if not targets and list_trusted(apply_manifest=False):
            # mirror of the CLI compat guard: atoms on disk, empty manifest
            # projection — green attestation here would fail open
            projection_empty = True

    buckets, unapproved, v1_approved = scan_verify_targets(
        targets, kernel_signature=current_kernel_sig
    )

    if mode == "production":
        verdict, reasons = production_verdict(
            buckets, unapproved, kernel_signature=current_kernel_sig, v1_approved=v1_approved
        )
    else:
        reasons = [
            f"{label}: {len(buckets[label])}"
            for label in ("zero-sig", "schema-error")
            if buckets[label]
        ]
        if projection_empty:
            reasons.append("empty-manifest-projection")
        verdict = "pass" if not reasons else "fail"

    return {
        "kernel_signature": current_kernel_sig,
        "mode": mode,
        "verdict": verdict,
        "verdict_reasons": reasons,
        "verified_count": len(buckets["verified"]),
        "zero_sig_count": len(buckets["zero-sig"]),
        "kernel_drift_count": len(buckets["kernel-drift"]),
        "no_provenance_count": len(buckets["no-provenance"]),
        "schema_error_count": len(buckets["schema-error"]),
        "unapproved_count": len(unapproved),
        "v1_signed_approved_count": len(v1_approved),
        "buckets": {**buckets, "unapproved": unapproved},
    }


def tool_revive(
    path: str | None = None,
    all_due: bool = False,
    apply: bool = False,
    reviewer: str = "mcp_caller",
    extend_days: int = 90,
    grace_days: int = 0,
) -> dict:
    """Propose (or apply) revival for stale atoms.

    Args:
        path: A specific atom path to revive (ignored when all_due=True).
        all_due: If True, revive all due-for-revival atoms across the corpus.
        apply: If True, write the revived atom; otherwise return proposals only.
        reviewer: Who is performing the revival (recorded in revival_chain).
        extend_days: How far to push the new stale_after.
        grace_days: Grace window when collecting due atoms.
    """
    if all_due:
        targets = find_due_atoms(grace_days=grace_days)
    else:
        if not path:
            return {"error": "either path or all_due=True required"}
        targets = [Path(path).expanduser().resolve()]

    proposals: list[dict] = []
    applied: list[str] = []
    skipped: list[dict] = []
    for t in targets:
        try:
            p = propose_revival_fn(atom_path=t, extend_days=extend_days)
        except Exception as e:
            skipped.append({"path": str(t), "reason": str(e)})
            continue
        proposals.append({
            "atom_path": str(p.atom_path),
            "title": getattr(p, "title", ""),
            "extend_to": getattr(p, "extend_to", ""),
        })
        if apply:
            try:
                new_path = apply_revival_fn(p, reviewer=reviewer)
                applied.append(str(new_path))
            except Exception as e:
                skipped.append({"path": str(t), "reason": f"apply failed: {e}"})

    return {
        "proposed_count": len(proposals),
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "proposals": proposals,
        "applied": applied,
        "skipped": skipped,
    }


REVIEWER_TOKEN_ENV = "DHARMA_CHETANA_REVIEWER_TOKEN"


def tool_approve(path: str, reviewer_token: str, reviewer: str = "") -> dict:
    """Operator-token-gated approval transitioning staged/pending → approved.

    Authorization comes ONLY from ``reviewer_token`` matching the operator-set
    DHARMA_CHETANA_REVIEWER_TOKEN env var; token unset ⇒ approval via MCP is
    disabled entirely (fail closed). ``reviewer`` is an optional display name
    recorded in provenance so the approval trail keeps a human identity — it
    grants nothing.
    """
    expected = os.environ.get(REVIEWER_TOKEN_ENV, "")
    if not expected.strip():
        return {
            "error": f"approve disabled: {REVIEWER_TOKEN_ENV} is not configured",
            "decision": "REJECTED",
        }
    if not reviewer_token or not hmac.compare_digest(
        reviewer_token.encode("utf-8"), expected.encode("utf-8")
    ):
        return {"error": "invalid reviewer token", "decision": "REJECTED"}

    from .promote import approve_atom

    name = (reviewer or "").strip()
    recorded = f"operator-token:{name}" if name else "operator-token"
    try:
        result = approve_atom(path=path, reviewer=recorded)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "decision": "ERROR"}
    return {
        "decision": result.decision,
        "prior_status": result.prior_status,
        "reviewer": result.reviewer,
        "trusted_path": str(result.trusted_path) if result.trusted_path else None,
        "error": result.error,
        "notes": result.notes,
    }


TOOL_REGISTRY = {
    "chetana_ingest": tool_ingest,
    "chetana_promote": tool_promote,
    "chetana_query": tool_query,
    "chetana_gap_scan": tool_gap_scan,
    "chetana_decay_check": tool_decay_check,
    "chetana_palace_state": tool_palace_state,
    "chetana_verify": tool_verify,
    "chetana_revive": tool_revive,
    "chetana_approve": tool_approve,
}

TOOL_SCHEMAS: dict[str, dict] = {
    "chetana_ingest": {
        "type": "object",
        "properties": {
            "source_text": {"type": "string"},
            "source_kind": {
                "type": "string",
                "enum": [
                    "session",
                    "webclip",
                    "pdf",
                    "note",
                    "wiki_extract",
                    "voice",
                    "external",
                    "synthesis",
                ],
                "default": "note",
            },
            "title": {"type": "string"},
            "para_class": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
            "requester": {"type": "string", "default": "mcp_caller"},
        },
        "required": ["source_text"],
        "additionalProperties": False,
    },
    "chetana_promote": {
        "type": "object",
        "properties": {
            "staged_path": {
                "type": "string",
                "description": "Path to a staged atom under ~/.dharma/knowledge/staging.",
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "requester": {"type": "string", "default": "mcp_caller"},
        },
        "required": ["staged_path"],
        "additionalProperties": False,
    },
    "chetana_query": {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "sources": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        },
        "required": ["text"],
        "additionalProperties": False,
    },
    "chetana_gap_scan": {
        "type": "object",
        "properties": {
            "focus_topic": {"type": "string"},
            "min_occurrences": {"type": "integer", "minimum": 1, "default": 2},
        },
        "additionalProperties": False,
    },
    "chetana_decay_check": {
        "type": "object",
        "properties": {
            "quarantine": {"type": "boolean", "default": False},
            "grace_days": {"type": "integer", "minimum": 0, "default": 0},
        },
        "additionalProperties": False,
    },
    "chetana_palace_state": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "chetana_verify": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Specific atom path; omit or '.' to verify all trusted atoms.",
            },
            "mode": {
                "type": "string",
                "enum": ["compat", "production"],
                "default": "compat",
                "description": (
                    "compat: verdict fails only on zero-sig/schema-error. "
                    "production: fail-closed (also fails on no-provenance, "
                    "kernel-drift, unapproved review_status, v1-signed "
                    "approved atoms, unavailable kernel, or an empty scan)."
                ),
            },
        },
        "additionalProperties": False,
    },
    "chetana_revive": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Atom path to revive (ignored if all_due=true)."},
            "all_due": {"type": "boolean", "default": False, "description": "Revive all due atoms."},
            "apply": {"type": "boolean", "default": False, "description": "Write revived atoms (vs propose-only)."},
            "reviewer": {"type": "string", "default": "mcp_caller"},
            "extend_days": {"type": "integer", "minimum": 1, "default": 90},
            "grace_days": {"type": "integer", "minimum": 0, "default": 0},
        },
        "additionalProperties": False,
    },
    "chetana_approve": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to pending/staged atom needing operator approval.",
            },
            "reviewer_token": {
                "type": "string",
                "description": (
                    "REQUIRED: operator token matching DHARMA_CHETANA_REVIEWER_TOKEN. "
                    "Approval is disabled when the env var is unset."
                ),
            },
            "reviewer": {
                "type": "string",
                "description": (
                    "Optional display name recorded in provenance as "
                    "'operator-token:<name>'. Grants nothing; the token authorizes."
                ),
            },
        },
        "required": ["path", "reviewer_token"],
        "additionalProperties": False,
    },
}


def main() -> int:
    """Run the MCP server over stdio.

    Requires the `mcp` Python package. If unavailable, print a one-liner
    install hint and exit non-zero.
    """
    try:
        from mcp.server import Server  # type: ignore
        from mcp.server.stdio import stdio_server  # type: ignore
        import asyncio
    except ImportError:
        print(
            json.dumps(
                {
                    "error": "mcp package not installed. install with: pip install mcp"
                }
            ),
            file=sys.stderr,
        )
        return 1

    server = Server("chetana")  # type: ignore[no-untyped-call]

    @server.list_tools()  # type: ignore[misc]
    async def _list_tools():
        from mcp.types import Tool  # type: ignore

        return [
            Tool(name=name, description=f"chetana - {name}", inputSchema=TOOL_SCHEMAS[name])
            for name in TOOL_REGISTRY
        ]

    @server.call_tool()  # type: ignore[misc]
    async def _call_tool(name: str, arguments: dict | None):
        fn = TOOL_REGISTRY.get(name)
        if fn is None:
            raise ValueError(f"unknown tool: {name}")
        try:
            result = fn(**(arguments or {}))
        except Exception as e:
            return [{"type": "text", "text": json.dumps({"error": str(e)})}]
        return [{"type": "text", "text": json.dumps(result)}]

    async def _run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
