"""Read-only ingest health for the Operator Idea Spark lifecycle.

Counts the append-only stores WITHOUT writing or promoting anything (backlog
discipline: this never bulk-promotes — promotion is gate-only via
chetana.promote). Provides:

- ``ingest_health`` — counts (input receipts, candidates by status, routes,
  proposals/tasks/bets, lifecycle completion rate, unrouted/unimplemented,
  optional Chetana staged/trusted/quarantine backlog + stale concepts);
- ``write_health_receipt`` / ``health_receipt_freshness`` — a daily health
  receipt with a freshness gate (reuses the live-ops census freshness helper);
- ``wiki_cli_available`` — the executable check for the advertised ``wiki``
  command (Chetana CLI is the real executable path when it is absent).
"""

from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.live_ops_census_contract import census_payload_freshness

from .paths import (
    candidates_path,
    health_receipts_dir,
    idea_spark_root,
    input_receipts_dir,
    lifecycle_receipts_dir,
    memory_canonical_receipts_path,
    routing_receipts_dir,
)
from .schemas import utc_now_iso

INGEST_HEALTH_SCHEMA = "idea_spark_ingest_health.v0"
HEALTH_RECEIPT_NAME = "idea_spark_ingest_health.json"
HEALTH_MAX_AGE_HOURS = 24.0


def wiki_cli_available() -> bool:
    """True when an executable named ``wiki`` is on PATH (usually False)."""
    return shutil.which("wiki") is not None


