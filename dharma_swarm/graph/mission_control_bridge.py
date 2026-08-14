"""Authority-gated Mission Control dispatch through durable DharmaGraph.

This opt-in composition boundary owns no executor, scheduler, or truth store.
The graph persists admission and recovery progress; an injected execution
port remains the owner of provider effects and their idempotency records.

Authority is evaluator semantics, not receipt semantics. A grant is bound to
the graph program and an admitted task-plan digest, which is reread immediately
before the bridge enters the execution adapter. That reread is not atomic with
the adapter or its external effect. Production promotion therefore requires an
owner-side CAS/lease or immutable authorized snapshot spanning effect admission.
Receipts, checkpoints, and model consensus cannot mint grants.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol, TypedDict

from dharma_swarm.graph.persistence import (
    GraphCheckpointRecord,
    GraphPersistenceKernel,
    GraphThreadBusyError,
)
from dharma_swarm.graph.schema import TypedCompiledGraph, TypedStateGraph
from dharma_swarm.graph.types import END, START, GraphRunResult, RunCheckpoint
from dharma_swarm.mission_control_contract import clean_identifier, stable_id, utc_now
from dharma_swarm.mission_control_execution import (
    OwnerExecutionObservation,
    OwnerExecutionRef,
)
from dharma_swarm.models import TaskStatus

GRAPH_ID = "mission-control-durable-bridge.v2"
PRODUCTION_PROMOTION_BLOCKER = (
    "production wiring requires atomic TaskBoard owner CAS or an immutable "
    "authorized plan snapshot spanning effect admission"
)
_PROGRAM_SHAPE = {
    "graph_id": GRAPH_ID,
    "nodes": (
        "admit_authority",
        "dispatch_owner",
        "dispatch_reauthorized",
        "reauthorize_authority",
        "observe_owner",
        "wait_owner",
    ),
    "effect_owner": "MissionExecutionPort.dispatch",
    "state_schema": "mission-control-durable-bridge-state.v2",
}
PROGRAM_DIGEST = (
    "sha256:"
    + hashlib.sha256(
        json.dumps(_PROGRAM_SHAPE, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
)
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class MissionGraphError(RuntimeError):
    """The bridge contract failed closed."""


class MissionAuthorityDenied(MissionGraphError):
    """No valid authority existed at the pre-effect boundary."""


class MissionGrantExpired(MissionAuthorityDenied):
    """A once-valid grant requires a new checkpointed authority generation."""


class MissionPlanChanged(MissionAuthorityDenied):
    """The live task plan no longer matches the authority-bound plan."""


class MissionObservationPending(MissionGraphError):
    """The owner is nonterminal after this invocation's bounded poll budget."""


class MissionResumeRequired(MissionGraphError):
    """A durable thread exists and must be resumed, never reseeded."""


class MissionThreadBusy(MissionGraphError):
    """Another task or process owns this mission thread's run lease."""


