"""chetana.mcp_server — MCP server skeleton (stdio transport).

Exposes 6 tools to agents:

    chetana_ingest(source_text, source_kind, para_class) -> {atom_id, staging_path}
    chetana_promote(atom_id, confidence, requester) -> {gate_result, wiki_path, ...}
    chetana_query(question, filters) -> {hits, coverage, notes}
    chetana_gap_scan(focus_topic) -> {gaps, open_questions}
    chetana_decay_check() -> {stale_count, stale_atoms}
    chetana_palace_state() -> {pillar_rooms, total_atoms, coverage_gaps}

This is a thin wrapper over the chetana package functions. The server is
launched via `python -m dharma_swarm.chetana.mcp_server` from an .mcp.json
entry. JSON-RPC over stdio per MCP spec.

The server is stub-level: it does not require the `mcp` Python package to
import. When that package is installed and imported successfully, the server
runs on it. Otherwise it prints a setup hint and exits non-zero.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from .decay import scan_decay
from .gap_scan import gap_scan
from .graph_unifier import query as unified_query
from .ingest import ingest as ingest_fn
from .palace import render_palace
from .promote import promote as promote_fn
from .provenance import SourceKind


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
    auto_promote: bool = False,
) -> dict:
    result = promote_fn(
        staged_path=Path(staged_path),
        promoted_by=requester,
        auto_promote=auto_promote,
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


TOOL_REGISTRY = {
    "chetana_ingest": tool_ingest,
    "chetana_promote": tool_promote,
    "chetana_query": tool_query,
    "chetana_gap_scan": tool_gap_scan,
    "chetana_decay_check": tool_decay_check,
    "chetana_palace_state": tool_palace_state,
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
            Tool(name=name, description=f"chetana — {name}", inputSchema={"type": "object"})
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