def _count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _candidate_counts(state_root: Path | None) -> dict[str, Any]:
    path = candidates_path(state_root)
    promotion: Counter[str] = Counter()
    routing: Counter[str] = Counter()
    seen: dict[str, dict[str, str]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = str(row.get("candidate_id") or "")
            if not cid:
                continue
            seen[cid] = {
                "promotion_status": str(row.get("promotion_status") or "unknown"),
                "routing_status": str(row.get("routing_status") or "unknown"),
            }
    for entry in seen.values():
        promotion[entry["promotion_status"]] += 1
        routing[entry["routing_status"]] += 1
    return {
        "total": len(seen),
        "by_promotion_status": dict(promotion),
        "by_routing_status": dict(routing),
        "unrouted": routing.get("unrouted", 0),
    }


def _lifecycle_counts(state_root: Path | None) -> dict[str, Any]:
    directory = lifecycle_receipts_dir(state_root)
    by_status: Counter[str] = Counter()
    total = 0
    proposals = tasks = bets = routed = memory_linked = implemented = blocked = 0
    unimplemented_tasks = 0
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        total += 1
        status = str(row.get("status") or "unknown")
        by_status[status] += 1
        if row.get("proposal_id"):
            proposals += 1
        if row.get("task_id"):
            tasks += 1
            if status != "implemented":
                unimplemented_tasks += 1
        if row.get("bet_id"):
            bets += 1
        if row.get("semantic_route"):
            routed += 1
        if row.get("memory_canonical_receipt_id"):
            memory_linked += 1
        if status == "implemented":
            implemented += 1
        if status == "blocked" or row.get("blockers"):
            blocked += 1
    completion_rate = round(implemented / total, 3) if total else 0.0
    return {
        "total": total,
        "by_status": dict(by_status),
        "proposals": proposals,
        "tasks": tasks,
        "bets": bets,
        "routed": routed,
        "memory_linked": memory_linked,
        "implemented": implemented,
        "blocked": blocked,
        "unimplemented_tasks": unimplemented_tasks,
        "completion_rate": completion_rate,
    }


def _chetana_backlog(sample_limit: int) -> dict[str, Any]:
    """Optional Chetana staged/trusted/quarantine counts + stale-concept sample.

    Scans the REAL Chetana roots (Path.home()-based; not DHARMA_STATE_DIR), so
    callers opt in explicitly and tests leave it off.
    """
    try:
        from dharma_swarm.chetana import staging as staging_mod
        from dharma_swarm.chetana.provenance import parse_frontmatter
    except Exception as exc:  # pragma: no cover - import guard
        return {"available": False, "note": f"chetana import failed: {exc}"}

    staged = len(staging_mod.list_staged())
    trusted_paths = staging_mod.list_trusted()
    quarantine = len(staging_mod.list_quarantine())

    today = date.today()
    stale = 0
    sampled = 0
    for path in trusted_paths[:sample_limit]:
        try:
            schema, _ = parse_frontmatter(path.read_text(encoding="utf-8"), lenient=True)
        except Exception:
            continue
        sampled += 1
        stale_after = getattr(schema, "stale_after", None) if schema else None
        if stale_after:
            try:
                if date.fromisoformat(str(stale_after)) < today:
                    stale += 1
            except ValueError:
                continue
    return {
        "available": True,
        "staged": staged,
        "trusted": len(trusted_paths),
        "quarantine": quarantine,
        "stale_concepts_in_sample": stale,
        "stale_concept_sample_size": sampled,
        "zero_review_mark_warning": staged > 0 and len(trusted_paths) == 0,
        "note": "promotion is gate-only (chetana.promote); never bulk-promoted here",
    }


def ingest_health(
    state_root: Path | None = None,
    *,
    now: str | None = None,
    include_chetana_backlog: bool = False,
    sample_limit: int = 2000,
) -> dict[str, Any]:
    """Read-only ingest health snapshot (no writes, no promotion)."""
    candidates = _candidate_counts(state_root)
    lifecycle = _lifecycle_counts(state_root)
    health: dict[str, Any] = {
        "schema_version": INGEST_HEALTH_SCHEMA,
        "generated_at": now or utc_now_iso(),
        "root": str(idea_spark_root(state_root)),
        "input_receipts": len(list(input_receipts_dir(state_root).glob("*.json")))
        if input_receipts_dir(state_root).exists()
        else 0,
        "candidates": candidates,
        "routing_receipts": len(list(routing_receipts_dir(state_root).glob("*.json")))
        if routing_receipts_dir(state_root).exists()
        else 0,
        "memory_canonical_receipts": _count_jsonl_lines(memory_canonical_receipts_path(state_root)),
        "lifecycle": lifecycle,
        "wiki_cli_available": wiki_cli_available(),
        "executable_knowledge_path": "python -m dharma_swarm.chetana.cli status",
    }
    if include_chetana_backlog:
        health["chetana_backlog"] = _chetana_backlog(sample_limit)
    return health


def render_lines(health: dict[str, Any]) -> list[str]:
    """Compact, human-readable lines for an onboard-style section."""
    candidates = health.get("candidates", {})
    lifecycle = health.get("lifecycle", {})
    lines = [
        f"  Input receipts : {health.get('input_receipts', 0)}",
        f"  Candidates     : {candidates.get('total', 0)} "
        f"(unrouted {candidates.get('unrouted', 0)})",
        f"  Routing recpts : {health.get('routing_receipts', 0)}",
        f"  Memory recpts  : {health.get('memory_canonical_receipts', 0)}",
        f"  Lifecycle      : {lifecycle.get('total', 0)} "
        f"(implemented {lifecycle.get('implemented', 0)}, "
        f"completion {lifecycle.get('completion_rate', 0.0)})",
        f"  Proposals/Tasks/Bets : {lifecycle.get('proposals', 0)}/"
        f"{lifecycle.get('tasks', 0)}/{lifecycle.get('bets', 0)}",
        f"  wiki CLI       : {'present' if health.get('wiki_cli_available') else 'missing — use ' + health.get('executable_knowledge_path', '')}",
    ]
    backlog = health.get("chetana_backlog")
    if isinstance(backlog, dict) and backlog.get("available"):
        lines.append(
            f"  Chetana backlog: staged {backlog.get('staged', 0)}, "
            f"trusted {backlog.get('trusted', 0)}, quarantine {backlog.get('quarantine', 0)}, "
            f"stale {backlog.get('stale_concepts_in_sample', 0)}/{backlog.get('stale_concept_sample_size', 0)}"
        )
    return lines


def health_receipt_path(state_root: Path | None = None) -> Path:
    return health_receipts_dir(state_root) / HEALTH_RECEIPT_NAME


def write_health_receipt(
    state_root: Path | None = None,
    *,
    now: str | None = None,
    include_chetana_backlog: bool = True,
) -> Path:
    """Write the daily ingest-health receipt atomically (read-only over stores).

    The daily receipt includes the Chetana staged backlog + stale-concept sample
    by default (DoD §8: health output must report stale wiki concepts and staged
    backlog). Pass ``include_chetana_backlog=False`` for a fast, hermetic receipt
    that does not scan the real Chetana roots.
    """
    import os

    health = ingest_health(
        state_root, now=now, include_chetana_backlog=include_chetana_backlog
    )
    health_receipts_dir(state_root, ensure=True)
    path = health_receipt_path(state_root)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(health, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_health_receipt(state_root: Path | None = None) -> dict[str, Any] | None:
    path = health_receipt_path(state_root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def health_receipt_freshness(
    state_root: Path | None = None,
    *,
    now=None,
    max_age_hours: float = HEALTH_MAX_AGE_HOURS,
) -> dict[str, Any]:
    """Freshness of the latest health receipt (reuses census freshness helper)."""
    payload = load_health_receipt(state_root)
    if payload is None:
        return {
            "state": "missing",
            "age_minutes": None,
            "max_age_hours": max_age_hours,
            "evidence": "idea spark ingest health receipt is missing",
        }
    return census_payload_freshness(payload, max_age_hours=max_age_hours, now=now)
