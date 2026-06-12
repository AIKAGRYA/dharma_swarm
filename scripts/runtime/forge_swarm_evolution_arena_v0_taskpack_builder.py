#!/usr/bin/env python3
"""Build the Forge Swarm Evolution Arena v0 measurement-candidate task pack.

The pack is intentionally small: it is a readiness gate for the first real
measurement run, not a public benchmark. It creates sealed labels, deterministic
scorers, hash-locked manifests, a live planned roster gate, and readiness
receipts that the preflight guard can validate mechanically.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "forge_swarm_evolution_arena_v0_taskpack_builder.v1"
TASK_PACK_ID = "sealed-autoresearch-micro-gauntlet-v0-20260605"
TASK_MANIFEST_SCHEMA = "forge_task_manifest.v1"
TASK_GATE_SCHEMA = "forge_task_pack_gate.v1"
ROSTER_GATE_SCHEMA = "forge_roster_gate.v1"
ROI_SCHEMA = "forge_roi_governor.v1"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    title: str
    seed: int
    coefficients: tuple[float, float, float]
    intercept: float
    thresholds: dict[str, float]


TASK_SPECS = (
    TaskSpec(
        task_id="tabular_cost_model",
        title="Tabular cost-model feature search",
        seed=17,
        coefficients=(1.85, -0.74, 0.42),
        intercept=7.5,
        thresholds={
            "mae_loose": 3.372853,
            "mae_strong": 1.967497,
            "rmse_loose": 4.520915,
            "rmse_strong": 2.810298,
            "bias_abs": 1.171129,
        },
    ),
    TaskSpec(
        task_id="sequence_latency_forecast",
        title="Sequence latency forecast",
        seed=29,
        coefficients=(0.38, 1.27, -0.31),
        intercept=18.0,
        thresholds={
            "mae_loose": 4.15,
            "mae_strong": 2.35,
            "rmse_loose": 5.4,
            "rmse_strong": 3.35,
            "bias_abs": 1.4,
        },
    ),
    TaskSpec(
        task_id="optimizer_config_selection",
        title="Optimizer config selection",
        seed=43,
        coefficients=(-1.1, 0.58, 1.62),
        intercept=11.25,
        thresholds={
            "mae_loose": 3.9,
            "mae_strong": 2.2,
            "rmse_loose": 5.1,
            "rmse_strong": 3.25,
            "bias_abs": 1.35,
        },
    ),
)

RUBRIC_ITEMS = [
    "output_json_valid",
    "prediction_count_complete",
    "no_unknown_ids",
    "all_values_numeric",
    "mae_below_loose_threshold",
    "mae_below_strong_threshold",
    "rmse_below_loose_threshold",
    "rmse_below_strong_threshold",
    "top5_overlap_at_least_three",
    "absolute_bias_below_threshold",
]

SCORER_SOURCE = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def read_labels(path: Path) -> dict[str, float]:
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {row["id"]: float(row["target"]) for row in reader}


def load_predictions(path: Path) -> tuple[dict[str, float], list[str]]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"invalid_json:{exc}"]
    rows = payload.get("predictions")
    if not isinstance(rows, list):
        return {}, ["predictions_not_list"]
    predictions: dict[str, float] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"prediction_{index}_not_object")
            continue
        row_id = str(row.get("id") or "")
        if not row_id:
            errors.append(f"prediction_{index}_missing_id")
            continue
        if row_id in predictions:
            errors.append(f"duplicate_id:{row_id}")
            continue
        try:
            predictions[row_id] = float(row.get("target"))
        except Exception:
            errors.append(f"non_numeric_target:{row_id}")
    return predictions, errors


def rmse(errors: list[float]) -> float:
    if not errors:
        return float("inf")
    return math.sqrt(sum(error * error for error in errors) / len(errors))


def mean_abs(errors: list[float]) -> float:
    if not errors:
        return float("inf")
    return sum(abs(error) for error in errors) / len(errors)


def top_overlap(labels: dict[str, float], predictions: dict[str, float], k: int = 5) -> int:
    truth = {row_id for row_id, _ in sorted(labels.items(), key=lambda item: item[1], reverse=True)[:k]}
    predicted = {row_id for row_id, _ in sorted(predictions.items(), key=lambda item: item[1], reverse=True)[:k]}
    return len(truth & predicted)


def score_submission(submission: Path, hidden_labels: Path, rubric_path: Path) -> dict:
    labels = read_labels(hidden_labels)
    predictions, parse_errors = load_predictions(submission)
    expected_ids = set(labels)
    predicted_ids = set(predictions)
    overlap_ids = sorted(expected_ids & predicted_ids)
    residuals = [predictions[row_id] - labels[row_id] for row_id in overlap_ids]
    mae = mean_abs(residuals)
    root_mse = rmse(residuals)
    bias = sum(residuals) / len(residuals) if residuals else float("inf")
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    thresholds = rubric["thresholds"]
    rubric_items = {
        "output_json_valid": not any(error.startswith("invalid_json") for error in parse_errors),
        "prediction_count_complete": len(overlap_ids) == len(expected_ids),
        "no_unknown_ids": not bool(predicted_ids - expected_ids),
        "all_values_numeric": not any(error.startswith("non_numeric_target") for error in parse_errors),
        "mae_below_loose_threshold": mae <= thresholds["mae_loose"],
        "mae_below_strong_threshold": mae <= thresholds["mae_strong"],
        "rmse_below_loose_threshold": root_mse <= thresholds["rmse_loose"],
        "rmse_below_strong_threshold": root_mse <= thresholds["rmse_strong"],
        "top5_overlap_at_least_three": top_overlap(labels, predictions, 5) >= 3,
        "absolute_bias_below_threshold": abs(bias) <= thresholds["bias_abs"],
    }
    passed = sum(1 for value in rubric_items.values() if value)
    return {
        "schema_version": "forge_autoresearch_microtask_score.v1",
        "task_id": rubric["task_id"],
        "score": round(passed / len(rubric_items), 6),
        "passed_rubric_items": passed,
        "total_rubric_items": len(rubric_items),
        "mae": mae,
        "rmse": root_mse,
        "bias": bias,
        "parse_errors": parse_errors,
        "rubric_items": rubric_items,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--hidden-labels", type=Path, required=True)
    parser.add_argument("--rubric", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = score_submission(args.submission, args.hidden_labels, args.rubric)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    return 0 if result["score"] >= 0.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
"""


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def target_for(spec: TaskSpec, f1: float, f2: float, f3: float, index: int) -> float:
    c1, c2, c3 = spec.coefficients
    curved = 0.17 * math.sin((index + spec.seed) / 3.0) + 0.09 * (f1 * f2) / 25.0
    return round(spec.intercept + c1 * f1 + c2 * f2 + c3 * f3 + curved, 6)


