"""Forge v1 — offline-first scoreboard for honest swarm-vs-single-model
measurement at equal token budget. See ``harness.py`` for the machinery and
``demo.py`` for a runnable end-to-end example (no live calls, no cost)."""
from .harness import (
    ArmResult,
    BudgetExhausted,
    Candidate,
    RepairTask,
    TokenBroker,
    best_of_n,
    run_arm,
    run_scoreboard,
    verify,
)
from .models import FlakyStub, StrongStub, WeakStub

__all__ = [
    "ArmResult",
    "BudgetExhausted",
    "Candidate",
    "RepairTask",
    "TokenBroker",
    "best_of_n",
    "run_arm",
    "run_scoreboard",
    "verify",
    "FlakyStub",
    "StrongStub",
    "WeakStub",
]
