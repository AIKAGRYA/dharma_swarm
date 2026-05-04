#!/usr/bin/env python3
"""Measure how many durable write surfaces are native to the Dharma substrate."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


RUNTIME_TABLES = (
    "sessions",
    "task_claims",
    "delegation_runs",
    "workspace_leases",
    "artifact_records",
    "artifact_links",
    "memory_facts",
    "memory_edges",
    "context_bundles",
    "operator_actions",
    "session_events",
    "session_events_fts",
)

KNOWN_SURFACES = (
    ("sqlite:ontology.objects", "dharma_swarm/ontology_hub.py"),
    ("sqlite:ontology.links", "dharma_swarm/ontology_hub.py"),
    ("sqlite:ontology.action_log", "dharma_swarm/ontology_hub.py"),
    ("ontology:action_definitions", "dharma_swarm/ontology.py"),
    ("ontology:telic_seam_lifecycle", "dharma_swarm/telic_seam.py"),
    ("jsonl:stigmergy_marks", "dharma_swarm/stigmergy.py"),
    ("jsonl:handoffs", "dharma_swarm/handoff.py"),
    ("jsonl:telos_witness", "dharma_swarm/telos_gates.py"),
)


@dataclass(frozen=True)
class Surface:
    name: str
    owner: Path


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _has_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in tokens)


def _score_surface(surface: Surface, repo_root: Path) -> dict[str, object]:
    text = _read(surface.owner)
    criteria = {
        "typed_contract": _has_any(
            text,
            (
                "@dataclass",
                "basemodel",
                "actiondef",
                "create table",
                "objecttype",
            ),
        ),
        "authority_metadata": _has_any(
            text,
            (
                "agent_id",
                "actor",
                "operator",
                "session_id",
                "executed_by",
                "created_by",
                "proposal",
            ),
        ),
        "governance_hook": _has_any(
            text,
            ("telos", "gate", "policy", "witness", "shakti", "audit"),
        ),
        "traceability": _has_any(
            text,
            (
                "created_at",
                "updated_at",
                "timestamp",
                "lineage",
                "provenance",
                "action_log",
                "fts",
                "query",
            ),
        ),
    }
    native = all(criteria.values())
    try:
        owner = str(surface.owner.relative_to(repo_root))
    except ValueError:
        owner = str(surface.owner)
    return {
        "name": surface.name,
        "owner": owner,
        "native": native,
        "criteria": criteria,
    }


def _known_surfaces(repo_root: Path) -> list[Surface]:
    surfaces = [
        Surface(f"sqlite:runtime_state.{table}", repo_root / "dharma_swarm/runtime_state.py")
        for table in RUNTIME_TABLES
    ]
    surfaces.extend(
        Surface(name, repo_root / owner)
        for name, owner in KNOWN_SURFACES
    )
    lf5 = Path("/Users/dhyana/dharma_swarm_lf5/dharma_swarm/shakti_zeitgeist_executive.py")
    if lf5.exists():
        surfaces.append(Surface("json:shakti_zeitgeist_governance_bundle", lf5))
    return surfaces


def _discover_literal_surfaces(repo_root: Path) -> list[Surface]:
    surfaces: list[Surface] = []
    seen: set[tuple[str, str]] = set()
    pattern = re.compile(r"(?P<literal>(?:~|Path\.home\(\)).{0,120}\.dharma.{0,160}?\.(?:jsonl?|db))")
    for base in (repo_root / "dharma_swarm", repo_root / "scripts"):
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            text = _read(path)
            for match in pattern.finditer(text):
                literal = " ".join(match.group("literal").split())
                key = (str(path), literal)
                if key in seen:
                    continue
                seen.add(key)
                rel = path.relative_to(repo_root)
                surfaces.append(Surface(f"literal:{rel}:{literal[:72]}", path))
    return surfaces


def measure(repo_root: Path) -> dict[str, object]:
    repo_root = repo_root.resolve()
    surfaces = _known_surfaces(repo_root) + _discover_literal_surfaces(repo_root)
    rows = [_score_surface(surface, repo_root) for surface in surfaces]
    total = len(rows)
    native = sum(1 for row in rows if row["native"])
    score = round(native / total, 4) if total else 0.0
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "native_surfaces": native,
        "total_surfaces": total,
        "surfaces": rows,
    }


def write_baseline(payload: dict[str, object], state_dir: Path, output_date: str) -> Path:
    out_dir = state_dir.expanduser() / "baselines"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"substrate_nativeness_{output_date}.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".dharma")
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args(argv)

    payload = measure(args.repo_root)
    write_baseline(payload, args.state_dir, args.date)
    print(f"{payload['score']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
