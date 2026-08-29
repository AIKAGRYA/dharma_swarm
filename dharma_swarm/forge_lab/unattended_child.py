"""Child-spec validation wrappers and the isolated child runner.

Split out of ``unattended_explore`` to keep both modules under the repo's
500-line budget (CLAUDE.md law; SOVEREIGN_MANIFEST axiom A5). The parent
module re-exports every name defined here.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.state_io import (
    content_digest,
    safe_json,
    write_json_exclusive,
)
from dharma_swarm.forge_lab.unattended_admission import admission_status
from dharma_swarm.forge_lab.unattended_call_shape import (
    EXPECTED_PROVIDER_CALLS,
    CallShapeError,
    build_bounded_child_seams,
    execution_shape_matches,
    validate_child_spec,
    validated_child_result,
)
from dharma_swarm.forge_lab.unattended_chain import (
    _chain_digest,
    _now,
    append_chain,
    read_chain,
)
from dharma_swarm.forge_lab.unattended_child_support import (
    child_scratch_identity as _child_scratch_identity,
    child_scratch_marker_digest as _child_scratch_marker_digest,
    clone_scratch as _clone_scratch,
    redact_secret_values as _redact_secret_values,
    remove_clone_scratch as _remove_clone_scratch,
    run_with_scratch_custody as _run_with_scratch_custody,
)
from dharma_swarm.forge_lab.unattended_policy import (
    CHILD_SCHEMA,
    CHILDREN,
    GENERATIONS,
    LOGICAL_PROVIDER_CALL_SLOTS,
    MAX_EXPERIMENT_TOKENS,
    PER_CALL_TOKENS,
    PER_CANDIDATE_TOKENS,
    PER_CANDIDATE_USD,
    RECEIPT_SCHEMA,
    RUNNER_POLICY,
    RUNNER_SCHEMA,
    TASKS,
    TERMINAL_SUCCESS_STATES,
    LogicalCallBudget,
    UnattendedError,
)
from dharma_swarm.forge_lab.unattended_recovery import recover_stale_scratch
from dharma_swarm.forge_lab.unattended_scratch import (
    ScratchCustodyError,
    acquire_run_scratch_lease,
)


def _append_receipt(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return append_chain(
        root / "receipts.jsonl",
        payload,
        schema=RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )


def _validated_child_result(
    path: Path,
    *,
    run_id: str,
    scratch_root: Path,
    scratch_marker_digest: str,
    scratch_root_identity: dict[str, int],
) -> dict[str, Any] | None:
    return validated_child_result(
        path,
        run_id=run_id,
        scratch_root=scratch_root,
        scratch_marker_digest=scratch_marker_digest,
        scratch_root_identity=scratch_root_identity,
        terminal_success_states=frozenset(TERMINAL_SUCCESS_STATES),
        policy=RUNNER_POLICY,
        safe_json_fn=safe_json,
        chain_digest_fn=_chain_digest,
    )


def _validate_child_spec(
    spec: dict[str, Any],
    spec_path: Path,
    *,
    admission: dict[str, Any],
) -> None:
    try:
        validate_child_spec(
            spec,
            spec_path,
            admission=admission,
            policy=RUNNER_POLICY,
            read_chain_fn=read_chain,
        )
    except CallShapeError as exc:
        raise UnattendedError(exc.code, str(exc)) from exc


def _recover_stale_scratch(
    state_root: Path,
    control_root: Path,
) -> list[dict[str, Any]]:
    return recover_stale_scratch(
        state_root,
        control_root,
        read_chain_fn=read_chain,
        append_receipt_fn=_append_receipt,
        now_fn=_now,
    )

def _bounded_child_seams(spec: dict[str, Any], counter: LogicalCallBudget):
    """Build seams with exactly one provider dispatch per logical slot."""

    return build_bounded_child_seams(
        spec,
        counter,
        per_call_tokens=PER_CALL_TOKENS,
        error_factory=UnattendedError,
        clone_scratch=_clone_scratch,
        remove_clone_scratch=_remove_clone_scratch,
    )


def _execute_child_experiment(
    spec: dict[str, Any],
    *,
    run_id: str,
    scratch_attestation: dict[str, Any],
) -> int:
    """Execute one already-attested child while its scratch lease is held."""

    from dharma_swarm.forge_lab.experiment import ExperimentConfig, run_experiment

    os.environ["DHARMA_EVOLUTION_WORKTREE_ROOT"] = spec["scratch_root"]
    counter = LogicalCallBudget()
    role_bindings = spec["role_bindings"]
    cfg = ExperimentConfig(
        generations=GENERATIONS,
        children=CHILDREN,
        tasks_per_generation=TASKS,
        solver_model=role_bindings["solver"]["model_id"],
        verifier_model=role_bindings["verifier"]["model_id"],
        mutator_model=role_bindings["mutator"]["model_id"],
        seed_genome={
            "arm_kind": "freeform_single",
            "generator_model": role_bindings["solver"]["model_id"],
            "verifier_model": role_bindings["verifier"]["model_id"],
            "per_call_tokens": PER_CALL_TOKENS,
            "window_chars": 24_000,
            "extra_instruction": "bounded unattended EXPLORE control",
            "notes": "bounded_unattended_seed",
        },
        budget_cap_tokens=PER_CANDIDATE_TOKENS,
        budget_cap_usd=PER_CANDIDATE_USD,
        soft_token_cap=False,
        max_experiment_tokens=MAX_EXPERIMENT_TOKENS,
        propose_timeout_s=240,
        grade_timeout_s=600,
        rng_seed=20260825,
        source_repo=Path(spec["source_repo"]),
        state_root=Path(spec["archive_root"]),
        keep_worktree=False,
        force_single_llm_mutation=True,
    )
    closeout = _run_with_scratch_custody(
        _bounded_child_seams(spec, counter),
        lambda seams: asyncio.run(run_experiment(cfg, seams=seams)),
    )
    closeout = _redact_secret_values(closeout)
    stats = closeout.get("stats") if isinstance(closeout.get("stats"), dict) else {}
    counters = stats.get("counters") if isinstance(stats.get("counters"), dict) else {}
    scratch = (
        closeout.get("scratch_worktree")
        if isinstance(closeout.get("scratch_worktree"), dict)
        else {}
    )
    scratch_cleanup_ok = bool(
        scratch.get("state") == "removed" and scratch.get("removed") is True
    )
    execution_shape_ok = scratch_cleanup_ok and execution_shape_matches(
        counter,
        counters,
        slots=LOGICAL_PROVIDER_CALL_SLOTS,
    )
    effective_state = (
        closeout.get("closeout_state")
        if execution_shape_ok
        else "inconclusive_generation"
    )
    result = {
        "schema": CHILD_SCHEMA,
        "run_id": run_id,
        "experiment_id": closeout.get("experiment_id"),
        "closeout_state": effective_state,
        "logical_provider_calls_used": counter.used,
        "logical_provider_call_limit": counter.limit,
        "logical_provider_calls_by_role": counter.by_label,
        "expected_provider_calls_by_role": EXPECTED_PROVIDER_CALLS,
        "execution_shape_ok": execution_shape_ok,
        "scratch_cleanup_ok": scratch_cleanup_ok,
        "scratch_custody_attestation": scratch_attestation,
        "experiment_closeout": closeout,
        "epistemic_modality": "EXPLORE_ONLY",
        "positive_rsi_claim": False,
        "billing_telemetry": "unavailable_reservation_only",
    }
    result["result_digest"] = content_digest(result)
    write_json_exclusive(Path(spec["result_path"]), result)
    return 0 if effective_state in TERMINAL_SUCCESS_STATES else 1


def run_child(spec_path: Path) -> int:
    """Execute the admitted child spec and persist one exclusive result."""

    spec = safe_json(spec_path)
    if spec is None or spec.get("schema") != RUNNER_SCHEMA:
        raise UnattendedError("CHILD_SPEC_INVALID", str(spec_path))
    expected_digest = spec.get("spec_digest")
    actual_digest = content_digest({key: value for key, value in spec.items() if key != "spec_digest"})
    if expected_digest != actual_digest:
        raise UnattendedError("CHILD_SPEC_DIGEST", "child spec digest mismatch")
    run_id = str(spec.get("run_id") or "")
    if os.environ.get("RSI_LAB_UNATTENDED_CHILD_RUN_ID") != run_id:
        raise UnattendedError("CHILD_CUSTODY", "child run id environment mismatch")
    state_root = Path(spec["state_root"]).resolve()
    admission = admission_status(state_root)
    if not admission["ready"]:
        raise UnattendedError("CHILD_ADMISSION_REFUSED", ",".join(admission["reasons"]))
    if admission["source"].get("commit") != spec.get("source_commit"):
        raise UnattendedError("SOURCE_CHANGED", "source commit changed after parent admission")
    if admission["routes"] != spec.get("routes"):
        raise UnattendedError("PROVIDER_RECEIPT_CHANGED", "provider routes changed after admission")
    if admission["role_bindings"] != spec.get("role_bindings"):
        raise UnattendedError("MODEL_PROFILE_CHANGED", "model roles changed after admission")
    if admission["model_profile_digest"] != spec.get("model_profile_digest"):
        raise UnattendedError("MODEL_PROFILE_CHANGED", "model profile changed after admission")
    if admission["provider_receipt_digest"] != spec.get("provider_receipt_digest"):
        raise UnattendedError("PROVIDER_RECEIPT_CHANGED", "provider receipt changed after admission")
    _validate_child_spec(spec, spec_path, admission=admission)
    root_identity = _child_scratch_identity()
    marker_digest = _child_scratch_marker_digest()
    try:
        scratch_lease = acquire_run_scratch_lease(
            state_root,
            run_id,
            source_commit=str(spec["source_commit"]),
            spec_digest=str(spec["spec_digest"]),
            expected_root_identity=root_identity,
            expected_marker_digest=marker_digest,
        )
    except ScratchCustodyError as exc:
        raise UnattendedError(exc.code, str(exc.proof["proof_digest"])) from exc
    try:
        return _execute_child_experiment(
            spec,
            run_id=run_id,
            scratch_attestation=scratch_lease.proof,
        )
    finally:
        scratch_lease.close()
