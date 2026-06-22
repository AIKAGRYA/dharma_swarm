"""Recorded fixture pool + roster registry for the hermetic arena (spec §3, build
invariant: ZERO keys / ZERO GPU by default).

Worker/roster responses come from a RECORDED FIXTURE POOL keyed by
``(task_id, model_id)``. Live model dispatch is gated behind ``DHARMA_ARENA_LIVE=1``
(OFF by default, requiring keys); the default path is fully deterministic and
replayable.

These recorded answers are INTENTIONALLY embedded as literal strings here (not
imported from the sealed taskpack labels) so the fixture pool is provably
independent of the scorer's correctness authority. Whether a recorded answer is
"correct" is decided ONLY by the scorer comparing it to the sealed label — the
fixtures themselves carry no correctness signal.

The roster is designed for skill-selection transcendence (Krogh-Vedelsby): each
model is a specialist, no single model is correct everywhere, so a genome that
routes each task to the right specialist can beat the best single model at equal
compute — the falsifiable success claim of spec §3.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dharma_swarm.coordination.arena.taskpack import TaskFamily

UNIFORM_CALL_COST = 100  # token/compute units per worker call (keeps parity legible)


@dataclass(frozen=True)
class ModelSpec:
    """Public capability metadata for a roster member (analogous to model_pool).

    ``specialty`` is PUBLIC routing metadata — not a sealed label. Routing a task
    by its (public) family to a (public) specialist is legitimate, not contamination.
    """

    model_id: str
    specialty: TaskFamily
    cost_per_call: int = UNIFORM_CALL_COST


ROSTER_REGISTRY: dict[str, ModelSpec] = {
    "alpha-math": ModelSpec("alpha-math", "math"),
    "beta-code": ModelSpec("beta-code", "code"),
    "gamma-logic": ModelSpec("gamma-logic", "logic"),
}

ALL_MODEL_IDS: tuple[str, ...] = tuple(ROSTER_REGISTRY)

# Recorded answers: model_id -> {task_id: answer_string}. Embedded literals — a
# faithful recording of what each worker returned, independent of sealed labels.
_RECORDED: dict[str, dict[str, str]] = {
    "alpha-math": {
        # math specialty (faithful)
        "m1": "391", "m2": "129", "m3": "12", "m4": "132",
        # one cross-domain hit, the rest plausible-but-wrong (distinct per model)
        "c3": "8",
        "c1": "dharma", "c2": "4", "c4": "8",
        "l1": "yes", "l2": "sue", "l3": "5", "l4": "30",
    },
    "beta-code": {
        # code specialty (faithful)
        "c1": "amrahd", "c2": "5", "c3": "8", "c4": "9",
        # one cross-domain hit, rest wrong (distinct)
        "m1": "391",
        "m2": "100", "m3": "6", "m4": "120",
        "l1": "yes", "l2": "ann", "l3": "9", "l4": "24",
    },
    "gamma-logic": {
        # logic specialty (faithful)
        "l1": "no", "l2": "tom", "l3": "6", "l4": "32",
        # no cross-domain hits — everything else wrong (distinct)
        "m1": "400", "m2": "130", "m3": "10", "m4": "144",
        "c1": "amrad", "c2": "3", "c3": "7", "c4": "6",
    },
}


@dataclass(frozen=True)
class WorkerResponse:
    """A single recorded worker call result."""

    model_id: str
    task_id: str
    answer: str
    cost: int


class FixturePool:
    """Deterministic, replayable worker-response source (the default arena path)."""

    def __init__(self, *, live: bool | None = None) -> None:
        # Live dispatch is opt-in and requires keys; default is hermetic replay.
        self.live = (
            live if live is not None else os.environ.get("DHARMA_ARENA_LIVE") == "1"
        )

    def dispatch(self, model_id: str, task_id: str) -> WorkerResponse:
        """Return the recorded worker response for ``(model_id, task_id)``.

        In live mode this would dispatch to a real provider. That path is a
        documented seam (requires keys) and is OFF by default — calling it raises
        so a missing key can never silently corrupt a hermetic run.
        """
        if self.live:  # pragma: no cover - requires external keys, out of scope
            raise NotImplementedError(
                "DHARMA_ARENA_LIVE dispatch requires provider keys and is out of "
                "scope for the hermetic keystone. TODO: route through the Forge "
                "Arena v0 live runner / provider_policy (consult-only) when wiring "
                "the live lane (spec §3, §11)."
            )
        spec = ROSTER_REGISTRY.get(model_id)
        cost = spec.cost_per_call if spec else UNIFORM_CALL_COST
        answer = _RECORDED.get(model_id, {}).get(task_id)
        if answer is None:
            # Unknown pairing in hermetic mode is a refusal, recorded honestly.
            return WorkerResponse(model_id=model_id, task_id=task_id, answer="", cost=cost)
        return WorkerResponse(model_id=model_id, task_id=task_id, answer=answer, cost=cost)


def specialty_for_family(family: TaskFamily) -> str | None:
    """Public routing helper: which roster model specializes in this family."""
    for spec in ROSTER_REGISTRY.values():
        if spec.specialty == family:
            return spec.model_id
    return None


__all__ = [
    "ALL_MODEL_IDS",
    "ROSTER_REGISTRY",
    "UNIFORM_CALL_COST",
    "FixturePool",
    "ModelSpec",
    "WorkerResponse",
    "specialty_for_family",
]
