"""Deterministic renderers for compact, deep, and JSON session status.

Rendering only — no collection, no policy, no I/O.  The compact human view is
hard-bounded to 40–70 lines; ``--json`` is a deterministic projection of the
verdict and stable core plus one explicitly bounded local NATS observation.
No other volatile receipt field is projected.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

HUMAN_MIN_LINES = 40
HUMAN_MAX_LINES = 70

# Fields the machine projection deliberately carries: no observed_at, ages,
# durations, absolute host paths, cache bookkeeping, or delta. NATS status is
# the one explicit live observation and carries no admission authority.
_JSON_PROJECTION_KEYS = (
    "schema",
    "verdict",
    "exit_code",
    "stable_core",
    "conditions",
    "nats_substrate",
)


def machine_projection(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic ``--json`` view over an assembled v2 receipt object."""
    stable_core = dict(receipt.get("stable_core", {}))
    # The receipt keeps these empty v2 compatibility fields, but session
    # status deliberately exposes no packet-binding or track-selection seam.
    stable_core.pop("packet", None)
    portfolio = dict(stable_core.get("portfolio", {}))
    portfolio.pop("selected_track", None)
    stable_core["portfolio"] = portfolio
    conditions = [
        {
            "id": str(row.get("id", "")),
            "state": str(row.get("state", "")),
            "reason": str(row.get("reason", "")),
        }
        for row in receipt.get("live_delta", {}).get("conditions", [])
        if isinstance(row, dict)
    ]
    nats_substrate = receipt.get("extensions", {}).get("nats_substrate", {})
    if not isinstance(nats_substrate, Mapping):
        nats_substrate = {}
    projection = {
        "schema": "dharma_swarm.onboard_json.v1",
        "verdict": str(receipt.get("primary_verdict", "")),
        "exit_code": receipt.get("exit_code", 1),
        "stable_core": stable_core,
        "conditions": sorted(conditions, key=lambda row: row["id"]),
        "nats_substrate": dict(nats_substrate),
    }
    assert tuple(projection) == _JSON_PROJECTION_KEYS
    return projection


