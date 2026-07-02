"""RSI Lab conductor for the corrected Forge/DGM run shape.

This launcher ties the pieces together without weakening any gate:

* allocate EXPLORE/CONFIRM tasks from the durable taskbed ledger when requested;
* run DGM scaffold genomes through the real Forge fitness path in shadow mode;
* emit the canonical packet consumed by guard lanes;
* run the deterministic packet guard;
* call ``verify_promotion`` as the sole live-apply arbiter.

It is intentionally not an overnight loop.  It is the small, auditable unit that
overnight launchers can repeat once the fresh taskbed is populated.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.dgm_loop import DGMLoop, DGMResult

from . import taskbed_ledger
from .packet_guard import run_guard
from .runner import DEFAULT_FORGE_GENERATOR_MODEL, DEFAULT_FORGE_VERIFIER_MODEL
from .scheduler import emit_canonical_packet
from .signals import canonical_sha256
from .verify_promotion import verify_promotion

RUN_ROOT = dharma_state_dir() / "forge_v1" / "forge_v2" / "rsi_conductor"
SCHEMA_VERSION = "forge_v2.rsi_conductor.v1"


def now_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, default=str) + "\n" for row in rows))


class _NoDarwinEngine:
    async def auto_evolve(self, **_kwargs: Any) -> None:
        raise AssertionError("RSI conductor must use Forge genome grading, not local Darwin auto_evolve")


def _result_dict(result: DGMResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, dict):
        return dict(result)
    return asdict(result)


async def _default_dgm_runner(
    genome: dict[str, Any],
    instance_ids: list[str],
    *,
    split: str,
) -> DGMResult:
    loop = DGMLoop(engine=_NoDarwinEngine(), shadow_mode=True)
    return await loop.run_forge_genome_generation(genome, instance_ids, split=split)


def _runner_receipt(result: dict[str, Any]) -> dict[str, Any]:
    forge_grade = dict(result.get("forge_grade") or {})
    return dict(forge_grade.get("runner_receipt") or {})


def _history_attempts(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    attempts = receipt.get("attempts") if isinstance(receipt.get("attempts"), list) else []
    return [
        {**dict(attempt), "_campaign_index": 1}
        for attempt in attempts
        if isinstance(attempt, dict)
    ]


def _cost_from_attempts(attempts: list[dict[str, Any]]) -> float:
    total = 0.0
    for attempt in attempts:
        budget = dict(attempt.get("budget") or {})
        try:
            total += float(budget.get("total_cost_usd") or 0.0)
        except (TypeError, ValueError):
            continue
    return round(total, 6)


def _state_from_result(
    *,
    label: str,
    run_dir: Path,
    split: str,
    instance_ids: list[str],
    genome: dict[str, Any],
    result: dict[str, Any],
    taskbed_allocation: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt = _runner_receipt(result)
    attempts = _history_attempts(receipt)
    lift = dict(receipt.get("contrast_vs_class_null") or result.get("forge_grade", {}).get("ci") or {})
    closeout = str(receipt.get("closeout") or result.get("forge_grade", {}).get("closeout") or "blocked_with_evidence")
    arm = str(receipt.get("arm") or genome.get("arm") or "verify_chain")
    state = {
        "schema": SCHEMA_VERSION,
        "started_at": now_stamp(),
        "finished_at": now_stamp(),
        "run_dir": str(run_dir),
        "label": label,
        "dry_run": False,
        "config": {
            "instances": instance_ids,
            "n_explore": len(instance_ids) if split == "explore" else 0,
            "replicates": 1,
            "budget_cap": 60000,
            "campaign_budget_usd": 0.25,
            "per_call_tokens": 3500,
            "k_self_moa": 1,
            "grade_timeout": 1200,
            "timeout_s": 240,
            "strategy": "explore",
            "roster_n": 14,
            "generator": genome.get("generator") or DEFAULT_FORGE_GENERATOR_MODEL,
            "verifier": genome.get("verifier") or DEFAULT_FORGE_VERIFIER_MODEL,
            "arms": [arm],
            "mix_models": list(genome.get("mix_models") or []),
            "taskbed": taskbed_allocation or None,
        },
        "taskbed_allocation": (
            {**taskbed_allocation, "source": "forge_v2.taskbed_ledger"}
            if taskbed_allocation
            else None
        ),
        "completed_campaigns": 1,
        "invalid_runs": 0,
        "total_cost_usd": _cost_from_attempts(attempts),
        "last_closeout": closeout,
        "stop_reason": "single_conductor_smoke",
        "campaigns": [
            {
                "campaign_index": 1,
                "campaign_label": label,
                "arm": arm,
                "instances": instance_ids,
                "n_explore": len(instance_ids) if split == "explore" else 0,
                "status": "ok" if result.get("error") is None else "error",
                "closeout": closeout,
                "n_pairs": receipt.get("n_pairs", lift.get("n", 0)),
                "lift": lift,
                "cost_usd": _cost_from_attempts(attempts),
                "artifact_dir": receipt.get("artifact_dir", ""),
                "coordination_edges": receipt.get("coordination_edges") or receipt.get("final_use_edges") or [],
            }
        ],
        "dgm_result": result,
    }
    return state, attempts


def _ci(receipt: dict[str, Any], split: str) -> dict[str, Any]:
    split_contrasts = dict(receipt.get("split_contrasts") or {})
    if split in split_contrasts:
        return dict(split_contrasts[split] or {})
    return dict(receipt.get("contrast_vs_class_null") or {})


def _contamination_state(receipt: dict[str, Any]) -> str:
    value = receipt.get("contamination_state")
    if isinstance(value, dict):
        return str(value.get("state") or "unknown")
    return str(value or "unknown")


def _promotion_signal(
    *,
    run_id: str,
    split: str,
    genome: dict[str, Any],
    result: dict[str, Any],
    packet_guard_review: dict[str, Any],
    taskbed_allocation: dict[str, Any] | None,
    epoch_id: str,
) -> dict[str, Any]:
    receipt = _runner_receipt(result)
    forge_grade = dict(result.get("forge_grade") or {})
    overall = dict(receipt.get("contrast_vs_class_null") or forge_grade.get("ci") or {})
    explore = _ci(receipt, "explore")
    confirm = _ci(receipt, "confirm")
    contamination = _contamination_state(receipt)
    signal = {
        "run_id": run_id,
        "signal_key": f"{run_id}:rsi_conductor:{genome.get('arm', 'verify_chain')}:{split}",
        "epoch_id": epoch_id,
        "taskbed": (taskbed_allocation or {}).get("allocation_id") or "explicit_smoke_instances",
        "mission_class": str(receipt.get("mission_class") or "verifier_role"),
        "arm": str(receipt.get("arm") or genome.get("arm") or "verify_chain"),
        "class_null": str(receipt.get("class_null") or "self_moa"),
        "overall_ci": overall,
        "explore_ci": explore,
        "confirm_ci": confirm,
        "fdr_positive_significant": bool(overall.get("lower", 0.0) and float(overall.get("lower", 0.0)) > 0),
        "contamination_state": contamination,
        "sealed_provenance": {
            "contamination_state": contamination,
            "source": "forge_runner_receipt",
            "run_id": run_id,
        },
        "null_survived": float(overall.get("lower", 0.0) or 0.0) <= 0.0,
        "evidence_strength": max(0.0, float(confirm.get("lower", 0.0) or 0.0)),
        "promotion_blockers": list(forge_grade.get("blockers") or []),
        "packet_guard_review": packet_guard_review,
    }
    signal["signal_sha256"] = canonical_sha256(signal)
    return signal


def _blocked_no_taskbed(
    *,
    run_dir: Path,
    label: str,
    error: str,
    split: str,
    epoch_id: str,
) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA_VERSION,
        "label": label,
        "run_dir": str(run_dir),
        "status": "blocked_with_evidence",
        "blocked_stage": "taskbed_allocation",
        "split": split,
        "epoch_id": epoch_id,
        "error": error,
        "next_action": "populate the fresh taskbed ledger before launching this split",
    }
    write_json(run_dir / "conductor_closeout.json", payload)
    return payload


def run_conductor(
    *,
    label: str = "rsi_conductor",
    genome: dict[str, Any] | None = None,
    instance_ids: list[str] | None = None,
    split: str = "explore",
    epoch_id: str = "epoch_0",
    taskbed_db: Path | str = taskbed_ledger.DEFAULT_DB,
    taskbed_split: str | None = None,
    taskbed_count: int | None = None,
    taskbed_min_confirm_count: int = taskbed_ledger.MIN_CONFIRM_TASKS,
    taskbed_allocation_id: str | None = None,
    taskbed_lane_id: str | None = None,
    taskbed_candidate_id: str = "",
    operator_lease: dict[str, Any] | None = None,
    dgm_runner: Callable[..., Any] | None = None,
    packet_guard_runner: Callable[..., dict[str, Any]] = run_guard,
    promotion_verifier: Callable[..., dict[str, Any]] = verify_promotion,
) -> dict[str, Any]:
    if split not in {"explore", "confirm"}:
        raise ValueError("split must be explore or confirm")
    genome = dict(genome or {"arm": "verify_chain"})
    genome.setdefault("generator", DEFAULT_FORGE_GENERATOR_MODEL)
    genome.setdefault("verifier", DEFAULT_FORGE_VERIFIER_MODEL)
    run_dir = RUN_ROOT / f"{label}_{now_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    allocation: dict[str, Any] | None = None
    if taskbed_split:
        try:
            allocation = taskbed_ledger.allocate_tasks(
                split=taskbed_split,  # type: ignore[arg-type]
                count=taskbed_count or (taskbed_ledger.MIN_CONFIRM_TASKS if taskbed_split == "confirm" else 1),
                epoch_id=epoch_id,
                lane_id=taskbed_lane_id or label,
                db_path=taskbed_db,
                allocation_id=taskbed_allocation_id,
                candidate_id=taskbed_candidate_id,
                min_count=taskbed_min_confirm_count if taskbed_split == "confirm" else taskbed_count,
            )
        except Exception as exc:  # noqa: BLE001 - blocked allocation must receipt.
            return _blocked_no_taskbed(
                run_dir=run_dir,
                label=label,
                error=f"{type(exc).__name__}: {exc}",
                split=taskbed_split,
                epoch_id=epoch_id,
            )
        instance_ids = list(allocation["task_ids"])
        split = taskbed_split
    instance_ids = [str(item) for item in (instance_ids or []) if str(item).strip()]
    if not instance_ids:
        return _blocked_no_taskbed(
            run_dir=run_dir,
            label=label,
            error="no instances supplied or allocated",
            split=split,
            epoch_id=epoch_id,
        )

    runner = dgm_runner or _default_dgm_runner
    maybe_result = runner(genome, list(instance_ids), split=split)
    result_obj = asyncio.run(maybe_result) if asyncio.iscoroutine(maybe_result) else maybe_result
    result = _result_dict(result_obj)
    state, attempts = _state_from_result(
        label=label,
        run_dir=run_dir,
        split=split,
        instance_ids=instance_ids,
        genome=genome,
        result=result,
        taskbed_allocation=allocation,
    )
    write_json(run_dir / "state.json", state)
    write_jsonl(run_dir / "campaign_ledger.jsonl", [{"event": "dgm_result", "result": result}])
    packet_emit = emit_canonical_packet(run_dir, state, history_attempts=attempts)
    guard_review = packet_guard_runner(packet_dir=run_dir, out_dir=run_dir)
    signal = _promotion_signal(
        run_id=run_dir.name,
        split=split,
        genome=genome,
        result=result,
        packet_guard_review=guard_review,
        taskbed_allocation=allocation,
        epoch_id=epoch_id,
    )
    promotion = promotion_verifier(signal, operator_lease=operator_lease)
    closeout = {
        "schema": SCHEMA_VERSION,
        "label": label,
        "run_dir": str(run_dir),
        "status": "complete",
        "shadow_mode": bool(result.get("shadow_mode", True)),
        "applied": bool(result.get("applied", False)),
        "split": split,
        "task_count": len(instance_ids),
        "taskbed_allocation": allocation,
        "dgm_result": result,
        "canonical_packet": packet_emit,
        "packet_guard_review": guard_review,
        "promotion_signal": signal,
        "promotion_verdict": promotion,
    }
    write_json(run_dir / "conductor_closeout.json", closeout)
    return closeout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one RSI Lab DGM/Forge conductor cycle")
    parser.add_argument("--label", default="rsi_conductor")
    parser.add_argument("--instances", default="", help="Comma-separated explicit instance ids for smoke runs")
    parser.add_argument("--split", choices=["explore", "confirm"], default="explore")
    parser.add_argument("--arm", default="verify_chain")
    parser.add_argument("--epoch-id", default="epoch_0")
    parser.add_argument("--taskbed-db", default=str(taskbed_ledger.DEFAULT_DB))
    parser.add_argument("--taskbed-split", choices=["explore", "confirm"], default=None)
    parser.add_argument("--taskbed-count", type=int, default=0)
    parser.add_argument("--taskbed-min-confirm-count", type=int, default=taskbed_ledger.MIN_CONFIRM_TASKS)
    parser.add_argument("--taskbed-allocation-id", default=None)
    parser.add_argument("--taskbed-lane-id", default=None)
    parser.add_argument("--taskbed-candidate-id", default="")
    parser.add_argument("--operator-lease-id", default="")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_conductor(
        label=args.label,
        genome={"arm": args.arm},
        instance_ids=[item.strip() for item in args.instances.split(",") if item.strip()],
        split=args.split,
        epoch_id=args.epoch_id,
        taskbed_db=args.taskbed_db,
        taskbed_split=args.taskbed_split,
        taskbed_count=args.taskbed_count or None,
        taskbed_min_confirm_count=args.taskbed_min_confirm_count,
        taskbed_allocation_id=args.taskbed_allocation_id,
        taskbed_lane_id=args.taskbed_lane_id,
        taskbed_candidate_id=args.taskbed_candidate_id,
        operator_lease={"lease_id": args.operator_lease_id} if args.operator_lease_id else None,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        print(
            "[rsi_conductor] status={status} split={split} task_count={task_count} dir={run_dir}".format(
                status=result.get("status"),
                split=result.get("split", ""),
                task_count=result.get("task_count", 0),
                run_dir=result.get("run_dir"),
            ),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
