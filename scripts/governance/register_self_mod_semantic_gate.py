#!/usr/bin/env python3
"""WS4: register the Tier-A SELF_MOD_SEMANTIC gate via GateRegistry.propose().

telos_gates.py is HAND-EDIT FORBIDDEN — new gates may only enter the system
through the Variety Expansion Protocol (GateRegistry.propose() -> S5 approve()).
This script performs the propose() step idempotently. It does NOT approve the
gate (S5 / Dhyana approval is a separate, deliberate act) and it does NOT
enable live apply.

The gate adds richer self-modification trigger patterns on top of the existing
keyword gates. As a Tier-A custom gate, any trigger-pattern hit produces a
GateResult.FAIL, which TelosGatekeeper.check() escalates to GateDecision.BLOCK
(see the tier_a_fail branch). Combined with the WS4 gate_check change in
evolution.py (REVIEW-on-self-mod -> REJECTED), self-modification proposals can
no longer slip through to apply on an advisory.

Run:  python3 scripts/governance/register_self_mod_semantic_gate.py
Reverse: delete the SELF_MOD_SEMANTIC line from
         ~/.dharma/meta/gate_proposals.jsonl (the gate is inert until S5
         approves it, so leaving it 'proposed' is already a no-op at runtime).
"""

from __future__ import annotations

import sys

from dharma_swarm.telos_gates import GateProposal, GateRegistry

GATE_NAME = "SELF_MOD_SEMANTIC"

# Richer trigger patterns for self-modification intents. Substring-matched
# (case-folded) against combined action+content by TelosGatekeeper.check().
TRIGGER_PATTERNS = [
    "modify telos_gates",
    "edit telos_gates",
    "patch telos_gates",
    "disable gate",
    "disable telos gate",
    "remove gate",
    "weaken gate",
    "bypass gate",
    "bypass telos",
    "skip gate",
    "skip telos",
    "lower gate tier",
    "downgrade gate",
    "self-modify the gate",
    "modify the gatekeeper",
    "edit kernel axiom",
    "modify dharma_kernel",
    "rewrite the gate logic",
    "auto-approve self-mod",
    "make gate non-blocking",
    "turn review into allow",
]


def build_proposal() -> GateProposal:
    return GateProposal(
        name=GATE_NAME,
        tier="A",
        justification=(
            "WS4: self-modification of the governance surface (telos gates, "
            "kernel axioms, the gatekeeper itself) or any attempt to weaken / "
            "bypass / downgrade a gate is the highest-risk class of change. "
            "A Tier-A gate blocks unconditionally so such intents cannot reach "
            "apply. Complements the evolution.py REVIEW-on-self-mod reject."
        ),
        trigger_patterns=TRIGGER_PATTERNS,
        proposed_by="ws4-governance",
    )


def main() -> int:
    registry = GateRegistry()
    existing = {p.name for p in registry.list_proposals()}
    if GATE_NAME in existing:
        print(f"[ws4] gate '{GATE_NAME}' already proposed — nothing to do.")
        return 0
    name = registry.propose(build_proposal())
    print(
        f"[ws4] proposed Tier-A gate '{name}' with "
        f"{len(TRIGGER_PATTERNS)} trigger patterns. "
        "Pending S5 (Dhyana) approval — inert until approved."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
