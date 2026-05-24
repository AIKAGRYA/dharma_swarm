#!/usr/bin/env python3
"""Backfill identity invariants onto existing registered agents."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.identity_invariant import (  # noqa: E402
    build_identity_invariant,
    validate_identity_invariant,
)

DEFAULT_STATE_ROOT = Path.home() / ".dharma"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    path.write_text(encoded, encoding="utf-8")


def nested_identity_invariant(
    payload: dict[str, Any],
    *,
    card: bool = False,
) -> dict[str, Any] | None:
    if card:
        value = (payload.get("metadata") or {}).get("identity_invariant")
    else:
        value = payload.get("identity_invariant")
    return value if isinstance(value, dict) else None


@dataclass(frozen=True)
class AgentSurface:
    agent_uid: str
    callsign: str
    kind: str
    root: Path
    registration: Path
    living_agent: Path
    a2a_card: Path
    invariant_path: Path


def discover_surfaces(state_root: Path) -> list[AgentSurface]:
    surfaces: list[AgentSurface] = []
    seen: set[str] = set()

    external_root = state_root / "external_agents"
    if external_root.exists():
        for root in sorted(external_root.iterdir()):
            if not root.is_dir():
                continue
            registration = root / "registration.json"
            payload = read_json(registration)
            agent_uid = str(payload.get("agent_uid") or root.name)
            callsign = str(payload.get("callsign") or agent_uid)
            living_agent = state_root / "agents" / agent_uid / "living_agent.json"
            if not registration.exists() and not living_agent.exists():
                continue
            surfaces.append(
                AgentSurface(
                    agent_uid=agent_uid,
                    callsign=callsign,
                    kind="external",
                    root=root,
                    registration=registration,
                    living_agent=living_agent,
                    a2a_card=state_root / "a2a" / "cards" / f"{callsign}.json",
                    invariant_path=root / "identity_invariant.json",
                )
            )
            seen.add(agent_uid)

    agents_root = state_root / "agents"
    if agents_root.exists():
        for root in sorted(agents_root.iterdir()):
            if not root.is_dir() or root.name in seen:
                continue
            identity = root / "identity.json"
            payload = read_json(identity)
            agent_uid = root.name
            callsign = str(payload.get("callsign") or agent_uid)
            surfaces.append(
                AgentSurface(
                    agent_uid=agent_uid,
                    callsign=callsign,
                    kind="canonical",
                    root=root,
                    registration=identity,
                    living_agent=root / "living_agent.json",
                    a2a_card=state_root / "a2a" / "cards" / f"{callsign}.json",
                    invariant_path=root / "identity_invariant.json",
                )
            )

    return surfaces


def authority_floor(surface: AgentSurface) -> str:
    registration = read_json(surface.registration)
    living = read_json(surface.living_agent)
    return str(
        registration.get("authority")
        or registration.get("authority_floor")
        or living.get("authority")
        or living.get("authority_floor")
        or "unknown"
    )


def memory_namespace(surface: AgentSurface) -> str:
    registration = read_json(surface.registration)
    living = read_json(surface.living_agent)
    return str(
        registration.get("memory_namespace")
        or living.get("memory_namespace")
        or f"agent:{surface.agent_uid}"
    )


def trace_identity(surface: AgentSurface) -> str:
    registration = read_json(surface.registration)
    living = read_json(surface.living_agent)
    return str(
        registration.get("trace_identity")
        or living.get("trace_identity")
        or f"trace:{surface.agent_uid}"
    )


def created_at(surface: AgentSurface) -> str:
    registration = read_json(surface.registration)
    living = read_json(surface.living_agent)
    return str(registration.get("created_at") or living.get("created_at") or "")


def build_surface_invariant(surface: AgentSurface) -> dict[str, Any]:
    return build_identity_invariant(
        agent_uid=surface.agent_uid,
        authority_floor=authority_floor(surface),
        memory_namespace=memory_namespace(surface),
        trace_identity=trace_identity(surface),
        created_at=created_at(surface),
    )


def surface_status(surface: AgentSurface) -> dict[str, Any]:
    locations: dict[str, dict[str, Any] | None] = {
        "identity_invariant": read_json(surface.invariant_path)
        if surface.invariant_path.exists()
        else None,
        "registration": nested_identity_invariant(read_json(surface.registration)),
        "living_agent": nested_identity_invariant(read_json(surface.living_agent)),
        "a2a_card": nested_identity_invariant(read_json(surface.a2a_card), card=True),
    }
    invalid: list[str] = []
    digests: set[str] = set()
    for name, value in locations.items():
        if not value:
            invalid.append(f"{name}: missing")
            continue
        validation = validate_identity_invariant(value)
        if value.get("agent_uid") != surface.agent_uid:
            validation["valid"] = False
            validation["errors"].append("agent_uid mismatch")
        if not validation["valid"]:
            invalid.append(f"{name}: {', '.join(validation['errors'])}")
        digest = value.get("digest")
        if digest:
            digests.add(str(digest))
    if len(digests) > 1:
        invalid.append("digest mismatch across surfaces")
    return {
        "agent_uid": surface.agent_uid,
        "callsign": surface.callsign,
        "kind": surface.kind,
        "valid": not invalid,
        "issues": invalid,
        "digests": sorted(digests),
    }


def apply_surface(surface: AgentSurface, *, force: bool = False) -> dict[str, Any]:
    before = surface_status(surface)
    if before["valid"] and not force:
        return {**before, "changed": False}

    invariant = build_surface_invariant(surface)
    write_json(surface.invariant_path, invariant)

    registration = read_json(surface.registration)
    if registration or surface.registration.exists():
        registration["identity_invariant"] = invariant
        write_json(surface.registration, registration)

    living = read_json(surface.living_agent)
    if living or surface.living_agent.exists():
        living["identity_invariant"] = invariant
        write_json(surface.living_agent, living)

    card = read_json(surface.a2a_card)
    if card or surface.a2a_card.exists():
        metadata = card.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        metadata["identity_invariant"] = invariant
        card["metadata"] = metadata
        write_json(surface.a2a_card, card)

    return {**surface_status(surface), "changed": True}


def run_backfill(state_root: Path, *, apply: bool = False, force: bool = False) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for surface in discover_surfaces(state_root):
        if apply:
            rows.append(apply_surface(surface, force=force))
        else:
            rows.append(surface_status(surface))
    return {
        "schema_version": "dharma_identity_invariant_backfill.v0",
        "state_root": str(state_root),
        "mode": "apply" if apply else "dry_run",
        "force": force,
        "agent_count": len(rows),
        "invalid_count": sum(1 for row in rows if not row["valid"]),
        "changed_count": sum(1 for row in rows if row.get("changed")),
        "agents": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill identity invariants for registered agents."
    )
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rewrite existing valid invariant surfaces.",
    )
    args = parser.parse_args(argv)
    print(
        json.dumps(
            run_backfill(args.state_root, apply=args.apply, force=args.force),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
