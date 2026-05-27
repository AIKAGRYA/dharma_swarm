"""Append-only external operator research log for Darshan Season 0."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from dharma_swarm.venture_cell.darshan.schema import ExternalOperatorObservation


def default_operator_log_path() -> Path:
    return (
        Path.home()
        / ".dharma"
        / "venture_cell"
        / "DARSHAN"
        / "external_operator_observations.jsonl"
    )


def append_operator_observation(
    observation: ExternalOperatorObservation,
    *,
    path: Path | None = None,
) -> Path:
    log_path = path or default_operator_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = observation.model_dump(mode="json")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")
    return log_path


def read_operator_observations(
    path: Path | None = None,
) -> list[ExternalOperatorObservation]:
    log_path = path or default_operator_log_path()
    if not log_path.exists():
        return []
    return list(_iter_operator_observations(log_path))


def _iter_operator_observations(path: Path) -> Iterable[ExternalOperatorObservation]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield ExternalOperatorObservation.model_validate(json.loads(line))
