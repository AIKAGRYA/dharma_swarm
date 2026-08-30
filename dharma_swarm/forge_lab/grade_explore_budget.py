"""Explore-open budget adapter for the explore-tier grading loop.

Leaf module of ``grade_explore``: it owns only the budget-accounting adapter so
the grading orchestration module stays inside the repo's 500-line module
budget. No imports from ``grade_explore`` — dependency direction is
``grade_explore`` → ``grade_explore_budget`` only.
"""

from __future__ import annotations

from typing import Any


class _ExploreOpenBudget:
    """Explore-mode budget adapter.

    Forge v0.1 separates *research accounting* from *candidate validity*:
    tokens over the declared comparison budget are measured and reported, but
    they do not make an otherwise executable candidate invalid during open
    exploration. Hard operational fuses, especially a real/shadow dollar cap,
    still invalidate and short-circuit through ``invalid``.

    The wrapped forge_v2 ``Budget`` still records the original over-token
    reason, so legacy evidence remains auditable, while arms that check
    ``budget.invalid`` no longer stop simply because the soft token cap was
    crossed.
    """

    def __init__(self, base: Any, *, soft_cap_tokens: int):
        self._base = base
        self.soft_cap_tokens = int(soft_cap_tokens)
        self.token_soft_cap_reason: str | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    @property
    def spent(self) -> int:
        return int(getattr(self._base, "spent", 0) or 0)

    def _base_reason(self) -> str | None:
        return getattr(self._base, "invalid_reason", None)

    def _token_overage_reason(self) -> str | None:
        reason = self._base_reason()
        if isinstance(reason, str) and reason.startswith("over token cap:"):
            return reason
        if self.spent > self.soft_cap_tokens:
            return f"over token soft cap: {self.spent}/{self.soft_cap_tokens}"
        return self.token_soft_cap_reason

    def _hard_invalid_reason(self) -> str | None:
        reason = self._base_reason()
        if not getattr(self._base, "invalid", False):
            return None
        if isinstance(reason, str) and reason.startswith("over token cap:"):
            return None
        return reason or "hard_budget_invalid"

    @property
    def soft_token_cap_exceeded(self) -> bool:
        return self._token_overage_reason() is not None

    @property
    def invalid(self) -> bool:
        return self._hard_invalid_reason() is not None

    @property
    def invalid_reason(self) -> str | None:
        return self._hard_invalid_reason()

    def charge(self, component: str, tokens: int, **kw: Any) -> int:
        spent = int(self._base.charge(component, tokens, **kw))
        if spent > self.soft_cap_tokens:
            self.token_soft_cap_reason = f"over token soft cap: {spent}/{self.soft_cap_tokens}"
        return spent

    def remaining(self) -> int:
        return max(0, self.soft_cap_tokens - self.spent)

    def to_dict(self) -> dict[str, Any]:
        data = dict(self._base.to_dict() if hasattr(self._base, "to_dict") else {})
        spent = int(data.get("spent_tokens", self.spent) or 0)
        soft_reason = self._token_overage_reason()
        hard_reason = self._hard_invalid_reason()
        data.update(
            {
                "soft_cap_tokens": self.soft_cap_tokens,
                "soft_token_cap_exceeded": bool(soft_reason),
                "token_soft_cap_reason": soft_reason,
                "token_invalid_ignored_for_explore": bool(soft_reason and not hard_reason),
                "hard_invalid": bool(hard_reason),
                "hard_invalid_reason": hard_reason,
                # In explore-open, ``invalid`` means hard invalid, not token over
                # soft cap. Keep the soft overage in explicit fields above.
                "invalid": bool(hard_reason),
                "invalid_reason": hard_reason,
                "spent_tokens": spent,
            }
        )
        return data
