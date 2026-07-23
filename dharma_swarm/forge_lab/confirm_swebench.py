"""Confirm/depth tier: grade a genome (or a control patch) against REAL
SWE-bench-Verified instances via the official Docker harness.

This is the depth tier of the ratified cascade: the fast host-pytest
``explore`` tier screens breadth; this tier grades survivors against actual
SWE-bench-Verified instances, where the verdict comes only from swebench's
per-instance ``report.json`` (never self-reported). It reuses the ALREADY
tier-agnostic grade chain: ``grade_genome_explore -> production_seams.grade_task
(= runner._grade_task) -> autoloop.grade -> swebench_real.verify_prediction``,
which Docker-grades any non-``pr::`` instance automatically.

Estate invariants held structurally, not by promise:
  * shadow-only    — writes ONLY ~/.dharma/forge_lab/confirm/<run_id>/receipt.json;
                     never imports CandidateStore or the explore archive.
  * worker!=judge  — the verdict is swebench's report.json; the solver never grades.
  * tier-honest    — every row carries tier='confirm-swebench-docker'; never
                     ranked against explore rows.
  * honest failure — a missing report.json raises (infra fail) and is recorded
                     as a hard error row, never coerced to a False verdict.

Usage:
  # falsifiable honesty proof — gold must resolve True, empty False:
  python -m dharma_swarm.forge_lab.confirm_swebench --instance django__django-12209 --control
  # grade a real solver genome against the instance (confirm tier):
  python -m dharma_swarm.forge_lab.confirm_swebench --instance django__django-12209 --solver-model kimi-code
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Import the swebench adapter FIRST so its Docker-context resolution runs before
# any docker.from_env() call (swebench's SDK ignores `docker context`).
from dharma_swarm.forge_v1 import swebench_real
from dharma_swarm.forge_v1.autoloop_context import pull_context
from dharma_swarm.forge_lab.genome_spec import DEFAULT_GENOME
from dharma_swarm.forge_lab.grade_explore import (
    GradeSeams,
    TIER_CONFIRM_SWEBENCH,
    grade_genome_explore,
    production_seams,
)

CONFIRM_ROOT = Path.home() / ".dharma" / "forge_lab" / "confirm"


def _ensure_docker() -> None:
    swebench_real._ensure_docker_host()
    if not os.environ.get("DOCKER_HOST"):
        default = Path.home() / ".colima" / "default" / "docker.sock"
        if default.exists():
            os.environ["DOCKER_HOST"] = f"unix://{default}"


def _prewarm(inst: dict) -> str:
    """Pull the prebuilt amd64 instance image so the first grade is ~1min, not
    tens of minutes. Returns the image key; asserts the image is present."""
    key = swebench_real.instance_image_key(inst)
    print(f"[confirm] pre-warming image {key}", flush=True)
    subprocess.run(["docker", "pull", key], check=False, timeout=3600)
    present = subprocess.run(
        ["docker", "images", "-q", key], capture_output=True, text=True, timeout=60
    )
    if not present.stdout.strip():
        raise RuntimeError(f"image_not_present_after_pull:{key}")
    return key


def _run_id(instance_id: str, stamp: float) -> str:
    return f"confirm_{instance_id.replace('/', '_')}_{int(stamp)}"


def _write_receipt(run_id: str, payload: dict[str, Any]) -> Path:
    out_dir = CONFIRM_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "receipt.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


def _patch_metadata(run_id: str, instance_id: str, patch: str) -> dict[str, Any]:
    """Persist and fingerprint the generated patch for confirm-tier evidence."""

    patch = patch or ""
    metadata: dict[str, Any] = {
        "non_empty_patch": bool(patch.strip()),
        "patch_len": len(patch),
        "patch_sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest() if patch else None,
        "patch_path": None,
    }
    if patch.strip():
        out_dir = CONFIRM_ROOT / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_instance = instance_id.replace("/", "_").replace(":", "_")
        path = out_dir / f"{safe_instance}.candidate.patch"
        path.write_text(patch, encoding="utf-8")
        metadata["patch_path"] = str(path)
    return metadata


def _control(inst: dict, image_key: str, run_id: str) -> dict[str, Any]:
    """Grade the GOLD patch (expect resolved=True) and the EMPTY patch (expect
    False) DIRECTLY via the grade seam — never the solver. This is the
    falsifiable honesty proof for the tier: if gold does not resolve or empty
    does, the tier is not measuring what it claims."""
    seams = production_seams()
    rows: list[dict[str, Any]] = []
    for arm, patch in (("gold", inst["patch"]), ("empty", "")):
        row: dict[str, Any] = {"arm": arm, "tier": TIER_CONFIRM_SWEBENCH, "resolved": False}
        t0 = time.time()
        try:
            resolved, seconds, note = seams.grade_task(inst, patch, timeout=1800)
            row.update(resolved=bool(resolved), grade_seconds=float(seconds), note=note)
        except Exception as exc:  # infra/report failure — hard error, NOT a False verdict
            row["error"] = f"{type(exc).__name__}:{exc}"[:500]
            row["grade_seconds"] = round(time.time() - t0, 1)
        rows.append(row)
    gold = next(r for r in rows if r["arm"] == "gold")
    empty = next(r for r in rows if r["arm"] == "empty")
    discriminates = bool(gold.get("resolved")) and not bool(empty.get("resolved"))
    return {
        "schema": "forge_lab.confirm_swebench.control.v0",
        "run_id": run_id,
        "instance_id": inst["instance_id"],
        "image_key": image_key,
        "tier": TIER_CONFIRM_SWEBENCH,
        "rows": rows,
        "discriminates": discriminates,
        "verdict": "PASS" if discriminates else "FAIL",
    }


def _candidate(inst: dict, ctx: dict, image_key: str, run_id: str, solver_model: str,
               budget_tokens: int) -> dict[str, Any]:
    """Grade one real solver genome against the instance on the confirm tier."""
    genome = dict(DEFAULT_GENOME)
    genome["generator_model"] = solver_model
    base_seams = production_seams()
    generated_patches: list[str] = []

    def capture_propose_slot(*args: Any, **kwargs: Any) -> dict[str, Any]:
        rec = base_seams.propose_slot(*args, **kwargs)
        patch = str(rec.get("patch") or "")
        if patch.strip():
            generated_patches.append(patch)
        return rec

    seams = GradeSeams(
        slot_for_id=base_seams.slot_for_id,
        propose_slot=capture_propose_slot,
        self_moa_arm=base_seams.self_moa_arm,
        verify_chain_arm=base_seams.verify_chain_arm,
        mixed_moa_arm=base_seams.mixed_moa_arm,
        grade_task=base_seams.grade_task,
        budget_factory=base_seams.budget_factory,
    )
    outcome = grade_genome_explore(
        genome,
        {inst["instance_id"]: (inst, ctx)},
        seams=seams,
        budget_cap_tokens=budget_tokens,
        budget_cap_usd=8.0,
        propose_timeout_s=240,
        grade_timeout_s=1800,
        soft_token_cap=True,
        tier=TIER_CONFIRM_SWEBENCH,
    )
    patch = generated_patches[-1] if generated_patches else ""
    patch_meta = _patch_metadata(run_id, inst["instance_id"], patch)
    per_task = [dict(row, **patch_meta) for row in outcome.per_task]
    return {
        "schema": "forge_lab.confirm_swebench.candidate.v0",
        "run_id": run_id,
        "instance_id": inst["instance_id"],
        "image_key": image_key,
        "tier": outcome.tier,
        "solver_model": solver_model,
        **patch_meta,
        "pass_rate": outcome.pass_rate,
        "tokens_used": outcome.tokens_used,
        "per_task": per_task,
        "budget": outcome.budget,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SWE-bench confirm/depth tier grader")
    ap.add_argument("--instance", required=True, help="SWE-bench-Verified instance_id")
    ap.add_argument("--control", action="store_true",
                    help="grade gold+empty (honesty proof) instead of a solver genome")
    ap.add_argument("--solver-model", default="kimi-code",
                    help="slot-resolvable model id for the candidate path")
    ap.add_argument("--budget-tokens", type=int, default=400_000)
    args = ap.parse_args(argv)

    _ensure_docker()
    stamp = time.time()
    run_id = _run_id(args.instance, stamp)

    inst, ctx = pull_context(args.instance)
    image_key = _prewarm(inst)

    if args.control:
        payload = _control(inst, image_key, run_id)
    else:
        payload = _candidate(inst, ctx, image_key, run_id, args.solver_model, args.budget_tokens)

    path = _write_receipt(run_id, payload)
    print(json.dumps({k: payload[k] for k in payload if k not in ("per_task", "rows")}, indent=2), flush=True)
    if "rows" in payload:
        for r in payload["rows"]:
            print(f"  {r['arm']}: resolved={r.get('resolved')} secs={r.get('grade_seconds')} "
                  f"err={r.get('error')}", flush=True)
    print(f"[confirm] receipt: {path}", flush=True)
    # Exit code: control -> 0 iff discriminates; candidate -> always 0 (a row is a row).
    if args.control:
        return 0 if payload.get("discriminates") else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
