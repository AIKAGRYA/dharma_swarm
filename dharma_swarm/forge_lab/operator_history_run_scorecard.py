"""Construct evidence-qualified Forge Lab operator-history scorecards."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.operator_history_sources import (
    METRIC_KEYS,
    SCORECARD_SCHEMA,
    _closeout_metric,
    _display_state,
    _experiment_summary,
    _first,
    _format_count,
    _format_rate,
    _get,
    _iso,
    _length,
    _mapping,
    _number,
    _parse_time,
    _read_json,
    _result_counts,
    _sequence,
    _short_sha,
    _slug,
    _sum_known,
)


def _scorecard_for_run(run: dict[str, Any]) -> dict[str, Any]:
    warnings = list(run["warnings"])
    run_path: Path = run["path"]
    associations = run["associations"]
    experiments = [
        item["experiment"] for item in associations if item.get("experiment")
    ]
    rows = [
        _mapping(row)
        for experiment in experiments
        for row in _sequence(experiment.get("results"))
    ]
    counts = _result_counts(rows)
    manager_result = _read_json(
        run_path / "protocol_result.json", warnings, "protocol result"
    )
    prereg = _read_json(run_path / "preregistration.json", warnings, "preregistration")
    manager_closeout = _read_json(
        run_path / "manager_closeout.json", warnings, "manager closeout"
    )
    supervisor = _read_json(
        run_path / "supervisor_closeout.json", warnings, "supervisor closeout"
    )
    audit = _read_json(run_path / "postrun_audit.json", warnings, "post-run audit")

    closeout_states = [
        _get(experiment, "closeout", "closeout_state")
        for experiment in experiments
        if _get(experiment, "closeout", "closeout_state")
    ]
    if manager_result:
        verdict = manager_result.get("closeout_state")
    elif closeout_states:
        verdict = (
            closeout_states[-1]
            if len(set(closeout_states)) == 1
            else "mixed_native_closeouts"
        )
    elif experiments and counts["graded_rows"]:
        verdict = "incomplete_no_closeout"
    elif experiments:
        verdict = "incomplete_no_results"
    elif "END_UTC" in run["log_fields"] or "LOOP_END_UTC" in run["log_fields"]:
        verdict = "complete_dry_check"
    elif not run["log_text"]:
        verdict = "prepared_only_or_missing_log"
    else:
        verdict = "incomplete"

    accepted_ids: set[str] = set()
    for receipt in _sequence(_get(audit, "native_receipts")):
        if isinstance(receipt, Mapping) and receipt.get("experiment_id"):
            accepted_ids.add(str(receipt["experiment_id"]))
    loaded_associations = [item for item in associations if item.get("experiment")]
    if accepted_ids:
        accepted_experiments = [
            item["experiment"]
            for item in loaded_associations
            if item["experiment_id"] in accepted_ids
        ]
    else:
        accepted_experiments = [
            item["experiment"]
            for item in loaded_associations
            if item.get("disposition") in {"accepted", "recorded"}
        ]
    accepted_rows = [
        _mapping(row)
        for experiment in accepted_experiments
        for row in _sequence(experiment.get("results"))
    ]
    accepted_counts = _result_counts(accepted_rows)

    quality_pairs: list[dict[str, Any]] = []
    observed_best_values: list[int | float] = []
    for experiment in accepted_experiments:
        phase_seed = _number(_closeout_metric(experiment, "seed"))
        phase_best = _number(_closeout_metric(experiment, "best"))
        if phase_best is not None:
            observed_best_values.append(phase_best)
        if phase_seed is not None and phase_best is not None:
            quality_pairs.append(
                {
                    "experiment_id": experiment.get("experiment_id"),
                    "seed": phase_seed,
                    "best": phase_best,
                    "lift": float(phase_best) - float(phase_seed),
                    "finished_at": experiment.get("finished_at_dt"),
                }
            )
    selected_quality = max(
        quality_pairs,
        key=lambda pair: (
            pair["lift"],
            pair["finished_at"] or datetime.min.replace(tzinfo=timezone.utc),
        ),
        default=None,
    )
    seed_rate = selected_quality["seed"] if selected_quality else None
    best_rate = selected_quality["best"] if selected_quality else None
    best_same_phase_lift = selected_quality["lift"] if selected_quality else None
    maximum_observed_pass_rate = (
        max(observed_best_values) if observed_best_values else None
    )

    graded_for_budget = accepted_counts["graded_rows"] if accepted_rows else None
    known_budget_rows = accepted_counts["budget_known_rows"] if accepted_rows else 0
    valid_budget_rows = accepted_counts["budget_valid_rows"] if accepted_rows else None
    if not graded_for_budget:
        budget_evidence_state = "unknown"
        headline_lift_valid = None
    elif known_budget_rows != graded_for_budget:
        budget_evidence_state = "incomplete_budget_validity"
        headline_lift_valid = False
    elif valid_budget_rows == graded_for_budget:
        budget_evidence_state = "all_rows_budget_valid"
        headline_lift_valid = True
    elif valid_budget_rows == 0:
        budget_evidence_state = "no_budget_valid_rows"
        headline_lift_valid = False
    else:
        budget_evidence_state = "partially_budget_invalid"
        headline_lift_valid = False

    usage = _mapping(_first(manager_result.get("usage"), manager_closeout.get("usage")))
    closeout_tokens = _sum_known(
        _closeout_metric(experiment, "tokens") for experiment in accepted_experiments
    )
    partial_row_tokens = _sum_known(
        _get(row, "budget", "spent_tokens") for row in accepted_rows
    )
    reported_tokens = _first(
        usage.get("reported_tokens"),
        closeout_tokens,
        partial_row_tokens,
    )
    if usage:
        unreported_failures = (
            _number(_get(audit, "provider_trace", "failed_responses")) or 0
        )
        usage_scope = "full protocol provider trace, including discarded attempts"
        usage_is_lower_bound = bool(unreported_failures)
    elif closeout_tokens is not None:
        usage_scope = "accepted native closeout totals"
        usage_is_lower_bound = False
    elif partial_row_tokens is not None:
        usage_scope = "partial sum from accepted native result-row budgets"
        usage_is_lower_bound = True
    else:
        usage_scope = "unknown"
        usage_is_lower_bound = None
    token_cap = _get(prereg, "fuses", "reported_token_cap")

    models = sorted(
        {
            model
            for experiment in experiments
            for model in _sequence(experiment.get("models"))
            if model
        }
    )
    declared_route = _first(
        _get(audit, "provider_trace", "route"),
        _get(prereg, "provider", "route"),
    )
    if declared_route and not models:
        models = [str(declared_route)]
    mode_tokens = str(run["log_fields"].get("MODE", "")).split()
    log_mode = mode_tokens[0] if mode_tokens else None
    mode = _first(
        log_mode,
        next(
            (
                experiment.get("mode")
                for experiment in experiments
                if experiment.get("mode")
            ),
            None,
        ),
        run.get("declared_mode"),
        "dry" if "dry" in run["kind"] else None,
        "shadow" if experiments else None,
    )
    git_sha = _first(
        _get(prereg, "source", "head"),
        run["log_fields"].get("REPO_HEAD"),
        next(
            (
                experiment.get("git_sha")
                for experiment in experiments
                if experiment.get("git_sha")
            ),
            None,
        ),
    )

    finished_candidates = [
        _parse_time(manager_closeout.get("finished_at")),
        *[experiment.get("finished_at_dt") for experiment in experiments],
        _parse_time(run["log_fields"].get("END_UTC")),
        _parse_time(run["log_fields"].get("LOOP_END_UTC")),
    ]
    finished = max((value for value in finished_candidates if value), default=None)
    started = run["started_at_dt"]
    elapsed = (finished - started).total_seconds() if started and finished else None
    supervisor_started = _parse_time(supervisor.get("started_epoch"))
    supervisor_finished = _parse_time(supervisor.get("finished_epoch"))
    active_wall = (
        (supervisor_finished - supervisor_started).total_seconds()
        if supervisor_started and supervisor_finished
        else _sum_known(
            _closeout_metric(experiment, "wall") for experiment in experiments
        )
    )

    provider_trace = _mapping(audit.get("provider_trace"))
    panel = _mapping(audit.get("panel_preservation"))
    screen = _mapping(audit.get("screen_summary"))
    winner = _get(manager_result, "winner")
    if winner is None and manager_result:
        winner = _get(
            _read_json(run_path / "screen_decision.json", warnings, "screen decision"),
            "winner",
        )

    accepted_receipts = [
        _mapping(receipt) for receipt in _sequence(audit.get("native_receipts"))
    ]
    if accepted_receipts:
        merkle_values = [
            receipt.get("merkle_verified") for receipt in accepted_receipts
        ]
        scratch_values = [
            receipt.get("scratch_removed") for receipt in accepted_receipts
        ]
    else:
        merkle_values = [
            _get(experiment, "closeout", "merkle", "verified")
            for experiment in accepted_experiments
            if _mapping(experiment.get("closeout"))
        ]
        scratch_values = [
            _get(experiment, "closeout", "scratch_worktree", "removed")
            for experiment in accepted_experiments
            if _get(experiment, "closeout", "scratch_worktree") is not None
        ]
    cleanup_warning_count = _get(audit, "known_defect", "task_exception_warnings")

    if not associations:
        warnings.append("No native experiment is linked to this operator session")
    if experiments and any(
        not _mapping(experiment.get("closeout")) for experiment in experiments
    ):
        warnings.append("At least one linked native experiment has no closeout")
    if reported_tokens is not None:
        warnings.append(
            "Actual provider cost is unknown; reported tokens are not billing telemetry"
        )
    if budget_evidence_state == "no_budget_valid_rows":
        warnings.append(
            "QUALITY INVALID FOR LIFT: 0/"
            f"{_format_count(graded_for_budget)} graded rows were budget-valid; "
            "do not interpret the observed score change as progress"
        )
    elif budget_evidence_state == "partially_budget_invalid":
        warnings.append(
            "QUALITY PARTIALLY BUDGET-INVALID: only "
            f"{_format_count(valid_budget_rows)}/{_format_count(graded_for_budget)} "
            "graded rows were budget-valid"
        )
    elif budget_evidence_state == "incomplete_budget_validity":
        warnings.append(
            "QUALITY BUDGET VALIDITY INCOMPLETE: not every graded row records a validity decision"
        )
    if _number(cleanup_warning_count):
        warnings.append(
            f"Post-response HTTP client cleanup emitted {_format_count(cleanup_warning_count)} task warnings"
        )
    warnings.extend(
        warning
        for experiment in experiments
        for warning in _sequence(experiment.get("warnings"))
    )
    warnings = list(dict.fromkeys(str(warning) for warning in warnings if warning))

    stamp = started.strftime("%Y-%m-%dT%H%M%SZ") if started else "undated"
    model_slug = _slug(
        models[0] if len(models) == 1 else "multi-model" if models else None,
        fallback="model-unknown",
    )
    slug = f"{stamp}__{_slug(run['kind'])}__{_slug(mode, fallback='mode-unknown')}__{model_slug}"

    metrics = {
        "verdict": {
            "state": verdict,
            "display": _display_state(verdict),
            "winner": winner,
            "promotion": "none" if winner is None else "candidate-recorded",
            "claim_boundary": _first(
                manager_result.get("claim_boundary"), _get(prereg, "claim_boundary")
            ),
        },
        "quality": {
            "seed_pass_rate": seed_rate,
            "best_pass_rate": best_rate,
            "absolute_lift": best_same_phase_lift,
            "aggregation": "single phase with maximum candidate-minus-seed delta",
            "selected_experiment_id": (
                selected_quality["experiment_id"] if selected_quality else None
            ),
            "maximum_observed_pass_rate": maximum_observed_pass_rate,
            "quality_phase_count": len(quality_pairs),
            "budget_evidence_state": budget_evidence_state,
            "headline_lift_valid": headline_lift_valid,
            "best_display": _format_rate(best_rate),
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
            "native_experiment_ids": [item["experiment_id"] for item in associations],
            "native_experiment_count": len(associations),
            "raw_graded_rows": counts["graded_rows"] if rows else None,
            "accepted_graded_rows": accepted_counts["graded_rows"]
            if accepted_rows
            else None,
            "task_observations": accepted_counts["task_observations"]
            if accepted_rows
            else counts["task_observations"]
            if rows
            else None,
            "solved_observations": accepted_counts["solved_observations"]
            if accepted_rows
            else counts["solved_observations"]
            if rows
            else None,
            "empty_patch_observations": accepted_counts["empty_patch_observations"]
            if accepted_rows
            else counts["empty_patch_observations"]
            if rows
            else None,
            "unique_task_ids": accepted_counts["task_ids"]
            if accepted_rows
            else counts["task_ids"],
            "unique_solved_task_ids": accepted_counts["solved_task_ids"]
            if accepted_rows
            else counts["solved_task_ids"],
            "budget_valid_graded_rows": accepted_counts["budget_valid_rows"]
            if accepted_rows
            else counts["budget_valid_rows"],
            "budget_rows_with_known_validity": accepted_counts["budget_known_rows"]
            if accepted_rows
            else counts["budget_known_rows"],
        },
        "usage": {
            "reported_tokens": reported_tokens,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "reported_token_cap": token_cap,
            "cap_fraction": (
                float(reported_tokens) / float(token_cap)
                if _number(reported_tokens) is not None and _number(token_cap)
                else None
            ),
            "actual_cost_usd": None,
            "scope": usage_scope,
            "is_lower_bound": usage_is_lower_bound,
        },
        "provider": {
            "models": models,
            "declared_route": declared_route,
            "independent_routes": _first(
                provider_trace.get("independent_routes"),
                _get(prereg, "provider", "independent_routes"),
            ),
            "logical_requests": _first(
                provider_trace.get("trace_rows"), usage.get("logical_requests")
            ),
            "successful_requests": provider_trace.get("successful_responses"),
            "failed_requests": provider_trace.get("failed_responses"),
            "hidden_retries": provider_trace.get("hidden_retries"),
        },
        "runtime": {
            "started_at": _iso(started),
            "finished_at": _iso(finished),
            "operator_elapsed_seconds": elapsed,
            "active_wall_seconds": active_wall,
            "deadline_respected": _first(
                supervisor.get("deadline_respected"),
                _get(audit, "supervision", "deadline_respected"),
            ),
            "timed_out": _first(
                supervisor.get("timed_out"), _get(audit, "supervision", "timed_out")
            ),
        },
        "holdout": {
            "planned_tasks": panel.get("preregistered_holdout_tasks"),
            "result_occurrences": panel.get("holdout_result_occurrences"),
            "used": _first(
                manager_result.get("holdout_used"), screen.get("holdout_used")
            ),
            "reserve_tasks": panel.get("untouched_reserve_tasks"),
            "reserve_result_occurrences": panel.get("reserve_result_occurrences"),
            "winner_frozen": panel.get("frozen_candidate_file_exists"),
        },
        "provenance": {
            "run_id": run["run_id"],
            "source_git_sha": git_sha,
            "source_git_sha8": _short_sha(git_sha),
            "mode": mode,
            "operator_session_path": str(run_path),
            "operator_log_path": str(run["log_path"]) if run.get("log_path") else None,
            "association_methods": sorted(
                {item["link_method"] for item in associations}
            ),
        },
        "integrity": {
            "merkle_verified": all(value is True for value in merkle_values)
            if merkle_values
            else None,
            "scratch_removed": all(value is True for value in scratch_values)
            if scratch_values
            else None,
            "source_worktree_clean": _get(audit, "source", "worktree_clean"),
            "cleanup_warning_count": cleanup_warning_count,
            "complete_receipts": (
                bool(associations)
                and len(experiments) == len(associations)
                and all(
                    _mapping(experiment.get("closeout")) for experiment in experiments
                )
            ),
            "warning_count": len(warnings),
        },
    }
    assert tuple(metrics) == METRIC_KEYS
    return {
        "schema": SCORECARD_SCHEMA,
        "run_id": run["run_id"],
        "slug": slug,
        "started_at": _iso(started),
        "finished_at": _iso(finished),
        "kind": run["kind"],
        "metrics": metrics,
        "experiments": [_experiment_summary(item) for item in associations],
        "warnings": warnings,
    }
