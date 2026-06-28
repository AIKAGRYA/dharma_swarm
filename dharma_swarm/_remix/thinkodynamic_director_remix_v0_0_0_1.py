"""Thinkodynamic Director — Remix v0.0.0.1  (principled hardening exemplar).

WHY THIS FILE EXISTS
--------------------
``dharma_swarm/thinkodynamic_director.py`` is the largest module in the repo
(5,255 LOC, one ~3,160-line class, ~70 methods on a single surface). The
operator's brief was *not* "make it smaller" — it was "make it more powerful and
truly robust, abiding by the principles of the five specialists." This module is
the first exemplar: it proves the target architecture on the real engine before
the pattern is scaled to the other god modules. The original stays untouched;
this lives in ``dharma_swarm/_remix`` and is imported by nothing in production.

THE FIVE PRINCIPLES, MADE CONCRETE (see the scorecard for the full mapping)
---------------------------------------------------------------------------
* Ousterhout (depth): one *narrow* public interface (a handful of high-level
  verbs) in front of a deep body. The 70-method flat surface becomes a small
  number of capability seams. ``PUBLIC_INTERFACE_BUDGET`` is enforced as a
  fitness function, so the interface cannot silently widen.
* Feathers (seams): the monolith's responsibilities are expressed as narrow
  capability ``Protocol``s (SignalReader, OpportunityModel, WorkflowPlanner,
  EcosystemSensor, TaskLedger). Consumers depend on the protocol they actually
  use, not on the whole concrete class. Behaviour is preserved by delegating to
  the proven engine (Strangler-Fig) — proven pure logic is *reused, not blindly
  rewritten*; only the robustness envelope is new code.
* Tornhill (decoupling): the swarm is reached only through the ``SwarmGateway``
  protocol view, so the remix does not co-change with ``swarm.py``.
* Ford/Parsons (fitness functions): invariants are *executable* and embedded.
  ``self_audit()`` runs a registry of holistic fitness functions and (in strict
  mode) the constructor refuses to build an instance that fails them.
* Leveson (fail-closed + no silent harm): every fallible operation returns a
  ``DirectorOutcome`` (ok / value / error / witness) instead of a bare value or a
  silent ``None``; every caught exception is recorded as a witnessed ``Incident``
  (never ``except: pass``); preconditions are ``_require``-guarded and fail
  closed via ``InvariantViolation``.

WHAT "MORE POWERFUL" MEANS HERE
-------------------------------
Same capabilities, but: callers can no longer be silently lied to (every result
is an explicit success/failure with a witness trail), the interface cannot decay
(fitness budget), the swarm coupling is severed (protocol seam), and the module
self-checks its own design on construction. Power = guarantees, not line count.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    Mapping,
    Protocol,
    Sequence,
    TypeVar,
    runtime_checkable,
)

from dharma_swarm.thinkodynamic_director import (
    DirectorOpportunity,
    FileSignal,
    ThinkodynamicDirector,
    WorkflowPlan,
    WorkflowReview,
)

logger = logging.getLogger(__name__)

REMIX_VERSION = "0.0.0.1"

T = TypeVar("T")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Leveson layer — fail-closed invariants and witnessed (never silent) failure
# ---------------------------------------------------------------------------
class InvariantViolation(RuntimeError):
    """Raised when a fail-closed precondition or postcondition is broken.

    Distinct from ordinary exceptions so callers and tests can assert that the
    *control structure itself* refused to proceed, rather than a downstream bug.
    """


def _require(condition: object, message: str, *, context: Mapping[str, Any] | None = None) -> None:
    """Fail closed: raise ``InvariantViolation`` unless ``condition`` holds.

    This is the Leveson "no unfailing control structure" guard. Every guard has a
    message; nothing is permitted to pass on assumption.
    """
    if not condition:
        suffix = f" context={dict(context)}" if context else ""
        raise InvariantViolation(f"{message}{suffix}")


@dataclass(frozen=True, slots=True)
class Incident:
    """A witnessed failure. The remix never swallows an exception silently;

    it converts it into one of these and records it, so a failing director run
    can always be reconstructed (Leveson: no silent harm, Ahimsa axiom)."""

    when: str
    where: str
    error_type: str
    detail: str
    recovered: bool


class WitnessLog:
    """Append-only record of incidents. The anti-``except: pass`` discipline.

    Anything that catches an exception MUST route it here; the fitness audit
    asserts the module contains no bare ``except`` swallow.
    """

    def __init__(self) -> None:
        self._incidents: list[Incident] = []

    def record(self, *, where: str, error: BaseException, recovered: bool) -> Incident:
        incident = Incident(
            when=_utc_now().isoformat(),
            where=where,
            error_type=type(error).__name__,
            detail=str(error)[:500],
            recovered=recovered,
        )
        self._incidents.append(incident)
        # Witnessed, not swallowed: it is always logged at the appropriate level.
        logger.warning(
            "director.remix incident where=%s type=%s recovered=%s detail=%s",
            where,
            incident.error_type,
            recovered,
            incident.detail,
        )
        return incident

    @property
    def incidents(self) -> tuple[Incident, ...]:
        return tuple(self._incidents)


@dataclass(frozen=True, slots=True)
class DirectorOutcome(Generic[T]):
    """Fail-closed result envelope.

    Replaces "return a value, or ``None``, or raise" with one explicit shape.
    A caller cannot mistake a swallowed failure for an empty success: ``ok`` is
    always present, and ``unwrap()`` fails closed.
    """

    ok: bool
    value: T | None
    error: str = ""
    witness: tuple[Incident, ...] = ()

    @classmethod
    def success(cls, value: T, *, witness: Sequence[Incident] = ()) -> "DirectorOutcome[T]":
        return cls(ok=True, value=value, error="", witness=tuple(witness))

    @classmethod
    def failure(cls, error: str, *, witness: Sequence[Incident] = ()) -> "DirectorOutcome[T]":
        _require(bool(error), "a failure outcome must carry a non-empty error")
        return cls(ok=False, value=None, error=error, witness=tuple(witness))

    def unwrap(self) -> T:
        _require(self.ok, f"unwrap() on failed outcome: {self.error}")
        # ok == True guarantees value was set by success(); typed as T | None only
        # because the dataclass is generic.
        return self.value  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Feathers layer — narrow capability protocols (the seams)
# ---------------------------------------------------------------------------
@runtime_checkable
class SignalReader(Protocol):
    """The "read the world into ranked signals" capability."""

    def collect_candidates(self) -> list[Path]: ...
    def read_signal(self, path: Path) -> FileSignal | None: ...
    def rank_file_signals(self) -> list[FileSignal]: ...


@runtime_checkable
class OpportunityModel(Protocol):
    """The "turn signals into ranked opportunities and pick one" capability."""

    def build_opportunities(
        self, signals: Sequence[FileSignal], *, latent_gold: Sequence[Any] = ..., limit: int = ...
    ) -> list[DirectorOpportunity]: ...
    def choose_primary(self, opportunities: Sequence[DirectorOpportunity]) -> DirectorOpportunity: ...


@runtime_checkable
class WorkflowPlanner(Protocol):
    """The "compile an opportunity into a dependency-ordered workflow" capability."""

    def plan_workflow(self, opportunity: DirectorOpportunity, *, cycle_id: str) -> WorkflowPlan: ...


@runtime_checkable
class EcosystemSensor(Protocol):
    """The "sense the live ecosystem" capability."""

    def sense(self) -> dict[str, Any]: ...


@runtime_checkable
class TaskLedger(Protocol):
    """The "enqueue / count / review director tasks" capability."""

    async def enqueue_workflow(self, workflow: WorkflowPlan) -> list[Any]: ...
    async def active_director_task_count(self) -> int: ...
    def review_workflow(self, workflow: WorkflowPlan, tasks: Sequence[Any]) -> WorkflowReview: ...


@runtime_checkable
class SwarmGateway(Protocol):
    """Tornhill decoupling seam.

    The remix never touches the concrete ``swarm.py`` shape. If a swarm is
    present it is viewed only through this narrow protocol, so the remix does not
    co-change with the swarm module (the original co-changes with swarm.py at a
    measurable rate). v0.0.0.1 keeps the surface intentionally minimal; later
    versions widen it deliberately, behind the fitness budget.
    """

    ...


# The set of capability protocols the engine must satisfy to be a valid director.
_REQUIRED_SEAMS: tuple[type, ...] = (
    SignalReader,
    OpportunityModel,
    WorkflowPlanner,
    EcosystemSensor,
    TaskLedger,
)


# ---------------------------------------------------------------------------
# Ford/Parsons layer — embedded, executable fitness functions
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FitnessCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class FitnessReport:
    checks: tuple[FitnessCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failures(self) -> tuple[FitnessCheck, ...]:
        return tuple(check for check in self.checks if not check.passed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Domain value objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Survey:
    """Immutable snapshot of one read of the world: ranked signals + the live
    opportunity model + the ecosystem sense. Deep result behind a narrow verb."""

    signals: tuple[FileSignal, ...]
    opportunities: tuple[DirectorOpportunity, ...]
    primary: DirectorOpportunity | None
    ecosystem: dict[str, Any]


# ---------------------------------------------------------------------------
# Ousterhout layer — the deep orchestrator with a narrow public interface
# ---------------------------------------------------------------------------
class ThinkodynamicDirectorRemix:
    """Deep director orchestrator with a deliberately narrow public interface.

    Public verbs (Ousterhout):
        survey()            -> DirectorOutcome[Survey]
        think_once()        -> awaitable DirectorOutcome[dict]  (wraps run_cycle)
        self_audit()        -> FitnessReport
        verify_invariants() -> None   (fail closed)

    Capability seams (Feathers, read-only protocol views):
        .signals .opportunities .planner .sensor .ledger

    Everything else stays behind the seams or is private. The number of public
    names is bounded by PUBLIC_INTERFACE_BUDGET and enforced as a fitness check,
    so the interface cannot silently regress toward the original's 70-method
    flat surface.
    """

    # Ousterhout fitness threshold: the public interface may not exceed this.
    PUBLIC_INTERFACE_BUDGET = 14

    def __init__(
        self,
        engine: ThinkodynamicDirector | None = None,
        *,
        strict: bool = True,
        **engine_kwargs: Any,
    ) -> None:
        self._witness = WitnessLog()
        if engine is None:
            engine = ThinkodynamicDirector(**engine_kwargs)
        else:
            _require(
                not engine_kwargs,
                "pass an explicit engine OR engine kwargs, never both",
                context={"engine_kwargs": sorted(engine_kwargs)},
            )
        self._engine = engine
        # Feathers: confirm the engine satisfies every capability seam up front.
        self._verify_seams()
        if strict:
            report = self.self_audit()
            _require(
                report.passed,
                "construction refused: fitness audit failed",
                context={"failures": [c.name for c in report.failures]},
            )

    # -- capability seams (Feathers): narrow protocol views onto the engine ---
    @property
    def signals(self) -> SignalReader:
        return self._engine

    @property
    def opportunities(self) -> OpportunityModel:
        return self._engine

    @property
    def planner(self) -> WorkflowPlanner:
        return self._engine

    @property
    def sensor(self) -> EcosystemSensor:
        return self._engine

    @property
    def ledger(self) -> TaskLedger:
        return self._engine

    @property
    def witness(self) -> tuple[Incident, ...]:
        return self._witness.incidents

    # -- public verbs (Ousterhout: narrow surface, deep body) -----------------
    def survey(self) -> DirectorOutcome[Survey]:
        """Read the world once: rank signals, build the opportunity model, pick a
        primary, and sense the ecosystem. Fail-closed: any internal failure is
        witnessed and returned as a failure outcome, never a partial silent one."""
        return self._guard("survey", self._survey)

    async def think_once(self, *, delegate: bool = True, model: str = "sonnet") -> DirectorOutcome[dict[str, Any]]:
        """Run exactly one director cycle through the proven engine, wrapped in the
        fail-closed envelope. Behaviour is the engine's; the guarantee is new."""
        return await self._guard_async(
            "think_once",
            lambda: self._engine.run_cycle(delegate=delegate, model=model),
        )

    def self_audit(self) -> FitnessReport:
        """Run the embedded fitness functions (Ford/Parsons). Holistic and
        continuous: this is the same audit the constructor runs in strict mode and
        the same one the contract test asserts on."""
        checks: list[FitnessCheck] = []
        checks.append(self._fitness_interface_budget())
        checks.append(self._fitness_seam_integrity())
        checks.append(self._fitness_no_silent_swallow())
        checks.append(self._fitness_invariants_hold())
        checks.append(self._fitness_swarm_decoupled())
        return FitnessReport(checks=tuple(checks))

    def verify_invariants(self) -> None:
        """Fail-closed structural invariants. Raises ``InvariantViolation`` on the
        first breach (Leveson: the control structure must be able to fail)."""
        _require(self._engine is not None, "director must wrap a live engine")
        _require(self.PUBLIC_INTERFACE_BUDGET >= len(_REQUIRED_SEAMS) + 4,
                 "interface budget too small to express the required seams")
        for seam in _REQUIRED_SEAMS:
            _require(
                isinstance(self._engine, seam),
                f"engine does not satisfy required seam {seam.__name__}",
            )

    # -- internal: guarded execution (Leveson) --------------------------------
    def _survey(self) -> Survey:
        signals = list(self._engine.rank_file_signals())
        opportunities = list(self._engine.build_opportunities(signals))
        primary: DirectorOpportunity | None = None
        if opportunities:
            primary = self._engine.choose_primary(opportunities)
            # Postcondition: choose_primary must return the max-score opportunity.
            best = max(opportunities, key=lambda item: item.score)
            _require(
                primary.score == best.score,
                "choose_primary must select a maximal-score opportunity",
            )
        ecosystem = self._engine.sense()
        _require(isinstance(ecosystem, dict), "sense() must return a mapping")
        return Survey(
            signals=tuple(signals),
            opportunities=tuple(opportunities),
            primary=primary,
            ecosystem=ecosystem,
        )

    def _guard(self, where: str, fn: Callable[[], T]) -> DirectorOutcome[T]:
        try:
            return DirectorOutcome.success(fn())
        except InvariantViolation:
            # Invariant breaches are fail-closed by design: re-raise, do not mask.
            raise
        except Exception as error:  # noqa: BLE001 — broad on purpose, but witnessed
            incident = self._witness.record(where=where, error=error, recovered=True)
            return DirectorOutcome.failure(f"{where} failed: {error}", witness=(incident,))

    async def _guard_async(self, where: str, fn: Callable[[], Awaitable[T]]) -> DirectorOutcome[T]:
        try:
            return DirectorOutcome.success(await fn())
        except InvariantViolation:
            raise
        except Exception as error:  # noqa: BLE001 — broad on purpose, but witnessed
            incident = self._witness.record(where=where, error=error, recovered=True)
            return DirectorOutcome.failure(f"{where} failed: {error}", witness=(incident,))

    # -- internal: Feathers seam verification ---------------------------------
    def _verify_seams(self) -> None:
        missing = [seam.__name__ for seam in _REQUIRED_SEAMS if not isinstance(self._engine, seam)]
        _require(
            not missing,
            "wrapped engine is missing required capability seams",
            context={"missing": missing},
        )

    # -- internal: fitness functions (Ford/Parsons) ---------------------------
    def _fitness_interface_budget(self) -> FitnessCheck:
        public = [name for name in dir(type(self)) if not name.startswith("_")]
        ok = len(public) <= self.PUBLIC_INTERFACE_BUDGET
        return FitnessCheck(
            name="interface_budget",
            passed=ok,
            detail=f"{len(public)} public names <= budget {self.PUBLIC_INTERFACE_BUDGET}: {public}",
        )

    def _fitness_seam_integrity(self) -> FitnessCheck:
        missing = [seam.__name__ for seam in _REQUIRED_SEAMS if not isinstance(self._engine, seam)]
        return FitnessCheck(
            name="seam_integrity",
            passed=not missing,
            detail="all required seams satisfied" if not missing else f"missing: {missing}",
        )

    def _fitness_no_silent_swallow(self) -> FitnessCheck:
        """Meta fitness function: prove this module contains no silent ``except``
        swallow (bare ``except`` / ``except Exception`` immediately followed by a
        bare ``pass`` or ``continue``). Reads its own source."""
        try:
            source = Path(__file__).read_text(encoding="utf-8")
        except OSError as error:
            incident = self._witness.record(where="fitness.no_silent_swallow", error=error, recovered=True)
            return FitnessCheck(
                name="no_silent_swallow",
                passed=False,
                detail=f"could not read own source: {incident.detail}",
            )
        lines = source.splitlines()
        offenders: list[int] = []
        for idx, raw in enumerate(lines):
            stripped = raw.strip()
            if stripped.startswith("except"):
                # find the next non-blank, non-comment line
                for follow in lines[idx + 1 :]:
                    fs = follow.strip()
                    if not fs or fs.startswith("#"):
                        continue
                    if fs in {"pass", "continue"}:
                        offenders.append(idx + 1)
                    break
        return FitnessCheck(
            name="no_silent_swallow",
            passed=not offenders,
            detail="no silent swallow" if not offenders else f"silent swallow at lines {offenders}",
        )

    def _fitness_invariants_hold(self) -> FitnessCheck:
        try:
            self.verify_invariants()
        except InvariantViolation as error:
            return FitnessCheck(name="invariants_hold", passed=False, detail=str(error))
        return FitnessCheck(name="invariants_hold", passed=True, detail="all invariants hold")

    def _fitness_swarm_decoupled(self) -> FitnessCheck:
        """Tornhill: the remix must not co-change with the concrete swarm module.

        A swarm may be *present* on the engine and reached through the
        ``SwarmGateway`` protocol, but the remix's own source must not *import*
        the concrete swarm module. We inspect only import statements (read from
        source) so the guarantee is structural and cannot be defeated by prose."""
        try:
            source = Path(__file__).read_text(encoding="utf-8")
        except OSError as error:
            incident = self._witness.record(where="fitness.swarm_decoupled", error=error, recovered=True)
            return FitnessCheck(
                name="swarm_decoupled", passed=False, detail=f"could not read own source: {incident.detail}"
            )
        import_lines = [
            line.strip()
            for line in source.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        leaks = [
            line
            for line in import_lines
            if "swarm.swarm" in line or line.endswith(".swarm") or ".swarm " in line
        ]
        return FitnessCheck(
            name="swarm_decoupled",
            passed=not leaks,
            detail="no concrete swarm import" if not leaks else f"concrete swarm imports: {leaks}",
        )


__all__ = [
    "REMIX_VERSION",
    "ThinkodynamicDirectorRemix",
    "DirectorOutcome",
    "Survey",
    "Incident",
    "WitnessLog",
    "FitnessReport",
    "FitnessCheck",
    "InvariantViolation",
    "SignalReader",
    "OpportunityModel",
    "WorkflowPlanner",
    "EcosystemSensor",
    "TaskLedger",
    "SwarmGateway",
]
