"""Detector adapters — wrap external tools, emit unified Findings.

Each adapter is a callable that takes a list of paths and returns a
DetectorResult. Adapters MUST NOT mutate state outside their own
process; they MUST handle missing tools gracefully (return a
DetectorResult with exit_code != 0 and a useful error string).

Add a new adapter by:
  1. Subclass BaseAdapter or write a function returning DetectorResult
  2. Register it in REGISTRY below
  3. Confirm its DetectorFamily weight is in aggregate.FAMILY_WEIGHTS
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from dharma_swarm.slop.adapters.ai_slop_detector import run_ai_slop_detector
from dharma_swarm.slop.adapters.base import BaseAdapter, run_subprocess
from dharma_swarm.slop.adapters.spotlight_adapter import (
    probe_spotlight,
    run_spotlight,
)
from dharma_swarm.slop.adapters.vulture_adapter import run_vulture
from dharma_swarm.slop.models import DetectorResult

AdapterCallable = Callable[[Iterable[Path]], DetectorResult]

REGISTRY: dict[str, AdapterCallable] = {
    "vulture": run_vulture,
    "ai-slop-detector": run_ai_slop_detector,
    "sentry-spotlight": run_spotlight,
}


__all__ = [
    "AdapterCallable",
    "BaseAdapter",
    "REGISTRY",
    "probe_spotlight",
    "run_ai_slop_detector",
    "run_spotlight",
    "run_subprocess",
    "run_vulture",
]
