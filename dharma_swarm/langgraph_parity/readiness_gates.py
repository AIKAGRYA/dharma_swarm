"""Gate-specific aggregators for LangGraph parity readiness."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from dharma_swarm.langgraph_parity.readiness import ReadinessBlocker, ReadinessGate


def runtime_gate(
    runtime_global: Mapping[str, Any],
    runtime_fresh: Mapping[str, Any],
    global_path: Path,
    fresh_path: Path,
) -> tuple[ReadinessGate, list[ReadinessBlocker]]:
    blockers: list[ReadinessBlocker] = []
    global_summary = _as_mapping(runtime_global.get("summary"))
    fresh_summary = _as_mapping(runtime_fresh.get("summary"))
    queue = _as_sequence(
        _as_mapping(runtime_global.get("major_task_receipts")).get(
            "field_gap_action_queue"
        )
    )
    for row in queue:
        item = _as_mapping(row)
        action = str(item.get("action") or "runtime_gap")
        short_label = str(item.get("short_label") or action)
        blockers.append(
            ReadinessBlocker(
                id=f"runtime.{_slug(short_label)}",
                source_gate="runtime_receipt_coverage",
                task_id=f"lgp-runtime-{_slug(short_label)}",
                status=str(item.get("disposition") or "open"),
                evidence_path=str(global_path),
                summary=str(item.get("fresh_proof", {}).get("remaining_action") or action)
                if isinstance(item.get("fresh_proof"), Mapping)
                else action,
                owner_surface=str(item.get("owner_surface") or ""),
                missing_count=int(item.get("missing") or 0),
                operator_decision_required=bool(
                    item.get("operator_decision_required")
                ),
                evidence=item,
            )
        )
    global_pass = bool(global_summary.get("score_gate_70_to_75"))
    fresh_pass = bool(fresh_summary.get("score_gate_70_to_75"))
    gate_pass = global_pass and fresh_pass and not blockers
    return (
        ReadinessGate(
            id="E1.runtime_receipt_coverage",
            status="green" if gate_pass else "red",
            passed=gate_pass,
            evidence_path=str(global_path),
            summary=(
                "global and fresh runtime receipt gates pass"
                if gate_pass
                else "global runtime receipt gate remains red; fresh slice is tracked separately"
            ),
            blocker_ids=tuple(blocker.id for blocker in blockers),
            metrics={
                "global_score_gate_70_to_75": global_pass,
                "fresh_score_gate_70_to_75": fresh_pass,
                "global_runtime_receipts_total": int(
                    global_summary.get("runtime_receipts_total") or 0
                ),
                "fresh_runtime_receipts_total": int(
                    fresh_summary.get("runtime_receipts_total") or 0
                ),
                "fresh_major_task_receipts_total": int(
                    fresh_summary.get("major_task_receipts_total") or 0
                ),
            },
        ),
        blockers,
    )


def a2a_gate(
    a2a: Mapping[str, Any],
    a2a_path: Path,
) -> tuple[ReadinessGate, list[ReadinessBlocker]]:
    blockers: list[ReadinessBlocker] = []
    blocker_task_ids = _as_mapping(a2a.get("blocker_task_ids"))
    for reason, raw_task_ids in blocker_task_ids.items():
        task_ids = [str(task_id) for task_id in _as_sequence(raw_task_ids)]
        if not task_ids:
            continue
        blockers.append(
            ReadinessBlocker(
                id=f"a2a.{_slug(str(reason))}",
                source_gate="a2a_readiness",
                task_id=f"lgp-a2a-{_slug(str(reason))}",
                status="open",
                evidence_path=str(a2a_path),
                summary=f"{len(task_ids)} A2A task(s) block readiness for {reason}",
                owner_surface="a2a_queue",
                missing_count=len(task_ids),
                evidence={"reason": reason, "task_ids": task_ids},
            )
        )
    ready = bool(a2a.get("ready"))
    coverage_complete = bool(a2a.get("blocker_task_id_coverage_complete"))
    accepted_degraded = bool(not ready and coverage_complete and blockers)
    gate_blockers: tuple[ReadinessBlocker, ...] = (
        () if ready or coverage_complete else tuple(blockers)
    )
    gate_pass = ready or coverage_complete
    status = "green" if ready else ("amber" if coverage_complete else "red")
    return (
        ReadinessGate(
            id="E2.a2a_readiness",
            status=status,
            passed=gate_pass,
            evidence_path=str(a2a_path),
            summary=(
                "A2A readiness is green"
                if ready
                else "A2A degraded, but accepted by complete blocker task-id coverage"
                if coverage_complete
                else "A2A degraded and blocker task-id coverage is incomplete"
            ),
            blocker_ids=tuple(blocker.id for blocker in gate_blockers),
            metrics={
                "ready": ready,
                "gate_status": str(a2a.get("gate_status") or ""),
                "open_tasks": int(a2a.get("open_tasks") or 0),
                "unverified_closed_tasks": int(
                    a2a.get("unverified_closed_tasks") or 0
                ),
                "unknown_status_tasks": int(a2a.get("unknown_status_tasks") or 0),
                "blocker_task_id_coverage_complete": coverage_complete,
                "accepted_degraded": accepted_degraded,
                "tracked_blocker_ids": [blocker.id for blocker in blockers],
            },
        ),
        list(gate_blockers),
    )


def spine_live_gate(
    spine: Mapping[str, Any],
    live: Mapping[str, Any],
    spine_path: Path,
    live_path: Path,
) -> tuple[ReadinessGate, list[ReadinessBlocker]]:
    summary = _as_mapping(spine.get("summary"))
    live_surfaces = _as_sequence(live.get("surfaces"))
    blockers: list[ReadinessBlocker] = []
    for surface in live_surfaces:
        item = _as_mapping(surface)
        proof_gaps = [str(gap) for gap in _as_sequence(item.get("proof_gaps")) if str(gap)]
        if not proof_gaps:
            continue
        surface_id = str(item.get("id") or "unknown_surface")
        blockers.append(
            ReadinessBlocker(
                id=f"live_ops.{_slug(surface_id)}",
                source_gate="live_ops_census",
                task_id=f"lgp-live-{_slug(surface_id)}",
                status=str(item.get("status") or "proof_gap"),
                evidence_path=str(live_path),
                summary=f"{surface_id} has {len(proof_gaps)} proof gap(s)",
                owner_surface=surface_id,
                missing_count=len(proof_gaps),
                operator_decision_required=bool(
                    item.get("human_authority_required")
                ),
                evidence={
                    "proof_gaps": proof_gaps,
                    "human_authority_required": bool(
                        item.get("human_authority_required")
                    ),
                    "next_action": str(item.get("next_action") or ""),
                },
            )
        )
    spine_pass = bool(summary.get("score_gate_65_to_70"))
    gate_pass = spine_pass and not blockers
    return (
        ReadinessGate(
            id="E3.spine_live_ops",
            status="green" if gate_pass else "amber",
            passed=gate_pass,
            evidence_path=str(spine_path),
            summary=(
                "spine dispatch and live ops are green"
                if gate_pass
                else "spine dispatch gate passes, but live ops proof gaps remain"
                if spine_pass
                else "spine dispatch gate is not green"
            ),
            blocker_ids=tuple(blocker.id for blocker in blockers),
            metrics={
                "score_gate_65_to_70": spine_pass,
                "live_census_state": str(summary.get("live_census_state") or ""),
                "live_census_proof_gap_surfaces": int(
                    summary.get("live_census_proof_gap_surfaces") or len(blockers)
                ),
                "orchestrator_current_process": str(
                    summary.get("orchestrator_current_process") or ""
                ),
                "orchestrator_persistent_daemon": str(
                    summary.get("orchestrator_persistent_daemon") or ""
                ),
            },
        ),
        blockers,
    )


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: object) -> Sequence[object]:
    return value if isinstance(value, Sequence) and not isinstance(value, str) else ()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "unknown"
