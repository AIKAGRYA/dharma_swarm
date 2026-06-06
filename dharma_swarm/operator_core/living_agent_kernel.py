"""Living agent kernel contract for governed agent runs.

This module is a narrow envelope around existing operator-core organs. It
persists canonical kernel events and dispatches only kernel-owned read-only
tools plus a bounded apply_patch adapter. It also owns an append-only wake
ledger for bounded resume tests. It does not dispatch providers, run
subprocess tools, start a daemon, or replace persistent-agent runtimes.
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from dharma_swarm.event_log import EventLog
from dharma_swarm.operator_core.governed_work_admission import (
    GovernedWorkAdmission,
    GovernedWorkRequest,
    WorkKind,
    evaluate_governed_work_admission,
)
from dharma_swarm.operator_core.runtime_truth import (
    MutationTruth,
    RuntimeSourceKind,
    RuntimeTruthPacket,
    RuntimeTruthState,
    sha256_file,
    stable_payload_hash,
    utc_now,
)
from dharma_swarm.runtime_contract import RuntimeEnvelope, RuntimeEventType

KernelRunStatus = Literal["completed", "review", "blocked", "failed"]
KernelToolStatus = Literal["completed", "denied", "failed"]
KernelWakeStatus = Literal["queued", "leased", "completed", "review", "blocked", "failed"]
KernelWakeExecutionStatus = Literal["idle", "completed", "review", "blocked", "failed"]
KernelWakeSource = Literal["manual", "a2a", "ds_goal", "persistent_self_wake", "external_fleet", "subagent"]
KernelSourceClosebackStatus = Literal["closed", "recorded", "refused", "blocked"]
KernelSubagentDispatchStatus = Literal["spawned", "denied"]
KernelDaemonControlAction = Literal["pause", "resume", "stop"]
KernelDaemonStateStatus = Literal["running", "paused", "stopped"]
KernelDaemonCycleStatus = Literal["idle", "completed", "review", "blocked", "failed", "paused", "stopped"]
DEFAULT_KERNEL_RUN_DIR = Path.home() / ".dharma" / "living_agent_kernel"
KERNEL_EVENT_STREAM = "kernel_events"
KERNEL_SOURCE = "operator_core.living_agent_kernel"

READ_ONLY_TOOLS = ("memory_read", "read_file", "search_files", "session_status")
WRITE_TOOLS = ("apply_patch", "compileall", "pytest", "memory_write")
DANGEROUS_TOOLS = ("deploy", "external_outreach", "payment", "publish", "push_merge")
SELF_EVOLUTION_TOOLS = ("self_edit", "skill_promote")
EVIDENCE_ONLY_DENIED_TOOLS = (
    "apply_patch",
    "deploy",
    "external_outreach",
    "payment",
    "process_spawn",
    "publish",
    "push_merge",
    "self_edit",
    "skill_promote",
    "write_file",
)


def _new_run_id() -> str:
    return f"kernel_run_{uuid4().hex[:16]}"


def _model_payload(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    return value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)


def _sorted_unique(values: list[str] | tuple[str, ...]) -> list[str]:
    return sorted({str(value) for value in values if str(value)})


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")


def _write_jsonl_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    tmp.replace(path)


def _utc_datetime(value: str) -> datetime:
    raw = value.strip()
    if not raw:
        return datetime.fromtimestamp(0, UTC)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    observed = datetime.fromisoformat(raw)
    if observed.tzinfo is None:
        return observed.replace(tzinfo=UTC)
    return observed.astimezone(UTC)


def _utc_after(value: str, seconds: int) -> str:
    return (
        _utc_datetime(value)
        + timedelta(seconds=max(1, int(seconds)))
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _allowed_path(target: Path, allowed_files: list[str], *, workspace_root: Path) -> bool:
    if not allowed_files:
        return False
    resolved_target = target.expanduser()
    if not resolved_target.is_absolute():
        resolved_target = workspace_root / resolved_target
    resolved_target = resolved_target.resolve()
    for raw in allowed_files:
        allowed = Path(raw).expanduser()
        if not allowed.is_absolute():
            allowed = workspace_root / allowed
        allowed = allowed.resolve()
        if resolved_target == allowed:
            return True
        if allowed.exists() and allowed.is_dir() and resolved_target.is_relative_to(allowed):
            return True
    return False


def _workspace_relative_path(target: Path, *, workspace_root: Path) -> str:
    resolved_target = target.expanduser()
    if not resolved_target.is_absolute():
        resolved_target = workspace_root / resolved_target
    try:
        return resolved_target.resolve().relative_to(workspace_root.resolve()).as_posix()
    except ValueError:
        return ""


def _repo_pattern_matches(relative_path: str, pattern: str) -> bool:
    normalized = str(pattern).strip().replace("\\", "/")
    if not relative_path or not normalized or normalized.startswith("/"):
        return False
    posix = PurePosixPath(normalized)
    if any(part == ".." for part in posix.parts):
        return False
    if fnmatch.fnmatchcase(relative_path, normalized):
        return True
    if normalized.endswith("/"):
        return relative_path.startswith(normalized)
    return fnmatch.fnmatchcase(relative_path, f"{normalized}/**")


def _path_matches_contract(target: Path, patterns: list[str], *, workspace_root: Path) -> bool:
    if not patterns:
        return False
    if _allowed_path(target, patterns, workspace_root=workspace_root):
        return True
    relative = _workspace_relative_path(target, workspace_root=workspace_root)
    return any(_repo_pattern_matches(relative, pattern) for pattern in patterns)


def _contract_pattern_allowed(raw_pattern: str, parent_patterns: list[str], *, workspace_root: Path) -> bool:
    pattern = str(raw_pattern or "").strip().replace("\\", "/")
    if not pattern:
        return False
    if pattern in parent_patterns:
        return True
    if any(ch in pattern for ch in "*?[]"):
        return False
    candidate = Path(pattern).expanduser()
    candidate = candidate if candidate.is_absolute() else workspace_root / candidate
    if _path_matches_contract(candidate, parent_patterns, workspace_root=workspace_root):
        return True
    normalized = pattern.rstrip("/") + "/"
    for parent in parent_patterns:
        parent_norm = str(parent).strip().replace("\\", "/")
        if parent_norm.endswith("/") and normalized.startswith(parent_norm):
            return True
    return False


def _safe_diff_target(raw_path: str) -> str:
    candidate = str(raw_path or "").strip().replace("\\", "/")
    if not candidate or candidate.startswith("/"):
        return ""
    posix = PurePosixPath(candidate)
    if any(part in {"", ".", ".."} for part in posix.parts):
        return ""
    return posix.as_posix()


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    return [str(value)] if str(value) else []


def _first_text(payload: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def _payload_hash_ref(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "payload_hash": stable_payload_hash(payload),
    }


def _work_kind(value: Any, *, default: WorkKind = WorkKind.READ_ONLY) -> WorkKind:
    raw = str(value or "").strip().lower()
    for kind in WorkKind:
        if raw in {kind.value, kind.name.lower()}:
            return kind
    return default


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "present", "claimed"}


def _kernel_close_status(status: KernelRunStatus) -> Literal["completed", "failed", "blocked"]:
    if status == "completed":
        return "completed"
    if status == "failed":
        return "failed"
    return "blocked"


class TriggerEnvelope(BaseModel):
    source: str = "manual"
    mission_id: str = ""
    task_id: str = ""
    correlation_id: str = ""
    parent_run_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class KernelTask(BaseModel):
    text: str
    source: str = "manual"
    requested_output: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuthorityPassport(BaseModel):
    work_kind: WorkKind = WorkKind.READ_ONLY
    risk_tier: str = "Q1"
    autonomy_level: str = "manual"
    mutation_budget_remaining: int | None = None
    allowed_files: list[str] = Field(default_factory=list)
    forbidden_files: list[str] = Field(default_factory=list)
    protected_file_hits: list[str] = Field(default_factory=list)
    telos_decision: str = "allow"
    telos_reasons: list[str] = Field(default_factory=list)
    context_quorum_ok: bool = True
    context_quorum_ref: str = ""
    scanner_available: bool = True
    scanner_verdict: str = "clean"
    mission_contract_present: bool = False
    workspace_lease_present: bool = False
    external_worker_authority: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_governed_request(self, *, agent_uid: str, intent: str) -> GovernedWorkRequest:
        return GovernedWorkRequest(
            agent_uid=agent_uid,
            work_kind=self.work_kind,
            intent=intent,
            risk_tier=self.risk_tier,
            autonomy_level=self.autonomy_level,
            mutation_budget_remaining=self.mutation_budget_remaining,
            allowed_files=list(self.allowed_files),
            forbidden_files=list(self.forbidden_files),
            protected_file_hits=list(self.protected_file_hits),
            telos_decision=self.telos_decision,
            telos_reasons=list(self.telos_reasons),
            context_quorum_ok=self.context_quorum_ok,
            context_quorum_ref=self.context_quorum_ref,
            scanner_available=self.scanner_available,
            scanner_verdict=self.scanner_verdict,
            mission_contract_present=self.mission_contract_present,
            workspace_lease_present=self.workspace_lease_present,
            metadata=dict(self.metadata),
        )


class MemoryPlan(BaseModel):
    read_namespaces: list[str] = Field(default_factory=list)
    write_namespaces: list[str] = Field(default_factory=list)
    proposed_learning_delta: str = ""
    promotion_receipts: list[str] = Field(default_factory=list)
    promotion_allowed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolRequest(BaseModel):
    requested_tools: list[str] = Field(default_factory=list)
    requested_tool_groups: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    sandbox_policy: dict[str, Any] = Field(default_factory=dict)
    inherited_subagent_limits: dict[str, Any] = Field(default_factory=dict)
    late_bound_tools: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProofRequest(BaseModel):
    expected_receipts: list[str] = Field(default_factory=list)
    verifier_commands: list[str] = Field(default_factory=list)
    artifact_refs: list[dict[str, Any]] = Field(default_factory=list)
    receipt_refs: list[dict[str, Any]] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    runtime_truth_ref: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRunEnvelope(BaseModel):
    agent_uid: str
    task: KernelTask
    run_id: str = Field(default_factory=_new_run_id)
    trigger: TriggerEnvelope = Field(default_factory=TriggerEnvelope)
    authority: AuthorityPassport = Field(default_factory=AuthorityPassport)
    memory: MemoryPlan = Field(default_factory=MemoryPlan)
    tool_request: ToolRequest = Field(default_factory=ToolRequest)
    proof: ProofRequest = Field(default_factory=ProofRequest)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolPlan(BaseModel):
    visible_tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    denial_reasons: dict[str, str] = Field(default_factory=dict)
    tool_schemas: list[dict[str, Any]] = Field(default_factory=list)
    sandbox_policy: dict[str, Any] = Field(default_factory=dict)
    inherited_subagent_limits: dict[str, Any] = Field(default_factory=dict)
    late_bound_tools: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    policy_hash: str = ""


class KernelToolResult(BaseModel):
    run_id: str
    tool_name: str
    status: KernelToolStatus
    arguments_hash: str
    output: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    denial_reason: str = ""
    started_at: str = Field(default_factory=utc_now)
    completed_at: str = Field(default_factory=utc_now)
    receipt_hash: str = ""
    event_ref: dict[str, Any] = Field(default_factory=dict)


class KernelRunReplay(BaseModel):
    run_id: str
    events: list[dict[str, Any]] = Field(default_factory=list)
    proof_entries: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    integrity_ok: bool = True
    integrity_errors: list[str] = Field(default_factory=list)
    replay_hash: str = ""


class ProofLedgerEntry(BaseModel):
    run_id: str
    agent_uid: str
    status: KernelRunStatus
    envelope_hash: str
    tool_plan_hash: str
    authority_decision: str
    authority_reasons: list[str] = Field(default_factory=list)
    mission_id: str = ""
    task_id: str = ""
    correlation_id: str = ""
    runtime_truth_ref: dict[str, Any] = Field(default_factory=dict)
    receipt_refs: list[dict[str, Any]] = Field(default_factory=list)
    artifact_refs: list[dict[str, Any]] = Field(default_factory=list)
    event_refs: list[dict[str, Any]] = Field(default_factory=list)
    tool_result_refs: list[dict[str, Any]] = Field(default_factory=list)
    verifier_commands: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    ledger_sequence: int = 0
    previous_entry_hash: str = ""
    entry_hash: str = ""
    created_at: str = Field(default_factory=utc_now)


class KernelRunResult(BaseModel):
    status: KernelRunStatus
    run_id: str
    did_execute: bool = False
    did_persist: bool = False
    message: str = ""
    admission: GovernedWorkAdmission
    tool_plan: ToolPlan
    tool_results: list[KernelToolResult] = Field(default_factory=list)
    event_refs: list[dict[str, Any]] = Field(default_factory=list)
    replay_ref: dict[str, Any] = Field(default_factory=dict)
    runtime_truth_packet: dict[str, Any]
    proof_ledger_entry: ProofLedgerEntry
    metadata: dict[str, Any] = Field(default_factory=dict)


class KernelWakeRecord(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_wake.v1"
    wake_id: str
    run_id: str
    status: KernelWakeStatus
    envelope: AgentRunEnvelope
    queued_at: str = ""
    updated_at: str = Field(default_factory=utc_now)
    attempt: int = 0
    lease_owner: str = ""
    lease_expires_at: str = ""
    result_status: str = ""
    result_ref: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    previous_record_hash: str = ""
    record_hash: str = ""


class KernelWakeExecution(BaseModel):
    status: KernelWakeExecutionStatus
    wake_record: KernelWakeRecord | None = None
    result: KernelRunResult | None = None
    message: str = ""


class KernelSourceCloseback(BaseModel):
    source: str
    status: KernelSourceClosebackStatus = "recorded"
    mutated: bool = False
    reason: str = ""
    wake_id: str = ""
    run_id: str = ""
    source_ref: dict[str, Any] = Field(default_factory=dict)
    result_ref: dict[str, Any] = Field(default_factory=dict)
    receipt_ref: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class KernelControlTick(BaseModel):
    status: KernelWakeExecutionStatus
    lease_owner: str
    recovered_wake_ids: list[str] = Field(default_factory=list)
    executions: list[KernelWakeExecution] = Field(default_factory=list)
    closebacks: list[KernelSourceCloseback] = Field(default_factory=list)
    latest_wake_status: list[dict[str, Any]] = Field(default_factory=list)
    message: str = ""


class KernelControlSnapshot(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_control_snapshot.v1"
    generated_at: str = Field(default_factory=utc_now)
    integrity_ok: bool = True
    integrity_errors: list[str] = Field(default_factory=list)
    queued_wake_ids: list[str] = Field(default_factory=list)
    leased_wake_ids: list[str] = Field(default_factory=list)
    expired_lease_wake_ids: list[str] = Field(default_factory=list)
    terminal_wake_ids: list[str] = Field(default_factory=list)
    latest_wake_status: list[dict[str, Any]] = Field(default_factory=list)


class KernelSubagentDispatch(BaseModel):
    status: KernelSubagentDispatchStatus
    parent_run_id: str
    child_run_id: str = ""
    child_agent_uid: str = ""
    wake_id: str = ""
    reason: str = ""
    inherited_authority_ref: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class KernelDaemonControlReceipt(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_daemon_control.v1"
    action: KernelDaemonControlAction
    daemon_id: str = "living-agent-kernel"
    requested_by: str = "operator"
    reason: str = ""
    requested_at: str = Field(default_factory=utc_now)
    expires_at: str = ""
    previous_record_hash: str = ""
    record_hash: str = ""


class KernelDaemonState(BaseModel):
    status: KernelDaemonStateStatus = "running"
    daemon_id: str = "living-agent-kernel"
    reason: str = "daemon_control_running"
    observed_at: str = Field(default_factory=utc_now)
    active_control_ref: dict[str, Any] = Field(default_factory=dict)
    latest_control: KernelDaemonControlReceipt | None = None


class KernelDaemonCycle(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_daemon_cycle.v1"
    cycle_id: str = Field(default_factory=lambda: f"kernel_daemon_cycle_{uuid4().hex[:16]}")
    daemon_id: str = "living-agent-kernel"
    status: KernelDaemonCycleStatus
    started_at: str = Field(default_factory=utc_now)
    finished_at: str = ""
    next_run_after: str = ""
    control_state: KernelDaemonState = Field(default_factory=KernelDaemonState)
    tick: KernelControlTick | None = None
    heartbeat_ref: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
    previous_record_hash: str = ""
    record_hash: str = ""


def _seal_tool_result(result: KernelToolResult) -> KernelToolResult:
    result.receipt_hash = ""
    result.receipt_hash = stable_payload_hash(result.model_dump(mode="json", exclude={"receipt_hash"}))
    return result


def _tool_result(
    *,
    run_id: str,
    tool_name: str,
    status: KernelToolStatus,
    arguments: dict[str, Any],
    output: dict[str, Any] | None = None,
    error: str = "",
    denial_reason: str = "",
    started_at: str | None = None,
) -> KernelToolResult:
    result = KernelToolResult(
        run_id=run_id,
        tool_name=tool_name,
        status=status,
        arguments_hash=stable_payload_hash(arguments),
        output=output or {},
        error=error,
        denial_reason=denial_reason,
        started_at=started_at or utc_now(),
        completed_at=utc_now(),
    )
    return _seal_tool_result(result)


@dataclass(frozen=True)
class KernelToolDefinition:
    name: str
    description: str
    schema: dict[str, Any]
    handler: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


class KernelReadOnlyToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, KernelToolDefinition] = {}

    @classmethod
    def default(cls) -> "KernelReadOnlyToolRegistry":
        registry = cls()
        registry.register("session_status", "Return governed run status.", {}, _tool_session_status)
        registry.register("memory_read", "Return declared memory namespaces.", {"namespace": "string"}, _tool_memory_read)
        registry.register("read_file", "Read an explicitly allowed file.", {"path": "string", "max_bytes": "integer"}, _tool_read_file, required=["path"])
        registry.register("search_files", "Search file names under allowed paths.", {"query": "string", "limit": "integer"}, _tool_search_files, required=["query"])
        registry.register(
            "apply_patch",
            "Apply a unified diff through the LivingAgentKernel write adapter.",
            {"patch": "string", "diff": "string"},
            _tool_apply_patch_requires_kernel_context,
        )
        return registry

    def register(
        self,
        name: str,
        description: str,
        properties: dict[str, str],
        handler: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        *,
        required: list[str] | None = None,
    ) -> None:
        self._tools[name] = KernelToolDefinition(
            name=name,
            description=description,
            schema={
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {key: {"type": value} for key, value in properties.items()},
                    "required": required or [],
                    "additionalProperties": False,
                },
            },
            handler=handler,
        )

    def schemas(self, tool_names: list[str]) -> list[dict[str, Any]]:
        return [
            {"type": "function", "function": self._tools[name].schema}
            for name in sorted(set(tool_names))
            if name in self._tools
        ]

    def dispatch(self, *, tool_name: str, arguments: dict[str, Any], context: dict[str, Any]) -> KernelToolResult:
        started_at = utc_now()
        definition = self._tools.get(tool_name)
        if definition is None:
            return _tool_result(
                run_id=str(context["run_id"]),
                tool_name=tool_name,
                status="denied",
                arguments=arguments,
                denial_reason="tool_not_registered_in_kernel_v1",
                started_at=started_at,
            )
        validation_error = self._validate_arguments(definition.schema, arguments)
        if validation_error:
            return _tool_result(
                run_id=str(context["run_id"]),
                tool_name=tool_name,
                status="failed",
                arguments=arguments,
                error=validation_error,
                started_at=started_at,
            )
        try:
            output = definition.handler(arguments, context)
        except PermissionError as exc:
            return _tool_result(
                run_id=str(context["run_id"]),
                tool_name=tool_name,
                status="denied",
                arguments=arguments,
                denial_reason=str(exc),
                started_at=started_at,
            )
        except Exception as exc:
            return _tool_result(
                run_id=str(context["run_id"]),
                tool_name=tool_name,
                status="failed",
                arguments=arguments,
                error=f"{type(exc).__name__}: {exc}",
                started_at=started_at,
            )
        return _tool_result(
            run_id=str(context["run_id"]),
            tool_name=tool_name,
            status="completed",
            arguments=arguments,
            output=output,
            started_at=started_at,
        )

    @staticmethod
    def _validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> str:
        parameters = schema.get("parameters", {})
        required = parameters.get("required", [])
        properties = parameters.get("properties", {})
        expected_types = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "object": dict,
            "array": list,
        }
        for key in required:
            if key not in arguments:
                return f"missing_required_argument:{key}"
        for key, value in arguments.items():
            spec = properties.get(key)
            if not spec and parameters.get("additionalProperties") is False:
                return f"unexpected_argument:{key}"
            expected = expected_types.get(str((spec or {}).get("type") or ""))
            if expected is not None and not isinstance(value, expected):
                return f"invalid_argument_type:{key}"
        return ""


def _tool_session_status(_arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": str(context["run_id"]),
        "agent_uid": str(context["agent_uid"]),
        "task_source": str(context["task_source"]),
        "authority_decision": str(context["authority_decision"]),
        "authority_reasons": list(context["authority_reasons"]),
        "visible_tools": list(context["visible_tools"]),
        "kernel_version": "v1",
        "provider_execution": False,
    }


def _tool_memory_read(arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    namespaces = list(context["memory_read_namespaces"])
    requested = str(arguments.get("namespace") or "")
    if requested and requested not in namespaces:
        raise PermissionError("memory_namespace_not_declared")
    return {"namespaces": [requested] if requested else namespaces, "records": [], "projection_only": True}


def _tool_read_file(arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    workspace_root = Path(str(context["workspace_root"])).expanduser().resolve()
    target = Path(str(arguments["path"])).expanduser()
    target = target if target.is_absolute() else workspace_root / target
    target = target.resolve()
    if not _allowed_path(target, list(context["allowed_files"]), workspace_root=workspace_root):
        raise PermissionError("read_file_requires_explicit_allowed_file")
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(str(target))
    max_bytes = max(1, min(int(arguments.get("max_bytes") or 4096), 16384))
    data = target.read_bytes()
    chunk = data[:max_bytes]
    return {
        "path": str(target),
        "bytes_read": len(chunk),
        "truncated": len(data) > len(chunk),
        "sha256": sha256_file(target),
        "content": chunk.decode("utf-8", errors="replace"),
    }


def _tool_search_files(arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    query = str(arguments["query"]).lower()
    limit = max(1, min(int(arguments.get("limit") or 20), 50))
    workspace_root = Path(str(context["workspace_root"])).expanduser().resolve()
    matches: list[dict[str, Any]] = []
    for raw in list(context["allowed_files"]):
        allowed = Path(str(raw)).expanduser()
        allowed = allowed if allowed.is_absolute() else workspace_root / allowed
        allowed = allowed.resolve()
        candidates = [allowed] if allowed.is_file() else allowed.rglob("*") if allowed.is_dir() else []
        for candidate in candidates:
            if len(matches) >= limit:
                break
            if candidate.is_file() and query in candidate.name.lower():
                matches.append({"path": str(candidate), "sha256": sha256_file(candidate)})
        if len(matches) >= limit:
            break
    return {"query": query, "matches": matches, "searched_allowed_roots": len(list(context["allowed_files"]))}


def _tool_apply_patch_requires_kernel_context(_arguments: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
    raise PermissionError("apply_patch_requires_living_agent_kernel_write_adapter")


class KernelRunStore:
    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir or DEFAULT_KERNEL_RUN_DIR).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.event_log = EventLog(self.base_dir / "events")
        self.proof_ledger_path = self.base_dir / "proof_ledger.jsonl"
        self.tool_results_path = self.base_dir / "tool_results.jsonl"
        self.wake_ledger_path = self.base_dir / "wake_ledger.jsonl"
        self.daemon_control_path = self.base_dir / "daemon_control.jsonl"
        self.daemon_cycles_path = self.base_dir / "daemon_cycles.jsonl"

    def append_daemon_control(self, receipt: KernelDaemonControlReceipt) -> KernelDaemonControlReceipt:
        row = receipt.model_dump(mode="json")
        rows = _jsonl_rows(self.daemon_control_path)
        row["previous_record_hash"] = str(rows[-1].get("record_hash") or "") if rows else ""
        row["record_hash"] = ""
        row["record_hash"] = stable_payload_hash(row)
        _append_jsonl(self.daemon_control_path, row)
        return KernelDaemonControlReceipt.model_validate(row)

    def daemon_control_receipts(self) -> list[KernelDaemonControlReceipt]:
        return [KernelDaemonControlReceipt.model_validate(row) for row in _jsonl_rows(self.daemon_control_path)]

    def append_daemon_cycle(self, cycle: KernelDaemonCycle) -> KernelDaemonCycle:
        row = cycle.model_dump(mode="json")
        rows = _jsonl_rows(self.daemon_cycles_path)
        row["previous_record_hash"] = str(rows[-1].get("record_hash") or "") if rows else ""
        row["record_hash"] = ""
        row["record_hash"] = stable_payload_hash(row)
        _append_jsonl(self.daemon_cycles_path, row)
        return KernelDaemonCycle.model_validate(row)

    def daemon_cycles(self) -> list[KernelDaemonCycle]:
        return [KernelDaemonCycle.model_validate(row) for row in _jsonl_rows(self.daemon_cycles_path)]

    def verify_daemon_control_ledger(self) -> tuple[bool, list[str]]:
        return self._verify_hash_ledger(self.daemon_control_path, empty_ok=True)

    def verify_daemon_cycle_ledger(self) -> tuple[bool, list[str]]:
        return self._verify_hash_ledger(self.daemon_cycles_path, empty_ok=True)

    @staticmethod
    def _verify_hash_ledger(path: Path, *, empty_ok: bool = False) -> tuple[bool, list[str]]:
        rows = _jsonl_rows(path)
        if not rows:
            return (True, []) if empty_ok else (False, [f"{path.name} missing"])
        errors: list[str] = []
        previous_hash = ""
        for index, row in enumerate(rows, start=1):
            if str(row.get("previous_record_hash") or "") != previous_hash:
                errors.append(f"line {index}: previous_record_hash mismatch")
            observed_hash = str(row.get("record_hash") or "")
            material = dict(row)
            material["record_hash"] = ""
            if observed_hash != stable_payload_hash(material):
                errors.append(f"line {index}: record_hash mismatch")
            previous_hash = observed_hash
        return (len(errors) == 0, errors)

    def append_event(
        self,
        envelope: AgentRunEnvelope,
        *,
        suffix: str,
        event_type: RuntimeEventType,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        runtime_event = RuntimeEnvelope.create(
            event_type=event_type,
            source=KERNEL_SOURCE,
            agent_id=envelope.agent_uid,
            session_id=envelope.trigger.mission_id or envelope.run_id,
            trace_id=envelope.trigger.correlation_id or envelope.run_id,
            event_id=f"evt_{envelope.run_id}_{suffix}",
            emitted_at=utc_now(),
            payload={"run_id": envelope.run_id, **payload},
        )
        row = self.event_log.append_envelope(runtime_event, stream=KERNEL_EVENT_STREAM)
        return {
            "kind": "kernel_event",
            "path": str(self.event_log.stream_path(KERNEL_EVENT_STREAM)),
            "event_id": str(row.get("event_id") or ""),
            "event_type": str(row.get("event_type") or ""),
            "sha256": stable_payload_hash(row),
        }

    def append_tool_result(self, result: KernelToolResult) -> dict[str, Any]:
        _append_jsonl(self.tool_results_path, result.model_dump(mode="json"))
        return {
            "kind": "kernel_tool_result",
            "path": str(self.tool_results_path),
            "run_id": result.run_id,
            "tool_name": result.tool_name,
            "receipt_hash": result.receipt_hash,
        }

    def append_proof_entry(self, entry: ProofLedgerEntry) -> ProofLedgerEntry:
        row = entry.model_dump(mode="json")
        rows = _jsonl_rows(self.proof_ledger_path)
        row["ledger_sequence"] = len(rows) + 1
        row["previous_entry_hash"] = str(rows[-1].get("entry_hash") or "") if rows else ""
        row["entry_hash"] = ""
        row["entry_hash"] = stable_payload_hash(row)
        _append_jsonl(self.proof_ledger_path, row)
        return ProofLedgerEntry.model_validate(row)

    def replay_run(self, run_id: str) -> KernelRunReplay:
        events = [
            row
            for row in self.event_log.read_envelopes(stream=KERNEL_EVENT_STREAM)
            if str(row.get("payload", {}).get("run_id") or "") == run_id
        ]
        proof_entries = [row for row in _jsonl_rows(self.proof_ledger_path) if str(row.get("run_id") or "") == run_id]
        tool_results = [row for row in _jsonl_rows(self.tool_results_path) if str(row.get("run_id") or "") == run_id]
        event_ok, event_errors = self.event_log.verify_stream(stream=KERNEL_EVENT_STREAM)
        proof_ok, proof_errors = self.verify_proof_ledger()
        payload = {"run_id": run_id, "events": events, "proof_entries": proof_entries, "tool_results": tool_results}
        return KernelRunReplay(
            run_id=run_id,
            events=events,
            proof_entries=proof_entries,
            tool_results=tool_results,
            integrity_ok=event_ok and proof_ok,
            integrity_errors=[*event_errors, *proof_errors],
            replay_hash=stable_payload_hash(payload),
        )

    def verify_proof_ledger(self) -> tuple[bool, list[str]]:
        rows = _jsonl_rows(self.proof_ledger_path)
        if not rows:
            return (False, ["proof ledger missing"])
        errors: list[str] = []
        previous_hash = ""
        for index, row in enumerate(rows, start=1):
            if int(row.get("ledger_sequence") or 0) != index:
                errors.append(f"line {index}: ledger_sequence mismatch")
            if str(row.get("previous_entry_hash") or "") != previous_hash:
                errors.append(f"line {index}: previous_entry_hash mismatch")
            observed_hash = str(row.get("entry_hash") or "")
            material = dict(row)
            material["entry_hash"] = ""
            if observed_hash != stable_payload_hash(material):
                errors.append(f"line {index}: entry_hash mismatch")
            previous_hash = observed_hash
        return (len(errors) == 0, errors)

    def verify_integrity(self) -> tuple[bool, list[str]]:
        event_ok, event_errors = self.event_log.verify_stream(stream=KERNEL_EVENT_STREAM)
        proof_ok, proof_errors = self.verify_proof_ledger()
        return (event_ok and proof_ok, [*event_errors, *proof_errors])

    def enqueue_wake(
        self,
        envelope: AgentRunEnvelope,
        *,
        wake_id: str | None = None,
        reason: str = "",
        now: str | None = None,
    ) -> KernelWakeRecord:
        observed_at = now or utc_now()
        return self._append_wake_record(
            KernelWakeRecord(
                wake_id=wake_id or f"wake_{uuid4().hex[:16]}",
                run_id=envelope.run_id,
                status="queued",
                envelope=envelope,
                queued_at=observed_at,
                updated_at=observed_at,
                reason=reason or "wake_enqueued",
            )
        )

    def wake_records(self) -> list[KernelWakeRecord]:
        return [KernelWakeRecord.model_validate(row) for row in _jsonl_rows(self.wake_ledger_path)]

    def latest_wake_records(self) -> dict[str, KernelWakeRecord]:
        latest: dict[str, KernelWakeRecord] = {}
        for record in self.wake_records():
            latest[record.wake_id] = record
        return latest

    def latest_wake_status(self, *, limit: int = 20) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 200))
        rows: list[dict[str, Any]] = []
        latest = sorted(
            self.latest_wake_records().values(),
            key=lambda item: item.updated_at or item.queued_at,
            reverse=True,
        )
        for record in latest[:bounded_limit]:
            envelope = record.envelope
            rows.append(
                {
                    "wake_id": record.wake_id,
                    "run_id": record.run_id,
                    "status": record.status,
                    "source": envelope.trigger.source,
                    "agent_uid": envelope.agent_uid,
                    "task_text": envelope.task.text,
                    "mission_id": envelope.trigger.mission_id,
                    "task_id": envelope.trigger.task_id,
                    "correlation_id": envelope.trigger.correlation_id,
                    "queued_at": record.queued_at,
                    "updated_at": record.updated_at,
                    "attempt": record.attempt,
                    "lease_owner": record.lease_owner,
                    "lease_expires_at": record.lease_expires_at,
                    "result_status": record.result_status,
                    "result_ref": dict(record.result_ref),
                    "source_payload_hash": str(envelope.metadata.get("source_payload_hash") or ""),
                }
            )
        return rows

    def control_snapshot(self, *, now: str | None = None, latest_limit: int = 20) -> KernelControlSnapshot:
        observed_at = now or utc_now()
        latest = self.latest_wake_records()
        queued: list[str] = []
        leased: list[str] = []
        expired: list[str] = []
        terminal: list[str] = []
        for record in latest.values():
            if record.status == "queued":
                queued.append(record.wake_id)
            elif record.status == "leased":
                leased.append(record.wake_id)
                if self._lease_is_expired(record, observed_at):
                    expired.append(record.wake_id)
            elif record.status in {"completed", "review", "blocked", "failed"}:
                terminal.append(record.wake_id)
        if self.wake_ledger_path.exists():
            integrity_ok, integrity_errors = self.verify_wake_ledger()
        else:
            integrity_ok, integrity_errors = True, []
        return KernelControlSnapshot(
            generated_at=observed_at,
            integrity_ok=integrity_ok,
            integrity_errors=integrity_errors,
            queued_wake_ids=sorted(queued),
            leased_wake_ids=sorted(leased),
            expired_lease_wake_ids=sorted(expired),
            terminal_wake_ids=sorted(terminal),
            latest_wake_status=self.latest_wake_status(limit=latest_limit),
        )

    def lease_next_wake(
        self,
        *,
        lease_owner: str,
        lease_seconds: int = 300,
        allowed_sources: list[str] | tuple[str, ...] | None = None,
        now: str | None = None,
    ) -> KernelWakeRecord | None:
        observed_at = now or utc_now()
        source_filter = {str(source) for source in allowed_sources or [] if str(source)}
        for record in sorted(self.latest_wake_records().values(), key=lambda item: item.queued_at or item.updated_at):
            if source_filter and record.envelope.trigger.source not in source_filter:
                continue
            if record.status == "queued" or self._lease_is_expired(record, observed_at):
                return self._append_wake_record(
                    record.model_copy(
                        update={
                            "status": "leased",
                            "updated_at": observed_at,
                            "attempt": record.attempt + 1,
                            "lease_owner": lease_owner,
                            "lease_expires_at": _utc_after(observed_at, lease_seconds),
                            "reason": "wake_leased",
                            "previous_record_hash": "",
                            "record_hash": "",
                        }
                    )
                )
        return None

    def complete_external_wake(
        self,
        wake_record: KernelWakeRecord,
        *,
        status: KernelRunStatus,
        result_ref: dict[str, Any],
        reason: str = "external_worker_terminal_result",
        now: str | None = None,
    ) -> KernelWakeRecord:
        if status not in {"completed", "review", "blocked", "failed"}:
            raise ValueError(f"external wake status is not terminal: {status}")
        observed_at = now or utc_now()
        return self._append_wake_record(
            wake_record.model_copy(
                update={
                    "status": status,
                    "updated_at": observed_at,
                    "result_status": status,
                    "result_ref": dict(result_ref),
                    "reason": reason,
                    "previous_record_hash": "",
                    "record_hash": "",
                }
            )
        )

    def complete_wake(
        self,
        wake_record: KernelWakeRecord,
        result: KernelRunResult,
        *,
        now: str | None = None,
    ) -> KernelWakeRecord:
        observed_at = now or utc_now()
        return self._append_wake_record(
            wake_record.model_copy(
                update={
                    "status": result.status,
                    "updated_at": observed_at,
                    "result_status": result.status,
                    "result_ref": {
                        "kind": "kernel_run_result",
                        "run_id": result.run_id,
                        "replay_ref": result.replay_ref,
                        "proof_entry_hash": result.proof_ledger_entry.entry_hash,
                    },
                    "reason": "wake_terminal_result",
                    "previous_record_hash": "",
                    "record_hash": "",
                }
            )
        )

    def record_wake_closeback(
        self,
        wake_record: KernelWakeRecord,
        closeback: KernelSourceCloseback,
        *,
        now: str | None = None,
    ) -> KernelWakeRecord:
        observed_at = now or utc_now()
        result_ref = dict(wake_record.result_ref)
        result_ref["source_closeback"] = closeback.model_dump(mode="json")
        return self._append_wake_record(
            wake_record.model_copy(
                update={
                    "updated_at": observed_at,
                    "result_ref": result_ref,
                    "reason": "source_closeback_recorded",
                    "previous_record_hash": "",
                    "record_hash": "",
                }
            )
        )

    def recover_expired_wakes(
        self,
        *,
        lease_owners: list[str] | tuple[str, ...] | None = None,
        now: str | None = None,
    ) -> list[KernelWakeRecord]:
        observed_at = now or utc_now()
        owner_filter = None if lease_owners is None else {str(owner) for owner in lease_owners if str(owner)}
        recovered: list[KernelWakeRecord] = []
        for record in sorted(self.latest_wake_records().values(), key=lambda item: item.queued_at or item.updated_at):
            if owner_filter is not None and record.lease_owner not in owner_filter:
                continue
            if not self._lease_is_expired(record, observed_at):
                continue
            recovered.append(
                self._append_wake_record(
                    record.model_copy(
                        update={
                            "status": "queued",
                            "updated_at": observed_at,
                            "lease_owner": "",
                            "lease_expires_at": "",
                            "reason": "leased_wake_expired_and_requeued",
                            "previous_record_hash": "",
                            "record_hash": "",
                        }
                    )
                )
            )
        return recovered

    def verify_wake_ledger(self) -> tuple[bool, list[str]]:
        rows = _jsonl_rows(self.wake_ledger_path)
        if not rows:
            return (False, ["wake ledger missing"])
        errors: list[str] = []
        previous_hash = ""
        for index, row in enumerate(rows, start=1):
            if str(row.get("previous_record_hash") or "") != previous_hash:
                errors.append(f"line {index}: previous_record_hash mismatch")
            observed_hash = str(row.get("record_hash") or "")
            material = dict(row)
            material["record_hash"] = ""
            if observed_hash != stable_payload_hash(material):
                errors.append(f"line {index}: record_hash mismatch")
            previous_hash = observed_hash
        return (len(errors) == 0, errors)

    def _append_wake_record(self, record: KernelWakeRecord) -> KernelWakeRecord:
        rows = _jsonl_rows(self.wake_ledger_path)
        row = record.model_dump(mode="json")
        row["previous_record_hash"] = str(rows[-1].get("record_hash") or "") if rows else ""
        row["record_hash"] = ""
        row["record_hash"] = stable_payload_hash(row)
        _append_jsonl(self.wake_ledger_path, row)
        return KernelWakeRecord.model_validate(row)

    @staticmethod
    def _lease_is_expired(record: KernelWakeRecord, now: str) -> bool:
        if record.status != "leased" or not record.lease_expires_at:
            return False
        return _utc_datetime(record.lease_expires_at) <= _utc_datetime(now)


class LivingAgentKernel:
    def __init__(
        self,
        *,
        store: KernelRunStore | None = None,
        tool_registry: KernelReadOnlyToolRegistry | None = None,
        workspace_root: Path | str | None = None,
        persist: bool = True,
    ) -> None:
        self.store = store if store is not None else KernelRunStore()
        self.tool_registry = tool_registry or KernelReadOnlyToolRegistry.default()
        self.workspace_root = Path(workspace_root or Path.cwd()).expanduser().resolve()
        self.persist = persist
        self._lesson_store: "KernelLessonStore | None" = None

    @property
    def lesson_store(self) -> "KernelLessonStore":
        if self._lesson_store is None:
            from dharma_swarm.operator_core.living_agent_kernel_lessons import KernelLessonStore

            self._lesson_store = KernelLessonStore(self.store.base_dir)
        return self._lesson_store

    def evaluate_authority(self, envelope: AgentRunEnvelope) -> GovernedWorkAdmission:
        return evaluate_governed_work_admission(
            envelope.authority.to_governed_request(agent_uid=envelope.agent_uid, intent=envelope.task.text)
        )

    def normalize_wake_source(
        self,
        source: KernelWakeSource,
        payload: dict[str, Any],
        *,
        agent_uid: str | None = None,
    ) -> AgentRunEnvelope:
        if not isinstance(payload, dict):
            raise ValueError("wake payload must be an object")
        source_payload = dict(payload)
        if source == "manual":
            return self._normalize_manual_wake(source_payload, agent_uid=agent_uid)
        if source == "a2a":
            return self._normalize_a2a_wake(source_payload, agent_uid=agent_uid)
        if source == "ds_goal":
            return self._normalize_ds_goal_wake(source_payload, agent_uid=agent_uid)
        if source == "persistent_self_wake":
            return self._normalize_persistent_self_wake(source_payload, agent_uid=agent_uid)
        if source == "external_fleet":
            return self._normalize_external_fleet_wake(source_payload, agent_uid=agent_uid)
        raise ValueError(f"unsupported wake source: {source}")

    def enqueue_source_wake(
        self,
        source: KernelWakeSource,
        payload: dict[str, Any],
        *,
        agent_uid: str | None = None,
        wake_id: str | None = None,
    ) -> KernelWakeRecord:
        envelope = self.normalize_wake_source(source, payload, agent_uid=agent_uid)
        return self.enqueue_wake(envelope, wake_id=wake_id, reason=f"{source}_wake_normalized")

    def _normalize_manual_wake(
        self,
        payload: dict[str, Any],
        *,
        agent_uid: str | None,
    ) -> AgentRunEnvelope:
        resolved_agent = agent_uid or _first_text(payload, "agent_uid", "agent", "name", default="codex_composer")
        task_text = _first_text(payload, "task", "text", "goal", "prompt", "title", default="Manual kernel wake")
        return self._build_normalized_envelope(
            source="manual",
            payload=payload,
            agent_uid=resolved_agent,
            task_text=task_text,
            task_source="manual",
            trigger=TriggerEnvelope(
                source="manual",
                mission_id=_first_text(payload, "mission_id"),
                task_id=_first_text(payload, "task_id", "id"),
                correlation_id=_first_text(payload, "correlation_id", "trace_id"),
                parent_run_id=_first_text(payload, "parent_run_id"),
                metadata={"normalized_from": "manual"},
            ),
            authority=self._authority_from_payload(payload),
        )

    def _normalize_a2a_wake(
        self,
        payload: dict[str, Any],
        *,
        agent_uid: str | None,
    ) -> AgentRunEnvelope:
        return_address = payload.get("return_address") if isinstance(payload.get("return_address"), dict) else {}
        task_id = _first_text(payload, "id", "task_id")
        resolved_agent = agent_uid or _first_text(payload, "agent_uid", "to", "recipient", "claimed_by", default="codex_composer")
        task_text = _first_text(payload, "task", "text", "body", "message", "title", "summary", default=f"A2A task {task_id or 'wake'}")
        authority = self._authority_from_payload(payload, default_work_kind=WorkKind.A2A_CLAIM)
        return self._build_normalized_envelope(
            source="a2a",
            payload=payload,
            agent_uid=resolved_agent,
            task_text=task_text,
            task_source="a2a",
            trigger=TriggerEnvelope(
                source="a2a",
                mission_id=_first_text(payload, "mission_id"),
                task_id=task_id,
                correlation_id=_first_text(payload, "correlation_id", "trace_id", default=str(return_address.get("trace_id") or "")),
                parent_run_id=_first_text(payload, "parent_run_id"),
                metadata={
                    "from": _first_text(payload, "from", "sender"),
                    "status": _first_text(payload, "status", default="pending"),
                    "return_address": return_address,
                    "normalized_from": "a2a",
                },
            ),
            authority=authority,
        )

    def _normalize_ds_goal_wake(
        self,
        payload: dict[str, Any],
        *,
        agent_uid: str | None,
    ) -> AgentRunEnvelope:
        mission = payload.get("mission") if isinstance(payload.get("mission"), dict) else {}
        lease = payload.get("lease") if isinstance(payload.get("lease"), dict) else {}
        allowed_writes = _string_list(payload.get("allowed_writes"))
        mission_id = _first_text(payload, "mission_id", default=_first_text(mission, "mission_id"))
        task_id = _first_text(payload, "task_id", "id")
        resolved_agent = agent_uid or _first_text(payload, "agent_uid", "agent", default="codex_composer")
        default_work_kind = WorkKind.CODE_WRITE if allowed_writes else WorkKind.READ_ONLY
        authority = self._authority_from_payload(
            payload,
            default_work_kind=default_work_kind,
            allowed_files=allowed_writes,
            mission_contract_present=bool(mission_id) or _truthy(payload.get("mission_contract_present")),
            workspace_lease_present=bool(lease.get("claimed_by")) or _truthy(payload.get("workspace_lease_present")),
            autonomy_level="leased" if lease.get("claimed_by") else "manual",
            risk_tier="Q2" if default_work_kind == WorkKind.CODE_WRITE else "Q1",
        )
        return self._build_normalized_envelope(
            source="ds_goal",
            payload=payload,
            agent_uid=resolved_agent,
            task_text=_first_text(payload, "title", "task", "goal", default=f"ds-goal task {task_id or mission_id or 'wake'}"),
            task_source="ds_goal",
            trigger=TriggerEnvelope(
                source="ds_goal",
                mission_id=mission_id,
                task_id=task_id,
                correlation_id=_first_text(payload, "correlation_id", "trace_id", default=_first_text(payload, "return_address")),
                parent_run_id=_first_text(payload, "parent_run_id"),
                metadata={
                    "role": _first_text(payload, "role"),
                    "status": _first_text(payload, "status", default="open"),
                    "lease": lease,
                    "return_address": _first_text(payload, "return_address"),
                    "normalized_from": "ds_goal",
                },
            ),
            authority=authority,
        )

    def _normalize_persistent_self_wake(
        self,
        payload: dict[str, Any],
        *,
        agent_uid: str | None,
    ) -> AgentRunEnvelope:
        resolved_agent = agent_uid or _first_text(payload, "agent_uid", "name", "agent", default="persistent_agent")
        task_text = _first_text(payload, "task", "self_task", "wake_reason", "reason", "title", default="Persistent self-wake")
        return self._build_normalized_envelope(
            source="persistent_self_wake",
            payload=payload,
            agent_uid=resolved_agent,
            task_text=task_text,
            task_source="persistent_self_wake",
            trigger=TriggerEnvelope(
                source="persistent_self_wake",
                mission_id=_first_text(payload, "mission_id"),
                task_id=_first_text(payload, "task_id", "wake_id", "id"),
                correlation_id=_first_text(payload, "correlation_id", "trace_id"),
                parent_run_id=_first_text(payload, "parent_run_id"),
                metadata={
                    "wake_interval_seconds": payload.get("wake_interval_seconds"),
                    "witness_log": _first_text(payload, "witness_log"),
                    "normalized_from": "persistent_self_wake",
                },
            ),
            authority=self._authority_from_payload(payload),
        )

    def _normalize_external_fleet_wake(
        self,
        payload: dict[str, Any],
        *,
        agent_uid: str | None,
    ) -> AgentRunEnvelope:
        resolved_agent = agent_uid or _first_text(payload, "agent_uid", "name", "worker", "agent", default="external_worker")
        authority = self._authority_from_payload(
            payload,
            external_worker_authority="external_worker_evidence_only",
            autonomy_level="external_evidence_only",
        )
        return self._build_normalized_envelope(
            source="external_fleet",
            payload=payload,
            agent_uid=resolved_agent,
            task_text=_first_text(payload, "task", "prompt", "title", "role", default="External fleet evidence-only wake"),
            task_source="external_fleet",
            trigger=TriggerEnvelope(
                source="external_fleet",
                mission_id=_first_text(payload, "mission_id"),
                task_id=_first_text(payload, "task_id", "id"),
                correlation_id=_first_text(payload, "correlation_id", "trace_id"),
                parent_run_id=_first_text(payload, "parent_run_id"),
                metadata={
                    "provider": _first_text(payload, "provider"),
                    "model": _first_text(payload, "model"),
                    "status": _first_text(payload, "status"),
                    "normalized_from": "external_fleet",
                },
            ),
            authority=authority,
        )

    def _build_normalized_envelope(
        self,
        *,
        source: KernelWakeSource,
        payload: dict[str, Any],
        agent_uid: str,
        task_text: str,
        task_source: str,
        trigger: TriggerEnvelope,
        authority: AuthorityPassport,
    ) -> AgentRunEnvelope:
        payload_ref = _payload_hash_ref(f"{source}_wake_payload", payload)
        return AgentRunEnvelope(
            agent_uid=agent_uid,
            task=KernelTask(
                text=task_text,
                source=task_source,
                requested_output=_string_list(payload.get("requested_output")),
                metadata={
                    "normalized_from": source,
                    "source_payload_hash": payload_ref["payload_hash"],
                },
            ),
            run_id=_first_text(payload, "run_id") or _new_run_id(),
            trigger=trigger,
            authority=authority,
            memory=self._memory_plan_from_payload(payload, agent_uid),
            tool_request=self._tool_request_from_payload(payload),
            proof=self._proof_request_from_payload(payload, payload_ref),
            metadata={
                "normalized_from": source,
                "source_payload_hash": payload_ref["payload_hash"],
            },
        )

    @staticmethod
    def _authority_from_payload(
        payload: dict[str, Any],
        *,
        default_work_kind: WorkKind = WorkKind.READ_ONLY,
        allowed_files: list[str] | None = None,
        mission_contract_present: bool | None = None,
        workspace_lease_present: bool | None = None,
        external_worker_authority: str | None = None,
        autonomy_level: str | None = None,
        risk_tier: str | None = None,
    ) -> AuthorityPassport:
        work_kind = _work_kind(payload.get("work_kind"), default=default_work_kind)
        return AuthorityPassport(
            work_kind=work_kind,
            risk_tier=risk_tier or _first_text(payload, "risk_tier", default="Q1"),
            autonomy_level=autonomy_level or _first_text(payload, "autonomy_level", default="manual"),
            mutation_budget_remaining=payload.get("mutation_budget_remaining") if isinstance(payload.get("mutation_budget_remaining"), int) else None,
            allowed_files=list(allowed_files or _string_list(payload.get("allowed_files") or payload.get("allowed_writes"))),
            forbidden_files=_string_list(payload.get("forbidden_files")),
            protected_file_hits=_string_list(payload.get("protected_file_hits")),
            telos_decision=_first_text(payload, "telos_decision", default="allow"),
            telos_reasons=_string_list(payload.get("telos_reasons")),
            context_quorum_ok=payload.get("context_quorum_ok") is not False,
            context_quorum_ref=_first_text(payload, "context_quorum_ref"),
            scanner_available=payload.get("scanner_available") is not False,
            scanner_verdict=_first_text(payload, "scanner_verdict", default="clean"),
            mission_contract_present=_truthy(payload.get("mission_contract_present")) if mission_contract_present is None else mission_contract_present,
            workspace_lease_present=_truthy(payload.get("workspace_lease_present")) if workspace_lease_present is None else workspace_lease_present,
            external_worker_authority=external_worker_authority or _first_text(payload, "external_worker_authority"),
            metadata={
                "normalized_authority_from_payload": True,
                "source_payload_hash": stable_payload_hash(payload),
            },
        )

    @staticmethod
    def _memory_plan_from_payload(payload: dict[str, Any], agent_uid: str) -> MemoryPlan:
        if isinstance(payload.get("memory"), dict):
            return MemoryPlan.model_validate(payload["memory"])
        return MemoryPlan(
            read_namespaces=_string_list(payload.get("memory_read_namespaces")) or [f"agent:{agent_uid}:working"],
            write_namespaces=_string_list(payload.get("memory_write_namespaces")) or [f"agent:{agent_uid}:lessons"],
            proposed_learning_delta=_first_text(payload, "proposed_learning_delta"),
        )

    @staticmethod
    def _tool_request_from_payload(payload: dict[str, Any]) -> ToolRequest:
        if isinstance(payload.get("tool_request"), dict):
            return ToolRequest.model_validate(payload["tool_request"])
        raw_calls = payload.get("tool_calls")
        tool_calls = raw_calls if isinstance(raw_calls, list) else []
        return ToolRequest(
            requested_tools=_string_list(payload.get("requested_tools")),
            requested_tool_groups=_string_list(payload.get("requested_tool_groups")),
            tool_calls=[call for call in tool_calls if isinstance(call, dict)],
            sandbox_policy=payload.get("sandbox_policy") if isinstance(payload.get("sandbox_policy"), dict) else {},
            inherited_subagent_limits=payload.get("inherited_subagent_limits") if isinstance(payload.get("inherited_subagent_limits"), dict) else {},
            late_bound_tools=_string_list(payload.get("late_bound_tools")),
        )

    @staticmethod
    def _proof_request_from_payload(payload: dict[str, Any], payload_ref: dict[str, Any]) -> ProofRequest:
        if isinstance(payload.get("proof"), dict):
            proof = ProofRequest.model_validate(payload["proof"])
            proof.receipt_refs.append(payload_ref)
            return proof
        verifier_commands = _string_list(payload.get("verifier_commands"))
        verifier = _first_text(payload, "verifier_command")
        if verifier:
            verifier_commands.append(verifier)
        return ProofRequest(
            verifier_commands=verifier_commands,
            artifact_refs=[item for item in payload.get("artifact_refs", []) if isinstance(item, dict)] if isinstance(payload.get("artifact_refs"), list) else [],
            receipt_refs=[payload_ref],
            stop_conditions=_string_list(payload.get("stop_conditions")),
        )

    def enqueue_wake(
        self,
        envelope: AgentRunEnvelope,
        *,
        wake_id: str | None = None,
        reason: str = "",
    ) -> KernelWakeRecord:
        return self.store.enqueue_wake(envelope, wake_id=wake_id, reason=reason)

    def lease_next_wake(
        self,
        *,
        lease_owner: str,
        lease_seconds: int = 300,
    ) -> KernelWakeRecord | None:
        return self.store.lease_next_wake(lease_owner=lease_owner, lease_seconds=lease_seconds)

    def recover_expired_wakes(self, *, now: str | None = None) -> list[KernelWakeRecord]:
        return self.store.recover_expired_wakes(now=now)

    def latest_wake_status(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return self.store.latest_wake_status(limit=limit)

    def control_snapshot(self, *, now: str | None = None, latest_limit: int = 20) -> KernelControlSnapshot:
        return self.store.control_snapshot(now=now, latest_limit=latest_limit)

    def request_daemon_control(
        self,
        action: KernelDaemonControlAction,
        *,
        daemon_id: str = "living-agent-kernel",
        requested_by: str = "operator",
        reason: str = "",
        ttl_seconds: int | None = None,
        now: str | None = None,
    ) -> KernelDaemonControlReceipt:
        observed_at = now or utc_now()
        expires_at = ""
        if ttl_seconds is not None and action in {"pause", "stop"}:
            expires_at = _utc_after(observed_at, ttl_seconds)
        return self.store.append_daemon_control(
            KernelDaemonControlReceipt(
                action=action,
                daemon_id=daemon_id,
                requested_by=requested_by,
                reason=reason,
                requested_at=observed_at,
                expires_at=expires_at,
            )
        )

    def daemon_control_state(
        self,
        *,
        daemon_id: str = "living-agent-kernel",
        now: str | None = None,
    ) -> KernelDaemonState:
        observed_at = now or utc_now()
        controls = [
            receipt
            for receipt in self.store.daemon_control_receipts()
            if receipt.daemon_id in {daemon_id, "*"}
        ]
        if not controls:
            return KernelDaemonState(
                status="running",
                daemon_id=daemon_id,
                reason="daemon_control_running",
                observed_at=observed_at,
            )
        latest = controls[-1]
        if latest.action == "resume":
            return KernelDaemonState(
                status="running",
                daemon_id=daemon_id,
                reason="daemon_control_resumed",
                observed_at=observed_at,
                active_control_ref=self._daemon_control_ref(latest),
                latest_control=latest,
            )
        if latest.expires_at and _utc_datetime(latest.expires_at) <= _utc_datetime(observed_at):
            return KernelDaemonState(
                status="running",
                daemon_id=daemon_id,
                reason=f"daemon_control_{latest.action}_expired",
                observed_at=observed_at,
                active_control_ref=self._daemon_control_ref(latest),
                latest_control=latest,
            )
        status: KernelDaemonStateStatus = "paused" if latest.action == "pause" else "stopped"
        return KernelDaemonState(
            status=status,
            daemon_id=daemon_id,
            reason=f"daemon_control_{latest.action}_active",
            observed_at=observed_at,
            active_control_ref=self._daemon_control_ref(latest),
            latest_control=latest,
        )

    @staticmethod
    def _daemon_control_ref(receipt: KernelDaemonControlReceipt) -> dict[str, Any]:
        return {
            "kind": "kernel_daemon_control",
            "daemon_id": receipt.daemon_id,
            "action": receipt.action,
            "requested_at": receipt.requested_at,
            "record_hash": receipt.record_hash,
        }

    def run_daemon_cycle(
        self,
        *,
        daemon_id: str = "living-agent-kernel",
        lease_seconds: int = 300,
        max_wakes: int = 1,
        source_roots: dict[str, Path | str] | None = None,
        recover_expired: bool = True,
        latest_limit: int = 20,
        interval_seconds: int = 60,
        now: str | None = None,
    ) -> KernelDaemonCycle:
        observed_at = now or utc_now()
        control_state = self.daemon_control_state(daemon_id=daemon_id, now=observed_at)
        tick: KernelControlTick | None = None
        status: KernelDaemonCycleStatus
        message: str
        if control_state.status in {"paused", "stopped"}:
            status = control_state.status
            message = f"Daemon cycle skipped: {control_state.reason}."
        else:
            try:
                tick = self.run_control_tick(
                    lease_owner=daemon_id,
                    lease_seconds=lease_seconds,
                    max_wakes=max_wakes,
                    source_roots=source_roots,
                    recover_expired=recover_expired,
                    latest_limit=latest_limit,
                )
                status = tick.status
                message = f"Daemon cycle ran control tick with status {tick.status}."
            except Exception as exc:
                status = "failed"
                message = f"Daemon cycle failed: {type(exc).__name__}: {exc}"
        cycle_id = f"kernel_daemon_cycle_{uuid4().hex[:16]}"
        cycle = KernelDaemonCycle(
            cycle_id=cycle_id,
            daemon_id=daemon_id,
            status=status,
            started_at=observed_at,
            finished_at=observed_at,
            next_run_after=_utc_after(observed_at, interval_seconds),
            control_state=control_state,
            tick=tick,
            heartbeat_ref={
                "kind": "kernel_daemon_cycle",
                "daemon_id": daemon_id,
                "path": str(self.store.daemon_cycles_path),
                "cycle_id": cycle_id,
                "started_at": observed_at,
                "status": status,
            },
            message=message,
        )
        return self.store.append_daemon_cycle(cycle)

    def spawn_subagent_wake(
        self,
        parent_envelope: AgentRunEnvelope,
        *,
        child_agent_uid: str,
        task_text: str,
        role: str = "",
        allowed_files: list[str] | None = None,
        requested_tools: list[str] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        wake_id: str | None = None,
    ) -> KernelSubagentDispatch:
        limits = dict(parent_envelope.tool_request.inherited_subagent_limits)
        child_agent = str(child_agent_uid or "").strip()
        if not child_agent:
            return self._subagent_denied(parent_envelope, child_agent, "subagent_agent_uid_missing")
        allowed_agents = _string_list(limits.get("allowed_agents"))
        if allowed_agents and child_agent not in allowed_agents:
            return self._subagent_denied(parent_envelope, child_agent, "subagent_agent_not_allowed")
        existing_children = [
            record
            for record in self.store.latest_wake_records().values()
            if record.envelope.trigger.parent_run_id == parent_envelope.run_id
        ]
        max_children = limits.get("max_children")
        if isinstance(max_children, int) and max_children >= 0 and len(existing_children) >= max_children:
            return self._subagent_denied(parent_envelope, child_agent, "subagent_max_children_exceeded")
        parent_depth = self._parent_subagent_depth(parent_envelope)
        child_depth = parent_depth + 1
        max_depth = limits.get("max_depth")
        if isinstance(max_depth, int) and max_depth >= 0 and child_depth > max_depth:
            return self._subagent_denied(parent_envelope, child_agent, "subagent_max_depth_exceeded")

        child_allowed_files = _string_list(
            allowed_files if allowed_files is not None else parent_envelope.authority.allowed_files
        )
        for pattern in child_allowed_files:
            if not _contract_pattern_allowed(pattern, parent_envelope.authority.allowed_files, workspace_root=self.workspace_root):
                return self._subagent_denied(parent_envelope, child_agent, "subagent_allowed_files_escalation")

        parent_ref_payload = {
            "parent_run_id": parent_envelope.run_id,
            "parent_agent_uid": parent_envelope.agent_uid,
            "child_agent_uid": child_agent,
            "role": role,
            "allowed_files": child_allowed_files,
            "limits": limits,
        }

        child_trigger = TriggerEnvelope(
            source="subagent",
            mission_id=parent_envelope.trigger.mission_id,
            task_id=f"{parent_envelope.trigger.task_id or parent_envelope.run_id}:subagent:{role or child_agent}",
            correlation_id=parent_envelope.trigger.correlation_id,
            parent_run_id=parent_envelope.run_id,
            metadata={
                "normalized_from": "subagent",
                "subagent_role": role,
                "parent_agent_uid": parent_envelope.agent_uid,
                "subagent_depth": child_depth,
            },
        )
        child_authority = parent_envelope.authority.model_copy(
            update={
                "allowed_files": child_allowed_files,
                "forbidden_files": list(parent_envelope.authority.forbidden_files),
                "protected_file_hits": list(parent_envelope.authority.protected_file_hits),
                "metadata": {
                    **dict(parent_envelope.authority.metadata),
                    "inherited_from_run": parent_envelope.run_id,
                    "inherited_from_agent": parent_envelope.agent_uid,
                    "subagent_role": role,
                },
            }
        )
        child_envelope = AgentRunEnvelope(
            agent_uid=child_agent,
            task=KernelTask(
                text=task_text,
                source="subagent",
                requested_output=list(parent_envelope.task.requested_output),
                metadata={
                    "normalized_from": "subagent",
                    "parent_run_id": parent_envelope.run_id,
                    "subagent_role": role,
                },
            ),
            trigger=child_trigger,
            authority=child_authority,
            memory=MemoryPlan(
                read_namespaces=[f"agent:{child_agent}:working"],
                write_namespaces=[f"agent:{child_agent}:lessons"],
                metadata={"inherited_from_run": parent_envelope.run_id},
            ),
            tool_request=ToolRequest(
                requested_tools=_string_list(requested_tools),
                tool_calls=[call for call in (tool_calls or []) if isinstance(call, dict)],
                sandbox_policy=dict(parent_envelope.tool_request.sandbox_policy),
                inherited_subagent_limits=dict(limits),
                metadata={"inherited_from_run": parent_envelope.run_id},
            ),
            proof=ProofRequest(
                expected_receipts=list(parent_envelope.proof.expected_receipts),
                verifier_commands=list(parent_envelope.proof.verifier_commands),
                artifact_refs=list(parent_envelope.proof.artifact_refs),
                receipt_refs=[
                    *list(parent_envelope.proof.receipt_refs),
                    {
                        "kind": "subagent_parent_run",
                        "parent_run_id": parent_envelope.run_id,
                        "parent_agent_uid": parent_envelope.agent_uid,
                        "payload_hash": stable_payload_hash(parent_ref_payload),
                    },
                ],
                stop_conditions=list(parent_envelope.proof.stop_conditions),
                runtime_truth_ref=dict(parent_envelope.proof.runtime_truth_ref),
                metadata={"inherited_from_run": parent_envelope.run_id},
            ),
            metadata={
                "normalized_from": "subagent",
                "parent_run_id": parent_envelope.run_id,
                "parent_agent_uid": parent_envelope.agent_uid,
                "subagent_role": role,
            },
        )
        wake = self.enqueue_wake(child_envelope, wake_id=wake_id, reason="subagent_wake_spawned")
        return KernelSubagentDispatch(
            status="spawned",
            parent_run_id=parent_envelope.run_id,
            child_run_id=child_envelope.run_id,
            child_agent_uid=child_agent,
            wake_id=wake.wake_id,
            reason="subagent_wake_spawned",
            inherited_authority_ref={
                "work_kind": child_authority.work_kind.value,
                "allowed_files": list(child_authority.allowed_files),
                "forbidden_files": list(child_authority.forbidden_files),
                "parent_run_id": parent_envelope.run_id,
            },
        )

    @staticmethod
    def _parent_subagent_depth(parent_envelope: AgentRunEnvelope) -> int:
        for payload in (parent_envelope.trigger.metadata, parent_envelope.metadata):
            try:
                return max(0, int(payload.get("subagent_depth") or 0))
            except (TypeError, ValueError):
                continue
        return 0

    @staticmethod
    def _subagent_denied(
        parent_envelope: AgentRunEnvelope,
        child_agent_uid: str,
        reason: str,
    ) -> KernelSubagentDispatch:
        return KernelSubagentDispatch(
            status="denied",
            parent_run_id=parent_envelope.run_id,
            child_agent_uid=child_agent_uid,
            reason=reason,
        )

    def run_next_wake(
        self,
        *,
        lease_owner: str,
        lease_seconds: int = 300,
    ) -> KernelWakeExecution:
        wake_record = self.lease_next_wake(lease_owner=lease_owner, lease_seconds=lease_seconds)
        if wake_record is None:
            return KernelWakeExecution(status="idle", message="No queued kernel wake is ready.")
        result = self.run(wake_record.envelope)
        terminal = self.store.complete_wake(wake_record, result)
        return KernelWakeExecution(
            status=result.status,
            wake_record=terminal,
            result=result,
            message=f"Executed wake {terminal.wake_id} for run {result.run_id}.",
        )

    def run_control_tick(
        self,
        *,
        lease_owner: str,
        lease_seconds: int = 300,
        max_wakes: int = 1,
        source_roots: dict[str, Path | str] | None = None,
        recover_expired: bool = True,
        latest_limit: int = 20,
    ) -> KernelControlTick:
        recovered = self.recover_expired_wakes() if recover_expired else []
        executions: list[KernelWakeExecution] = []
        closebacks: list[KernelSourceCloseback] = []
        for _ in range(max(0, min(int(max_wakes), 50))):
            execution = self.run_next_wake(lease_owner=lease_owner, lease_seconds=lease_seconds)
            if execution.status == "idle":
                break
            executions.append(execution)
            if execution.wake_record is None or execution.result is None:
                continue
            closebacks.append(
                self.closeback_source_wake(
                    execution.wake_record,
                    execution.result,
                    source_root=self._source_root_for_closeback(execution.wake_record, source_roots),
                )
            )
        status = self._control_tick_status(executions)
        return KernelControlTick(
            status=status,
            lease_owner=lease_owner,
            recovered_wake_ids=[record.wake_id for record in recovered],
            executions=executions,
            closebacks=closebacks,
            latest_wake_status=self.latest_wake_status(limit=latest_limit),
            message=(
                f"Control tick executed {len(executions)} wake(s); "
                f"recovered {len(recovered)} expired wake(s)."
                if executions or recovered
                else "Control tick found no queued kernel wake."
            ),
        )

    @staticmethod
    def _source_root_for_closeback(
        wake_record: KernelWakeRecord,
        source_roots: dict[str, Path | str] | None,
    ) -> Path | str | None:
        if not source_roots:
            return None
        source = str(
            wake_record.envelope.metadata.get("normalized_from")
            or wake_record.envelope.trigger.metadata.get("normalized_from")
            or wake_record.envelope.trigger.source
        )
        return source_roots.get(source) or source_roots.get("*") or source_roots.get("default")

    @staticmethod
    def _control_tick_status(executions: list[KernelWakeExecution]) -> KernelWakeExecutionStatus:
        if not executions:
            return "idle"
        statuses = {execution.status for execution in executions}
        if "failed" in statuses:
            return "failed"
        if "blocked" in statuses:
            return "blocked"
        if "review" in statuses:
            return "review"
        return "completed"

    def wake(
        self,
        envelope: AgentRunEnvelope,
        *,
        lease_owner: str,
        lease_seconds: int = 300,
        wake_id: str | None = None,
    ) -> KernelWakeExecution:
        self.enqueue_wake(envelope, wake_id=wake_id, reason="wake_called")
        return self.run_next_wake(lease_owner=lease_owner, lease_seconds=lease_seconds)

    def closeback_source_wake(
        self,
        wake_record: KernelWakeRecord,
        result: KernelRunResult,
        *,
        source_root: Path | str | None = None,
    ) -> KernelSourceCloseback:
        source = str(
            wake_record.envelope.metadata.get("normalized_from")
            or wake_record.envelope.trigger.metadata.get("normalized_from")
            or wake_record.envelope.trigger.source
        )
        result_ref = self._kernel_result_ref(result)
        if not self._result_has_closeback_proof(result):
            closeback = self._closeback(
                source=source,
                status="blocked",
                mutated=False,
                reason="kernel_result_proof_missing",
                wake_record=wake_record,
                result_ref=result_ref,
            )
            self.store.record_wake_closeback(wake_record, closeback)
            return closeback

        if source == "a2a":
            closeback = self._closeback_a2a(wake_record, result, result_ref=result_ref, source_root=source_root)
        elif source == "ds_goal":
            closeback = self._closeback_ds_goal(wake_record, result, result_ref=result_ref, source_root=source_root)
        elif source == "persistent_self_wake":
            closeback = self._closeback_persistent_self_wake(
                wake_record,
                result,
                result_ref=result_ref,
                source_root=source_root,
            )
        elif source == "subagent":
            closeback = self._closeback_subagent(wake_record, result, result_ref=result_ref)
        elif source == "external_fleet":
            closeback = self._closeback(
                source=source,
                status="refused",
                mutated=False,
                reason="external_fleet_evidence_only_closeback_refused",
                wake_record=wake_record,
                result_ref=result_ref,
                source_ref={"kind": "external_fleet_wake_payload", "payload_hash": wake_record.envelope.metadata.get("source_payload_hash", "")},
            )
        else:
            closeback = self._closeback(
                source=source,
                status="recorded",
                mutated=False,
                reason="manual_wake_has_no_source_closeback",
                wake_record=wake_record,
                result_ref=result_ref,
                source_ref={"kind": f"{source}_wake_payload", "payload_hash": wake_record.envelope.metadata.get("source_payload_hash", "")},
            )
        self.store.record_wake_closeback(wake_record, closeback)
        return closeback

    def _closeback_subagent(
        self,
        wake_record: KernelWakeRecord,
        result: KernelRunResult,
        *,
        result_ref: dict[str, Any],
    ) -> KernelSourceCloseback:
        parent_run_id = wake_record.envelope.trigger.parent_run_id
        role = str(
            wake_record.envelope.trigger.metadata.get("subagent_role")
            or wake_record.envelope.task.metadata.get("subagent_role")
            or wake_record.envelope.metadata.get("subagent_role")
            or ""
        )
        receipt_ref = {
            "kind": "subagent_delivery",
            "parent_run_id": parent_run_id,
            "child_run_id": result.run_id,
            "child_agent_uid": wake_record.envelope.agent_uid,
            "status": result.status,
        }
        receipt_ref["payload_hash"] = stable_payload_hash(receipt_ref)
        return self._closeback(
            source="subagent",
            status="recorded",
            mutated=False,
            reason="subagent_result_recorded",
            wake_record=wake_record,
            result_ref=result_ref,
            source_ref={
                "kind": "subagent_wake",
                "parent_run_id": parent_run_id,
                "child_run_id": result.run_id,
                "child_agent_uid": wake_record.envelope.agent_uid,
                "role": role,
            },
            receipt_ref=receipt_ref,
        )

    def _closeback_a2a(
        self,
        wake_record: KernelWakeRecord,
        result: KernelRunResult,
        *,
        result_ref: dict[str, Any],
        source_root: Path | str | None,
    ) -> KernelSourceCloseback:
        if source_root is None:
            return self._closeback(
                source="a2a",
                status="blocked",
                mutated=False,
                reason="a2a_state_root_missing",
                wake_record=wake_record,
                result_ref=result_ref,
            )
        task_id = wake_record.envelope.trigger.task_id
        if not task_id:
            return self._closeback(
                source="a2a",
                status="blocked",
                mutated=False,
                reason="a2a_task_id_missing",
                wake_record=wake_record,
                result_ref=result_ref,
            )
        from dharma_swarm.operator_core.a2a_task_lifecycle import build_task_receipt, close_task, queue_path

        status = _kernel_close_status(result.status)
        return_address = wake_record.envelope.trigger.metadata.get("return_address")
        if not isinstance(return_address, dict):
            return_address = None
        failure_reason = f"kernel_result_status_{result.status}" if status != "completed" else None
        receipt = build_task_receipt(
            task_id=task_id,
            agent_uid=wake_record.envelope.agent_uid,
            status=status,
            summary=f"LivingAgentKernel closeback: {result.status}",
            correlation_id=wake_record.envelope.trigger.correlation_id or None,
            return_address=return_address,
            authority="operator_core.living_agent_kernel.source_closeback",
            evidence={"kernel_result": result_ref},
            replay_command="pytest -q tests/test_living_agent_kernel.py --tb=short",
            spine_receipt_id=result.proof_ledger_entry.entry_hash,
            completion_via="operator_core.living_agent_kernel.source_closeback",
            failure_reason=failure_reason,
        )
        try:
            closed = close_task(
                task_id,
                agent_uid=wake_record.envelope.agent_uid,
                status=status,
                receipt=receipt,
                state_root=source_root,
                closed_via="operator_core.living_agent_kernel.source_closeback",
                require_artifact_or_evidence=False,
            )
        except Exception as exc:
            return self._closeback(
                source="a2a",
                status="blocked",
                mutated=False,
                reason=f"a2a_closeback_failed:{type(exc).__name__}:{exc}",
                wake_record=wake_record,
                result_ref=result_ref,
                source_ref={"kind": "a2a_task_queue", "state_root": str(Path(source_root)), "task_id": task_id},
            )
        return self._closeback(
            source="a2a",
            status="closed",
            mutated=True,
            reason="a2a_task_closed_with_kernel_receipt",
            wake_record=wake_record,
            result_ref=result_ref,
            source_ref={
                "kind": "a2a_task_queue",
                "state_root": str(Path(source_root)),
                "path": str(queue_path(source_root)),
                "task_id": task_id,
                "queue_status": str(closed.get("status") or ""),
            },
            receipt_ref={
                "kind": "a2a_task_receipt",
                "receipt_id": str(receipt.get("receipt_id") or ""),
                "content_hash": str(receipt.get("content_hash") or ""),
            },
        )

    def _closeback_ds_goal(
        self,
        wake_record: KernelWakeRecord,
        result: KernelRunResult,
        *,
        result_ref: dict[str, Any],
        source_root: Path | str | None,
    ) -> KernelSourceCloseback:
        if source_root is None:
            return self._closeback(
                source="ds_goal",
                status="blocked",
                mutated=False,
                reason="ds_goal_state_root_missing",
                wake_record=wake_record,
                result_ref=result_ref,
            )
        task_id = wake_record.envelope.trigger.task_id
        mission_id = wake_record.envelope.trigger.mission_id
        tasks_path = self._ds_goal_tasks_path(Path(source_root), mission_id)
        if tasks_path is None:
            return self._closeback(
                source="ds_goal",
                status="blocked",
                mutated=False,
                reason="ds_goal_tasks_path_missing",
                wake_record=wake_record,
                result_ref=result_ref,
                source_ref={"kind": "ds_goal_tasks", "state_root": str(Path(source_root)), "mission_id": mission_id, "task_id": task_id},
            )
        tasks = _jsonl_rows(tasks_path)
        matched = False
        for task in tasks:
            if str(task.get("task_id") or task.get("id") or "") != task_id:
                continue
            matched = True
            task["kernel_result_ref"] = result_ref
            task["kernel_result_status"] = result.status
            task["kernel_closeback_at"] = utc_now()
            task["kernel_closeback_via"] = "operator_core.living_agent_kernel.source_closeback"
            break
        if not matched:
            return self._closeback(
                source="ds_goal",
                status="blocked",
                mutated=False,
                reason="ds_goal_task_not_found",
                wake_record=wake_record,
                result_ref=result_ref,
                source_ref={"kind": "ds_goal_tasks", "path": str(tasks_path), "mission_id": mission_id, "task_id": task_id},
            )
        _write_jsonl_rows(tasks_path, tasks)
        return self._closeback(
            source="ds_goal",
            status="recorded",
            mutated=True,
            reason="ds_goal_task_kernel_result_ref_recorded",
            wake_record=wake_record,
            result_ref=result_ref,
            source_ref={"kind": "ds_goal_tasks", "path": str(tasks_path), "mission_id": mission_id, "task_id": task_id},
        )

    def _closeback_persistent_self_wake(
        self,
        wake_record: KernelWakeRecord,
        result: KernelRunResult,
        *,
        result_ref: dict[str, Any],
        source_root: Path | str | None,
    ) -> KernelSourceCloseback:
        source_base = Path(source_root).expanduser().resolve() if source_root is not None else None
        raw_witness = str(wake_record.envelope.trigger.metadata.get("witness_log") or "")
        if raw_witness:
            witness_path = Path(raw_witness).expanduser()
            if not witness_path.is_absolute() and source_base is not None:
                witness_path = source_base / witness_path
        elif source_base is not None:
            witness_path = source_base / "witness" / "kernel_self_wake_receipts.jsonl"
        else:
            return self._closeback(
                source="persistent_self_wake",
                status="blocked",
                mutated=False,
                reason="persistent_self_wake_witness_log_missing",
                wake_record=wake_record,
                result_ref=result_ref,
            )
        witness_path = witness_path.resolve()
        if source_base is not None and not witness_path.is_relative_to(source_base):
            return self._closeback(
                source="persistent_self_wake",
                status="blocked",
                mutated=False,
                reason="persistent_self_wake_witness_log_outside_source_root",
                wake_record=wake_record,
                result_ref=result_ref,
                source_ref={"kind": "persistent_self_wake_witness", "path": str(witness_path)},
            )
        receipt = {
            "schema_version": "dharma_living_agent_kernel_self_wake_receipt.v1",
            "agent_uid": wake_record.envelope.agent_uid,
            "run_id": result.run_id,
            "wake_id": wake_record.wake_id,
            "status": result.status,
            "correlation_id": wake_record.envelope.trigger.correlation_id,
            "result_ref": result_ref,
            "created_at": utc_now(),
        }
        _append_jsonl(witness_path, receipt)
        return self._closeback(
            source="persistent_self_wake",
            status="recorded",
            mutated=True,
            reason="persistent_self_wake_witness_receipt_recorded",
            wake_record=wake_record,
            result_ref=result_ref,
            source_ref={"kind": "persistent_self_wake_witness", "path": str(witness_path)},
            receipt_ref={"kind": "self_wake_receipt", "path": str(witness_path), "payload_hash": stable_payload_hash(receipt)},
        )

    @staticmethod
    def _ds_goal_tasks_path(source_root: Path, mission_id: str) -> Path | None:
        root = source_root.expanduser().resolve()
        candidates = [root / "tasks.jsonl"]
        if mission_id:
            candidates.append(root / mission_id / "tasks.jsonl")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _kernel_result_ref(result: KernelRunResult) -> dict[str, Any]:
        return {
            "kind": "kernel_run_result",
            "run_id": result.run_id,
            "status": result.status,
            "replay_ref": dict(result.replay_ref),
            "proof_entry_hash": result.proof_ledger_entry.entry_hash,
            "runtime_truth_ref": dict(result.proof_ledger_entry.runtime_truth_ref),
        }

    @staticmethod
    def _result_has_closeback_proof(result: KernelRunResult) -> bool:
        return bool(
            result.did_persist
            and result.proof_ledger_entry.entry_hash
            and result.replay_ref
            and result.replay_ref.get("integrity_ok") is True
        )

    @staticmethod
    def _closeback(
        *,
        source: str,
        status: KernelSourceClosebackStatus,
        mutated: bool,
        reason: str,
        wake_record: KernelWakeRecord,
        result_ref: dict[str, Any],
        source_ref: dict[str, Any] | None = None,
        receipt_ref: dict[str, Any] | None = None,
    ) -> KernelSourceCloseback:
        return KernelSourceCloseback(
            source=source,
            status=status,
            mutated=mutated,
            reason=reason,
            wake_id=wake_record.wake_id,
            run_id=wake_record.run_id,
            source_ref=source_ref or {},
            result_ref=result_ref,
            receipt_ref=receipt_ref or {},
        )

    def compile_tool_plan(
        self,
        envelope: AgentRunEnvelope,
        admission: GovernedWorkAdmission | None = None,
    ) -> ToolPlan:
        decision = admission or self.evaluate_authority(envelope)
        visible = list(READ_ONLY_TOOLS)
        denial_reasons: dict[str, str] = {
            tool: "dangerous_external_action_requires_separate_authority" for tool in DANGEROUS_TOOLS
        }
        if decision.decision == "allow" and envelope.authority.work_kind == WorkKind.CODE_WRITE:
            visible.extend(WRITE_TOOLS)
        elif envelope.authority.work_kind in {
            WorkKind.CODE_WRITE,
            WorkKind.LONG_RUNNING,
            WorkKind.SELF_EVOLUTION,
            WorkKind.PROMOTION,
        }:
            for tool in (*WRITE_TOOLS, "process_spawn", "write_file"):
                denial_reasons[tool] = f"authority_decision_{decision.decision}"
        if envelope.authority.work_kind == WorkKind.SELF_EVOLUTION:
            for tool in SELF_EVOLUTION_TOOLS:
                denial_reasons[tool] = f"authority_decision_{decision.decision}"
        if envelope.authority.protected_file_hits:
            denial_reasons["mutate_protected_files"] = "protected_file_hits"
        if envelope.authority.external_worker_authority == "external_worker_evidence_only":
            for tool in EVIDENCE_ONLY_DENIED_TOOLS:
                denial_reasons[tool] = "external_worker_evidence_only"

        call_names = {
            str(call.get("name") or call.get("tool_name") or "")
            for call in envelope.tool_request.tool_calls
        }
        requested = set(envelope.tool_request.requested_tools) | {name for name in call_names if name}
        for tool in requested:
            if tool in denial_reasons:
                continue
            if tool in {*WRITE_TOOLS, "write_file"} and envelope.authority.work_kind != WorkKind.CODE_WRITE:
                denial_reasons[tool] = "write_tool_requires_code_write_authority"
                continue
            if decision.decision == "allow" and tool not in DANGEROUS_TOOLS:
                visible.append(tool)
            else:
                denial_reasons[tool] = f"authority_decision_{decision.decision}"

        diagnostics = [
            f"admission={decision.decision}",
            *[f"reason={reason}" for reason in decision.reasons],
            *[f"required_receipt={receipt}" for receipt in decision.required_receipts],
        ]
        payload = {
            "visible_tools": _sorted_unique(visible),
            "denied_tools": _sorted_unique(list(denial_reasons)),
            "denial_reasons": dict(sorted(denial_reasons.items())),
            "tool_schemas": self.tool_registry.schemas(_sorted_unique(visible)),
            "sandbox_policy": dict(envelope.tool_request.sandbox_policy),
            "inherited_subagent_limits": dict(envelope.tool_request.inherited_subagent_limits),
            "late_bound_tools": _sorted_unique(envelope.tool_request.late_bound_tools),
            "diagnostics": sorted(diagnostics),
        }
        return ToolPlan(**payload, policy_hash=stable_payload_hash(payload))

    def record_proof(
        self,
        envelope: AgentRunEnvelope,
        admission: GovernedWorkAdmission,
        tool_plan: ToolPlan,
        status: KernelRunStatus,
        runtime_truth_packet: RuntimeTruthPacket,
        *,
        event_refs: list[dict[str, Any]] | None = None,
        tool_result_refs: list[dict[str, Any]] | None = None,
        unsupported_claims: list[str] | None = None,
    ) -> ProofLedgerEntry:
        return ProofLedgerEntry(
            run_id=envelope.run_id,
            agent_uid=envelope.agent_uid,
            status=status,
            envelope_hash=stable_payload_hash(_model_payload(envelope)),
            tool_plan_hash=tool_plan.policy_hash,
            authority_decision=admission.decision,
            authority_reasons=list(admission.reasons),
            mission_id=envelope.trigger.mission_id,
            task_id=envelope.trigger.task_id,
            correlation_id=envelope.trigger.correlation_id,
            runtime_truth_ref={
                "surface_id": runtime_truth_packet.surface_id,
                "run_id": runtime_truth_packet.run_id,
                "source_kind": runtime_truth_packet.source_kind,
            },
            receipt_refs=list(envelope.proof.receipt_refs),
            artifact_refs=list(envelope.proof.artifact_refs),
            event_refs=list(event_refs or []),
            tool_result_refs=list(tool_result_refs or []),
            verifier_commands=list(envelope.proof.verifier_commands),
            unsupported_claims=list(unsupported_claims or ["no_provider_execution_in_v1"]),
        )

    def run(self, envelope: AgentRunEnvelope) -> KernelRunResult:
        admission = self.evaluate_authority(envelope)
        tool_plan = self.compile_tool_plan(envelope, admission)
        status = self._status_for(admission)
        event_refs: list[dict[str, Any]] = []
        tool_result_refs: list[dict[str, Any]] = []
        if self.persist:
            event_refs.append(
                self.store.append_event(
                    envelope,
                    suffix="000_run_started",
                    event_type=RuntimeEventType.AUDIT_EVENT,
                    payload={
                        "gate": "living_agent_kernel.run",
                        "result": "started",
                        "reason": admission.decision,
                        "tool_call_count": len(envelope.tool_request.tool_calls),
                    },
                )
            )

        tool_results = self._execute_tool_calls(envelope, admission, tool_plan, event_refs, tool_result_refs)
        status = self._status_after_tools(status, tool_results)
        did_execute = any(result.status == "completed" for result in tool_results)
        runtime_truth_packet = self._runtime_truth_packet(
            envelope,
            admission,
            status,
            tool_results=tool_results,
            event_refs=event_refs,
            tool_result_refs=tool_result_refs,
        )
        unsupported_claims = ["no_provider_execution_in_v1"]
        if any(result.tool_name == "memory_read" and result.status == "completed" for result in tool_results):
            unsupported_claims.append("memory_read_projection_only")
        if any(
            result.tool_name == "apply_patch"
            and result.status == "completed"
            and result.output.get("mutation_mode") == "dry_run"
            for result in tool_results
        ):
            unsupported_claims.append("apply_patch_dry_run_only")
        if any(
            result.tool_name == "apply_patch"
            and result.status == "completed"
            and result.output.get("mutation_mode") == "apply"
            for result in tool_results
        ):
            unsupported_claims.append("write_tool_execution_limited_to_kernel_diff_adapter")
        if any(
            result.tool_name == "memory_write" and result.status == "completed"
            for result in tool_results
        ):
            unsupported_claims.append("memory_write_mutation_limited_to_agent_lessons_ledger")
        if any(result.denial_reason == "tool_not_registered_in_kernel_v1" for result in tool_results):
            unsupported_claims.append("write_or_custom_tool_dispatch_not_implemented_in_v1")

        if self.persist:
            event_refs.append(
                self.store.append_event(
                    envelope,
                    suffix="999_run_finished",
                    event_type=RuntimeEventType.AUDIT_EVENT,
                    payload={
                        "gate": "living_agent_kernel.run",
                        "result": status,
                        "reason": admission.decision,
                        "tool_result_count": len(tool_results),
                        "completed_tool_count": sum(1 for result in tool_results if result.status == "completed"),
                    },
                )
            )

        proof = self.record_proof(
            envelope,
            admission,
            tool_plan,
            status,
            runtime_truth_packet,
            event_refs=event_refs,
            tool_result_refs=tool_result_refs,
            unsupported_claims=unsupported_claims,
        )
        replay_ref: dict[str, Any] = {}
        if self.persist:
            proof = self.store.append_proof_entry(proof)
            replay = self.store.replay_run(envelope.run_id)
            replay_ref = {
                "kind": "kernel_replay",
                "run_id": envelope.run_id,
                "replay_hash": replay.replay_hash,
                "integrity_ok": replay.integrity_ok,
            }
        return KernelRunResult(
            status=status,
            run_id=envelope.run_id,
            did_execute=did_execute,
            did_persist=self.persist,
            message=self._message_for(tool_results),
            admission=admission,
            tool_plan=tool_plan,
            tool_results=tool_results,
            event_refs=event_refs,
            replay_ref=replay_ref,
            runtime_truth_packet=runtime_truth_packet.to_dict(),
            proof_ledger_entry=proof,
            metadata={
                "kernel_version": "v1",
                "execution_mode": "read_only_tool_dispatch" if did_execute else "durable_governed_projection",
                "event_count": len(event_refs),
                "tool_result_count": len(tool_results),
            },
        )

    def _execute_tool_calls(
        self,
        envelope: AgentRunEnvelope,
        admission: GovernedWorkAdmission,
        tool_plan: ToolPlan,
        event_refs: list[dict[str, Any]],
        tool_result_refs: list[dict[str, Any]],
    ) -> list[KernelToolResult]:
        results: list[KernelToolResult] = []
        context = self._tool_context(envelope, admission, tool_plan)
        for index, call in enumerate(envelope.tool_request.tool_calls, start=1):
            tool_name = str(call.get("name") or call.get("tool_name") or "")
            raw_arguments = call.get("arguments", call.get("args", {}))
            arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
            if not tool_name:
                result = _tool_result(run_id=envelope.run_id, tool_name="", status="denied", arguments=arguments, denial_reason="tool_name_missing")
            elif admission.decision != "allow":
                result = _tool_result(
                    run_id=envelope.run_id,
                    tool_name=tool_name,
                    status="denied",
                    arguments=arguments,
                    denial_reason=f"authority_decision_{admission.decision}",
                )
            elif tool_name in tool_plan.denial_reasons:
                result = _tool_result(
                    run_id=envelope.run_id,
                    tool_name=tool_name,
                    status="denied",
                    arguments=arguments,
                    denial_reason=tool_plan.denial_reasons[tool_name],
                )
            elif tool_name not in tool_plan.visible_tools:
                result = _tool_result(
                    run_id=envelope.run_id,
                    tool_name=tool_name,
                    status="denied",
                    arguments=arguments,
                    denial_reason="tool_not_visible_after_policy",
                )
            elif tool_name == "apply_patch":
                result = self._dispatch_apply_patch(envelope, arguments)
            elif tool_name == "memory_write":
                result = self._dispatch_memory_write(envelope, arguments)
            else:
                result = self.tool_registry.dispatch(tool_name=tool_name, arguments=arguments, context=context)

            if self.persist:
                event_ref = self.store.append_event(
                    envelope,
                    suffix=f"{100 + index:03d}_tool_{self._safe_event_suffix(tool_name)}",
                    event_type=RuntimeEventType.ACTION_EVENT,
                    payload={
                        "action_name": f"tool:{tool_name or 'unknown'}",
                        "decision": result.status,
                        "confidence": 1.0,
                        "tool_name": tool_name,
                        "arguments_hash": result.arguments_hash,
                        "denial_reason": result.denial_reason,
                        "error": result.error,
                    },
                )
                result.event_ref = event_ref
                _seal_tool_result(result)
                event_refs.append(event_ref)
                tool_result_refs.append(self.store.append_tool_result(result))
            results.append(result)
        return results

    def _dispatch_apply_patch(self, envelope: AgentRunEnvelope, arguments: dict[str, Any]) -> KernelToolResult:
        patch_text = str(arguments.get("patch") or arguments.get("diff") or "")
        if not patch_text.strip():
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="apply_patch",
                status="failed",
                arguments=arguments,
                error="apply_patch_requires_patch_or_diff",
            )
        if envelope.authority.work_kind != WorkKind.CODE_WRITE:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="apply_patch",
                status="denied",
                arguments=arguments,
                denial_reason="apply_patch_requires_code_write_authority",
            )
        if not envelope.authority.mission_contract_present or not envelope.authority.workspace_lease_present:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="apply_patch",
                status="denied",
                arguments=arguments,
                denial_reason="apply_patch_requires_mission_contract_and_workspace_lease",
            )
        if envelope.authority.external_worker_authority == "external_worker_evidence_only":
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="apply_patch",
                status="denied",
                arguments=arguments,
                denial_reason="external_worker_evidence_only",
            )

        sandbox_policy = dict(envelope.tool_request.sandbox_policy)
        mutation_mode = str(sandbox_policy.get("mutation_mode") or "dry_run").strip().lower()
        if mutation_mode not in {"dry_run", "apply"}:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="apply_patch",
                status="denied",
                arguments=arguments,
                denial_reason="apply_patch_mutation_mode_invalid",
            )
        dry_run = mutation_mode != "apply"
        if not dry_run and sandbox_policy.get("allow_write_tool_execution") is not True:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="apply_patch",
                status="denied",
                arguments=arguments,
                denial_reason="apply_patch_live_apply_requires_explicit_sandbox_allowance",
            )
        if not dry_run and sandbox_policy.get("rollback_receipt_required") is not True:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="apply_patch",
                status="denied",
                arguments=arguments,
                denial_reason="apply_patch_live_apply_requires_rollback_receipt",
            )

        try:
            from dharma_swarm.diff_applier import DiffApplier, parse_unified_diff

            patches = parse_unified_diff(patch_text)
        except Exception as exc:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="apply_patch",
                status="failed",
                arguments=arguments,
                error=f"apply_patch_parse_failed:{type(exc).__name__}:{exc}",
            )

        workspace = self.workspace_root.resolve()
        target_refs: list[dict[str, Any]] = []
        for patch in patches:
            if patch.new_path == "/dev/null":
                return _tool_result(
                    run_id=envelope.run_id,
                    tool_name="apply_patch",
                    status="denied",
                    arguments=arguments,
                    denial_reason="apply_patch_delete_file_not_supported_in_kernel_v1",
                )
            target_rel = _safe_diff_target(patch.target_path)
            if not target_rel:
                return _tool_result(
                    run_id=envelope.run_id,
                    tool_name="apply_patch",
                    status="denied",
                    arguments=arguments,
                    denial_reason="apply_patch_target_path_unsafe",
                )
            target = (workspace / target_rel).resolve()
            if not target.is_relative_to(workspace):
                return _tool_result(
                    run_id=envelope.run_id,
                    tool_name="apply_patch",
                    status="denied",
                    arguments=arguments,
                    denial_reason="apply_patch_target_outside_workspace",
                )
            if _path_matches_contract(target, envelope.authority.forbidden_files, workspace_root=workspace):
                return _tool_result(
                    run_id=envelope.run_id,
                    tool_name="apply_patch",
                    status="denied",
                    arguments=arguments,
                    denial_reason="apply_patch_target_forbidden",
                )
            if not _path_matches_contract(target, envelope.authority.allowed_files, workspace_root=workspace):
                return _tool_result(
                    run_id=envelope.run_id,
                    tool_name="apply_patch",
                    status="denied",
                    arguments=arguments,
                    denial_reason="apply_patch_target_not_allowed",
                )
            if not dry_run and patch.is_new_file:
                return _tool_result(
                    run_id=envelope.run_id,
                    tool_name="apply_patch",
                    status="denied",
                    arguments=arguments,
                    denial_reason="apply_patch_new_file_live_apply_lacks_rollback_backup",
                )
            backup_path = target.with_suffix(target.suffix + ".bak")
            if not dry_run and backup_path.exists():
                return _tool_result(
                    run_id=envelope.run_id,
                    tool_name="apply_patch",
                    status="denied",
                    arguments=arguments,
                    denial_reason="apply_patch_rollback_backup_path_already_exists",
                )
            target_refs.append(
                {
                    "path": str(target),
                    "relative_path": target_rel,
                    "is_new_file": bool(patch.is_new_file),
                    "backup_path": str(backup_path) if not patch.is_new_file else "",
                }
            )

        try:
            apply_result = self._run_diff_apply(DiffApplier(workspace=workspace).apply(patch_text, dry_run=dry_run))
        except RuntimeError as exc:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="apply_patch",
                status="failed",
                arguments=arguments,
                error=f"apply_patch_adapter_failed:{exc}",
            )
        if not apply_result.success:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="apply_patch",
                status="failed",
                arguments=arguments,
                error=apply_result.error,
                output={
                    "mutation_mode": mutation_mode,
                    "dry_run": dry_run,
                    "target_refs": target_refs,
                    "files_changed": list(apply_result.files_changed),
                    "backup_paths": dict(apply_result.backup_paths),
                },
            )

        return _tool_result(
            run_id=envelope.run_id,
            tool_name="apply_patch",
            status="completed",
            arguments=arguments,
            output={
                "mutation_mode": mutation_mode,
                "dry_run": dry_run,
                "applied": not dry_run,
                "target_refs": target_refs,
                "files_changed": list(apply_result.files_changed),
                "backup_paths": dict(apply_result.backup_paths),
                "rollback_available": bool(apply_result.backup_paths),
                "provider_execution": False,
                "subprocess_execution": False,
            },
        )

    def _dispatch_memory_write(self, envelope: AgentRunEnvelope, arguments: dict[str, Any]) -> KernelToolResult:
        if envelope.authority.work_kind != WorkKind.CODE_WRITE:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="memory_write",
                status="denied",
                arguments=arguments,
                denial_reason="memory_write_requires_code_write_authority",
            )
        if not envelope.authority.mission_contract_present or not envelope.authority.workspace_lease_present:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="memory_write",
                status="denied",
                arguments=arguments,
                denial_reason="memory_write_requires_mission_contract_and_workspace_lease",
            )
        if envelope.authority.external_worker_authority == "external_worker_evidence_only":
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="memory_write",
                status="denied",
                arguments=arguments,
                denial_reason="external_worker_evidence_only",
            )
        namespace = str(arguments.get("namespace") or "").strip()
        if not namespace:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="memory_write",
                status="denied",
                arguments=arguments,
                denial_reason="memory_write_namespace_required",
            )
        if namespace not in envelope.memory.write_namespaces:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="memory_write",
                status="denied",
                arguments=arguments,
                denial_reason="memory_write_namespace_not_declared",
            )
        from dharma_swarm.operator_core.living_agent_kernel_lessons import EmptyLessonDeltaError

        delta = str(arguments.get("delta") or "").strip() or str(envelope.memory.proposed_learning_delta or "").strip()
        if not delta:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="memory_write",
                status="failed",
                arguments=arguments,
                error="memory_write_requires_delta_or_proposed_learning_delta",
            )
        try:
            receipt = self.lesson_store.append_lesson(
                envelope.agent_uid,
                namespace,
                delta,
                run_id=envelope.run_id,
                provenance={
                    "source": envelope.trigger.source,
                    "mission_id": envelope.trigger.mission_id,
                    "task_id": envelope.trigger.task_id,
                    "correlation_id": envelope.trigger.correlation_id,
                    "parent_run_id": envelope.trigger.parent_run_id,
                },
            )
        except EmptyLessonDeltaError:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="memory_write",
                status="failed",
                arguments=arguments,
                error="memory_write_requires_delta_or_proposed_learning_delta",
            )
        except ValueError as exc:
            return _tool_result(
                run_id=envelope.run_id,
                tool_name="memory_write",
                status="denied",
                arguments=arguments,
                denial_reason="memory_write_namespace_unsafe",
                error=f"{type(exc).__name__}:{exc}",
            )
        return _tool_result(
            run_id=envelope.run_id,
            tool_name="memory_write",
            status="completed",
            arguments=arguments,
            output={
                "namespace": namespace,
                "agent_uid": receipt.agent_uid,
                "delta_hash": receipt.delta_hash,
                "receipt_hash": receipt.entry_hash,
                "ledger_sequence": receipt.ledger_sequence,
                "previous_entry_hash": receipt.previous_entry_hash,
                "provider_execution": False,
                "subprocess_execution": False,
            },
        )

    @staticmethod
    def _run_diff_apply(coro: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        coro.close()
        raise RuntimeError("apply_patch_adapter_requires_sync_kernel_call")

    def _tool_context(
        self,
        envelope: AgentRunEnvelope,
        admission: GovernedWorkAdmission,
        tool_plan: ToolPlan,
    ) -> dict[str, Any]:
        return {
            "run_id": envelope.run_id,
            "agent_uid": envelope.agent_uid,
            "task_source": envelope.task.source,
            "task_text": envelope.task.text,
            "authority_decision": admission.decision,
            "authority_reasons": list(admission.reasons),
            "visible_tools": list(tool_plan.visible_tools),
            "memory_read_namespaces": list(envelope.memory.read_namespaces),
            "allowed_files": list(envelope.authority.allowed_files),
            "workspace_root": str(self.workspace_root),
        }

    @staticmethod
    def _status_for(admission: GovernedWorkAdmission) -> KernelRunStatus:
        if admission.decision == "block":
            return "blocked"
        if admission.decision == "review":
            return "review"
        return "completed"

    @staticmethod
    def _status_after_tools(status: KernelRunStatus, tool_results: list[KernelToolResult]) -> KernelRunStatus:
        if status != "completed" or not tool_results:
            return status
        if any(result.status == "failed" for result in tool_results):
            return "failed"
        if any(result.status == "denied" for result in tool_results):
            if any(result.status == "completed" for result in tool_results):
                return "review"
            return "blocked"
        return status

    @staticmethod
    def _safe_event_suffix(value: str) -> str:
        suffix = "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")
        return suffix[:48] or "unknown"

    @staticmethod
    def _message_for(tool_results: list[KernelToolResult]) -> str:
        completed = sum(1 for result in tool_results if result.status == "completed")
        if completed:
            return f"LivingAgentKernel v1 dispatched {completed} read-only tool call(s)."
        return "LivingAgentKernel v1 persisted a governed run without provider execution."

    def _runtime_truth_packet(
        self,
        envelope: AgentRunEnvelope,
        admission: GovernedWorkAdmission,
        status: KernelRunStatus,
        *,
        tool_results: list[KernelToolResult] | None = None,
        event_refs: list[dict[str, Any]] | None = None,
        tool_result_refs: list[dict[str, Any]] | None = None,
    ) -> RuntimeTruthPacket:
        observed_tool_results = list(tool_results or [])
        live_mutation = any(
            result.tool_name == "apply_patch"
            and result.status == "completed"
            and result.output.get("mutation_mode") == "apply"
            and result.output.get("applied") is True
            for result in observed_tool_results
        )
        completion_state = RuntimeTruthState.UNKNOWN.value
        if status == "blocked":
            completion_state = RuntimeTruthState.BLOCKED_BY_RECEIPT.value
        elif any(result.status == "completed" for result in observed_tool_results):
            completion_state = RuntimeTruthState.COMPLETED_BY_RECEIPT.value
        elif status == "completed":
            completion_state = RuntimeTruthState.PROJECTION_ONLY.value
        return RuntimeTruthPacket(
            surface_id=f"living_agent_kernel:{envelope.agent_uid}",
            kind="living_agent_kernel",
            run_id=envelope.run_id,
            mission_id=envelope.trigger.mission_id,
            correlation_id=envelope.trigger.correlation_id,
            task_id=envelope.trigger.task_id,
            receipt_refs=list(envelope.proof.receipt_refs),
            artifact_refs=list(envelope.proof.artifact_refs),
            source_refs=[*(event_refs or []), *(tool_result_refs or [])],
            heartbeat_state=RuntimeTruthState.PROJECTION_ONLY.value,
            progress_state=RuntimeTruthState.PROGRESSING_BY_ARTIFACT.value if observed_tool_results else RuntimeTruthState.PROJECTION_ONLY.value,
            completion_state=completion_state,
            authority_state=RuntimeTruthState.PROJECTION_ONLY.value,
            mutation_truth=MutationTruth(
                dry_run_only=not live_mutation,
                human_review_candidate=admission.decision == "review",
            ),
            source_kind=RuntimeSourceKind.DERIVED_RECONCILIATION.value,
            missing_machine_fields=[] if envelope.trigger.correlation_id else ["correlation_id"],
        )


__all__ = [
    "AgentRunEnvelope",
    "AuthorityPassport",
    "KernelControlSnapshot",
    "KernelControlTick",
    "KernelDaemonControlReceipt",
    "KernelDaemonCycle",
    "KernelDaemonState",
    "KernelReadOnlyToolRegistry",
    "KernelRunReplay",
    "KernelRunResult",
    "KernelRunStore",
    "KernelSourceCloseback",
    "KernelSubagentDispatch",
    "KernelTask",
    "KernelToolResult",
    "KernelWakeExecution",
    "KernelWakeRecord",
    "KernelWakeSource",
    "LivingAgentKernel",
    "MemoryPlan",
    "ProofLedgerEntry",
    "ProofRequest",
    "ToolPlan",
    "ToolRequest",
    "TriggerEnvelope",
]
