"""Parse and associate canonical Forge Lab receipts for operator history."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
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
