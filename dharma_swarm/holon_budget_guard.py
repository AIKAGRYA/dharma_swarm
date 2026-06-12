"""Cost-cap ENFORCEMENT for sovereign holons (U8).

`economic_spine` *tracks* spend but does not halt on it. This is the enforcement primitive
the autonomous wake loop (U5) calls before each cycle: given the holon's spend and cap,
raise ``CostLimitExceeded`` when the cap is hit. Pure validation — no loop, no spend, no
animation; the loop wires the real `economic_spine` read to ``spent_usd``.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class CostLimitExceeded(Exception):
    """Raised when a holon's spend reaches its cap. The wake loop must catch this and halt."""

    def __init__(self, holon: str, spent: float, cap: float):
        self.holon = holon
        self.spent = spent
        self.cap = cap
        super().__init__(f"holon {holon} cost cap exceeded: ${spent:.4f} >= ${cap:.4f}")


def check_cost_cap(holon: str, spent_usd: float, cap_usd: float) -> None:
    """Raise ``CostLimitExceeded`` if ``spent_usd >= cap_usd``. Call before each wake cycle.

    A cap of ``<= 0`` means explicitly unbounded (opt-out) — no enforcement.
    """
    if cap_usd <= 0:
        return
    if spent_usd >= cap_usd:
        logger.warning(
            "[holon %s] cost cap hit: $%.4f >= $%.4f — halting", holon, spent_usd, cap_usd
        )
        raise CostLimitExceeded(holon, spent_usd, cap_usd)
