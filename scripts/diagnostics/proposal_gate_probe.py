#!/usr/bin/env python3
"""Proposal gate probe — map which telos gates a self-mod proposal trips.

Why this exists
---------------
The WS4 hardening (see ``dharma_swarm/evolution.py`` ~L1543) makes a self-mod
proposal a HARD REJECT whenever the gatekeeper returns ``REVIEW`` — and a
``REVIEW`` is produced whenever *any* Tier-C advisory gate flags. So a proposal
must satisfy the WHOLE Tier-C battery at once (epistemological diversity,
steelman counterargument, dogma-drift balance, ...). Crafting a description by
trial and error trips one gate while fixing another.

This probe runs a candidate ``(description, diff, change_type)`` through the
real ``DarwinEngine.gate_check`` path and prints the per-gate verdict plus the
final decision, so the requirement is *mapped* rather than guessed. It is the
diagnostic floor for the gate-compliant proposal contract documented in
``docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md``.

Usage
-----
    python3 scripts/diagnostics/proposal_gate_probe.py            # built-in samples
    python3 scripts/diagnostics/proposal_gate_probe.py -d "..." --diff "+x"
"""
from __future__ import annotations

import argparse
import asyncio
import tempfile
from pathlib import Path


async def probe(
    description: str,
    *,
    diff: str = "+placeholder change",
    change_type: str = "mutation",
) -> dict[str, object]:
    """Run one proposal through gate_check and return decision + gate verdicts."""
    from dharma_swarm.evolution import DarwinEngine

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        engine = DarwinEngine(
            archive_path=root / "archive.jsonl",
            traces_path=root / "traces",
            predictor_path=root / "predictor.jsonl",
        )
        await engine.init()
        proposal = await engine.propose(
            component="probe.py",
            change_type=change_type,
            description=description,
            diff=diff,
        )
        await engine.gate_check(proposal)
        gate_results = (proposal.metadata or {}).get("gate_results", {})
        return {
            "decision": proposal.gate_decision,
            "status": proposal.status.value,
            "gates": gate_results,
        }


def _render(label: str, result: dict[str, object]) -> None:
    gates = result.get("gates", {}) or {}
    print(f"\n=== {label} ===")
    print(f"  decision : {result['decision']}   status: {result['status']}")
    for name, verdict in sorted(gates.items()):
        v = verdict if isinstance(verdict, str) else getattr(verdict, "value", verdict)
        mark = "✅" if str(v).upper() in {"PASS", "ALLOW"} else "❌"
        print(f"    {mark} {name:<14} {v}")


# Verified to clear the whole Tier-C battery for a self-mod proposal. Kept in
# sync with tests/evolution_gate_helpers.py: the three epistemological frames
# live in the DESCRIPTION (ANEKANTA reads description+diff) while the steelman
# counterargument + dogma-drift evidence markers live in the DIFF (STEELMAN /
# DOGMA_DRIFT scan the diff, not the description).
TIER_C_COMPLIANT = (
    "Refactor the computation-layer mechanism for this change, keeping the "
    "observer's first-person awareness of the behaviour and preserving "
    "system-level feedback, adaptation, and resilience across the network"
)
TIER_C_COMPLIANT_DIFF = (
    "+# however, risk: a regression is possible; tested and measured, "
    "verified by the results above\n+placeholder change"
)


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-d", "--description", default=None)
    parser.add_argument("--diff", default="+placeholder change")
    parser.add_argument("--change-type", default="mutation")
    args = parser.parse_args()

    if args.description is not None:
        _render("custom", await probe(args.description, diff=args.diff, change_type=args.change_type))
        return

    # Built-in samples: a terse (failing) description and the compliant one.
    _render("terse 'Improve error handling' (expected REJECT)", await probe("Improve error handling"))
    _render(
        "TIER_C_COMPLIANT (expected ALLOW)",
        await probe(TIER_C_COMPLIANT, diff=TIER_C_COMPLIANT_DIFF),
    )


if __name__ == "__main__":
    asyncio.run(_main())
