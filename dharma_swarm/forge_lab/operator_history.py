"""Build a human-first, read-only projection of Forge Lab run history.

Canonical run receipts remain under ``state/rsi_runs`` and the native evolution
archive.  This module writes only summaries, indexes, and symlinks into a
separate operator-facing directory.  It deliberately uses the standard library
so an archive can still be inspected when the broader runtime is unavailable.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any


VIEW_SCHEMA = "rsi_lab.operator_history_view.v1"
SCORECARD_SCHEMA = "rsi_lab.operator_run_scorecard.v1"
HISTORY_ROW_SCHEMA = "rsi_lab.operator_history_row.v1"
MARKER_NAME = ".rsi-operator-history"
METRIC_KEYS = (
    "verdict",
    "quality",
    "lineage",
    "evaluation",
    "usage",
    "provider",
    "runtime",
    "holdout",
    "provenance",
    "integrity",
)

_RUN_RE = re.compile(r"^(?P<prefix>rsi-(?P<kind>.+))-(?P<stamp>\d{8}T\d{6}Z)$")
_EXPERIMENT_RE = re.compile(r"exp_[A-Za-z0-9_]+")
_NATIVE_STAMP_RE = re.compile(r"_(?P<base>\d{8}T\d{6})(?P<tenth>\d)?(?:Z)?(?:_|$)")
_MINUTE_STAMP_RE = re.compile(r"(?P<base>\d{8}T\d{4})Z")
_DATE_RE = re.compile(r"(?P<base>20\d{6})")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.isdigit():
        return _parse_time(int(text))
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        for pattern in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d"):
            try:
                parsed = datetime.strptime(value.rstrip("Z"), pattern)
                break
            except ValueError:
                continue
        else:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _time_from_run_id(run_id: str) -> datetime | None:
    match = _RUN_RE.match(run_id)
    return _parse_time(match.group("stamp")) if match else None


def _time_from_experiment_id(experiment_id: str) -> datetime | None:
    match = _NATIVE_STAMP_RE.search(experiment_id)
    if match:
        parsed = _parse_time(match.group("base"))
        if parsed and match.group("tenth"):
            return parsed.replace(microsecond=int(match.group("tenth")) * 100_000)
        return parsed
    match = _MINUTE_STAMP_RE.search(experiment_id)
    if match:
        return _parse_time(match.group("base"))
    match = _DATE_RE.search(experiment_id)
    return _parse_time(match.group("base")) if match else None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []


def _get(data: Mapping[str, Any], *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
        return int(parsed) if parsed.is_integer() else parsed
    return None


def _sum_known(values: Iterable[Any]) -> int | float | None:
    known = [_number(value) for value in values]
    present = [value for value in known if value is not None]
    return sum(present) if present else None


def _slug(value: Any, *, fallback: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    text = text.split(":")[-1]
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or fallback


def _display_state(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value).replace("_", " ").strip()


def _short_sha(value: Any) -> str | None:
    text = str(value or "").strip()
    return text[:8] if text else None


def _identity_suffix(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:8]


def _format_count(value: Any) -> str:
    number = _number(value)
    return "unknown" if number is None else f"{number:,.0f}"


def _length(value: Any) -> int | None:
    return len(value) if value is not None else None


def _format_rate(value: Any) -> str:
    number = _number(value)
    return "unknown" if number is None else f"{float(number) * 100:.1f}%"


def _format_duration(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "unknown"
    seconds = max(0, int(round(float(number))))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def _read_json(path: Path, warnings: list[str], label: str) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        warnings.append(f"Could not read {label} at {path}: {type(exc).__name__}")
        return {}
    if not isinstance(value, Mapping):
        warnings.append(f"Expected an object in {label} at {path}")
        return {}
    return dict(value)


def _read_jsonl(path: Path, warnings: list[str], label: str) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        warnings.append(f"Could not read {label} at {path}: {type(exc).__name__}")
        return rows
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"Ignored malformed {label} row {index} at {path}")
            continue
        if isinstance(row, Mapping):
            rows.append(dict(row))
        else:
            warnings.append(f"Ignored non-object {label} row {index} at {path}")
    return rows


def _read_text(path: Path, warnings: list[str], label: str) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        warnings.append(f"Could not read {label} at {path}: {type(exc).__name__}")
        return ""


def _log_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", line.strip())
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def _models_from_manifest(manifest: Mapping[str, Any]) -> list[str]:
    config = _mapping(manifest.get("config"))
    seed = _mapping(manifest.get("seed_genome"))
    proposer = _mapping(manifest.get("proposer"))
    values = [
        config.get("solver_model"),
        config.get("generator_model"),
        config.get("verifier_model"),
        config.get("mutator_model"),
        seed.get("generator_model"),
        seed.get("verifier_model"),
        proposer.get("model"),
        proposer.get("route"),
    ]
    return sorted({str(value) for value in values if value})


def _load_experiment(path: Path) -> dict[str, Any]:
    warnings: list[str] = []
    manifest = _read_json(path / "run_manifest.json", warnings, "run manifest")
    closeout = _read_json(path / "closeout.json", warnings, "closeout")
    results = _read_jsonl(path / "results.jsonl", warnings, "result stream")
    experiment_id = str(
        _first(manifest.get("experiment_id"), closeout.get("experiment_id"), path.name)
    )
    started = _first(
        _parse_time(manifest.get("started_at")),
        _parse_time(manifest.get("created_at")),
        _parse_time(closeout.get("started_at")),
        _time_from_experiment_id(experiment_id),
    )
    finished = _first(
        _parse_time(closeout.get("finished_at")),
        _parse_time(closeout.get("created_at")),
    )
    config = _mapping(manifest.get("config"))
    git_sha = _first(
        manifest.get("git_base_sha"),
        _get(manifest, "runtime_code_identity", "git_sha"),
        _get(manifest, "safety", "code_identity", "git_sha"),
    )
    mode = manifest.get("mode")
    return {
        "experiment_id": experiment_id,
        "path": path.resolve(),
        "manifest": manifest,
        "closeout": closeout,
        "results": results,
        "started_at_dt": started,
        "finished_at_dt": finished,
        "git_sha": git_sha,
        "mode": mode,
        "models": _models_from_manifest(manifest),
        "benchmark": _first(manifest.get("benchmark"), config.get("benchmark")),
        "warnings": warnings,
    }


def _discover_experiments(state_root: Path) -> dict[str, dict[str, Any]]:
    archive = state_root / ".dharma" / "evolution_archive" / "agent_evolution"
    experiments: dict[str, dict[str, Any]] = {}
    if not archive.is_dir():
        return experiments
    for path in sorted(archive.iterdir()):
        if path.is_dir() and not path.name.startswith("._"):
            experiment = _load_experiment(path)
            experiments[experiment["experiment_id"]] = experiment
    return experiments


def _result_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    graded = [row for row in rows if row.get("state") == "graded"]
    task_rows = [
        task
        for row in graded
        for task in _sequence(row.get("per_task"))
        if isinstance(task, Mapping)
    ]
    solved = [task for task in task_rows if task.get("resolved") is True]
    empty = [task for task in task_rows if task.get("error") == "empty_patch"]
    budget_known = [
        _mapping(row.get("budget")).get("invalid")
        for row in graded
        if "invalid" in _mapping(row.get("budget"))
    ]
    valid = sum(value is False for value in budget_known) if budget_known else None
    candidate_ids = {str(row.get("candidate_id")) for row in graded if row.get("candidate_id")}
    child_ids = {
        str(row.get("candidate_id"))
        for row in graded
        if row.get("candidate_id") and row.get("parent_id")
    }
    parent_ids = {str(row.get("parent_id")) for row in graded if row.get("parent_id")}
    edges = {
        (str(row.get("parent_id")), str(row.get("candidate_id")))
        for row in graded
        if row.get("parent_id") and row.get("candidate_id")
    }
    generations = [_number(row.get("generation")) for row in graded]
    parent_metadata_complete = all("parent_id" in row for row in graded)
    return {
        "graded_rows": len(graded),
        "candidate_ids": candidate_ids,
        "child_ids": child_ids if parent_metadata_complete else None,
        "parent_ids": parent_ids if parent_metadata_complete else None,
        "edges": edges if parent_metadata_complete else None,
        "parent_metadata_complete": parent_metadata_complete if graded else None,
        "max_generation": max((int(value) for value in generations if value is not None), default=None),
        "task_observations": len(task_rows),
        "solved_observations": len(solved),
        "empty_patch_observations": len(empty),
        "task_ids": sorted({str(task.get("task_id")) for task in task_rows if task.get("task_id")}),
        "solved_task_ids": sorted(
            {str(task.get("task_id")) for task in solved if task.get("task_id")}
        ),
        "budget_valid_rows": valid,
        "budget_known_rows": len(budget_known),
    }


def _closeout_metric(experiment: Mapping[str, Any], key: str) -> Any:
    closeout = _mapping(experiment.get("closeout"))
    stats = _mapping(closeout.get("stats"))
    counters = _mapping(stats.get("counters"))
    aliases: dict[str, tuple[Any, ...]] = {
        "graded": (counters.get("graded"), closeout.get("graded_count"), closeout.get("graded")),
        "tokens": (stats.get("tokens_spent_total"), closeout.get("tokens_spent_total")),
        "seed": (stats.get("seed_pass_rate"), closeout.get("seed_pass_rate")),
        "best": (
            stats.get("best_pass_rate"),
            closeout.get("best_pass_rate"),
        ),
        "wall": (closeout.get("wall_seconds"),),
    }
    return _first(*aliases[key])


def _association_label(receipt_name: str) -> tuple[str, str]:
    labels = {
        "canary_attempt1_blocked": ("canary", "blocked"),
        "canary_attempt2_timeout": ("canary", "timeout-discarded"),
        "canary": ("canary", "accepted"),
        "screen_775": ("screen-primary-rng-775", "accepted"),
        "screen_3232_fallback": ("screen-fallback-rng-3232", "accepted"),
    }
    return labels.get(receipt_name, (_slug(receipt_name), "recorded"))


def _manager_associations(
    run_path: Path,
    experiments: Mapping[str, dict[str, Any]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    associations: list[dict[str, Any]] = []
    receipt_root = run_path / "experiments"
    if not receipt_root.is_dir():
        return associations
    phase_order = {
        "canary_attempt1_blocked": 1,
        "canary_attempt2_timeout": 2,
        "canary": 3,
        "screen_775": 4,
        "screen_3232_fallback": 5,
    }
    receipt_paths = sorted(
        receipt_root.glob("*.json"),
        key=lambda path: (phase_order.get(path.stem, 100), path.name),
    )
    for receipt_path in receipt_paths:
        receipt = _read_json(receipt_path, warnings, f"manager phase receipt {receipt_path.name}")
        experiment_id = receipt.get("experiment_id")
        if not experiment_id:
            continue
        label, disposition = _association_label(receipt_path.stem)
        experiment = experiments.get(str(experiment_id))
        if experiment is None:
            warnings.append(f"Manager phase {receipt_path.name} references missing {experiment_id}")
        associations.append(
            {
                "experiment_id": str(experiment_id),
                "experiment": experiment,
                "label": label,
                "disposition": disposition,
                "link_method": "explicit_phase_receipt",
                "confidence": "exact",
                "receipt_path": receipt_path.resolve(),
            }
        )
    return associations


def _inference_matches(
    run: Mapping[str, Any], experiment: Mapping[str, Any]
) -> bool:
    if run.get("kind") != "smoke":
        return False
    fields = _mapping(run.get("log_fields"))
    preset = str(fields.get("PRESET", ""))
    if "generations=2" not in preset or "children=1" not in preset or "tasks=3" not in preset:
        return False
    manifest = _mapping(experiment.get("manifest"))
    config = _mapping(manifest.get("config"))
    tasks = _first(config.get("tasks_per_generation"), config.get("task_count"))
    if (_number(config.get("generations")), _number(config.get("children")), _number(tasks)) != (2, 1, 3):
        return False
    run_sha = fields.get("REPO_HEAD")
    exp_sha = experiment.get("git_sha")
    return not run_sha or not exp_sha or str(run_sha) == str(exp_sha)


def _associate_runs(
    runs: list[dict[str, Any]], experiments: Mapping[str, dict[str, Any]]
) -> set[str]:
    linked: set[str] = set()
    for run in runs:
        if run["kind"] == "manager-4h":
            associations = _manager_associations(run["path"], experiments, run["warnings"])
        else:
            associations = []
            seen: set[str] = set()
            for experiment_id in _EXPERIMENT_RE.findall(run["log_text"]):
                if experiment_id in seen:
                    continue
                seen.add(experiment_id)
                experiment = experiments.get(experiment_id)
                if experiment is None:
                    run["warnings"].append(f"Log references missing native experiment {experiment_id}")
                associations.append(
                    {
                        "experiment_id": experiment_id,
                        "experiment": experiment,
                        "label": "native-experiment",
                        "disposition": "recorded",
                        "link_method": "explicit_operator_log",
                        "confidence": "exact",
                        "receipt_path": run.get("log_path"),
                    }
                )
        run["associations"] = associations
        linked.update(item["experiment_id"] for item in associations if item.get("experiment"))

    for run in runs:
        if run["associations"] or not run["log_text"]:
            continue
        started = run["started_at_dt"]
        candidates: list[tuple[float, dict[str, Any]]] = []
        for experiment_id, experiment in experiments.items():
            if experiment_id in linked or not _inference_matches(run, experiment):
                continue
            exp_started = experiment.get("started_at_dt")
            if not started or not exp_started:
                continue
            distance = abs((exp_started - started).total_seconds())
            if distance <= 5:
                candidates.append((distance, experiment))
        if len(candidates) != 1:
            continue
        experiment = candidates[0][1]
        run["associations"] = [
            {
                "experiment_id": experiment["experiment_id"],
                "experiment": experiment,
                "label": "native-experiment",
                "disposition": "recorded",
                "link_method": "inferred_timestamp_and_config",
                "confidence": "high",
                "receipt_path": None,
            }
        ]
        linked.add(experiment["experiment_id"])
        run["warnings"].append(
            f"Native link to {experiment['experiment_id']} is inferred from timestamp, source SHA, and config"
        )
    return linked


def _discover_runs(state_root: Path) -> list[dict[str, Any]]:
    run_root = state_root / "rsi_runs"
    runs: list[dict[str, Any]] = []
    if not run_root.is_dir():
        return runs
    for path in sorted(run_root.iterdir()):
        if not path.is_dir():
            continue
        match = _RUN_RE.match(path.name)
        if not match:
            continue
        warnings: list[str] = []
        log_path = run_root / f"{path.name}.log"
        if not log_path.is_file() and (path / "engine.log").is_file():
            log_path = path / "engine.log"
        log_text = _read_text(log_path, warnings, "operator log") if log_path.is_file() else ""
        fields = _log_fields(log_text)
        launcher_text = _read_text(path / "run.sh", warnings, "run launcher")
        if not launcher_text:
            launcher_text = _read_text(path / "loop.sh", warnings, "loop launcher")
        declared_mode_match = re.search(
            r"(?:MODE=|--mode[ =]+)([A-Za-z0-9_-]+)", launcher_text
        )
        started = _first(_parse_time(fields.get("START_UTC")), _time_from_run_id(path.name))
        runs.append(
            {
                "run_id": path.name,
                "kind": match.group("kind"),
                "path": path.resolve(),
                "log_path": log_path.resolve() if log_path.is_file() else None,
                "log_text": log_text,
                "log_fields": fields,
                "declared_mode": declared_mode_match.group(1) if declared_mode_match else None,
                "started_at_dt": started,
                "warnings": warnings,
                "associations": [],
            }
        )
    return runs


def _experiment_summary(association: Mapping[str, Any]) -> dict[str, Any]:
    experiment = _mapping(association.get("experiment"))
    closeout = _mapping(experiment.get("closeout"))
    results = _sequence(experiment.get("results"))
    counts = _result_counts([_mapping(row) for row in results])
    return {
        "experiment_id": association.get("experiment_id"),
        "label": association.get("label"),
        "disposition": association.get("disposition"),
        "link_method": association.get("link_method"),
        "confidence": association.get("confidence"),
        "closeout_state": closeout.get("closeout_state"),
        "started_at": _iso(experiment.get("started_at_dt")),
        "finished_at": _iso(experiment.get("finished_at_dt")),
        "graded_rows": _first(_closeout_metric(experiment, "graded"), counts["graded_rows"]),
        "seed_pass_rate": _closeout_metric(experiment, "seed"),
        "best_pass_rate": _closeout_metric(experiment, "best"),
        "reported_tokens": _closeout_metric(experiment, "tokens"),
        "wall_seconds": _closeout_metric(experiment, "wall"),
        "git_sha": experiment.get("git_sha"),
        "models": experiment.get("models", []),
        "source_path": str(experiment["path"]) if experiment.get("path") else None,
        "warnings": experiment.get("warnings", []),
    }


def _scorecard_for_run(run: dict[str, Any]) -> dict[str, Any]:
    warnings = list(run["warnings"])
    run_path: Path = run["path"]
    associations = run["associations"]
    experiments = [item["experiment"] for item in associations if item.get("experiment")]
    rows = [
        _mapping(row)
        for experiment in experiments
        for row in _sequence(experiment.get("results"))
    ]
    counts = _result_counts(rows)
    manager_result = _read_json(run_path / "protocol_result.json", warnings, "protocol result")
    prereg = _read_json(run_path / "preregistration.json", warnings, "preregistration")
    manager_closeout = _read_json(run_path / "manager_closeout.json", warnings, "manager closeout")
    supervisor = _read_json(run_path / "supervisor_closeout.json", warnings, "supervisor closeout")
    audit = _read_json(run_path / "postrun_audit.json", warnings, "post-run audit")

    closeout_states = [
        _get(experiment, "closeout", "closeout_state")
        for experiment in experiments
        if _get(experiment, "closeout", "closeout_state")
    ]
    if manager_result:
        verdict = manager_result.get("closeout_state")
    elif closeout_states:
        verdict = closeout_states[-1] if len(set(closeout_states)) == 1 else "mixed_native_closeouts"
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
    maximum_observed_pass_rate = max(observed_best_values) if observed_best_values else None

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
        unreported_failures = _number(_get(audit, "provider_trace", "failed_responses")) or 0
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
        next((experiment.get("mode") for experiment in experiments if experiment.get("mode")), None),
        run.get("declared_mode"),
        "dry" if "dry" in run["kind"] else None,
        "shadow" if experiments else None,
    )
    git_sha = _first(
        _get(prereg, "source", "head"),
        run["log_fields"].get("REPO_HEAD"),
        next((experiment.get("git_sha") for experiment in experiments if experiment.get("git_sha")), None),
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
        else _sum_known(_closeout_metric(experiment, "wall") for experiment in experiments)
    )

    provider_trace = _mapping(audit.get("provider_trace"))
    panel = _mapping(audit.get("panel_preservation"))
    screen = _mapping(audit.get("screen_summary"))
    winner = _get(manager_result, "winner")
    if winner is None and manager_result:
        winner = _get(_read_json(run_path / "screen_decision.json", warnings, "screen decision"), "winner")

    accepted_receipts = [
        _mapping(receipt) for receipt in _sequence(audit.get("native_receipts"))
    ]
    if accepted_receipts:
        merkle_values = [receipt.get("merkle_verified") for receipt in accepted_receipts]
        scratch_values = [receipt.get("scratch_removed") for receipt in accepted_receipts]
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
    if experiments and any(not _mapping(experiment.get("closeout")) for experiment in experiments):
        warnings.append("At least one linked native experiment has no closeout")
    if reported_tokens is not None:
        warnings.append("Actual provider cost is unknown; reported tokens are not billing telemetry")
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
    model_slug = _slug(models[0] if len(models) == 1 else "multi-model" if models else None, fallback="model-unknown")
    slug = f"{stamp}__{_slug(run['kind'])}__{_slug(mode, fallback='mode-unknown')}__{model_slug}"

    metrics = {
        "verdict": {
            "state": verdict,
            "display": _display_state(verdict),
            "winner": winner,
            "promotion": "none" if winner is None else "candidate-recorded",
            "claim_boundary": _first(manager_result.get("claim_boundary"), _get(prereg, "claim_boundary")),
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
            "accepted_graded_rows": accepted_counts["graded_rows"] if accepted_rows else None,
            "task_observations": accepted_counts["task_observations"] if accepted_rows else counts["task_observations"] if rows else None,
            "solved_observations": accepted_counts["solved_observations"] if accepted_rows else counts["solved_observations"] if rows else None,
            "empty_patch_observations": accepted_counts["empty_patch_observations"] if accepted_rows else counts["empty_patch_observations"] if rows else None,
            "unique_task_ids": accepted_counts["task_ids"] if accepted_rows else counts["task_ids"],
            "unique_solved_task_ids": accepted_counts["solved_task_ids"] if accepted_rows else counts["solved_task_ids"],
            "budget_valid_graded_rows": accepted_counts["budget_valid_rows"] if accepted_rows else counts["budget_valid_rows"],
            "budget_rows_with_known_validity": accepted_counts["budget_known_rows"] if accepted_rows else counts["budget_known_rows"],
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
            "independent_routes": _first(provider_trace.get("independent_routes"), _get(prereg, "provider", "independent_routes")),
            "logical_requests": _first(provider_trace.get("trace_rows"), usage.get("logical_requests")),
            "successful_requests": provider_trace.get("successful_responses"),
            "failed_requests": provider_trace.get("failed_responses"),
            "hidden_retries": provider_trace.get("hidden_retries"),
        },
        "runtime": {
            "started_at": _iso(started),
            "finished_at": _iso(finished),
            "operator_elapsed_seconds": elapsed,
            "active_wall_seconds": active_wall,
            "deadline_respected": _first(supervisor.get("deadline_respected"), _get(audit, "supervision", "deadline_respected")),
            "timed_out": _first(supervisor.get("timed_out"), _get(audit, "supervision", "timed_out")),
        },
        "holdout": {
            "planned_tasks": panel.get("preregistered_holdout_tasks"),
            "result_occurrences": panel.get("holdout_result_occurrences"),
            "used": _first(manager_result.get("holdout_used"), screen.get("holdout_used")),
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
            "association_methods": sorted({item["link_method"] for item in associations}),
        },
        "integrity": {
            "merkle_verified": all(value is True for value in merkle_values) if merkle_values else None,
            "scratch_removed": all(value is True for value in scratch_values) if scratch_values else None,
            "source_worktree_clean": _get(audit, "source", "worktree_clean"),
            "cleanup_warning_count": cleanup_warning_count,
            "complete_receipts": (
                bool(associations)
                and len(experiments) == len(associations)
                and all(_mapping(experiment.get("closeout")) for experiment in experiments)
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


def _scorecard_for_native(experiment: dict[str, Any]) -> dict[str, Any]:
    rows = [_mapping(row) for row in _sequence(experiment.get("results"))]
    counts = _result_counts(rows)
    started = experiment.get("started_at_dt")
    finished = experiment.get("finished_at_dt")
    closeout = _mapping(experiment.get("closeout"))
    seed = _number(_closeout_metric(experiment, "seed"))
    best = _number(_closeout_metric(experiment, "best"))
    models = list(experiment.get("models", []))
    verdict = closeout.get("closeout_state") or ("incomplete_no_closeout" if rows else "archive_tombstone")
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
        warnings.append(
            "QUALITY INVALID FOR LIFT: no graded row is budget-valid"
        )
    elif budget_state in {"partially_budget_invalid", "incomplete_budget_validity"}:
        warnings.append("Quality evidence is budget-qualified or has incomplete validity metadata")

    closeout_tokens = _closeout_metric(experiment, "tokens")
    partial_tokens = _sum_known(_get(row, "budget", "spent_tokens") for row in rows)
    reported_tokens = _first(closeout_tokens, partial_tokens)
    usage_scope = "native closeout" if closeout_tokens is not None else (
        "partial sum from native result-row budgets" if partial_tokens is not None else "unknown"
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
        "verdict": {"state": verdict, "display": _display_state(verdict), "winner": None, "promotion": None, "claim_boundary": None},
        "quality": {
            "seed_pass_rate": seed,
            "best_pass_rate": best,
            "absolute_lift": float(best) - float(seed) if seed is not None and best is not None else None,
            "aggregation": "single native experiment candidate-minus-seed delta",
            "quality_phase_count": 1 if seed is not None and best is not None else 0,
            "budget_evidence_state": budget_state,
            "headline_lift_valid": headline_lift_valid,
            "best_display": _format_rate(best),
        },
        "lineage": {"unique_candidate_ids": len(counts["candidate_ids"]) if rows else None, "unique_parent_ids": _length(counts["parent_ids"]) if rows else None, "unique_child_ids": _length(counts["child_ids"]) if rows else None, "unique_edges": _length(counts["edges"]) if rows else None, "parent_metadata_complete": counts["parent_metadata_complete"], "maximum_generation": counts["max_generation"]},
        "evaluation": {"native_experiment_ids": [experiment["experiment_id"]], "native_experiment_count": 1, "raw_graded_rows": graded_rows, "accepted_graded_rows": graded_rows, "task_observations": counts["task_observations"] if rows else None, "solved_observations": counts["solved_observations"] if rows else None, "empty_patch_observations": counts["empty_patch_observations"] if rows else None, "unique_task_ids": counts["task_ids"], "unique_solved_task_ids": counts["solved_task_ids"], "budget_valid_graded_rows": counts["budget_valid_rows"], "budget_rows_with_known_validity": counts["budget_known_rows"]},
        "usage": {"reported_tokens": reported_tokens, "prompt_tokens": None, "completion_tokens": None, "reported_token_cap": _get(experiment, "manifest", "config", "max_experiment_tokens"), "cap_fraction": None, "actual_cost_usd": None, "scope": usage_scope, "is_lower_bound": usage_is_lower_bound},
        "provider": {"models": models, "declared_route": None, "independent_routes": None, "logical_requests": None, "successful_requests": None, "failed_requests": None, "hidden_retries": None},
        "runtime": {"started_at": _iso(started), "finished_at": _iso(finished), "operator_elapsed_seconds": None, "active_wall_seconds": _closeout_metric(experiment, "wall"), "deadline_respected": None, "timed_out": None},
        "holdout": {"planned_tasks": None, "result_occurrences": None, "used": None, "reserve_tasks": None, "reserve_result_occurrences": None, "winner_frozen": None},
        "provenance": {"run_id": None, "source_git_sha": experiment.get("git_sha"), "source_git_sha8": _short_sha(experiment.get("git_sha")), "mode": experiment.get("mode"), "operator_session_path": None, "operator_log_path": None, "native_experiment_path": str(experiment["path"]), "association_methods": []},
        "integrity": {"merkle_verified": _get(closeout, "merkle", "verified"), "scratch_removed": _get(closeout, "scratch_worktree", "removed"), "source_worktree_clean": None, "cleanup_warning_count": None, "complete_receipts": bool(closeout), "warning_count": len(warnings)},
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


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _write_text(path: Path, content: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        if executable:
            path.chmod(0o755)
    finally:
        try:
            Path(temp_name).unlink()
        except FileNotFoundError:
            pass


def _safe_symlink(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(target)


def _scorecard_table(scorecard: Mapping[str, Any]) -> str:
    metrics = _mapping(scorecard.get("metrics"))
    quality = _mapping(metrics.get("quality"))
    lineage = _mapping(metrics.get("lineage"))
    evaluation = _mapping(metrics.get("evaluation"))
    usage = _mapping(metrics.get("usage"))
    provider = _mapping(metrics.get("provider"))
    runtime = _mapping(metrics.get("runtime"))
    holdout = _mapping(metrics.get("holdout"))
    provenance = _mapping(metrics.get("provenance"))
    integrity = _mapping(metrics.get("integrity"))
    verdict = _mapping(metrics.get("verdict"))
    models = ", ".join(str(item) for item in _sequence(provider.get("models"))) or "unknown"
    quality_text = f"{_format_rate(quality.get('seed_pass_rate'))} → {_format_rate(quality.get('best_pass_rate'))}"
    budget_state = quality.get("budget_evidence_state")
    if budget_state == "no_budget_valid_rows":
        quality_text += " — **INVALID FOR LIFT: 0 budget-valid rows**"
    elif budget_state in {"partially_budget_invalid", "incomplete_budget_validity"}:
        quality_text += " — **BUDGET-QUALIFIED / PARTIAL**"
    evaluation_text = (
        f"{_format_count(evaluation.get('solved_observations'))}/"
        f"{_format_count(evaluation.get('task_observations'))} passed observations"
    )
    calls = provider.get("logical_requests")
    calls_text = "unknown" if calls is None else f"{_format_count(calls)} ({_format_count(provider.get('successful_requests'))} ok / {_format_count(provider.get('failed_requests'))} failed)"
    usage_text = _format_count(usage.get("reported_tokens"))
    if usage.get("is_lower_bound") is True and usage_text != "unknown":
        usage_text = f"≥{usage_text}"
    return "\n".join(
        [
            "| # | Metric | Value |",
            "|---:|---|---|",
            f"| 1 | Verdict | **{_display_state(verdict.get('state'))}**; promotion: {_display_state(verdict.get('promotion'))} |",
            f"| 2 | Quality | {quality_text}; lift {_format_rate(quality.get('absolute_lift'))} |",
            f"| 3 | Lineage | {_format_count(lineage.get('unique_candidate_ids'))} unique candidates, {_format_count(lineage.get('unique_child_ids'))} descendants, depth {_format_count(lineage.get('maximum_generation'))} |",
            f"| 4 | Evaluation | {_format_count(evaluation.get('accepted_graded_rows'))} accepted graded rows; {evaluation_text} |",
            f"| 5 | Usage | {usage_text} reported tokens; actual USD **unknown** |",
            f"| 6 | Provider | {models}; calls {calls_text} |",
            f"| 7 | Runtime | {_format_duration(runtime.get('operator_elapsed_seconds'))} operator elapsed; {_format_duration(runtime.get('active_wall_seconds'))} active |",
            f"| 8 | Holdout | used: {_display_state(holdout.get('used'))}; results: {_format_count(holdout.get('result_occurrences'))} |",
            f"| 9 | Provenance | mode {_display_state(provenance.get('mode'))}; source `{provenance.get('source_git_sha8') or 'unknown'}` |",
            f"| 10 | Integrity | Merkle {_display_state(integrity.get('merkle_verified'))}; scratch removed {_display_state(integrity.get('scratch_removed'))}; warnings {_format_count(integrity.get('warning_count'))} |",
        ]
    )


def _run_readme(scorecard: Mapping[str, Any]) -> str:
    metrics = _mapping(scorecard.get("metrics"))
    verdict = _mapping(metrics.get("verdict"))
    warnings = _sequence(scorecard.get("warnings"))
    warning_section = "\n".join(f"- {warning}" for warning in warnings) or "- None recorded."
    return f"""# {scorecard.get('run_id') or scorecard.get('experiment_id')}

