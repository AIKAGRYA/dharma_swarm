"""Closed, self-bound campaign authority manifest contract and custody checks."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dharma_swarm.mission_control_contract import (
    MissionControlError,
    clean_identifier,
    stable_id,
)
from dharma_swarm.mission_control_dispatch import (
    LEASE_DISPATCH_ACTION,
    LEASE_WORKSPACE_ACTION,
)
from dharma_swarm.mission_control_observed_input import (
    OBSERVED_INPUT_REF_KEY,
    ObservedInputRef,
)
from dharma_swarm.operator_core.execution_lease import parse_time


AUTHORITY_MANIFEST_SCHEMA_VERSION = "dharma.sadhana.campaign_authority_manifest.v4"
AUTHORITY_MANIFEST_MAX_BYTES = 1_048_576
AUTHORITY_ACTIONS = (LEASE_DISPATCH_ACTION, LEASE_WORKSPACE_ACTION)
READ_ONLY_EFFECT_MODE = "read_only"
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
_RAW_SHA256_RE = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class CampaignGoalAuthority:
    goal_id: str
    task_id: str
    goal_contract_sha256: str
    task_creation_hash: str
    effect_mode: str
    agent_name: str
    workspace_path: str
    allowed_files: tuple[str, ...]
    observed_input_ref: ObservedInputRef
    max_attempts: int
    max_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class CampaignAuthorityManifest:
    campaign_id: str
    mission_id: str
    goal_contract_sha256: str
    agent_roster_sha256: str
    campaign_end: datetime
    campaign_end_text: str
    manifest_digest: str
    observed_input_manifest_digest: str
    held_out_oracle_manifest_digest: str
    operator_control_semantics_sha256: str
    operator_control_authority_binding_sha256: str
    deployment_authority_topology_sha256: str
    deployment_authority_credential_clarification_sha256: str
    goals: tuple[CampaignGoalAuthority, ...]
    allowed_actions: tuple[str, ...] = AUTHORITY_ACTIONS
    max_usd: float = 0.0


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise MissionControlError(message)


def _canonical_json(value: Any, label: str) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise MissionControlError(f"{label} must be canonical JSON") from exc


def authority_manifest_digest(payload: Mapping[str, Any]) -> str:
    """Return the self-digest over every manifest field except the digest."""
    canonical = dict(payload)
    canonical.pop("manifest_digest", None)
    encoded = _canonical_json(canonical, "authority manifest").encode("ascii")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def campaign_workspace_path(campaign_id: str, goal_id: str) -> str:
    campaign_id = clean_identifier(campaign_id, "campaign_id")
    goal_id = clean_identifier(goal_id, "goal_id")
    return f"workspaces/{stable_id('sadhana_workspace', campaign_id, goal_id)}"


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MissionControlError(f"authority manifest duplicates key {key!r}")
        result[key] = value
    return result


def _file_identity(item: os.stat_result) -> tuple[int, ...]:
    return (
        item.st_dev,
        item.st_ino,
        item.st_uid,
        item.st_gid,
        item.st_mode,
        item.st_nlink,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )


def _open_manifest_parent(candidate: Path) -> tuple[int, str]:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    _need(
        nofollow is not None and directory is not None,
        "authority manifest requires O_NOFOLLOW and O_DIRECTORY support",
    )
    flags = os.O_RDONLY | nofollow | directory | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(os.path.sep, flags)
    try:
        for component in candidate.parent.parts[1:]:
            _need(
                component not in {"", ".", ".."},
                "authority manifest path component is invalid",
            )
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        parent = os.fstat(descriptor)
        _need(
            stat.S_ISDIR(parent.st_mode)
            and parent.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(parent.st_mode) & 0o022 == 0,
            "authority manifest parent lacks private custody",
        )
        return descriptor, candidate.name
    except OSError as exc:
        os.close(descriptor)
        raise MissionControlError(
            "authority manifest parent could not be opened exactly"
        ) from exc
    except BaseException:
        os.close(descriptor)
        raise


def _read_manifest_file(path: Path | str) -> dict[str, Any]:
    candidate = Path(path).expanduser()
    _need(candidate.is_absolute(), "authority manifest path must be absolute")
    parent, name = _open_manifest_parent(candidate)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    assert nofollow is not None
    flags = os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent)
    except OSError as exc:
        os.close(parent)
        raise MissionControlError("authority manifest could not be opened exactly") from exc
    try:
        before = os.fstat(descriptor)
        _need(stat.S_ISREG(before.st_mode), "authority manifest must be a regular file")
        _need(before.st_nlink == 1, "authority manifest must have one filesystem link")
        _need(stat.S_IMODE(before.st_mode) == 0o600, "authority manifest mode must be 0600")
        if hasattr(os, "geteuid"):
            _need(before.st_uid == os.geteuid(), "authority manifest owner is foreign")
        _need(
            0 < before.st_size <= AUTHORITY_MANIFEST_MAX_BYTES,
            "authority manifest size is invalid",
        )
        chunks: list[bytes] = []
        remaining = AUTHORITY_MANIFEST_MAX_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        encoded = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
        os.close(parent)
    _need(
        _file_identity(before) == _file_identity(after),
        "authority manifest changed while read",
    )
    _need(len(encoded) == before.st_size, "authority manifest read was incomplete")
    _need(len(encoded) <= AUTHORITY_MANIFEST_MAX_BYTES, "authority manifest is too large")
    try:
        payload = json.loads(encoded, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MissionControlError("authority manifest is not valid UTF-8 JSON") from exc
    _need(type(payload) is dict, "authority manifest must be an object")
    canonical = (_canonical_json(payload, "authority manifest") + "\n").encode("ascii")
    _need(encoded == canonical, "authority manifest bytes are not canonical")
    return payload


def _exact_keys(payload: Mapping[str, Any], expected: set[str], label: str) -> None:
    observed = set(payload)
    _need(observed == expected, f"{label} fields conflict: {sorted(observed ^ expected)}")


def _exact_identifier(value: Any, label: str) -> str:
    _need(isinstance(value, str), f"{label} must be a string")
    cleaned = clean_identifier(value, label)
    _need(cleaned == value, f"{label} must be canonical")
    return cleaned


def _exact_sha256(value: Any, label: str) -> str:
    _need(
        isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None,
        f"{label} must be sha256",
    )
    return value


def _exact_raw_sha256(value: Any, label: str) -> str:
    _need(
        isinstance(value, str) and _RAW_SHA256_RE.fullmatch(value) is not None,
        f"{label} must be a raw lowercase SHA-256",
    )
    return value


def _zero_usd(value: Any, label: str) -> float:
    _need(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and float(value) == 0.0,
        f"{label} must be exactly zero",
    )
    return 0.0


def _positive_int(value: Any, label: str) -> int:
    _need(
        isinstance(value, int) and not isinstance(value, bool) and value > 0,
        f"{label} must be a positive integer",
    )
    return value


def _relative_path(value: Any, label: str) -> str:
    _need(
        isinstance(value, str) and value == value.strip() and value,
        f"{label} must be a nonempty canonical path",
    )
    _need(
        not value.startswith(("/", "~"))
        and "\\" not in value
        and not set(value) & set("*?[]{}()!|")
        and ":" not in value.split("/", 1)[0]
        and all(
            part not in {"", ".", ".."} and not part.startswith("~")
            for part in value.split("/")
        ),
        f"{label} must be a canonical relative path",
    )
    return value


def _allowed_files(value: Any, label: str) -> tuple[str, ...]:
    _need(type(value) is list and bool(value), f"{label} must be a nonempty list")
    paths = tuple(_relative_path(item, f"{label} item") for item in value)
    _need(len(set(paths)) == len(paths), f"{label} contains duplicates")
    _need(list(paths) == sorted(paths), f"{label} must be sorted")
    return paths


def _exact_observed_ref(value: Any, goal_id: str) -> ObservedInputRef:
    _need(type(value) is dict, f"goal {goal_id} observed input ref must be an object")
    expected = {
        "receipt_id",
        "receipt_sha256",
        "artifact_id",
        "artifact_record_sha256",
        "content_sha256",
    }
    _need(set(value) == expected, f"goal {goal_id} observed input ref fields conflict")
    return ObservedInputRef(
        receipt_id=_exact_identifier(value["receipt_id"], f"goal {goal_id} receipt_id"),
        receipt_sha256=_exact_sha256(
            value["receipt_sha256"], f"goal {goal_id} receipt_sha256"
        ),
        artifact_id=_exact_identifier(value["artifact_id"], f"goal {goal_id} artifact_id"),
        artifact_record_sha256=_exact_sha256(
            value["artifact_record_sha256"],
            f"goal {goal_id} artifact_record_sha256",
        ),
        content_sha256=_exact_sha256(
            value["content_sha256"], f"goal {goal_id} content_sha256"
        ),
    )


def _canonical_time(value: Any, label: str) -> tuple[str, datetime]:
    _need(isinstance(value, str) and value, f"{label} must be a timestamp")
    parsed = parse_time(value)
    _need(
        parsed is not None
        and parsed.tzinfo is not None
        and parsed.isoformat() == value,
        f"{label} must be a canonical timezone-aware ISO timestamp",
    )
    return value, parsed


def load_campaign_authority_manifest(path: Path | str) -> CampaignAuthorityManifest:
    payload = _read_manifest_file(path)
    _exact_keys(
        payload,
        {
            "schema_version",
            "campaign_id",
            "mission_id",
            "goal_contract_sha256",
            "agent_roster_sha256",
            "campaign_end",
            "allowed_actions",
            "max_usd",
            "goals",
            "manifest_digest",
            "observed_input_manifest_digest",
            "held_out_oracle_manifest_digest",
            "operator_control_semantics_sha256",
            "operator_control_authority_binding_sha256",
            "deployment_authority_topology_sha256",
            "deployment_authority_credential_clarification_sha256",
        },
        "authority manifest",
    )
    _need(
        payload["schema_version"] == AUTHORITY_MANIFEST_SCHEMA_VERSION,
        "authority manifest schema is foreign",
    )
    campaign_id = _exact_identifier(payload["campaign_id"], "campaign_id")
    mission_id = _exact_identifier(payload["mission_id"], "mission_id")
    _need(campaign_id == mission_id, "campaign and mission identity must be exact")
    contract = _exact_sha256(payload["goal_contract_sha256"], "goal contract digest")
    roster_sha256 = _exact_raw_sha256(payload["agent_roster_sha256"], "agent roster digest")
    end_text, campaign_end = _canonical_time(payload["campaign_end"], "campaign_end")
    _need(
        payload["allowed_actions"] == list(AUTHORITY_ACTIONS),
        "authority manifest actions must be the exact campaign actions",
    )
    _zero_usd(payload["max_usd"], "authority manifest max_usd")
    digest = _exact_sha256(payload["manifest_digest"], "manifest_digest")
    _need(digest == authority_manifest_digest(payload), "authority manifest digest conflicts")
    raw_goals = payload["goals"]
    _need(type(raw_goals) is dict and bool(raw_goals), "authority manifest goals must be an object")
    goals: list[CampaignGoalAuthority] = []
    for raw_goal_id in sorted(raw_goals):
        goal_id = _exact_identifier(raw_goal_id, "goal_id")
        raw = raw_goals[raw_goal_id]
        _need(type(raw) is dict, f"goal {goal_id} authority must be an object")
        _exact_keys(
            raw,
            {
                "task_id",
                "goal_contract_sha256",
                "task_creation_hash",
                "effect_mode",
                "agent_name",
                "workspace_path",
                "allowed_files",
                "max_attempts",
                "max_usd",
                OBSERVED_INPUT_REF_KEY,
            },
            f"goal {goal_id} authority",
        )
        workspace = _relative_path(raw["workspace_path"], f"goal {goal_id} workspace")
        effect_mode = raw["effect_mode"]
        _need(
            effect_mode in {READ_ONLY_EFFECT_MODE, "write"},
            f"goal {goal_id} effect mode is unsupported",
        )
        _need(
            workspace == campaign_workspace_path(campaign_id, goal_id),
            f"goal {goal_id} workspace is not the deterministic campaign path",
        )
        goals.append(
            CampaignGoalAuthority(
                goal_id=goal_id,
                task_id=_exact_identifier(raw["task_id"], f"goal {goal_id} task_id"),
                goal_contract_sha256=_exact_sha256(
                    raw["goal_contract_sha256"], f"goal {goal_id} contract digest"
                ),
                task_creation_hash=_exact_raw_sha256(
                    raw["task_creation_hash"], f"goal {goal_id} task creation hash"
                ),
                effect_mode=effect_mode,
                agent_name=_exact_identifier(
                    raw["agent_name"], f"goal {goal_id} agent_name"
                ),
                workspace_path=workspace,
                allowed_files=_allowed_files(
                    raw["allowed_files"], f"goal {goal_id} allowed_files"
                ),
                observed_input_ref=_exact_observed_ref(
                    raw[OBSERVED_INPUT_REF_KEY], goal_id
                ),
                max_attempts=_positive_int(
                    raw["max_attempts"], f"goal {goal_id} max_attempts"
                ),
                max_usd=_zero_usd(raw["max_usd"], f"goal {goal_id} max_usd"),
            )
        )
    _need(
        len({goal.task_id for goal in goals}) == len(goals),
        "authority manifest maps multiple goals to one task",
    )
    return CampaignAuthorityManifest(
        campaign_id=campaign_id,
        mission_id=mission_id,
        goal_contract_sha256=contract,
        agent_roster_sha256=roster_sha256,
        campaign_end=campaign_end,
        campaign_end_text=end_text,
        manifest_digest=digest,
        observed_input_manifest_digest=_exact_sha256(
            payload["observed_input_manifest_digest"],
            "observed input manifest digest",
        ),
        held_out_oracle_manifest_digest=_exact_sha256(
            payload["held_out_oracle_manifest_digest"],
            "held-out oracle manifest digest",
        ),
        operator_control_semantics_sha256=_exact_sha256(
            payload["operator_control_semantics_sha256"],
            "operator control semantics digest",
        ),
        operator_control_authority_binding_sha256=_exact_sha256(
            payload["operator_control_authority_binding_sha256"],
            "operator control authority binding digest",
        ),
        deployment_authority_topology_sha256=_exact_sha256(
            payload["deployment_authority_topology_sha256"],
            "deployment authority topology digest",
        ),
        deployment_authority_credential_clarification_sha256=_exact_sha256(
            payload["deployment_authority_credential_clarification_sha256"],
            "deployment authority credential clarification digest",
        ),
        goals=tuple(goals),
    )


__all__ = [
    "AUTHORITY_ACTIONS",
    "AUTHORITY_MANIFEST_MAX_BYTES",
    "AUTHORITY_MANIFEST_SCHEMA_VERSION",
    "READ_ONLY_EFFECT_MODE",
    "CampaignAuthorityManifest",
    "CampaignGoalAuthority",
    "authority_manifest_digest",
    "campaign_workspace_path",
    "load_campaign_authority_manifest",
]
