"""RUDRA v0 strict mission and result contracts.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md section 7.

Admission is the only authority boundary: strict YAML, strict frozen
Pydantic v2 models, one canonical digest. Only ``goal_gate.promote`` can
construct ``ReproducedCompletion`` (spec section 9).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, ClassVar

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

SCHEMA_VERSION = "rudra.mission.v0"
MISSION_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_hex64(value: str, field: str) -> str:
    if not HEX64_RE.match(value):
        raise ValueError(f"{field} must be 64 lowercase hex")
    return value


class AdmissionReject(StrEnum):
    """Pre-attempt admission rejections (spec section 12)."""

    ALREADY_SATISFIED = "ALREADY_SATISFIED"
    BLOCKED_CONTAINMENT = "BLOCKED_CONTAINMENT"
    BLOCKED_ENVIRONMENT = "BLOCKED_ENVIRONMENT"
    REJECT_INVALID = "REJECT_INVALID"


class Terminal(StrEnum):
    """Lifecycle terminal values; the complete vocabulary (spec section 12)."""

    COMPLETE_REPRODUCED = "COMPLETE_REPRODUCED"
    FAILED_BUDGET = "FAILED_BUDGET"
    FAILED_INVARIANT = "FAILED_INVARIANT"
    BLOCKED_ENVIRONMENT = "BLOCKED_ENVIRONMENT"
    CANCELLED_OPERATOR = "CANCELLED_OPERATOR"


class DerivedStatus(StrEnum):
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class AdmissionError(ValueError):
    """Mission admission failure carrying a stable rejection code."""

    def __init__(self, code: AdmissionReject, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


# --- Strict YAML parsing (spec section 7) -----------------------------------


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader hardened: no aliases/anchors, merge keys, or duplicate keys."""

    def fetch_alias(self) -> Any:  # pragma: no cover - error path shape
        raise yaml.YAMLError("RUDRA admission rejects YAML aliases/anchors")

    def fetch_anchor(self) -> Any:  # pragma: no cover - error path shape
        raise yaml.YAMLError("RUDRA admission rejects YAML anchors")

    def flatten_mapping(self, node: yaml.MappingNode) -> None:
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                raise yaml.YAMLError("RUDRA admission rejects YAML merge keys")
        # No merge keys survive, so no flattening is ever required.

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=True)
            if key in seen:
                raise yaml.YAMLError(f"RUDRA admission rejects duplicate key: {key!r}")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _reject_non_finite(node: Any) -> None:
    if isinstance(node, float) and not math.isfinite(node):
        raise AdmissionError(AdmissionReject.REJECT_INVALID, "non-finite number in contract")
    if isinstance(node, dict):
        for k, v in node.items():
            _reject_non_finite(k)
            _reject_non_finite(v)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _reject_non_finite(item)


def load_mission_yaml(text: str) -> dict[str, Any]:
    """Parse a mission document strictly; any laxness is REJECT_INVALID."""
    try:
        data = yaml.load(text, Loader=_StrictLoader)  # noqa: S506 - hardened loader
    except yaml.YAMLError as exc:
        raise AdmissionError(AdmissionReject.REJECT_INVALID, f"YAML parse: {exc}") from exc
    if not isinstance(data, dict):
        raise AdmissionError(AdmissionReject.REJECT_INVALID, "mission document must be a mapping")
    _reject_non_finite(data)
    return data