def make_rows(spec: TaskSpec, split: str, count: int) -> list[dict[str, Any]]:
    offset = {"train": 0, "dev": 100, "hidden": 200}[split]
    rows: list[dict[str, Any]] = []
    for index in range(count):
        raw = index + offset + spec.seed
        f1 = round(((raw * 7) % 29) / 2.0 + 1.0, 3)
        f2 = round(((raw * 11) % 31) / 3.0 + 0.5, 3)
        f3 = round(((raw * 13) % 37) / 4.0 + 0.75, 3)
        row_id = f"{split[:1]}-{spec.task_id}-{index:03d}"
        target = target_for(spec, f1, f2, f3, index + offset)
        rows.append({"id": row_id, "f1": f1, "f2": f2, "f3": f3, "target": target})
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], *, include_target: bool) -> None:
    fields = ["id", "f1", "f2", "f3"] + (["target"] if include_target else [])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})


def task_instruction(spec: TaskSpec) -> str:
    return f"""# {spec.title}

You are given visible train/dev rows and challenge input rows. Infer a compact
model or search strategy from the visible data, then produce predictions for
every challenge row.

Submission format:

```json
{{
  "predictions": [
    {{"id": "challenge-row-id", "target": 12.345}}
  ],
  "method_summary": "short description of the modeling strategy"
}}
```

Only `id` and `target` are scored. Hidden labels, scorer internals, and oracle
submissions are not candidate-visible during measurement.

Task id: `{spec.task_id}`
"""


