"""Stub models for the offline harness — deterministic patch generators that
report a token cost, standing in for real provider calls so the scoreboard
machinery can be validated WITHOUT spending money. Real providers implement the
same ``propose(task, sample_idx) -> Candidate`` interface later (wired to the
live model pool / dharma_swarm.model_pool)."""
from __future__ import annotations

from .harness import Candidate, RepairTask


class StrongStub:
    """A perfect 'model' — always returns the gold patch."""

    name = "strong-stub"

    def __init__(self, tokens: int = 1000):
        self.tokens = tokens

    def propose(self, task: RepairTask, sample_idx: int) -> Candidate:
        return Candidate(patch=dict(task.gold_patch), tokens=self.tokens)


class WeakStub:
    """A 'model' that never fixes it — returns the buggy files unchanged."""

    name = "weak-stub"

    def __init__(self, tokens: int = 1000):
        self.tokens = tokens

    def propose(self, task: RepairTask, sample_idx: int) -> Candidate:
        return Candidate(patch=dict(task.files), tokens=self.tokens)


class FlakyStub:
    """Correct on every ``hit_every``-th sample (deterministic) — exercises
    best-of-N selection and budget enforcement."""

    name = "flaky-stub"

    def __init__(self, hit_every: int = 3, tokens: int = 1000):
        self.hit_every = hit_every
        self.tokens = tokens

    def propose(self, task: RepairTask, sample_idx: int) -> Candidate:
        if (sample_idx + 1) % self.hit_every == 0:
            return Candidate(patch=dict(task.gold_patch), tokens=self.tokens)
        return Candidate(patch=dict(task.files), tokens=self.tokens)
