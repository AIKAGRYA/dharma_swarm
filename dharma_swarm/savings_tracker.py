"""API savings tracker — records avoided costs when free/cheap models are used.

Sits between the provider layer and the economic engine. After each completion
on a free-tier provider, computes the counterfactual cost (what a paid provider
would have charged) and records it as an API savings transaction.

Usage:
    tracker = SavingsTracker(engine)
    # After a completion on a free model:
    tracker.record_savings(
        provider_name="openrouter_free",
        input_tokens=500,
        output_tokens=200,
        task_class="code_edit",
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from dharma_swarm.economic_engine import EconomicEngine, Transaction
from dharma_swarm.economic_fitness import SAVINGS_BASELINES

logger = logging.getLogger(__name__)


@dataclass
class SavingsRecord:
    """Result of a savings computation."""
    baseline_model: str
    counterfactual_cost: float
    actual_cost: float
    savings: float
    task_class: str


class SavingsTracker:
    """Computes and records API cost savings to the EconomicEngine."""

    def __init__(self, engine: EconomicEngine) -> None:
        self._engine = engine

    def compute_savings(
        self,
        input_tokens: int,
        output_tokens: int,
        task_class: str = "default",
        actual_cost: float = 0.0,
    ) -> SavingsRecord:
        """Compute counterfactual savings for a free-tier completion.

        Uses conservative baselines per task class to prevent inflated claims.
        """
        baseline = SAVINGS_BASELINES.get(task_class, SAVINGS_BASELINES["default"])
        model_name, input_price, output_price = baseline

        counterfactual = (
            (input_tokens / 1000) * input_price
            + (output_tokens / 1000) * output_price
        )
        savings = counterfactual - actual_cost

        return SavingsRecord(
            baseline_model=model_name,
            counterfactual_cost=counterfactual,
            actual_cost=actual_cost,
            savings=max(savings, 0.0),
            task_class=task_class,
        )

    def _quality_passed(self, output_text: str) -> bool:
        """Simple quality gate: output must be sufficiently long and free of obvious error markers."""
        if not output_text:
            return False
        # Minimum length heuristic (can be tuned)
        if len(output_text.strip()) < 10:
            return False
        lower = output_text.lower()
        # Basic error markers
        if any(marker in lower for marker in ("error", "exception", "failed", "fail")):
            return False
        return True

    def record_savings(
        self,
        provider_name: str,
        input_tokens: int,
        output_tokens: int,
        task_class: str = "default",
        actual_cost: float = 0.0,
        description: str = "",
        quality_parity_check: bool = False,
        output_text: str = "",
    ) -> Transaction | None:
        """Compute and record savings if positive.

        Returns the Transaction if savings were recorded, None otherwise.

        If quality_parity_check is True, savings are only recorded when the
        output passes a basic quality acceptance gate (length > minimum,
        no error markers).
        """
        record = self.compute_savings(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            task_class=task_class,
            actual_cost=actual_cost,
        )

        if record.savings <= 0.001:
            return None

        if quality_parity_check:
            if not self._quality_passed(output_text):
                logger.info(
                    "Quality gate failed for %s (%s); no savings recorded.",
                    provider_name,
                    task_class,
                )
                return None

        desc = description or (
            f"Used {provider_name} ({record.task_class}) "
            f"instead of {record.baseline_model} — "
            f"saved ${record.savings:.4f}"
        )

        # Cap at the counterfactual cost (can't save more than you'd have spent)
        tx = self._engine.record_api_savings(
            saved_usd=record.savings,
            description=desc,
            counterfactual_cap=record.counterfactual_cost,
        )

        logger.info(
            "Savings: $%.4f (counterfactual $%.4f via %s, actual $%.4f via %s)",
            record.savings, record.counterfactual_cost, record.baseline_model,
            record.actual_cost, provider_name,
        )
        return tx