def render_json(receipt: Mapping[str, Any]) -> str:
    """Byte-stable JSON: sorted keys, fixed separators, trailing newline."""
    return json.dumps(
        machine_projection(receipt),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"


def _pad_to_minimum(lines: list[str]) -> list[str]:
    while len(lines) < HUMAN_MIN_LINES:
        lines.append("")
    return lines


def _format_age(seconds: Any) -> str:
    """Compact human age: ``90`` -> ``2m``, ``7200`` -> ``2h``, ``172800`` -> ``2d``."""
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return "?"
    if value >= 86400:
        return f"{int(value // 86400)}d"
    if value >= 3600:
        return f"{int(value // 3600)}h"
    return f"{int(value // 60)}m"


def _world_identity_lines(receipt: Mapping[str, Any]) -> list[str]:
    """Fetch-free world-identity block (One World Step 4), advisory only."""
    world = receipt.get("extensions", {}).get("world_identity", {})
    if not isinstance(world, Mapping) or not world:
        return []
    ahead = world.get("ahead")
    behind = world.get("behind")
    distance = (
        f"ahead {ahead if ahead is not None else '?'} · "
        f"behind {behind if behind is not None else '?'}"
    )
    base_line = f"  vs local {world.get('base_ref', 'origin/main')}: {distance}"
    tip_iso = world.get("base_tip_committer_iso")
    if tip_iso:
        base_line += f" · tip committed {tip_iso}"
    fetch_age = world.get("last_fetch_observed_age_seconds")
    if fetch_age is not None:
        base_line += f" · last fetch observed {_format_age(fetch_age)} ago"
    else:
        base_line += " · last fetch unobserved; local ref may be stale"
    lines = [
        "",
        "WORLD IDENTITY — FETCH-FREE, ADVISORY ONLY",
        f"  {world.get('branch', '?')} @ {str(world.get('head', ''))[:12]} "
        f"· host {world.get('host', '?')}",
        base_line,
    ]
    drift_limit = world.get("drift_warn_behind")
    if (
        isinstance(behind, int)
        and isinstance(drift_limit, int)
        and behind > drift_limit
    ):
        lines.append(
            f"  WARNING: {behind} commits behind local "
            f"{world.get('base_ref', 'origin/main')} (> {drift_limit}) — "
            "world drift; rebase or merge toward trunk"
        )
    dirty_age = world.get("oldest_dirty_age_seconds")
    dirty_limit = world.get("dirty_warn_age_seconds")
    if (
        isinstance(dirty_age, (int, float))
        and isinstance(dirty_limit, (int, float))
        and dirty_age > dirty_limit
    ):
        lines.append(
            f"  WARNING: oldest dirty entry "
            f"({world.get('oldest_dirty_path', '?')}) is "
            f"{_format_age(dirty_age)} old (> 24h) — stale uncommitted work"
        )
    return lines


def render_compact(receipt: Mapping[str, Any]) -> str:
    """Render the bounded 40–70 line human session-status view."""
    verdict = str(receipt.get("primary_verdict", "UNKNOWN"))
    exit_code = receipt.get("exit_code", 1)
    core = receipt.get("stable_core", {})
    repo = core.get("repository", {})
    live = receipt.get("live_delta", {})
    repo_state = live.get("repo_state", {})
    conditions = [row for row in live.get("conditions", []) if isinstance(row, dict)]

    by_state: dict[str, list[dict[str, Any]]] = {}
    for row in conditions:
        by_state.setdefault(str(row.get("state", "")), []).append(row)
    failing = by_state.get("fail", [])
    warns = by_state.get("warn", [])
    gaps = by_state.get("needs_host", [])
    skips = by_state.get("skipped", []) + by_state.get("not_observed", [])

    lines: list[str] = []
    lines.append(f"DHARMA ONBOARD — {verdict} (exit {exit_code})")
    lines.append("")
    dirty = "dirty" if repo_state.get("dirty") else "clean"
    lines.append(
        f"Repo:    {repo.get('branch', '?')} @ {str(repo.get('head', ''))[:12]}, "
        f"{dirty}, base {repo_state.get('base', '?')} "
        f"(ahead {repo_state.get('ahead', 0)}, behind {repo_state.get('behind', 0)})"
    )
    lines.append("View:    read-only session status")
    lines.append("Authority: none — no edit, merge, or deploy permission")
    lines.extend(_world_identity_lines(receipt))
    lines.append("")
    if failing:
        lines.append(f"Primary blocker: {failing[0].get('id')}")
    else:
        lines.append("Primary blocker: none")
    lines.append(
        f"Also observed: {len(gaps)} needs_host · {len(warns)} warning(s) · "
        f"{len(skips)} skipped/unobserved"
    )
    lines.append("")
    lines.append("Conditions (sorted, lossless):")
    condition_budget = 12
    ordered = sorted(conditions, key=lambda r: str(r.get("id", "")))
    for row in ordered[:condition_budget]:
        reason = str(row.get("reason", ""))
        suffix = f" — {reason[:60]}" if reason else ""
        lines.append(f"  [{row.get('state', '?'):>12}] {row.get('id')}{suffix}")
    if len(ordered) > condition_budget:
        lines.append(f"  … {len(ordered) - condition_budget} more in the receipt")

    nats_substrate = receipt.get("extensions", {}).get("nats_substrate", {})
    if isinstance(nats_substrate, Mapping) and nats_substrate:
        mirrors = [
            row
            for row in nats_substrate.get("filesystem_mirrors", [])
            if isinstance(row, Mapping)
        ]
        mirror_count = sum(row.get("exists") is True for row in mirrors)
        mirror_state = "present" if nats_substrate.get(
            "filesystem_mirrors_exist"
        ) else "absent"
        tcp_state = "listening" if nats_substrate.get(
            "tcp_listening"
        ) else "not listening"
        lines.append("")
        lines.append("NATS SUBSTRATE — LOCAL OBSERVATION ONLY")
        lines.append(f"  Spec: {nats_substrate.get('spec_path', '?')}")
        lines.append(
            "  Local TCP "
            f"{nats_substrate.get('tcp_host', '?')}:{nats_substrate.get('tcp_port', '?')}: "
            f"{tcp_state}"
        )
        lines.append(
            "  Compatibility filesystem A2A mirrors: "
            f"{mirror_state} ({mirror_count}/{len(mirrors)} declared paths)"
        )
        lines.append(
            "  WARNING: compatibility filesystem mirrors are not live-transport proof."
        )
        lines.append("  No JetStream ack or live contact is claimed.")

    lines.append("")
    tracks = core.get("portfolio", {}).get("tracks", [])
    lines.append("ACTIVE PORTFOLIO")
    lines.append(f"Declared portfolio ({len(tracks)} track(s); live state is NOT here):")
    for track_id in tracks[:12]:
        lines.append(f"  - {track_id}")
    if len(tracks) > 12:
        lines.append(f"  … {len(tracks) - 12} more in ACTIVE_TRACK.yaml")

    lines.append("")
    lines.append("Toolchain:")
    for tool, version in sorted(live.get("toolchain", {}).items()):
        lines.append(f"  {tool}: {version or 'MISSING'}")

    orientation = core.get("orientation", {})
    register = orientation.get("broken_register", {})
    lines.append("")
    lines.append(
        "Broken register: "
        f"{register.get('total', '?')} total · {register.get('open_like', '?')} open-like · "
        f"{register.get('closed_like', '?')} closed-like · {register.get('unknown', '?')} unknown"
    )
    lines.append("Read-first surfaces:")
    for rel, present in sorted(orientation.get("static_surfaces", {}).items()):
        lines.append(f"  [{'ok' if present else 'MISSING'}] {rel}")

    lines.append("")
    lines.append("LIVING AXIOMS")
    lines.append("Required reading (canonical max-five):")
    lines.append("  " + " · ".join(core.get("required_reading", [])[:5]))
    lines.append("")
    lines.append("WHAT TO DO NEXT")
    lines.append("Next: repair any blocker, rerun make onboard, then")
    lines.append("      make agent-build-preflight PACKET=<path>")

    lines = _pad_to_minimum(lines)
    if len(lines) > HUMAN_MAX_LINES:
        lines = lines[: HUMAN_MAX_LINES - 1] + ["  … output truncated to budget"]
    return "\n".join(lines) + "\n"


def render_deep(receipt: Mapping[str, Any]) -> str:
    """Detailed view over the same session status and verdict."""
    compact = render_compact(receipt)
    live = receipt.get("live_delta", {})
    extra: list[str] = ["", "— deep —"]
    extra.append("Toolchain:")
    for tool, version in sorted(live.get("toolchain", {}).items()):
        extra.append(f"  {tool}: {version or 'MISSING'}")
    extra.append("Projection freshness:")
    for rel, row in sorted(live.get("projection_freshness", {}).items()):
        extra.append(f"  {rel}: {json.dumps(row, sort_keys=True)}")
    orientation = receipt.get("stable_core", {}).get("orientation", {})
    extra.append(
        "Broken register: "
        + json.dumps(orientation.get("broken_register", {}), sort_keys=True)
    )
    return compact + "\n".join(extra) + "\n"


__all__ = [
    "HUMAN_MAX_LINES",
    "HUMAN_MIN_LINES",
    "machine_projection",
    "render_compact",
    "render_deep",
    "render_json",
]
