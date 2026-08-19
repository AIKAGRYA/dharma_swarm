"""Sublimation Foundry — a target-agnostic verified evolutionary refinery.

The Foundry is the AlphaEvolve/OpenEvolve pattern made native to dharma_swarm
and pointed at EXTERNAL open-source AI-substrate code: an army of cheap models
proposes candidate improvements (mutation operator), a three-ring verification
stack is the fitness function, a diversity-preserving elite grid keeps the
search open, and verified wins become upstream contributions, public report
cards, and — only through the guardian path — One Wire receipts.

Design invariants (see docs/plans/THE_WITNESS_ENGINE_2026-08-18.md and
ACTIVE_TRACK organism-rewire-2026-07 next-item 15):

- Three rings, always. Ring 1 (:mod:`tripwires` + a blind evaluator) is the
  in-loop fitness the mutating army can never read; ring 2 (:mod:`heldout`)
  re-verifies survivors on rotated never-in-loop workloads; ring 3 is external
  confirmation (a merged PR, an independent leaderboard, or a
  counterparty-signed receipt). Nothing is claimed below ring 3.
- Fitness NEVER selects on money. Revenue is a downstream product, not a
  per-iteration selection signal (ratified no-daily-P&L rule).
- Foundry receipts stay lab-local under ``~/.dharma/foundry/`` until the One
  Wire guardian quorum (N>=5 confirmed receipts across M>=3 domains) is real;
  only :mod:`guardian_feed` can mint the guardian receipt that authorizes
  archive fitness.

The package is deliberately dependency-light (standard library only) so its
evaluators run hermetically in CI lanes and against untrusted external targets.
Integrations with the heavier organism (model pool, evolution roster, MAP-Elites
archive) are reached through lazy, guarded imports so the core stays importable
and testable on its own.
"""

from __future__ import annotations

from dharma_swarm.foundry.evaluator import (
    Candidate,
    EvalMetrics,
    EvalReceipt,
    Evaluator,
    blind_evaluate,
    canonical_digest,
)
from dharma_swarm.foundry.tripwires import (
    TripwireReport,
    scan_tripwires,
)

__all__ = [
    "Candidate",
    "EvalMetrics",
    "EvalReceipt",
    "Evaluator",
    "blind_evaluate",
    "canonical_digest",
    "TripwireReport",
    "scan_tripwires",
]
