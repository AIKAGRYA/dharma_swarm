#!/usr/bin/env python3
"""Loop 3 (Evolution / DarwinEngine) closure replay.

This is a bounded, scratch-only DarwinEngine replay. It proves the Loop 3
cycle without writing to the live evolution archive:

  sense      : execute local DarwinEngine behavioral probes and read their
               real outcomes.
  interpret  : identify the concrete deficit: no prior predictor outcome for
               the loop-3 component/change pair.
  constrain  : build a small proposal, prove its diff avoids protected archive
               authority surfaces, and run the real Telos gates.
  act        : evaluate the gated proposal and archive its fitness in a
               scratch archive.
  adapt      : prove the scratch predictor and parent selector read that
               recorded outcome on a later proposal/selection cycle.

Usage:
    .venv/bin/python scripts/loop3_evolution_closure_run.py \
      --report reports/loop_closure/cybernetics_codex/2026-07-01_loop3_evolution_closure.json
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dharma_swarm.archive import FitnessScore  # noqa: E402
from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402
from dharma_swarm.evolution import (  # noqa: E402
    DarwinEngine,
    EvolutionStatus,
    Proposal,
    _paths_from_unified_diff,
)
from dharma_swarm.fitness_predictor import ProposalFeatures  # noqa: E402

TRANSITIONS = ("sense", "interpret", "constrain", "act", "adapt")
COMPONENT = "loop3_evolution_policy"
CHANGE_TYPE = "bounded_replay"
MAX_DIFF_LINES = 32
PROTECTED_DIFF_PATHS = {
    "dharma_swarm/archive.py",
    "dharma_swarm/cybernetics_codex.py",
    "scripts/governance/cybernetics_codex_audit.py",
}

PROPOSAL_DIFF = """diff --git a/reports/loop_closure/cybernetics_codex/loop3_evolution_policy.json b/reports/loop_closure/cybernetics_codex/loop3_evolution_policy.json
--- a/reports/loop_closure/cybernetics_codex/loop3_evolution_policy.json
+++ b/reports/loop_closure/cybernetics_codex/loop3_evolution_policy.json
@@ -0,0 +1,7 @@
+{
+  "loop": 3,
+  "policy": "feed verified scratch Darwin outcomes into the predictor before the next proposal",
+  "scope": "bounded replay only",
+  "authority": "does not write live archive fitness",
+  "rollback": "discard scratch archive and receipt"
+}
"""

THINK_NOTES = (
    "Risk: this replay must not mutate live archive fitness authority or weaken "
    "gates. Rollback: discard the scratch directory and rerun. Evidence: the "
    "proposal is gate-checked, evaluated, archived only in scratch state, then "
    "a later proposal reads the changed predictor. However, it remains a local "
    "closure proof rather than production evolution authority."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _round(value: float) -> float:
    return round(float(value), 6)


@contextmanager
def _isolated_runtime(scratch_root: Path):
    """Route replay side effects to scratch state and disable JIKOKU tracing."""
    from dharma_swarm import jikoku_instrumentation, telos_gates

    old_gatekeeper = telos_gates.DEFAULT_GATEKEEPER
    old_witness_dir = telos_gates.WITNESS_DIR
    old_pressure_path = telos_gates.TelosGatekeeper._GATE_PRESSURE_PATH
    old_trust_mode = os.environ.get("DGC_TRUST_MODE")
    old_jikoku_enabled = jikoku_instrumentation.is_enabled()

    telos_gates.WITNESS_DIR = scratch_root / "witness"
    telos_gates.TelosGatekeeper._GATE_PRESSURE_PATH = (
        scratch_root / "meta" / "gate_pressure.json"
    )
    telos_gates.DEFAULT_GATEKEEPER = telos_gates.TelosGatekeeper(
        registry=telos_gates.GateRegistry(
            proposals_file=scratch_root / "meta" / "gate_proposals.jsonl"
        )
    )
    os.environ["DGC_TRUST_MODE"] = "internal_yolo"
    jikoku_instrumentation.set_enabled(False)
    try:
        yield
    finally:
        telos_gates.DEFAULT_GATEKEEPER = old_gatekeeper
        telos_gates.WITNESS_DIR = old_witness_dir
        telos_gates.TelosGatekeeper._GATE_PRESSURE_PATH = old_pressure_path
        if old_trust_mode is None:
            os.environ.pop("DGC_TRUST_MODE", None)
        else:
            os.environ["DGC_TRUST_MODE"] = old_trust_mode
        jikoku_instrumentation.set_enabled(old_jikoku_enabled)


def _proposal_features(diff: str = PROPOSAL_DIFF) -> ProposalFeatures:
    return ProposalFeatures(
        component=COMPONENT,
        change_type=CHANGE_TYPE,
        diff_size=len(diff.splitlines()),
    )


def _bounded_change_evidence(proposal: Proposal) -> dict[str, Any]:
    paths = _paths_from_unified_diff(proposal.diff)
    protected_hits = sorted(set(paths).intersection(PROTECTED_DIFF_PATHS))
    diff_lines = len(proposal.diff.splitlines())
    return {
        "passed": diff_lines <= MAX_DIFF_LINES and not protected_hits,
        "component": proposal.component,
        "change_type": proposal.change_type,
        "diff_lines": diff_lines,
        "max_diff_lines": MAX_DIFF_LINES,
        "paths": paths,
        "protected_hits": protected_hits,
        "scratch_only": True,
    }


async def _sense_task_outcomes(engine: DarwinEngine) -> list[dict[str, Any]]:
    """Run behavioral probes whose outcomes become the sensed task data."""
    outcomes: list[dict[str, Any]] = []

    safe_probe = await engine.propose(
        component=COMPONENT,
        change_type="observation",
        description=(
            "Probe DarwinEngine can gate a non-self-mod observation with risk, "
            "rollback, evidence, and alternative paths."
        ),
        diff="",
        think_notes=THINK_NOTES,
    )
    await engine.gate_check(safe_probe)
    outcomes.append(
        {
            "task_id": "loop3-probe-gate-observation",
            "source": "DarwinEngine.gate_check",
            "observed": safe_probe.status.value,
            "expected": EvolutionStatus.GATED.value,
            "score": 1.0 if safe_probe.status == EvolutionStatus.GATED else 0.0,
            "real_execution": True,
        }
    )

    review_probe = Proposal(
        component=COMPONENT,
        change_type="mutation",
        description="force override loop3 configuration",
        diff="",
        think_notes=(
            "Risk: deliberate review-trigger probe for self-modification guard. "
            "Rollback: no files are written. Evidence: expected rejected gate "
            "status confirms advisory self-mod changes do not apply."
        ),
    )
    await engine.gate_check(review_probe)
    outcomes.append(
        {
            "task_id": "loop3-probe-self-mod-review-guard",
            "source": "DarwinEngine.gate_check",
            "observed": review_probe.status.value,
            "expected": EvolutionStatus.REJECTED.value,
            "score": 1.0 if review_probe.status == EvolutionStatus.REJECTED else 0.0,
            "real_execution": True,
        }
    )

    features = _proposal_features()
    prior_prediction = engine.predictor.predict(features)
    outcomes.append(
        {
            "task_id": "loop3-probe-predictor-history-before-adapt",
            "source": "FitnessPredictor.predict/outcome_count",
            "observed": {
                "outcome_count": engine.predictor.outcome_count,
                "prediction": _round(prior_prediction),
            },
            "expected": "existing outcome history for loop3 replay candidate",
            "score": 1.0 if engine.predictor.outcome_count > 0 else 0.0,
            "real_execution": True,
        }
    )
    return outcomes


def _interpret_outcomes(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    score_total = sum(float(row["score"]) for row in outcomes)
    pass_rate = score_total / max(1, len(outcomes))
    deficits = [row["task_id"] for row in outcomes if float(row["score"]) < 1.0]
    return {
        "task_count": len(outcomes),
        "score_total": _round(score_total),
        "pass_rate": _round(pass_rate),
        "deficits": deficits,
        "selected_change": (
            "record the evaluated bounded replay in the scratch Darwin archive "
            "so the predictor has a real outcome before the later proposal"
        ),
    }


def _fitness_payload(fitness: FitnessScore | None, score: float) -> dict[str, Any]:
    payload = fitness.model_dump() if fitness is not None else FitnessScore().model_dump()
    payload["weighted"] = _round(score)
    return payload


async def _run_with_scratch(scratch_root: Path) -> dict[str, Any]:
    scratch_root.mkdir(parents=True, exist_ok=True)
    archive_path = scratch_root / "evolution" / "archive.jsonl"
    predictor_path = scratch_root / "evolution" / "predictor_data.jsonl"
    traces_path = scratch_root / "traces"
    experiment_log_path = scratch_root / "evolution" / "experiments.jsonl"
    live_archive_path = (
        dharma_state_dir("DHARMA_STATE_DIR", "DHARMA_HOME")
        / "evolution"
        / "archive.jsonl"
    )
    scratch_archive_is_live_archive = (
        archive_path.resolve() == live_archive_path.resolve()
    )
    if scratch_archive_is_live_archive:
        raise RuntimeError(
            "refusing to use live Dharma archive as loop3 scratch archive"
        )
    tick_errors: list[str] = []
    transitions_seen = {name: False for name in TRANSITIONS}
    engine = DarwinEngine(
        archive_path=archive_path,
        traces_path=traces_path,
        predictor_path=predictor_path,
        experiment_log_path=experiment_log_path,
        archive_enforce_one_wire=False,
    )
    engine.archive.enforce_one_wire = False
    engine.archive.fitness_guard_state_dir = None

    try:
        await engine.init()
        before_entries = len(await engine.archive.list_entries())
        features = _proposal_features()
        prediction_before = engine.predictor.predict(features)
        predictor_count_before = engine.predictor.outcome_count

        outcomes = await _sense_task_outcomes(engine)
        transitions_seen["sense"] = bool(outcomes) and all(
            bool(row.get("real_execution")) for row in outcomes
        )

        interpretation = _interpret_outcomes(outcomes)
        transitions_seen["interpret"] = bool(interpretation["deficits"])

        proposal = await engine.propose(
            component=COMPONENT,
            change_type=CHANGE_TYPE,
            description=(
                "Feed verified Loop 3 replay outcomes into scratch Darwin "
                "predictor state before the later proposal; however keep the "
                "live archive fitness authority untouched."
            ),
            diff=PROPOSAL_DIFF,
            spec_ref="CYBERNETIC_LOOP_MAP.md#loop-3-evolution",
            requirement_refs=[
                "loop3:sense-real-task-outcomes",
                "loop3:gate-bounded-change",
                "loop3:fitness-fed-forward",
            ],
            think_notes=THINK_NOTES,
        )
        proposal.metadata = {
            "loop3_interpretation": interpretation,
            "scratch_archive_path": str(archive_path),
        }
        bounded = _bounded_change_evidence(proposal)
        await engine.gate_check(proposal)
        gate_status = proposal.status.value
        gate_decision = proposal.gate_decision
        constrained = (
            bounded["passed"]
            and proposal.status == EvolutionStatus.GATED
            and str(proposal.gate_decision).lower() in {"allow", "review"}
        )
        transitions_seen["constrain"] = constrained

        test_results = {
            "pass_rate": interpretation["pass_rate"],
            "task_outcomes": outcomes,
            "bounded_change": bounded,
            "authority_guard": {
                "live_archive_path": str(live_archive_path),
                "scratch_archive_path": str(archive_path),
                "live_archive_used": False,
                "scratch_archive_is_live_archive": scratch_archive_is_live_archive,
                "scratch_archive_one_wire_enforced": engine.archive.enforce_one_wire,
            },
        }
        await engine.evaluate(proposal, test_results=test_results)
        weighted_fitness = engine.score_fitness(proposal.actual_fitness)
        entry_id = await engine.archive_result(proposal)
        stored = await engine.archive.get_entry(entry_id)
        after_entries = len(await engine.archive.list_entries())
        transitions_seen["act"] = (
            stored is not None
            and proposal.status == EvolutionStatus.ARCHIVED
            and weighted_fitness > 0.0
            and after_entries == before_entries + 1
        )

        prediction_after = engine.predictor.predict(features)
        predictor_count_after = engine.predictor.outcome_count
        later_proposal = await engine.propose(
            component=COMPONENT,
            change_type=CHANGE_TYPE,
            description="Later-cycle read of Loop 3 bounded replay predictor state.",
            diff=PROPOSAL_DIFF,
            think_notes=THINK_NOTES,
        )
        selected_parent = await engine.select_next_parent(strategy="elite")
        fed_forward = (
            predictor_count_after > predictor_count_before
            and prediction_after != prediction_before
            and later_proposal.predicted_fitness == prediction_after
            and selected_parent is not None
            and selected_parent.id == entry_id
        )
        transitions_seen["adapt"] = fed_forward

        gate_results = (proposal.metadata or {}).get("gate_results") or {}
        report = {
            "loop": 3,
            "loop_id": "evolution_loop",
            "cycles": 2,
            "real_data": True,
            "transitions_receipted": transitions_seen,
            "adapt_proof": {
                "field": (
                    "scratch Darwin predictor history + archive parent selection "
                    "read by the later proposal cycle"
                ),
                "before": {
                    "predictor_outcomes": predictor_count_before,
                    "prediction": _round(prediction_before),
                    "archive_entries": before_entries,
                },
                "after": {
                    "predictor_outcomes": predictor_count_after,
                    "prediction": _round(prediction_after),
                    "archive_entries": after_entries,
                },
                "fed_forward": fed_forward,
                "archive_entry_id": entry_id,
            },
            "tick_errors": tick_errors,
            "sense_evidence": {
                "source": "local DarwinEngine behavioral replay",
                "task_outcomes": outcomes,
            },
            "interpret_evidence": interpretation,
            "constrain_evidence": {
                "bounded_change": bounded,
                "gate_status": gate_status,
                "gate_decision": gate_decision,
                "gate_reason": proposal.gate_reason,
                "gate_results": gate_results,
            },
            "act_evidence": {
                "archive_entry_id": entry_id,
                "archive_status": stored.status if stored is not None else None,
                "scratch_archive_path": str(archive_path),
                "live_archive_used": False,
                "scratch_archive_is_live_archive": scratch_archive_is_live_archive,
                "scratch_archive_one_wire_enforced": engine.archive.enforce_one_wire,
                "fitness": _fitness_payload(proposal.actual_fitness, weighted_fitness),
                "predictor_history_path": str(predictor_path),
                "predictor_outcomes_after_archive": predictor_count_after,
            },
            "adapt_evidence": {
                "prediction_before": _round(prediction_before),
                "prediction_after": _round(prediction_after),
                "predictor_outcomes_before": predictor_count_before,
                "predictor_outcomes_after": predictor_count_after,
                "later_proposal_id": later_proposal.id,
                "later_proposal_predicted_fitness": _round(
                    later_proposal.predicted_fitness
                ),
                "selected_parent_id": selected_parent.id if selected_parent else None,
            },
            "later_cycle_read_evidence": {
                "prediction_changed": prediction_after != prediction_before,
                "later_proposal_read_after_prediction": (
                    later_proposal.predicted_fitness == prediction_after
                ),
                "parent_selection_read_archive_entry": (
                    selected_parent is not None and selected_parent.id == entry_id
                ),
            },
            "cycle_detail": [
                {
                    "cycle": 1,
                    "phase": "sense_interpret_constrain_act",
                    "task_count": len(outcomes),
                    "pass_rate": interpretation["pass_rate"],
                    "gate_decision": proposal.gate_decision,
                    "archive_entry_id": entry_id,
                    "weighted_fitness": _round(weighted_fitness),
                },
                {
                    "cycle": 2,
                    "phase": "later_cycle_read",
                    "prediction_before": _round(prediction_before),
                    "prediction_after": _round(prediction_after),
                    "later_proposal_predicted_fitness": _round(
                        later_proposal.predicted_fitness
                    ),
                    "selected_parent_id": selected_parent.id if selected_parent else None,
                },
            ],
            "observed_at": _utc_now(),
        }
    except Exception as exc:  # report honestly; the audit will not close on errors
        tick_errors.append(f"{type(exc).__name__}: {exc}")
        report = {
            "loop": 3,
            "loop_id": "evolution_loop",
            "cycles": 0,
            "real_data": True,
            "transitions_receipted": transitions_seen,
            "adapt_proof": {"before": None, "after": None, "fed_forward": False},
            "tick_errors": tick_errors,
            "observed_at": _utc_now(),
        }
    finally:
        await engine.close()
    return report


async def run(
    *,
    report_path: Path | None = None,
    scratch_root: Path | None = None,
) -> dict[str, Any]:
    if scratch_root is None:
        with TemporaryDirectory(prefix="loop3_evolution_closure_") as tmp:
            with _isolated_runtime(Path(tmp)):
                report = await _run_with_scratch(Path(tmp))
    else:
        with _isolated_runtime(scratch_root):
            report = await _run_with_scratch(scratch_root)

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _is_closed(report: dict[str, Any]) -> bool:
    transitions = report.get("transitions_receipted") or {}
    adapt = report.get("adapt_proof") or {}
    return (
        int(report.get("cycles") or 0) > 0
        and bool(report.get("real_data"))
        and all(bool(transitions.get(name)) for name in TRANSITIONS)
        and bool(adapt.get("fed_forward"))
        and adapt.get("before") != adapt.get("after")
        and not report.get("tick_errors")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "reports/loop_closure/cybernetics_codex"
            / f"{datetime.now(timezone.utc):%Y-%m-%d}_loop3_evolution_closure.json"
        ),
        help="write the closure receipt here",
    )
    parser.add_argument(
        "--scratch-root",
        type=Path,
        default=None,
        help="optional scratch root for tests/debugging; defaults to a temp dir",
    )
    args = parser.parse_args(argv)

    report = asyncio.run(run(report_path=args.report, scratch_root=args.scratch_root))
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"\nwrote closure receipt: {args.report}")
    closed = _is_closed(report)
    print(f"LOOP3_CLOSED={'yes' if closed else 'no'}")
    return 0 if closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
