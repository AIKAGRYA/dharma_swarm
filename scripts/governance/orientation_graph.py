#!/usr/bin/env python3
"""orientation_graph.py — one-command, whole-system orientation view.

Renders the organism AT ONCE — identity (why), organs, active tracks,
canon custody, liveness, and broken register — as one typed, queryable
packet. A fresh agent should be able to answer "what is this system,
what lives inside it, what is live, what is broken, and what is canon"
from this single command.

This command does NOT own any fact. It projects from the existing owners:

    identity   -> foundations/THE_ORGANISM.md + docs/vision_maps/NORTH_STAR.md
    organs     -> docs/governance/VENTURE_CELL_PORTFOLIO.yaml
    tracks     -> docs/governance/ACTIVE_TRACK.yaml
    custody    -> docs/docops/assertions.yaml (canonical_guard.registered) + git
    liveness   -> live ops census receipt (scripts/runtime/live_ops_census.py)
    broken     -> docs/state/BROKEN_REGISTER.md

Doctrine line that must hold (same as the reconciliation track's):
    Read models project truth from owners; they do not become authority.

Usage:
    python3 scripts/governance/orientation_graph.py          # human view
    python3 scripts/governance/orientation_graph.py --json   # machine packet
    make organism-status                                   # deep read-only view
    python3 scripts/governance/orientation_graph.py --write-context
                                                            # explicit refresh

Write behavior: default and --json never write; --write-context writes only
reports/orientation/repo_context.{json,md}. Exit code: always 0
(informational).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# This projection is read-only by default, and its explicit refresh owns only
# the two context artifacts below.  Disable bytecode before importing any
# repository module so a pristine checkout never gains ignored __pycache__
# files merely by invoking either route. `make organism-status` also exports the
# interpreter-level switch so the policy applies from process start.
sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.a2a.agent_presence import list_agent_presence  # noqa: E402
from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402


def _load_broken_register_parser():
    path = REPO_ROOT / "dharma_swarm/operator_core/onboarding/broken_register.py"
    spec = importlib.util.spec_from_file_location("_dharma_broken_register_orientation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load canonical broken-register parser: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.parse_broken_register


parse_broken_register = _load_broken_register_parser()

ORGANISM_DOC = REPO_ROOT / "foundations/THE_ORGANISM.md"
NORTH_STAR_DOC = REPO_ROOT / "docs/vision_maps/NORTH_STAR.md"
GENOME_SYNTHESIS = REPO_ROOT / "reports/swarm_genome/2026-06-11/SYNTHESIS.md"
PORTFOLIO = REPO_ROOT / "docs/governance/VENTURE_CELL_PORTFOLIO.yaml"
ACTIVE_TRACK = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
ASSERTIONS = REPO_ROOT / "docs/docops/assertions.yaml"
BROKEN_REGISTER = REPO_ROOT / "docs/state/BROKEN_REGISTER.md"
REPO_CONTEXT_DIR = REPO_ROOT / "reports/orientation"
REPO_CONTEXT_JSON = REPO_CONTEXT_DIR / "repo_context.json"
REPO_CONTEXT_MD = REPO_CONTEXT_DIR / "repo_context.md"
A2A_BUS = Path.home() / ".dharma/a2a_bus"
DEPLOY_RECEIPT = Path.home() / ".dharma/ops/deploy_receipt.json"
LANE_MAP = Path.home() / ".dharma/ops/parallel_lane_map.json"


def _normalize_context_path(value: str) -> str:
    """Normalize host-specific absolute paths for portable committed artifacts."""
    if not value:
        return ""
    try:
        path = Path(value).expanduser()
    except Exception:
        return value
    if not path.is_absolute():
        return value
    try:
        return f"$REPO_ROOT/{path.relative_to(REPO_ROOT)}"
    except ValueError:
        pass
    try:
        return f"~/{path.relative_to(Path.home())}"
    except ValueError:
        return "<absolute-path>"


def _is_repo_root_context_path(value: str) -> bool:
    if value in {"$REPO_ROOT", "$REPO_ROOT/."}:
        return True
    try:
        return Path(value).expanduser().resolve() == REPO_ROOT.resolve()
    except (OSError, RuntimeError, ValueError):
        return False


def _census_receipt_path() -> Path | None:
    """Receipt path declared by the census owner (scripts/runtime/live_ops_census.py).

    State-dir knowledge stays in the owner; this view only borrows its
    DEFAULT_OUTPUT constant (which honors DHARMA_STATE_DIR).
    """
    census_src = REPO_ROOT / "scripts/runtime/live_ops_census.py"
    if not census_src.exists():
        return None
    spec = importlib.util.spec_from_file_location("_live_ops_census", census_src)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return Path(module.DEFAULT_OUTPUT)


@dataclass
class Identity:
    one_line: str
    read_first: list[str]
    missing_sources: list[str] = field(default_factory=list)


@dataclass
class Organ:
    id: str
    instrument: str
    status: str
    external_name: str = ""


@dataclass
class Track:
    id: str
    status: str
    serves: str
    owner: str
    owned_surfaces: list[str] = field(default_factory=list)
    complements: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class CustodyReport:
    registered_total: int
    present: int
    missing: list[str] = field(default_factory=list)


@dataclass
class Liveness:
    receipt: str
    generated_at: str = ""
    surfaces: list[dict[str, str]] = field(default_factory=list)


@dataclass
class BrokenItem:
    id: str
    status: str
    title: str


@dataclass
class Loop1Closure:
    """Loop 1 (provider chain + dispatch) closure proof, projected read-only
    from the latest delegation_runs receipt. LIVE only when that receipt
    carries a non-empty provider AND model — the spine dispatch actually
    recorded which brain answered. Owner of the fact: runtime_state's
    delegation_runs.receipt_json; this view never writes."""
    live: bool
    provider: str = ""
    model: str = ""
    detail: str = ""


@dataclass
class Lane:
    path: str
    branch: str
    head: str = ""
    status: str = ""


@dataclass
class BodyState:
    receipt: str
    status: str = ""
    worktree: str = ""
    old_sha: str = ""
    new_sha: str = ""
    observed_at: str = ""
    note: str = ""


@dataclass
class A2ABusState:
    root: str
    inbox_files: int
    quarantine_files: int
    node_registry: str = ""
    task_log: str = ""
    nats_e2e_receipt: str = ""


@dataclass
class ReceiptTail:
    path: str
    modified_at: str


@dataclass
class OrientationPacket:
    identity: Identity
    organs: list[Organ]
    tracks: list[Track]
    custody: CustodyReport
    liveness: Liveness
    broken: list[BrokenItem]
    loop1: Loop1Closure
    lanes: list[Lane] = field(default_factory=list)
    agents: list[dict[str, Any]] = field(default_factory=list)
    receipts_tail: list[ReceiptTail] = field(default_factory=list)
    a2a_bus: A2ABusState | None = None
    body: BodyState | None = None
    context_hash: str = ""


# ── Graph-shaped query layer ───────────────────────────────────────────
#
# Typed nodes + edges over the same owners the flat packet already reads.
# Traversal: organ -> tracks -> surfaces -> liveness edges.
# No new truth store; purely derived from the packet.


@dataclass
class GraphNode:
    kind: str  # "organ", "track", "surface", "objective", "broken"
    id: str
    label: str
    status: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str  # "serves", "owns_surface", "complements", "depends_on",
    #                 "liveness", "has_broken"


@dataclass
class SurfaceLiveness:
    pattern: str
    exists: bool
    matched_paths: list[str] = field(default_factory=list)
    newest_mtime: str = ""


@dataclass
class OrientationGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    surface_liveness: list[SurfaceLiveness] = field(default_factory=list)


def _probe_surface(pattern: str) -> SurfaceLiveness:
    """Check whether an owned-surface glob matches files in the worktree."""
    if pattern.endswith("/**"):
        directory = REPO_ROOT / pattern[:-3]
        if directory.is_dir():
            matched = [
                str(p.relative_to(REPO_ROOT))
                for p in sorted(directory.rglob("*"))
                if p.is_file()
            ][:5]
            mtime = ""
            if matched:
                newest = max(
                    (REPO_ROOT / m for m in matched),
                    key=lambda p: p.stat().st_mtime,
                )
                mtime = _mtime_iso(newest)
            return SurfaceLiveness(
                pattern=pattern,
                exists=bool(matched),
                matched_paths=matched,
                newest_mtime=mtime,
            )
        return SurfaceLiveness(pattern=pattern, exists=False)

    if "*" in pattern or "?" in pattern:
        parent = REPO_ROOT
        parts = pattern.split("/")
        glob_part = "/".join(parts)
        matched = [
            str(p.relative_to(REPO_ROOT))
            for p in sorted(parent.glob(glob_part))
            if p.is_file()
        ][:5]
        mtime = ""
        if matched:
            newest = max(
                (REPO_ROOT / m for m in matched),
                key=lambda p: p.stat().st_mtime,
            )
            mtime = _mtime_iso(newest)
        return SurfaceLiveness(
            pattern=pattern,
            exists=bool(matched),
            matched_paths=matched,
            newest_mtime=mtime,
        )

    target = REPO_ROOT / pattern
    if target.exists():
        return SurfaceLiveness(
            pattern=pattern,
            exists=True,
            matched_paths=[pattern],
            newest_mtime=_mtime_iso(target),
        )
    return SurfaceLiveness(pattern=pattern, exists=False)


def build_graph(packet: OrientationPacket) -> OrientationGraph:
    """Build a typed graph from the flat orientation packet.

    Node kinds: objective, organ, track, surface, broken.
    Edge relations: serves, owns_surface, complements, depends_on,
    liveness (surface -> surface_liveness probe), has_broken.
    """
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    surface_probes: list[SurfaceLiveness] = []
    seen_objectives: set[str] = set()

    # Objective nodes (deduplicated from tracks)
    for track in packet.tracks:
        obj_id = track.serves
        if obj_id and obj_id not in seen_objectives:
            seen_objectives.add(obj_id)
            nodes.append(
                GraphNode(
                    kind="objective",
                    id=f"obj:{obj_id}",
                    label=obj_id,
                    status="declared",
                )
            )

    # Organ nodes
    for organ in packet.organs:
        nodes.append(
            GraphNode(
                kind="organ",
                id=f"organ:{organ.id}",
                label=organ.id,
                status=organ.status,
                attrs={
                    "instrument": organ.instrument,
                    "external_name": organ.external_name,
                },
            )
        )

    # Track nodes + edges
    for track in packet.tracks:
        tid = f"track:{track.id}"
        nodes.append(
            GraphNode(
                kind="track",
                id=tid,
                label=track.id,
                status=track.status,
                attrs={"owner": track.owner},
            )
        )
        if track.serves:
            edges.append(
                GraphEdge(source=tid, target=f"obj:{track.serves}", relation="serves")
            )
        for comp in track.complements:
            edges.append(
                GraphEdge(source=tid, target=f"track:{comp}", relation="complements")
            )
        for dep in track.depends_on:
            edges.append(
                GraphEdge(source=tid, target=f"track:{dep}", relation="depends_on")
            )

        # Surface nodes + edges
        for surface in track.owned_surfaces:
            sid = f"surface:{surface}"
            nodes.append(GraphNode(kind="surface", id=sid, label=surface, status=""))
            edges.append(GraphEdge(source=tid, target=sid, relation="owns_surface"))
            probe = _probe_surface(surface)
            surface_probes.append(probe)
            status = "live" if probe.exists else "missing"
            nodes[-1].status = status
            if probe.newest_mtime:
                nodes[-1].attrs["newest_mtime"] = probe.newest_mtime

    # Broken-register nodes
    for item in packet.broken:
        bid = f"broken:{item.id}"
        nodes.append(
            GraphNode(
                kind="broken",
                id=bid,
                label=f"{item.id} — {item.title}",
                status=item.status,
            )
        )

    return OrientationGraph(nodes=nodes, edges=edges, surface_liveness=surface_probes)


def query_neighbors(
    graph: OrientationGraph,
    node_id: str,
    relation: str | None = None,
) -> list[tuple[GraphEdge, GraphNode]]:
    """Return (edge, target_node) pairs reachable from *node_id*.

    If *relation* is given, only edges of that type are returned.
    """
    node_map = {n.id: n for n in graph.nodes}
    results: list[tuple[GraphEdge, GraphNode]] = []
    for edge in graph.edges:
        if edge.source != node_id:
            continue
        if relation and edge.relation != relation:
            continue
        target = node_map.get(edge.target)
        if target:
            results.append((edge, target))
    return results


def query_subgraph(
    graph: OrientationGraph,
    root_id: str,
    max_depth: int = 3,
) -> OrientationGraph:
    """BFS traversal from *root_id* up to *max_depth* hops."""
    node_map = {n.id: n for n in graph.nodes}
    visited: set[str] = set()
    frontier = [root_id]
    collected_nodes: list[GraphNode] = []
    collected_edges: list[GraphEdge] = []
    depth = 0

    while frontier and depth <= max_depth:
        next_frontier: list[str] = []
        for nid in frontier:
            if nid in visited:
                continue
            visited.add(nid)
            node = node_map.get(nid)
            if node:
                collected_nodes.append(node)
            for edge in graph.edges:
                if edge.source == nid and edge.target not in visited:
                    collected_edges.append(edge)
                    next_frontier.append(edge.target)
        frontier = next_frontier
        depth += 1

    liveness = [
        sl for sl in graph.surface_liveness if f"surface:{sl.pattern}" in visited
    ]
    return OrientationGraph(
        nodes=collected_nodes, edges=collected_edges, surface_liveness=liveness
    )


# ── Time-to-orientation measurement ───────────────────────────────────

ORIENTATION_RECEIPT_DIR = dharma_state_dir("DHARMA_STATE_DIR") / "ops"
ORIENTATION_RECEIPT = ORIENTATION_RECEIPT_DIR / "orientation_timing_receipt.json"


def measure_orientation(write_receipt: bool = True) -> dict[str, Any]:
    """Time a full build_packet + build_graph cycle.

    Target: < 10 s for a fresh agent.  Returns the timing receipt dict.
    """
    t0 = time.monotonic()
    packet = build_packet()
    t_packet = time.monotonic() - t0

    t1 = time.monotonic()
    graph = build_graph(packet)
    t_graph = time.monotonic() - t1

    total = t_packet + t_graph
    receipt = {
        "event": "orientation_timing",
        "packet_build_s": round(t_packet, 4),
        "graph_build_s": round(t_graph, 4),
        "total_s": round(total, 4),
        "target_s": 10.0,
        "meets_target": total < 10.0,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "surface_probes": len(graph.surface_liveness),
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "context_hash": packet.context_hash,
    }
    if write_receipt:
        ORIENTATION_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        ORIENTATION_RECEIPT.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return receipt


def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        # Reuse the track checker's stdlib parser; do not grow a second YAML
        # subset implementation merely to keep orientation dependency-light.
        from scripts.governance.check_track_status import _parse_minimal_yaml

        return _parse_minimal_yaml(text)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        from scripts.governance.check_track_status import _parse_minimal_yaml

        return _parse_minimal_yaml(text)
    return data if isinstance(data, dict) else {}


def build_identity() -> Identity:
    read_first = [
        "foundations/THE_ORGANISM.md",
        "docs/vision_maps/NORTH_STAR.md",
        "reports/swarm_genome/2026-06-11/SYNTHESIS.md",
        "docs/MEGAFILE_INDEX.md",
    ]
    missing = [p for p in read_first if not (REPO_ROOT / p).exists()]
    one_line = ""
    if ORGANISM_DOC.exists():
        for line in ORGANISM_DOC.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("> **dharma_swarm is"):
                one_line = stripped.lstrip("> ").strip().strip("*")
                break
    if not one_line:
        one_line = (
            "(identity owner missing — read docs/vision_maps/"
            "NORTH_STAR.md §1 for the telos)"
        )
    return Identity(one_line=one_line, read_first=read_first, missing_sources=missing)


def build_organs() -> list[Organ]:
    data = _load_yaml(PORTFOLIO)
    organs: list[Organ] = []
    for cell in data.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        organs.append(
            Organ(
                id=str(cell.get("id", "")),
                instrument=str(cell.get("instrument", "")),
                status=str(cell.get("status", "")),
                external_name=str(cell.get("external_name", "") or ""),
            )
        )
    return organs


def build_tracks() -> list[Track]:
    data = _load_yaml(ACTIVE_TRACK)
    tracks: list[Track] = []
    for entry in data.get("active_tracks") or []:
        if not isinstance(entry, dict):
            continue
        tracks.append(
            Track(
                id=str(entry.get("id", "")),
                status=str(entry.get("status", "")),
                serves=str(entry.get("serves", "")),
                owner=str(entry.get("owner", "")),
                owned_surfaces=[str(s) for s in entry.get("owned_surfaces") or []],
                complements=[str(s) for s in entry.get("complements") or []],
                depends_on=[str(s) for s in entry.get("depends_on") or []],
            )
        )
    return tracks


def build_custody() -> CustodyReport:
    registered: list[str] = []
    try:
        data = json.loads(ASSERTIONS.read_text(encoding="utf-8"))
        guard = data.get("canonical_guard", {})
        registered = [str(p) for p in guard.get("registered") or []]
    except Exception:
        data = _load_yaml(ASSERTIONS)
        guard = data.get("canonical_guard", {}) if isinstance(data, dict) else {}
        registered = [str(p) for p in guard.get("registered") or []]
    missing = [p for p in registered if not (REPO_ROOT / p).exists()]
    return CustodyReport(
        registered_total=len(registered),
        present=len(registered) - len(missing),
        missing=missing,
    )


def build_liveness() -> Liveness:
    receipt_path = _census_receipt_path()
    if receipt_path is None or not receipt_path.exists():
        return Liveness(
            receipt=(
                "no census receipt — run "
                "python3 scripts/runtime/live_ops_census.py --write"
            )
        )
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception:
        return Liveness(receipt=f"unreadable receipt at {_normalize_context_path(str(receipt_path))}")
    surfaces = []
    for surface in payload.get("surfaces") or []:
        if not isinstance(surface, dict):
            continue
        surfaces.append(
            {
                "id": str(surface.get("surface_id") or surface.get("id") or ""),
                "label": str(surface.get("label", "")),
                "status": str(surface.get("status", "")),
            }
        )
    return Liveness(
        receipt=_normalize_context_path(str(receipt_path)),
        generated_at=str(payload.get("generated_at", "")),
        surfaces=surfaces,
    )


def build_broken() -> list[BrokenItem]:
    result = parse_broken_register(BROKEN_REGISTER)
    return [
        BrokenItem(id=entry.id, status=entry.status, title=entry.title)
        for entry in result.open_entries
    ]


def _runtime_db_path() -> Any:
    """Resolve the runtime-state db path from its owner (runtime_state),
    not a hardcoded literal. Borrows the owner's DEFAULT_RUNTIME_DB constant."""
    try:
        from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB

        return DEFAULT_RUNTIME_DB
    except Exception:
        return Path.home() / ".dharma" / "state" / "runtime.db"



