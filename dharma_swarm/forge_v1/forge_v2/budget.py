"""Total-system budget accounting (contract invariant 3).

Equal budget means generation + aggregation + verification + coordination +
retries + selection overhead, in real tokens AND $ AND wall-clock. Free/
subscription routes get a SHADOW $ so 'free' is not infinite compute. Over cap
makes the run INVALID (closeout invalid_budget), never just 'lower score'.
"""
from __future__ import annotations

from dataclasses import dataclass, field

COMPONENTS = ("generation", "aggregation", "verification", "coordination", "retries", "selection")

# Shadow $/1M tokens for routes billed as free/subscription, so a free model
# does not become infinite compute in the budget. Coarse, blended, honest.
SHADOW_USD_PER_MTOK = 0.50


@dataclass
class Budget:
    cap_tokens: int
    cap_usd: float | None = None
    components: dict = field(default_factory=lambda: {c: 0 for c in COMPONENTS})
    usd: float = 0.0
    shadow_usd: float = 0.0
    wall_seconds: float = 0.0
    invalid: bool = False
    invalid_reason: str | None = None

    @property
    def spent(self) -> int:
        return int(sum(self.components.values()))

    def remaining(self) -> int:
        return max(0, self.cap_tokens - self.spent)

    def charge(self, component: str, tokens: int, *, usd: float = 0.0, is_free_route: bool = False) -> int:
        """Charge tokens to a component.

        Free routes and unknown-price routes accrue a shadow $ so missing price
        tables cannot silently turn into free infinite compute. Sets invalid if
        it crosses the token or $ cap; invalid runs are disqualified.
        """
        if component not in self.components:
            self.components[component] = 0
        self.components[component] += int(tokens)
        if is_free_route or usd <= 0:
            self.shadow_usd += tokens / 1_000_000 * SHADOW_USD_PER_MTOK
        else:
            self.usd += usd
        if self.spent > self.cap_tokens:
            self.invalid = True
            self.invalid_reason = f"over token cap: {self.spent}/{self.cap_tokens}"
        if self.cap_usd is not None and (self.usd + self.shadow_usd) > self.cap_usd:
            self.invalid = True
            self.invalid_reason = f"over $ cap: {self.usd + self.shadow_usd:.4f}/{self.cap_usd}"
        return self.spent

    def to_dict(self) -> dict:
        return {
            "cap_tokens": self.cap_tokens,
            "cap_usd": self.cap_usd,
            "components": dict(self.components),
            "spent_tokens": self.spent,
            "usd": round(self.usd, 4),
            "shadow_usd": round(self.shadow_usd, 4),
            "total_cost_usd": round(self.usd + self.shadow_usd, 4),
            "wall_seconds": round(self.wall_seconds, 1),
            "invalid": self.invalid,
            "invalid_reason": self.invalid_reason,
        }
