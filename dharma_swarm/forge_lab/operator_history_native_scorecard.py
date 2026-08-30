"""Construct scorecards for unassociated native Forge Lab experiments."""

from __future__ import annotations

from typing import Any

from dharma_swarm.forge_lab.operator_history_sources import (
    METRIC_KEYS,
    SCORECARD_SCHEMA,
    _closeout_metric,
    _display_state,
    _first,
    _format_rate,
    _get,
    _identity_suffix,
    _iso,
    _length,
    _mapping,
    _number,
    _result_counts,
    _sequence,
    _short_sha,
    _slug,
    _sum_known,
)


def _scorecard_for_native(experiment: dict[str, Any]) -> dict[str, Any]:
    rows = [_mapping(row) for row in _sequence(experiment.get("results"))]
    counts = _result_counts(rows)
    started = experiment.get("started_at_dt")
    finished = experiment.get("finished_at_dt")
    closeout = _mapping(experiment.get("closeout"))
    seed = _number(_closeout_metric(experiment, "seed"))
    best = _number(_closeout_metric(experiment, "best"))
    models = list(experiment.get("models", []))
    verdict = closeout.get("closeout_state") or (
        "incomplete_no_closeout" if rows else "archive_tombstone"
    )
    warnings = list(experiment.get("warnings", []))
    warnings.append("Native-only experiment: no operator session association was found")
    if not closeout:
        warnings.append("Native experiment has no closeout")
    graded_rows = _first(
        counts["graded_rows"] if rows else None,
        _closeout_metric(experiment, "graded"),
    )
    known_budget_rows = counts["budget_known_rows"] if rows else 0
    valid_budget_rows = counts["budget_valid_rows"] if rows else None
    if not _number(graded_rows):
        budget_state = "unknown"
        headline_lift_valid = None
    elif known_budget_rows != graded_rows:
        budget_state = "incomplete_budget_validity"
        headline_lift_valid = False
    elif valid_budget_rows == graded_rows:
        budget_state = "all_rows_budget_valid"
        headline_lift_valid = True
    elif valid_budget_rows == 0:
        budget_state = "no_budget_valid_rows"
        headline_lift_valid = False
    else:
        budget_state = "partially_budget_invalid"
        headline_lift_valid = False
    if budget_state == "no_budget_valid_rows":
        warnings.append("QUALITY INVALID FOR LIFT: no graded row is budget-valid")
    elif budget_state in {"partially_budget_invalid", "incomplete_budget_validity"}:
        warnings.append(
            "Quality evidence is budget-qualified or has incomplete validity metadata"
        )

    closeout_tokens = _closeout_metric(experiment, "tokens")
    partial_tokens = _sum_known(_get(row, "budget", "spent_tokens") for row in rows)
    reported_tokens = _first(closeout_tokens, partial_tokens)
    usage_scope = (
        "native closeout"
        if closeout_tokens is not None
        else (
            "partial sum from native result-row budgets"
            if partial_tokens is not None
            else "unknown"
        )
    )
    usage_is_lower_bound = closeout_tokens is None and partial_tokens is not None
    stamp = started.strftime("%Y-%m-%dT%H%M%SZ") if started else "undated"
    model_name = models[0] if len(models) == 1 else "multi-model" if models else None
    slug = (
        f"{stamp}__native-only__"
        f"{_slug(experiment.get('benchmark'), fallback='benchmark-unknown')}__"
        f"{_slug(model_name, fallback='model-unknown')}__"
        f"id-{_identity_suffix(experiment['experiment_id'])}"
    )
    metrics = {
        "verdict": {
            "state": verdict,
            "display": _display_state(verdict),
            "winner": None,
            "promotion": None,
            "claim_boundary": None,
        },
        "quality": {
            "seed_pass_rate": seed,
            "best_pass_rate": best,
            "absolute_lift": float(best) - float(seed)
            if seed is not None and best is not None
            else None,
            "aggregation": "single native experiment candidate-minus-seed delta",
            "quality_phase_count": 1 if seed is not None and best is not None else 0,
            "budget_evidence_state": budget_state,
            "headline_lift_valid": headline_lift_valid,
            "best_display": _format_rate(best),
        },
        "lineage": {
            "unique_candidate_ids": len(counts["candidate_ids"]) if rows else None,
            "unique_parent_ids": _length(counts["parent_ids"]) if rows else None,
            "unique_child_ids": _length(counts["child_ids"]) if rows else None,
            "unique_edges": _length(counts["edges"]) if rows else None,
            "parent_metadata_complete": counts["parent_metadata_complete"],
            "maximum_generation": counts["max_generation"],
        },
        "evaluation": {
            "native_experiment_ids": [experiment["experiment_id"]],
            "native_experiment_count": 1,
            "raw_graded_rows": graded_rows,
            "accepted_graded_rows": graded_rows,
            "task_observations": counts["task_observations"] if rows else None,
            "solved_observations": counts["solved_observations"] if rows else None,
            "empty_patch_observations": counts["empty_patch_observations"]
            if rows
            else None,
            "unique_task_ids": counts["task_ids"],
            "unique_solved_task_ids": counts["solved_task_ids"],
            "budget_valid_graded_rows": counts["budget_valid_rows"],
            "budget_rows_with_known_validity": counts["budget_known_rows"],
        },
        "usage": {
            "reported_tokens": reported_tokens,
            "prompt_tokens": None,
            "completion_tokens": None,
            "reported_token_cap": _get(
                experiment, "manifest", "config", "max_experiment_tokens"
            ),
            "cap_fraction": None,
            "actual_cost_usd": None,
            "scope": usage_scope,
            "is_lower_bound": usage_is_lower_bound,
        },
        "provider": {
            "models": models,
            "declared_route": None,
            "independent_routes": None,
            "logical_requests": None,
            "successful_requests": None,
            "failed_requests": None,
            "hidden_retries": None,
        },
        "runtime": {
            "started_at": _iso(started),
            "finished_at": _iso(finished),
            "operator_elapsed_seconds": None,
            "active_wall_seconds": _closeout_metric(experiment, "wall"),
            "deadline_respected": None,
            "timed_out": None,
        },
        "holdout": {
            "planned_tasks": None,
            "result_occurrences": None,
            "used": None,
            "reserve_tasks": None,
            "reserve_result_occurrences": None,
            "winner_frozen": None,
        },
        "provenance": {
            "run_id": None,
            "source_git_sha": experiment.get("git_sha"),
            "source_git_sha8": _short_sha(experiment.get("git_sha")),
            "mode": experiment.get("mode"),
            "operator_session_path": None,
            "operator_log_path": None,
            "native_experiment_path": str(experiment["path"]),
            "association_methods": [],
        },
        "integrity": {
            "merkle_verified": _get(closeout, "merkle", "verified"),
            "scratch_removed": _get(closeout, "scratch_worktree", "removed"),
            "source_worktree_clean": None,
            "cleanup_warning_count": None,
            "complete_receipts": bool(closeout),
            "warning_count": len(warnings),
        },
    }
    assert tuple(metrics) == METRIC_KEYS
    return {
        "schema": SCORECARD_SCHEMA,
        "run_id": experiment["experiment_id"],
        "experiment_id": experiment["experiment_id"],
        "slug": slug,
        "started_at": _iso(started),
        "finished_at": _iso(finished),
        "kind": "native-only",
        "metrics": metrics,
        "experiments": [],
        "warnings": warnings,
    }
