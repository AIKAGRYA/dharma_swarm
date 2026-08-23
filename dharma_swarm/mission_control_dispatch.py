"""Fail-closed, stateless governed dispatch for canonical Mission Control tasks."""
from __future__ import annotations
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol
from unicodedata import normalize
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_contract import SCHEMA_VERSION, MissionControlError, clean_identifier, stable_id
from dharma_swarm.mission_control_execution import OwnerExecutionRef
from dharma_swarm.models import Task
from dharma_swarm.operator_core.execution_lease import ExecutionLeaseError, parse_time, safe_lease_id, utc_now, validate_execution_lease
from dharma_swarm.operator_core.governed_work_admission import GovernedWorkAdmission, GovernedWorkRequest, WorkKind, evaluate_governed_work_admission
from dharma_swarm.operator_core.reversibility_gate import ActionClass, classify_action
from dharma_swarm.task_board import TaskBoard
DISPATCH_SCHEMA_VERSION = "dharma.mission_control.dispatch.v1"
CAMPAIGN_DISPATCH_SCHEMA_VERSION = "dharma.mission_control.dispatch.v2"
CAMPAIGN_LEASE_SCHEMA_VERSION = "dharma.sadhana.campaign_execution_lease.v4"
LEASE_DISPATCH_ACTION = "mission_control_dispatch"
LEASE_WORKSPACE_ACTION = "mission_control_workspace"
GOVERNANCE_METADATA_KEY = "mission_control_governance"
_RISK_TIERS = {"safe": "Q1", "low": "Q1", "medium": "Q2", "high": "Q3", "critical": "Q4"}
_KIND_RANK = {kind: rank for rank, kind in enumerate((WorkKind.READ_ONLY, WorkKind.A2A_CLAIM, WorkKind.LONG_RUNNING, WorkKind.CODE_WRITE, WorkKind.SELF_EVOLUTION, WorkKind.PROMOTION))}
_CODE_WORDS = frozenset({"build", "change", "code", "commit", "create", "edit", "fix", "implement", "modify", "patch", "publish", "refactor", "rewrite", "source", "update", "write"})
@dataclass(frozen=True, slots=True)
class MissionDispatchRequest:
    request_id: str
    mission_id: str
    task_id: str
    dispatch_key: str
    claimed_principal: str
    attempt_generation: int | None = None
    @classmethod
    def new(cls, mission_id: str, task_id: str, *, dispatch_key: str = "default",
            claimed_principal: str,
            attempt_generation: int | None = None) -> MissionDispatchRequest:
        mission_id = clean_identifier(mission_id, "mission_id")
        task_id = clean_identifier(task_id, "task_id")
        dispatch_key = clean_identifier(dispatch_key, "dispatch_key")
        principal = clean_identifier(claimed_principal, "claimed_principal")
        _need(
            attempt_generation is None
            or (
                isinstance(attempt_generation, int)
                and not isinstance(attempt_generation, bool)
                and attempt_generation >= 0
            ),
            "attempt_generation must be absent or a nonnegative integer",
        )
        identity_parts = ["mission_dispatch", mission_id, task_id, dispatch_key]
        if attempt_generation is not None:
            identity_parts.append(str(attempt_generation))
        return cls(
            stable_id(*identity_parts),
            mission_id,
            task_id,
            dispatch_key,
            principal,
            attempt_generation,
        )
@dataclass(frozen=True, slots=True)
class GovernanceAdmission:
    subject_id: str
    subject_digest: str
    principal: str
    request_digest: str
    reasons: tuple[str, ...]
    required_receipts: tuple[str, ...]
    reduced_authority: dict[str, Any]
    decision: Literal["allow", "review"] = "allow"
@dataclass(frozen=True, slots=True)
class DispatchAuthorityEnvelope:
    claimed_principal: str
    mission_id: str
    task_id: str
    dispatch_key: str
    authority_ref: str
    authority_digest: str
    attempt_generation: int | None = None
