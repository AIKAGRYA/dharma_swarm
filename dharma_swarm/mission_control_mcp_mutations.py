"""Authorized mutation support for the Mission Control MCP service."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeAlias

from dharma_swarm.models import TaskPriority


AUTHORIZED_PRINCIPAL_METADATA_KEY = "mission_control_authorized_principal"

MISSION_CREATE = "mission_create"
MISSION_CREATE_TASK = "mission_create_task"
MISSION_START_ATTEMPT = "mission_start_attempt"
MISSION_HEARTBEAT_LEASE = "mission_heartbeat_lease"
MISSION_FINISH_ATTEMPT = "mission_finish_attempt"
MISSION_FINISH_ATTEMPT_FROM_PATCH_EFFECT = (
    "mission_finish_attempt_from_patch_effect"
)

MUTATION_TOOL_NAMES = (
    MISSION_CREATE,
    MISSION_CREATE_TASK,
    MISSION_START_ATTEMPT,
    MISSION_HEARTBEAT_LEASE,
    MISSION_FINISH_ATTEMPT,
    MISSION_FINISH_ATTEMPT_FROM_PATCH_EFFECT,
)


@dataclass(frozen=True, slots=True)
class MutationRequest:
    """Minimal, non-secret context presented to a mutation authorizer.

    Descriptions, results, evidence, and metadata are intentionally excluded so
    an authorization integration cannot accidentally treat request content as
    a bearer credential or leak it through policy logs.
    """

    tool_name: str
    principal: str
    mission_id: str
    task_id: str = ""
    attempt_id: str = ""
    attempt_key: str = ""
    agent_id: str = ""
    operator_id: str = ""
    created_by: str = ""
    assigned_by: str = ""
    priority: str = ""
    dependency_count: int = 0
    dependency_ids: tuple[str, ...] = ()
    has_idempotency_key: bool = False
    lease_seconds: int | None = None
    terminal_status: str = ""
    failure_code_present: bool = False
    effect_key: str = ""


MutationDecision: TypeAlias = bool | Awaitable[bool]
MutationAuthorizer: TypeAlias = Callable[[MutationRequest], MutationDecision]
PrincipalDecision: TypeAlias = str | Awaitable[str]
TrustedPrincipalResolver: TypeAlias = Callable[[], PrincipalDecision]
TrustedPrincipal: TypeAlias = str | TrustedPrincipalResolver


class _ArgumentError(ValueError):
    """A safe, caller-correctable MCP argument error."""


def _normalize_lease_seconds(value: Any) -> int:
    """Return an authorization-safe lease duration without bool coercion."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _ArgumentError("lease_ttl_seconds must be a positive integer")
    return value


def _normalize_identifier(value: Any, label: str) -> str:
    """Mirror Mission Control identifier normalization before authorization."""

    normalized = str(value or "").strip()
    if not normalized:
        raise _ArgumentError(f"{label} is required")
    if any(character.isspace() for character in normalized):
        raise _ArgumentError(f"{label} must not contain whitespace")
    return normalized


def _authorized_metadata(
    metadata: Mapping[str, Any] | None,
    principal: str,
) -> dict[str, Any]:
    """Copy caller metadata and stamp the transport-authenticated identity."""

    return {
        **dict(metadata or {}),
        AUTHORIZED_PRINCIPAL_METADATA_KEY: principal,
    }


def _normalize_priority(value: Any) -> TaskPriority:
    try:
        return TaskPriority(value)
    except (TypeError, ValueError) as exc:
        raise _ArgumentError(f"invalid task priority: {value!r}") from exc


def _normalize_terminal_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in {"succeeded", "failed"}:
        raise _ArgumentError("outcome must be 'succeeded' or 'failed'")
    return normalized


