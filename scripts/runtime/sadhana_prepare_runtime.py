#!/usr/bin/env python3.11
"""Crash-replayable, no-effect preparation of the pinned SADHANA runtime."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dharma_swarm.mission_control import MissionControl  # noqa: E402
from dharma_swarm.mission_control_bootstrap import (  # noqa: E402
    BootstrapLockError,
    EXPECTED_CAMPAIGN_ID,
    EXPECTED_GOAL_IDS,
    GoalContractError,
    campaign_bootstrap_lock,
    initialize_sadhana_campaign,
    load_goal_contract,
)
from dharma_swarm.mission_control_campaign import (  # noqa: E402
    CampaignConfig,
    CampaignSupervisor,
    observer_only_adapter,
)
from dharma_swarm.mission_control_contract import MissionControlError  # noqa: E402
from dharma_swarm.mission_control_oracle_custody import (  # noqa: E402
    list_private_directory,
    private_directory,
    read_exact,
)
from dharma_swarm.mission_control_roster import (  # noqa: E402
    CampaignRosterError,
    load_campaign_agent_roster,
)
from dharma_swarm.mission_control_runtime_manifests import (  # noqa: E402
    RUNTIME_MANIFEST_NAMES,
    RuntimeManifestPins,
    render_runtime_manifests,
)
from dharma_swarm.runtime_admission import RuntimeAdmissionError  # noqa: E402
from dharma_swarm.runtime_state import RuntimeStateStore  # noqa: E402
from dharma_swarm.task_board import TaskBoard, TaskBoardError  # noqa: E402


PREPARATION_SCHEMA = "dharma.sadhana.runtime_preparation.v1"
SUPERVISOR_CONFIG_PROJECTION_SCHEMA = "dharma.sadhana.supervisor_config_projection.v1"
PREPARED_PROOF_TYPE = "Prepared<Mission,Release,InputSet,Config,TaskSet>"
NO_EFFECT = "NoEffect"
PREPARATION_RECEIPT_NAME = "sadhana-runtime-preparation.v1.json"
EFFECT_KINDS = (
    "provider",
    "tool",
    "lease",
    "dispatch",
    "verifier",
    "acceptance",
    "publication",
)
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RAW_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_RELEASE_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_PUBLICATION_TEMP_SUFFIX = ".sadhana-preparation.tmp"


@dataclass(frozen=True, slots=True)
class RuntimePreparationInputs:
    release_root: Path
    release_sha: str
    release_input_set_digest: str
    release_admission_receipt: Path
    contracts: Path
    observed_source: Path
    roster: Path
    roster_sha256: str
    objective_sha256: str
    state_dir: Path
    output_root: Path
    operator_id: str
    verifier_seat: str
    pins: RuntimeManifestPins
    max_dispatch_per_cycle: int = 4
    cycle_interval_seconds: float = 5.0
    freshness_seconds: float = 30.0


@dataclass(frozen=True, slots=True)
class PreparedNoEffectProof:
    campaign_id: str
    release_sha: str
    release_input_set_digest: str
    preparation_input_digest: str
    config_digest: str
    task_set_digest: str
    manifest_set_digest: str
    session_generation: int
    session_status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "type": PREPARED_PROOF_TYPE,
            "modality": "prepared",
            "effect": NO_EFFECT,
            "parameters": {
                "campaign_id": self.campaign_id,
                "release_sha": self.release_sha,
                "release_input_set_digest": self.release_input_set_digest,
                "preparation_input_digest": self.preparation_input_digest,
                "config_digest": self.config_digest,
                "task_set_digest": self.task_set_digest,
                "manifest_set_digest": self.manifest_set_digest,
                "session_generation": self.session_generation,
                "session_status": self.session_status,
            },
            "effect_counts": {kind: 0 for kind in EFFECT_KINDS},
        }


@dataclass(frozen=True, slots=True)
class _PreparationPauseRequest:
    action: str = "pause"
    request_id: str = "sadhana-runtime-preparation-pause"
    idempotency_key: str = "sadhana-runtime-preparation-pause-v1"
    issued_at: str = "1970-01-01T00:00:00Z"
    expires_at: str = "9999-12-31T23:59:59Z"
    reason: str = "Preparation must remain paused and authority-unbound."

    def validate_time_window(self, *, now: Any = None) -> None:
        _need(
            now is not None and getattr(now, "tzinfo", None) is not None,
            "preparation pause clock is invalid",
        )


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _static_input_set(
    inputs: RuntimePreparationInputs,
    *,
    release_admission_digest: str,
    contract_digest: str,
    observed_source: bytes,
) -> dict[str, object]:
    return {
        "release_admission_receipt_digest": release_admission_digest,
        "goal_contract_digest": contract_digest,
        "observed_source_sha256": (
            "sha256:" + hashlib.sha256(observed_source).hexdigest()
        ),
        "roster_sha256": inputs.roster_sha256,
        "objective_sha256": inputs.objective_sha256,
        "verifier_seat": inputs.verifier_seat,
        "manifest_pins": {
            "evaluator_path": str(inputs.pins.evaluator_path),
            "evaluator_sha256": inputs.pins.evaluator_sha256,
            "policy_path": str(inputs.pins.policy_path),
            "policy_sha256": inputs.pins.policy_sha256,
            "operator_control_semantics_sha256": (
                inputs.pins.operator_control_semantics_sha256
            ),
            "operator_control_authority_binding_sha256": (
                inputs.pins.operator_control_authority_binding_sha256
            ),
            "deployment_authority_topology_sha256": (
                inputs.pins.deployment_authority_topology_sha256
            ),
            "deployment_authority_credential_clarification_sha256": (
                inputs.pins.deployment_authority_credential_clarification_sha256
            ),
        },
    }


def supervisor_config_projection(config: CampaignConfig) -> dict[str, object]:
    """Export the exact nonsecret config inputs whose digest gates dispatch."""
    return {
        "schema_version": SUPERVISOR_CONFIG_PROJECTION_SCHEMA,
        "mission_id": config.mission_id,
        "operator_id": config.operator_id,
        "canary_task_id": config.canary_task_id,
        "max_dispatch_per_cycle": config.max_dispatch_per_cycle,
        "cycle_interval_seconds": config.cycle_interval_seconds,
        "freshness_seconds": config.freshness_seconds,
        "held_out_oracle_digest": config.held_out_oracle_digest,
    }


def validate_supervisor_config_projection(
    projection: Mapping[str, Any],
    *,
    expected_config_digest: str,
    expected_held_out_oracle_digest: str,
) -> CampaignConfig:
    """Recompute one supervisor config digest from its nonsecret projection."""
    _need(
        set(projection)
        == {
            "schema_version",
            "mission_id",
            "operator_id",
            "canary_task_id",
            "max_dispatch_per_cycle",
            "cycle_interval_seconds",
            "freshness_seconds",
            "held_out_oracle_digest",
        },
        "supervisor config projection keys are not exact",
    )
    _need(
        projection["schema_version"] == SUPERVISOR_CONFIG_PROJECTION_SCHEMA,
        "supervisor config projection schema conflicts",
    )
    try:
        config = CampaignConfig(
            mission_id=projection["mission_id"],
            operator_id=projection["operator_id"],
            canary_task_id=projection["canary_task_id"],
            max_dispatch_per_cycle=projection["max_dispatch_per_cycle"],
            cycle_interval_seconds=projection["cycle_interval_seconds"],
            freshness_seconds=projection["freshness_seconds"],
            held_out_oracle_digest=projection["held_out_oracle_digest"],
        )
    except (TypeError, ValueError) as exc:
        raise MissionControlError("supervisor config projection is invalid") from exc
    _need(
        config.held_out_oracle_digest == expected_held_out_oracle_digest,
        "supervisor config held-out substitution detected",
    )
    _need(
        config.digest == expected_config_digest,
        "supervisor config digest substitution detected",
    )
    return config


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise MissionControlError(message)


def _private_directory_descriptor(path: Path, label: str) -> int:
    directory = private_directory(path, label)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory_flag = getattr(os, "O_DIRECTORY", None)
    _need(
        nofollow is not None and directory_flag is not None,
        "runtime preparation requires no-follow directory opens",
    )
    descriptor = os.open(directory, os.O_RDONLY | nofollow | directory_flag)
    info = os.fstat(descriptor)
    if not (
        stat.S_ISDIR(info.st_mode)
        and info.st_uid == os.geteuid()
        and stat.S_IMODE(info.st_mode) == 0o700
    ):
        os.close(descriptor)
        raise MissionControlError(f"{label} custody is invalid")
    return descriptor


def _publication_temp_name(final_name: str) -> str:
    _need(
        final_name not in {"", ".", ".."} and "/" not in final_name,
        "atomic publication final name is invalid",
    )
    return f".{final_name}{_PUBLICATION_TEMP_SUFFIX}"


def _cleanup_publication_temp(
    directory_fd: int,
    *,
    final_name: str,
    label: str,
) -> None:
    temp_name = _publication_temp_name(final_name)
    try:
        temp = os.stat(temp_name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    _need(
        stat.S_ISREG(temp.st_mode)
        and temp.st_uid == os.geteuid()
        and stat.S_IMODE(temp.st_mode) == 0o600
        and temp.st_nlink in {1, 2},
        f"{label} atomic temp custody is invalid",
    )
    if temp.st_nlink == 2:
        try:
            final = os.stat(final_name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError as exc:
            raise MissionControlError(
                f"{label} atomic temp has a foreign hard link"
            ) from exc
        _need(
            stat.S_ISREG(final.st_mode)
            and (final.st_dev, final.st_ino) == (temp.st_dev, temp.st_ino),
            f"{label} atomic temp link identity conflicts",
        )
    os.unlink(temp_name, dir_fd=directory_fd)
    os.fsync(directory_fd)


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        _need(written > 0, "atomic publication write made no progress")
        remaining = remaining[written:]


def _read_published_exact(
    path: Path,
    payload: bytes,
    *,
    canonical_json: bool,
    label: str,
) -> None:
    raw, _ = read_exact(path, label=label, canonical_json=canonical_json)
    _need(raw == payload, f"{label} replay conflicts")


def _atomic_publish_exact(
    path: Path,
    payload: bytes,
    *,
    canonical_json: bool,
    label: str,
    checkpoint: Callable[[str], None] | None,
) -> None:
    """Publish complete bytes with same-directory temp + atomic no-replace link."""
    _need(bool(payload), f"{label} payload is empty")
    directory_fd = _private_directory_descriptor(path.parent, f"{label} root")
    final_name = path.name
    temp_name = _publication_temp_name(final_name)
    try:
        _cleanup_publication_temp(
            directory_fd,
            final_name=final_name,
            label=label,
        )
        try:
            os.stat(final_name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            _read_published_exact(
                path,
                payload,
                canonical_json=canonical_json,
                label=label,
            )
            return

        nofollow = getattr(os, "O_NOFOLLOW", None)
        _need(nofollow is not None, "runtime preparation requires O_NOFOLLOW")
        temp_fd = os.open(
            temp_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
            0o600,
            dir_fd=directory_fd,
        )
        try:
            midpoint = max(1, len(payload) // 2)
            _write_all(temp_fd, payload[:midpoint])
            if checkpoint is not None:
                checkpoint(f"{label}_partial")
            _write_all(temp_fd, payload[midpoint:])
            os.fsync(temp_fd)
            if checkpoint is not None:
                checkpoint(f"{label}_fsynced")
        finally:
            os.close(temp_fd)

        try:
            os.link(
                temp_name,
                final_name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError:
            os.unlink(temp_name, dir_fd=directory_fd)
            os.fsync(directory_fd)
            _read_published_exact(
                path,
                payload,
                canonical_json=canonical_json,
                label=label,
            )
            return
        os.fsync(directory_fd)
        if checkpoint is not None:
            checkpoint(f"{label}_linked")
        os.unlink(temp_name, dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    _read_published_exact(
        path,
        payload,
        canonical_json=canonical_json,
        label=label,
    )


def _reset_manifest_scratch(root: Path) -> Path:
    parent = private_directory(root.parent, "runtime preparation scratch root")
    _need(root.parent == parent, "runtime preparation scratch root conflicts")
    scratch = private_directory(root, "runtime preparation manifest scratch")
    entries = set(
        list_private_directory(scratch, "runtime preparation manifest scratch")
    )
    _need(
        entries <= set(RUNTIME_MANIFEST_NAMES),
        "runtime preparation scratch contains a foreign entry",
    )
    descriptor = _private_directory_descriptor(
        scratch,
        "runtime preparation manifest scratch",
    )
    try:
        for name in sorted(entries):
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            _need(
                stat.S_ISREG(info.st_mode)
                and info.st_uid == os.geteuid()
                and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_nlink == 1,
                "runtime preparation scratch file custody is invalid",
            )
            os.unlink(name, dir_fd=descriptor)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return scratch


def _validate_manifest_publication_root(root: Path, *, allow_temps: bool) -> None:
    directory = private_directory(root, "runtime preparation manifest publication")
    allowed = set(RUNTIME_MANIFEST_NAMES)
    if allow_temps:
        allowed.update(_publication_temp_name(name) for name in RUNTIME_MANIFEST_NAMES)
    entries = set(
        list_private_directory(
            directory,
            "runtime preparation manifest publication",
        )
    )
    _need(
        entries <= allowed,
        "runtime preparation manifest publication contains a foreign entry",
    )
    if not allow_temps:
        _need(
            entries == set(RUNTIME_MANIFEST_NAMES),
            "runtime preparation manifest publication is incomplete",
        )


def load_staged_release_admission(
    path: Path,
    *,
    expected_release_root: Path,
    expected_release_sha: str,
    expected_release_input_set_digest: str,
) -> dict[str, object]:
    """Read the immutable root-published release projection without Git access."""
    raw, parsed = read_exact(
        path,
        label="staged release admission receipt",
        canonical_json=True,
    )
    del raw
    _need(isinstance(parsed, Mapping), "staged release admission is malformed")
    payload = dict(parsed)
    _need(
        set(payload)
        == {
            "schema_version",
            "release_sha",
            "release_root",
            "tracked_source_manifest_digest",
            "tracked_source_manifest_sha256",
            "tracked_entry_count",
            "tracked_bytes",
            "isolated_build_receipt_sha256",
            "release_input_set_digest",
            "git_metadata_present",
            "frozen_tree",
            "candidate_code_executed_as_root",
            "receipt_digest",
        },
        "staged release admission keys are not exact",
    )
    _need(
        payload["schema_version"] == "dharma.sadhana.staged_release_admission.v1",
        "staged release admission schema conflicts",
    )
    _need(
        payload["release_sha"] == expected_release_sha,
        "staged release admission release substitution detected",
    )
    _need(
        payload["release_root"] == str(expected_release_root.resolve()),
        "staged release admission root substitution detected",
    )
    for field in (
        "tracked_source_manifest_digest",
        "tracked_source_manifest_sha256",
        "isolated_build_receipt_sha256",
        "release_input_set_digest",
    ):
        value = payload[field]
        _need(
            isinstance(value, str) and _RAW_SHA256_RE.fullmatch(value) is not None,
            f"staged release admission {field} is invalid",
        )
    _need(
        payload["release_input_set_digest"] == expected_release_input_set_digest,
        "staged release admission input-set substitution detected",
    )
    for field in ("tracked_entry_count", "tracked_bytes"):
        value = payload[field]
        _need(
            type(value) is int and value > 0,
            f"staged release admission {field} is invalid",
        )
    _need(
        payload["git_metadata_present"] is False
        and payload["frozen_tree"] is True
        and payload["candidate_code_executed_as_root"] is False,
        "staged release admission safety claims conflict",
    )
    claimed = payload["receipt_digest"]
    _need(
        isinstance(claimed, str) and _SHA256_RE.fullmatch(claimed) is not None,
        "staged release admission receipt digest is invalid",
    )
    unsigned = dict(payload)
    unsigned.pop("receipt_digest")
    _need(
        claimed == _digest(unsigned),
        "staged release admission receipt digest conflicts",
    )
    return payload


def validate_preparation_receipt(
    payload: Mapping[str, Any],
    *,
    expected_release_sha: str | None = None,
    expected_release_input_set_digest: str | None = None,
    expected_preparation_input_digest: str | None = None,
    expected_config_digest: str | None = None,
    expected_task_set_digest: str | None = None,
    expected_manifest_set_digest: str | None = None,
    expected_session_generation: int | None = None,
) -> None:
    """Validate the exact promotion shape for ``Prepared<...>: NoEffect``."""
    _need(
        set(payload)
        == {
            "schema_version",
            "authority_state",
            "dispatch_ready",
            "proof",
            "input_set",
            "tasks",
            "manifests",
            "config",
            "session",
            "receipt_digest",
        },
        "preparation receipt keys are not exact",
    )
    _need(
        payload["schema_version"] == PREPARATION_SCHEMA, "preparation schema conflicts"
    )
    _need(payload["authority_state"] == "unbound", "preparation bound authority")
    _need(payload["dispatch_ready"] is False, "preparation became dispatch-ready")
    proof = payload["proof"]
    _need(isinstance(proof, Mapping), "preparation proof is malformed")
    _need(
        set(proof) == {"type", "modality", "effect", "parameters", "effect_counts"},
        "preparation proof keys are not exact",
    )
    _need(proof["type"] == PREPARED_PROOF_TYPE, "preparation proof type conflicts")
    _need(proof["modality"] == "prepared", "preparation modality conflicts")
    _need(proof["effect"] == NO_EFFECT, "preparation effect conflicts")
    parameters = proof["parameters"]
    _need(isinstance(parameters, Mapping), "preparation parameters are malformed")
    _need(
        set(parameters)
        == {
            "campaign_id",
            "release_sha",
            "release_input_set_digest",
            "preparation_input_digest",
            "config_digest",
            "task_set_digest",
            "manifest_set_digest",
            "session_generation",
            "session_status",
        },
        "preparation parameters are not exact",
    )
    _need(
        parameters["campaign_id"] == EXPECTED_CAMPAIGN_ID,
        "prepared campaign identity conflicts",
    )
    _need(
        isinstance(parameters["release_sha"], str)
        and _RELEASE_SHA_RE.fullmatch(parameters["release_sha"]) is not None,
        "preparation release_sha is invalid",
    )
    _need(
        isinstance(parameters["release_input_set_digest"], str)
        and _RAW_SHA256_RE.fullmatch(parameters["release_input_set_digest"])
        is not None,
        "preparation release_input_set_digest is not raw sha256",
    )
    for field in (
        "preparation_input_digest",
        "config_digest",
        "task_set_digest",
        "manifest_set_digest",
    ):
        _need(
            isinstance(parameters[field], str)
            and _SHA256_RE.fullmatch(parameters[field]) is not None,
            f"preparation {field} is not sha256",
        )
    if expected_release_sha is not None:
        _need(
            parameters["release_sha"] == expected_release_sha,
            "preparation release substitution detected",
        )
    if expected_release_input_set_digest is not None:
        _need(
            parameters["release_input_set_digest"] == expected_release_input_set_digest,
            "preparation release input-set substitution detected",
        )
    if expected_preparation_input_digest is not None:
        _need(
            parameters["preparation_input_digest"] == expected_preparation_input_digest,
            "preparation computed-input substitution detected",
        )
    if expected_config_digest is not None:
        _need(
            parameters["config_digest"] == expected_config_digest,
            "preparation config substitution detected",
        )
    if expected_task_set_digest is not None:
        _need(
            parameters["task_set_digest"] == expected_task_set_digest,
            "preparation task-set substitution detected",
        )
    if expected_manifest_set_digest is not None:
        _need(
            parameters["manifest_set_digest"] == expected_manifest_set_digest,
            "preparation manifest-set substitution detected",
        )
    if expected_session_generation is not None:
        _need(
            parameters["session_generation"] == expected_session_generation,
            "preparation session substitution detected",
        )
    counts = proof["effect_counts"]
    _need(isinstance(counts, Mapping), "preparation effect counts are malformed")
    _need(set(counts) == set(EFFECT_KINDS), "preparation effect kinds are not exact")
    _need(
        all(type(counts[kind]) is int and counts[kind] == 0 for kind in EFFECT_KINDS),
        "preparation proof contains a nonzero effect",
    )
    tasks = payload["tasks"]
    input_set = payload["input_set"]
    manifests = payload["manifests"]
    config_projection = payload["config"]
    session = payload["session"]
    _need(
        isinstance(input_set, Mapping)
        and set(input_set)
        == {
            "release_admission_receipt_digest",
            "goal_contract_digest",
            "observed_source_sha256",
            "roster_sha256",
            "objective_sha256",
            "verifier_seat",
            "manifest_pins",
        },
        "prepared input set is not exact",
    )
    _need(
        parameters["preparation_input_digest"] == _digest(input_set),
        "prepared input-set proof does not bind inputs",
    )
    _need(
        isinstance(input_set["release_admission_receipt_digest"], str)
        and _SHA256_RE.fullmatch(input_set["release_admission_receipt_digest"])
        is not None
        and isinstance(input_set["goal_contract_digest"], str)
        and _SHA256_RE.fullmatch(input_set["goal_contract_digest"]) is not None
        and isinstance(input_set["observed_source_sha256"], str)
        and _SHA256_RE.fullmatch(input_set["observed_source_sha256"]) is not None,
        "prepared input-set source hashes are invalid",
    )
    _need(
        all(
            isinstance(input_set[field], str)
            and _RAW_SHA256_RE.fullmatch(input_set[field]) is not None
            for field in ("roster_sha256", "objective_sha256")
        ),
        "prepared input-set roster or objective hash is invalid",
    )
    pins = input_set["manifest_pins"]
    pin_keys = {
        "evaluator_path",
        "evaluator_sha256",
        "policy_path",
        "policy_sha256",
        "operator_control_semantics_sha256",
        "operator_control_authority_binding_sha256",
        "deployment_authority_topology_sha256",
        "deployment_authority_credential_clarification_sha256",
    }
    _need(
        isinstance(pins, Mapping) and set(pins) == pin_keys,
        "prepared manifest pins are not exact",
    )
    _need(
        all(
            isinstance(pins[field], str) and Path(pins[field]).is_absolute()
            for field in ("evaluator_path", "policy_path")
        ),
        "prepared manifest pin paths are invalid",
    )
    _need(
        all(
            isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None
            for field, value in pins.items()
            if field.endswith("sha256")
        ),
        "prepared manifest pin hashes are invalid",
    )
    _need(
        isinstance(tasks, Mapping) and set(tasks) == set(EXPECTED_GOAL_IDS),
        "prepared task set is not exact",
    )
    _need(
        all(isinstance(value, str) and value for value in tasks.values())
        and len(set(tasks.values())) == len(EXPECTED_GOAL_IDS),
        "prepared task identities are invalid",
    )
    _need(
        isinstance(manifests, Mapping)
        and set(manifests)
        == {
            "files",
            "observed_input_manifest_digest",
            "held_out_oracle_manifest_digest",
            "authority_manifest_digest",
        },
        "prepared manifest set is not exact",
    )
    manifest_files = manifests["files"]
    _need(
        isinstance(manifest_files, Mapping)
        and set(manifest_files) == set(RUNTIME_MANIFEST_NAMES)
        and all(
            isinstance(value, str) and _RAW_SHA256_RE.fullmatch(value) is not None
            for value in manifest_files.values()
        ),
        "prepared manifest file hashes are invalid",
    )
    _need(
        all(
            isinstance(manifests[field], str)
            and _SHA256_RE.fullmatch(manifests[field]) is not None
            for field in (
                "observed_input_manifest_digest",
                "held_out_oracle_manifest_digest",
                "authority_manifest_digest",
            )
        ),
        "prepared semantic manifest digests are invalid",
    )
    _need(
        isinstance(session, Mapping)
        and set(session) == {"session_id", "generation", "status", "config_digest"},
        "prepared session is not exact",
    )
    _need(
        session["session_id"] == f"mission_campaign:{EXPECTED_CAMPAIGN_ID}"
        and session["generation"] == 1
        and session["status"] == "paused",
        "prepared session identity is invalid",
    )
    _need(
        parameters["task_set_digest"] == _digest(tasks),
        "prepared task proof does not bind tasks",
    )
    _need(
        parameters["manifest_set_digest"] == _digest(manifests),
        "prepared manifest proof does not bind manifests",
    )
    _need(
        parameters["config_digest"] == session["config_digest"],
        "prepared session proof does not bind config",
    )
    _need(isinstance(config_projection, Mapping), "prepared config is malformed")
    validate_supervisor_config_projection(
        config_projection,
        expected_config_digest=parameters["config_digest"],
        expected_held_out_oracle_digest=manifests["held_out_oracle_manifest_digest"],
    )
    _need(
        type(parameters["session_generation"]) is int
        and parameters["session_generation"] == session["generation"]
        and parameters["session_status"] == session["status"] == "paused",
        "prepared proof does not bind the paused session",
    )
    expected = dict(payload)
    claimed = expected.pop("receipt_digest")
    _need(claimed == _digest(expected), "preparation receipt digest conflicts")


async def _effect_census(runtime: RuntimeStateStore, session_id: str) -> dict[str, int]:
    claims = await runtime.list_task_claims(session_id=session_id, limit=10_000)
    runs = await runtime.list_delegation_runs(session_id=session_id, limit=10_000)
    leases = await runtime.list_workspace_leases(active_only=False, limit=10_000)
    artifacts = await runtime.list_artifacts(session_id=session_id, limit=10_000)
    receipts = await runtime.list_runtime_receipts(
        correlation_id=session_id,
        limit=10_000,
    )
    receipt_text = tuple(
        f"{row.receipt_type}:{row.side_effect_key}".lower() for row in receipts
    )
    verifier = sum("verif" in text or "held_out" in text for text in receipt_text)
    acceptance = sum("accept" in text for text in receipt_text)
    publication = sum(
        "publish" in row.artifact_kind or "publication" in row.artifact_kind
        for row in artifacts
    ) + sum("publish" in text or "publication" in text for text in receipt_text)
    return {
        "provider": sum("provider" in text for text in receipt_text),
        "tool": sum("tool" in text for text in receipt_text),
        "lease": len(leases),
        "dispatch": len(claims) + len(runs),
        "verifier": verifier,
        "acceptance": acceptance,
        "publication": publication,
    }


def _zero_delta(before: Mapping[str, int], after: Mapping[str, int]) -> None:
    _need(
        tuple(before) == EFFECT_KINDS and tuple(after) == EFFECT_KINDS,
        "effect census keys are not exact",
    )
    delta = {kind: after[kind] - before[kind] for kind in EFFECT_KINDS}
    _need(
        all(value == 0 for value in delta.values()),
        f"runtime preparation crossed an effect boundary: {delta}",
    )
    _need(
        all(value == 0 for value in before.values())
        and all(value == 0 for value in after.values()),
        "runtime preparation requires an effect-free campaign state",
    )


async def _require_authority_unbound(
    board: TaskBoard,
    task_ids: Mapping[str, str],
) -> None:
    for goal_id, task_id in task_ids.items():
        task = await board.get(task_id)
        _need(task is not None, f"prepared task {goal_id} disappeared")
        _need(
            task.metadata.get("dispatch_ready") is False
            and "mission_campaign_authority" not in task.metadata,
            f"prepared task {goal_id} already carries dispatch authority",
        )


async def prepare_runtime(
    inputs: RuntimePreparationInputs,
    *,
    checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Prepare canonical owners under one lock without an execution capability."""
    _need(
        inputs.state_dir.is_absolute(),
        "runtime preparation state root must be absolute",
    )
    _need(inputs.release_root.is_absolute(), "release root must be absolute")
    _need(
        inputs.release_root.is_dir()
        and inputs.release_root.name == inputs.release_sha
        and not (inputs.release_root / ".git").exists(),
        "release root must be the frozen gitless directory named by release_sha",
    )
    _need(inputs.output_root.is_absolute(), "runtime manifest root must be absolute")
    _need(
        inputs.output_root.resolve()
        == (inputs.state_dir / "prepared-runtime-manifests").resolve(),
        "runtime manifests must stage under the service-owned state root",
    )
    _need(
        _RELEASE_SHA_RE.fullmatch(inputs.release_sha) is not None,
        "release_sha must be a lowercase full commit SHA",
    )
    _need(
        _RAW_SHA256_RE.fullmatch(inputs.release_input_set_digest) is not None,
        "release_input_set_digest must be a raw lowercase sha256 digest",
    )
    _need(
        inputs.release_admission_receipt.is_absolute(),
        "release admission receipt path must be absolute",
    )
    inspected_release = load_staged_release_admission(
        inputs.release_admission_receipt,
        expected_release_root=inputs.release_root,
        expected_release_sha=inputs.release_sha,
        expected_release_input_set_digest=inputs.release_input_set_digest,
    )
    _need(
        inspected_release["release_sha"] == inputs.release_sha,
        "release admission returned a foreign commit",
    )
    inspected_portfolio = load_goal_contract(inputs.contracts)
    inspected_roster = load_campaign_agent_roster(
        inputs.roster,
        expected_sha256=inputs.roster_sha256,
        campaign_id=inspected_portfolio.campaign_id,
        objective_sha256=inputs.objective_sha256,
    )
    inspected_observed, _ = read_exact(
        inputs.observed_source,
        label="runtime preparation observed source",
        canonical_json=True,
    )
    inspected_input_set = _static_input_set(
        inputs,
        release_admission_digest=str(inspected_release["receipt_digest"]),
        contract_digest=inspected_portfolio.digest,
        observed_source=inspected_observed,
    )

    lock_path = inputs.state_dir / "locks" / "sadhana-bootstrap.lock"
    with campaign_bootstrap_lock(lock_path) as lock:
        release = load_staged_release_admission(
            inputs.release_admission_receipt,
            expected_release_root=inputs.release_root,
            expected_release_sha=inputs.release_sha,
            expected_release_input_set_digest=inputs.release_input_set_digest,
        )
        portfolio = load_goal_contract(inputs.contracts)
        roster = load_campaign_agent_roster(
            inputs.roster,
            expected_sha256=inputs.roster_sha256,
            campaign_id=portfolio.campaign_id,
            objective_sha256=inputs.objective_sha256,
        )
        observed, _ = read_exact(
            inputs.observed_source,
            label="runtime preparation observed source",
            canonical_json=True,
        )
        input_set = _static_input_set(
            inputs,
            release_admission_digest=str(release["receipt_digest"]),
            contract_digest=portfolio.digest,
            observed_source=observed,
        )
        _need(
            release == inspected_release
            and portfolio == inspected_portfolio
            and roster == inspected_roster
            and input_set == inspected_input_set,
            "installed preparation inputs changed across lock acquisition",
        )
        if checkpoint is not None:
            checkpoint("validated_inputs")
        runtime = RuntimeStateStore(
            inputs.state_dir / "state" / "runtime.db",
            include_memory_plane=False,
        )
        task_db = inputs.state_dir / "db" / "tasks.db"
        task_db.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        board = TaskBoard(task_db, runtime_state=runtime)
        await runtime.init_db()
        await board.init_db()
        control = MissionControl(board, runtime)
        if checkpoint is not None:
            checkpoint("owners_initialized")

        bootstrap = await initialize_sadhana_campaign(
            portfolio,
            control,
            operator_id=inputs.operator_id,
            lock=lock,
        )
        if checkpoint is not None:
            checkpoint("mission_bootstrapped")

        session_id = f"mission_campaign:{portfolio.campaign_id}"
        await _require_authority_unbound(board, dict(bootstrap.goal_task_map))
        before = await _effect_census(runtime, session_id)
        manifest_scratch = _reset_manifest_scratch(
            inputs.state_dir / "preparation-scratch" / "runtime-manifests"
        )
        manifests = await render_runtime_manifests(
            portfolio,
            control,
            board,
            runtime,
            roster,
            observed_source_path=inputs.observed_source,
            output_root=manifest_scratch,
            verifier_seat_name=inputs.verifier_seat,
            pins=inputs.pins,
            operator_id=inputs.operator_id,
            lock=lock,
            checkpoint=checkpoint,
        )
        expected_manifest_hashes = dict(manifests.files)
        _validate_manifest_publication_root(inputs.output_root, allow_temps=True)
        publication_labels = {
            "observed-inputs.json": "publish_observed_manifest",
            "held-out-oracle.json": "publish_held_out_manifest",
            "authority-manifest.json": "publish_authority_manifest",
        }
        for name in RUNTIME_MANIFEST_NAMES:
            raw, _ = read_exact(
                manifest_scratch / name,
                label=f"rendered {name}",
                canonical_json=False,
            )
            _need(
                hashlib.sha256(raw).hexdigest() == expected_manifest_hashes[name],
                f"rendered {name} hash conflicts",
            )
            _atomic_publish_exact(
                inputs.output_root / name,
                raw,
                canonical_json=True,
                label=publication_labels[name],
                checkpoint=checkpoint,
            )
        _validate_manifest_publication_root(inputs.output_root, allow_temps=False)
        _reset_manifest_scratch(manifest_scratch)

        config = CampaignConfig(
            mission_id=portfolio.campaign_id,
            operator_id=inputs.operator_id,
            canary_task_id=bootstrap.canary_task_id,
            max_dispatch_per_cycle=inputs.max_dispatch_per_cycle,
            cycle_interval_seconds=inputs.cycle_interval_seconds,
            freshness_seconds=inputs.freshness_seconds,
            held_out_oracle_digest=manifests.held_out_oracle_manifest_digest,
        )
        supervisor = CampaignSupervisor(
            config,
            control,
            board,
            runtime,
            observer_only_adapter(control, board, runtime),
            dispatcher=None,
        )
        session = await supervisor.start()
        if checkpoint is not None:
            checkpoint("session_started")
        application = await supervisor.apply_operator_control_result(
            _PreparationPauseRequest(),
            "sadhana-runtime-preparation",
            _digest(input_set),
        )
        _need(application.status == "applied", "preparation pause was not applied")
        paused = await runtime.get_session(session.session_id)
        _need(
            paused is not None and paused.status == "paused",
            "prepared campaign session did not remain paused",
        )
        session = paused
        if checkpoint is not None:
            checkpoint("session_prepared")

        after = await _effect_census(runtime, session_id)
        _zero_delta(before, after)
        await _require_authority_unbound(board, dict(bootstrap.goal_task_map))
        task_map = dict(bootstrap.goal_task_map)
        manifest_map: dict[str, object] = {
            "files": dict(manifests.files),
            "observed_input_manifest_digest": (
                manifests.observed_input_manifest_digest
            ),
            "held_out_oracle_manifest_digest": (
                manifests.held_out_oracle_manifest_digest
            ),
            "authority_manifest_digest": manifests.authority_manifest_digest,
        }
        config_projection = supervisor_config_projection(config)
        proof = PreparedNoEffectProof(
            campaign_id=portfolio.campaign_id,
            release_sha=str(release["release_sha"]),
            release_input_set_digest=inputs.release_input_set_digest,
            preparation_input_digest=_digest(input_set),
            config_digest=config.digest,
            task_set_digest=_digest(task_map),
            manifest_set_digest=_digest(manifest_map),
            session_generation=session.metadata["generation"],
            session_status=session.status,
        )
        payload: dict[str, Any] = {
            "schema_version": PREPARATION_SCHEMA,
            "authority_state": "unbound",
            "dispatch_ready": False,
            "proof": proof.to_dict(),
            "input_set": input_set,
            "tasks": task_map,
            "manifests": manifest_map,
            "config": config_projection,
            "session": {
                "session_id": session.session_id,
                "generation": session.metadata["generation"],
                "status": session.status,
                "config_digest": config.digest,
            },
        }
        payload["receipt_digest"] = _digest(payload)
        validate_preparation_receipt(
            payload,
            expected_release_sha=str(release["release_sha"]),
            expected_release_input_set_digest=inputs.release_input_set_digest,
            expected_preparation_input_digest=_digest(input_set),
            expected_config_digest=config.digest,
            expected_task_set_digest=_digest(task_map),
            expected_manifest_set_digest=_digest(manifest_map),
            expected_session_generation=session.metadata["generation"],
        )
        receipt_root = private_directory(
            inputs.state_dir / "receipts",
            "runtime preparation receipt root",
        )
        receipt_path = receipt_root / PREPARATION_RECEIPT_NAME
        _atomic_publish_exact(
            receipt_path,
            _canonical_bytes(payload),
            canonical_json=True,
            label="publish_receipt",
            checkpoint=checkpoint,
        )
        if checkpoint is not None:
            checkpoint("receipt_written")
        raw, stored = read_exact(
            receipt_path,
            label="runtime preparation receipt",
            canonical_json=True,
        )
        _need(
            raw == _canonical_bytes(payload) and isinstance(stored, Mapping),
            "runtime preparation receipt replay conflicts",
        )
        validate_preparation_receipt(
            stored,
            expected_release_sha=str(release["release_sha"]),
            expected_release_input_set_digest=inputs.release_input_set_digest,
            expected_preparation_input_digest=_digest(input_set),
            expected_config_digest=config.digest,
            expected_task_set_digest=_digest(task_map),
            expected_manifest_set_digest=_digest(manifest_map),
            expected_session_generation=session.metadata["generation"],
        )
        return dict(stored)


