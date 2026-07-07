"""Taskbed validation/grade quality reporting."""
from __future__ import annotations

import calendar
import json
import time
from pathlib import Path
from contextlib import closing
from typing import Any, Iterable

from .taskbed_store import DEFAULT_DB, DEFAULT_GRADE_RECEIPT_ROOTS, DEFAULT_QUALITY_ROOT, connect, now_stamp

# Keep the rest of the quality helpers in the canonical taskbed ledger history.
def _read_json(path: Path | str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_div(numerator: float, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _parse_stamp_seconds(stamp: Any) -> float | None:
    text = str(stamp or "").strip()
    if not text:
        return None
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return float(calendar.timegm(time.strptime(text, fmt)))
        except ValueError:
            continue
    return None


def _duration_seconds(started_at: Any, finished_at: Any) -> float | None:
    start = _parse_stamp_seconds(started_at)
    finish = _parse_stamp_seconds(finished_at)
    if start is None or finish is None or finish < start:
        return None
    return round(finish - start, 1)


def _repo_from_task(task_id: str, task: dict[str, Any]) -> str:
    repo = str(task.get("repo") or task.get("repository") or "").strip().strip("/")
    if repo:
        return repo
    text = str(task_id or "")
    if text.startswith("pr::") and "#" in text:
        return text[len("pr::") :].split("#", 1)[0].strip()
    return "(unknown)"


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 1)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 1)


def _all_task_rows(*, db_path: Path | str = DEFAULT_DB, active_only: bool = True) -> list[dict[str, Any]]:
    query = """
        SELECT task_id, task_json, source, taskbed, contamination_state,
               provenance_json, created_at, active, max_uses_per_epoch
          FROM taskbed_tasks
    """
    if active_only:
        query += " WHERE active=1"
    query += " ORDER BY task_id ASC"
    with closing(connect(db_path)) as conn:
        rows = conn.execute(query).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["task"] = json.loads(item.pop("task_json"))
        item["provenance"] = json.loads(item.pop("provenance_json") or "{}")
        result.append(item)
    return result


def _iter_grade_receipts(roots: Iterable[Path | str]) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for root_value in roots:
        root = Path(root_value).expanduser()
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            receipt = _read_json(path)
            task_id = str(receipt.get("task_id") or "").strip()
            if not task_id:
                continue
            receipt["_source_path"] = str(path)
            receipts.append(receipt)
    return receipts


def _repo_summary(repo: str) -> dict[str, Any]:
    return {
        "repo": repo,
        "task_count": 0,
        "validated_count": 0,
        "validation_failed_count": 0,
        "validation_missing_receipt_count": 0,
        "validation_runtime_seconds": [],
        "grade_attempt_count": 0,
        "grade_resolved_count": 0,
        "grade_failed_count": 0,
        "grade_runtime_seconds": [],
        "grade_observed_task_ids": set(),
    }


def _finalize_repo_summary(summary: dict[str, Any]) -> dict[str, Any]:
    validation_runtimes = list(summary.pop("validation_runtime_seconds"))
    grade_runtimes = list(summary.pop("grade_runtime_seconds"))
    observed_task_ids = sorted(summary.pop("grade_observed_task_ids"))
    task_count = int(summary["task_count"])
    grade_attempts = int(summary["grade_attempt_count"])
    summary["validation_failure_rate"] = _safe_div(float(summary["validation_failed_count"]), task_count)
    summary["validation_missing_receipt_rate"] = _safe_div(
        float(summary["validation_missing_receipt_count"]), task_count
    )
    summary["validation_runtime"] = {
        "observed_count": len(validation_runtimes),
        "median_seconds": _median(validation_runtimes),
        "min_seconds": round(min(validation_runtimes), 1) if validation_runtimes else None,
        "max_seconds": round(max(validation_runtimes), 1) if validation_runtimes else None,
        "total_seconds": round(sum(validation_runtimes), 1),
        "source": "validation_receipt.started_at/finished_at",
    }
    summary["grade_failure_rate"] = _safe_div(float(summary["grade_failed_count"]), grade_attempts)
    summary["grade_runtime"] = {
        "observed_count": len(grade_runtimes),
        "median_seconds": _median(grade_runtimes),
        "min_seconds": round(min(grade_runtimes), 1) if grade_runtimes else None,
        "max_seconds": round(max(grade_runtimes), 1) if grade_runtimes else None,
        "total_seconds": round(sum(grade_runtimes), 1),
        "source": "grade_receipt.grade_seconds or started_at/finished_at",
    }
    summary["grade_coverage"] = {
        "observed_task_count": len(observed_task_ids),
        "task_count": task_count,
        "observed_task_rate": _safe_div(float(len(observed_task_ids)), task_count),
        "observed_task_ids": observed_task_ids,
    }
    return summary


