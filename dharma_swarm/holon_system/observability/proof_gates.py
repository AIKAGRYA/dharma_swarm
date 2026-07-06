"""Small proof-gate summary helper; no new receipt store."""

from __future__ import annotations


def proof_gate_summary(*, sprawl_guard_clean: bool = False, wake_loop_active: bool = False) -> dict[str, object]:
    return {
        "schema_version": "dharma.holon_system.proof_gates.v1",
        "sprawl_guard_clean": sprawl_guard_clean,
        "wake_loop_active": wake_loop_active,
        "alive_claim_allowed": bool(sprawl_guard_clean and wake_loop_active),
    }


__all__ = ["proof_gate_summary"]
