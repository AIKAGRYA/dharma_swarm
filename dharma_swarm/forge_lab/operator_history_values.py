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
    return (
        list(value)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes))
        else []
    )


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
