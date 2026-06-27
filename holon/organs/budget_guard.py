"""Budget enforcement for Holon cycles."""

from __future__ import annotations


class CostLimitExceeded(RuntimeError):
    def __init__(self, holon: str, spent: float, cap: float) -> None:
        self.holon = holon
        self.spent = spent
        self.cap = cap
        super().__init__(f"holon {holon} cost cap exceeded: ${spent:.4f} >= ${cap:.4f}")


def check_cost_cap(holon: str, spent_usd: float, cap_usd: float) -> None:
    if cap_usd <= 0:
        return
    if spent_usd >= cap_usd:
        raise CostLimitExceeded(holon, spent_usd, cap_usd)