@dataclass(frozen=True, slots=True)
class VerifiedDispatchAuthority:
    authenticated_principal: str
    mission_id: str
    task_id: str
    dispatch_key: str
    authority_ref: str
    authority_digest: str
    execution_lease: Mapping[str, Any]
    revoked_lease_ids: tuple[str, ...] = ()
    attempt_generation: int | None = None
@dataclass(frozen=True, slots=True)
class AuthorizedDispatch:
    request: MissionDispatchRequest
    admission: GovernanceAdmission
    authority_ref: str
    authority_digest: str
    execution: OwnerExecutionRef
    proves_delivery: bool = False
    proves_executor_liveness: bool = False
    proves_semantic_outcome: bool = False
class AuthorityVerifier(Protocol):
    async def verify(self, envelope: DispatchAuthorityEnvelope, *, request: MissionDispatchRequest, admission: GovernanceAdmission) -> VerifiedDispatchAuthority: ...
class DispatchExecutor(Protocol):
    async def dispatch(
        self,
        mission_id: str,
        task_id: str,
        *,
        dispatch_key: str = "default",
        authenticated_principal_id: str = "",
        attempt_generation: int | None = None,
    ) -> OwnerExecutionRef: ...
AdmissionEvaluator = Callable[[GovernedWorkRequest], GovernedWorkAdmission]
@dataclass(frozen=True, slots=True)
class _DispatchBinding:
    subject_id: str
    subject_digest: str
    request_digest: str
    governed_json: str
def _need(condition: bool, message: str) -> None:
    if not condition:
        raise MissionControlError(message)
def _exact_id(value: Any, label: str) -> str:
    _need(isinstance(value, str), f"{label} must be a string")
    cleaned = clean_identifier(value, label)
    _need(cleaned == value, f"{label} must be canonical")
    return cleaned
def _canonical_json(value: Any, label: str) -> str:
    try:
        return json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise MissionControlError(f"{label} must be JSON-serializable") from exc
def _digest(value: Any, label: str) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value, label).encode()).hexdigest()
def _copy(value: Any, label: str) -> Any:
    return json.loads(_canonical_json(value, label))