def _absolute(value: str) -> Path:
    path = Path(str(value or "").strip()).expanduser()
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("path must be absolute")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", required=True, type=_absolute)
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--release-input-set-digest", required=True)
    parser.add_argument("--release-admission-receipt", required=True, type=_absolute)
    parser.add_argument("--contracts", required=True, type=_absolute)
    parser.add_argument("--observed-source", required=True, type=_absolute)
    parser.add_argument("--roster", required=True, type=_absolute)
    parser.add_argument("--roster-sha256", required=True)
    parser.add_argument("--objective-sha256", required=True)
    parser.add_argument("--state-dir", required=True, type=_absolute)
    parser.add_argument("--manifest-staging-root", required=True, type=_absolute)
    parser.add_argument("--operator-id", default="operator")
    parser.add_argument("--verifier-seat", required=True)
    parser.add_argument("--evaluator-path", required=True, type=_absolute)
    parser.add_argument("--evaluator-sha256", required=True)
    parser.add_argument("--policy-path", required=True, type=_absolute)
    parser.add_argument("--policy-sha256", required=True)
    parser.add_argument("--operator-control-semantics-sha256", required=True)
    parser.add_argument("--operator-control-authority-binding-sha256", required=True)
    parser.add_argument("--deployment-authority-topology-sha256", required=True)
    parser.add_argument(
        "--deployment-authority-credential-clarification-sha256",
        required=True,
    )
    parser.add_argument("--max-dispatch-per-cycle", type=int, default=4)
    parser.add_argument("--cycle-interval-seconds", type=float, default=5.0)
    parser.add_argument("--freshness-seconds", type=float, default=30.0)
    return parser


