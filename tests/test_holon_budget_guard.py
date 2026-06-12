"""Verifier for holon cost-cap enforcement (U8). Pure validation — no spend, no animation."""
from __future__ import annotations

import pytest

from dharma_swarm.holon_budget_guard import CostLimitExceeded, check_cost_cap


def test_under_cap_passes():
    check_cost_cap("h", spent_usd=1.0, cap_usd=3.0)  # must not raise


def test_at_cap_raises():
    with pytest.raises(CostLimitExceeded) as exc:
        check_cost_cap("h", spent_usd=3.0, cap_usd=3.0)
    assert exc.value.holon == "h"
    assert exc.value.spent == 3.0
    assert exc.value.cap == 3.0


def test_over_cap_raises():
    with pytest.raises(CostLimitExceeded):
        check_cost_cap("h", spent_usd=5.5, cap_usd=3.0)


def test_zero_cap_is_unbounded():
    check_cost_cap("h", spent_usd=999.0, cap_usd=0.0)  # opt-out, must not raise


def test_exception_message_is_informative():
    try:
        check_cost_cap("h", 5.0, 3.0)
    except CostLimitExceeded as exc:
        assert "cost cap exceeded" in str(exc)
        assert "5.0" in str(exc) and "3.0" in str(exc)
