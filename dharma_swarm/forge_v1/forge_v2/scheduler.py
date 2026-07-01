"""Stop-safe Forge v2 campaign scheduler.

This is the overnight/autoresearch wrapper around the one-campaign runner. It
does not change the statistical gates in runner.py; it only repeats bounded
campaigns, records an outer ledger, and stops before cost/time/invalid-run drift
turns a measurement loop into a spend loop.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

WT = Path(__file__).resolve().parents[3]
if str(WT) not in sys.path:
    sys.path.insert(0, str(WT))
os.environ.setdefault("DOCKER_CONTEXT", os.environ.get("FORGE_DOCKER_CONTEXT", "colima-forge-swebench"))

from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402

from .analysis import build_campaign_report, choose_adaptive_instances, write_campaign_report  # noqa: E402
from .runner import run as runner_run  # noqa: E402

RUN_ROOT = dharma_state_dir() / "forge_v1" / "forge_v2" / "scheduler"

DEFAULT_INSTANCES = [
    "django__django-12209",
    "sympy__sympy-22914",
    "sympy__sympy-19954",
    "django__django-11141",
    "sympy__sympy-15599",
]

DEFAULT_INSTANCE_POOL = [
    *DEFAULT_INSTANCES,
    "psf__requests-2317",
    "django__django-11099",
    "django__django-11848",
    "sympy__sympy-13437",
    "sympy__sympy-17655",
]

STOP_MAX_CAMPAIGNS = "max_campaigns"
STOP_DURATION = "duration_hours"
STOP_COST = "cost_cap_usd"
STOP_INVALID = "invalid_run_cap"


def now_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(payload, sort_keys=True, default=str) + "\n")


def cost_from_attempts(receipt: dict[str, Any]) -> float:
    total = 0.0
    for attempt in receipt.get("attempts", []):
        budget = attempt.get("budget", {}) if isinstance(attempt, dict) else {}
        try:
            total += float(budget.get("total_cost_usd") or 0.0)
        except (TypeError, ValueError):
            continue
    return round(total, 6)


def receipt_summary(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "arm": receipt.get("arm"),
        "class_null": receipt.get("class_null"),
        "closeout": receipt.get("closeout"),
        "n_pairs": receipt.get("n_pairs", 0),
        "lift": receipt.get("contrast_vs_class_null", {}),
        "split_contrasts": receipt.get("split_contrasts", {}),
        "critic": receipt.get("critic_verdict", {}),
        "contamination_state": receipt.get("contamination_state", {}).get("state"),
        "budget_matched_proof": receipt.get("budget_matched_proof", {}),
        "cost_usd": cost_from_attempts(receipt),
        "attempt_count": len(receipt.get("attempts", []) or []),
        "artifact_dir": receipt.get("artifact_dir", ""),
        "next_experiment": receipt.get("next_experiment", ""),
    }


def stop_reason(*, completed: int, invalid_runs: int, total_cost_usd: float, start: float,
                max_campaigns: int, invalid_run_cap: int, cost_cap_usd: float | None,
                duration_hours: float | None) -> str | None:
    if completed >= max_campaigns:
        return STOP_MAX_CAMPAIGNS
    if invalid_runs >= invalid_run_cap:
        return STOP_INVALID
    if cost_cap_usd is not None and total_cost_usd >= cost_cap_usd:
        return STOP_COST
    if duration_hours is not None and (time.time() - start) >= duration_hours * 3600:
        return STOP_DURATION
    return None


def dry_run_receipt(*, campaign_index: int, instances: list[str], n_explore: int,
                    replicates: int, budget_cap: int, budget_usd: float,
                    arm: str = "verify_chain") -> dict[str, Any]:
    n_pairs = len(instances) * replicates
    return {
        "kind": "forge_v2_dry_run",
        "campaign_index": campaign_index,
        "arm": arm,
        "class_null": "self_moa",
        "closeout": "dry_run",
        "n_pairs": n_pairs,
        "contrast_vs_class_null": {"n": n_pairs, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        "split_contrasts": {
            "explore": {"n": min(n_explore, len(instances)) * replicates, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
            "confirm": {"n": max(0, len(instances) - n_explore) * replicates, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        },
        "critic_verdict": {"ran": False},
        "contamination_state": {"state": "dry_run"},
        "budget_matched_proof": {
            "cap_tokens": budget_cap,
            "cap_usd": budget_usd,
            "any_invalid": False,
            "self_moa_pass_rate": 0.0,
            "verify_chain_pass_rate": 0.0,
        },
        "attempts": [],
        "next_experiment": "dry-run only; no model or Docker calls made",
    }


def ingest_learning_spine(
    run_dir: Path,
    *,
    store_root: Path | str | None,
    epoch_id: str,
) -> dict[str, Any]:
    """Ingest the latest campaign-boundary report into the shadow learning spine."""
    from .ingest_learning import ingest_run

    return ingest_run(run_dir, store_root=store_root, epoch_id=epoch_id)


def run_scheduler(
    *,
    instances: list[str],
    n_explore: int,
    replicates: int,
    budget_cap: int,
    campaign_budget_usd: float,
    per_call_tokens: int,
    k_self_moa: int,
    grade_timeout: int,
    timeout_s: int,
    strategy: str,
    roster_n: int,
    generator: str,
    verifier: str,
    arms: list[str],
    mix_models: list[str],
    label: str,
    max_campaigns: int,
    duration_hours: float | None,
    total_budget_usd: float | None,
    invalid_run_cap: int,
    sleep_seconds: float,
    instance_pool: list[str] | None = None,
    adaptive: bool = False,
    adaptive_target_count: int | None = None,
    hard_self_moa_threshold: float = 1.0,
    dry_run: bool = False,
    ingest_learning: bool = False,
    learning_store_root: Path | str | None = None,
    epoch_id: str = "epoch_0",
    runner: Callable[..., dict[str, Any]] = runner_run,
    learning_ingester: Callable[..., dict[str, Any]] = ingest_learning_spine,
) -> dict[str, Any]:
    out = RUN_ROOT / f"{label}_{now_stamp()}"
    out.mkdir(parents=True, exist_ok=True)
    ledger_path = out / "campaign_ledger.jsonl"

    arms = [arm for arm in arms if arm] or ["verify_chain"]
    pool = list(dict.fromkeys(instance_pool or instances))
    target_count = adaptive_target_count or len(instances)
    history_attempts: list[dict[str, Any]] = []

    state = {
        "schema": "forge_v2_scheduler.v1",
        "started_at": now_stamp(),
        "run_dir": str(out),
        "label": label,
        "dry_run": dry_run,
        "config": {
            "instances": instances,
            "n_explore": n_explore,
            "replicates": replicates,
            "budget_cap": budget_cap,
            "campaign_budget_usd": campaign_budget_usd,
            "per_call_tokens": per_call_tokens,
            "k_self_moa": k_self_moa,
            "grade_timeout": grade_timeout,
            "timeout_s": timeout_s,
            "strategy": strategy,
            "roster_n": roster_n,
            "generator": generator,
            "verifier": verifier,
            "arms": arms,
            "mix_models": mix_models,
            "instance_pool": pool,
            "max_campaigns": max_campaigns,
            "duration_hours": duration_hours,
            "total_budget_usd": total_budget_usd,
            "invalid_run_cap": invalid_run_cap,
            "sleep_seconds": sleep_seconds,
            "adaptive": adaptive,
            "adaptive_target_count": target_count,
            "hard_self_moa_threshold": hard_self_moa_threshold,
        },
        "completed_campaigns": 0,
        "invalid_runs": 0,
        "total_cost_usd": 0.0,
        "last_closeout": None,
        "stop_reason": None,
        "learning_spine": {
            "enabled": ingest_learning,
            "epoch_id": epoch_id,
            "store_root": str(learning_store_root) if learning_store_root else "",
            "ingests": 0,
            "failures": 0,
            "last_ingest": None,
        },
        "campaigns": [],
    }
    write_json(out / "state.json", state)

    start = time.time()
    while True:
        reason = stop_reason(
            completed=state["completed_campaigns"],
            invalid_runs=state["invalid_runs"],
            total_cost_usd=state["total_cost_usd"],
            start=start,
            max_campaigns=max_campaigns,
            invalid_run_cap=invalid_run_cap,
            cost_cap_usd=total_budget_usd,
            duration_hours=duration_hours,
        )
        if reason is not None:
            state["stop_reason"] = reason
            break

        campaign_index = state["completed_campaigns"] + 1
        campaign_label = f"{label}_c{campaign_index:04d}"
        current_arm = arms[(campaign_index - 1) % len(arms)]
        current_instances = list(instances)
        if adaptive and history_attempts:
            current_instances = choose_adaptive_instances(
                pool,
                history_attempts,
                target_count=target_count,
                hard_self_moa_threshold=hard_self_moa_threshold,
            )
        current_n_explore = min(n_explore, max(0, len(current_instances) - 1))
        row: dict[str, Any] = {
            "campaign_index": campaign_index,
            "campaign_label": campaign_label,
            "arm": current_arm,
            "instances": current_instances,
            "n_explore": current_n_explore,
            "started_at": now_stamp(),
        }
        append_jsonl(ledger_path, {"event": "campaign_start", **row})
        write_json(out / "state.json", state)

        try:
            if dry_run:
                receipt = dry_run_receipt(
                    campaign_index=campaign_index,
                    instances=current_instances,
                    n_explore=current_n_explore,
                    replicates=replicates,
                    budget_cap=budget_cap,
                    budget_usd=campaign_budget_usd,
                    arm=current_arm,
                )
            else:
                receipt = runner(
                    current_instances,
                    n_explore=current_n_explore,
                    replicates=replicates,
                    budget_cap=budget_cap,
                    budget_usd=campaign_budget_usd,
                    per_call_tokens=per_call_tokens,
                    k_self_moa=k_self_moa,
                    grade_timeout=grade_timeout,
                    timeout_s=timeout_s,
                    strategy=strategy,
                    roster_n=roster_n,
                    gen_id=generator,
                    ver_id=verifier,
                    label=campaign_label,
                    arm=current_arm,
                    mix_ids=mix_models,
                )
            for attempt in receipt.get("attempts", []) or []:
                if isinstance(attempt, dict):
                    history_attempts.append({**attempt, "_campaign_index": campaign_index})
            summary = receipt_summary(receipt)
            row.update({"finished_at": now_stamp(), "status": "ok", **summary})
        except Exception as exc:  # noqa: BLE001 - overnight loop must receipt failures.
            row.update({
                "finished_at": now_stamp(),
                "status": "error",
                "closeout": "blocked_with_evidence",
                "error": f"{type(exc).__name__}: {exc}",
                "cost_usd": 0.0,
            })

        state["completed_campaigns"] += 1
        state["total_cost_usd"] = round(state["total_cost_usd"] + float(row.get("cost_usd") or 0.0), 6)
        state["last_closeout"] = row.get("closeout")
        if row.get("closeout") == "invalid_budget" or row.get("status") == "error":
            state["invalid_runs"] += 1
        state["campaigns"].append(row)
        append_jsonl(ledger_path, {"event": "campaign_finish", **row})
        write_json(out / "state.json", state)
        try:
            report = build_campaign_report(out, receipt_root=RUN_ROOT.parent)
            write_campaign_report(report, out)
        except Exception as exc:  # noqa: BLE001 - report failure must not kill a long run.
            append_jsonl(ledger_path, {"event": "meta_report_error", "error": f"{type(exc).__name__}: {exc}",
                                       "at": now_stamp()})
        else:
            if ingest_learning:
                try:
                    ingest_summary = learning_ingester(
                        out,
                        store_root=learning_store_root,
                        epoch_id=epoch_id,
                    )
                    state["learning_spine"]["ingests"] += 1
                    state["learning_spine"]["last_ingest"] = ingest_summary
                    append_jsonl(
                        ledger_path,
                        {
                            "event": "learning_spine_ingest",
                            "campaign_index": campaign_index,
                            "at": now_stamp(),
                            "summary": ingest_summary,
                        },
                    )
                    write_json(out / "state.json", state)
                except Exception as exc:  # noqa: BLE001 - learning must not kill measurement.
                    failure = {
                        "event": "learning_spine_error",
                        "campaign_index": campaign_index,
                        "at": now_stamp(),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                    state["learning_spine"]["failures"] += 1
                    state["learning_spine"]["last_ingest"] = failure
                    append_jsonl(ledger_path, failure)
                    write_json(out / "state.json", state)

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    state["finished_at"] = now_stamp()
    write_json(out / "state.json", state)
    write_json(out / "decision_record.json", state)
    try:
        report = build_campaign_report(out, receipt_root=RUN_ROOT.parent)
        write_campaign_report(report, out)
    except Exception as exc:  # noqa: BLE001
        append_jsonl(ledger_path, {"event": "meta_report_error", "error": f"{type(exc).__name__}: {exc}",
                                   "at": now_stamp()})
    append_jsonl(ledger_path, {"event": "scheduler_stop", "stop_reason": state["stop_reason"],
                               "finished_at": state["finished_at"], "total_cost_usd": state["total_cost_usd"],
                               "completed_campaigns": state["completed_campaigns"]})
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forge v2 overnight campaign scheduler")
    parser.add_argument("--instances", default=",".join(DEFAULT_INSTANCES))
    parser.add_argument("--n-explore", type=int, default=3)
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--budget", type=int, default=60000)
    parser.add_argument("--campaign-budget-usd", type=float, default=0.25)
    parser.add_argument("--per-call-tokens", type=int, default=3500)
    parser.add_argument("--k-self-moa", type=int, default=1)
    parser.add_argument("--grade-timeout", type=int, default=1200)
    parser.add_argument("--timeout-s", type=int, default=240)
    parser.add_argument("--strategy", default="explore")
    parser.add_argument("--roster-n", type=int, default=14)
    parser.add_argument("--generator", default="glm-5.2")
    parser.add_argument("--verifier", default="moonshotai/kimi-k2.6")
    parser.add_argument("--arms", default="verify_chain", help="comma-separated arm rotation, e.g. verify_chain,mixed_moa")
    parser.add_argument("--mix-models", default="", help="comma-separated pinned mixed_moa model ids")
    parser.add_argument("--label", default="overnight_verifier_role")
    parser.add_argument("--max-campaigns", type=int, default=100)
    parser.add_argument("--duration-hours", type=float, default=8.0)
    parser.add_argument("--total-budget-usd", type=float, default=5.0)
    parser.add_argument("--invalid-run-cap", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--instance-pool", default=",".join(DEFAULT_INSTANCE_POOL))
    parser.add_argument("--adaptive", action="store_true")
    parser.add_argument("--adaptive-target-count", type=int, default=0)
    parser.add_argument("--hard-self-moa-threshold", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-ingest-learning", action="store_true",
                        help="Do not ingest campaign-boundary reports into the learning spine.")
    parser.add_argument("--learning-store-root", default=None,
                        help="Learning spine store root (default: ~/.dharma/forge_v1/learning_signals).")
    parser.add_argument("--epoch-id", default="epoch_0",
                        help="Epoch tag for learning signals written by this scheduler run.")
    args = parser.parse_args(argv)

    ids = [x.strip() for x in args.instances.split(",") if x.strip()]
    arms = [x.strip() for x in args.arms.split(",") if x.strip()]
    mix_models = [x.strip() for x in args.mix_models.split(",") if x.strip()]
    instance_pool = [x.strip() for x in args.instance_pool.split(",") if x.strip()]
    state = run_scheduler(
        instances=ids,
        n_explore=args.n_explore,
        replicates=args.replicates,
        budget_cap=args.budget,
        campaign_budget_usd=args.campaign_budget_usd,
        per_call_tokens=args.per_call_tokens,
        k_self_moa=args.k_self_moa,
        grade_timeout=args.grade_timeout,
        timeout_s=args.timeout_s,
        strategy=args.strategy,
        roster_n=args.roster_n,
        generator=args.generator,
        verifier=args.verifier,
        arms=arms,
        mix_models=mix_models,
        label=args.label,
        max_campaigns=args.max_campaigns,
        duration_hours=args.duration_hours,
        total_budget_usd=args.total_budget_usd,
        invalid_run_cap=args.invalid_run_cap,
        sleep_seconds=args.sleep_seconds,
        instance_pool=instance_pool,
        adaptive=args.adaptive,
        adaptive_target_count=args.adaptive_target_count or None,
        hard_self_moa_threshold=args.hard_self_moa_threshold,
        dry_run=args.dry_run,
        ingest_learning=not args.no_ingest_learning,
        learning_store_root=args.learning_store_root,
        epoch_id=args.epoch_id,
    )
    print(
        f"[forge_v2_scheduler] stop={state['stop_reason']} campaigns={state['completed_campaigns']} "
        f"invalid={state['invalid_runs']} cost_usd={state['total_cost_usd']} dir={state['run_dir']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
