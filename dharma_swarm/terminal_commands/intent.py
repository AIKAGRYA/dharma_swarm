"""Intent-plan and system-map inspection commands."""

from __future__ import annotations

from pathlib import Path
import json




def cmd_intent_plan(prompt: str) -> None:
    """Inspect the intent-to-work-packet pipeline for a prompt (non-executing)."""
    from dharma_swarm.operator_core.intent_payloads import build_intent_plan

    data = build_intent_plan(prompt)
    print(json.dumps(data, indent=2, default=str))


def cmd_system_map(
    map_cmd: str,
    *,
    organ: str | None = None,
    map_path: str | Path = "reports/system_map/latest.json",
    json_output: bool = False,
) -> int:
    """Read reports/system_map/latest.json and answer OrganState queries."""
    import sys

    path = Path(map_path).expanduser()
    if not path.exists():
        print(f"System map not found: {path}", file=sys.stderr)
        return 2
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"System map is invalid JSON: {path}: {exc}", file=sys.stderr)
        return 2

    organs = payload.get("organs")
    if not isinstance(organs, list):
        print(f"System map has no organs list: {path}", file=sys.stderr)
        return 2

    if map_cmd == "list":
        rows = organs
    elif map_cmd == "drifted":
        rows = [
            item
            for item in organs
            if str(item.get("coherence_state")) in {"drifted", "partial", "declared_only", "unknown"}
        ]
    elif map_cmd == "gaps":
        rows = [
            item
            for item in organs
            if item.get("next_bindable_gap") or item.get("next_packet_hint") or item.get("open_gap")
        ]
    elif map_cmd == "show":
        rows = [item for item in organs if item.get("name") == organ]
        if not rows:
            print(f"Organ not found: {organ}", file=sys.stderr)
            return 1
    else:
        print("Usage: dgc map {list|drifted|gaps|show}", file=sys.stderr)
        return 2

    if json_output:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0

    if map_cmd in {"list", "drifted"}:
        for item in rows:
            print(f"{item.get('name')}\t{item.get('coherence_state')}\t{item.get('owns')}")
    elif map_cmd == "gaps":
        for item in rows:
            gap = item.get("next_bindable_gap") or item.get("next_packet_hint") or item.get("open_gap")
            print(f"{item.get('name')}: {gap}")
    elif map_cmd == "show":
        item = rows[0]
        for key in (
            "name",
            "owns",
            "declared_state",
            "observed_state",
            "coherence_state",
            "open_gap",
            "next_bindable_gap",
            "risk",
        ):
            print(f"{key}: {item.get(key)}")
        refs = item.get("evidence_refs") or []
        if refs:
            print("evidence_refs:")
            for ref in refs:
                print(f"  - {ref}")
    return 0
