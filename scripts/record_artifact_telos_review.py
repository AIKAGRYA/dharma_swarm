#!/usr/bin/env python3
"""Record an artifact review through TelosGatekeeper and TelicSeam."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.models import GateDecision, Task  # noqa: E402
from dharma_swarm.telic_seam import TelicSeam  # noqa: E402
from dharma_swarm.telos_gates import TelosGatekeeper  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record a proof artifact review in the ontology metabolic loop.",
    )
    parser.add_argument("artifact", type=Path, help="Markdown/text artifact to review")
    parser.add_argument(
        "--ontology-path",
        type=Path,
        default=None,
        help="Ontology DB path (default: <artifact parent>/state/ontology.db)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON summary path",
    )
    parser.add_argument(
        "--agent-id",
        default="artifact_telos_reviewer",
        help="Agent identity recorded as reviewer",
    )
    parser.add_argument(
        "--fail-on-block",
        action="store_true",
        help="Exit 1 when TelosGatekeeper blocks the artifact",
    )
    return parser


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _gate_results_to_json(gate_results: dict[str, tuple[Any, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for name, (result, reason) in gate_results.items():
        out[name] = {
            "result": result.value if hasattr(result, "value") else str(result),
            "reason": str(reason),
        }
    return out


def _fitness_for_decision(decision: GateDecision) -> float:
    if decision == GateDecision.ALLOW:
        return 1.0
    if decision == GateDecision.REVIEW:
        return 0.55
    return 0.0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact = args.artifact.expanduser()
    content = artifact.read_text(encoding="utf-8")
    artifact_hash = _sha256_text(content)
    ontology_path = (
        args.ontology_path.expanduser()
        if args.ontology_path is not None
        else artifact.parent / "state" / "ontology.db"
    )

    task = Task(
        title=f"Telos review proof artifact {artifact.name}",
        description=f"Review proof artifact for gate-recorded packet loop: {artifact}",
        metadata={
            "task_type": "artifact_telos_review",
            "artifact_path": str(artifact),
            "artifact_sha256": artifact_hash,
        },
    )
    seam = TelicSeam(path=ontology_path)
    gatekeeper = TelosGatekeeper()
    proposal_id = seam.record_dispatch(task, args.agent_id, topology="manual")
    gate_result = gatekeeper.check(
        action=f"review proof artifact {artifact}",
        content=content,
        tool_name="record_artifact_telos_review",
        trust_mode="external_strict",
        think_phase="before_complete",
        reflection=(
            "Risk: this artifact could overclaim, leak private context, or collapse "
            "vision into unsupported proof. Verification: route it through existing "
            "TelosGatekeeper gates, record the GateDecisionRecord, and preserve the "
            "artifact hash so later witness and outcome records can challenge it. "
            "Rollback: this review writes only additive ontology records."
        ),
    )
    gate_decision_id = seam.record_gate_decision(proposal_id, gate_result)
    success = gate_result.decision != GateDecision.BLOCK
    outcome_id = seam.record_outcome(
        task,
        args.agent_id,
        success=success,
        result_summary=gate_result.reason if success else "",
        error="" if success else gate_result.reason,
        fitness_score=_fitness_for_decision(gate_result.decision),
    )
    value_event_id = None
    contribution_id = None
    if outcome_id is not None:
        value_event_id = seam.record_value_event(
            outcome_id,
            task,
            args.agent_id,
            result_text=content,
            success=success,
            cell_id="agentic_immune_system_packet_20260511",
        )
    if value_event_id is not None:
        contribution_id = seam.record_contribution(
            value_event_id,
            args.agent_id,
            composite_value=_fitness_for_decision(gate_result.decision),
            cell_id="agentic_immune_system_packet_20260511",
            task_type="artifact_telos_review",
        )

    payload = {
        "artifact_path": str(artifact),
        "artifact_sha256": artifact_hash,
        "ontology_path": str(ontology_path),
        "task_id": task.id,
        "proposal_id": proposal_id,
        "gate_decision_id": gate_decision_id,
        "gate_decision": gate_result.decision.value,
        "gate_reason": gate_result.reason,
        "gate_results": _gate_results_to_json(gate_result.gate_results),
        "outcome_id": outcome_id,
        "value_event_id": value_event_id,
        "contribution_id": contribution_id,
        "stats": seam.stats(),
    }
    if args.output is not None:
        output = args.output.expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))

    if args.fail_on_block and gate_result.decision == GateDecision.BLOCK:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