class _MissionControlMCPMutations:
    """Mutation methods mixed into the public Mission Control MCP service."""

    async def create_mission(
        self,
        mission_id: str,
        title: str,
        objective: str = "",
        *,
        operator_id: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool_name = MISSION_CREATE
        return await self._mutate(
            tool_name,
            lambda principal: MutationRequest(
                tool_name=tool_name,
                principal=principal,
                mission_id=_normalize_identifier(mission_id, "mission_id"),
                operator_id=principal,
            ),
            lambda request: self._control.create_mission(
                request.mission_id,
                title=title,
                goal=objective,
                operator_id=request.principal,
                metadata=_authorized_metadata(metadata, request.principal),
            ),
        )

    async def create_task(
        self,
        mission_id: str,
        title: str,
        description: str = "",
        *,
        priority: str = "normal",
        created_by: str = "system",
        depends_on: list[str] | None = None,
        idempotency_key: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool_name = MISSION_CREATE_TASK

        def request_factory(principal: str) -> MutationRequest:
            parsed_priority = _normalize_priority(priority)
            dependency_ids = tuple(
                _normalize_identifier(item, "depends_on item")
                for item in (depends_on or ())
            )
            return MutationRequest(
                tool_name=tool_name,
                principal=principal,
                mission_id=_normalize_identifier(mission_id, "mission_id"),
                created_by=principal,
                priority=parsed_priority.value,
                dependency_count=len(dependency_ids),
                dependency_ids=dependency_ids,
                has_idempotency_key=bool(str(idempotency_key or "").strip()),
            )

        async def operation(request: MutationRequest) -> Any:
            return await self._control.create_task(
                request.mission_id,
                title=title,
                description=description,
                priority=TaskPriority(request.priority),
                created_by=request.principal,
                depends_on=(
                    list(request.dependency_ids) if depends_on is not None else None
                ),
                idempotency_key=idempotency_key,
                metadata=_authorized_metadata(metadata, request.principal),
            )

        return await self._mutate(tool_name, request_factory, operation)

    async def start_attempt(
        self,
        mission_id: str,
        task_id: str,
        attempt_key: str,
        agent_id: str,
        *,
        lease_ttl_seconds: int = 300,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool_name = MISSION_START_ATTEMPT
        return await self._mutate(
            tool_name,
            lambda principal: MutationRequest(
                tool_name=tool_name,
                principal=principal,
                mission_id=_normalize_identifier(mission_id, "mission_id"),
                task_id=_normalize_identifier(task_id, "task_id"),
                attempt_key=str(attempt_key or "").strip(),
                agent_id=_normalize_identifier(agent_id, "agent_id"),
                assigned_by=principal,
                lease_seconds=_normalize_lease_seconds(lease_ttl_seconds),
            ),
            lambda request: self._control.start_attempt(
                request.mission_id,
                request.task_id,
                request.agent_id,
                attempt_key=request.attempt_key,
                lease_seconds=request.lease_seconds,
                assigned_by=request.principal,
                metadata=_authorized_metadata(metadata, request.principal),
            ),
        )

    async def heartbeat_lease(
        self,
        mission_id: str,
        task_id: str,
        attempt_id: str,
        agent_id: str,
        *,
        lease_ttl_seconds: int = 300,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool_name = MISSION_HEARTBEAT_LEASE
        return await self._mutate(
            tool_name,
            lambda principal: MutationRequest(
                tool_name=tool_name,
                principal=principal,
                mission_id=_normalize_identifier(mission_id, "mission_id"),
                task_id=_normalize_identifier(task_id, "task_id"),
                attempt_id=_normalize_identifier(attempt_id, "attempt_id"),
                agent_id=_normalize_identifier(agent_id, "agent_id"),
                lease_seconds=_normalize_lease_seconds(lease_ttl_seconds),
            ),
            lambda request: self._control.heartbeat_lease(
                request.mission_id,
                request.task_id,
                request.agent_id,
                attempt_id=request.attempt_id,
                lease_seconds=request.lease_seconds,
                metadata=_authorized_metadata(metadata, request.principal),
            ),
        )

    async def finish_attempt(
        self,
        mission_id: str,
        task_id: str,
        attempt_id: str,
        agent_id: str,
        outcome: str,
        *,
        result: str = "",
        error: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool_name = MISSION_FINISH_ATTEMPT
        return await self._mutate(
            tool_name,
            lambda principal: MutationRequest(
                tool_name=tool_name,
                principal=principal,
                mission_id=_normalize_identifier(mission_id, "mission_id"),
                task_id=_normalize_identifier(task_id, "task_id"),
                attempt_id=_normalize_identifier(attempt_id, "attempt_id"),
                agent_id=_normalize_identifier(agent_id, "agent_id"),
                terminal_status=_normalize_terminal_status(outcome),
                failure_code_present=bool(str(error or "").strip()),
            ),
            lambda request: self._control.finish_attempt(
                request.mission_id,
                request.task_id,
                request.agent_id,
                attempt_id=request.attempt_id,
                status=request.terminal_status,
                result=result,
                failure_code=error,
                metadata=_authorized_metadata(metadata, request.principal),
            ),
        )

    async def finish_attempt_from_patch_effect(
        self,
        mission_id: str,
        task_id: str,
        attempt_id: str,
        agent_id: str,
        effect_key: str,
    ) -> dict[str, Any]:
        tool_name = MISSION_FINISH_ATTEMPT_FROM_PATCH_EFFECT
        return await self._mutate(
            tool_name,
            lambda principal: MutationRequest(
                tool_name=tool_name,
                principal=principal,
                mission_id=_normalize_identifier(mission_id, "mission_id"),
                task_id=_normalize_identifier(task_id, "task_id"),
                attempt_id=_normalize_identifier(attempt_id, "attempt_id"),
                agent_id=_normalize_identifier(agent_id, "agent_id"),
                effect_key=_normalize_identifier(effect_key, "effect_key"),
                terminal_status="succeeded",
            ),
            lambda request: self._control.finish_attempt_from_patch_effect(
                request.mission_id,
                request.task_id,
                request.agent_id,
                attempt_id=request.attempt_id,
                effect_key=request.effect_key,
            ),
        )

    async def _mutate(
        self,
        tool_name: str,
        request_factory: Callable[[str], MutationRequest],
        operation: Callable[[MutationRequest], Awaitable[Any]],
    ) -> dict[str, Any]:
        if self._mutation_authorizer is None:
            return self._mutation_denied(tool_name)
        principal = await self._resolve_trusted_principal()
        if principal is None:
            return self._mutation_denied(tool_name)
        try:
            request = request_factory(principal)
        except Exception as exc:
            return self._failure(tool_name, exc)
        if not await self._is_authorized(request):
            return self._mutation_denied(tool_name)
        try:
            return self._success(tool_name, await operation(request))
        except Exception as exc:
            return self._failure(tool_name, exc)

    async def _is_authorized(self, request: MutationRequest) -> bool:
        authorizer = self._mutation_authorizer
        if authorizer is None:
            return False
        try:
            decision = authorizer(request)
            if inspect.isawaitable(decision):
                decision = await decision
        except Exception:
            return False
        return decision is True

    async def _resolve_trusted_principal(self) -> str | None:
        source = self._trusted_principal
        if source is None:
            return None
        try:
            principal = source() if callable(source) else source
            if inspect.isawaitable(principal):
                principal = await principal
        except Exception:
            return None
        if not isinstance(principal, str):
            return None
        normalized = principal.strip()
        if (
            not normalized
            or len(normalized) > 256
            or any(
                character.isspace() or ord(character) < 32 for character in normalized
            )
        ):
            return None
        return normalized

    def _mutation_denied(self, tool_name: str) -> dict[str, Any]:
        return self._error(
            tool_name,
            "mutation_not_authorized",
            "mutation denied: this Mission Control MCP surface is read-only by default",
        )
