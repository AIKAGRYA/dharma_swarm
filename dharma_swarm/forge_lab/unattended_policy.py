"""Single-source contracts for the bounded unattended EXPLORE lane."""

from __future__ import annotations

from dataclasses import dataclass, field

from dharma_swarm.forge_lab.unattended_call_shape import RunnerPolicy

RUNNER_SCHEMA = "rsi_lab.unattended_explore.v1"
LEDGER_SCHEMA = "rsi_lab.unattended_budget_ledger.v1"
RECEIPT_SCHEMA = "rsi_lab.unattended_receipt_chain.v1"
CHILD_SCHEMA = "rsi_lab.unattended_child_result.v1"

GENERATIONS = 1
CHILDREN = 1
TASKS = 1
LOGICAL_PROVIDER_CALL_SLOTS = 5
PER_CALL_TOKENS = 8_000
PER_CALL_USD = 0.25
PER_CANDIDATE_TOKENS = 16_000
PER_CANDIDATE_USD = 0.50
MAX_EXPERIMENT_TOKENS = 40_000
RUN_USD_RESERVATION = PER_CALL_USD * LOGICAL_PROVIDER_CALL_SLOTS
DAILY_USD_CAP = 3.0
MONTHLY_USD_CAP = 40.0
DAILY_CALL_CAP = 12
MONTHLY_CALL_CAP = 120
DEFAULT_TIMEOUT_SECONDS = 2_700
MAX_TIMEOUT_SECONDS = 3_000
PROVIDER_TTL_SECONDS = 3_600
MODEL_ROLES = ("mutator", "solver", "verifier")

TERMINAL_SUCCESS_STATES = {"inconclusive_low_power", "measured_negative"}


class UnattendedError(RuntimeError):
    """Typed fail-closed runner refusal."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        receipt: dict[str, object] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.receipt = receipt


@dataclass(frozen=True)
class BudgetPolicy:
    run_usd: float = RUN_USD_RESERVATION
    run_calls: int = LOGICAL_PROVIDER_CALL_SLOTS
    daily_usd: float = DAILY_USD_CAP
    monthly_usd: float = MONTHLY_USD_CAP
    daily_calls: int = DAILY_CALL_CAP
    monthly_calls: int = MONTHLY_CALL_CAP


@dataclass
class LogicalCallBudget:
    """Count admitted logical provider invocations before dispatch."""

    limit: int = LOGICAL_PROVIDER_CALL_SLOTS
    used: int = 0
    by_label: dict[str, int] = field(default_factory=dict)

    def consume(self, label: str) -> None:
        if self.used >= self.limit:
            raise UnattendedError(
                "LOGICAL_PROVIDER_CALL_CAP",
                f"provider call slot refused before {label}: {self.used}/{self.limit}",
            )
        self.used += 1
        self.by_label[label] = self.by_label.get(label, 0) + 1


RUNNER_POLICY = RunnerPolicy(
    runner_schema=RUNNER_SCHEMA,
    ledger_schema=LEDGER_SCHEMA,
    child_schema=CHILD_SCHEMA,
    generations=GENERATIONS,
    children=CHILDREN,
    tasks=TASKS,
    logical_provider_call_slots=LOGICAL_PROVIDER_CALL_SLOTS,
    per_call_tokens=PER_CALL_TOKENS,
    per_candidate_tokens=PER_CANDIDATE_TOKENS,
    per_candidate_usd=PER_CANDIDATE_USD,
    max_experiment_tokens=MAX_EXPERIMENT_TOKENS,
    max_timeout_seconds=MAX_TIMEOUT_SECONDS,
    run_usd_reservation=RUN_USD_RESERVATION,
)
