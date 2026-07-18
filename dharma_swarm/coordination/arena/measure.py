"""Opt-in live Arena measurement with fail-closed parity controls.

This module is the only supported constructor for ``LiveWorkerPool``.  It does
not make a capability claim: a published result is a measurement candidate
whose controls and receipts have passed structural validation.  Real provider
evidence remains an operator-owned follow-up.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from dharma_swarm.coordination.arena.fixtures import ModelSpec
from dharma_swarm.coordination.arena.live_pool import (
    LiveDispatchError,
    LiveWorkerPool,
    Transport,
)
from dharma_swarm.coordination.arena.runner import CLOSEOUT_STATES, ArenaRunner
from dharma_swarm.coordination.arena.taskpack import TaskFamily, Taskpack
from dharma_swarm.coordination.genome import OrchestrationGenome
from dharma_swarm.ollama_config import OLLAMA_LOCAL_BASE_URL

LIVE_MEASUREMENT_SCHEMA = "orchestration_arena_v1_live_measurement.v1"
CLAIM_BOUNDARY = "measurement_candidate_only"
LIVE_CLOSEOUT_STATE = "blocked_with_evidence"
LIVE_OPT_IN_ENV = "DHARMA_ARENA_LIVE"
SIGNIFICANCE_METHOD = "paired_seeded_bootstrap_percentile"

_FAMILIES: tuple[TaskFamily, ...] = ("math", "code", "logic")
_REQUIRED_ARMS = frozenset(
    {
        "candidate",
        "best_single_full_budget",
        "best_single_parity_budget",
        "same_budget_self_moa",
        "random_or_static_ensemble",
    }
)
_RUNNER_OUTPUTS = frozenset(
    {
        "arena_run.json",
        "scorecard.json",
        "trace_receipts.jsonl",
        "route_receipts.jsonl",
        "council_receipts.jsonl",
        "power_index.json",
        "decision_packet.md",
    }
)
_LIVE_OUTPUTS = frozenset(
    {"live_worker_receipts.json", "live_measurement_receipt.json"}
)
_MANIFEST_OUTPUTS = (_RUNNER_OUTPUTS | _LIVE_OUTPUTS) - {
    "live_measurement_receipt.json"
}
_REPO_ROOT = Path(__file__).resolve().parents[3]


class LiveMeasurementError(RuntimeError):
    """The live route could not produce a complete, controlled measurement."""


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _external_output_path(raw: Path) -> Path:
    expanded = raw.expanduser()
    if not expanded.is_absolute():
        raise LiveMeasurementError("output_dir must be an absolute external path")
    if expanded.is_symlink() or expanded.exists():
        raise LiveMeasurementError("output_dir must not already exist")
    resolved = expanded.resolve(strict=False)
    if _is_within(resolved, _REPO_ROOT.resolve()):
        raise LiveMeasurementError("output_dir must be outside the repository")
    return resolved


def _validated_roster(models_by_family: Mapping[str, str]) -> dict[str, ModelSpec]:
    if set(models_by_family) != set(_FAMILIES):
        raise LiveMeasurementError(
            "live roster must name exactly math, code, and logic"
        )
    seats: dict[str, str] = {}
    for family in _FAMILIES:
        model_id = models_by_family[family]
        if not isinstance(model_id, str) or not model_id:
            raise LiveMeasurementError(
                "live roster model ids must be non-empty strings"
            )
        if model_id != model_id.strip():
            raise LiveMeasurementError(
                f"live roster {family} seat must be the exact operator-supplied "
                "model id (no surrounding whitespace)"
            )
        seats[family] = model_id
    if len(set(seats.values())) != len(_FAMILIES):
        raise LiveMeasurementError(
            "live roster requires one distinct seat per task family"
        )
    return {
        model_id: ModelSpec(model_id=model_id, specialty=family)
        for family, model_id in seats.items()
    }


def _candidate(roster: Mapping[str, ModelSpec]) -> OrchestrationGenome:
    return OrchestrationGenome(
        roster=[
            {
                "role_id": f"live-{spec.specialty}",
                "member_id": model_id,
                "kind": "model",
            }
            for model_id, spec in roster.items()
        ],
        adjudication_rule="synthesize",
    )


def _require_seeded_significance(run: Mapping[str, Any], key: str) -> None:
    result = run.get(key)
    if not isinstance(result, dict):
        raise LiveMeasurementError(f"missing {key} result")
    if result.get("method") != SIGNIFICANCE_METHOD:
        raise LiveMeasurementError(f"{key} did not use seeded paired bootstrap")
    if int(result.get("iterations") or 0) <= 0:
        raise LiveMeasurementError(f"{key} has no bootstrap samples")
    ci95 = result.get("ci95_lift")
    if not isinstance(ci95, list) or len(ci95) != 2:
        raise LiveMeasurementError(f"{key} has no auditable 95% interval")


def _validate_controls(run: Mapping[str, Any], *, per_call_cap: int) -> None:
    if run.get("measurement_mode") != "live_ollama":
        raise LiveMeasurementError(
            "runner did not disclose live_ollama measurement mode"
        )
    for field in ("arm_scores", "budget_parity", "parity_ledger"):
        rows = run.get(field)
        if not isinstance(rows, dict) or not _REQUIRED_ARMS.issubset(rows):
            raise LiveMeasurementError(f"{field} is missing a mandatory control arm")
    parity = run.get("parity_control")
    if not isinstance(parity, dict):
        raise LiveMeasurementError("missing exact budget-parity control receipt")
    if not parity.get("verified") or not parity.get("calls_per_task_match"):
        raise LiveMeasurementError("best-single exact parity was not verified")
    if parity.get("candidate_total_calls") != parity.get("control_total_calls"):
        raise LiveMeasurementError("candidate and best-single parity calls differ")
    if int(parity.get("candidate_total_calls") or 0) <= 0:
        raise LiveMeasurementError("parity control contains no calls")
    if parity.get("per_call_cap") != per_call_cap:
        raise LiveMeasurementError("parity control used a different per-call cap")
    if not parity.get("per_call_cap_shared_across_arms"):
        raise LiveMeasurementError("per-call cap is not shared across arms")
    for arm in _REQUIRED_ARMS:
        ledger = run["parity_ledger"][arm]
        if int(ledger.get("total_calls") or 0) <= 0:
            raise LiveMeasurementError(f"{arm} has no call ledger")
        if int(ledger.get("total_compute") or 0) <= 0:
            raise LiveMeasurementError(f"{arm} has no measured compute")
        if ledger.get("per_call_cap") != per_call_cap:
            raise LiveMeasurementError(f"{arm} used a different per-call cap")
    _require_seeded_significance(run, "significance")
    _require_seeded_significance(run, "significance_vs_parity_control")


def _validate_live_receipts(
    pool: LiveWorkerPool,
    taskpack: Taskpack,
    roster: Mapping[str, ModelSpec],
    *,
    per_call_cap: int,
) -> None:
    expected = {
        (model_id, task_id) for model_id in roster for task_id in taskpack.task_ids()
    }
    observed = {
        (str(row.get("model_id")), str(row.get("task_id")))
        for row in pool.call_receipts
    }
    if observed != expected or len(pool.call_receipts) != len(expected):
        raise LiveMeasurementError(
            "live receipts do not cover every roster-seat/task pair exactly once"
        )
    for row in pool.call_receipts:
        model_id = str(row.get("model_id") or "")
        provider_model_id = str(row.get("provider_model_id") or "")
        if provider_model_id != model_id:
            raise LiveMeasurementError(
                "live receipt provider model identity does not match its roster seat"
            )
        prompt_tokens = row.get("prompt_tokens")
        completion_tokens = row.get("completion_tokens")
        if type(prompt_tokens) is not int or prompt_tokens < 0:
            raise LiveMeasurementError(
                "live receipt prompt token count is not a non-negative integer"
            )
        if type(completion_tokens) is not int or completion_tokens < 0:
            raise LiveMeasurementError(
                "live receipt completion token count is not a non-negative integer"
            )
        if completion_tokens > per_call_cap:
            raise LiveMeasurementError(
                "live receipt exceeds the configured completion token cap"
            )
        cost = row.get("cost")
        if (
            type(cost) is not int
            or cost <= 0
            or cost != prompt_tokens + completion_tokens
        ):
            raise LiveMeasurementError(
                "live receipt cost does not equal its non-zero token accounting"
            )


def _digest(payload: Mapping[str, Any]) -> str:
    canonical = dict(payload)
    canonical.pop("digest_sha256", None)
    data = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_manifest(staging: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for name in sorted(_MANIFEST_OUTPUTS):
        path = staging / name
        if path.is_symlink() or not path.is_file():
            raise LiveMeasurementError(f"cannot bind missing artifact: {name}")
        manifest[name] = _file_sha256(path)
    return manifest


def _validate_artifact_manifest(staging: Path, manifest: Mapping[str, str]) -> None:
    if set(manifest) != set(_MANIFEST_OUTPUTS):
        raise LiveMeasurementError("artifact manifest does not bind every output")
    for name in sorted(_MANIFEST_OUTPUTS):
        expected = manifest[name]
        if (
            len(expected) != 64
            or expected.lower() != expected
            or _file_sha256(staging / name) != expected
        ):
            raise LiveMeasurementError(f"artifact digest mismatch: {name}")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _render_measurement_decision(control_outcome: str) -> str:
    """Render an authority-safe decision surface without runner promotion text."""
    return (
        "> **Claim boundary:** live measurement candidate only; "
        "`capability_claim=false`; `promotion_authorized=false`.\n"
        "> This packet does not authorize MAP-Elites insertion, capability "
        "promotion, production routing, or benchmark claims.\n\n"
        "## Measurement state\n\n"
        f"- control_outcome: `{control_outcome}` (evidence only)\n"
        f"- closeout_state: `{LIVE_CLOSEOUT_STATE}`\n"
        f"- claim_boundary: `{CLAIM_BOUNDARY}`\n"
        "- this artifact grants no MAP-Elites insertion or promotion authority\n"
        "- promotion requires a separate governance decision over real evidence\n"
    )


def _validate_staged_outputs(staging: Path) -> None:
    for name in sorted(_RUNNER_OUTPUTS | _LIVE_OUTPUTS):
        path = staging / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
            raise LiveMeasurementError(f"missing or empty staged output: {name}")
    for name in (
        "arena_run.json",
        "scorecard.json",
        "power_index.json",
        "live_worker_receipts.json",
        "live_measurement_receipt.json",
    ):
        json.loads((staging / name).read_text(encoding="utf-8"))


def run_live_measurement(
    *,
    models_by_family: Mapping[str, str],
    output_dir: Path,
    base_url: str = OLLAMA_LOCAL_BASE_URL,
    per_call_cap: int = 64,
    timeout: float = 180.0,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Run and atomically publish one controlled, non-capability measurement."""
    if os.environ.get(LIVE_OPT_IN_ENV) != "1":
        raise LiveMeasurementError(f"live measurement requires {LIVE_OPT_IN_ENV}=1")
    if per_call_cap <= 0 or timeout <= 0:
        raise LiveMeasurementError("per_call_cap and timeout must be positive")
    parsed_url = urlparse(base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise LiveMeasurementError("base_url must be an absolute HTTP(S) URL")

    output = _external_output_path(Path(output_dir))
    roster = _validated_roster(models_by_family)
    taskpack = Taskpack()
    pool = LiveWorkerPool(
        taskpack.public_view(),
        base_url=base_url,
        per_call_cap=per_call_cap,
        temperature=0.0,
        timeout=timeout,
        transport=transport,
    )
    runner = ArenaRunner(taskpack=taskpack, pool=pool, roster=roster)

    output.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    )
    try:
        run = runner.run(_candidate(roster), output_dir=staging)
        _validate_controls(run, per_call_cap=per_call_cap)
        _validate_live_receipts(pool, taskpack, roster, per_call_cap=per_call_cap)

        control_outcome = str(run.get("closeout_state") or "")
        if control_outcome not in CLOSEOUT_STATES:
            raise LiveMeasurementError("runner returned an unknown control outcome")
        promotion_claim = run.get("promotion_claim")
        if not isinstance(promotion_claim, dict):
            raise LiveMeasurementError("runner returned no structured control claim")
        run["promotion_claim_authority"] = {
            "authority": "evidence_only",
            "promotion_authorized": False,
        }
        run["control_outcome"] = control_outcome
        run["closeout_state"] = LIVE_CLOSEOUT_STATE
        run["capability_claim"] = False
        run["claim_boundary"] = CLAIM_BOUNDARY
        run["live_controls_verified"] = True
        run["promotion_authorized"] = False
        _write_json(staging / "arena_run.json", run)
        pool.write_receipts(staging / "live_worker_receipts.json")

        scorecard_path = staging / "scorecard.json"
        scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
        scorecard["capability_claim"] = False
        scorecard["claim_boundary"] = CLAIM_BOUNDARY
        scorecard["control_outcome"] = control_outcome
        scorecard["closeout_state"] = LIVE_CLOSEOUT_STATE
        scorecard["promotion_authorized"] = False
        _write_json(scorecard_path, scorecard)

        (staging / "decision_packet.md").write_text(
            _render_measurement_decision(control_outcome), encoding="utf-8"
        )
        artifact_sha256 = _artifact_manifest(staging)

        receipt: dict[str, Any] = {
            "schema": LIVE_MEASUREMENT_SCHEMA,
            "capability_claim": False,
            "claim_boundary": CLAIM_BOUNDARY,
            "promotion_authorized": False,
            "measurement_mode": run["measurement_mode"],
            "control_outcome": control_outcome,
            "closeout_state": run["closeout_state"],
            "candidate_genome_id": run["candidate_genome_id"],
            "task_manifest_hash": run["task_manifest_hash"],
            "scorer_hash": run["scorer_hash"],
            "roster_by_family": {
                spec.specialty: model_id for model_id, spec in roster.items()
            },
            "expected_live_pairs": len(roster) * len(taskpack.task_ids()),
            "observed_live_pairs": len(pool.call_receipts),
            "required_control_arms": sorted(_REQUIRED_ARMS),
            "parity_verified": True,
            "significance_method": SIGNIFICANCE_METHOD,
            "output_files": sorted(_RUNNER_OUTPUTS | _LIVE_OUTPUTS),
            "artifact_sha256": artifact_sha256,
        }
        receipt["digest_sha256"] = _digest(receipt)
        _write_json(staging / "live_measurement_receipt.json", receipt)

        _validate_staged_outputs(staging)
        _validate_artifact_manifest(staging, artifact_sha256)
        if output.is_symlink() or output.exists():
            raise LiveMeasurementError(
                "output_dir appeared while the measurement was running"
            )
        staging.replace(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return {"run": run, "receipt": receipt, "output_dir": str(output)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--math-model", required=True)
    parser.add_argument("--code-model", required=True)
    parser.add_argument("--logic-model", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-url", default=OLLAMA_LOCAL_BASE_URL)
    parser.add_argument("--per-call-cap", type=int, default=64)
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_live_measurement(
            models_by_family={
                "math": args.math_model,
                "code": args.code_model,
                "logic": args.logic_model,
            },
            output_dir=args.output_dir,
            base_url=args.base_url,
            per_call_cap=args.per_call_cap,
            timeout=args.timeout,
        )
    except (LiveMeasurementError, LiveDispatchError, OSError, ValueError) as exc:
        print(f"arena live measurement refused: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "capability_claim": False,
                "claim_boundary": CLAIM_BOUNDARY,
                "closeout_state": result["run"]["closeout_state"],
                "output_dir": result["output_dir"],
                "receipt_digest": result["receipt"]["digest_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CLAIM_BOUNDARY",
    "LIVE_CLOSEOUT_STATE",
    "LIVE_MEASUREMENT_SCHEMA",
    "LIVE_OPT_IN_ENV",
    "LiveMeasurementError",
    "build_parser",
    "main",
    "run_live_measurement",
]
