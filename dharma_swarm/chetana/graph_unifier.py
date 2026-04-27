"""chetana.graph_unifier — single query interface over Dhyana's 4 graphs.

The four graphs:
    1. memory MCP (entities + relations) — semantic, cross-session
    2. gitnexus  (code symbols + relationships) — repo-scope
    3. contextplus (per-repo semantic trees) — repo-scope
    4. catalytic_graph.json (concept lattice) — system-scope

The proliferation IS the problem. chetana does NOT add a 5th graph; it adds a
unified query interface. Each call returns merged results with provenance
(which graph contributed what).

This module is intentionally thin — the actual graph backends are reached via
their existing tools (memory MCP via JSON-RPC, gitnexus/contextplus via CLI,
catalytic_graph via direct JSON read). When a backend is unreachable, its
contribution is empty and the call still returns.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


CATALYTIC_GRAPH_PATH = Path.home() / ".dharma" / "meta" / "catalytic_graph.json"


@dataclass
class GraphHit:
    source: str  # "memory" | "gitnexus" | "contextplus" | "catalytic"
    kind: str  # "entity" | "symbol" | "node" | "edge"
    id: str
    label: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedQueryResult:
    query: str
    hits: list[GraphHit] = field(default_factory=list)
    coverage: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def by_source(self, source: str) -> list[GraphHit]:
        return [h for h in self.hits if h.source == source]


def query(
    text: str,
    *,
    sources: list[str] | None = None,
    limit_per_source: int = 20,
) -> UnifiedQueryResult:
    """Query all configured graph backends, merge results.

    `sources` is a subset of {"memory", "gitnexus", "contextplus", "catalytic"}.
    Defaults to all available. Backends that are unreachable contribute 0 hits
    plus a note.
    """
    sources = sources or ["memory", "gitnexus", "contextplus", "catalytic"]
    result = UnifiedQueryResult(query=text)

    if "catalytic" in sources:
        hits, note = _query_catalytic(text, limit=limit_per_source)
        result.hits.extend(hits)
        result.coverage["catalytic"] = len(hits)
        if note:
            result.notes.append(f"catalytic: {note}")

    if "gitnexus" in sources:
        hits, note = _query_gitnexus(text, limit=limit_per_source)
        result.hits.extend(hits)
        result.coverage["gitnexus"] = len(hits)
        if note:
            result.notes.append(f"gitnexus: {note}")

    if "memory" in sources:
        hits, note = _query_memory(text, limit=limit_per_source)
        result.hits.extend(hits)
        result.coverage["memory"] = len(hits)
        if note:
            result.notes.append(f"memory: {note}")

    if "contextplus" in sources:
        hits, note = _query_contextplus(text, limit=limit_per_source)
        result.hits.extend(hits)
        result.coverage["contextplus"] = len(hits)
        if note:
            result.notes.append(f"contextplus: {note}")

    return result


def _query_catalytic(text: str, *, limit: int) -> tuple[list[GraphHit], str | None]:
    if not CATALYTIC_GRAPH_PATH.exists():
        return [], "catalytic_graph.json missing"
    try:
        data = json.loads(CATALYTIC_GRAPH_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return [], f"parse error: {e}"

    needle = text.lower()
    hits: list[GraphHit] = []
    nodes = data.get("nodes") or {}
    if isinstance(nodes, dict):
        node_iter = nodes.items()
    elif isinstance(nodes, list):
        node_iter = ((n.get("id") or n.get("name") or "?", n) for n in nodes if isinstance(n, dict))
    else:
        node_iter = []

    for node_id, payload in node_iter:
        label = ""
        if isinstance(payload, dict):
            label = str(payload.get("label") or payload.get("name") or node_id)
        else:
            label = str(payload)
        haystack = f"{node_id} {label}".lower()
        if needle in haystack:
            hits.append(
                GraphHit(
                    source="catalytic",
                    kind="node",
                    id=str(node_id),
                    label=label,
                    payload=payload if isinstance(payload, dict) else {"raw": payload},
                )
            )
            if len(hits) >= limit:
                break
    return hits, None


def _query_gitnexus(text: str, *, limit: int) -> tuple[list[GraphHit], str | None]:
    """Best-effort gitnexus call. Skips silently if the CLI isn't available."""
    bin_check = subprocess.run(
        ["which", "gitnexus"], capture_output=True, text=True, timeout=2
    )
    if bin_check.returncode != 0:
        return [], "gitnexus CLI not found"
    try:
        proc = subprocess.run(
            ["gitnexus", "search", "--json", "--limit", str(limit), text],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return [], f"call failed: {e}"
    if proc.returncode != 0:
        return [], f"exit {proc.returncode}: {proc.stderr[:120].strip()}"
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else []
    except Exception as e:
        return [], f"json error: {e}"

    hits: list[GraphHit] = []
    rows = data.get("results", data) if isinstance(data, dict) else data
    if isinstance(rows, list):
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            hits.append(
                GraphHit(
                    source="gitnexus",
                    kind=row.get("type", "symbol"),
                    id=str(row.get("id") or row.get("name") or "?"),
                    label=str(row.get("name") or row.get("label") or "?"),
                    payload=row,
                )
            )
    return hits, None


def _query_memory(text: str, *, limit: int) -> tuple[list[GraphHit], str | None]:
    """Memory MCP not directly reachable from a Python process without an MCP client."""
    return [], (
        "memory MCP query requires MCP client (use chetana.mcp_server tool: "
        "chetana_query) or call mcp__plugin_everything-claude-code_memory__search_nodes "
        "from an agent harness"
    )


def _query_contextplus(text: str, *, limit: int) -> tuple[list[GraphHit], str | None]:
    """contextplus is also typically reached via MCP — same situation as memory."""
    return [], (
        "contextplus query requires MCP client (use chetana.mcp_server tool or "
        "call mcp__contextplus__semantic_code_search from an agent harness)"
    )


def coverage_summary(result: UnifiedQueryResult) -> str:
    lines = [f"# Unified graph query: {result.query!r}", "", "## Coverage"]
    for src, count in sorted(result.coverage.items(), key=lambda x: -x[1]):
        lines.append(f"- {src}: {count}")
    if result.notes:
        lines.append("")
        lines.append("## Notes")
        for n in result.notes:
            lines.append(f"- {n}")
    return "\n".join(lines)
