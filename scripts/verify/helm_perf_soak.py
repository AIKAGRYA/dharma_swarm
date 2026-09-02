#!/usr/bin/env python3
"""Compose a strict Helm P4 performance, soak, and rollback receipt.

The composer is deliberately incapable of launching Helm, calling tmux, using a
provider, or reaching the network.  A separate operator-controlled runner records
raw observations, including its explicit private tmux socket and rollback states.
This module validates those observations, calculates the fixed statistics, compares
them with an explicit baseline, and writes one immutable runtime artifact beneath
``~/.dharma``.

The provider timing in this package is an offline stub round trip.  It is useful as a
local bridge/UI regression oracle and is never labelled as live-provider evidence.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence
from uuid import uuid4


MEASUREMENT_SCHEMA_VERSION = "dharma.helm.perf_soak_measurement.v1"
BASELINE_SCHEMA_VERSION = "dharma.helm.perf_soak_baseline.v1"
REPORT_SCHEMA_VERSION = "dharma.helm.perf_soak_report.v1"
MAX_SOAK_DURATION_MS = 45 * 60 * 1000
MAX_SAMPLE_COUNT = 100_000
MAX_INPUT_BYTES = 8 * 1024 * 1024

_SOCKET_RE = re.compile(r"^CODEX_MANAGED_[A-Za-z0-9][A-Za-z0-9_-]*$")
_SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,127}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAMPLE_NAMES = (
    "boot_ms",
    "intent_parse_ms",
    "provider_turn_ms",
    "render_ms",
)
_LIMIT_NAMES = (
    "boot_ms_p95",
    "intent_parse_ms_p95",
    "provider_turn_ms_p95",
    "render_ms_p95",
    "soak_duration_ms",
    "journey_failures",
    "rss_peak_growth_bytes",
    "fd_peak_growth",
)
# What each sample actually measures. Names are wire-stable (v1 schema); the
# semantics travel with every report so a reader never mistakes a harness
# round trip for a pure component latency.
METRIC_SEMANTICS: dict[str, str] = {
    "boot_ms": "launcher start-to-return wall time on the private tmux socket",
    "intent_parse_ms": (
        "navigation intent round trip: Enter keypress (draft already typed and "
        "echoed) to first rendered frame change; includes tmux input latency, "
        "so an upper bound on parser latency, not pure parser time"
    ),
    "provider_turn_ms": "offline stub bridge turn: Enter to completion glyph; never a live provider",
    "render_ms": "F2 surface toggle: keypress to first rendered frame change",
}
_ROLLBACK_SHAPE = (
    (1, "stop", "live"),
    (2, "start", "stopped"),
    (3, "replay-valid", "live"),
)
_ROLLBACK_SUCCESS_STATES = ("stopped", "live", "replay_valid")
_ROLLBACK_OBSERVED_STATES = (
    frozenset({"stopped", "live", "unknown"}),
    frozenset({"live", "stopped", "unknown"}),
    frozenset({"replay_valid", "replay_invalid", "unknown"}),
)


class HarnessInputError(ValueError):
    """The supplied measurement, baseline, or output path is unsafe or ambiguous."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise HarnessInputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise HarnessInputError(f"non-standard JSON constant: {value}")


def load_json(path: Path) -> Any:
    """Read bounded strict JSON, rejecting duplicate keys and NaN/Infinity."""

    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise HarnessInputError(f"input exceeds {MAX_INPUT_BYTES} bytes: {path}")
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HarnessInputError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise HarnessInputError(f"invalid JSON in {path}: {exc.msg}") from exc


