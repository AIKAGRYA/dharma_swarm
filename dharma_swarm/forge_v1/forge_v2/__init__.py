"""Forge v2 — the falsification engine (built to FORGE_CANONICAL_INDEX.md + the
2026-06-30 design contract). Falsification machinery wrapped AROUND the working
forge_v1 core (autoloop/canonical/TokenBroker/Docker) — not a new benchmark universe.

Null hypothesis: single_best / self_moa wins at equal token/$ budget. Everything
else must beat its mission-class null, with receipts, or the null survives (a
valid, valuable Forge result).
"""

# Only these closeout states are valid (canon + contract).
CLOSEOUT_STATES = (
    "positive_lift_candidate",
    "measured_negative",
    "invalid_budget",
    "contaminated_quarantine",
    "inconclusive_low_power",
    "blocked_with_evidence",
)