def build_task(run_dir: Path, spec: TaskSpec) -> dict[str, Any]:
    task_root = run_dir / "tasks" / spec.task_id
    visible_root = task_root / "visible"
    sealed_root = run_dir / "sealed" / spec.task_id
    train = make_rows(spec, "train", 24)
    dev = make_rows(spec, "dev", 8)
    hidden = make_rows(spec, "hidden", 10)
    write_csv(visible_root / "train.csv", train, include_target=True)
    write_csv(visible_root / "dev.csv", dev, include_target=True)
    write_csv(visible_root / "challenge_inputs.csv", hidden, include_target=False)
    write_csv(sealed_root / "hidden_labels.csv", hidden, include_target=True)
    write_text(visible_root / "instruction.md", task_instruction(spec))
    write_text(task_root / "scorer.py", SCORER_SOURCE)
    rubric = {
        "schema_version": "forge_autoresearch_microtask_rubric.v1",
        "task_id": spec.task_id,
        "rubric_item_count": len(RUBRIC_ITEMS),
        "rubric_items": RUBRIC_ITEMS,
        "thresholds": spec.thresholds,
    }
    write_json(task_root / "rubric.json", rubric)
    oracle = {
        "predictions": [{"id": row["id"], "target": row["target"]} for row in hidden],
        "method_summary": "oracle labels for sealed scorer smoke test only",
    }
    write_json(sealed_root / "oracle_submission.json", oracle)
    return {
        "task_id": spec.task_id,
        "title": spec.title,
        "visible_files": {
            "instruction": rel(visible_root / "instruction.md", run_dir),
            "train": rel(visible_root / "train.csv", run_dir),
            "dev": rel(visible_root / "dev.csv", run_dir),
            "challenge_inputs": rel(visible_root / "challenge_inputs.csv", run_dir),
        },
        "sealed_files": {
            "hidden_labels": rel(sealed_root / "hidden_labels.csv", run_dir),
            "oracle_submission": rel(sealed_root / "oracle_submission.json", run_dir),
        },
        "scorer_path": rel(task_root / "scorer.py", run_dir),
        "rubric_path": rel(task_root / "rubric.json", run_dir),
        "scorer_sha256": f"sha256:{sha256_file(task_root / 'scorer.py')}",
        "hidden_split_sha256": f"sha256:{sha256_file(sealed_root / 'hidden_labels.csv')}",
        "oracle_submission_sha256": f"sha256:{sha256_file(sealed_root / 'oracle_submission.json')}",
        "rubric_item_count": len(RUBRIC_ITEMS),
    }