def _text_list(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    _need(type(value) in {list, tuple}, f"{label} must be a list")
    items = list(value)
    _need(
        all(isinstance(item, str) and item and item == item.strip() for item in items),
        f"{label} contains a noncanonical item",
    )
    _need(len(set(items)) == len(items), f"{label} contains duplicates")
    return items
def _scope_paths(value: Any, label: str) -> list[str]:
    items = _text_list(value, label)
    _need(all(not item.startswith(("/", "~")) and "\\" not in item and not set(item) & set("*?[]{}()!|") and ":" not in item.split("/", 1)[0] and all(part not in {"", ".", ".."} and not part.startswith("~") for part in item.split("/")) for item in items), f"{label} contains a noncanonical relative path")
    return items
def _paths_overlap(left: str, right: str) -> bool:
    left_parts, right_parts = (tuple(normalize("NFC", part).casefold() for part in path.split("/")) for path in (left, right))
    return left_parts[:len(right_parts)] == right_parts or right_parts[:len(left_parts)] == left_parts
def _contract_paths(contract: Mapping[str, Any], stem: str) -> list[str]:
    files, paths = contract.get(f"{stem}_files"), contract.get(f"{stem}_paths")
    checked_files = _scope_paths(files, f"canonical {stem}_files") if files is not None else None
    checked_paths = _scope_paths(paths, f"canonical {stem}_paths") if paths is not None else None
    _need(files is None or paths is None or checked_files == checked_paths, f"canonical {stem} path aliases conflict")
    return checked_files if checked_files is not None else (checked_paths or [])
def _work_kind(encoded: str, metadata: Mapping[str, Any], contract: Mapping[str, Any]) -> WorkKind:
    words = set(re.findall(r"[a-z_]+", encoded.lower()))
    sarathi = metadata.get("mission_control_sarathi")
    candidates = (
        contract.get("work_kind"),
        metadata.get("work_kind"),
        sarathi.get("work_kind") if isinstance(sarathi, Mapping) else None,
    )
    inferred = (
        WorkKind.READ_ONLY
        if WorkKind.READ_ONLY.value in candidates
        else WorkKind.LONG_RUNNING
    )
    if {"self_evolution", "selfevolution"} & words or {"self", "evolution"} <= words:
        inferred = WorkKind.SELF_EVOLUTION
    elif {"promotion", "merge"} & words:
        inferred = WorkKind.PROMOTION
    elif _CODE_WORDS & words:
        inferred = WorkKind.CODE_WRITE
    declared: list[WorkKind] = [inferred]
    for raw in candidates:
        if raw not in (None, ""):
            try:
                declared.append(WorkKind(str(raw)))
            except ValueError as exc:
                raise MissionControlError("canonical work_kind is invalid") from exc
    return max(declared, key=_KIND_RANK.__getitem__)
def _admission_payload(value: GovernanceAdmission) -> dict[str, Any]:
    _need(type(value) is GovernanceAdmission, "GovernanceAdmission evidence is required")
    return {
        "subject_id": value.subject_id,
        "subject_digest": value.subject_digest,
        "principal": value.principal,
        "request_digest": value.request_digest,
        "reasons": list(value.reasons),
        "required_receipts": list(value.required_receipts),
        "reduced_authority": value.reduced_authority,
        "decision": value.decision,
    }
def _snapshot_admission(value: GovernanceAdmission) -> GovernanceAdmission:
    row = _copy(_admission_payload(value), "governance admission")
    return GovernanceAdmission(row["subject_id"], row["subject_digest"],
                               row["principal"], row["request_digest"],
                               tuple(row["reasons"]), tuple(row["required_receipts"]),
                               row["reduced_authority"], row["decision"])
def _admission_digest(value: GovernanceAdmission) -> str:
    return _digest(_admission_payload(value), "governance admission")
def _lease_id(value: Any, label: str) -> str:
    identifier = _exact_id(value, label)
    try:
        canonical = safe_lease_id(identifier)
    except ExecutionLeaseError as exc:
        raise MissionControlError(f"{label} is unsafe") from exc
    _need(canonical == identifier, f"{label} is noncanonical")
    return identifier
def _task_payload(request: MissionDispatchRequest, task: Task) -> dict[str, Any]:
    metadata = task.metadata
    creation_hash = metadata.get("mission_task_creation_hash")
    _need(isinstance(creation_hash, str) and re.fullmatch(r"[0-9a-f]{64}", creation_hash) is not None,
          "task has an invalid canonical creation hash")
    semantics = {
        key: metadata[key]
        for key in (
            GOVERNANCE_METADATA_KEY,
            "mission_control_sarathi",
            "mission_campaign_authority",
            "mission_observed_input",
            "campaign_effect_mode",
            "requires_tooling",
            "allow_provider_routing",
            "provider_allowlist",
            "preferred_provider",
            "preferred_model",
        )
        if key in metadata
    }
    payload = {
        "schema_version": (
            DISPATCH_SCHEMA_VERSION
            if request.attempt_generation is None
            else CAMPAIGN_DISPATCH_SCHEMA_VERSION
        ),
        "mission_id": request.mission_id,
        "task_id": request.task_id,
        "dispatch_key": request.dispatch_key,
        "task": {"title": task.title, "description": task.description,
                 "priority": task.priority.value, "created_by": task.created_by,
                 "depends_on": sorted(task.depends_on),
                 "creation_hash": creation_hash,
                 "semantics": semantics},
    }
    if request.attempt_generation is not None:
        payload["attempt_generation"] = request.attempt_generation
    return payload


def _gate_input(
    request: MissionDispatchRequest,
    task: Task,
    payload: Mapping[str, Any],
) -> str:
    """Classify campaign work content without treating TCB field names as actions."""
    if request.attempt_generation is None:
        return _canonical_json(payload, "canonical dispatch payload")
    observed = task.metadata.get("mission_observed_input")
    observed_content = observed.get("content", "") if isinstance(observed, Mapping) else ""
    return _canonical_json(
        {
            "title": task.title,
            "description": task.description,
            "observed_content": observed_content,
        },
        "campaign action content",
    )


def _governed_request(request: MissionDispatchRequest, payload: Mapping[str, Any], encoded: str, gate_risk: str,
                      workspace: Mapping[str, Any] | None = None) -> GovernedWorkRequest:
    metadata = payload["task"]["semantics"]
    raw = metadata.get(GOVERNANCE_METADATA_KEY)
    _need(raw is None or isinstance(raw, Mapping), "canonical governance contract must be a mapping")
    contract = _copy(dict(raw or {}), "canonical governance contract")
    allowed, forbidden = _contract_paths(contract, "allowed"), _contract_paths(contract, "forbidden")
    task_digest = _digest(payload, "canonical dispatch payload")
    evidence = {"schema_version": payload["schema_version"],
                "mission_id": request.mission_id, "task_id": request.task_id,
                "dispatch_key": request.dispatch_key, "subject_digest": task_digest,
                "governance_contract_digest": _digest(contract, "governance contract")}
    if request.attempt_generation is not None:
        evidence["attempt_generation"] = request.attempt_generation
    if workspace is not None:
        evidence["authenticated_workspace"] = dict(workspace)
    return GovernedWorkRequest(
        request_id=request.request_id,
        agent_uid=request.claimed_principal,
        work_kind=_work_kind(encoded, metadata, contract),
        intent=encoded,
        risk_tier=_RISK_TIERS[gate_risk],
        allowed_files=allowed,
        forbidden_files=forbidden,
        mission_contract_present=True,
        workspace_lease_present=workspace is not None,
        metadata=evidence,
    )
class GovernedMissionDispatcher:
    def __init__(self, mission_control: MissionControl, board: TaskBoard,
                 executor: DispatchExecutor, *, authority_verifier: AuthorityVerifier,
                 admission_evaluator: AdmissionEvaluator = evaluate_governed_work_admission) -> None:
        if authority_verifier is None:
            raise ValueError("authority_verifier is required")
        if executor is None:
            raise ValueError("executor is required")
        if admission_evaluator is None:
            raise ValueError("admission_evaluator is required")
        self._mission_control = mission_control
        self._board = board
        self._executor = executor
        self._authority_verifier = authority_verifier
        self._admission_evaluator = admission_evaluator
    async def canonical_governed_request(self, request: MissionDispatchRequest) -> GovernedWorkRequest:
        return GovernedWorkRequest.model_validate_json((await self._binding(request)).governed_json)
    async def admit(
        self, request: MissionDispatchRequest, governed_request: GovernedWorkRequest
    ) -> GovernanceAdmission:
        binding = await self._binding(request, governed_request)
        evaluated = self._evaluate(binding)
        _need(await self._binding(request, governed_request) == binding, "dispatch request changed during admission")
        return self._admission_from(binding, request, evaluated)
    async def authorize(self, request: MissionDispatchRequest,
                        governed_request: GovernedWorkRequest,
                        admission: GovernanceAdmission,
                        authority: DispatchAuthorityEnvelope) -> VerifiedDispatchAuthority:
        verified, _, _, _ = await self._authorize_flow(
            request, governed_request, admission, authority)
        return verified
    async def dispatch(self, request: MissionDispatchRequest,
                       governed_request: GovernedWorkRequest,
                       admission: GovernanceAdmission,
                       authority: DispatchAuthorityEnvelope) -> AuthorizedDispatch:
        caller, caller_guard = admission, _admission_digest(admission)
        admission = _snapshot_admission(caller)
        snapshot_guard = _admission_digest(admission)
        verified, preliminary, final, final_admission = await self._authorize_flow(
            request, governed_request, admission, authority)
        _need(
            _admission_digest(caller) == caller_guard and _admission_digest(admission) == snapshot_guard,
            "governance admission changed before dispatch",
        )
        verified = await self._verify_authority(authority, request=request, admission=final_admission)
        self._require_verified(request, authority, verified)
        self._require_lease(request, verified)
        current = await self._binding(request)
        _need(current == preliminary, "canonical task changed during final authority refresh")
        current_final = await self._binding(request, verified=verified)
        _need(current_final == final, "workspace authority changed during final authority refresh")
        expected = self._admission_from(
            current_final, request, self._evaluate(current_final, require_allow=True))
        _need(final_admission == expected, "final governance admission changed before dispatch")
        executor_args: dict[str, Any] = {
            "dispatch_key": request.dispatch_key,
            "authenticated_principal_id": verified.authenticated_principal,
        }
        if request.attempt_generation is not None:
            executor_args["attempt_generation"] = request.attempt_generation
        execution = await self._executor.dispatch(
            request.mission_id,
            request.task_id,
            **executor_args,
        )
        _need(type(execution) is OwnerExecutionRef, "owner executor returned an invalid reference type")
        _need(
            (
                execution.mission_id,
                execution.task_id,
                execution.dispatch_key,
                execution.attempt_generation,
            )
            == (
                request.mission_id,
                request.task_id,
                request.dispatch_key,
                request.attempt_generation,
            ),
            "owner executor returned a foreign reference",
        )
        _need(
            execution.agent_id == verified.authenticated_principal,
            "owner executor returned a foreign authenticated principal",
        )
        return AuthorizedDispatch(request, final_admission, verified.authority_ref,
                                  verified.authority_digest, execution)
    async def _authorize_flow(self, request: MissionDispatchRequest,
                              governed_request: GovernedWorkRequest,
                              admission: GovernanceAdmission,
                              authority: DispatchAuthorityEnvelope,
                              ) -> tuple[VerifiedDispatchAuthority, _DispatchBinding,
                                         _DispatchBinding, GovernanceAdmission]:
        caller, caller_guard = admission, _admission_digest(admission)
        admission = _snapshot_admission(caller)
        snapshot_guard = _admission_digest(admission)
        self._require_envelope(request, authority)
        preliminary = await self._binding(request, governed_request)
        expected = self._admission_from(preliminary, request, self._evaluate(preliminary))
        _need(admission == expected, "preliminary governance admission does not bind the dispatch request")
        _need(await self._binding(request, governed_request) == preliminary,
              "dispatch request changed during preliminary evaluation")
        verified = await self._verify_authority(authority, request=request, admission=admission)
        _need(_admission_digest(caller) == caller_guard
              and _admission_digest(admission) == snapshot_guard,
              "governance admission changed during verification")
        self._require_verified(request, authority, verified)
        self._require_lease(request, verified)
        try:
            refreshed = await self._binding(request, governed_request)
        except MissionControlError as exc:
            raise MissionControlError("canonical task changed during authorization") from exc
        _need(refreshed == preliminary, "canonical task changed during authorization")
        final = await self._binding(request, verified=verified)
        _need((final.subject_id, final.subject_digest)
              == (preliminary.subject_id, preliminary.subject_digest),
              "canonical task changed before final admission")
        self._require_verified(request, authority, verified)
        self._require_lease(request, verified)
        final_admission = self._admission_from(
            final, request, self._evaluate(final, require_allow=True))
        _need(_admission_digest(caller) == caller_guard
              and _admission_digest(admission) == snapshot_guard,
              "governance admission changed during final authorization")
        return verified, preliminary, final, final_admission
    async def _verify_authority(self, authority: DispatchAuthorityEnvelope, *, request: MissionDispatchRequest, admission: GovernanceAdmission) -> VerifiedDispatchAuthority:
        try:
            verified = await self._authority_verifier.verify(authority, request=request, admission=admission)
        except MissionControlError:
            raise
        except Exception as exc:
            raise MissionControlError("dispatch authority verification failed") from exc
        _need(type(verified) is VerifiedDispatchAuthority, "authority verifier returned an invalid evidence type")
        return verified
    async def _binding(self, request: MissionDispatchRequest, governed_request: GovernedWorkRequest | None = None, *,
                       verified: VerifiedDispatchAuthority | None = None) -> _DispatchBinding:
        self._require_request(request)
        mission = await self._mission_control.get_mission(request.mission_id)
        _need(mission is not None, f"mission {request.mission_id!r} was not found")
        _need(
            (mission.mission_id, mission.metadata.get("mission_id"), mission.metadata.get("schema_version"))
            == (request.mission_id, request.mission_id, SCHEMA_VERSION),
            "mission has a foreign canonical identity",
        )
        task = await self._board.get(request.task_id)
        _need(task is not None, f"task {request.task_id!r} was not found")
        _need(task.id == request.task_id, "TaskBoard returned a foreign task identity")
        _need(task.metadata.get("mission_id") == request.mission_id, "task does not belong to the requested mission")
        _need(task.metadata.get("schema_version") == SCHEMA_VERSION, "task has a foreign Mission Control schema")
        payload = _task_payload(request, task)
        encoded = _canonical_json(payload, "canonical dispatch payload")
        gate = classify_action(_gate_input(request, task, payload))
        _need(
            not gate.never_auto_hit and gate.action_class not in {ActionClass.IRREVERSIBLE, ActionClass.OPERATOR_ONLY},
            "canonical dispatch payload is not eligible for autonomous execution",
        )
        subject_parts = [
            "mission_dispatch_subject",
            request.mission_id,
            request.task_id,
            request.dispatch_key,
        ]
        if request.attempt_generation is not None:
            subject_parts.append(str(request.attempt_generation))
        subject_id = stable_id(*subject_parts)
        canonical = _governed_request(request, payload, encoded, gate.risk.value)
        subject_digest = _digest(payload, "canonical dispatch payload")
        if verified is not None:
            canonical = _governed_request(
                request, payload, encoded, gate.risk.value,
                self._workspace_evidence(canonical, verified))
        governed_json = _canonical_json(canonical.model_dump(mode="json"), "canonical governed request")
        if governed_request is not None:
            _need(type(governed_request) is GovernedWorkRequest, "governed_request has an invalid evidence type")
            try:
                supplied = governed_request.model_dump(mode="json")
            except Exception as exc:
                raise MissionControlError("governed request is not serializable") from exc
            _need(
                _canonical_json(supplied, "governed request") == governed_json,
                "governed work request does not bind the canonical task",
            )
        request_digest = _digest(
            {
                "schema_version": DISPATCH_SCHEMA_VERSION,
                "request": asdict(request),
                "governed_request": json.loads(governed_json),
                "subject_digest": subject_digest,
            },
            "governed dispatch request",
        )
        return _DispatchBinding(subject_id, subject_digest, request_digest, governed_json)
    def _evaluate(self, binding: _DispatchBinding, *,
                  require_allow: bool = False) -> GovernedWorkAdmission:
        request = GovernedWorkRequest.model_validate_json(binding.governed_json)
        try:
            evaluated = self._admission_evaluator(request)
        except MissionControlError:
            raise
        except Exception as exc:
            raise MissionControlError("governance admission evaluation failed") from exc
        _need(
            _canonical_json(request.model_dump(mode="json"), "governed request") == binding.governed_json,
            "governed request changed during evaluation",
        )
        _need(type(evaluated) is GovernedWorkAdmission, "admission evaluator returned an invalid type")
        _need(evaluated.request_id == request.request_id, "admission evaluator changed request identity")
        _need(evaluated.decision in {"allow", "review"},
              f"governance admission blocked dispatch: {evaluated.decision}")
        if require_allow:
            _need(evaluated.decision == "allow",
                  f"final governance admission did not allow dispatch: {evaluated.decision}")
        return evaluated
    @staticmethod
    def _admission_from(binding: _DispatchBinding, request: MissionDispatchRequest,
                        evaluated: GovernedWorkAdmission) -> GovernanceAdmission:
        return GovernanceAdmission(binding.subject_id, binding.subject_digest,
                                   request.claimed_principal, binding.request_digest,
                                   tuple(evaluated.reasons), tuple(evaluated.required_receipts),
                                   _copy(evaluated.reduced_authority, "governance reduced authority"),
                                   evaluated.decision)
    @staticmethod
    def _require_request(request: MissionDispatchRequest) -> None:
        _need(type(request) is MissionDispatchRequest, "request has an invalid evidence type")
        mission_id = _exact_id(request.mission_id, "mission_id")
        task_id = _exact_id(request.task_id, "task_id")
        key = _exact_id(request.dispatch_key, "dispatch_key")
        _exact_id(request.claimed_principal, "claimed_principal")
        generation = request.attempt_generation
        _need(
            generation is None
            or (
                isinstance(generation, int)
                and not isinstance(generation, bool)
                and generation >= 0
            ),
            "attempt_generation must be absent or a nonnegative integer",
        )
        request_id = _exact_id(request.request_id, "request_id")
        identity_parts = ["mission_dispatch", mission_id, task_id, key]
        if generation is not None:
            identity_parts.append(str(generation))
        _need(
            request_id == stable_id(*identity_parts),
            "request_id is not the stable dispatch identity",
        )
    @staticmethod
    def _require_envelope(request: MissionDispatchRequest, authority: DispatchAuthorityEnvelope) -> None:
        _need(type(authority) is DispatchAuthorityEnvelope, "authority has an invalid evidence type")
        _lease_id(authority.authority_ref, "authority_ref")
        _exact_id(authority.authority_digest, "authority_digest")
        _need(
            (
                authority.claimed_principal,
                authority.mission_id,
                authority.task_id,
                authority.dispatch_key,
                authority.attempt_generation,
            )
            == (
                request.claimed_principal,
                request.mission_id,
                request.task_id,
                request.dispatch_key,
                request.attempt_generation,
            ),
            "authority envelope conflicts with dispatch identity",
        )
    @staticmethod
    def _require_verified(request: MissionDispatchRequest,
                          authority: DispatchAuthorityEnvelope,
                          verified: VerifiedDispatchAuthority) -> None:
        _exact_id(verified.authenticated_principal, "authenticated_principal")
        _need(
            (verified.authenticated_principal, verified.mission_id, verified.task_id,
             verified.dispatch_key, verified.authority_ref, verified.authority_digest)
            == (request.claimed_principal, request.mission_id, request.task_id,
                request.dispatch_key, authority.authority_ref, authority.authority_digest),
            "verified dispatch authority conflicts with the presented envelope",
        )
        _need(
            verified.attempt_generation
            == authority.attempt_generation
            == request.attempt_generation,
            "verified dispatch authority has a foreign attempt generation",
        )
    @staticmethod
    def _workspace_evidence(request: GovernedWorkRequest, verified: VerifiedDispatchAuthority) -> dict[str, Any]:
        _need(request.work_kind in {WorkKind.CODE_WRITE, WorkKind.LONG_RUNNING, WorkKind.SELF_EVOLUTION, WorkKind.PROMOTION},
              "workspace authority cannot lower the canonical work kind")
        lease = verified.execution_lease
        actions = lease.get("allowed_actions")
        _need(isinstance(actions, Sequence) and not isinstance(actions, (str, bytes))
              and LEASE_WORKSPACE_ACTION in actions and LEASE_WORKSPACE_ACTION not in lease.get("forbidden_actions", ()),
              "authenticated authority does not grant workspace access")
        paths = _scope_paths(lease.get("allowed_paths"), "authenticated workspace paths")
        _need(bool(request.allowed_files) and paths == request.allowed_files,
              "authenticated workspace scope conflicts with canonical allowed files")
        _need(not any(_paths_overlap(path, blocked) for path in paths for blocked in request.forbidden_files),
              "authenticated workspace scope includes a forbidden file")
        scope = {"authority_ref": verified.authority_ref,
                 "authority_digest": verified.authority_digest,
                 "allowed_paths": paths}
        scope["scope_digest"] = _digest({**scope, "work_kind": request.work_kind.value}, "workspace authority scope")
        return scope
    @staticmethod
    def _require_lease(request: MissionDispatchRequest, verified: VerifiedDispatchAuthority) -> None:
        lease = verified.execution_lease
        _need(isinstance(lease, Mapping), "verified execution lease must be a mapping")
        _scope_paths(lease.get("allowed_paths"), "authenticated workspace paths")
        _need(_lease_id(lease.get("lease_id"), "execution lease_id") == verified.authority_ref, "verified execution lease reference conflicts")
        _need(lease.get("content_hash") == verified.authority_digest, "verified execution lease digest conflicts")
        _need(lease.get("issued_to") == request.claimed_principal, "verified execution lease principal conflicts")
        _need(lease.get("task_id") == request.task_id, "verified execution lease task conflicts")
        _need(lease.get("correlation_id") == request.request_id, "verified execution lease correlation conflicts")
        _need(
            lease.get("attempt_generation") == request.attempt_generation,
            "verified execution lease attempt generation conflicts",
        )
        allowed, forbidden = lease.get("allowed_actions"), lease.get("forbidden_actions")
        _need(not isinstance(allowed, (str, bytes)) and isinstance(allowed, Sequence), "verified execution lease actions are invalid")
        _need(not isinstance(forbidden, (str, bytes)) and isinstance(forbidden, Sequence), "verified execution lease prohibitions are invalid")
        _need(LEASE_DISPATCH_ACTION in allowed and LEASE_DISPATCH_ACTION not in forbidden, "verified execution lease does not allow dispatch")
        revoked = verified.revoked_lease_ids
        _need(not isinstance(revoked, (str, bytes)) and isinstance(revoked, Sequence), "verified lease revocations are invalid")
        canonical_revoked = tuple(_lease_id(item, "revoked lease_id") for item in revoked)
        _need(len(set(canonical_revoked)) == len(canonical_revoked), "verified lease revocations contain duplicates")
        try:
            validation = validate_execution_lease(
                lease,
                agent_uid=request.claimed_principal,
                task_id=request.task_id,
                requested_actions=[LEASE_DISPATCH_ACTION],
                revoked_lease_ids=canonical_revoked,
            )
        except (TypeError, ValueError) as exc:
            raise MissionControlError("verified execution lease is malformed") from exc
        _need(
            validation.valid and validation.lease_id == verified.authority_ref,
            "verified execution lease is invalid: " + "; ".join(validation.errors),
        )
        issued_at = parse_time(lease.get("issued_at"))
        _need(issued_at is not None and issued_at <= utc_now(), "verified execution lease is not yet valid")
        if lease.get("campaign_authority_schema") == CAMPAIGN_LEASE_SCHEMA_VERSION:
            _need(
                lease.get("effect_mode") == "read_only",
                "write-capable campaign execution lacks an enforced workspace sandbox",
            )
            _need(
                list(allowed) == [LEASE_DISPATCH_ACTION, LEASE_WORKSPACE_ACTION],
                "campaign execution lease actions are not exact",
            )
            budget = lease.get("budget")
            _need(isinstance(budget, Mapping), "campaign execution lease budget is invalid")
            max_usd = budget.get("max_usd")
            _need(
                not isinstance(max_usd, bool)
                and isinstance(max_usd, (int, float))
                and max_usd == 0,
                "campaign execution lease must be zero-dollar",
            )
            _need(
                lease.get("campaign_id") == request.mission_id
                and lease.get("mission_id") == request.mission_id,
                "campaign execution lease identity is foreign",
            )
            campaign_end = parse_time(lease.get("campaign_end"))
            expires_at = parse_time(lease.get("expires_at"))
            _need(
                campaign_end is not None
                and expires_at is not None
                and expires_at <= campaign_end,
                "campaign execution lease exceeds the campaign end",
            )