def _inputs(args: argparse.Namespace) -> RuntimePreparationInputs:
    return RuntimePreparationInputs(
        release_root=args.release_root,
        release_sha=args.release_sha,
        release_input_set_digest=args.release_input_set_digest,
        release_admission_receipt=args.release_admission_receipt,
        contracts=args.contracts,
        observed_source=args.observed_source,
        roster=args.roster,
        roster_sha256=args.roster_sha256,
        objective_sha256=args.objective_sha256,
        state_dir=args.state_dir,
        output_root=args.manifest_staging_root,
        operator_id=args.operator_id,
        verifier_seat=args.verifier_seat,
        pins=RuntimeManifestPins(
            evaluator_path=args.evaluator_path,
            evaluator_sha256=args.evaluator_sha256,
            policy_path=args.policy_path,
            policy_sha256=args.policy_sha256,
            operator_control_semantics_sha256=args.operator_control_semantics_sha256,
            operator_control_authority_binding_sha256=(
                args.operator_control_authority_binding_sha256
            ),
            deployment_authority_topology_sha256=(
                args.deployment_authority_topology_sha256
            ),
            deployment_authority_credential_clarification_sha256=(
                args.deployment_authority_credential_clarification_sha256
            ),
        ),
        max_dispatch_per_cycle=args.max_dispatch_per_cycle,
        cycle_interval_seconds=args.cycle_interval_seconds,
        freshness_seconds=args.freshness_seconds,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        payload = asyncio.run(prepare_runtime(_inputs(_parser().parse_args(argv))))
    except (
        BootstrapLockError,
        CampaignRosterError,
        GoalContractError,
        MissionControlError,
        OSError,
        RuntimeAdmissionError,
        sqlite3.Error,
        TaskBoardError,
        ValueError,
    ) as exc:
        sys.stderr.write(
            _canonical_bytes(
                {"status": "error", "error_type": type(exc).__name__, "error": str(exc)}
            ).decode("utf-8")
        )
        return 2
    sys.stdout.write(_canonical_bytes(payload).decode("utf-8"))
    return 0


__all__ = [
    "PREPARED_PROOF_TYPE",
    "PREPARATION_SCHEMA",
    "SUPERVISOR_CONFIG_PROJECTION_SCHEMA",
    "PreparedNoEffectProof",
    "RuntimePreparationInputs",
    "load_staged_release_admission",
    "prepare_runtime",
    "supervisor_config_projection",
    "validate_preparation_receipt",
    "validate_supervisor_config_projection",
]


if __name__ == "__main__":
    raise SystemExit(main())
