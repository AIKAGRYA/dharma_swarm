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

from . import staging as staging_mod

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

    `sources` is a subset of {"wiki", "memory", "gitnexus", "contextplus", "catalytic"}.
    Defaults to all available. Backends that are unreachable contribute 0 hits
    plus a note.
    """
    sources = sources or ["wiki", "memory", "gitnexus", "contextplus", "catalytic"]
    result = UnifiedQueryResult(query=text)

    if "wiki" in sources:
        hits, note = _query_wiki(text, limit=limit_per_source)
        result.hits.extend(hits)
        result.coverage["wiki"] = len(hits)
        if note:
            result.notes.append(f"wiki: {note}")

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


def _query_wiki(text: str, *, limit: int) -> tuple[list[GraphHit], str | None]:
    # W2 (2026-06-07; fairness-fixed 2026-06-08; coverage-fixed 2026-06-08):
    # query EVERY tier under WIKI_ROOT, not a hardcoded 4. concepts/ holds ~4900
    # files; iterating it first under a single shared limit starved the smaller
    # tiers (any query with >=limit concept matches returned zero atoms). Scan
    # each root independently (capped at `limit`), then round-robin merge so every
    # matching tier is represented near the top. The earlier fix only listed
    # concepts/atoms/mocs/inter_agent, which silently dropped ~308 real pages
    # (connections/ ~258, _meta/ ~36, raw/, tooling/, and the root-level files
    # incl. the canonical 3.6MB index.md). Roots are now derived from the live
    # directory layout so new tiers appear automatically and none can be starved.
    if not isinstance(text, str):
        return [], "non-string query"
    if limit <= 0:
        return [], f"limit must be positive (got {limit})"
    wiki_root = staging_mod.WIKI_ROOT
    if not wiki_root.exists():
        return [], f"no wiki roots present under {wiki_root}"
    # concepts/ (TRUSTED_DEFAULT) keeps priority; every other top-level dir is a
    # peer tier and they round-robin together so no curated tier is starved. The
    # wiki_root sentinel (non-recursive top-level files) is NOT a co-equal tier:
    # its contents are uncurated operator scratch, so it is drained as a
    # low-priority tail only after every curated tier is exhausted.
    trusted = staging_mod.TRUSTED_DEFAULT
    subdirs = sorted(
        p for p in wiki_root.iterdir() if p.is_dir() and p != trusted
    )
    curated_roots = [r for r in [trusted, *subdirs] if r.exists()]
    if not curated_roots and not wiki_root.exists():
        return [], f"no wiki roots present under {wiki_root}"
    needles = [part for part in text.lower().split() if part]
    if not needles:
        # Empty/whitespace query: all(... for needle in []) is True, which would
        # match every file. Treat as a no-op rather than flooding the results.
        return [], "empty query"

    # Generated/operational aggregates live at the wiki root: index.md is an
    # auto-built concatenation of every page (~3.6MB), log.md is an append-only
    # session log (~5MB and growing), contradictions.md is a generated digest.
    # They substring-match almost any query, carry no answer, and the two large
    # ones dominate read cost on every miss. Never return them as content hits.
    ROOT_AGGREGATE_DENYLIST = {"index.md", "log.md", "contradictions.md"}
    # Belt-and-suspenders against a future un-denylisted aggregate: genuine
    # curated pages top out around 60KB, so a root-level file above this is an
    # aggregate/dump, not content. Bounds worst-case read cost as log.md grows.
    ROOT_FILE_SIZE_CAP = 512 * 1024

    def _scan(root):
        found: list[GraphHit] = []
        # The wiki_root sentinel scans only its top-level files (glob, not rglob)
        # so it does not double-count files already covered by the subdir tiers.
        is_root_tier = root == wiki_root
        paths = root.glob("*.md") if is_root_tier else root.rglob("*.md")
        for path in sorted(paths):
            if is_root_tier:
                if path.name in ROOT_AGGREGATE_DENYLIST:
                    continue
                try:
                    if path.stat().st_size > ROOT_FILE_SIZE_CAP:
                        continue
                except OSError:
                    continue
            try:
                raw = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            haystack = raw.lower()
            if not all(needle in haystack for needle in needles):
                continue
            title = _extract_title(raw) or path.stem.replace("-", " ").title()
            try:
                rel = path.relative_to(staging_mod.WIKI_ROOT)
            except ValueError:
                rel = path
            found.append(
                GraphHit(
                    source="wiki",
                    kind="page",
                    id=rel.as_posix(),
                    label=title,
                    payload={"path": str(path)},
                )
            )
            if len(found) >= limit:
                break
        return found

    per_curated = [_scan(root) for root in curated_roots]
    hits: list[GraphHit] = []
    depth = 0
    # Round-robin across curated tiers first (anti-starvation fairness).
    while len(hits) < limit and any(depth < len(found) for found in per_curated):
        for found in per_curated:
            if depth < len(found):
                hits.append(found[depth])
                if len(hits) >= limit:
                    break
        depth += 1
    # Drain the uncurated root-file tail only if curated tiers left room.
    if len(hits) < limit:
        for hit in _scan(wiki_root):
            hits.append(hit)
            if len(hits) >= limit:
                break
    return hits, None


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


def _git_toplevel() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0:
        return None
    root = proc.stdout.strip()
    return root or None


def _parse_gitnexus_query_stdout(stdout: str) -> dict[str, Any] | None:
    """gitnexus query prints optional bunyan logs, then a JSON object."""
    text = stdout.strip()
    if not text:
        return None
    candidates: list[str] = [text]
    lines = text.splitlines()
    if len(lines) > 1:
        candidates.append("\n".join(lines[1:]).strip())
        candidates.append(lines[0])
    for blob in candidates:
        if not blob:
            continue
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and (
            "processes" in data or "definitions" in data or "process_symbols" in data
        ):
            return data
    return None


def _hit_from_gitnexus_row(row: dict[str, Any], *, default_kind: str) -> GraphHit:
    return GraphHit(
        source="gitnexus",
        kind=str(row.get("kind") or row.get("type") or default_kind),
        id=str(row.get("id") or row.get("uid") or row.get("name") or "?"),
        label=str(row.get("name") or row.get("label") or row.get("id") or "?"),
        payload=row,
    )


def _query_gitnexus(text: str, *, limit: int) -> tuple[list[GraphHit], str | None]:
    """Best-effort gitnexus call. Skips silently if the CLI isn't available."""
    bin_check = subprocess.run(
        ["which", "gitnexus"], capture_output=True, text=True, timeout=2
    )
    if bin_check.returncode != 0:
        return [], "gitnexus CLI not found"
    cmd = ["gitnexus", "query", text, "--limit", str(limit)]
    repo = _git_toplevel()
    if repo:
        cmd.extend(["--repo", repo])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return [], f"call failed: {e}"
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return [], f"exit {proc.returncode}: {err[:160]}"
    data = _parse_gitnexus_query_stdout(proc.stdout)
    if data is None:
        return [], "json error: no query payload"

    hits: list[GraphHit] = []
    for row in data.get("definitions") or []:
        if isinstance(row, dict):
            hits.append(_hit_from_gitnexus_row(row, default_kind="symbol"))
        if len(hits) >= limit:
            break
    if len(hits) < limit:
        for row in data.get("process_symbols") or []:
            if isinstance(row, dict):
                hits.append(_hit_from_gitnexus_row(row, default_kind="symbol"))
            if len(hits) >= limit:
                break
    if len(hits) < limit:
        for row in data.get("processes") or []:
            if isinstance(row, dict):
                hits.append(_hit_from_gitnexus_row(row, default_kind="process"))
            if len(hits) >= limit:
                break

    note = data.get("warning")
    if isinstance(note, str) and note.strip():
        return hits, note.strip()
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


def _extract_title(raw: str) -> str | None:
    for line in raw.splitlines()[:20]:
        if line.startswith("title:"):
            return line.split(":", 1)[1].strip().strip('"')
        if line.startswith("# "):
            return line[2:].strip()
    return None


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