> Generated operator projection. Canonical receipts are linked, never replaced.

- **Started (UTC):** {scorecard.get('started_at') or 'unknown'}
- **Finished (UTC):** {scorecard.get('finished_at') or 'unknown'}
- **Verdict:** {_display_state(verdict.get('state'))}
- **Descriptive folder:** `{scorecard.get('slug')}`

## Ten-metric scorecard

{_scorecard_table(scorecard)}

## Warnings and evidence limits

{warning_section}

## Read next

- `SCORECARD.json` — machine-readable values and explicit nulls.
- `LINEAGE.md` — phases, retries, parents, and children.
- `SOURCE_ARTIFACTS.md` — canonical receipt locations and link confidence.
- `SOURCE_LINKS/` — symlinks only; raw artifacts are not copied here.
"""


def _lineage_markdown(scorecard: Mapping[str, Any]) -> str:
    experiments = _sequence(scorecard.get("experiments"))
    lines = [
        f"# Lineage and phases — {scorecard.get('run_id') or scorecard.get('experiment_id')}",
        "",
        "Native experiments are phases or attempts beneath the operator session, not separate top-level runs.",
        "",
        "| # | Label | Disposition | Native state | Graded | Score | Tokens | Experiment |",
        "|---:|---|---|---|---:|---:|---:|---|",
    ]
    if not experiments:
        lines.append("| — | — | — | — | — | — | — | No linked native experiment |")
    for index, item in enumerate(experiments, start=1):
        data = _mapping(item)
        lines.append(
            "| {index} | {label} | {disposition} | {state} | {graded} | {seed}→{best} | {tokens} | `{experiment_id}` |".format(
                index=index,
                label=data.get("label") or "native",
                disposition=data.get("disposition") or "unknown",
                state=_display_state(data.get("closeout_state")),
                graded=_format_count(data.get("graded_rows")),
                seed=_format_rate(data.get("seed_pass_rate")),
                best=_format_rate(data.get("best_pass_rate")),
                tokens=_format_count(data.get("reported_tokens")),
                experiment_id=data.get("experiment_id"),
            )
        )
    return "\n".join(lines) + "\n"


def _sources_markdown(scorecard: Mapping[str, Any]) -> str:
    provenance = _mapping(_get(scorecard, "metrics", "provenance"))
    lines = [
        f"# Canonical source artifacts — {scorecard.get('run_id') or scorecard.get('experiment_id')}",
        "",
        "> This directory is a projection. The paths below remain source truth.",
        "",
        f"- Operator session: `{provenance.get('operator_session_path') or 'none'}`",
        f"- Operator log: `{provenance.get('operator_log_path') or 'none'}`",
        f"- Native experiment: `{provenance.get('native_experiment_path') or 'see associations below'}`",
        f"- Source Git SHA: `{provenance.get('source_git_sha') or 'unknown'}`",
        "",
        "## Native associations",
        "",
        "| Experiment | Method | Confidence | Source path |",
        "|---|---|---|---|",
    ]
    experiments = _sequence(scorecard.get("experiments"))
    if not experiments:
        lines.append("| — | — | — | No linked native experiment |")
    for item in experiments:
        data = _mapping(item)
        lines.append(
            f"| `{data.get('experiment_id')}` | {data.get('link_method') or 'native-only'} | {data.get('confidence') or 'n/a'} | `{data.get('source_path') or 'missing'}` |"
        )
    return "\n".join(lines) + "\n"


def _history_row(scorecard: Mapping[str, Any], relative_path: str) -> dict[str, Any]:
    metrics = _mapping(scorecard.get("metrics"))
    return {
        "schema": HISTORY_ROW_SCHEMA,
        "run_id": scorecard.get("run_id"),
        "slug": scorecard.get("slug"),
        "started_at": scorecard.get("started_at"),
        "finished_at": scorecard.get("finished_at"),
        "kind": scorecard.get("kind"),
        "verdict": _get(metrics, "verdict", "state"),
        "seed_pass_rate": _get(metrics, "quality", "seed_pass_rate"),
        "best_pass_rate": _get(metrics, "quality", "best_pass_rate"),
        "graded_rows": _get(metrics, "evaluation", "accepted_graded_rows"),
        "task_observations": _get(metrics, "evaluation", "task_observations"),
        "reported_tokens": _get(metrics, "usage", "reported_tokens"),
        "actual_cost_usd": _get(metrics, "usage", "actual_cost_usd"),
        "models": _get(metrics, "provider", "models"),
        "mode": _get(metrics, "provenance", "mode"),
        "source_git_sha": _get(metrics, "provenance", "source_git_sha"),
        "warning_count": _get(metrics, "integrity", "warning_count"),
        "relative_path": relative_path,
    }


def _index_table(entries: Sequence[tuple[dict[str, Any], str]]) -> str:
    lines = [
        "| UTC start | Run | Verdict | Quality | Graded | Passed observations | Tokens | Elapsed | Model | Source |",
        "|---|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for scorecard, relative_path in entries:
        metrics = _mapping(scorecard["metrics"])
        model_values = _sequence(_get(metrics, "provider", "models"))
        model = ", ".join(str(item).split(":")[-1] for item in model_values) or "unknown"
        quality_display = _format_rate(_get(metrics, "quality", "best_pass_rate"))
        budget_state = _get(metrics, "quality", "budget_evidence_state")
        if quality_display != "unknown" and budget_state == "no_budget_valid_rows":
            quality_display += " — INVALID (0 budget-valid)"
        elif quality_display != "unknown" and _get(metrics, "quality", "headline_lift_valid") is False:
            quality_display += " ⚠ partial budget validity"
        token_display = _format_count(_get(metrics, "usage", "reported_tokens"))
        if _get(metrics, "usage", "is_lower_bound") is True and token_display != "unknown":
            token_display = f"≥{token_display}"
        solved = _get(metrics, "evaluation", "solved_observations")
        observations = _get(metrics, "evaluation", "task_observations")
        lines.append(
            "| {started} | [{run}]({path}/README.md) | {verdict} | {quality} | {graded} | {solved}/{observations} | {tokens} | {elapsed} | {model} | `{sha}` |".format(
                started=scorecard.get("started_at") or "undated",
                run=scorecard.get("run_id") or scorecard.get("experiment_id"),
                path=relative_path,
                verdict=_display_state(_get(metrics, "verdict", "state")),
                quality=quality_display,
                graded=_format_count(_get(metrics, "evaluation", "accepted_graded_rows")),
                solved=_format_count(solved),
                observations=_format_count(observations),
                tokens=token_display,
                elapsed=_format_duration(_get(metrics, "runtime", "operator_elapsed_seconds")),
                model=model,
                sha=_get(metrics, "provenance", "source_git_sha8") or "unknown",
            )
        )
    return "\n".join(lines)


def _write_scorecard_directory(
    root: Path,
    scorecard: dict[str, Any],
    source_run: Mapping[str, Any] | None,
) -> str:
    started = _parse_time(scorecard.get("started_at"))
    date = started.strftime("%Y-%m-%d") if started else "undated"
    relative = Path("runs" if source_run else "native-only") / date / str(scorecard["slug"])
    destination = root / relative
    if destination.exists():
        raise ValueError(f"Operator-history destination collision: {relative}")
    destination.mkdir(parents=True, exist_ok=True)
    _write_text(destination / "README.md", _run_readme(scorecard))
    _write_text(destination / "SCORECARD.json", _json_text(scorecard))
    _write_text(destination / "LINEAGE.md", _lineage_markdown(scorecard))
    _write_text(destination / "SOURCE_ARTIFACTS.md", _sources_markdown(scorecard))
    links = destination / "SOURCE_LINKS"
    links.mkdir(exist_ok=True)
    if source_run:
        _safe_symlink(Path(source_run["path"]), links / "operator-session")
        if source_run.get("log_path"):
            _safe_symlink(Path(source_run["log_path"]), links / "operator-log.log")
    experiments = _sequence(scorecard.get("experiments"))
    for index, item in enumerate(experiments, start=1):
        data = _mapping(item)
        if not data.get("source_path"):
            continue
        name = f"E{index:02d}__{_slug(data.get('label'), fallback='native')}__{_slug(data.get('disposition'), fallback='recorded')}"
        _safe_symlink(Path(str(data["source_path"])), links / name)
    if not source_run:
        native_path = _first(
            _get(scorecard, "metrics", "provenance", "native_experiment_path"),
            _get(scorecard, "metrics", "provenance", "operator_session_path"),
        )
        if not native_path and scorecard.get("_source_path"):
            native_path = scorecard["_source_path"]
        if native_path:
            _safe_symlink(Path(str(native_path)), links / "native-experiment")
    return relative.as_posix()


def _build_tree(
    target: Path,
    state_root: Path,
    generated_at: datetime,
) -> dict[str, Any]:
    experiments = _discover_experiments(state_root)
    runs = _discover_runs(state_root)
    linked = _associate_runs(runs, experiments)
    scorecards = [_scorecard_for_run(run) for run in runs]
    paired = sorted(
        zip(scorecards, runs, strict=True),
        key=lambda pair: _parse_time(pair[0].get("started_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    entries: list[tuple[dict[str, Any], str]] = []
    for scorecard, run in paired:
        relative = _write_scorecard_directory(target, scorecard, run)
        entries.append((scorecard, relative))

    native_only_entries: list[tuple[dict[str, Any], str]] = []
    for experiment_id, experiment in sorted(
        experiments.items(),
        key=lambda item: item[1].get("started_at_dt") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    ):
        if experiment_id in linked:
            continue
        scorecard = _scorecard_for_native(experiment)
        relative = _write_scorecard_directory(target, scorecard, None)
        native_only_entries.append((scorecard, relative))

    marker = {
        "schema": VIEW_SCHEMA,
        "purpose": "safe replacement marker for generated operator history",
    }
    _write_text(target / MARKER_NAME, _json_text(marker))
    readme = f"""# Read this first — RSI operator run history

