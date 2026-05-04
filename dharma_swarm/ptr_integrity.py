"""Cheap PTR integrity artifact readers.

Expensive checks belong in ``scripts/ptr_integrity_probe.py``. Runtime code
should only read the small JSON artifacts produced out of band.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.ptr_metric import PTRPillar, conservative_lcb

DEFAULT_STATE_DIR = Path.home() / ".dharma"
DEFAULT_FRESHNESS_SECONDS = 24 * 60 * 60


def read_repo_integrity(
    state_dir: Path | None = None,
    *,
    freshness_seconds: float = DEFAULT_FRESHNESS_SECONDS,
    now: datetime | None = None,
) -> PTRPillar:
    """Read ``~/.dharma/meta/repo_integrity.json`` as a PTR pillar."""

    root = state_dir or DEFAULT_STATE_DIR
    return read_integrity_artifact(
        root / "meta" / "repo_integrity.json",
        pillar_name="repo_integrity",
        freshness_seconds=freshness_seconds,
        now=now,
    )


def read_governance_integrity(
    state_dir: Path | None = None,
    *,
    freshness_seconds: float = DEFAULT_FRESHNESS_SECONDS,
    now: datetime | None = None,
) -> PTRPillar:
    """Read ``~/.dharma/meta/governance_integrity.json`` as a PTR pillar."""

    root = state_dir or DEFAULT_STATE_DIR
    return read_integrity_artifact(
        root / "meta" / "governance_integrity.json",
        pillar_name="governance_integrity",
        freshness_seconds=freshness_seconds,
        now=now,
    )


def read_integrity_artifact(
    path: Path,
    *,
    pillar_name: str,
    freshness_seconds: float = DEFAULT_FRESHNESS_SECONDS,
    now: datetime | None = None,
) -> PTRPillar:
    """Read one integrity JSON artifact as a PTRPillar.

    Expected artifact shape is intentionally small:

    ``{"score": 0.0, "confidence": 0.0, "checks": [], "hard_failures": []}``
    """

    now = now or datetime.now(timezone.utc)
    if not path.exists():
        return PTRPillar(
            point=None,
            confidence=0.0,
            missing=True,
            evidence_refs=[str(path)],
            notes=[f"{pillar_name} artifact missing: {path}"],
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return PTRPillar(
            point=None,
            confidence=0.0,
            missing=True,
            evidence_refs=[str(path)],
            notes=[f"{pillar_name} artifact malformed: {path}"],
        )
    if not isinstance(payload, dict):
        return PTRPillar(
            point=None,
            confidence=0.0,
            missing=True,
            evidence_refs=[str(path)],
            notes=[f"{pillar_name} artifact malformed: {path}"],
        )

    score = _first_float(
        payload,
        "score",
        "integrity",
        pillar_name,
        "repo_integrity",
        "governance_integrity",
    )
    confidence = _first_float(payload, "confidence")
    if confidence is None:
        confidence = 1.0

    stale = _artifact_stale(path, payload, freshness_seconds=freshness_seconds, now=now)
    hard_failures = _as_list(payload.get("hard_failures"))
    if hard_failures and score is not None:
        score = min(float(score), 0.49)

    notes = _as_list(payload.get("notes"))
    flags = [str(item) for item in _as_list(payload.get("flags"))]
    skipped = _as_list(payload.get("skipped"))
    if skipped or confidence <= 0.0:
        if "low_coverage" not in flags:
            flags.append("low_coverage")
        notes.append(f"{pillar_name} artifact low coverage: {path}")
    if stale:
        notes.append(f"{pillar_name} artifact stale: {path}")
        confidence = min(confidence, 0.5)
    if hard_failures:
        notes.append(f"{pillar_name} hard failures: {len(hard_failures)}")

    evidence_refs = [str(path)]
    evidence_refs.extend(str(item) for item in _as_list(payload.get("evidence_refs")))

    return PTRPillar(
        point=score,
        lcb90=conservative_lcb(score, confidence),
        confidence=confidence,
        missing=score is None,
        stale=stale,
        evidence_refs=evidence_refs,
        notes=notes,
        flags=flags,
    )


def write_integrity_artifact(path: Path, payload: dict[str, Any]) -> bool:
    """Write an integrity artifact. Returns False on filesystem failure."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return False
    return True


def _artifact_stale(
    path: Path,
    payload: dict[str, Any],
    *,
    freshness_seconds: float,
    now: datetime,
) -> bool:
    timestamps: list[datetime] = []
    for key in ("computed_at", "timestamp"):
        parsed = _parse_iso(payload.get(key))
        if parsed is not None:
            timestamps.append(parsed)
    if not timestamps:
        try:
            timestamps.append(
                datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            )
        except OSError:
            return True
    newest = max(timestamps)
    return (now - newest).total_seconds() > freshness_seconds


def _first_float(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in payload:
            continue
        try:
            value = float(payload[key])
        except (TypeError, ValueError):
            continue
        return value
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


__all__ = [
    "read_governance_integrity",
    "read_integrity_artifact",
    "read_repo_integrity",
    "write_integrity_artifact",
]
