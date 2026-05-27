"""Append-only Polsia observation log for Darshan Season 0."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from dharma_swarm.venture_cell.darshan.schema import PolsiaObservation


def default_polsia_log_path() -> Path:
    return Path.home() / ".dharma" / "venture_cell" / "DARSHAN" / "polsia_observations.jsonl"


def append_observation(
    observation: PolsiaObservation,
    *,
    path: Path | None = None,
) -> Path:
    log_path = path or default_polsia_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = observation.model_dump(mode="json")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")
    return log_path


def read_observations(path: Path | None = None) -> list[PolsiaObservation]:
    log_path = path or default_polsia_log_path()
    if not log_path.exists():
        return []
    return list(_iter_observations(log_path))


def _iter_observations(path: Path) -> Iterable[PolsiaObservation]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield PolsiaObservation.model_validate(json.loads(line))