# --- Path policy (spec section 7) -------------------------------------------

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def validate_rel_path(value: str) -> str:
    """Reject absolute paths, traversal, backslashes, control chars, .git/**."""
    if not isinstance(value, str) or not value:
        raise AdmissionError(AdmissionReject.REJECT_INVALID, "empty path")
    if _CONTROL_RE.search(value) or "\\" in value:
        raise AdmissionError(AdmissionReject.REJECT_INVALID, f"bad characters in path {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise AdmissionError(AdmissionReject.REJECT_INVALID, f"unsafe path {value!r}")
    if pure.parts and pure.parts[0] == ".git":
        raise AdmissionError(AdmissionReject.REJECT_INVALID, f".git path {value!r}")
    return value


def _check_paths(values: list[str]) -> list[str]:
    return [validate_rel_path(v) for v in values]


# --- Mission contract models (strict, frozen, extra=forbid) -----------------


class _Strict(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        strict=True, extra="forbid", frozen=True
    )


class RepositorySpec(_Strict):
    canonical_remote: str
    base_sha: str

    @field_validator("base_sha")
    @classmethod
    def _hex40(cls, v: str) -> str:
        if not HEX40_RE.match(v):
            raise ValueError("base_sha must be exact 40 lowercase hex")
        return v


class ScopeSpec(_Strict):
    required_changed_paths: list[str]
    allowed_changed_paths: list[str]
    forbidden_changed_paths: list[str]
    forbidden_diff_literals: list[str] = []
    reject_symlinks: bool = True
    max_changed_files: int
    max_diff_bytes: int

    @field_validator(
        "required_changed_paths", "allowed_changed_paths", "forbidden_changed_paths"
    )
    @classmethod
    def _paths(cls, v: list[str]) -> list[str]:
        return _check_paths(v)

    @model_validator(mode="after")
    def _consistency(self) -> "ScopeSpec":
        if self.max_changed_files < 1 or self.max_diff_bytes < 1:
            raise ValueError("scope limits must be positive")
        if not self.allowed_changed_paths:
            raise ValueError("allowed_changed_paths must not be empty")
        return self


class LockfileBinding(_Strict):
    path: str
    sha256: str

    @field_validator("path")
    @classmethod
    def _rel(cls, v: str) -> str:
        return validate_rel_path(v)

    @field_validator("sha256")
    @classmethod
    def _hex64(cls, v: str) -> str:
        return _require_hex64(v, "sha256")


class EnvironmentManifest(_Strict):
    kind: str
    covers: list[str]
    sha256: str


class ExecutableBinding(_Strict):
    path: str
    sha256: str
    version: str

    @model_validator(mode="after")
    def _absolute(self) -> "ExecutableBinding":
        if not self.path.startswith("/"):
            raise ValueError("executable path must be absolute")
        _require_hex64(self.sha256, "executable sha256")
        return self


class ToolchainSpec(_Strict):
    lockfile: LockfileBinding
    environment_manifest: EnvironmentManifest
    executables: dict[str, ExecutableBinding]
    require_first_party_imports_from_workcell: bool = True
    allowed_pytest_plugins: list[str] = []


class PytestJunitAssertion(_Strict):
    kind: str
    artifact: str
    required_testcases: list[str]
    require_counts: dict[str, int]

    @model_validator(mode="after")
    def _shape(self) -> "PytestJunitAssertion":
        if self.kind != "pytest_junit":
            raise ValueError(f"unsupported structured_result kind {self.kind!r}")
        if not self.required_testcases:
            raise ValueError("required_testcases must not be empty")
        return self


class VerifierExpect(_Strict):
    exit_code: int = 0
    stdout_must_match: list[str] = []
    structured_result: PytestJunitAssertion | None = None


class VerifierCommand(_Strict):
    id: str
    argv: list[str]
    timeout_seconds: int
    expect: VerifierExpect = VerifierExpect()

    @model_validator(mode="after")
    def _argv_shape(self) -> "VerifierCommand":
        if not self.argv:
            raise ValueError(f"verifier {self.id!r} has empty argv")
        if any(not isinstance(a, str) or not a for a in self.argv):
            raise ValueError(f"verifier {self.id!r} argv entries must be non-empty strings")
        if self.timeout_seconds < 1:
            raise ValueError(f"verifier {self.id!r} timeout must be positive")
        if not MISSION_ID_RE.match(self.id):
            raise ValueError(f"verifier id {self.id!r} must match {MISSION_ID_RE.pattern}")
        return self


class AcceptanceSpec(_Strict):
    cwd: str
    commands: list[VerifierCommand]
    environment: dict[str, str] = {}

    @model_validator(mode="after")
    def _nonempty(self) -> "AcceptanceSpec":
        if not self.commands:
            raise ValueError("acceptance.commands must not be empty")
        validate_rel_path(self.cwd)
        return self


class ExecutorSpec(_Strict):
    driver: str
    binary: ExecutableBinding
    protocol_schema_sha256: str
    model: str
    model_provider: str
    reasoning_effort: str
    service_tier: str

    @model_validator(mode="after")
    def _pinned(self) -> "ExecutorSpec":
        _require_hex64(self.protocol_schema_sha256, "protocol_schema_sha256")
        return self


class ContainmentSpec(_Strict):
    risk_class: str
    sandbox: str
    writable_roots: list[str]
    provider_egress: str
    tool_network_access: bool
    approval_policy: str
    allow_mcp: bool
    allow_plugins: bool
    allow_external_effects: bool
    allow_dependency_install: bool

    @model_validator(mode="after")
    def _trusted_operator_only(self) -> "ContainmentSpec":
        if self.risk_class != "trusted_operator_coding":
            raise ValueError(f"risk_class {self.risk_class!r} is BLOCKED_CONTAINMENT")
        if self.sandbox != "workspace-write":
            raise ValueError("sandbox must be workspace-write: BLOCKED_CONTAINMENT")
        if self.tool_network_access:
            raise ValueError("tool network access is BLOCKED_CONTAINMENT")
        if self.approval_policy != "never":
            raise ValueError("approval_policy must be never: BLOCKED_CONTAINMENT")
        if self.allow_mcp or self.allow_plugins or self.allow_external_effects:
            raise ValueError("mcp/plugins/external effects are BLOCKED_CONTAINMENT")
        if self.allow_dependency_install:
            raise ValueError("dependency installation is BLOCKED_CONTAINMENT")
        if self.writable_roots != ["WORKCELL_ONLY"]:
            raise ValueError("writable_roots must be exactly [WORKCELL_ONLY]")
        return self


class BudgetSpec(_Strict):
    max_turns: int
    max_total_tokens: int
    max_tokens_per_turn: int
    max_wall_seconds: int
    max_turn_seconds: int
    max_verifier_seconds: int
    max_cpu_seconds: int
    max_memory_bytes: int
    max_processes: int
    max_disk_bytes: int
    max_captured_output_bytes: int
    max_context_resets: int
    max_consecutive_no_delta_turns: int

    @model_validator(mode="after")
    def _consistency(self) -> "BudgetSpec":
        for name, value in self:
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"budget {name} must be a positive integer")
        if self.max_tokens_per_turn > self.max_total_tokens:
            raise ValueError("max_tokens_per_turn exceeds max_total_tokens")
        if self.max_turn_seconds > self.max_wall_seconds:
            raise ValueError("max_turn_seconds exceeds max_wall_seconds")
        return self


