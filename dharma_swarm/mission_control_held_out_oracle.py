"""Strict evidence collection and deterministic held-out G10 evaluation.

Candidate prose never enters the evidence bundle.  The frozen evaluator sees
only its hash plus eight independently custodied semantic records.  Missing
records produce a durable ``BLOCKED`` verdict; malformed custody or lineage
fails before evaluator execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from dharma_swarm.mission_control_bootstrap import BootstrapResult
from dharma_swarm.mission_control_contract import clean_identifier, stable_id, utc_now
from dharma_swarm.mission_control_evidence import (
    VERIFIER_RESULT_RECEIPT_TYPE,
    IndependentAcceptance,
    candidate_output_digest,
)
from dharma_swarm.mission_control_execution import OwnerExecutionObservation
from dharma_swarm.mission_control_oracle_custody import (
    HeldOutOracleError,
    OracleRunLock,
    list_private_directory,
    private_directory,
    read_exact,
    write_exact,
)
from dharma_swarm.mission_control_oracle_launcher import (
    OracleLaunchRequest,
    OracleLaunchTerminal,
    OracleSandboxLauncher,
)
from dharma_swarm.models import Task, TaskStatus
from dharma_swarm.runtime_state import (
    ArtifactRecord,
    DelegationRun,
    RuntimeStateStore,
)
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard


HELD_OUT_MANIFEST_SCHEMA = "dharma.sadhana.held_out_oracle_manifest.v1"
HELD_OUT_INPUT_SCHEMA = "dharma.sadhana.held_out_oracle_input.v1"
HELD_OUT_VERDICT_SCHEMA = "dharma.sadhana.held_out_oracle_verdict.v1"
G10_BUNDLE_SCHEMA = "dharma.sadhana.g10_evidence_bundle.v1"
G10_ENTRY_SCHEMA = "dharma.sadhana.g10_evidence_entry.v1"
G10_GOAL_ID = "G10_SAFETY_TCB"
G10_REQUIRED_EVIDENCE_IDS = (
    "authority_binding",
    "contract_binding",
    "effect_audit",
    "generation_recovery_tests",
    "leader_fencing_tests",
    "oracle_sandbox",
    "pause_stop_tests",
    "secret_boundary_scan",
)
G10_REQUIRED_PREDICATE_IDS = (
    "P01_AUTHORITY_BINDING",
    "P02_CONTRACT_BINDING",
    "P03_EFFECT_AUDIT",
    "P04_GENERATION_RECOVERY",
    "P05_LEADER_FENCING",
    "P06_ORACLE_SANDBOX",
    "P07_PAUSE_STOP",
    "P08_SECRET_BOUNDARY",
)
G10_EVIDENCE_DIRECTORY = "g10-evidence"
ORACLE_VERSION = "v1"
ORACLE_TIMEOUT_SECONDS = 30.0

_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RAW_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE_URI_RE = re.compile(r"(?:runtime|repo|campaign|test)://[^\x00-\x20]{1,512}\Z")
_AUTHORITIES = frozenset(
    {
        "accepted_repo_test",
        "canonical_runtime",
        "operator_bound_contract",
        "root_custody_audit",
    }
)
_RECORD_KINDS = frozenset(
    {"artifact_record", "audit_receipt", "runtime_receipt", "test_receipt"}
)
_ENTRY_KEYS = frozenset(
    {"schema_version", "evidence_id", "record_kind", "record_sha256", "record", "custody"}
)
_CUSTODY_KEYS = frozenset({"source_uri", "observed_at", "authority", "immutable"})


class HeldOutOracleIndeterminate(HeldOutOracleError):
    """An external request may exist, so the exact attempt must be polled again."""


@dataclass(frozen=True, slots=True)
class HeldOutOracleManifest:
    campaign_id: str
    mission_id: str
    goal_id: str
    task_id: str
    task_creation_hash: str
    evaluator_path: Path
    evaluator_sha256: str
    policy_path: Path
    policy_sha256: str
    required_evidence_ids: tuple[str, ...]
    oracle_version: str
    manifest_digest: str
    manifest_path: Path

    @property
    def evidence_directory(self) -> Path:
        return self.manifest_path.parent / G10_EVIDENCE_DIRECTORY


@dataclass(frozen=True, slots=True)
class G10EvidenceBundle:
    payload: dict[str, Any]
    digest: str
    missing_evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HeldOutOracleOutcome:
    status: str
    run_id: str
    verdict: dict[str, Any]
    acceptance: IndependentAcceptance | None
    replayed: bool


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise HeldOutOracleError(message)


def _canonical_bytes(value: Any, *, newline: bool = True) -> bytes:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HeldOutOracleError("held-out oracle JSON is not canonicalizable") from exc
    return encoded + (b"\n" if newline else b"")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def held_out_manifest_digest(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("manifest_digest", None)
    return "sha256:" + hashlib.sha256(_canonical_bytes(payload, newline=False)).hexdigest()


def _sha256(value: Any, label: str) -> str:
    _need(isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None,
          f"{label} must be sha256")
    return value


def _identifier(value: Any, label: str) -> str:
    _need(isinstance(value, str), f"{label} must be text")
    _need(clean_identifier(value, label) == value, f"{label} must be canonical")
    return value


def _timestamp(value: Any, label: str) -> datetime:
    _need(isinstance(value, str), f"{label} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HeldOutOracleError(f"{label} is invalid") from exc
    _need(parsed.tzinfo is not None, f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def load_held_out_oracle_manifest(
    path: Path | str,
    *,
    expected_digest: str = "",
) -> HeldOutOracleManifest:
    manifest_path = Path(path).expanduser().absolute()
    _, payload = read_exact(
        manifest_path,
        label="held-out oracle manifest",
        canonical_json=True,
    )
    _need(type(payload) is dict, "held-out oracle manifest must be an object")
    expected = {
        "schema_version",
        "campaign_id",
        "mission_id",
        "goal_id",
        "task_id",
        "task_creation_hash",
        "evaluator_path",
        "evaluator_sha256",
        "policy_path",
        "policy_sha256",
        "required_evidence_ids",
        "oracle_version",
        "manifest_digest",
    }
    _need(set(payload) == expected, "held-out oracle manifest fields are not exact")
    _need(payload["schema_version"] == HELD_OUT_MANIFEST_SCHEMA,
          "held-out oracle manifest schema is foreign")
    campaign_id = _identifier(payload["campaign_id"], "campaign_id")
    mission_id = _identifier(payload["mission_id"], "mission_id")
    _need(campaign_id == mission_id, "held-out oracle mission is foreign")
    _need(payload["goal_id"] == G10_GOAL_ID, "held-out oracle goal is foreign")
    task_id = _identifier(payload["task_id"], "task_id")
    creation_hash = payload["task_creation_hash"]
    _need(
        isinstance(creation_hash, str) and _RAW_SHA256_RE.fullmatch(creation_hash) is not None,
        "held-out oracle task creation hash is invalid",
    )
    required = payload["required_evidence_ids"]
    _need(required == list(G10_REQUIRED_EVIDENCE_IDS),
          "held-out oracle required evidence set is foreign")
    _need(payload["oracle_version"] == ORACLE_VERSION,
          "held-out oracle version is foreign")
    digest = _sha256(payload["manifest_digest"], "oracle manifest digest")
    _need(digest == held_out_manifest_digest(payload),
          "held-out oracle manifest digest conflicts")
    if expected_digest:
        _need(digest == expected_digest, "held-out oracle manifest is not precommitted")
    evaluator_path = Path(str(payload["evaluator_path"])).expanduser()
    policy_path = Path(str(payload["policy_path"])).expanduser()
    evaluator_sha = _sha256(payload["evaluator_sha256"], "evaluator digest")
    policy_sha = _sha256(payload["policy_sha256"], "policy digest")
    _need(
        evaluator_path.is_absolute() and policy_path.is_absolute(),
        "held-out evaluator or policy path is not absolute",
    )
    return HeldOutOracleManifest(
        campaign_id=campaign_id,
        mission_id=mission_id,
        goal_id=G10_GOAL_ID,
        task_id=task_id,
        task_creation_hash=creation_hash,
        evaluator_path=evaluator_path,
        evaluator_sha256=evaluator_sha,
        policy_path=policy_path,
        policy_sha256=policy_sha,
        required_evidence_ids=G10_REQUIRED_EVIDENCE_IDS,
        oracle_version=ORACLE_VERSION,
        manifest_digest=digest,
        manifest_path=manifest_path,
    )


async def render_held_out_oracle_manifest(
    bootstrap: BootstrapResult,
    board: TaskBoard,
    *,
    evaluator_path: Path | str,
    evaluator_sha256: str,
    policy_path: Path | str,
    policy_sha256: str,
) -> bytes:
    """Bind frozen oracle hashes to the exact post-bootstrap G10 task."""
    task_ids = dict(bootstrap.goal_task_map)
    goal_digests = dict(bootstrap.goal_contract_digests)
    _need(
        len(task_ids) == len(bootstrap.goal_task_map)
        and len(goal_digests) == len(bootstrap.goal_contract_digests)
        and set(task_ids) == set(goal_digests) == set(bootstrap.dependency_order)
        and G10_GOAL_ID in task_ids,
        "bootstrap result cannot identify one exact G10 task",
    )
    task = await board.get(task_ids[G10_GOAL_ID])
    _need(task is not None, "bootstrapped G10 task is absent")
    creation_hash = task.metadata.get("mission_task_creation_hash")
    _need(
        task.metadata.get("mission_id") == bootstrap.mission_id
        and task.metadata.get("campaign_id") == bootstrap.mission_id
        and task.metadata.get("goal_id") == G10_GOAL_ID
        and task.metadata.get("goal_contract_sha256") == goal_digests[G10_GOAL_ID]
        and isinstance(creation_hash, str)
        and _RAW_SHA256_RE.fullmatch(creation_hash) is not None,
        "bootstrapped G10 task provenance conflicts",
    )
    evaluator = Path(evaluator_path).expanduser()
    policy = Path(policy_path).expanduser()
    _need(
        evaluator.is_absolute()
        and policy.is_absolute()
        and ".." not in evaluator.parts
        and ".." not in policy.parts,
        "held-out evaluator and policy paths must be absolute lexical paths",
    )
    payload: dict[str, Any] = {
        "schema_version": HELD_OUT_MANIFEST_SCHEMA,
        "campaign_id": bootstrap.mission_id,
        "mission_id": bootstrap.mission_id,
        "goal_id": G10_GOAL_ID,
        "task_id": task.id,
        "task_creation_hash": creation_hash,
        "evaluator_path": os.fspath(evaluator),
        "evaluator_sha256": _sha256(evaluator_sha256, "evaluator digest"),
        "policy_path": os.fspath(policy),
        "policy_sha256": _sha256(policy_sha256, "policy digest"),
        "required_evidence_ids": list(G10_REQUIRED_EVIDENCE_IDS),
        "oracle_version": ORACLE_VERSION,
    }
    payload["manifest_digest"] = held_out_manifest_digest(payload)
    return _canonical_bytes(payload)


def _validate_entry(value: Any, evidence_id: str) -> dict[str, Any]:
    _need(type(value) is dict and set(value) == _ENTRY_KEYS,
          f"G10 evidence {evidence_id} fields are not exact")
    _need(value["schema_version"] == G10_ENTRY_SCHEMA,
          f"G10 evidence {evidence_id} schema is foreign")
    _need(value["evidence_id"] == evidence_id,
          f"G10 evidence {evidence_id} identity is foreign")
    _need(value["record_kind"] in _RECORD_KINDS,
          f"G10 evidence {evidence_id} kind is foreign")
    _sha256(value["record_sha256"], f"G10 evidence {evidence_id} digest")
    _need(type(value["record"]) is dict,
          f"G10 evidence {evidence_id} record is not an object")
    _need(_digest(value["record"]) == value["record_sha256"],
          f"G10 evidence {evidence_id} record digest conflicts")
    custody = value["custody"]
    _need(type(custody) is dict and set(custody) == _CUSTODY_KEYS,
          f"G10 evidence {evidence_id} custody is not exact")
    _need(
        isinstance(custody["source_uri"], str)
        and _SOURCE_URI_RE.fullmatch(custody["source_uri"]) is not None,
        f"G10 evidence {evidence_id} source URI is invalid",
    )
    _timestamp(custody["observed_at"], f"G10 evidence {evidence_id} observed_at")
    _need(custody["authority"] in _AUTHORITIES and custody["immutable"] is True,
          f"G10 evidence {evidence_id} authority is invalid")
    return value


def collect_g10_evidence(
    manifest: HeldOutOracleManifest,
    *,
    producer_run_id: str,
    producer_completed_at: datetime,
) -> G10EvidenceBundle:
    _identifier(producer_run_id, "producer_run_id")
    _need(producer_completed_at.tzinfo is not None,
          "producer completion must be timezone-aware")
    directory = manifest.evidence_directory
    if directory.exists():
        names = list_private_directory(directory, "G10 evidence directory")
        allowed = {f"{item}.json" for item in manifest.required_evidence_ids}
        _need(set(names).issubset(allowed), "G10 evidence directory has foreign entries")
    entries: dict[str, Any] = {}
    observed = [producer_completed_at.astimezone(timezone.utc)]
    missing: list[str] = []
    for evidence_id in manifest.required_evidence_ids:
        entry_path = directory / f"{evidence_id}.json"
        if not entry_path.exists():
            missing.append(evidence_id)
            continue
        _, raw = read_exact(
            entry_path.absolute(),
            label=f"G10 evidence {evidence_id}",
            canonical_json=True,
        )
        entry = _validate_entry(raw, evidence_id)
        entries[evidence_id] = entry
        observed.append(_timestamp(entry["custody"]["observed_at"], "evidence observed_at"))
    bundle = {
        "schema_version": G10_BUNDLE_SCHEMA,
        "campaign_id": manifest.campaign_id,
        "mission_id": manifest.mission_id,
        "goal_id": manifest.goal_id,
        "task_id": manifest.task_id,
        "producer_run_id": producer_run_id,
        "collected_at": max(observed).isoformat(),
        "entries": entries,
    }
    return G10EvidenceBundle(
        payload=bundle,
        digest=_digest(bundle),
        missing_evidence_ids=tuple(missing),
    )


def _validate_verdict(
    value: Any,
    *,
    manifest_digest: str,
    candidate_digest: str,
    bundle_digest: str,
) -> dict[str, Any]:
    expected = {
        "schema_version",
        "manifest_digest",
        "candidate_output_sha256",
        "evidence_bundle_sha256",
        "accepted",
        "verdict",
        "predicates",
    }
    _need(type(value) is dict and set(value) == expected,
          "held-out oracle verdict fields are not exact")
    _need(
        value["schema_version"] == HELD_OUT_VERDICT_SCHEMA
        and value["manifest_digest"] == manifest_digest
        and value["candidate_output_sha256"] == candidate_digest
        and value["evidence_bundle_sha256"] == bundle_digest,
        "held-out oracle verdict coordinates conflict",
    )
    verdict = value["verdict"]
    accepted = value["accepted"]
    _need(
        verdict in {"ACCEPT", "REJECT", "BLOCKED"}
        and type(accepted) is bool
        and accepted == (verdict == "ACCEPT"),
        "held-out oracle verdict decision conflicts",
    )
    predicates = value["predicates"]
    _need(type(predicates) is list and len(predicates) == len(G10_REQUIRED_EVIDENCE_IDS),
          "held-out oracle predicate results are incomplete")
    for expected_id, predicate in zip(G10_REQUIRED_PREDICATE_IDS, predicates, strict=True):
        _need(
            type(predicate) is dict
            and set(predicate) == {"id", "passed", "evidence_sha256", "detail_code"}
            and predicate["id"] == expected_id
            and type(predicate["passed"]) is bool
            and _SHA256_RE.fullmatch(str(predicate["evidence_sha256"])) is not None
            and isinstance(predicate["detail_code"], str)
            and bool(predicate["detail_code"]),
            "held-out oracle predicate result is malformed",
        )
        _need(
            (predicate["passed"] and predicate["detail_code"] == "PASS")
            or (not predicate["passed"] and predicate["detail_code"] != "PASS"),
            "held-out oracle predicate decision conflicts",
        )
    all_passed = all(item["passed"] for item in predicates)
    only_missing = not all_passed and all(
        item["passed"] or item["detail_code"] == "EVIDENCE_MISSING"
        for item in predicates
    )
    _need(
        (verdict == "ACCEPT" and all_passed)
        or (verdict == "BLOCKED" and only_missing)
        or (verdict == "REJECT" and not all_passed and not only_missing),
        "held-out oracle verdict does not match predicate results",
    )
    return value


def _oracle_identity(
    manifest: HeldOutOracleManifest,
    candidate: OwnerExecutionObservation,
    *,
    candidate_digest: str,
    bundle_digest: str,
    missing_evidence_ids: tuple[str, ...],
    attempt_number: int,
) -> ExecutionIdentity:
    agent_id = stable_id(
        "held_out_oracle_agent",
        manifest.campaign_id,
        manifest.manifest_digest,
    )
    run_id = stable_id(
        "held_out_oracle_run",
        manifest.campaign_id,
        manifest.task_id,
        candidate.ref.run_id,
        candidate_digest,
        bundle_digest,
        str(attempt_number),
    )
    return ExecutionIdentity.new(
        trace_id=stable_id("held_out_oracle_trace", run_id),
        correlation_id=f"mission_campaign:{manifest.mission_id}",
        task_id=manifest.task_id,
        run_id=run_id,
        claim_id=stable_id("held_out_oracle_claim", run_id),
        agent_id=agent_id,
        session_id=f"mission_verifier:{manifest.mission_id}",
        causation_id=candidate.ref.run_id,
        parent_run_id=candidate.ref.run_id,
        idempotency_key=stable_id("held_out_oracle_idempotency", run_id),
        metadata={
            "schema_version": HELD_OUT_VERDICT_SCHEMA,
            "mission_id": manifest.mission_id,
            "goal_id": manifest.goal_id,
            "manifest_digest": manifest.manifest_digest,
            "candidate_output_sha256": candidate_digest,
            "evidence_bundle_sha256": bundle_digest,
            "missing_evidence_ids": list(missing_evidence_ids),
            "oracle_version": manifest.oracle_version,
            "attempt_number": attempt_number,
        },
    )


def _acceptance(
    identity: ExecutionIdentity,
    candidate: OwnerExecutionObservation,
    manifest: HeldOutOracleManifest,
    verdict: dict[str, Any],
    *,
    observed_at: datetime,
    receipt_id: str,
    artifact_id: str,
) -> IndependentAcceptance | None:
    if verdict["verdict"] == "BLOCKED":
        return None
    return IndependentAcceptance.new(
        mission_id=manifest.mission_id,
        task_id=manifest.task_id,
        producer_run_id=candidate.ref.run_id,
        producer_agent_id=candidate.ref.agent_id,
        producer_model_family="",
        producer_output_digest=verdict["candidate_output_sha256"],
        verifier_run_id=identity.run_id,
        verifier_agent_id=identity.agent_id,
        verifier_model_family="deterministic-held-out",
        oracle_kind="deterministic_held_out",
        oracle_digest=manifest.manifest_digest,
        accepted=verdict["accepted"],
        observed_at=observed_at,
        rationale=f"Held-out deterministic oracle verdict {verdict['verdict']}.",
        evidence_receipt_ids=(receipt_id,),
        evidence_artifact_ids=(artifact_id,),
    )


async def _run_evaluator(
    manifest: HeldOutOracleManifest,
    *,
    launcher: OracleSandboxLauncher,
    identity: ExecutionIdentity,
    input_path: Path,
    input_sha256: str,
    sandbox_evidence_sha256: str,
    timeout_seconds: float,
) -> OracleLaunchTerminal:
    _need(
        isinstance(timeout_seconds, (int, float))
        and not isinstance(timeout_seconds, bool)
        and 0 < float(timeout_seconds) <= 300,
        "held-out oracle timeout is invalid",
    )
    request = OracleLaunchRequest(
            campaign_id=manifest.campaign_id,
            mission_id=manifest.mission_id,
            goal_id=manifest.goal_id,
            task_id=manifest.task_id,
            verifier_run_id=identity.run_id,
            idempotency_key=identity.idempotency_key,
            manifest_digest=manifest.manifest_digest,
            evaluator_path=manifest.evaluator_path,
            evaluator_sha256=manifest.evaluator_sha256,
            policy_path=manifest.policy_path,
            policy_sha256=manifest.policy_sha256,
            input_path=input_path,
            input_sha256=input_sha256,
            sandbox_evidence_sha256=sandbox_evidence_sha256,
        )
    try:
        request.validate()
    except ValueError as exc:
        raise HeldOutOracleError("held-out oracle launch request is invalid") from exc
    try:
        terminal = await launcher.launch(request)
    except Exception as exc:
        raise HeldOutOracleIndeterminate(
            "held-out oracle external request is indeterminate"
        ) from exc
    try:
        terminal.validate_for(request)
    except ValueError as exc:
        raise HeldOutOracleError("held-out oracle terminal is invalid") from exc
    _need(terminal.status == "completed", "held-out oracle worker failed")
    return terminal


async def _stored_outcome(
    runtime: RuntimeStateStore,
    manifest: HeldOutOracleManifest,
    candidate: OwnerExecutionObservation,
    identity: ExecutionIdentity,
    *,
    receipt_id: str,
    artifact_id: str,
) -> HeldOutOracleOutcome | None:
    run = await runtime.get_delegation_run(identity.run_id)
    if run is None:
        return None
    stored_identity = await runtime.get_execution_identity(identity.run_id)
    _need(stored_identity == identity, "stored held-out oracle identity conflicts")
    receipt = await runtime.get_runtime_receipt(receipt_id)
    artifact = await runtime.get_artifact(artifact_id)
    if receipt is None and artifact is None:
        if run.status.lower() == "failed":
            raise HeldOutOracleError("held-out oracle attempt is terminally failed")
        return None
    if receipt is None or artifact is None:
        _need(run.status.lower() == "running",
              "held-out oracle terminal evidence is partial")
        return None
    verdict = receipt.payload.get("verdict_payload")
    _need(type(verdict) is dict, "stored held-out oracle verdict is malformed")
    verdict = _validate_verdict(
        verdict,
        manifest_digest=manifest.manifest_digest,
        candidate_digest=candidate_output_digest(candidate.result),
        bundle_digest=str(identity.metadata["evidence_bundle_sha256"]),
    )
    checksum = _digest(verdict)
    expected = {
        "producer_output_digest": verdict["candidate_output_sha256"],
        "oracle_manifest_digest": manifest.manifest_digest,
        "accepted": verdict["accepted"],
        "oracle_evaluator": manifest.evaluator_sha256,
        "oracle_version": manifest.oracle_version,
        "oracle_terminal_digest": receipt.payload.get("oracle_terminal_digest"),
        "oracle_terminal_path": receipt.payload.get("oracle_terminal_path"),
    }
    _need(
        receipt.receipt_type == VERIFIER_RESULT_RECEIPT_TYPE
        and receipt.status == "completed"
        and all(receipt.payload.get(key) == value for key, value in expected.items())
        and artifact.artifact_kind == "mission_held_out_oracle_verdict"
        and artifact.checksum == checksum
        and artifact.payload_path == expected["oracle_terminal_path"]
        and _SHA256_RE.fullmatch(str(expected["oracle_terminal_digest"])) is not None
        and Path(str(expected["oracle_terminal_path"])).is_absolute()
        and all(artifact.metadata.get(key) == value for key, value in expected.items()),
        "stored held-out oracle evidence conflicts",
    )
    completed_at = receipt.created_at
    if run.status.lower() != "completed" or run.completed_at is None:
        _need(run.status.lower() == "running", "held-out oracle lifecycle is foreign")
        await runtime.finalize_delegation_run_evidence_exact(
            expected_running=run,
            completed=replace(run, status="completed", completed_at=completed_at),
            receipts=(receipt,),
            artifacts=(artifact,),
        )
    else:
        _need(
            run.completed_at == completed_at and not run.failure_code,
            "held-out oracle completed lifecycle conflicts",
        )
    acceptance = _acceptance(
        identity,
        candidate,
        manifest,
        verdict,
        observed_at=completed_at,
        receipt_id=receipt_id,
        artifact_id=artifact_id,
    )
    return HeldOutOracleOutcome(
        status=str(verdict["verdict"]).lower(),
        run_id=identity.run_id,
        verdict=verdict,
        acceptance=acceptance,
        replayed=True,
    )


async def run_held_out_oracle(
    *,
    runtime: RuntimeStateStore,
    manifest_path: Path | str,
    expected_manifest_digest: str,
    task: Task,
    candidate: OwnerExecutionObservation,
    work_root: Path | str,
    sandbox_launcher: OracleSandboxLauncher,
    attempt_number: int = 1,
    expected_evidence_bundle_sha256: str = "",
    timeout_seconds: float = ORACLE_TIMEOUT_SECONDS,
    now: Any = utc_now,
    effect_ready: Callable[[], None] | None = None,
) -> HeldOutOracleOutcome:
    """Run or replay one exact deterministic G10 verifier attempt."""
    _need(
        isinstance(attempt_number, int)
        and not isinstance(attempt_number, bool)
        and 1 <= attempt_number <= 5,
        "held-out oracle attempt must be from 1 to 5",
    )
    manifest = load_held_out_oracle_manifest(
        manifest_path,
        expected_digest=expected_manifest_digest,
    )
    authority = task.metadata.get("mission_campaign_authority")
    generation = task.metadata.get("attempt_generation")
    _need(
        task.id == manifest.task_id
        and task.status is TaskStatus.COMPLETED
        and task.metadata.get("mission_id") == manifest.mission_id
        and task.metadata.get("goal_id") == manifest.goal_id
        and task.metadata.get("mission_task_creation_hash") == manifest.task_creation_hash
        and isinstance(authority, dict)
        and type(generation) is int
        and generation >= 0
        and authority.get("attempt_generation") == generation
        and authority.get("held_out_oracle_manifest_digest") == manifest.manifest_digest
        and candidate.ref.mission_id == manifest.mission_id
        and candidate.ref.task_id == task.id
        and candidate.ref.attempt_generation == generation
        and candidate.task_status is TaskStatus.COMPLETED
        and candidate.terminal
        and candidate.succeeded
        and bool(candidate.result),
        "held-out oracle candidate or authority binding is invalid",
    )
    producer = await runtime.get_delegation_run(candidate.ref.run_id)
    producer_identity = await runtime.get_execution_identity(candidate.ref.run_id)
    _need(
        producer is not None
        and producer_identity is not None
        and producer.status.lower() == "completed"
        and producer.completed_at is not None
        and producer.task_id == task.id
        and producer.assigned_to == candidate.ref.agent_id
        and producer_identity.task_id == task.id
        and producer_identity.agent_id == candidate.ref.agent_id
        and producer.metadata.get("attempt_generation") == generation
        and producer_identity.metadata.get("attempt_generation") == generation,
        "held-out oracle producer lifecycle is not durable",
    )
    bundle = collect_g10_evidence(
        manifest,
        producer_run_id=candidate.ref.run_id,
        producer_completed_at=producer.completed_at,
    )
    if expected_evidence_bundle_sha256:
        _need(
            _sha256(
                expected_evidence_bundle_sha256,
                "expected G10 evidence bundle digest",
            )
            == bundle.digest,
            "G10 evidence changed after attempt selection",
        )
    launcher_digest = _sha256(
        sandbox_launcher.sandbox_evidence_sha256,
        "oracle sandbox launcher evidence",
    )
    sandbox_entry = bundle.payload["entries"].get("oracle_sandbox")
    if sandbox_entry is not None:
        _need(
            sandbox_entry["record_sha256"] == launcher_digest,
            "oracle sandbox launcher is not bound to admitted evidence",
        )
    output_digest = candidate_output_digest(candidate.result)
    input_payload = {
        "schema_version": HELD_OUT_INPUT_SCHEMA,
        "campaign_id": manifest.campaign_id,
        "mission_id": manifest.mission_id,
        "goal_id": manifest.goal_id,
        "task_id": manifest.task_id,
        "producer_run_id": candidate.ref.run_id,
        "manifest_digest": manifest.manifest_digest,
        "candidate_output_sha256": output_digest,
        "evidence_bundle_sha256": bundle.digest,
        "evidence_bundle": bundle.payload,
    }
    identity = _oracle_identity(
        manifest,
        candidate,
        candidate_digest=output_digest,
        bundle_digest=bundle.digest,
        missing_evidence_ids=bundle.missing_evidence_ids,
        attempt_number=attempt_number,
    )
    root = private_directory(Path(work_root).expanduser().absolute(), "oracle work root")
    run_root = private_directory(root / identity.run_id, "oracle run directory")
    input_path = run_root / "input.json"
    receipt_id = stable_id("held_out_oracle_receipt", identity.run_id)
    artifact_id = stable_id("held_out_oracle_artifact", identity.run_id)
    with OracleRunLock(run_root / "run.lock"):
        replay = await _stored_outcome(
            runtime,
            manifest,
            candidate,
            identity,
            receipt_id=receipt_id,
            artifact_id=artifact_id,
        )
        if replay is not None:
            return replay
        stored_identity = await runtime.get_execution_identity(identity.run_id)
        _need(
            stored_identity is None or stored_identity == identity,
            "held-out oracle run identity conflicts",
        )
        if stored_identity is None:
            await runtime.record_execution_identity(identity, source="campaign-held-out-oracle")
        started_at = now().astimezone(timezone.utc)
        _need(started_at >= producer.completed_at, "held-out oracle clock precedes producer")
        run = await runtime.get_delegation_run(identity.run_id)
        if run is None:
            run = DelegationRun(
                run_id=identity.run_id,
                task_id=identity.task_id,
                assigned_to=identity.agent_id,
                assigned_by="mission-control-held-out-oracle",
                status="running",
                session_id=identity.session_id,
                claim_id=identity.claim_id,
                parent_run_id=identity.parent_run_id,
                requested_output=["deterministic_held_out_acceptance"],
                started_at=started_at,
                metadata=dict(identity.metadata),
            )
            await runtime.record_delegation_run(run)
        write_exact(input_path, _canonical_bytes(input_payload))
        verdict_ready = False
        try:
            if effect_ready is not None:
                effect_ready()
            terminal = await _run_evaluator(
                manifest,
                launcher=sandbox_launcher,
                identity=identity,
                input_path=input_path,
                input_sha256=_digest(input_payload),
                sandbox_evidence_sha256=launcher_digest,
                timeout_seconds=timeout_seconds,
            )
            verdict = _validate_verdict(
                terminal.verdict_payload,
                manifest_digest=manifest.manifest_digest,
                candidate_digest=output_digest,
                bundle_digest=bundle.digest,
            )
            completed_at = terminal.completed_at.astimezone(timezone.utc)
            _need(completed_at >= started_at, "held-out oracle clock moved backwards")
            expected = {
                "producer_output_digest": output_digest,
                "oracle_manifest_digest": manifest.manifest_digest,
                "accepted": verdict["accepted"],
                "oracle_evaluator": manifest.evaluator_sha256,
                "oracle_version": manifest.oracle_version,
            }
            receipt = RuntimeStateStore.build_runtime_receipt(
                identity,
                receipt_id=receipt_id,
                receipt_type=VERIFIER_RESULT_RECEIPT_TYPE,
                status="completed",
                side_effect_key=f"held_out_oracle:{identity.run_id}",
                payload={
                    **expected,
                    "schema_version": HELD_OUT_VERDICT_SCHEMA,
                    "policy_sha256": manifest.policy_sha256,
                    "evidence_bundle_sha256": bundle.digest,
                    "missing_evidence_ids": list(bundle.missing_evidence_ids),
                    "verdict": verdict["verdict"],
                    "verdict_payload": verdict,
                    "oracle_terminal_digest": terminal.terminal_digest,
                    "oracle_terminal_path": os.fspath(terminal.terminal_path),
                },
                created_at=completed_at,
            )
            artifact = ArtifactRecord(
                artifact_id=artifact_id,
                artifact_kind="mission_held_out_oracle_verdict",
                session_id=identity.session_id,
                task_id=identity.task_id,
                run_id=identity.run_id,
                trace_id=identity.trace_id,
                payload_path=os.fspath(terminal.terminal_path),
                checksum=_digest(verdict),
                promotion_state="verified" if verdict["accepted"] else "rejected",
                created_at=completed_at,
                metadata={
                    **expected,
                    "schema_version": HELD_OUT_VERDICT_SCHEMA,
                    "policy_sha256": manifest.policy_sha256,
                    "evidence_bundle_sha256": bundle.digest,
                    "oracle_terminal_digest": terminal.terminal_digest,
                    "oracle_terminal_path": os.fspath(terminal.terminal_path),
                    "verdict": verdict["verdict"],
                },
            )
            verdict_ready = True
            await runtime.finalize_delegation_run_evidence_exact(
                expected_running=run,
                completed=replace(run, status="completed", completed_at=completed_at),
                receipts=(receipt,),
                artifacts=(artifact,),
            )
            acceptance = _acceptance(
                identity,
                candidate,
                manifest,
                verdict,
                observed_at=completed_at,
                receipt_id=receipt_id,
                artifact_id=artifact_id,
            )
            return HeldOutOracleOutcome(
                status=str(verdict["verdict"]).lower(),
                run_id=identity.run_id,
                verdict=verdict,
                acceptance=acceptance,
                replayed=False,
            )
        except Exception as exc:
            if not verdict_ready and not isinstance(exc, HeldOutOracleIndeterminate):
                failed_at = max(now().astimezone(timezone.utc), started_at)
                await runtime.compare_and_swap_delegation_run_exact(
                    run,
                    replace(
                        run,
                        status="failed",
                        completed_at=failed_at,
                        failure_code="held_out_oracle_failure",
                    ),
                )
            if isinstance(exc, HeldOutOracleError):
                raise
            phase = "during atomic finalization" if verdict_ready else "before verdict"
            raise HeldOutOracleError(f"held-out oracle failed {phase}") from exc


__all__ = [
    "G10_EVIDENCE_DIRECTORY",
    "G10_REQUIRED_EVIDENCE_IDS",
    "G10_REQUIRED_PREDICATE_IDS",
    "HELD_OUT_MANIFEST_SCHEMA",
    "G10EvidenceBundle",
    "HeldOutOracleError",
    "HeldOutOracleIndeterminate",
    "HeldOutOracleManifest",
    "HeldOutOracleOutcome",
    "collect_g10_evidence",
    "held_out_manifest_digest",
    "load_held_out_oracle_manifest",
    "render_held_out_oracle_manifest",
    "run_held_out_oracle",
]
