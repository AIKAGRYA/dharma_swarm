"""Read safe live-model result receipts for model-status projection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

TRANSIENT_LIVE_FAILURES = frozenset({"rate_limited"})


def merge_live_result(
    existing: dict[str, Any] | None,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    if existing is None:
        return candidate
    existing_status = str(existing.get("status", "")).strip()
    candidate_status = str(candidate.get("status", "")).strip()
    candidate_failure = str(candidate.get("failure_class") or "").strip()
    existing_failure = str(existing.get("failure_class") or "").strip()
    if candidate_status == "ok":
        return candidate
    if candidate_status == "failed" and candidate_failure in TRANSIENT_LIVE_FAILURES:
        return existing
    if existing_status == "failed" and existing_failure in TRANSIENT_LIVE_FAILURES:
        return candidate
    if existing_status == "failed":
        return candidate if candidate_status == "failed" else existing
    if candidate_status == "failed":
        return candidate
    return candidate


def _merge_live_result_items(
    results: dict[str, dict[str, Any]],
    items: Iterable[Any],
) -> None:
    for item in items:
        if not isinstance(item, dict):
            continue
        route = item.get("route")
        if isinstance(route, str) and route:
            results[route] = merge_live_result(results.get(route), item)


def _legacy_live_result_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    models = data.get("models")
    if not isinstance(models, list):
        return items
    for model in models:
        if not isinstance(model, dict):
            continue
        actual = model.get("actual_live_call")
        if isinstance(actual, dict):
            items.append(actual)
        actual_many = model.get("actual_live_calls")
        if isinstance(actual_many, list):
            items.extend(item for item in actual_many if isinstance(item, dict))
    return items


def _direct_live_probe_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    results = data.get("results")
    if not isinstance(results, list):
        return []
    return [item for item in results if isinstance(item, dict)]


def _resolve_live_artifact_path(raw: str, *, parent: Path) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    if path.exists():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    return parent / path


def load_live_call_results(
    target: Path | None,
    *,
    seen: set[Path] | None = None,
) -> dict[str, dict[str, Any]]:
    if target is None:
        return {}
    seen = seen or set()
    resolved = target.resolve()
    if resolved in seen:
        return {}
    seen.add(resolved)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    results: dict[str, dict[str, Any]] = {}
    _merge_live_result_items(results, _legacy_live_result_items(data))
    _merge_live_result_items(results, _direct_live_probe_items(data))

    artifacts = data.get("artifacts")
    if isinstance(artifacts, dict):
        for raw in artifacts.values():
            if not isinstance(raw, str) or not raw.strip().endswith(".json"):
                continue
            child = _resolve_live_artifact_path(raw, parent=target.parent)
            child_results = load_live_call_results(child, seen=seen)
            for route, item in child_results.items():
                results[route] = merge_live_result(results.get(route), item)
    return results


__all__ = [
    "TRANSIENT_LIVE_FAILURES",
    "load_live_call_results",
    "merge_live_result",
]
