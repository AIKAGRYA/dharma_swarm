"""Semantic outcome schema + diff engine for the differential oracle.

Outcomes are engine-agnostic dicts of SEMANTIC facts (final active agent,
receipt sequence, message-visibility sets, final state shape) — never raw
text dumps. Each scenario declares which fields the two engines must agree
on and which fields carry an ADJUDICATED deviation (a documented, deliberate
difference between dharma doctrine and LangGraph semantics). An undocumented
divergence is a finding that FAILS the oracle test; a documented one is
recorded in the diff report and passes.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_REPORT_PATH",
    "OracleDiff",
    "ScenarioSpec",
    "diff_outcomes",
    "write_report",
]

DEFAULT_REPORT_PATH = (
    Path.home() / ".dharma" / "oracle" / "langgraph_oracle_report.json"
)


@dataclass(frozen=True)
class ScenarioSpec:
    """One dual-run scenario: a name, the fields to compare, and the fields
    whose divergence is a documented deliberate deviation."""

    name: str
    kind: str  # "swarm" | "supervisor"
    compare_fields: tuple[str, ...]
    expected_divergences: dict[str, str] = field(default_factory=dict)
    notes: str = ""


@dataclass
class OracleDiff:
    scenario: str
    matched_fields: list[str]
    adjudicated_deviations: dict[str, dict[str, Any]]
    unexpected_divergences: dict[str, dict[str, Any]]

    @property
    def is_parity(self) -> bool:
        return not self.unexpected_divergences

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "matched_fields": list(self.matched_fields),
            "adjudicated_deviations": dict(self.adjudicated_deviations),
            "unexpected_divergences": dict(self.unexpected_divergences),
            "verdict": "PARITY" if self.is_parity else "UNEXPECTED_DIVERGENCE",
        }


def _canon(value: Any) -> Any:
    """JSON round-trip so tuples/lists and key order never masquerade as
    semantic differences."""
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def diff_outcomes(
    spec: ScenarioSpec,
    dharma: dict[str, Any],
    langgraph: dict[str, Any],
) -> OracleDiff:
    matched: list[str] = []
    adjudicated: dict[str, dict[str, Any]] = {}
    unexpected: dict[str, dict[str, Any]] = {}
    for field_name in spec.compare_fields:
        d_value = _canon(dharma.get(field_name))
        l_value = _canon(langgraph.get(field_name))
        if d_value == l_value:
            matched.append(field_name)
            continue
        entry = {"dharma": d_value, "langgraph": l_value}
        if field_name in spec.expected_divergences:
            entry["adjudication"] = spec.expected_divergences[field_name]
            adjudicated[field_name] = entry
        else:
            unexpected[field_name] = entry
    return OracleDiff(
        scenario=spec.name,
        matched_fields=matched,
        adjudicated_deviations=adjudicated,
        unexpected_divergences=unexpected,
    )


def report_path() -> Path:
    raw = os.environ.get("DHARMA_ORACLE_REPORT_PATH", "")
    return Path(raw).expanduser() if raw else DEFAULT_REPORT_PATH


def write_report(entries: list[dict[str, Any]], *, langgraph_version: str) -> Path:
    """Write the machine-readable diff report artifact (runtime artifact —
    lands under ~/.dharma/ by default, or wherever the CI job points it;
    never committed to git)."""
    target = report_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "report": "langgraph_differential_oracle",
        "track": "dharmagraph-engine-2026-07",
        "spec_section": "Phase 1",
        "langgraph_version": langgraph_version,
        "scenario_count": len(entries),
        "parity_count": sum(1 for e in entries if e["diff"]["verdict"] == "PARITY"),
        "scenarios": entries,
    }
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return target
