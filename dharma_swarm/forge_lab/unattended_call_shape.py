"""Exact child-spec and provider-call shape for bounded unattended runs."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.forge_lab.unattended_scratch import validate_scratch_proof


class CallShapeError(RuntimeError):
    """Internal typed refusal translated by the unattended runner."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RunnerPolicy:
    runner_schema: str
    ledger_schema: str
    child_schema: str
    generations: int
    children: int
    tasks: int
    logical_provider_call_slots: int
    per_call_tokens: int
    per_candidate_tokens: int
    per_candidate_usd: float
    max_experiment_tokens: int
    max_timeout_seconds: int
    run_usd_reservation: float


EXPECTED_PROVIDER_CALLS = {
    "candidate_generation": 2,
    "mutation": 1,
    "candidate_solver": 1,
    "candidate_verifier": 1,
}

_TASKBED_ALLOCATION_RECEIPT_SCHEMA = "forge_v2.taskbed_allocation_receipt.v1"


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


def _build_state_anchored_explore_allocator(
    *,
    admitted_task_id: str,
    taskbed_db: Path,
    error_factory: Callable[[str, str], Exception],
    allocate_task_ids_fn: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    """Bind the allocate_explore interface to one admitted task and state DB."""

    task_id = str(admitted_task_id or "").strip()
    anchored_db = taskbed_db.expanduser().resolve(strict=False)

    def state_anchored_allocate(
        *,
        count: int,
        epoch_id: str,
        lane_id: str,
        db_path: Path | str = anchored_db,
        allocation_id: str | None = None,
        candidate_id: str = "",
    ) -> dict[str, Any]:
        # Keep this signature aligned with allocate_explore. Explicit keyword
        # parameters make additions or split overrides fail at the interface
        # instead of being silently forwarded to the lower-level allocator.
        if type(count) is not int or count != 1:
            raise error_factory(
                "TASK_SHAPE",
                "unattended allocation requires exactly one task",
            )
        if not task_id:
            raise error_factory(
                "TASK_ALLOCATION_INTERFACE",
                "admitted task id is empty",
            )
        if not isinstance(epoch_id, str) or not epoch_id.strip():
            raise error_factory(
                "TASK_ALLOCATION_INTERFACE",
                "allocation epoch id must be a non-empty string",
            )
        if not isinstance(lane_id, str) or not lane_id.strip():
            raise error_factory(
                "TASK_ALLOCATION_INTERFACE",
                "allocation lane id must be a non-empty string",
            )
        try:
            requested_db = Path(db_path).expanduser().resolve(strict=False)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise error_factory(
                "TASK_ALLOCATION_OVERRIDE",
                "taskbed database override is invalid",
            ) from exc
        if requested_db != anchored_db:
            raise error_factory(
                "TASK_ALLOCATION_OVERRIDE",
                "taskbed database cannot change after admission",
            )
        if allocation_id is not None or candidate_id != "":
            raise error_factory(
                "TASK_ALLOCATION_OVERRIDE",
                "allocation identity overrides are not admitted",
            )

        try:
            receipt = allocate_task_ids_fn(
                split="explore",
                task_ids=[task_id],
                epoch_id=epoch_id,
                lane_id=lane_id,
                db_path=anchored_db,
                allocation_id=None,
                candidate_id="",
            )
        except Exception as exc:
            raise error_factory(
                "TASK_ALLOCATION_REFUSED",
                f"exact explore allocation failed ({type(exc).__name__}): {exc}",
            ) from exc

        valid_receipt = bool(
            isinstance(receipt, dict)
            and receipt.get("schema") == _TASKBED_ALLOCATION_RECEIPT_SCHEMA
            and receipt.get("split") == "explore"
            and type(receipt.get("task_count")) is int
            and receipt.get("task_count") == 1
            and receipt.get("task_ids") == [task_id]
            and isinstance(receipt.get("allocation_id"), str)
            and bool(receipt.get("allocation_id"))
            and receipt.get("blockers") == []
        )
        if not valid_receipt:
            raise error_factory(
                "TASK_ALLOCATION_RECEIPT",
                "allocator did not receipt exactly one admitted EXPLORE task",
            )
        return receipt

    return state_anchored_allocate


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


def validate_child_spec(
    spec: dict[str, Any],
    spec_path: Path,
    *,
    admission: dict[str, Any],
    policy: RunnerPolicy,
    read_chain_fn: Callable[..., list[dict[str, Any]]],
) -> None:
    """Bind the hidden child to the parent's reservation and canonical paths."""

    run_id = str(spec.get("run_id") or "")
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise CallShapeError("CHILD_RUN_ID", "child run id is not one safe path component")
    state_root = Path(str(spec.get("state_root") or "")).resolve(strict=False)
    control_root = state_root / ".dharma" / "forge_lab" / "unattended_explore"
    expected_run_dir = control_root / "runs" / run_id
    expected_spec = expected_run_dir / "child_spec.json"
    expected_result = expected_run_dir / "child_result.json"
    expected_archive = state_root / ".dharma" / "evolution_archive"
    expected_scratch = (
        state_root / ".dharma" / "evolution_worktrees" / "unattended" / run_id
    )
    if spec_path.resolve(strict=False) != expected_spec.resolve(strict=False):
        raise CallShapeError("CHILD_SPEC_PATH", "child spec is outside its run directory")
    if Path(str(spec.get("result_path") or "")).resolve(
        strict=False
    ) != expected_result.resolve(strict=False):
        raise CallShapeError("CHILD_RESULT_PATH", "child result path is not canonical")
    if Path(str(spec.get("archive_root") or "")).resolve(
        strict=False
    ) != expected_archive.resolve(strict=False):
        raise CallShapeError("CHILD_ARCHIVE_PATH", "archive root is not state-anchored")
    if Path(str(spec.get("scratch_root") or "")).resolve(
        strict=False
    ) != expected_scratch.resolve(strict=False):
        raise CallShapeError("CHILD_SCRATCH_PATH", "scratch root is not state-anchored")
    source = admission["source"]
    if Path(str(spec.get("source_repo") or "")).resolve(strict=False) != Path(
        source["repo"]
    ).resolve(strict=False):
        raise CallShapeError("CHILD_SOURCE_PATH", "source path changed after admission")
    if not spec.get("task_id") or spec.get("task_id") != admission.get("task_id"):
        raise CallShapeError("CHILD_TASK", "isolated task changed after admission")
    if spec.get("role_bindings") != admission.get("role_bindings"):
        raise CallShapeError("CHILD_MODEL_ROLES", "model role bindings changed after admission")
    if spec.get("model_profile_digest") != admission.get("model_profile_digest"):
        raise CallShapeError("CHILD_MODEL_PROFILE", "model profile changed after admission")
    if spec.get("provider_receipt_digest") != admission.get("provider_receipt_digest"):
        raise CallShapeError("CHILD_PROVIDER_RECEIPT", "provider receipt changed after admission")
    binding = admission.get("task_context_binding")
    binding_digest = binding.get("binding_digest") if isinstance(binding, dict) else None
    if not binding_digest or spec.get("task_context_binding_digest") != binding_digest:
        raise CallShapeError(
            "CHILD_TASK_CONTEXT",
            "release-bound task context changed after admission",
        )
    expected_shape = {
        "generations": policy.generations,
        "children": policy.children,
        "tasks": policy.tasks,
    }
    if spec.get("shape") != expected_shape:
        raise CallShapeError("CHILD_SHAPE", "child shape is not fixed 1x1x1")
    limits = spec.get("limits") if isinstance(spec.get("limits"), dict) else {}
    expected_limits = {
        "logical_provider_call_slots": policy.logical_provider_call_slots,
        "per_call_tokens": policy.per_call_tokens,
        "per_candidate_tokens": policy.per_candidate_tokens,
        "per_candidate_usd": policy.per_candidate_usd,
        "max_experiment_tokens": policy.max_experiment_tokens,
        "external_timeout_seconds": limits.get("external_timeout_seconds"),
    }
    if limits != expected_limits:
        raise CallShapeError("CHILD_LIMITS", "child limits differ from fixed policy")
    timeout = int(limits.get("external_timeout_seconds") or 0)
    if timeout < 60 or timeout > policy.max_timeout_seconds:
        raise CallShapeError("CHILD_TIMEOUT", "child timeout is outside fixed policy")
    ledger = read_chain_fn(
        control_root / "budget_ledger.jsonl",
        schema=policy.ledger_schema,
        digest_field="ledger_digest",
    )
    reservation = next(
        (row for row in ledger if row.get("ledger_digest") == spec.get("reservation_digest")),
        None,
    )
    if (
        reservation is None
        or reservation.get("run_id") != run_id
        or reservation.get("reserved_usd") != policy.run_usd_reservation
        or reservation.get("reserved_logical_calls")
        != policy.logical_provider_call_slots
    ):
        raise CallShapeError("CHILD_RESERVATION", "exact parent reservation is absent")


def build_bounded_child_seams(
    spec: dict[str, Any],
    counter: Any,
    *,
    per_call_tokens: int,
    error_factory: Callable[[str, str], Exception],
    clone_scratch: Callable[..., Path],
    remove_clone_scratch: Callable[..., None],
) -> Any:
    """Build seams with exactly one provider dispatch per logical slot."""

    from dharma_swarm.api_keys import bootstrap_runtime_env
    from dharma_swarm.forge_lab import grade_explore
    from dharma_swarm.forge_lab.experiment import Seams
    from dharma_swarm.forge_v1.forge_v2.arms import VERIFY_TEMPLATE, _is_free_route, _win
    from dharma_swarm.forge_lab.unattended_context import (
        UnattendedContextError,
        load_admitted_task_context,
        sanitize_unattended_docker_env,
    )
    from dharma_swarm.forge_v1.forge_v2.taskbed_ledger import allocate_task_ids
    from dharma_swarm.forge_v1.providers import PoolCompletion

    bootstrap_runtime_env()
    sanitize_unattended_docker_env()
    base = grade_explore.production_seams()
    original_propose = base.propose_slot

    def propose_once(*args: Any, **kwargs: Any) -> dict[str, Any]:
        counter.consume("candidate_generation")
        kwargs["continue_rounds"] = 0
        return original_propose(*args, **kwargs)

    def forbidden_arm(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise error_factory(
            "UNBOUNDED_ARM_REFUSED",
            "unattended lane admits freeform_single and one bounded verify_chain only",
        )

    def bounded_verify_chain(
        generator: Any,
        verifier: Any,
        inst: dict[str, Any],
        ctx: dict[str, Any],
        budget: Any,
        *,
        per_call_tokens: int,
        timeout_s: int,
        window_chars: int | None = None,
        extra_instruction: str = "",
    ) -> dict[str, Any]:
        counter.consume("candidate_solver")
        generated = original_propose(
            generator,
            inst,
            ctx,
            max_tokens=per_call_tokens,
            timeout_s=timeout_s,
            continue_rounds=0,
            window_chars=_win(generator, window_chars),
            extra_instruction=extra_instruction,
        )
        budget.charge(
            "generation",
            int(generated.get("tokens") or 0),
            is_free_route=_is_free_route(generator),
        )
        patch = str(generated.get("patch") or "")
        generated_patch = bool(patch.strip())
        verifier_called = False
        verified = None
        if not budget.invalid:
            counter.consume("candidate_verifier")
            verifier_called = True
            proposed_patch = patch[:2000] if generated_patch else "<EMPTY_PATCH>"
            verified = original_propose(
                verifier,
                inst,
                ctx,
                max_tokens=per_call_tokens,
                timeout_s=timeout_s,
                continue_rounds=0,
                window_chars=_win(verifier, window_chars),
                extra_instruction=VERIFY_TEMPLATE + "\n\nProposed patch:\n" + proposed_patch,
            )
            budget.charge(
                "verification",
                int(verified.get("tokens") or 0),
                is_free_route=_is_free_route(verifier),
            )
            if generated_patch and str(verified.get("patch") or "").strip():
                patch = str(verified["patch"])
        return {
            "arm": "verify_chain",
            "final_patch": patch,
            "generator": generator.model_id,
            "verifier": verifier.model_id,
            "execution_evidence": {
                "schema": "rsi_lab.verify_chain_execution.v1",
                "generator_input": generated.get("execution_input_receipt"),
                "generator_empty_patch": not generated_patch,
                "verifier_called": verifier_called,
                "verifier_input": (
                    verified.get("execution_input_receipt")
                    if isinstance(verified, dict)
                    else None
                ),
                "verifier_empty_patch": (
                    not bool(str(verified.get("patch") or "").strip())
                    if isinstance(verified, dict)
                    else None
                ),
                "final_patch_empty": not bool(patch.strip()),
            },
        }

    grade = replace(
        base,
        propose_slot=propose_once,
        self_moa_arm=forbidden_arm,
        verify_chain_arm=bounded_verify_chain,
        mixed_moa_arm=forbidden_arm,
    )
    role_bindings = spec["role_bindings"]
    mutation_completion = PoolCompletion(role_bindings["mutator"]["model_id"])
    taskbed_db = Path(spec["state_root"]) / ".dharma" / "forge_v1" / "taskbed.db"

    state_anchored_allocate = _build_state_anchored_explore_allocator(
        admitted_task_id=spec["task_id"],
        taskbed_db=taskbed_db,
        error_factory=error_factory,
        allocate_task_ids_fn=allocate_task_ids,
    )

    def bounded_mutation(prompt: str) -> tuple[str, int]:
        counter.consume("mutation")
        text, tokens = mutation_completion.complete(prompt)
        child = {
            "arm_kind": "verify_chain",
            "generator_model": role_bindings["solver"]["model_id"],
            "verifier_model": role_bindings["verifier"]["model_id"],
            "per_call_tokens": per_call_tokens,
            "window_chars": 24_000,
            "extra_instruction": str(text or "")[:4_000],
            "notes": "bounded_unattended_mutation_projection",
        }
        return json.dumps(child, sort_keys=True), int(tokens)

    def pinned_task_context(task_id: str) -> tuple[dict[str, Any], dict[str, str]]:
        try:
            task, context, binding = load_admitted_task_context(
                task_id,
                state_root=Path(spec["state_root"]),
            )
        except UnattendedContextError as exc:
            raise error_factory(exc.code, str(exc)) from exc
        if binding.get("binding_digest") != spec.get("task_context_binding_digest"):
            raise error_factory(
                "TASK_CONTEXT_CHANGED",
                "release-bound task context changed after parent admission",
            )
        return task, context

    return Seams(
        grade=grade,
        pull_task_context=pinned_task_context,
        allocate_explore=state_anchored_allocate,
        mutate_complete=bounded_mutation,
        make_worktree=clone_scratch,
        remove_worktree=remove_clone_scratch,
    )


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
    "CallShapeError",
    "EXPECTED_PROVIDER_CALLS",
    "RunnerPolicy",
    "build_bounded_child_seams",
    "execution_shape_matches",
    "validate_child_spec",
    "validated_child_result",
]