This is a **regeneratable, read-only projection** of canonical Forge Lab receipts.
It exists outside the rotating `current` checkout so operators get stable,
obvious paths. Do not hand-edit generated files.

## Start here

- `LATEST/` — symlink to the newest operator session.
- `LATEST.md` — newest run's ten-metric scorecard.
- `LATEST_10.md` — fast comparison of the ten newest sessions.
- `ALL_RUNS.md` — every operator session, newest first.
- `runs/YYYY-MM-DD/` — dated, descriptive run folders.
- `native-only/` — imported or manual native experiments that cannot be honestly linked to an operator session.
- `history.v1.jsonl` — line-oriented machine-readable projection rows.

Folder names are sortable and descriptive:

`UTC-start__run-kind__mode__model`

Verdicts are kept inside each folder. Mode/model labels may become more specific
when missing receipts arrive, because this is a regenerated projection rather
than an immutable archive path.
Missing evidence stays `unknown`/`null`; it is never silently converted to zero.

## Refresh

```bash
/root/rsi-lab/current/repo/scripts/forge_lab/operator-history
```

Generated at {_iso(generated_at)} from `{state_root}`.
"""
    _write_text(target / "README_FIRST.md", readme)
    _write_text(
        target / "ALL_RUNS.md",
        "# All operator sessions\n\n" + _index_table(entries) + "\n",
    )
    _write_text(
        target / "LATEST_10.md",
        "# Ten newest operator sessions\n\n" + _index_table(entries[:10]) + "\n",
    )
    _write_text(
        target / "NATIVE_ONLY.md",
        "# Native-only and imported experiments\n\n"
        "These are deliberately separate because no trustworthy operator-session link exists.\n\n"
        + _index_table(native_only_entries)
        + "\n",
    )
    history_lines = [
        json.dumps(_history_row(scorecard, relative), sort_keys=True, ensure_ascii=False)
        for scorecard, relative in entries
    ]
    _write_text(target / "history.v1.jsonl", "\n".join(history_lines) + ("\n" if history_lines else ""))
    if entries:
        latest_scorecard, latest_relative = entries[0]
        _safe_symlink(Path(latest_relative), target / "LATEST")
        _write_text(
            target / "LATEST.md",
            f"# Latest operator session\n\n"
            f"Open [`{latest_scorecard['run_id']}`]({latest_relative}/README.md).\n\n"
            + _scorecard_table(latest_scorecard)
            + "\n",
        )
    else:
        _write_text(target / "LATEST.md", "# Latest operator session\n\nNo operator sessions found.\n")
    refresh = """#!/usr/bin/env bash