def mission_plan_digest(plan: Mapping[str, Any]) -> str:
    """Return the canonical digest an authority binds for one task manifest."""

    if not isinstance(plan, Mapping):
        raise MissionGraphError("mission plan must be a mapping")
    try:
        payload = json.dumps(
            dict(plan),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MissionGraphError("mission plan is not canonical JSON") from exc
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise MissionGraphError(f"{label} must be a canonical sha256 digest")
    return value


@dataclass(frozen=True, slots=True)
class MissionDispatchRequest:
    mission_id: str
    task_id: str
    dispatch_key: str
    graph_id: str
    program_digest: str
    plan_digest: str
    graph_run_id: str
    thread_id: str

    @classmethod
    def create(
        cls,
        mission_id: str,
        task_id: str,
        plan_digest: str,
        dispatch_key: str = "default",
    ) -> "MissionDispatchRequest":
        mission_id = clean_identifier(mission_id, "mission_id")
        task_id = clean_identifier(task_id, "task_id")
        dispatch_key = clean_identifier(dispatch_key, "dispatch_key")
        plan_digest = _require_digest(plan_digest, "plan_digest")
        identity = (GRAPH_ID, PROGRAM_DIGEST, mission_id, task_id, dispatch_key)
        return cls(
            mission_id=mission_id,
            task_id=task_id,
            dispatch_key=dispatch_key,
            graph_id=GRAPH_ID,
            program_digest=PROGRAM_DIGEST,
            plan_digest=plan_digest,
            graph_run_id=stable_id("mission_graph_run", *identity, plan_digest),
            thread_id=stable_id("mission_graph_thread", *identity),
        )

    @classmethod
    def thread_id_for(
        cls, mission_id: str, task_id: str, dispatch_key: str = "default"
    ) -> str:
        mission_id = clean_identifier(mission_id, "mission_id")
        task_id = clean_identifier(task_id, "task_id")
        dispatch_key = clean_identifier(dispatch_key, "dispatch_key")
        return stable_id(
            "mission_graph_thread",
            GRAPH_ID,
            PROGRAM_DIGEST,
            mission_id,
            task_id,
            dispatch_key,
        )

    @property
    def scope_digest(self) -> str:
        return mission_plan_digest(self.to_state())

    def to_state(self) -> dict[str, str]:
        return {
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "dispatch_key": self.dispatch_key,
            "graph_id": self.graph_id,
            "program_digest": self.program_digest,
            "plan_digest": self.plan_digest,
            "graph_run_id": self.graph_run_id,
            "thread_id": self.thread_id,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "MissionDispatchRequest":
        if not isinstance(state, Mapping):
            raise MissionGraphError("persisted mission graph state is not a mapping")
        request = cls.create(
            str(state.get("mission_id", "")),
            str(state.get("task_id", "")),
            _require_digest(state.get("plan_digest"), "persisted plan_digest"),
            str(state.get("dispatch_key", "")),
        )
        expected = request.to_state()
        if any(state.get(key) != value for key, value in expected.items()):
            raise MissionGraphError("persisted mission graph identity is inconsistent")
        return request


@dataclass(frozen=True, slots=True)
class MissionDispatchGrant:
    """A closed, plan- and program-bound allow value from an authority source."""

    grant_id: str
    principal_id: str
    mission_id: str
    task_id: str
    dispatch_key: str
    graph_id: str
    program_digest: str
    plan_digest: str
    graph_run_id: str
    thread_id: str
    scope_digest: str
    issued_at: datetime
    expires_at: datetime

    def validate_shape(self, request: MissionDispatchRequest, *, now: datetime) -> None:
        now = _aware_utc(now, "clock", MissionAuthorityDenied)
        issued_at = _aware_utc(self.issued_at, "issued_at", MissionAuthorityDenied)
        expires_at = _aware_utc(self.expires_at, "expires_at", MissionAuthorityDenied)
        if not self.grant_id.strip() or not self.principal_id.strip():
            raise MissionAuthorityDenied("authority grant identity is blank")
        scoped = (
            self.mission_id,
            self.task_id,
            self.dispatch_key,
            self.graph_id,
            self.program_digest,
            self.plan_digest,
            self.graph_run_id,
            self.thread_id,
        )
        expected = (
            request.mission_id,
            request.task_id,
            request.dispatch_key,
            request.graph_id,
            request.program_digest,
            request.plan_digest,
            request.graph_run_id,
            request.thread_id,
        )
        if scoped != expected:
            raise MissionAuthorityDenied("authority grant scope does not match request")
        if self.scope_digest != request.scope_digest:
            raise MissionAuthorityDenied("authority grant scope digest does not match")
        if issued_at > now or expires_at <= issued_at:
            raise MissionAuthorityDenied("authority grant time bounds are invalid")
        if expires_at <= now:
            raise MissionGrantExpired("authority grant has expired")

    def to_state(self) -> dict[str, str]:
        return {
            "grant_id": self.grant_id,
            "principal_id": self.principal_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "dispatch_key": self.dispatch_key,
            "graph_id": self.graph_id,
            "program_digest": self.program_digest,
            "plan_digest": self.plan_digest,
            "graph_run_id": self.graph_run_id,
            "thread_id": self.thread_id,
            "scope_digest": self.scope_digest,
            "issued_at": _aware_utc(
                self.issued_at, "issued_at", MissionAuthorityDenied
            ).isoformat(),
            "expires_at": _aware_utc(
                self.expires_at, "expires_at", MissionAuthorityDenied
            ).isoformat(),
        }

    @classmethod
    def from_state(cls, raw: Any) -> "MissionDispatchGrant":
        values = _exact_string_mapping(raw, _GRANT_FIELDS, "authority grant")
        try:
            return cls(
                grant_id=values["grant_id"],
                principal_id=values["principal_id"],
                mission_id=values["mission_id"],
                task_id=values["task_id"],
                dispatch_key=values["dispatch_key"],
                graph_id=values["graph_id"],
                program_digest=values["program_digest"],
                plan_digest=values["plan_digest"],
                graph_run_id=values["graph_run_id"],
                thread_id=values["thread_id"],
                scope_digest=values["scope_digest"],
                issued_at=datetime.fromisoformat(values["issued_at"]),
                expires_at=datetime.fromisoformat(values["expires_at"]),
            )
        except (TypeError, ValueError) as exc:
            raise MissionAuthorityDenied(
                "authority grant timestamps are invalid"
            ) from exc


class MissionAuthority(Protocol):
    async def authorize(
        self, request: MissionDispatchRequest
    ) -> MissionDispatchGrant: ...

    async def validate(
        self, request: MissionDispatchRequest, grant: MissionDispatchGrant
    ) -> bool: ...


class MissionPlanSource(Protocol):
    async def current_plan_digest(
        self, mission_id: str, task_id: str, dispatch_key: str
    ) -> str: ...


class MissionExecutionPort(Protocol):
    """Shadow execution port; production use owes PRODUCTION_PROMOTION_BLOCKER."""

    async def dispatch(
        self, mission_id: str, task_id: str, *, dispatch_key: str = "default"
    ) -> OwnerExecutionRef: ...

    async def observe(self, ref: OwnerExecutionRef) -> OwnerExecutionObservation: ...


@dataclass(slots=True)
class _ObservationBudget:
    maximum: int
    used: int = 0


class _MissionPersistenceView:
    """CAS-enforcing view consumed by the existing graph persistence runtime."""

    def __init__(
        self,
        kernel: GraphPersistenceKernel,
        thread_id: str,
        expected_latest_checkpoint_id: str | None,
    ) -> None:
        self.kernel = kernel
        self.thread_id = thread_id
        self.expected_latest_checkpoint_id = expected_latest_checkpoint_id

    def _require_thread(self, thread_id: str) -> None:
        if thread_id != self.thread_id:
            raise MissionGraphError(
                "mission persistence view received a foreign thread"
            )

    def get_checkpoint_record(
        self, thread_id: str, checkpoint_id: str | None = None
    ) -> GraphCheckpointRecord | None:
        self._require_thread(thread_id)
        return self.kernel.get_checkpoint_record(thread_id, checkpoint_id)

    def get_state_history(self, thread_id: str) -> list[GraphCheckpointRecord]:
        self._require_thread(thread_id)
        return self.kernel.get_state_history(thread_id)

    def recover_pending_writes(self, thread_id: str):
        self._require_thread(thread_id)
        return self.kernel.recover_pending_writes(thread_id)

    def put_writes(
        self,
        thread_id: str,
        writes,
        task_id: str,
        *,
        checkpoint_id: str | None = None,
        task_path: str = "",
    ) -> None:
        self._require_thread(thread_id)
        self.kernel.put_writes_cas(
            thread_id,
            writes,
            task_id,
            expected_latest_checkpoint_id=self.expected_latest_checkpoint_id,
            checkpoint_id=checkpoint_id,
            task_path=task_path,
        )

    def clear_pending_writes(self, thread_id: str, task_id: str | None = None) -> None:
        self._require_thread(thread_id)
        self.kernel.clear_pending_writes_cas(
            thread_id,
            task_id,
            expected_latest_checkpoint_id=self.expected_latest_checkpoint_id,
        )

    def put_run_checkpoint(
        self,
        thread_id: str,
        checkpoint: RunCheckpoint,
        *,
        checkpoint_id: str | None = None,
        parent_checkpoint_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> GraphCheckpointRecord:
        self._require_thread(thread_id)
        record = self.kernel.put_run_checkpoint_cas(
            thread_id,
            checkpoint,
            expected_latest_checkpoint_id=self.expected_latest_checkpoint_id,
            checkpoint_id=checkpoint_id,
            parent_checkpoint_id=parent_checkpoint_id,
            metadata=metadata,
        )
        self.expected_latest_checkpoint_id = record.checkpoint_id
        return record

    def assert_latest(self) -> None:
        self.kernel.assert_latest(self.thread_id, self.expected_latest_checkpoint_id)


@dataclass(frozen=True, slots=True)
class MissionGraphContext:
    execution: MissionExecutionPort
    authority: MissionAuthority
    plan_source: MissionPlanSource
    clock: Callable[[], datetime]
    persistence: _MissionPersistenceView
    observation_budget: _ObservationBudget
    observation_poll_delay: float


class _MissionState(TypedDict, total=False):
    mission_id: str
    task_id: str
    dispatch_key: str
    graph_id: str
    program_digest: str
    plan_digest: str
    graph_run_id: str
    thread_id: str
    authority_grant: dict[str, str]
    authority_generation: int
    dispatch_outcome: str
    owner_execution: dict[str, str]
    owner_observation: dict[str, Any]
    observation_count: int


@dataclass(frozen=True, slots=True)
class MissionGraphRun:
    graph: GraphRunResult
    request: MissionDispatchRequest
    grant: MissionDispatchGrant
    authority_generation: int
    owner: OwnerExecutionRef
    observation: OwnerExecutionObservation


class MissionControlGraphBridge:
    """Run one stable Mission Control dispatch as a durable graph thread."""

    def __init__(
        self,
        execution: MissionExecutionPort,
        authority: MissionAuthority,
        persistence: GraphPersistenceKernel,
        *,
        plan_source: MissionPlanSource,
        clock: Callable[[], datetime] = utc_now,
        max_observation_polls: int = 8,
        observation_poll_delay: float = 0.25,
    ) -> None:
        if max_observation_polls <= 0:
            raise ValueError("max_observation_polls must be positive")
        if observation_poll_delay < 0:
            raise ValueError("observation_poll_delay must be non-negative")
        self._execution = execution
        self._authority = authority
        self._plan_source = plan_source
        self._persistence = persistence
        self._clock = clock
        self._max_observation_polls = max_observation_polls
        self._observation_poll_delay = observation_poll_delay
        self._graph = _compile_graph()

    async def run(
        self, mission_id: str, task_id: str, *, dispatch_key: str = "default"
    ) -> MissionGraphRun:
        thread_id = MissionDispatchRequest.thread_id_for(
            mission_id, task_id, dispatch_key
        )
        try:
            with self._persistence.run_lease(thread_id):
                if self._persistence.get_state_history(thread_id):
                    raise MissionResumeRequired(
                        f"mission graph thread {thread_id!r} already exists; resume it"
                    )
                plan_digest = await _resolve_plan_digest(
                    self._plan_source, mission_id, task_id, dispatch_key
                )
                request = MissionDispatchRequest.create(
                    mission_id, task_id, plan_digest, dispatch_key
                )
                persistence = _MissionPersistenceView(
                    self._persistence, request.thread_id, None
                )
                return await self._invoke_locked(
                    request, request.to_state(), persistence
                )
        except GraphThreadBusyError as exc:
            raise MissionThreadBusy(str(exc)) from exc

    async def resume(
        self, mission_id: str, task_id: str, *, dispatch_key: str = "default"
    ) -> MissionGraphRun:
        thread_id = MissionDispatchRequest.thread_id_for(
            mission_id, task_id, dispatch_key
        )
        try:
            with self._persistence.run_lease(thread_id):
                latest = self._persistence.get_checkpoint_record(thread_id)
                if latest is None:
                    raise MissionGraphError(
                        f"mission graph thread {thread_id!r} has no durable checkpoint"
                    )
                request = _request_from_checkpoint(
                    latest, mission_id, task_id, dispatch_key
                )
                persistence = _MissionPersistenceView(
                    self._persistence, request.thread_id, latest.checkpoint_id
                )
                return await self._invoke_locked(request, None, persistence)
        except GraphThreadBusyError as exc:
            raise MissionThreadBusy(str(exc)) from exc

    async def _invoke_locked(
        self,
        request: MissionDispatchRequest,
        seed: Mapping[str, Any] | None,
        persistence: _MissionPersistenceView,
    ) -> MissionGraphRun:
        context = MissionGraphContext(
            execution=self._execution,
            authority=self._authority,
            plan_source=self._plan_source,
            clock=self._clock,
            persistence=persistence,
            observation_budget=_ObservationBudget(self._max_observation_polls),
            observation_poll_delay=self._observation_poll_delay,
        )
        graph = await self._graph.invoke(
            seed,
            context=context,
            graph_run_id=request.graph_run_id,
            persistence=persistence,
            thread_id=request.thread_id,
            superstep_cap=max(16, self._max_observation_polls * 3 + 12),
        )
        if graph.graph_id != GRAPH_ID or graph.graph_run_id != request.graph_run_id:
            raise MissionGraphError("completed graph returned a foreign graph identity")
        persisted_request = MissionDispatchRequest.from_state(graph.state)
        if persisted_request != request:
            raise MissionGraphError("completed graph returned a foreign request")
        grant = MissionDispatchGrant.from_state(graph.state.get("authority_grant"))
        generation = graph.state.get("authority_generation")
        if type(generation) is not int or generation < 1:
            raise MissionGraphError("authority generation is invalid")
        owner = _owner_from_state(graph.state.get("owner_execution"))
        observation = _observation_from_state(graph.state.get("owner_observation"))
        if owner != observation.ref:
            raise MissionGraphError("owner observation refers to a foreign execution")
        if not observation.terminal:
            raise MissionObservationPending(
                "a nonterminal owner observation cannot complete the mission graph"
            )
        return MissionGraphRun(graph, request, grant, generation, owner, observation)


async def _resolve_plan_digest(
    plan_source: MissionPlanSource,
    mission_id: str,
    task_id: str,
    dispatch_key: str,
) -> str:
    try:
        digest = await plan_source.current_plan_digest(
            mission_id, task_id, dispatch_key
        )
    except MissionGraphError:
        raise
    except Exception as exc:
        raise MissionAuthorityDenied("task-plan source failed closed") from exc
    return _require_digest(digest, "current plan digest")


async def _require_current_plan(
    context: MissionGraphContext, request: MissionDispatchRequest
) -> None:
    current = await _resolve_plan_digest(
        context.plan_source,
        request.mission_id,
        request.task_id,
        request.dispatch_key,
    )
    if current != request.plan_digest:
        raise MissionPlanChanged(
            "task plan changed after authority admission; refusing dispatch"
        )


def _request_from_checkpoint(
    record: GraphCheckpointRecord,
    mission_id: str,
    task_id: str,
    dispatch_key: str,
) -> MissionDispatchRequest:
    checkpoint = record.checkpoint
    if checkpoint.graph_id != GRAPH_ID:
        raise MissionGraphError(
            f"checkpoint graph_id {checkpoint.graph_id!r} is foreign to {GRAPH_ID!r}"
        )
    request = MissionDispatchRequest.from_state(record.state)
    expected_ids = (
        clean_identifier(mission_id, "mission_id"),
        clean_identifier(task_id, "task_id"),
        clean_identifier(dispatch_key, "dispatch_key"),
    )
    if (request.mission_id, request.task_id, request.dispatch_key) != expected_ids:
        raise MissionGraphError("checkpoint request does not match resume arguments")
    if record.thread_id != request.thread_id:
        raise MissionGraphError("checkpoint is stored under a foreign thread")
    if checkpoint.graph_run_id != request.graph_run_id:
        raise MissionGraphError("checkpoint graph_run_id is foreign to its request")
    return request


def _compile_graph() -> TypedCompiledGraph:
    async def admit(
        state: Mapping[str, Any], context: MissionGraphContext
    ) -> Mapping[str, Any]:
        request = MissionDispatchRequest.from_state(state)
        await _require_current_plan(context, request)
        grant = await _authorize(context, request, "admission")
        return {
            "authority_grant": grant.to_state(),
            "authority_generation": 1,
            "dispatch_outcome": "",
        }

    async def reauthorize(
        state: Mapping[str, Any], context: MissionGraphContext
    ) -> Mapping[str, Any]:
        request = MissionDispatchRequest.from_state(state)
        await _require_current_plan(context, request)
        old = MissionDispatchGrant.from_state(state.get("authority_grant"))
        generation = state.get("authority_generation")
        if type(generation) is not int or generation < 1:
            raise MissionAuthorityDenied("authority generation is invalid")
        grant = await _authorize(context, request, "reauthorization")
        if grant.grant_id == old.grant_id:
            raise MissionAuthorityDenied(
                "reauthorization must issue a distinct grant identity"
            )
        return {
            "authority_grant": grant.to_state(),
            "authority_generation": generation + 1,
            "dispatch_outcome": "",
        }

    async def dispatch(
        state: Mapping[str, Any], context: MissionGraphContext
    ) -> Mapping[str, Any]:
        request = MissionDispatchRequest.from_state(state)
        grant = MissionDispatchGrant.from_state(state.get("authority_grant"))
        try:
            grant.validate_shape(request, now=context.clock())
        except MissionGrantExpired:
            return {"dispatch_outcome": "reauthorize"}

        await _require_current_plan(context, request)
        try:
            grant.validate_shape(request, now=context.clock())
        except MissionGrantExpired:
            return {"dispatch_outcome": "reauthorize"}
        try:
            valid = await context.authority.validate(request, grant)
        except MissionAuthorityDenied:
            raise
        except Exception as exc:
            raise MissionAuthorityDenied(
                "authority source failed at the pre-effect boundary"
            ) from exc
        if valid is not True:
            raise MissionAuthorityDenied(
                "authority source rejected the grant at the pre-effect boundary"
            )
        context.persistence.assert_latest()
        owner = await context.execution.dispatch(
            request.mission_id,
            request.task_id,
            dispatch_key=request.dispatch_key,
        )
        if not isinstance(owner, OwnerExecutionRef):
            raise MissionGraphError("executor returned no typed owner reference")
        if (
            owner.mission_id,
            owner.task_id,
            owner.dispatch_key,
        ) != (request.mission_id, request.task_id, request.dispatch_key):
            raise MissionGraphError("executor returned a foreign owner reference")
        return {
            "owner_execution": _owner_to_state(owner),
            "dispatch_outcome": "dispatched",
        }

    async def observe(
        state: Mapping[str, Any], context: MissionGraphContext
    ) -> Mapping[str, Any]:
        owner = _owner_from_state(state.get("owner_execution"))
        observation = await context.execution.observe(owner)
        encoded = _validated_observation_state(observation)
        validated = _observation_from_state(encoded)
        if validated.ref != owner:
            raise MissionGraphError("executor observed a foreign owner reference")
        context.observation_budget.used += 1
        count = state.get("observation_count", 0)
        if type(count) is not int or count < 0:
            raise MissionGraphError("observation count is invalid")
        return {"owner_observation": encoded, "observation_count": count + 1}

    async def wait_owner(
        _state: Mapping[str, Any], context: MissionGraphContext
    ) -> Mapping[str, Any]:
        if context.observation_budget.used >= context.observation_budget.maximum:
            raise MissionObservationPending(
                "owner remains nonterminal after the bounded observation budget"
            )
        if context.observation_poll_delay:
            await asyncio.sleep(context.observation_poll_delay)
        return {}

    def route_dispatch(state: Mapping[str, Any]) -> str:
        outcome = state.get("dispatch_outcome")
        if outcome not in {"reauthorize", "dispatched"}:
            raise MissionGraphError("dispatch outcome is invalid")
        return str(outcome)

    def route_observation(state: Mapping[str, Any]) -> str:
        observation = _observation_from_state(state.get("owner_observation"))
        return "terminal" if observation.terminal else "nonterminal"

    return (
        TypedStateGraph(_MissionState, context=MissionGraphContext, graph_id=GRAPH_ID)
        .add_node("admit_authority", admit)
        .add_node("dispatch_owner", dispatch)
        .add_node("dispatch_reauthorized", dispatch)
        .add_node("reauthorize_authority", reauthorize)
        .add_node("observe_owner", observe)
        .add_node("wait_owner", wait_owner)
        .add_edge(START, "admit_authority")
        .add_edge("admit_authority", "dispatch_owner")
        .add_conditional_edges(
            "dispatch_owner",
            route_dispatch,
            {
                "reauthorize": "reauthorize_authority",
                "dispatched": "observe_owner",
            },
        )
        .add_edge("reauthorize_authority", "dispatch_reauthorized")
        .add_conditional_edges(
            "dispatch_reauthorized",
            route_dispatch,
            {
                "reauthorize": "reauthorize_authority",
                "dispatched": "observe_owner",
            },
        )
        .add_conditional_edges(
            "observe_owner",
            route_observation,
            {"terminal": END, "nonterminal": "wait_owner"},
        )
        .add_edge("wait_owner", "observe_owner")
        .compile(allow_cycles=True)
    )


async def _authorize(
    context: MissionGraphContext,
    request: MissionDispatchRequest,
    phase: str,
) -> MissionDispatchGrant:
    try:
        grant = await context.authority.authorize(request)
    except MissionAuthorityDenied:
        raise
    except Exception as exc:
        raise MissionAuthorityDenied(f"authority source failed during {phase}") from exc
    if not isinstance(grant, MissionDispatchGrant):
        raise MissionAuthorityDenied("authority source returned no typed grant")
    grant.validate_shape(request, now=context.clock())
    return grant


_GRANT_FIELDS = frozenset(
    {
        "grant_id",
        "principal_id",
        "mission_id",
        "task_id",
        "dispatch_key",
        "graph_id",
        "program_digest",
        "plan_digest",
        "graph_run_id",
        "thread_id",
        "scope_digest",
        "issued_at",
        "expires_at",
    }
)
_OWNER_FIELDS = frozenset(
    {
        "backend",
        "mission_id",
        "task_id",
        "dispatch_key",
        "run_id",
        "claim_id",
        "agent_id",
        "idempotency_key",
        "owner_session_id",
    }
)
_OBSERVATION_FIELDS = frozenset(
    {
        "ref",
        "task_status",
        "run_status",
        "claim_status",
        "stale",
        "receipt_ids",
        "terminal",
        "succeeded",
        "result",
        "failure_code",
        "observed_at",
        "proves_executor_liveness",
    }
)


def _exact_string_mapping(
    raw: Any, fields: frozenset[str], label: str
) -> dict[str, str]:
    if not isinstance(raw, Mapping) or set(raw) != fields:
        raise MissionGraphError(f"{label} has an invalid closed shape")
    values = dict(raw)
    if any(not isinstance(values[field], str) for field in fields):
        raise MissionGraphError(f"{label} contains a non-string identity field")
    return values


def _aware_utc(
    value: datetime, label: str, error_type: type[MissionGraphError]
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise error_type(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _owner_to_state(ref: OwnerExecutionRef) -> dict[str, str]:
    if not isinstance(ref, OwnerExecutionRef):
        raise MissionGraphError("owner execution is not a typed reference")
    values = {field: str(getattr(ref, field)) for field in _OWNER_FIELDS}
    if any(not value.strip() for value in values.values()):
        raise MissionGraphError("owner execution contains a blank identity")
    return values


def _owner_from_state(raw: Any) -> OwnerExecutionRef:
    values = _exact_string_mapping(raw, _OWNER_FIELDS, "owner execution")
    if any(not value.strip() for value in values.values()):
        raise MissionGraphError("owner execution contains a blank identity")
    return OwnerExecutionRef(**values)


def _validated_observation_state(observation: Any) -> dict[str, Any]:
    if not isinstance(observation, OwnerExecutionObservation):
        raise MissionGraphError("executor returned no typed owner observation")
    encoded = _observation_to_state(observation)
    if _observation_from_state(encoded) != observation:
        raise MissionGraphError("owner observation changed during validation")
    return encoded


def _observation_to_state(observation: OwnerExecutionObservation) -> dict[str, Any]:
    return {
        "ref": _owner_to_state(observation.ref),
        "task_status": observation.task_status.value,
        "run_status": observation.run_status,
        "claim_status": observation.claim_status,
        "stale": observation.stale,
        "receipt_ids": list(observation.receipt_ids),
        "terminal": observation.terminal,
        "succeeded": observation.succeeded,
        "result": observation.result,
        "failure_code": observation.failure_code,
        "observed_at": _aware_utc(
            observation.observed_at, "observed_at", MissionGraphError
        ).isoformat(),
        "proves_executor_liveness": observation.proves_executor_liveness,
    }


def _observation_from_state(raw: Any) -> OwnerExecutionObservation:
    if not isinstance(raw, Mapping) or set(raw) != _OBSERVATION_FIELDS:
        raise MissionGraphError("owner observation has an invalid closed shape")
    receipt_ids = raw["receipt_ids"]
    if not isinstance(receipt_ids, list) or any(
        not isinstance(value, str) or not value.strip() for value in receipt_ids
    ):
        raise MissionGraphError("owner observation receipt IDs are invalid")
    string_fields = (
        "task_status",
        "run_status",
        "claim_status",
        "result",
        "failure_code",
        "observed_at",
    )
    if any(not isinstance(raw[field], str) for field in string_fields):
        raise MissionGraphError("owner observation string fields are invalid")
    if any(
        type(raw[field]) is not bool for field in ("stale", "terminal", "succeeded")
    ):
        raise MissionGraphError("owner observation boolean fields are invalid")
    if raw["proves_executor_liveness"] is not False:
        raise MissionGraphError("owner records cannot prove executor liveness")
    try:
        observed_at = datetime.fromisoformat(raw["observed_at"])
        task_status = TaskStatus(raw["task_status"])
    except (TypeError, ValueError) as exc:
        raise MissionGraphError("owner observation values are invalid") from exc
    observed_at = _aware_utc(observed_at, "observed_at", MissionGraphError)
    terminal_statuses = {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    }
    if raw["succeeded"] and (
        not raw["terminal"] or task_status != TaskStatus.COMPLETED
    ):
        raise MissionGraphError("owner observation success semantics are inconsistent")
    if raw["terminal"] != (task_status in terminal_statuses):
        raise MissionGraphError("owner observation terminal semantics are inconsistent")
    return OwnerExecutionObservation(
        ref=_owner_from_state(raw["ref"]),
        task_status=task_status,
        run_status=raw["run_status"],
        claim_status=raw["claim_status"],
        stale=raw["stale"],
        receipt_ids=tuple(receipt_ids),
        terminal=raw["terminal"],
        succeeded=raw["succeeded"],
        result=raw["result"],
        failure_code=raw["failure_code"],
        observed_at=observed_at,
        proves_executor_liveness=False,
    )