def build_loop1_closure(db_path: Any = None) -> Loop1Closure:
    """Project Loop 1 closure from the latest delegation_runs receipt.

    LIVE only when the most recent COMPLETED receipt (by started_at, then rowid)
    carries a non-empty provider AND model. This view owns nothing — it reads the
    receipt_json column the spine dispatch writes (runtime_state owner). Only
    `completed` runs count: a stale `running`/in-flight receipt is not closure
    evidence (it would otherwise let an orphaned dispatch outrank a real one)."""
    import sqlite3

    path = Path(db_path) if db_path is not None else _runtime_db_path()
    if not Path(path).exists():
        return Loop1Closure(live=False, detail=f"no runtime db at {path}")
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except Exception:
        try:
            conn = sqlite3.connect(str(path))
        except Exception as exc:  # pragma: no cover - defensive
            return Loop1Closure(live=False, detail=f"db unreadable: {exc}")
    try:
        # status filter is applied only when the column exists (older schemas omit it).
        has_status = any(
            r[1] == "status" for r in conn.execute("pragma table_info(delegation_runs)")
        )
        status_clause = "AND status = 'completed' " if has_status else ""
        row = conn.execute(
            "SELECT receipt_json FROM delegation_runs "
            "WHERE receipt_json IS NOT NULL AND receipt_json != '' "
            f"{status_clause}"
            "ORDER BY started_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
    except Exception as exc:
        conn.close()
        return Loop1Closure(live=False, detail=f"delegation_runs query failed: {exc}")
    conn.close()
    if not row or not row[0]:
        return Loop1Closure(live=False, detail="no persisted EvidenceReceipt yet")
    try:
        blob = json.loads(row[0])
    except Exception:
        return Loop1Closure(live=False, detail="latest receipt_json unparseable")
    provider = str(blob.get("provider", "") or "")
    model = str(blob.get("model", "") or "")
    live = bool(provider and model)
    detail = (
        "latest dispatch receipt carries provider+model"
        if live
        else "latest receipt missing provider and/or model"
    )
    return Loop1Closure(live=live, provider=provider, model=model, detail=detail)


def build_lanes() -> list[Lane]:
    """Project parallel lane state from the ops lane map or git worktrees."""
    lanes: list[Lane] = []
    if LANE_MAP.exists():
        try:
            payload = json.loads(LANE_MAP.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        raw_lanes = payload.get("lanes") if isinstance(payload, dict) else None
        if isinstance(raw_lanes, list):
            for item in raw_lanes:
                if not isinstance(item, dict):
                    continue
                lanes.append(
                    Lane(
                        path=_normalize_context_path(str(item.get("path") or item.get("worktree") or "")),
                        branch=str(item.get("branch") or ""),
                        head=str(item.get("head") or item.get("sha") or ""),
                        status=str(item.get("status") or ""),
                    )
                )
    if lanes:
        return [_stable_lane(lane) for lane in lanes]

    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return []
    current: dict[str, str] = {}
    for line in result.stdout.splitlines() + [""]:
        if not line.strip():
            if current:
                lanes.append(
                    _stable_lane(
                        Lane(
                            path=_normalize_context_path(current.get("worktree", "")),
                            branch=current.get("branch", "").removeprefix("refs/heads/")
                            or "(detached)",
                            head=current.get("HEAD", ""),
                        )
                    )
                )
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return lanes


def _stable_lane(lane: Lane) -> Lane:
    """Avoid repo_context churn from moving lane SHAs."""
    if _is_repo_root_context_path(lane.path):
        return Lane(
            path=lane.path,
            branch=lane.branch,
            head="CURRENT_CHECKOUT",
            status=lane.status,
        )
    if lane.head:
        return Lane(
            path=lane.path,
            branch=lane.branch,
            head="LIVE_HEAD",
            status=lane.status,
        )
    return lane


def build_agents() -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    for agent in list_agent_presence():
        payload = agent.to_dict()
        payload.pop("age_hours", None)
        source_path = payload.get("source_path")
        if isinstance(source_path, str):
            payload["source_path"] = _normalize_context_path(source_path)
        agents.append(payload)
    return agents


def build_receipts_tail(limit: int = 8) -> list[ReceiptTail]:
    roots = [
        Path.home() / ".dharma/ds_goals",
        Path.home() / ".dharma/a2a_bus/inboxes",
        Path.home() / ".dharma/onboarding",
        REPO_CONTEXT_DIR,
    ]
    candidates: list[Path] = []
    for root in roots:
        if root == REPO_CONTEXT_DIR:
            nats_receipt = root / "nats_e2e_receipt.json"
            if nats_receipt.exists():
                candidates.append(nats_receipt)
        elif root.exists():
            candidates.extend(
                p
                for p in root.rglob("*")
                if p.is_file() and p.suffix in {".json", ".jsonl"}
            )
    candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    tail: list[ReceiptTail] = []
    for path in candidates[:limit]:
        tail.append(ReceiptTail(path=_normalize_context_path(str(path)), modified_at=_mtime_iso(path)))
    return tail


def build_a2a_bus_state() -> A2ABusState:
    inbox_root = A2A_BUS / "inboxes"
    quarantine_root = A2A_BUS / "quarantine"
    inbox_files = _count_files(inbox_root)
    quarantine_files = _count_files(quarantine_root)
    node_registry = Path.home() / ".dharma/a2a/nodes.json"
    task_log = Path.home() / ".dharma/a2a/task_log.jsonl"
    nats_receipt = REPO_CONTEXT_DIR / "nats_e2e_receipt.json"
    return A2ABusState(
        root=_normalize_context_path(str(A2A_BUS)),
        inbox_files=inbox_files,
        quarantine_files=quarantine_files,
        node_registry=_normalize_context_path(str(node_registry)) if node_registry.exists() else "",
        task_log=_normalize_context_path(str(task_log)) if task_log.exists() else "",
        nats_e2e_receipt=_normalize_context_path(str(nats_receipt)) if nats_receipt.exists() else "",
    )


def build_body_state() -> BodyState:
    if not DEPLOY_RECEIPT.exists():
        return BodyState(receipt=_normalize_context_path(str(DEPLOY_RECEIPT)), status="missing")
    try:
        payload = json.loads(DEPLOY_RECEIPT.read_text(encoding="utf-8"))
    except Exception:
        return BodyState(receipt=_normalize_context_path(str(DEPLOY_RECEIPT)), status="unreadable")
    return BodyState(
        receipt=_normalize_context_path(str(DEPLOY_RECEIPT)),
        status=str(payload.get("status") or ""),
        worktree=_normalize_context_path(str(payload.get("worktree") or "")),
        old_sha=str(payload.get("old_sha") or ""),
        new_sha=str(payload.get("new_sha") or ""),
        observed_at=str(payload.get("observed_at") or ""),
        note=str(payload.get("note") or ""),
    )


def build_packet() -> OrientationPacket:
    packet = OrientationPacket(
        identity=build_identity(),
        organs=build_organs(),
        tracks=build_tracks(),
        custody=build_custody(),
        liveness=build_liveness(),
        broken=build_broken(),
        loop1=build_loop1_closure(),
        lanes=build_lanes(),
        agents=build_agents(),
        receipts_tail=build_receipts_tail(),
        a2a_bus=build_a2a_bus_state(),
        body=build_body_state(),
    )
    payload = asdict(packet)
    payload.pop("context_hash", None)
    packet.context_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return packet


def write_repo_context(packet: OrientationPacket) -> tuple[Path, Path]:
    REPO_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    data = asdict(packet)
    REPO_CONTEXT_JSON.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    REPO_CONTEXT_MD.write_text(_repo_context_markdown(packet), encoding="utf-8")
    return REPO_CONTEXT_JSON, REPO_CONTEXT_MD


def _repo_context_markdown(packet: OrientationPacket) -> str:
    lines = [
        "# Repo Context",
        "",
        "Projection from existing owners. This file owns no facts.",
        "",
        f"- context_hash: `{packet.context_hash}`",
        f"- identity: {packet.identity.one_line}",
        f"- active_tracks: {len(packet.tracks)}",
        f"- lanes: {len(packet.lanes)}",
        f"- agents: {len(packet.agents)}",
        f"- receipts_tail: {len(packet.receipts_tail)}",
        f"- loop1_live: {packet.loop1.live}",
        "",
        "## Tracks",
    ]
    for track in packet.tracks:
        lines.append(
            f"- `{track.id}` [{track.status}] serves `{track.serves}` owner `{track.owner}`"
        )
    lines.append("")
    lines.append("## Agents")
    for agent in packet.agents:
        lines.append(
            f"- `{agent['agent_uid']}` status={agent['status']} "
            f"heartbeat={agent['heartbeat_status']} last_seen={agent['last_seen_at'] or '(none)'}"
        )
    lines.append("")
    lines.append("## A2A")
    if packet.a2a_bus is not None:
        lines.append(f"- root: `{packet.a2a_bus.root}`")
        lines.append(f"- inbox_files: {packet.a2a_bus.inbox_files}")
        lines.append(f"- quarantine_files: {packet.a2a_bus.quarantine_files}")
        if packet.a2a_bus.nats_e2e_receipt:
            lines.append(f"- nats_e2e_receipt: `{packet.a2a_bus.nats_e2e_receipt}`")
    lines.append("")
    lines.append("## Body")
    if packet.body is not None:
        lines.append(f"- status: `{packet.body.status}`")
        lines.append(f"- worktree: `{packet.body.worktree}`")
        lines.append(f"- old_sha: `{packet.body.old_sha}`")
        lines.append(f"- new_sha: `{packet.body.new_sha}`")
        lines.append(f"- note: {packet.body.note}")
    lines.append("")
    lines.append("## Broken Register")
    for item in packet.broken:
        lines.append(f"- `{item.id}` [{item.status}] {item.title}")
    lines.append("")
    return "\n".join(lines)


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def _mtime_iso(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return ""


def _section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def render(packet: OrientationPacket) -> None:
    _section("ORIENTATION — the whole organism at once (projection, not authority)")
    print(f"  {packet.identity.one_line}")
    print("  Read-first:")
    for path in packet.identity.read_first:
        marker = "MISSING " if path in packet.identity.missing_sources else ""
        print(f"    - {marker}{path}")

    _section(
        f"ORGANS ({len(packet.organs)}) — owner: docs/governance/VENTURE_CELL_PORTFOLIO.yaml"
    )
    for organ in packet.organs:
        name = f" ({organ.external_name})" if organ.external_name else ""
        print(f"  [{organ.status:<18}] {organ.id}{name} — {organ.instrument}")

    _section(
        f"ACTIVE TRACKS ({len(packet.tracks)}) — owner: docs/governance/ACTIVE_TRACK.yaml"
    )
    for track in packet.tracks:
        print(
            f"  [{track.status}] {track.id} serves={track.serves} owner={track.owner}"
        )
        for surface in track.owned_surfaces:
            print(f"      owns {surface}")

    _section(
        "CANON CUSTODY — owner: docs/docops/assertions.yaml canonical_guard.registered"
    )
    print(
        f"  Registered canon docs: {packet.custody.registered_total} "
        f"(present in this checkout: {packet.custody.present})"
    )
    for path in packet.custody.missing:
        print(f"  MISSING: {path}")

    _section("LIVENESS — owner: live ops census receipt (read-only)")
    print(f"  Receipt: {packet.liveness.receipt}")
    if packet.liveness.generated_at:
        print(f"  Generated: {packet.liveness.generated_at}")
    for surface in packet.liveness.surfaces:
        print(f"  [{surface['status']:<8}] {surface['id']} — {surface['label']}")

    _section("LOOP 1 CLOSURE — owner: delegation_runs.receipt_json (read-only)")
    c = packet.loop1
    print(f"  Loop 1 (provider chain + dispatch): {'LIVE' if c.live else 'NOT LIVE'}")
    if c.provider or c.model:
        print(f"    latest receipt: provider={c.provider!r} model={c.model!r}")
    if c.detail:
        print(f"    {c.detail}")

    _section(f"BROKEN REGISTER — open-like items ({len(packet.broken)})")
    for item in packet.broken:
        print(f"  [{item.status}] {item.id} — {item.title}")

    print()
    print("  Depth: make onboard (state) · docs/MEGAFILE_INDEX.md (maps)")
    print("  This view writes nothing and owns nothing.")


def render_graph(graph: OrientationGraph) -> None:
    """Human-readable dump of the orientation graph."""
    _section(f"ORIENTATION GRAPH ({len(graph.nodes)} nodes, {len(graph.edges)} edges)")
    by_kind: dict[str, list[GraphNode]] = {}
    for node in graph.nodes:
        by_kind.setdefault(node.kind, []).append(node)

    for kind in ("objective", "organ", "track", "surface", "broken"):
        group = by_kind.get(kind, [])
        if not group:
            continue
        print(f"\n  {kind.upper()} nodes ({len(group)}):")
        for node in group:
            print(f"    [{node.status or '-':<18}] {node.id}  {node.label}")

    print(f"\n  EDGES ({len(graph.edges)}):")
    for edge in graph.edges:
        print(f"    {edge.source} --{edge.relation}--> {edge.target}")

    live = [sl for sl in graph.surface_liveness if sl.exists]
    missing = [sl for sl in graph.surface_liveness if not sl.exists]
    print(f"\n  SURFACE LIVENESS: {len(live)} live, {len(missing)} missing")
    for sl in missing:
        print(f"    MISSING: {sl.pattern}")
    for sl in live:
        mtime_note = f"  newest={sl.newest_mtime}" if sl.newest_mtime else ""
        print(f"    LIVE:    {sl.pattern} ({len(sl.matched_paths)} files){mtime_note}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the whole organism at once from its owners.",
        # No prefix abbreviation: `--write` must not silently resolve to
        # `--write-context`, or the packet-runner positive-gate allowlist (which
        # forbids the write flag) could be bypassed by an abbreviated form.
        allow_abbrev=False,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="print the machine packet JSON to stdout",
    )
    parser.add_argument(
        "--write-context",
        action="store_true",
        help="write reports/orientation/repo_context.{json,md}",
    )
    parser.add_argument(
        "--graph",
        action="store_true",
        help="render the orientation graph (nodes + edges)",
    )
    parser.add_argument(
        "--graph-json", action="store_true", help="print the graph as JSON to stdout"
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        metavar="NODE_ID",
        help="BFS subgraph from NODE_ID (e.g. track:loop-closure-2026-06)",
    )
    parser.add_argument(
        "--measure",
        action="store_true",
        help="measure time-to-orientation and write receipt",
    )
    args = parser.parse_args(argv)

    if args.measure:
        receipt = measure_orientation(write_receipt=True)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0

    packet = build_packet()

    if args.write_context:
        json_path, md_path = write_repo_context(packet)
        render(packet)
        print(f"  Wrote: {json_path}")
        print(f"  Wrote: {md_path}")
        return 0

    graph = build_graph(packet)

    if args.query:
        sub = query_subgraph(graph, args.query)
        if not sub.nodes:
            print(f"  No node found for id={args.query!r}")
            return 1
        render_graph(sub)
        return 0

    if args.graph_json:
        print(json.dumps(asdict(graph), sort_keys=True, indent=1))
        return 0

    if args.graph:
        render_graph(graph)
        return 0

    if args.as_json:
        print(json.dumps(asdict(packet), sort_keys=True, indent=1))
    else:
        render(packet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
