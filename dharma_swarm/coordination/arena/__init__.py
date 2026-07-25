"""Arena v1 — the keystone (spec §3).

Two layers with a hard boundary: a frozen hermetic scorer (the sole correctness
authority) and an evolving task curator (stub). Scores *verified capability delta
under budget parity*; a genome wins only by beating the best single model at
equal compute, with significance.
"""

from dharma_swarm.coordination.arena.corpus import (
    build_cold_start_corpus,
    corpus_sha256,
)
from dharma_swarm.coordination.arena.curator import TaskCurator
from dharma_swarm.coordination.arena.fixtures import FixturePool
from dharma_swarm.coordination.arena.runner import (
    CLOSEOUT_STATES,
    ArenaRunner,
    render_decision_packet,
)
from dharma_swarm.coordination.arena.scorer import score_submission, scorer_hash
from dharma_swarm.coordination.arena.taskpack import ArenaTask, Taskpack

__all__ = [
    "CLOSEOUT_STATES",
    "ArenaRunner",
    "ArenaTask",
    "FixturePool",
    "TaskCurator",
    "Taskpack",
    "build_cold_start_corpus",
    "corpus_sha256",
    "render_decision_packet",
    "score_submission",
    "scorer_hash",
]