def _object(
    value: Any,
    *,
    label: str,
    fields: Sequence[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HarnessInputError(f"{label} must be a JSON object")
    expected = set(fields)
    actual = set(value)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        raise HarnessInputError(f"{label} missing field: {missing[0]}")
    if unexpected:
        raise HarnessInputError(f"{label} has unexpected field: {unexpected[0]}")
    if any(not isinstance(key, str) for key in value):
        raise HarnessInputError(f"{label} field names must be strings")
    return value


def _text(value: Any, *, label: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise HarnessInputError(f"{label} must be non-empty text up to {maximum} characters")
    if "\n" in value or "\r" in value or "\x00" in value:
        raise HarnessInputError(f"{label} must be one line without NUL")
    return value


def _number(value: Any, *, label: str, integer: bool = False) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        kind = "integer" if integer else "number"
        raise HarnessInputError(f"{label} must be a finite non-negative {kind}")
    if integer and not isinstance(value, int):
        raise HarnessInputError(f"{label} must be a finite non-negative integer")
    if not math.isfinite(value) or value < 0:
        kind = "integer" if integer else "number"
        raise HarnessInputError(f"{label} must be a finite non-negative {kind}")
    return value


def _timestamp(value: Any, *, label: str) -> str:
    text_value = _text(value, label=label, maximum=64)
    candidate = text_value[:-1] + "+00:00" if text_value.endswith("Z") else text_value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise HarnessInputError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HarnessInputError(f"{label} must include a timezone")
    return text_value


def _sample_array(value: Any, *, label: str) -> list[int | float]:
    if not isinstance(value, list) or not value:
        raise HarnessInputError(f"{label} must be a non-empty JSON array")
    if len(value) > MAX_SAMPLE_COUNT:
        raise HarnessInputError(f"{label} exceeds {MAX_SAMPLE_COUNT} samples")
    for index, item in enumerate(value):
        _number(item, label=f"{label}[{index}]")
    return value


def parse_measurement_payload(value: Any) -> dict[str, Any]:
    """Validate and detach one closed-schema raw measurement payload."""

    root = _object(
        value,
        label="measurement",
        fields=(
            "schema_version",
            "measurement_id",
            "captured_at",
            "clock",
            "tmux",
            "execution",
            "samples",
            "soak",
            "rollback",
        ),
    )
    if root["schema_version"] != MEASUREMENT_SCHEMA_VERSION:
        raise HarnessInputError(f"measurement schema_version must be {MEASUREMENT_SCHEMA_VERSION}")
    measurement_id = _text(root["measurement_id"], label="measurement_id", maximum=128)
    if not _ID_RE.fullmatch(measurement_id):
        raise HarnessInputError("measurement_id contains unsupported characters")
    _timestamp(root["captured_at"], label="captured_at")
    if root["clock"] != "perf_counter_ns":
        raise HarnessInputError("clock must be perf_counter_ns")

    tmux = _object(root["tmux"], label="tmux", fields=("socket", "session"))
    socket = _text(tmux["socket"], label="tmux.socket", maximum=128)
    if not _SOCKET_RE.fullmatch(socket):
        raise HarnessInputError("tmux.socket must be an explicit CODEX_MANAGED_* socket")
    session = _text(tmux["session"], label="tmux.session", maximum=128)
    if not _SESSION_RE.fullmatch(session):
        raise HarnessInputError("tmux.session contains unsupported characters")

    execution = _object(
        root["execution"],
        label="execution",
        fields=("offline", "network_attempted", "provider_mode"),
    )
    if (
        execution["offline"] is not True
        or execution["network_attempted"] is not False
        or execution["provider_mode"] != "offline_stub"
    ):
        raise HarnessInputError(
            "execution must be offline=true, network_attempted=false, provider_mode=offline_stub"
        )

    samples = _object(root["samples"], label="samples", fields=_SAMPLE_NAMES)
    for sample_name in _SAMPLE_NAMES:
        _sample_array(samples[sample_name], label=f"samples.{sample_name}")

    soak = _object(root["soak"], label="soak", fields=("duration_ms", "journeys"))
    duration_ms = _number(soak["duration_ms"], label="soak.duration_ms")
    if duration_ms <= 0:
        raise HarnessInputError("soak.duration_ms must be greater than zero")
    if duration_ms > MAX_SOAK_DURATION_MS:
        raise HarnessInputError("soak.duration_ms exceeds the hard 45-minute campaign cap")
    journeys = soak["journeys"]
    if not isinstance(journeys, list) or len(journeys) < 2:
        raise HarnessInputError("soak.journeys must contain at least two repeated journeys")
    if len(journeys) > MAX_SAMPLE_COUNT:
        raise HarnessInputError(f"soak.journeys exceeds {MAX_SAMPLE_COUNT} rows")
    for index, journey_value in enumerate(journeys, start=1):
        journey = _object(
            journey_value,
            label=f"soak.journeys[{index - 1}]",
            fields=("sequence", "ok", "rss_bytes", "fd_count"),
        )
        sequence = _number(
            journey["sequence"], label=f"soak.journeys[{index - 1}].sequence", integer=True
        )
        if sequence != index:
            raise HarnessInputError("journey sequence must be contiguous, unique, and start at 1")
        if not isinstance(journey["ok"], bool):
            raise HarnessInputError(f"soak.journeys[{index - 1}].ok must be boolean")
        _number(
            journey["rss_bytes"],
            label=f"soak.journeys[{index - 1}].rss_bytes",
            integer=True,
        )
        _number(
            journey["fd_count"],
            label=f"soak.journeys[{index - 1}].fd_count",
            integer=True,
        )

    rollback = _object(root["rollback"], label="rollback", fields=("steps",))
    steps = rollback["steps"]
    if not isinstance(steps, list) or len(steps) != len(_ROLLBACK_SHAPE):
        raise HarnessInputError("rollback steps must be exactly stop -> start -> replay-valid")
    for index, (step_value, expected) in enumerate(zip(steps, _ROLLBACK_SHAPE, strict=True)):
        step = _object(
            step_value,
            label=f"rollback.steps[{index}]",
            fields=(
                "sequence",
                "action",
                "input_state",
                "exit_code",
                "elapsed_ms",
                "observed_state",
            ),
        )
        sequence, action, input_state = expected
        if (
            step["sequence"] != sequence
            or step["action"] != action
            or step["input_state"] != input_state
        ):
            raise HarnessInputError("rollback steps must be exactly stop -> start -> replay-valid")
        _number(step["exit_code"], label=f"rollback.steps[{index}].exit_code", integer=True)
        _number(step["elapsed_ms"], label=f"rollback.steps[{index}].elapsed_ms")
        if step["observed_state"] not in _ROLLBACK_OBSERVED_STATES[index]:
            raise HarnessInputError(
                f"rollback.steps[{index}].observed_state is not valid for {action}"
            )

    return copy.deepcopy(dict(root))


def parse_baseline_payload(value: Any) -> dict[str, Any]:
    """Validate an explicit, immutable comparison baseline."""

    root = _object(
        value,
        label="baseline",
        fields=(
            "schema_version",
            "baseline_id",
            "recorded_at",
            "source",
            "limits",
            "require_rollback_success",
        ),
    )
    if root["schema_version"] != BASELINE_SCHEMA_VERSION:
        raise HarnessInputError(f"baseline schema_version must be {BASELINE_SCHEMA_VERSION}")
    baseline_id = _text(root["baseline_id"], label="baseline_id", maximum=128)
    if not _ID_RE.fullmatch(baseline_id):
        raise HarnessInputError("baseline_id contains unsupported characters")
    _timestamp(root["recorded_at"], label="baseline.recorded_at")
    _text(root["source"], label="baseline.source", maximum=512)
    limits = _object(root["limits"], label="baseline.limits", fields=_LIMIT_NAMES)
    for name in _LIMIT_NAMES:
        integer = name in {"journey_failures", "rss_peak_growth_bytes", "fd_peak_growth"}
        _number(limits[name], label=f"baseline.limits.{name}", integer=integer)
    if limits["soak_duration_ms"] > MAX_SOAK_DURATION_MS:
        raise HarnessInputError("baseline cannot weaken the hard 45-minute campaign cap")
    if root["require_rollback_success"] is not True:
        raise HarnessInputError("baseline.require_rollback_success must be true")
    return copy.deepcopy(dict(root))


def _p95(samples: Sequence[int | float]) -> float:
    """Return the deterministic nearest-rank 95th percentile."""

    ordered = sorted(float(sample) for sample in samples)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return round(ordered[index], 6)


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _rollback_success(steps: Sequence[Mapping[str, Any]]) -> bool:
    return all(
        step["exit_code"] == 0 and step["observed_state"] == expected_state
        for step, expected_state in zip(steps, _ROLLBACK_SUCCESS_STATES, strict=True)
    )


def build_report(
    *,
    measurement: Mapping[str, Any],
    baseline: Mapping[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Summarize one validated run and evaluate every fixed admission metric."""

    # Revalidation keeps callers from bypassing the schema helpers or mutating a
    # previously validated object before report composition.
    raw_measurement = parse_measurement_payload(measurement)
    raw_baseline = parse_baseline_payload(baseline)
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise HarnessInputError("generated_at must be timezone-aware")

    samples = raw_measurement["samples"]
    journeys = raw_measurement["soak"]["journeys"]
    rss_values = [journey["rss_bytes"] for journey in journeys]
    fd_values = [journey["fd_count"] for journey in journeys]
    rollback_success = _rollback_success(raw_measurement["rollback"]["steps"])
    summary: dict[str, int | float | bool] = {
        "boot_ms_p95": _p95(samples["boot_ms"]),
        "intent_parse_ms_p95": _p95(samples["intent_parse_ms"]),
        "provider_turn_ms_p95": _p95(samples["provider_turn_ms"]),
        "render_ms_p95": _p95(samples["render_ms"]),
        "soak_duration_ms": raw_measurement["soak"]["duration_ms"],
        "journey_count": len(journeys),
        "journey_failures": sum(not journey["ok"] for journey in journeys),
        "rss_initial_bytes": rss_values[0],
        "rss_peak_bytes": max(rss_values),
        "rss_final_bytes": rss_values[-1],
        "rss_peak_growth_bytes": max(rss_values) - rss_values[0],
        "rss_end_growth_bytes": rss_values[-1] - rss_values[0],
        "fd_initial": fd_values[0],
        "fd_peak": max(fd_values),
        "fd_final": fd_values[-1],
        "fd_peak_growth": max(fd_values) - fd_values[0],
        "fd_end_growth": fd_values[-1] - fd_values[0],
        "rollback_success": rollback_success,
    }

    limits = raw_baseline["limits"]
    comparisons = [
        {
            "metric": metric,
            "actual": summary[metric],
            "operator": "<=",
            "limit": limits[metric],
            "passed": summary[metric] <= limits[metric],
        }
        for metric in _LIMIT_NAMES
    ]
    comparisons.append(
        {
            "metric": "rollback_success",
            "actual": rollback_success,
            "operator": "==",
            "limit": raw_baseline["require_rollback_success"],
            "passed": rollback_success is raw_baseline["require_rollback_success"],
        }
    )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "state": "PASS" if all(row["passed"] for row in comparisons) else "FAIL",
        "authority": "MEASURED_LOCAL_ONLY",
        "provider_truth": "OFFLINE_STUB_NOT_LIVE_PROVIDER",
        "metric_semantics": dict(METRIC_SEMANTICS),
        "generated_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "measurement_sha256": _sha256_json(raw_measurement),
        "baseline_sha256": _sha256_json(raw_baseline),
        "tmux": copy.deepcopy(raw_measurement["tmux"]),
        "summary": summary,
        "comparisons": comparisons,
        "raw_measurement": raw_measurement,
        "baseline": raw_baseline,
    }


def validate_output_path(path: Path) -> Path:
    """Confine a new non-symlink JSON artifact to the current home ``.dharma``."""

    expanded = path.expanduser()
    if expanded.is_symlink():
        raise HarnessInputError("--output must not be a symlink")
    root = (Path.home() / ".dharma").resolve()
    resolved = expanded.resolve(strict=False)
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise HarnessInputError("--output must be beneath ~/.dharma") from exc
    if not relative.parts or resolved.suffix != ".json":
        raise HarnessInputError("--output must name a .json file beneath ~/.dharma")
    if resolved.exists():
        raise HarnessInputError("--output already exists; reports are write-once")
    return resolved


def write_report_once(path: Path, report: Mapping[str, Any]) -> None:
    """Publish bytes atomically without following or replacing an output link."""

    output = validate_output_path(path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Resolve again after directory creation to detect a parent-link race.
    output = validate_output_path(output)
    encoded = (
        json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary = output.parent / f".{output.name}.tmp-{uuid4().hex}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = None
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o600)
        try:
            os.link(temporary, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise HarnessInputError("--output already exists; reports are write-once") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurement", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        measurement = parse_measurement_payload(load_json(args.measurement))
        baseline = parse_baseline_payload(load_json(args.baseline))
        report = build_report(measurement=measurement, baseline=baseline)
        write_report_once(args.output, report)
    except (HarnessInputError, OSError) as exc:
        print(f"helm_perf_soak: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0 if report["state"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
