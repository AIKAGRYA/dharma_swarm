"""Sarathi pulse surfaces.

Two surfaces coexist here:

- ``sarathi_pulse``: read-only status projection; does not start or mutate
  agents.
- ``run_pulse``: one governed tick — read fleet state, gate a planned action,
  produce an operator brief, write a pulse receipt. It makes NO model calls;
  it is a governed reflex (read state → classify → emit). Model-invoking wake
  (Tier-2) is a separate build behind proof gate 9.

Usage:
    python -m dharma_swarm.holon_system.sarathi.pulse
    python -m dharma_swarm.holon_system.sarathi.pulse --action "read fleet status"
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.holon_health import holon_status

from .roster import DEFAULT_ROSTER

PULSE_RECEIPT_DIR = Path.home() / ".dharma/agents/sarathi/pulse_receipts"
STATE_FILE = Path.home() / ".dharma/a2a_bus/state/sarathi.json"


def sarathi_pulse(roster: Iterable[str] = DEFAULT_ROSTER, *, agents_root: str | Path | None = None) -> dict[str, object]:
    """Return an honest status projection; does not start or mutate agents."""
    root = Path(agents_root).expanduser() if agents_root is not None else None
    rows = []
    for name in roster:
        try:
            rows.append(holon_status(str(name), agents_root=root))
        except Exception as exc:  # noqa: BLE001 - pulse is diagnostic, not a gate
            rows.append({"name": str(name), "registered": False, "error": str(exc)[:200]})
    return {
        "schema_version": "dharma.sarathi.pulse.v1",
        "wake_loop_active": False,
        "alive_claim": False,
        "roster": rows,
    }


def _ensure_state_file() -> None:
    """Gate 5: create the sarathi state file if it doesn't exist."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        initial = {
            "agent_uid": "sarathi",
            "service_alive": False,
            "wake_loop_active": False,
            "last_pulse": None,
            "pulse_count": 0,
            "schema_version": "dharma.sarathi.state.v1",
        }
        STATE_FILE.write_text(json.dumps(initial, indent=2))


def _update_state(pulse_receipt: dict[str, Any]) -> None:
    """Update the state file after a pulse — but NEVER flip wake_loop_active."""
    _ensure_state_file()
    data = json.loads(STATE_FILE.read_text())
    data["last_pulse"] = pulse_receipt["timestamp"]
    data["pulse_count"] = data.get("pulse_count", 0) + 1
    data["last_pulse_receipt"] = pulse_receipt["receipt_path"]
    # service_alive reflects that a pulse ran, wake_loop_active stays False
    # until proof gate 9 (overnight durability proof)
    data["service_alive"] = True
    STATE_FILE.write_text(json.dumps(data, indent=2))


def run_pulse(
    planned_action: str = "read fleet status and generate operator brief",
    *,
    operator_reachable: bool = False,
) -> dict[str, Any]:
    """Run a single governed Sarathi pulse.

    Returns the pulse receipt dict. This is the canonical Sarathi tick.
    """
    # Imported here, not at module top: gateway/brief import this module for
    # sarathi_pulse, so top-level imports would create a package import cycle.
    from .brief import generate_brief
    from .gateway import evaluate
    from .roster import fleet_summary

    _ensure_state_file()

    # Step 1: read fleet state
    roster = fleet_summary()

    # Step 2: gate the planned action
    gate_result = evaluate(planned_action, operator_reachable=operator_reachable)

    # Step 3: generate operator brief (always — even if gate blocks execution)
    brief = generate_brief(roster=roster, gate_result=gate_result)

    # Step 4: write pulse receipt
    PULSE_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    receipt_path = PULSE_RECEIPT_DIR / f"pulse-{ts}.json"

    receipt = {
        "schema_version": "dharma.sarathi.pulse.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "planned_action": planned_action,
        "operator_reachable": operator_reachable,
        "gate_decision": gate_result.gate_decision,
        "roster": roster,
        "brief": brief,
        "executed": gate_result.gate_decision.get("may_execute_unattended", False),
        "receipt_path": str(receipt_path),
    }

    receipt_path.write_text(json.dumps(receipt, indent=2, default=str))
    receipt["receipt_path"] = str(receipt_path)

    # Step 5: update state
    _update_state(receipt)

    return receipt


def main() -> None:
    """CLI entry for a single pulse."""
    import sys

    action = (
        " ".join(sys.argv[2:])
        if len(sys.argv) > 2 and sys.argv[1] == "--action"
        else "read fleet status and generate operator brief"
    )
    receipt = run_pulse(action, operator_reachable=False)

    # Print brief to stdout for cron consumption
    print(receipt["brief"])
    print(f"\n[receipt: {receipt['receipt_path']}]")
    print(f"[gate: {receipt['gate_decision']['action_class']}]")


if __name__ == "__main__":
    main()


__all__ = ["run_pulse", "sarathi_pulse"]
