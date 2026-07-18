#!/usr/bin/env python3
"""Fleet field registry reader — secret-free multi-authority runtime-cell view.

Prints uid, transport tier, semantic/effect ceiling, and readiness for every
registered agent from docs/ops/FLEET_FIELD_REGISTRY.yaml (schema v2).

Usage:
    python3 scripts/runtime/fleet_field_registry.py            # field table
    python3 scripts/runtime/fleet_field_registry.py --check    # validate (exit 2)
    python3 scripts/runtime/fleet_field_registry.py --json     # machine dump

All modes validate first (including --json). No network calls; never prints
secret values. Schema/validation live in fleet_field_registry_contract.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime.fleet_field_registry_contract import (  # noqa: E402
    SCHEMA_V2,
    RegistryError,
    load_registry_data,
    validate_registry,
)

REGISTRY_PATH = REPO_ROOT / "docs/ops/FLEET_FIELD_REGISTRY.yaml"

# Re-export contract surface for tests and negative controls.
validate = validate_registry


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    return load_registry_data(path)


def render_table(data: dict) -> str:
    """Render multi-authority + per-agent transport/semantic ceilings honestly."""
    authorities = data.get("authorities") or []
    if isinstance(authorities, list) and authorities:
        auth_bits = []
        for auth in authorities:
            if not isinstance(auth, dict):
                continue
            auth_bits.append(
                f"{auth.get('authority_id', '?')}[{auth.get('role', '?')}/"
                f"{auth.get('evidence_status', '?')}]"
            )
        auth_line = "authorities: " + ", ".join(auth_bits)
    else:
        hub = data.get("hub") or {}
        auth_line = f"hub {hub.get('name', '?')} stream {hub.get('live_stream', '?')}"

    rows = [("AGENT", "TRANSPORT", "SEM/EFFECT", "READINESS", "SEM-MODE", "OBS-SUBJECT")]
    for agent in data.get("agents", []) or []:
        if not isinstance(agent, dict):
            continue
        obs = agent.get("observed_effective_route")
        obs_subject = "-"
        if isinstance(obs, dict):
            if obs.get("collision_ref"):
                obs_subject = f"quarantined:{obs.get('collision_ref')}"
            elif obs.get("inbox_subject") is not None:
                obs_subject = str(obs.get("inbox_subject"))
        rows.append(
            (
                str(agent.get("agent_uid", "?")),
                str(agent.get("transport_contact_tier", "unknown")),
                str(agent.get("semantic_effect_ceiling", "unknown")),
                str(agent.get("readiness_ceiling", "unknown")),
                str(agent.get("semantic_executor_mode", "unknown")),
                obs_subject[:40],
            )
        )
    widths = [max(len(row[col]) for row in rows) for col in range(len(rows[0]))]
    lines = [
        "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows
    ]
    header = (
        f"Fleet field registry v2 (updated {data.get('updated', '?')}) — {auth_line}\n"
        "Tiers are fail-closed; unknown is not green; non-proof components ⇒ readiness unknown.\n"
        "declared_route ≠ observed_effective_route ≠ target_route.\n"
    )
    n_coll = len(data.get("routing_collisions") or [])
    footer = (
        f"\n{len(data.get('agents') or [])} runtime-cell projections; "
        f"{n_coll} routing_collisions; full detail: docs/ops/FLEET_FIELD_REGISTRY.yaml"
    )
    return header + "\n".join(lines) + footer


def _emit_errors(errors: list[str]) -> None:
    for error in errors:
        print(f"[registry-check] {error}", file=sys.stderr)


def main(argv: list[str]) -> int:
    try:
        data = load_registry()
    except RegistryError as exc:
        print(f"[registry-check] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover — last-resort controlled exit
        print(
            f"[registry-check] registry load failure: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 2

    # Validate before every output mode, including --json and default table.
    try:
        errors = validate_registry(data, repo_root=REPO_ROOT)
    except Exception as exc:
        print(
            f"[registry-check] validation failure: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 2

    if errors:
        _emit_errors(errors)
        return 2

    if "--check" in argv:
        n_auth = len(data.get("authorities") or [])
        print(
            f"[registry-check] OK — schema {SCHEMA_V2}, "
            f"{len(data['agents'])} agents, {n_auth} authorities, secret policy holds"
        )
        return 0
    if "--json" in argv:
        print(json.dumps(data, indent=2, default=str))
        return 0
    print(render_table(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
