"""Child-result and provider-call shape checks for bounded unattended runs.

Split out of ``unattended_call_shape`` to keep both modules under the repo's
500-line budget (CLAUDE.md law; SOVEREIGN_MANIFEST axiom A5). The parent
module re-exports every name defined here; import from there or from here,
never both directions — this module must stay a leaf.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from dharma_swarm.forge_lab.unattended_scratch import validate_scratch_proof

if TYPE_CHECKING:
    from dharma_swarm.forge_lab.unattended_call_shape import RunnerPolicy

EXPECTED_PROVIDER_CALLS = {
    "candidate_generation": 2,
    "mutation": 1,
    "candidate_solver": 1,
    "candidate_verifier": 1,
}


def _exact_provider_call_map(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == set(EXPECTED_PROVIDER_CALLS)
        and all(
            type(value.get(role)) is int
            and value.get(role) == expected
            for role, expected in EXPECTED_PROVIDER_CALLS.items()
        )
    )


def validated_child_result(
    path: Path,
    *,
    run_id: str,
    scratch_root: Path,
    scratch_marker_digest: str,
    scratch_root_identity: dict[str, int],
    terminal_success_states: frozenset[str],
    policy: RunnerPolicy,
    safe_json_fn: Callable[[Path], dict[str, Any] | None],
    chain_digest_fn: Callable[[dict[str, Any], str], str],
) -> dict[str, Any] | None:
    if path.is_symlink():
        return None
    payload = safe_json_fn(path)
    if payload is None or payload.get("schema") != policy.child_schema:
        return None
    if payload.get("run_id") != run_id or payload.get("positive_rsi_claim") is not False:
        return None
    if payload.get("result_digest") != chain_digest_fn(payload, "result_digest"):
        return None
    used = payload.get("logical_provider_calls_used")
    limit = payload.get("logical_provider_call_limit")
    if type(used) is not int or type(limit) is not int:
        return None
    closeout = payload.get("experiment_closeout")
    if not isinstance(closeout, dict):
        return None
    experiment_id = payload.get("experiment_id")
    closeout_state = payload.get("closeout_state")
    if (
        not isinstance(experiment_id, str)
        or not experiment_id
        or Path(experiment_id).name != experiment_id
        or experiment_id in {".", ".."}
        or closeout.get("schema") != "forge_lab.closeout.v0"
        or closeout.get("experiment_id") != experiment_id
        or closeout.get("closeout_state") != closeout_state
        or not isinstance(closeout_state, str)
        or closeout_state not in terminal_success_states
    ):
        return None
    scratch = closeout.get("scratch_worktree")
    if not isinstance(scratch, dict):
        return None
    expected_root = Path(os.path.abspath(os.path.normpath(os.fspath(scratch_root))))
    expected_repo = expected_root / experiment_id / "repo"
    raw_scratch_path = scratch.get("path")
    if not isinstance(raw_scratch_path, str) or not raw_scratch_path:
        return None
    actual_repo = Path(os.path.abspath(os.path.normpath(raw_scratch_path)))
    stats = closeout.get("stats")
    counters = stats.get("counters") if isinstance(stats, dict) else None
    attestation = payload.get("scratch_custody_attestation")
    attestation_ok = validate_scratch_proof(
        attestation,
        operation="attest",
        scratch_root=expected_root,
        run_id=run_id,
        expected_root_identity=scratch_root_identity,
        expected_marker_digest=scratch_marker_digest,
    )
    if (
        used != policy.logical_provider_call_slots
        or limit != policy.logical_provider_call_slots
        or not _exact_provider_call_map(payload.get("logical_provider_calls_by_role"))
        or not _exact_provider_call_map(payload.get("expected_provider_calls_by_role"))
        or payload.get("execution_shape_ok") is not True
        or payload.get("scratch_cleanup_ok") is not True
        or payload.get("epistemic_modality") != "EXPLORE_ONLY"
        or not attestation_ok
        or scratch.get("state") != "removed"
        or scratch.get("removed") is not True
        or actual_repo != expected_repo
        or os.path.lexists(os.fspath(actual_repo))
        or os.path.lexists(os.fspath(expected_root))
        or not isinstance(counters, dict)
        or type(counters.get("graded")) is not int
        or counters.get("graded", 0) < 2
        or type(counters.get("paired_controls")) is not int
        or counters.get("paired_controls") != 1
        or type(counters.get("blocked")) is not int
        or counters.get("blocked") != 0
    ):
        return None
    return payload


def execution_shape_matches(counter: Any, counters: dict[str, Any], *, slots: int) -> bool:
    return bool(
        counter.used == slots
        and counter.by_label == EXPECTED_PROVIDER_CALLS
        and type(counters.get("graded")) is int
        and counters.get("graded", 0) >= 2
        and type(counters.get("paired_controls")) is int
        and counters.get("paired_controls") == 1
        and type(counters.get("blocked")) is int
        and counters.get("blocked") == 0
    )


__all__ = [
    "EXPECTED_PROVIDER_CALLS",
    "execution_shape_matches",
    "validated_child_result",
]