set -euo pipefail
exec /root/rsi-lab/current/repo/scripts/forge_lab/operator-history "$@"
"""
    _write_text(target / "REFRESH.sh", refresh, executable=True)
    manifest = {
        "schema": VIEW_SCHEMA,
        "generated_at": _iso(generated_at),
        "source_state_root": str(state_root),
        "operator_run_count": len(entries),
        "linked_native_experiment_count": len(linked),
        "native_experiment_count": len(experiments),
        "native_only_experiment_count": len(native_only_entries),
        "latest_run_id": entries[0][0]["run_id"] if entries else None,
        "metric_groups": list(METRIC_KEYS),
    }
    _write_text(target / "VIEW_MANIFEST.json", _json_text(manifest))
    return manifest


def _replace_generated_tree(staging: Path, output_root: Path) -> None:
    if output_root.is_symlink():
        raise ValueError(f"Refusing to replace symlink output root: {output_root}")
    if not output_root.exists():
        os.replace(staging, output_root)
        return
    marker = output_root / MARKER_NAME
    if not marker.is_file():
        raise ValueError(
            f"Refusing to replace non-generated directory without {MARKER_NAME}: {output_root}"
        )
    try:
        marker_payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Refusing to replace output with an invalid generated marker: {output_root}") from exc
    if not isinstance(marker_payload, Mapping) or marker_payload.get("schema") != VIEW_SCHEMA:
        raise ValueError(f"Refusing to replace output with an unrecognized generated marker: {output_root}")
    backup = output_root.parent / f".{output_root.name}.previous-{os.getpid()}"
    if backup.exists() or backup.is_symlink():
        raise ValueError(f"Refusing to overwrite stale backup: {backup}")
    os.replace(output_root, backup)
    try:
        os.replace(staging, output_root)
    except BaseException:
        os.replace(backup, output_root)
        raise
    shutil.rmtree(backup)


def build_operator_history(
    state_root: Path,
    output_root: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build and atomically install the operator-facing history projection."""

    state = Path(state_root).expanduser().resolve()
    requested_output = Path(output_root).expanduser().absolute()
    if requested_output.is_symlink():
        raise ValueError(f"Output root must not be a symlink: {requested_output}")
    output = requested_output.resolve(strict=False)
    if not state.is_dir():
        raise FileNotFoundError(f"State root does not exist: {state}")
    if output == state or state in output.parents or output in state.parents:
        raise ValueError("Output must be a second location outside the canonical state root")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.build-", dir=output.parent))
    try:
        manifest = _build_tree(staging, state, generated_at or _utc_now())
        _replace_generated_tree(staging, output)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="operator-history",
        description="build a human-first projection of Forge Lab run receipts",
    )
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = build_operator_history(args.state_root, args.output_root)
    print(
        "operator history refreshed: "
        f"{args.output_root} "
        f"runs={manifest['operator_run_count']} "
        f"native_only={manifest['native_only_experiment_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