class RecoverySpec(_Strict):
    resume_policy: str
    resume_failure: str
    max_fresh_thread_handoffs: int
    unresolved_turn_token_charge: str
    rpc_retry_policy: dict[str, Any]


class ResultSpec(_Strict):
    require_baseline_red: bool = True
    require_nonempty_diff: bool = True
    require_local_candidate_commit: bool = True
    require_final_clean_worktree: bool = True
    allow_push: bool = False
    allow_merge: bool = False

    @model_validator(mode="after")
    def _no_external_effects(self) -> "ResultSpec":
        if self.allow_push or self.allow_merge:
            raise ValueError("push/merge grants ambient authority; forbidden")
        return self


_HOSTILE_TOKENS = (
    "exploit", "payload", "exfiltrat", "credential theft", "privilege escalation",
    "c2 server", "malware", "ransomware",
)


class RudraMissionContract(_Strict):
    """The immutable admitted mission. Digest binds every group."""

    schema_version: str
    mission_id: str
    objective: str
    repository: RepositorySpec
    scope: ScopeSpec
    toolchain: ToolchainSpec
    acceptance: AcceptanceSpec
    executor: ExecutorSpec
    containment: ContainmentSpec
    budgets: BudgetSpec
    recovery: RecoverySpec
    result: ResultSpec

    @model_validator(mode="after")
    def _root_policy(self) -> "RudraMissionContract":
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        if not MISSION_ID_RE.match(self.mission_id):
            raise ValueError(f"mission_id must match {MISSION_ID_RE.pattern}")
        lowered = self.objective.lower()
        for token in _HOSTILE_TOKENS:
            if token in lowered:
                raise ValueError(f"objective contains hostile token {token!r}")
        return self

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("ascii")).hexdigest()


def parse_mission(text: str) -> RudraMissionContract:
    """Strict YAML -> strict model. All rejection is AdmissionError."""
    data = load_mission_yaml(text)
    try:
        return RudraMissionContract.model_validate(data)
    except ValueError as exc:
        code = (
            AdmissionReject.BLOCKED_CONTAINMENT
            if "BLOCKED_CONTAINMENT" in str(exc)
            else AdmissionReject.REJECT_INVALID
        )
        raise AdmissionError(code, str(exc)) from exc


# --- Frozen result contracts shared across module boundaries (spec section 7,
# interface freeze) live in ``result_contracts`` to keep this module inside
# the 500-line budget. The public import path stays ``rudra.contracts``.

from dharma_swarm.rudra.result_contracts import (  # noqa: E402
    GateResult as GateResult,
    GoalGatePassed as GoalGatePassed,
    ProcessHandle as ProcessHandle,
    ReportedCompletion as ReportedCompletion,
    ReproducedCompletion as ReproducedCompletion,
    TurnObservation as TurnObservation,
    VerifierReceipt as VerifierReceipt,
    _GATE_TOKEN as _GATE_TOKEN,
    derive_attempt_key as derive_attempt_key,
    derive_mission_key as derive_mission_key,
    sha256_json as sha256_json,
)
