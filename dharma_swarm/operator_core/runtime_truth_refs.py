"""Read-only helpers for carrying runtime truth references across organs."""

from __future__ import annotations

from typing import Any


def runtime_ref_values(report: dict[str, Any], keys: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    _collect(report.get("runtime_truth_refs"), keys, values)
    _collect(report.get("runtime_truth"), keys, values)
    _collect(report.get("runtime_state"), keys, values)
    return tuple(sorted(set(values)))


def _collect(value: Any, keys: tuple[str, ...], values: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in keys:
                _append(item, values)
            else:
                _collect(item, keys, values)
        return
    if isinstance(value, list):
        for item in value:
            _collect(item, keys, values)


def _append(value: Any, values: list[str]) -> None:
    if isinstance(value, (str, int, float, bool)):
        cleaned = str(value).strip()
        if cleaned:
            values.append(cleaned)
        return
    if isinstance(value, list):
        for item in value:
            _append(item, values)
        return
    if isinstance(value, dict):
        for item in value.values():
            _append(item, values)