def taskbed_quality_report(
    *,
    db_path: Path | str = DEFAULT_DB,
    active_only: bool = True,
    grade_receipt_roots: Iterable[Path | str] = DEFAULT_GRADE_RECEIPT_ROOTS,
) -> dict[str, Any]:
    """Return per-repo taskbed validation/grade quality and runtime evidence.

    Workstream 2's done-state requires failure rate and runtime per repo to be
    known.  The ledger already stores validated task payloads and validation
    receipt paths; this report derives per-repo metrics from those receipts plus
    any observed PR-suite/native grade receipts.  It does not infer missing
    timings: unavailable evidence is counted via coverage fields and left as
    ``None`` instead of guessed.
    """
    rows = _all_task_rows(db_path=db_path, active_only=active_only)
    by_repo: dict[str, dict[str, Any]] = {}
    task_to_repo: dict[str, str] = {}
    task_details: list[dict[str, Any]] = []

    for row in rows:
        task_id = str(row["task_id"])
        task = dict(row["task"])
        repo = _repo_from_task(task_id, task)
        task_to_repo[task_id] = repo
        summary = by_repo.setdefault(repo, _repo_summary(repo))
        summary["task_count"] += 1

        validation_path = str(task.get("validation_receipt") or "").strip()
        validation = _read_json(validation_path) if validation_path else {}
        status = str(validation.get("status") or task.get("validation_state") or "").strip()
        blockers = list(validation.get("blockers") or task.get("validator_blockers") or [])
        validated = status == "fail_to_pass_validated" and not blockers
        missing_receipt = bool(validation_path and not validation) or not validation_path
        if validated:
            summary["validated_count"] += 1
        else:
            summary["validation_failed_count"] += 1
        if missing_receipt:
            summary["validation_missing_receipt_count"] += 1
        duration = _duration_seconds(validation.get("started_at"), validation.get("finished_at"))
        if duration is not None:
            summary["validation_runtime_seconds"].append(duration)

        task_details.append(
            {
                "task_id": task_id,
                "repo": repo,
                "validation_status": status,
                "validation_receipt": validation_path,
                "validation_receipt_present": bool(validation),
                "validation_runtime_seconds": duration,
                "validation_blockers": blockers,
            }
        )

    grade_receipts = _iter_grade_receipts(grade_receipt_roots)
    for receipt in grade_receipts:
        task_id = str(receipt.get("task_id") or "").strip()
        repo = task_to_repo.get(task_id) or _repo_from_task(task_id, receipt)
        if repo not in by_repo:
            continue
        summary = by_repo[repo]
        summary["grade_attempt_count"] += 1
        summary["grade_observed_task_ids"].add(task_id)
        resolved = bool(receipt.get("resolved"))
        if resolved:
            summary["grade_resolved_count"] += 1
        else:
            summary["grade_failed_count"] += 1
        seconds_value = receipt.get("grade_seconds")
        runtime = None
        if seconds_value is not None:
            try:
                runtime = round(float(seconds_value), 1)
            except (TypeError, ValueError):
                runtime = None
        if runtime is None:
            runtime = _duration_seconds(receipt.get("started_at"), receipt.get("finished_at"))
        if runtime is not None:
            summary["grade_runtime_seconds"].append(runtime)

    per_repo = [_finalize_repo_summary(by_repo[key]) for key in sorted(by_repo)]
    total_tasks = len(rows)
    total_validated = sum(int(item["validated_count"]) for item in per_repo)
    total_grade_attempts = sum(int(item["grade_attempt_count"]) for item in per_repo)
    total_grade_resolved = sum(int(item["grade_resolved_count"]) for item in per_repo)
    total_grade_failed = sum(int(item["grade_failed_count"]) for item in per_repo)
    return {
        "schema": "forge_v2.taskbed_quality_report.v1",
        "generated_at": now_stamp(),
        "db_path": str(Path(db_path).expanduser()),
        "active_only": active_only,
        "task_count": total_tasks,
        "validated_count": total_validated,
        "validation_failure_rate": _safe_div(float(total_tasks - total_validated), total_tasks),
        "grade_attempt_count": total_grade_attempts,
        "grade_resolved_count": total_grade_resolved,
        "grade_failed_count": total_grade_failed,
        "grade_failure_rate": _safe_div(float(total_grade_failed), total_grade_attempts),
        "repo_count": len(per_repo),
        "per_repo": per_repo,
        "task_details": task_details,
        "grade_receipt_roots": [str(Path(root).expanduser()) for root in grade_receipt_roots],
        "source_of_truth_mutated": False,
        "official_score_claimed": False,
        "promotion_gate": "verify_promotion_only",
    }


