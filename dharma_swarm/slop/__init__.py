"""Dharma Code Quality Governance — slop verification package.

Three layers:
  1. Detector adapters (dharma_swarm.slop.adapters) — wrap external tools, emit unified Findings
  2. Aggregate (dharma_swarm.slop.aggregate) — noisy-OR + agreement-cap cross-validator
  3. Router (dharma_swarm.slop.router) — threshold-based action routing

CLI entry point: scripts/governance/slop_verify.py
Schema source: dharma_swarm.slop.models
"""

from dharma_swarm.slop.models import (
    DetectorFamily,
    DetectorResult,
    Finding,
    ModuleScore,
    Severity,
    SlopLedgerEntry,
)

__all__ = [
    "DetectorFamily",
    "DetectorResult",
    "Finding",
    "ModuleScore",
    "Severity",
    "SlopLedgerEntry",
]
