"""RUDRA v0 frozen result contracts and canonical digest helpers.

Frozen result shapes shared across module boundaries (spec section 7,
interface freeze): the only shapes Driver, Workcell, and GoalGate exchange,
plus the canonical JSON digest helpers every RUDRA module shares. Split out
of ``contracts`` to keep both modules inside the 500-line budget; the
public import path stays ``dharma_swarm.rudra.contracts`` via re-export.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md sections 7-9.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


class VerifierReceipt(_Frozen):

    command_id: str
    argv: list[str]
    executable_sha256: str
    cwd: str
    env_digest: str
    started_at: float
    ended_at: float
    exit_code: int | None
    timed_out: bool
    stdout_sha256: str
    stderr_sha256: str
    assertions_passed: bool
    failure_reason: str | None = None


class GateResult(_Frozen):

    green: bool
    subject_digest: str
    changed_paths: list[str]
    receipts: list[VerifierReceipt]
    reasons: list[str]
    verifier_run_id: str


class ProcessHandle(_Frozen):

    pid: int
    pgid: int
    os_boot_id: str
    process_start_id: str
    executable: str
    cwd: str
    run_nonce: str


class TurnObservation(_Frozen):

    thread_id: str
    turn_id: str
    terminal_event: str
    input_tokens: int | None
    output_tokens: int | None
    aggregate_diff_sha256: str | None
    response_sha256: str | None
    reported_complete: bool = False


class GoalGatePassed(_Frozen):
    """Exact subject of reproduced completion (spec section 8)."""

    mission_id: str
    attempt_id: str
    base_sha: str
    candidate_sha: str
    contract_digest: str
    verification_workcell_id: str
    workspace_digest: str
    changed_path_digest: str
    verifier_run_id: str
    ordered_verifier_receipt_digests: list[str]
    codex_version: str
    schema_digest: str
    completed_at: float


class ReportedCompletion(_Frozen):
    """Executor-side claim. Carries no authority and cannot be promoted."""

    mission_id: str
    attempt_id: str
    candidate_sha: str
    summary: str = ""


_GATE_TOKEN: object = object()  # module-private; exported to goal_gate only


class ReproducedCompletion(_Frozen):
    """MissionCompletion[Reproduced]. No public constructor (spec section 9)."""

    mission_id: str
    attempt_id: str
    base_sha: str
    candidate_sha: str
    contract_digest: str
    workspace_digest: str
    verifier_run_id: str
    gate_passed_digest: str

    def __init__(self, **data: Any) -> None:
        token = data.pop("_gate_token", None)
        if token is not _GATE_TOKEN:
            raise TypeError(
                "ReproducedCompletion is constructible only inside "
                "goal_gate.promote (spec section 9)"
            )
        super().__init__(**data)


def sha256_json(payload: Any) -> str:
    """Canonical JSON digest helper shared by all RUDRA modules."""
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False, default=str,
        ).encode("ascii")
    ).hexdigest()


def derive_mission_key(canonical_remote: str, base_sha: str, contract_digest: str) -> str:
    """Safe filesystem key; raw mission IDs never name directories."""
    return hashlib.sha256(
        f"rudra-mission\x00{canonical_remote}\x00{base_sha}\x00{contract_digest}".encode()
    ).hexdigest()[:32]


def derive_attempt_key(mission_key: str, attempt_uuid: str) -> str:
    return hashlib.sha256(
        f"rudra-attempt\x00{mission_key}\x00{attempt_uuid}".encode()
    ).hexdigest()[:32]
