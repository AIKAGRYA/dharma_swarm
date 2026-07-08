"""Gateway: read fleet state → reversibility-classify → emit brief/receipt.

The gateway is the ONLY entry point for a Sarathi wake cycle. It:
1. Loads the fleet roster (roster.py)
2. Accepts a planned_action string
3. Runs it through the code-deterministic reversibility gate
4. If REVERSIBLE_SAFE: wraps holon_wake_cycle with the action
5. If anything else: logs the gate decision and does NOT execute
6. Emits a receipt every time, regardless of outcome

The gate takes NO model input by construction. A weak model at 3am cannot
widen authority. This is the apex safety spine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.reversibility_gate import classify_action
from dharma_swarm.holon_system.sarathi.roster import fleet_summary

RECEIPT_DIR = Path.home() / ".dharma/agents/sarathi/gateway_receipts"


@dataclass(frozen=True)
class GatewayResult:
    """The output of one gateway evaluation + optional execution."""

    timestamp: str
    planned_action: str
    gate_decision: dict[str, Any]
    roster_snapshot: dict[str, Any]
    executed: bool
    wake_result: dict[str, Any] | None = None
    receipt_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "dharma.sarathi.gateway.v1",
            "timestamp": self.timestamp,
            "planned_action": self.planned_action,
            "gate_decision": self.gate_decision,
            "executed": self.executed,
            "wake_result": self.wake_result,
            "roster_alive_count": self.roster_snapshot.get("alive_count", 0),
            "receipt_path": self.receipt_path,
        }


def _write_receipt(result: GatewayResult) -> str:
    """Write a JSON receipt for this gateway evaluation."""
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RECEIPT_DIR / f"gateway-{ts}.json"
    path.write_text(json.dumps(result.to_dict(), indent=2, default=str))
    return str(path)


def evaluate(
    planned_action: str,
    *,
    operator_reachable: bool = False,
) -> GatewayResult:
    """Evaluate a planned action through the reversibility gate.

    This is the GATE-ONLY path: it classifies and returns a decision but
    does NOT execute. The pulse module calls this, then decides whether
    to proceed to holon_wake_cycle based on the gate verdict.

    Returns a GatewayResult with executed=False and the gate decision.
    """
    decision = classify_action(planned_action, operator_reachable=operator_reachable)
    roster = fleet_summary()

    result = GatewayResult(
        timestamp=datetime.now(timezone.utc).isoformat(),
        planned_action=planned_action,
        gate_decision=decision.to_dict(),
        roster_snapshot=roster,
        executed=False,
    )

    result = GatewayResult(
        timestamp=result.timestamp,
        planned_action=result.planned_action,
        gate_decision=result.gate_decision,
        roster_snapshot=result.roster_snapshot,
        executed=result.executed,
        receipt_path=_write_receipt(result),
    )
    return result


def gate_and_execute(
    planned_action: str,
    *,
    operator_reachable: bool = False,
    execute_fn=None,
) -> GatewayResult:
    """Gate a planned action, and if REVERSIBLE_SAFE, execute it.

    ``execute_fn`` is an optional callable that performs the actual work.
    If not provided, the action is evaluated but not executed (safe default).

    This function NEVER bypasses the gate. If the gate says anything other
    than REVERSIBLE_SAFE, executed stays False regardless of execute_fn.
    """
    decision = classify_action(planned_action, operator_reachable=operator_reachable)
    roster = fleet_summary()

    executed = False
    wake_result = None

    if decision.may_execute_unattended and execute_fn is not None:
        try:
            wake_result = execute_fn()
            executed = True
        except Exception as exc:
            wake_result = {"error": str(exc), "type": type(exc).__name__}

    result = GatewayResult(
        timestamp=datetime.now(timezone.utc).isoformat(),
        planned_action=planned_action,
        gate_decision=decision.to_dict(),
        roster_snapshot=roster,
        executed=executed,
        wake_result=wake_result,
    )
    receipt_path = _write_receipt(result)
    return GatewayResult(
        timestamp=result.timestamp,
        planned_action=result.planned_action,
        gate_decision=result.gate_decision,
        roster_snapshot=result.roster_snapshot,
        executed=result.executed,
        wake_result=result.wake_result,
        receipt_path=receipt_path,
    )


def main() -> None:
    """CLI entry: evaluate a planned action from stdin or arg."""
    import sys

    action = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "read fleet status"
    result = evaluate(action, operator_reachable=False)
    print(json.dumps(result.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    main()