def taskbed_quality_markdown(report: dict[str, Any]) -> str:
    def fmt(value: Any) -> str:
        return "n/a" if value is None else str(value)

    lines = [
        "# Taskbed quality report",
        "",
        f"- task_count: {report.get('task_count', 0)}",
        f"- validated_count: {report.get('validated_count', 0)}",
        f"- validation_failure_rate: {fmt(report.get('validation_failure_rate'))}",
        f"- grade_attempt_count: {report.get('grade_attempt_count', 0)}",
        f"- grade_failure_rate: {fmt(report.get('grade_failure_rate'))}",
        f"- repo_count: {report.get('repo_count', 0)}",
        "",
        "| repo | tasks | validated | validation failure | validation median sec | grade attempts | grade failure | grade median sec | grade coverage |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in report.get("per_repo", []):
        validation_runtime = item.get("validation_runtime", {})
        grade_runtime = item.get("grade_runtime", {})
        coverage = item.get("grade_coverage", {})
        lines.append(
            "| {repo} | {tasks} | {validated} | {vfail} | {vmed} | {gatt} | {gfail} | {gmed} | {gcov} |".format(
                repo=item.get("repo", ""),
                tasks=item.get("task_count", 0),
                validated=item.get("validated_count", 0),
                vfail=fmt(item.get("validation_failure_rate")),
                vmed=fmt(validation_runtime.get("median_seconds")),
                gatt=item.get("grade_attempt_count", 0),
                gfail=fmt(item.get("grade_failure_rate")),
                gmed=fmt(grade_runtime.get("median_seconds")),
                gcov=fmt(coverage.get("observed_task_rate")),
            )
        )
    lines.extend(
        [
            "",
            "Validation runtime is measured from validation receipt timestamps.",
            "Grade runtime is measured only when grade receipts expose grade_seconds or usable timestamps; coverage is explicit, not guessed.",
            "",
        ]
    )
    return "\n".join(lines)


def write_taskbed_quality_report(
    *,
    output_root: Path | str = DEFAULT_QUALITY_ROOT,
    db_path: Path | str = DEFAULT_DB,
    active_only: bool = True,
    grade_receipt_roots: Iterable[Path | str] = DEFAULT_GRADE_RECEIPT_ROOTS,
    label: str | None = None,
) -> dict[str, Any]:
    report = taskbed_quality_report(
        db_path=db_path,
        active_only=active_only,
        grade_receipt_roots=grade_receipt_roots,
    )
    stem = f"taskbed_quality_{label or now_stamp()}"
    root = Path(output_root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{stem}.json"
    md_path = root / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(taskbed_quality_markdown(report), encoding="utf-8")
    return {"report": report, "json_path": str(json_path), "markdown_path": str(md_path)}