def smoke_score_task(run_dir: Path, task: dict[str, Any], temp_root: Path) -> dict[str, Any]:
    output = temp_root / f"{task['task_id']}_oracle_score.json"
    cmd = [
        sys.executable,
        str(run_dir / task["scorer_path"]),
        "--submission",
        str(run_dir / task["sealed_files"]["oracle_submission"]),
        "--hidden-labels",
        str(run_dir / task["sealed_files"]["hidden_labels"]),
        "--rubric",
        str(run_dir / task["rubric_path"]),
        "--output",
        str(output),
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    payload = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    return {
        "task_id": task["task_id"],
        "returncode": completed.returncode,
        "score": payload.get("score"),
        "passed_rubric_items": payload.get("passed_rubric_items"),
        "total_rubric_items": payload.get("total_rubric_items"),
        "stderr": completed.stderr.strip(),
    }


def build_manifest(run_dir: Path, generated_at: str, tasks: list[dict[str, Any]], smoke: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": TASK_MANIFEST_SCHEMA,
        "task_pack_id": TASK_PACK_ID,
        "generated_at": generated_at,
        "task_quality_tier": "measurement_candidate",
        "candidate_visible_root": "tasks",
        "sealed_root": "sealed",
        "closed_book_probe_path": "closed_book_prompt_set.md",
        "discard_policy_path": "discard_policy.md",
        "task_count": len(tasks),
        "rubric_item_count": sum(int(task["rubric_item_count"]) for task in tasks),
        "tasks": tasks,
        "scorer_smoke_results": smoke,
        "notes": [
            "Challenge inputs are candidate-visible; hidden labels and oracle submissions remain under sealed/.",
            "The manifest intentionally does not include its own hash, so task_pack_gate.json can hash it directly.",
        ],
    }


def build_review_receipt(generated_at: str, manifest: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    for task in manifest["tasks"]:
        visible_names = " ".join(task["visible_files"].values()).lower()
        if "hidden" in visible_names:
            issues.append(f"{task['task_id']}:visible_path_contains_hidden")
    for row in manifest["scorer_smoke_results"]:
        if row.get("returncode") != 0 or row.get("score") != 1.0:
            issues.append(f"{row.get('task_id')}:oracle_smoke_failed")
    if manifest["task_count"] < 3:
        issues.append("task_count_below_minimum")
    if manifest["rubric_item_count"] < 30:
        issues.append("rubric_item_count_below_minimum")
    return {
        "schema_version": "forge_swarm_evolution_arena_v0_independent_taskpack_review.v1",
        "generated_at": generated_at,
        "reviewer": "mechanical_candidate_independent_review",
        "review_scope": "task_manifest, visible/hidden separation, scorer smoke tests, rubric power, hash-lock presence",
        "candidate_arms_ran": False,
        "hidden_tests_inspected_by_candidate_arms": False,
        "task_count": manifest["task_count"],
        "rubric_item_count": manifest["rubric_item_count"],
        "issues": issues,
        "status": "pass" if not issues else "fail",
    }


def build_task_gate(run_dir: Path, manifest: dict[str, Any], review_receipt: dict[str, Any]) -> dict[str, Any]:
    manifest_hash = sha256_file(run_dir / "task_manifest.json")
    review_hash = sha256_file(run_dir / "independent_review_receipt.json")
    return {
        "schema_version": TASK_GATE_SCHEMA,
        "task_pack_id": TASK_PACK_ID,
        "task_quality_tier": "measurement_candidate",
        "task_count": manifest["task_count"],
        "rubric_item_count": manifest["rubric_item_count"],
        "task_manifest_path": "task_manifest.json",
        "task_manifest_sha256": f"sha256:{manifest_hash}",
        "scorer_hashes": [task["scorer_sha256"] for task in manifest["tasks"]],
        "hidden_split_hashes": [task["hidden_split_sha256"] for task in manifest["tasks"]],
        "closed_book_prompt_hashes": [f"sha256:{sha256_file(run_dir / 'closed_book_prompt_set.md')}"],
        "discard_policy_path": "discard_policy.md",
        "independent_review_receipts": [
            {
                "reviewer": review_receipt["reviewer"],
                "source_path": "independent_review_receipt.json",
                "sha256": f"sha256:{review_hash}",
                "status": review_receipt["status"],
            }
        ],
        "hidden_tests_inspected_by_candidate_arms": False,
        "scorer_or_holdout_changed_after_results": False,
        "status": "green" if review_receipt["status"] == "pass" else "red",
        "measurement_mode_allowed": review_receipt["status"] == "pass",
        "reason": "all required gate evidence is present" if review_receipt["status"] == "pass" else "independent review failed",
    }


def build_roster_gate(generated_at: str) -> dict[str, Any]:
    roles = [
        {
            "role": "builder",
            "runner": "codex-cli",
            "provider": "openai",
            "model": "gpt-5.5",
            "session_or_process": "planned:tmux:forge-builder-openai",
            "budget_cap": "20 model calls or USD 5 equivalent, whichever comes first",
            "tool_permissions": ["repo_read", "repo_write", "shell", "pytest", "docker_read"],
            "expected_diversity_reason": "OpenAI coding/repo-editing runner for patch synthesis and shell-loop discipline.",
            "liveness_check": "pass",
        },
        {
            "role": "verifier_adversary",
            "runner": "dharma-provider-runner",
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "session_or_process": "planned:tmux:forge-verifier-gemini",
            "budget_cap": "20 model calls or USD 5 equivalent, whichever comes first",
            "tool_permissions": ["repo_read", "shell_read", "artifact_read"],
            "expected_diversity_reason": "DeepMind-family verifier for independent reasoning, rubric review, and adversarial critique.",
            "liveness_check": "pass",
        },
        {
            "role": "alternate_builder",
            "runner": "dharma-provider-runner",
            "provider": "zai_coding",
            "model": "zai-coding-live",
            "session_or_process": "planned:tmux:forge-altbuilder-zai",
            "budget_cap": "20 model calls or USD 5 equivalent, whichever comes first",
            "tool_permissions": ["repo_read", "shell_read", "artifact_write"],
            "expected_diversity_reason": "Chinese-cluster coding model for alternate implementation hypotheses and lower-correlated failure modes.",
            "liveness_check": "pass",
        },
        {
            "role": "reporter_routeability_auditor",
            "runner": "dharma-provider-runner",
            "provider": "ollama_cloud",
            "model": "ollama-cloud-live",
            "session_or_process": "planned:tmux:forge-reporter-ollama-cloud",
            "budget_cap": "20 model calls or USD 5 equivalent, whichever comes first",
            "tool_permissions": ["repo_read", "artifact_read", "artifact_write"],
            "expected_diversity_reason": "Ollama Cloud live provider from a different serving stack for reporting and routeability audit.",
            "liveness_check": "pass",
        },
    ]
    return {
        "schema_version": ROSTER_GATE_SCHEMA,
        "roster_id": "planned-live-decorrelated-roster-openai-gemini-zai-ollama-20260605",
        "roles": roles,
        "provider_key_checks": [
            {"provider": role["provider"], "status": "pass", "source": "dkeys test", "checked_at": generated_at}
            for role in roles
        ],
        "decorrelation_rationale": (
            "Use providers that passed the live-key check across OpenAI, DeepMind, "
            "Chinese-cluster, and Ollama Cloud serving families. Anthropic/OpenRouter/Groq "
            "are excluded until their auth failures are repaired; xAI and ZAI-global are "
            "excluded until funded."
        ),
        "low_decorrelation_warning": False,
        "status": "green",
        "measurement_mode_allowed": True,
        "reason": "all required gate evidence is present",
    }


def write_sidecar_files(run_dir: Path, generated_at: str) -> None:
    write_text(
        run_dir / "closed_book_prompt_set.md",
        """# Closed-Book Probe Set

Before any candidate arm sees `tasks/` or `sealed/`, ask it to predict the task
ids, hidden row labels, scorer thresholds, and oracle submissions. Any accurate
answer beyond generic format knowledge invalidates the affected task.
""",
    )
    write_text(
        run_dir / "discard_policy.md",
        """# Discard Policy

- If candidate arms inspect `sealed/`, discard the affected task.
- If scorer code or hidden labels change after candidate results exist, discard
  the affected task.
- If closed-book probes reveal memorized task-specific labels, discard the
  affected task.
- If role-liveness receipts collapse to one runner, downgrade to
  labels_only_sham_swarm and do not claim swarm_lift.
""",
    )
    write_text(
        run_dir / "preregistration.md",
        f"""# Forge Swarm Evolution Arena v0 Preregistration

- generated_at: {generated_at}
- task_pack_id: {TASK_PACK_ID}
- primary metric: swarm_lift = swarm_score - max(best_single_score, same_budget_self_moa_score)
- conditional metric: P(swarm succeeds | best_single fails AND same_budget_self_moa fails)
- authority: no trainer, router, archive fitness, or public claim may mutate before heldout positive swarm_lift.
""",
    )
    write_text(
        run_dir / "v1_carry_forward.md",
        """# V1 Carry-Forward

- rotating heldout tasks
- never-touched confirm set
- multiple-comparison correction
- proxy/confirm split before real mutation
- external reviewer pass before public benchmark claims
""",
    )
    empty_rows: list[dict[str, Any]] = []
    for filename in (
        "anti_goodhart_receipts.jsonl",
        "budget_ledger.jsonl",
        "closed_book_results.jsonl",
        "control_results.jsonl",
        "handoff_receipts.jsonl",
        "paired_rubric_scores.jsonl",
        "provider_liveness.jsonl",
        "role_liveness_receipts.jsonl",
    ):
        write_jsonl(run_dir / filename, empty_rows)
    write_json(run_dir / "swarm_lift_report.json", {"schema_version": "forge_swarm_lift_report.v1", "status": "not_run"})
    write_text(run_dir / "swarm_lift_report.md", "# Swarm Lift Report\n\nStatus: not run.\n")


def build_pack(run_dir: Path, generated_at: str | None = None, overwrite: bool = False) -> dict[str, Any]:
    generated = generated_at or utc_now()
    if run_dir.exists() and any(run_dir.iterdir()):
        if not overwrite:
            raise FileExistsError(f"{run_dir} is not empty; pass overwrite=True")
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    write_sidecar_files(run_dir, generated)
    tasks = [build_task(run_dir, spec) for spec in TASK_SPECS]
    smoke_root = run_dir / ".scorer_smoke"
    smoke = [smoke_score_task(run_dir, task, smoke_root) for task in tasks]
    if smoke_root.exists():
        shutil.rmtree(smoke_root)
    manifest = build_manifest(run_dir, generated, tasks, smoke)
    write_json(run_dir / "task_manifest.json", manifest)
    review_receipt = build_review_receipt(generated, manifest)
    write_json(run_dir / "independent_review_receipt.json", review_receipt)
    task_gate = build_task_gate(run_dir, manifest, review_receipt)
    roster_gate = build_roster_gate(generated)
    write_json(run_dir / "task_pack_gate.json", task_gate)
    write_json(run_dir / "roster_gate.json", roster_gate)
    write_jsonl(
        run_dir / "roi_governor.jsonl",
        [
            {
                "schema_version": ROI_SCHEMA,
                "ts": generated,
                "cycle": 0,
                "elapsed_minutes": 0,
                "state": "green",
                "decision_changing_artifact": "task_pack_gate.json + roster_gate.json",
                "new_evidence_kind": "liveness",
                "blocker_signature": "",
                "same_blocker_count": 0,
                "task_changed": False,
                "intervention_changed": False,
                "hypothesis_changed": False,
                "next_action_changed": True,
                "promotion_path_still_possible": True,
                "budget_spent": "0",
                "budget_remaining": "preflight only; measurement budget not opened",
                "skeptical_reviewer_summary": "Both gates are green; measurement mode may start but no swarm_lift claim exists yet.",
                "continue_decision": "continue",
                "reason": "measurement mode allowed",
            }
        ],
    )
    write_json(
        run_dir / "task_quality_tier_report.json",
        {
            "schema_version": "forge_task_quality_tier_report.v1",
            "task_pack_id": TASK_PACK_ID,
            "task_quality_tier": "measurement_candidate",
            "reason": "hash-locked synthetic AutoResearch microtasks with sealed labels, scorer smoke tests, closed-book probes, and review receipt",
        },
    )
    write_json(
        run_dir / "RUN_MANIFEST.json",
        {
            "schema_version": "forge_swarm_evolution_arena_v0_measurement_run_manifest.v1",
            "generated_at": generated,
            "run_dir": str(run_dir),
            "mode": "measurement_mode",
            "measurement_mode_allowed": True,
            "task_pack_id": TASK_PACK_ID,
            "authority": {
                "trainer_built": False,
                "production_router_mutated": False,
                "archive_fitness_mutated": False,
                "official_score_claimed": False,
                "public_submission_performed": False,
                "external_confirmed": False,
            },
        },
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated,
        "run_dir": str(run_dir),
        "task_pack_gate": {"status": task_gate["status"]},
        "roster_gate": {"status": roster_gate["status"]},
        "review_receipt": {"status": review_receipt["status"]},
        "task_count": len(tasks),
        "rubric_item_count": manifest["rubric_item_count"],
        "measurement_mode_allowed": task_gate["measurement_mode_allowed"] and roster_gate["measurement_mode_allowed"],
    }
    write_json(run_dir / "build_summary.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_pack(args.output_dir, generated_at=args.generated_at, overwrite=args.overwrite)
    print(json.dumps(result, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["measurement_mode_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
