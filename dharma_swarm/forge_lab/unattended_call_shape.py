"""Exact child-spec and provider-call shape for bounded unattended runs."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable


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


def validated_child_result(
    path: Path,
    *,
    run_id: str,
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
    try:
        used = int(payload.get("logical_provider_calls_used"))
        limit = int(payload.get("logical_provider_call_limit"))
    except (TypeError, ValueError):
        return None
    if (
        used != policy.logical_provider_call_slots
        or limit != policy.logical_provider_call_slots
        or payload.get("execution_shape_ok") is not True
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
    state_root = Path(str(spec.get("state_root") or "")).resolve(strict=False)
    control_root = state_root / ".dharma" / "forge_lab" / "unattended_explore"
    expected_run_dir = control_root / "runs" / run_id
    expected_spec = expected_run_dir / "child_spec.json"
    expected_result = expected_run_dir / "child_result.json"
    expected_archive = state_root / ".dharma" / "evolution_archive"
    expected_scratch = state_root / ".dharma" / "evolution_worktrees"
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
    from dharma_swarm.forge_v1.forge_v2.runner import _pull_task_context
    from dharma_swarm.forge_v1.forge_v2.taskbed_ledger import allocate_task_ids
    from dharma_swarm.forge_v1.providers import PoolCompletion

    bootstrap_runtime_env()
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
        )
        budget.charge(
            "generation",
            int(generated.get("tokens") or 0),
            is_free_route=_is_free_route(generator),
        )
        patch = str(generated.get("patch") or "")
        if patch.strip() and not budget.invalid:
            counter.consume("candidate_verifier")
            verified = original_propose(
                verifier,
                inst,
                ctx,
                max_tokens=per_call_tokens,
                timeout_s=timeout_s,
                continue_rounds=0,
                window_chars=_win(verifier, window_chars),
                extra_instruction=VERIFY_TEMPLATE + "\n\nProposed patch:\n" + patch[:2000],
            )
            budget.charge(
                "verification",
                int(verified.get("tokens") or 0),
                is_free_route=_is_free_route(verifier),
            )
            if str(verified.get("patch") or "").strip():
                patch = str(verified["patch"])
        return {
            "arm": "verify_chain",
            "final_patch": patch,
            "generator": generator.model_id,
            "verifier": verifier.model_id,
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

    def state_anchored_allocate(**kwargs: Any) -> dict[str, Any]:
        if kwargs.pop("count", None) != 1:
            raise error_factory(
                "TASK_SHAPE",
                "unattended allocation requires one task",
            )
        return allocate_task_ids(task_ids=[spec["task_id"]], db_path=taskbed_db, **kwargs)

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

    return Seams(
        grade=grade,
        pull_task_context=_pull_task_context,
        allocate_explore=state_anchored_allocate,
        mutate_complete=bounded_mutation,
        make_worktree=clone_scratch,
        remove_worktree=remove_clone_scratch,
    )


def execution_shape_matches(counter: Any, counters: dict[str, Any], *, slots: int) -> bool:
    return bool(
        counter.used == slots
        and counter.by_label == EXPECTED_PROVIDER_CALLS
        and int(counters.get("graded") or 0) >= 2
        and int(counters.get("paired_controls") or 0) == 1
        and int(counters.get("blocked") or 0) == 0
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
