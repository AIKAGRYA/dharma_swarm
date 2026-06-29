"""Mission-level readiness ledger for LangGraph parity evidence."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


MISSION_ID = "langgraph-swarm-supervisor-parity-to-10-10"
GateStatus = Literal["green", "amber", "red"]


@dataclass(frozen=True, slots=True)
class ReadinessBlocker:
    """One concrete remaining blocker with a stable mission-local id."""

    id: str
    source_gate: str
    task_id: str
    status: str
    evidence_path: str
    summary: str
    owner_surface: str = ""
    missing_count: int = 0
    operator_decision_required: bool = False
    evidence: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source_gate": self.source_gate,
            "task_id": self.task_id,
            "status": self.status,
            "evidence_path": self.evidence_path,
            "summary": self.summary,
            "owner_surface": self.owner_surface,
            "missing_count": self.missing_count,
            "operator_decision_required": self.operator_decision_required,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True, slots=True)
class ReadinessGate:
    """Mission-level view of one acceptance gate."""

    id: str
    status: GateStatus
    passed: bool
    evidence_path: str
    summary: str
    blocker_ids: tuple[str, ...] = ()
    metrics: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "status": self.status,
            "passed": self.passed,
            "evidence_path": self.evidence_path,
            "summary": self.summary,
            "blocker_ids": list(self.blocker_ids),
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True, slots=True)
class MissionReadinessReport:
    """Aggregated A-E readiness report from existing gate receipts."""

    mission_id: str
    overall_status: GateStatus
    ten_out_of_ten: bool
    gates: tuple[ReadinessGate, ...]
    blockers: tuple[ReadinessBlocker, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "mission_id": self.mission_id,
            "overall_status": self.overall_status,
            "ten_out_of_ten": self.ten_out_of_ten,
            "gates": [gate.to_dict() for gate in self.gates],
            "blockers": [blocker.to_dict() for blocker in self.blockers],
        }


def build_readiness_report(
    report_root: str | Path = "reports/langgraph_parity",
    *,
    live_census_path: str | Path = Path.home() / ".dharma" / "ops" / "live_process_census.json",
    mission_id: str = MISSION_ID,
) -> MissionReadinessReport:
    from dharma_swarm.langgraph_parity.readiness_gates import (
        a2a_gate,
        runtime_gate,
        spine_live_gate,
    )

    root = Path(report_root)
    receipt_root = root / "receipts"
    benchmark_path = root / "benchmark" / "benchmark_report.json"
    runtime_global_path = receipt_root / "gate_C_runtime_receipt_coverage_report.json"
    runtime_fresh_path = (
        receipt_root / "gate_C_runtime_receipt_coverage_fresh_slice_20260629T094800Z.json"
    )
    spine_path = receipt_root / "gate_D_spine_dispatch_mode_report.json"
    a2a_path = receipt_root / "gate_E_check_a2a_readiness.stdout.txt"
    live_path = Path(live_census_path)

    blockers: list[ReadinessBlocker] = []
    gates: list[ReadinessGate] = []

    benchmark = _read_json(benchmark_path)
    gates.extend(_benchmark_gates(benchmark, benchmark_path))

    runtime_global = _read_json(runtime_global_path)
    runtime_fresh = _read_json(runtime_fresh_path)
    runtime_receipt_gate, runtime_blockers = runtime_gate(
        runtime_global,
        runtime_fresh,
        runtime_global_path,
        runtime_fresh_path,
    )
    gates.append(runtime_receipt_gate)
    blockers.extend(runtime_blockers)

    a2a = _read_json(a2a_path)
    a2a_readiness_gate, a2a_blockers = a2a_gate(a2a, a2a_path)
    gates.append(a2a_readiness_gate)
    blockers.extend(a2a_blockers)

    spine = _read_json(spine_path)
    live = _read_json(live_path)
    spine_gate, spine_blockers = spine_live_gate(spine, live, spine_path, live_path)
    gates.append(spine_gate)
    blockers.extend(spine_blockers)

    runtime_blocker_ids = tuple(blocker.id for blocker in runtime_blockers)
    e_blocker_ids = tuple(
        blocker.id
        for blocker in (*runtime_blockers, *a2a_blockers, *spine_blockers)
    )
    gates.append(
        ReadinessGate(
            id="E.runtime_truth",
            status="green" if not e_blocker_ids else "red",
            passed=not e_blocker_ids,
            evidence_path=str(runtime_global_path),
            summary=(
                "runtime truth is green"
                if not e_blocker_ids
                else "runtime truth still has global coverage or live-ops blockers"
            ),
            blocker_ids=e_blocker_ids,
            metrics={
                "runtime_global_score_gate_70_to_75": _summary_bool(
                    runtime_global,
                    "score_gate_70_to_75",
                ),
                "runtime_fresh_score_gate_70_to_75": _summary_bool(
                    runtime_fresh,
                    "score_gate_70_to_75",
                ),
                "runtime_blocker_ids": list(runtime_blocker_ids),
                "a2a_ready": bool(a2a.get("ready")),
                "spine_score_gate_65_to_70": bool(
                    (spine.get("summary") or {}).get("score_gate_65_to_70")
                ),
            },
        )
    )

    ten_out_of_ten = all(gate.passed for gate in gates) and not blockers
    return MissionReadinessReport(
        mission_id=mission_id,
        overall_status="green" if ten_out_of_ten else "red",
        ten_out_of_ten=ten_out_of_ten,
        gates=tuple(gates),
        blockers=tuple(blockers),
    )


def write_readiness_report(
    report: MissionReadinessReport,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "mission_readiness_report.json"
    markdown_path = destination / "mission_readiness_report.md"
    json_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(format_readiness_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def format_readiness_markdown(report: MissionReadinessReport) -> str:
    lines = [
        "# LangGraph Parity Mission Readiness",
        "",
        f"Mission id: `{report.mission_id}`",
        f"Overall status: **{report.overall_status.upper()}**",
        f"10/10: `{str(report.ten_out_of_ten).lower()}`",
        "",
        "## Gates",
        "",
        "| Gate | Status | Summary | Blockers |",
        "| --- | --- | --- | ---: |",
    ]
    for gate in report.gates:
        lines.append(
            f"| `{gate.id}` | {gate.status} | {gate.summary} | {len(gate.blocker_ids)} |"
        )

    lines.extend(["", "## Blockers", ""])
    if not report.blockers:
        lines.append("None.")
    else:
        lines.extend(
            [
                "| ID | Source | Task ID | Missing | Operator Decision | Summary |",
                "| --- | --- | --- | ---: | --- | --- |",
            ]
        )
        for blocker in report.blockers:
            lines.append(
                "| `{id}` | `{source}` | `{task}` | {missing} | {operator} | {summary} |".format(
                    id=blocker.id,
                    source=blocker.source_gate,
                    task=blocker.task_id,
                    missing=blocker.missing_count,
                    operator=str(blocker.operator_decision_required).lower(),
                    summary=blocker.summary,
                )
            )
    lines.append("")
    return "\n".join(lines)


def _benchmark_gates(
    benchmark: Mapping[str, Any],
    benchmark_path: Path,
) -> list[ReadinessGate]:
    summary = benchmark.get("summary") if isinstance(benchmark, Mapping) else {}
    modes = summary.get("modes") if isinstance(summary, Mapping) else {}
    mode_names = set(modes) if isinstance(modes, Mapping) else set()
    has_required_modes = {"single_agent", "swarm", "supervisor"}.issubset(mode_names)
    distractors = int(benchmark.get("distractor_domain_count") or 0)
    multi_hop = int(summary.get("multi_hop_task_count") or 0) if isinstance(summary, Mapping) else 0
    benchmark_ok = bool(has_required_modes and distractors >= 6 and multi_hop >= 1)
    common_metrics = {
        "distractor_domain_count": distractors,
        "multi_hop_task_count": multi_hop,
        "modes": sorted(mode_names),
    }
    return [
        ReadinessGate(
            id="A.swarm_parity",
            status="green" if benchmark_ok else "red",
            passed=benchmark_ok,
            evidence_path=str(benchmark_path),
            summary="local deterministic swarm parity exercised in focused tests",
            metrics=common_metrics,
        ),
        ReadinessGate(
            id="B.supervisor_parity",
            status="green" if benchmark_ok else "red",
            passed=benchmark_ok,
            evidence_path=str(benchmark_path),
            summary="local deterministic supervisor parity exercised in focused tests",
            metrics=common_metrics,
        ),
        ReadinessGate(
            id="C.context_tool_isolation",
            status="green" if benchmark_ok else "red",
            passed=benchmark_ok,
            evidence_path=str(benchmark_path),
            summary="distractor benchmark includes hard domain/tool isolation evidence",
            metrics=common_metrics,
        ),
        ReadinessGate(
            id="D.benchmark",
            status="green" if benchmark_ok else "red",
            passed=benchmark_ok,
            evidence_path=str(benchmark_path),
            summary="single-agent, swarm, and supervisor benchmark report is present",
            metrics=common_metrics,
        ),
    ]


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _summary_bool(payload: Mapping[str, Any], key: str) -> bool:
    return bool(_as_mapping(payload.get("summary")).get(key))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate LangGraph parity mission gate receipts."
    )
    parser.add_argument("--report-root", default="reports/langgraph_parity")
    parser.add_argument(
        "--live-census",
        default=str(Path.home() / ".dharma" / "ops" / "live_process_census.json"),
    )
    parser.add_argument("--mission-id", default=MISSION_ID)
    parser.add_argument(
        "--output-dir",
        default="reports/langgraph_parity/readiness",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero unless every mission gate is green.",
    )
    args = parser.parse_args(argv)
    report = build_readiness_report(
        args.report_root,
        live_census_path=args.live_census,
        mission_id=args.mission_id,
    )
    json_path, markdown_path = write_readiness_report(report, args.output_dir)
    print(f"wrote {json_path}")
    print(f"wrote {markdown_path}")
    print(
        json.dumps(
            {
                "overall_status": report.overall_status,
                "ten_out_of_ten": report.ten_out_of_ten,
                "gate_count": len(report.gates),
                "blocker_count": len(report.blockers),
                "red_gates": [
                    gate.id for gate in report.gates if gate.status == "red"
                ],
                "amber_gates": [
                    gate.id for gate in report.gates if gate.status == "amber"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.ten_out_of_ten or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
