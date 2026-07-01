"""Outer-loop analysis for Forge v2 scheduler campaigns.

The runner measures one falsification campaign. This module aggregates many
campaign receipts into a learning state the scheduler can use for the next run:
which arm actually moved lift, which tasks are saturated by the null, which tasks
remain hard, and whether any positive pocket survives FDR/CONFIRM discipline.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .stats import benjamini_hochberg, paired_bootstrap_ci


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def find_decision_records(run_dir: str | Path, *, receipt_root: str | Path | None = None) -> list[Path]:
    """Find child campaign decision records for a scheduler run.

    New scheduler rows carry artifact_dir. Older overnight runs did not, so this
    also falls back to campaign_label globbing under the Forge v2 receipt root.
    """
    run_path = Path(run_dir)
    state = read_json(run_path / "state.json")
    root = Path(receipt_root) if receipt_root else run_path.parent.parent
    records: list[Path] = []
    seen: set[Path] = set()
    for campaign in state.get("campaigns", []):
        if not isinstance(campaign, dict):
            continue
        artifact_dir = campaign.get("artifact_dir")
        candidates: list[Path] = []
        if artifact_dir:
            candidates.append(Path(str(artifact_dir)) / "decision_record.json")
        label = str(campaign.get("campaign_label") or "")
        if label:
            candidates.extend(sorted(root.glob(f"{label}_*/decision_record.json")))
        for candidate in candidates:
            if candidate.exists() and candidate not in seen:
                records.append(candidate)
                seen.add(candidate)
                break
    return records


def load_decision_records(run_dir: str | Path, *, receipt_root: str | Path | None = None) -> list[dict[str, Any]]:
    records = []
    for index, path in enumerate(find_decision_records(run_dir, receipt_root=receipt_root), start=1):
        payload = read_json(path)
        if payload:
            payload["_decision_record_path"] = str(path)
            payload["_campaign_index"] = index
            records.append(payload)
    return records


def attempts_from_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for campaign_index, record in enumerate(records, start=1):
        for attempt in record.get("attempts", []):
            if isinstance(attempt, dict):
                row = dict(attempt)
                row["_campaign_index"] = record.get("_campaign_index", campaign_index)
                row["_decision_record_path"] = record.get("_decision_record_path", "")
                rows.append(row)
    return rows


def pass_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return round(sum(1 for row in rows if row.get("resolved")) / len(rows), 4)


def paired_diffs(attempts: list[dict[str, Any]], *, arm: str, class_null: str = "self_moa") -> tuple[list[float], dict[str, list[float]]]:
    grouped: dict[tuple[Any, ...], dict[str, bool]] = defaultdict(dict)
    split_by_key: dict[tuple[Any, ...], str] = {}
    for row in attempts:
        row_arm = str(row.get("arm") or "")
        if row_arm not in {arm, class_null}:
            continue
        key = (
            row.get("_campaign_index"),
            row.get("task_id"),
            row.get("split"),
            row.get("replicate"),
        )
        grouped[key][row_arm] = bool(row.get("resolved"))
        split_by_key[key] = str(row.get("split") or "unknown")

    diffs: list[float] = []
    by_split: dict[str, list[float]] = defaultdict(list)
    for key, pair in grouped.items():
        if arm not in pair or class_null not in pair:
            continue
        diff = (1.0 if pair[arm] else 0.0) - (1.0 if pair[class_null] else 0.0)
        diffs.append(diff)
        by_split[split_by_key[key]].append(diff)
    return diffs, dict(by_split)


def task_statistics(attempts: list[dict[str, Any]], *, class_null: str = "self_moa") -> dict[str, dict[str, Any]]:
    by_task_arm: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in attempts:
        task_id = str(row.get("task_id") or "")
        arm = str(row.get("arm") or "")
        if task_id and arm:
            by_task_arm[task_id][arm].append(row)

    stats: dict[str, dict[str, Any]] = {}
    for task_id, arms in sorted(by_task_arm.items()):
        arm_stats = {
            arm: {
                "attempts": len(rows),
                "passes": sum(1 for row in rows if row.get("resolved")),
                "pass_rate": pass_rate(rows),
                "splits": sorted({str(row.get("split") or "unknown") for row in rows}),
            }
            for arm, rows in sorted(arms.items())
        }
        null_rate = arm_stats.get(class_null, {}).get("pass_rate", 0.0)
        lifts = {
            arm: round(data["pass_rate"] - null_rate, 4)
            for arm, data in arm_stats.items()
            if arm != class_null
        }
        stats[task_id] = {
            "arms": arm_stats,
            "class_null": class_null,
            "self_moa_pass_rate": null_rate,
            "hard_for_null": null_rate < 1.0,
            "saturated_by_null": null_rate >= 1.0,
            "lift_vs_null": lifts,
        }
    return stats


def reliability_summary(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm_task: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in attempts:
        arm = str(row.get("arm") or "")
        task_id = str(row.get("task_id") or "")
        if arm and task_id:
            by_arm_task[arm][task_id].append(row)
    out: dict[str, Any] = {}
    for arm, tasks in sorted(by_arm_task.items()):
        any_pass = 0
        all_pass = 0
        for rows in tasks.values():
            passes = sum(1 for row in rows if row.get("resolved"))
            any_pass += int(passes > 0)
            all_pass += int(passes == len(rows) and len(rows) > 0)
        n = len(tasks)
        out[arm] = {
            "task_count": n,
            "pass_at_observed_k": round(any_pass / n, 4) if n else 0.0,
            "pass_all_observed_replicates": round(all_pass / n, 4) if n else 0.0,
        }
    return out


def choose_adaptive_instances(
    instance_pool: list[str],
    attempts: list[dict[str, Any]],
    *,
    target_count: int,
    hard_self_moa_threshold: float = 1.0,
) -> list[str]:
    """Pick the next campaign's task set from receipts.

    Preference order: hard observed tasks where the class null is not saturated,
    then unobserved tasks from the pool, then the original pool order. This keeps
    the loop learning while still adding diversity when the current slice is flat.
    """
    pool = [item for item in dict.fromkeys(instance_pool) if item]
    if target_count <= 0:
        target_count = len(pool)
    if not attempts:
        return pool[:target_count]

    stats = task_statistics(attempts)
    observed = set(stats)
    scored: list[tuple[float, str]] = []
    for task_id, row in stats.items():
        null_rate = float(row.get("self_moa_pass_rate") or 0.0)
        if null_rate >= hard_self_moa_threshold:
            continue
        lifts = [abs(float(v)) for v in row.get("lift_vs_null", {}).values()]
        attempts_n = sum(int(arm.get("attempts") or 0) for arm in row.get("arms", {}).values())
        score = (hard_self_moa_threshold - null_rate) + (0.25 * max(lifts or [0.0])) + min(attempts_n, 50) * 0.001
        scored.append((score, task_id))
    scored.sort(key=lambda item: (-item[0], item[1]))

    selected: list[str] = []
    for _, task_id in scored:
        if task_id in pool and task_id not in selected:
            selected.append(task_id)
        if len(selected) >= target_count:
            return selected
    for task_id in pool:
        if task_id not in observed and task_id not in selected:
            selected.append(task_id)
        if len(selected) >= target_count:
            return selected
    for task_id in pool:
        if task_id not in selected:
            selected.append(task_id)
        if len(selected) >= target_count:
            return selected
    return selected


def build_campaign_report(run_dir: str | Path, *, receipt_root: str | Path | None = None) -> dict[str, Any]:
    run_path = Path(run_dir)
    state = read_json(run_path / "state.json")
    records = load_decision_records(run_path, receipt_root=receipt_root)
    attempts = attempts_from_records(records)
    task_stats = task_statistics(attempts)
    arms = sorted({str(row.get("arm")) for row in attempts if row.get("arm") and row.get("arm") != "self_moa"})
    config = state.get("config") or {}
    adaptive_run = bool(config.get("adaptive"))
    inference_scope = "explore_only_no_promotion" if adaptive_run else "fixed_allocation_confirmable"

    contrasts: dict[str, Any] = {}
    pvals: list[float] = []
    for arm in arms:
        diffs, by_split = paired_diffs(attempts, arm=arm)
        ci = paired_bootstrap_ci(diffs)
        split_ci = {split: paired_bootstrap_ci(vals) for split, vals in sorted(by_split.items())}
        contrasts[arm] = {"overall": ci, "by_split": split_ci}
        pvals.append(float(ci.get("p_le_0", 1.0)))
    fdr = benjamini_hochberg(pvals)
    for arm, significant in zip(arms, fdr):
        contrasts[arm]["fdr_positive_significant"] = bool(
            not adaptive_run
            and significant
            and contrasts[arm]["overall"].get("mean", 0.0) > 0
        )
        contrasts[arm]["promotion_suppressed_reason"] = (
            "adaptive_sequential_sampling_requires_alpha_spending_or_confirm_split"
            if adaptive_run and significant and contrasts[arm]["overall"].get("mean", 0.0) > 0
            else ""
        )

    closeout_counts = Counter(str(record.get("closeout") or "unknown") for record in records)
    pool = list(config.get("instance_pool") or config.get("instances") or [])
    target_count = len(config.get("instances") or pool)
    recommended_instances = choose_adaptive_instances(pool, attempts, target_count=target_count)
    tested_arms = set(arms)
    recommended_arms: list[str] = []
    if "mixed_moa" not in tested_arms:
        recommended_arms.append("mixed_moa")
    if "verify_chain" in tested_arms:
        vc_mean = float((contrasts.get("verify_chain", {}).get("overall") or {}).get("mean", 0.0))
        if vc_mean <= 0:
            recommended_arms.append("verify_chain_hard_only")
    if not recommended_arms:
        recommended_arms.append("repeat_best_arm_on_confirm")

    return {
        "schema": "forge_v2.campaign_meta_report.v1",
        "run_dir": str(run_path),
        "scheduler": {
            "label": state.get("label"),
            "started_at": state.get("started_at"),
            "finished_at": state.get("finished_at"),
            "stop_reason": state.get("stop_reason"),
            "completed_campaigns": state.get("completed_campaigns", 0),
            "invalid_runs": state.get("invalid_runs", 0),
            "total_cost_usd": state.get("total_cost_usd", 0.0),
        },
        "decision_record_count": len(records),
        "attempt_count": len(attempts),
        "inference_scope": inference_scope,
        "promotion_policy": {
            "adaptive_run": adaptive_run,
            "positive_promotion_allowed": not adaptive_run,
            "reason": (
                "adaptive sampling is EXPLORE-only until alpha-spending/pre-registration is implemented"
                if adaptive_run
                else "fixed allocation; FDR/CONFIRM gates may promote positive candidates"
            ),
        },
        "closeout_counts": dict(sorted(closeout_counts.items())),
        "arms_tested": arms,
        "contrasts": contrasts,
        "task_stats": task_stats,
        "reliability": reliability_summary(attempts),
        "learning_state": {
            "positive_lift_candidates": [
                arm for arm, row in contrasts.items() if row.get("fdr_positive_significant")
            ],
            "null_survived_arms": [
                arm for arm, row in contrasts.items() if (row.get("overall") or {}).get("mean", 0.0) <= 0
            ],
            "hard_task_count": sum(1 for row in task_stats.values() if row.get("hard_for_null")),
            "saturated_task_count": sum(1 for row in task_stats.values() if row.get("saturated_by_null")),
        },
        "next_policy": {
            "recommended_arms": recommended_arms,
            "recommended_instances": recommended_instances,
            "rationale": (
                "adaptive run: use as hypothesis generation only, then confirm under fixed allocation"
                if adaptive_run
                else "focus hard tasks in future EXPLORE runs, but promote only fixed-allocation confirmed effects"
            ),
        },
    }


def format_markdown_report(report: dict[str, Any]) -> str:
    scheduler = report.get("scheduler", {})
    lines = [
        "# Forge v2 Campaign Meta Report",
        "",
        f"Run dir: `{report.get('run_dir')}`",
        f"Stop reason: `{scheduler.get('stop_reason')}`",
        f"Campaigns: {scheduler.get('completed_campaigns', 0)}",
        f"Cost USD: {scheduler.get('total_cost_usd', 0.0)}",
        f"Inference scope: `{report.get('inference_scope')}`",
        "",
        "## Contrasts",
        "",
        "| Arm | n | Mean lift | CI lower | CI upper | p<=0 | FDR positive |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for arm, row in sorted((report.get("contrasts") or {}).items()):
        ci = row.get("overall") or {}
        lines.append(
            "| {arm} | {n} | {mean} | {lower} | {upper} | {p} | {sig} |".format(
                arm=arm,
                n=ci.get("n", 0),
                mean=ci.get("mean", 0.0),
                lower=ci.get("lower", 0.0),
                upper=ci.get("upper", 0.0),
                p=ci.get("p_le_0", 1.0),
                sig=str(bool(row.get("fdr_positive_significant"))).lower(),
            )
        )
    lines.extend(["", "## Next Policy", ""])
    policy = report.get("next_policy") or {}
    lines.append(f"Recommended arms: `{', '.join(policy.get('recommended_arms') or [])}`")
    lines.append(f"Recommended instances: `{', '.join(policy.get('recommended_instances') or [])}`")
    lines.append("")
    return "\n".join(lines)


def write_campaign_report(report: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    out = Path(output_dir)
    json_path = out / "campaign_meta_report.json"
    md_path = out / "campaign_meta_report.md"
    write_json(json_path, report)
    md_path.write_text(format_markdown_report(report), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate Forge v2 scheduler receipts")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--receipt-root", default="")
    args = parser.parse_args(argv)
    report = build_campaign_report(args.run_dir, receipt_root=args.receipt_root or None)
    json_path, md_path = write_campaign_report(report, args.run_dir)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(json.dumps(report.get("next_policy", {}), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
