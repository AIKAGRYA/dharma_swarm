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
from dharma_swarm.slop.adapters.dependency_cruiser_adapter import (
    run_dependency_cruiser,
)
from dharma_swarm.slop.adapters.eslint_adapter import run_eslint
from dharma_swarm.slop.adapters.fallow_adapter import run_fallow
from dharma_swarm.slop.adapters.grimp_adapter import run_grimp
from dharma_swarm.slop.adapters.jscpd_adapter import run_jscpd
from dharma_swarm.slop.adapters.knip_adapter import run_knip
from dharma_swarm.slop.adapters.oxlint_adapter import run_oxlint
from dharma_swarm.slop.adapters.semgrep_adapter import run_semgrep
from dharma_swarm.slop.adapters.spotlight_adapter import (
    probe_spotlight,
    run_spotlight,
)
from dharma_swarm.slop.adapters.tsc_adapter import run_tsc
from dharma_swarm.slop.adapters.vulture_adapter import run_vulture
from dharma_swarm.slop.models import DetectorResult

AdapterCallable = Callable[[Iterable[Path]], DetectorResult]

REGISTRY: dict[str, AdapterCallable] = {
    # Python detectors
    "vulture": run_vulture,
    "ai-slop-detector": run_ai_slop_detector,
    "grimp": run_grimp,
    "semgrep": run_semgrep,
    # Telemetry
    "sentry-spotlight": run_spotlight,
    # JS/TS detectors
    "fallow": run_fallow,
    "knip": run_knip,
    "jscpd": run_jscpd,
    "tsc": run_tsc,
    "dependency-cruiser": run_dependency_cruiser,
    "eslint": run_eslint,
    "oxlint": run_oxlint,
}


__all__ = [
    "AdapterCallable",
    "BaseAdapter",
    "REGISTRY",
    "probe_spotlight",
    "run_ai_slop_detector",
    "run_dependency_cruiser",
    "run_eslint",
    "run_fallow",
    "run_grimp",
    "run_jscpd",
    "run_knip",
    "run_oxlint",
    "run_semgrep",
    "run_spotlight",
    "run_subprocess",
    "run_tsc",
    "run_vulture",
]
