"""Forge v1 — the FIRST real end-to-end swarm-vs-best-of-N measurement on a
REAL SWE-bench-Verified instance, graded by the OFFICIAL swebench Docker harness.

This is the L3 flip taken all the way: live frontier models (Gemini + GLM),
real repo@commit tasks, real hidden-test grading. Nothing is faked. An honest
negative (swarm did not beat best-of-N) is a valid, ship-worthy result.

What it measures
----------------
For each instance, two arms at EQUAL token budget:

  CHAMPION : best-of-N on ONE Gemini Flash model. Sample up to N patches
             under a TokenBroker cap; grade EACH with verify_prediction (Docker);
             keep the first that resolves.
  SWARM    : two DECORRELATED real model families (Gemini Flash + GLM)
             each propose one patch; grade each with verify_prediction; keep the
             first that resolves. Same TokenBroker cap as champion (equal budget).

  swarm_lift = pass_rate(swarm) - pass_rate(champion) over the instances.

Why a swebench-aware best-of-N (not harness.best_of_n)
------------------------------------------------------
The forge_v1 inline `verify()` runs an inline gold test in a temp dir. Real
SWE-bench tasks are repo@commit + a HIDDEN FAIL_TO_PASS/PASS_TO_PASS suite that
only exists inside the instance's Docker image. So we grade with
`swebench_real.verify_prediction` (the official Docker harness) instead. The
model is given the problem statement (+ the real target-file context pulled from
the instance image — the same context an agent grepping the repo would find, NOT
the gold patch) and must emit a unified diff against the repo.

Run (needs the swebench venv + Docker up; SLOW — ~11 min/instance under qemu):

    PYTHONPATH=/Users/dhyana/ds_forge_v1_scoreboard \
      /Users/dhyana/dharma_swarm/.venv/bin/python \
      -m dharma_swarm.forge_v1.run_real --instances django__django-12209 -n 3

Artifacts (full result JSON) go to ~/.dharma/forge_v1/real_run_<ts>.json — never
the repo.
"""
# ruff: noqa: F401  -- re-export seam consumed by tests/test_forge_v2.py: imported names ARE the public surface
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

# When run as `python dharma_swarm/forge_v1/run_real.py`, sys.path[0] is THIS
# dir, and the sibling `swebench.py` (offline fixtures) shadows the real swebench
# PyPI library. Drop the script dir only for that direct-script invocation;
# normal imports must not mutate process-wide import resolution.
_here = Path(__file__).resolve().parent
if __name__ == "__main__" and sys.path and Path(sys.path[0] or ".").resolve() == _here:
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != _here]

from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402
from dharma_swarm.forge_v1.harness import TokenBroker  # noqa: E402
from dharma_swarm.forge_v1.providers import LiveModel  # noqa: E402
from dharma_swarm.forge_v1.swebench_real import (  # noqa: E402
    instance_image_key,
    verified_instances,
)
from dharma_swarm.forge_v1.run_real_arms import (  # noqa: E402
    ArmRun,
    GradedSample,
    champion_best_of_n,
    swarm_arm,
)
from dharma_swarm.forge_v1.run_real_patch import (  # noqa: E402
    _read_files_from_image,
    _target_paths_from_gold,
    apply_edit_blocks,
    build_repair_prompt,
    compute_unified_diff,
    parse_edit_blocks,
    parse_full_files,
)
from dharma_swarm.forge_v1.run_real_proposer import (  # noqa: E402
    DIFF_MAX_TOKENS,
    MODEL_CALL_TIMEOUT_S,
    Proposal,
    SweBenchProposer,
    _rate_limit_wait_s,
)
from dharma_swarm.model_defaults import default_for_provider  # noqa: E402
from dharma_swarm.models import ProviderType  # noqa: E402

# Default tiny/fast pure-logic instances (no network tests). Picked by smallest
# (FAIL_TO_PASS, PASS_TO_PASS, patch size) over sympy/django in Verified.
DEFAULT_INSTANCES = ["django__django-12209"]

CHAMPION_MODEL = default_for_provider(ProviderType.GOOGLE_AI)
# Second DECORRELATED family for the swarm (Ollama-Cloud GLM, chinese_cluster) —
# a genuinely different model family from Gemini (deepmind), not a temperature
# stand-in. Verified live via dkeys + a real PONG call before this run.
SWARM_MODELS = [CHAMPION_MODEL, default_for_provider(ProviderType.OLLAMA)]


# --------------------------------------------------------------------------- #
# Pulling REAL target-file context out of the instance Docker image
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def run(
    instance_ids: list[str],
    *,
    n: int,
    budget: int,
    grade_timeout: int,
    swarm_second_model: str,
    single_family_standin: bool,
) -> dict:
    results = []
    for iid in instance_ids:
        print(f"\n{'=' * 72}\n[run_real] instance: {iid}", flush=True)
        instance = verified_instances(instance_ids=[iid])[0]
        image = instance_image_key(instance)
        print(f"[run_real] repo={instance['repo']} base={instance['base_commit'][:12]} image={image}", flush=True)

        # Real working-tree context (paths from gold headers, contents from image).
        paths = _target_paths_from_gold(instance)
        print(f"[run_real] pulling file context for {paths} from image (one-time pull may be slow)...", flush=True)
        ctx = _read_files_from_image(instance, paths)
        print(f"[run_real] got context for {list(ctx)} ({sum(len(v) for v in ctx.values())} chars)", flush=True)

        # CHAMPION: best-of-N on gemini.
        champ_proposer = SweBenchProposer(CHAMPION_MODEL)
        champ_broker = TokenBroker(cap=budget)
        print(f"[run_real] CHAMPION best-of-{n} on {CHAMPION_MODEL} (budget {budget} tok)...", flush=True)
        champ = champion_best_of_n(
            instance, ctx, champ_proposer, champ_broker, n=n, grade_timeout=grade_timeout
        )
        for s in champ.samples:
            print(f"    champ sample: model={s.model} tok={s.tokens} patch_len={s.patch_len} "
                  f"resolved={s.resolved} ({s.grade_seconds:.0f}s){' ERR:'+s.error if s.error else ''}", flush=True)
        print(f"[run_real] CHAMPION passed={champ.passed} tokens={champ.tokens_spent} wall={champ.wall_seconds:.0f}s", flush=True)

        # SWARM: gemini + second family, equal budget.
        if single_family_standin:
            swarm_proposers = [
                SweBenchProposer(SWARM_MODELS[0], temperature=0.2),
                SweBenchProposer(SWARM_MODELS[0], temperature=0.9),
            ]
            swarm_note = "single-family stand-in: gemini@0.2 + gemini@0.9 (NOT a 2nd family)"
        else:
            swarm_proposers = [
                SweBenchProposer(SWARM_MODELS[0]),
                SweBenchProposer(swarm_second_model),
            ]
            swarm_note = f"decorrelated 2-family: {SWARM_MODELS[0]} + {swarm_second_model}"
        swarm_broker = TokenBroker(cap=budget)
        print(f"[run_real] SWARM ({swarm_note}) budget {budget} tok...", flush=True)
        swarm = swarm_arm(instance, ctx, swarm_proposers, swarm_broker, grade_timeout=grade_timeout)
        for s in swarm.samples:
            print(f"    swarm sample: model={s.model} tok={s.tokens} patch_len={s.patch_len} "
                  f"resolved={s.resolved} ({s.grade_seconds:.0f}s){' ERR:'+s.error if s.error else ''}", flush=True)
        print(f"[run_real] SWARM passed={swarm.passed} tokens={swarm.tokens_spent} wall={swarm.wall_seconds:.0f}s", flush=True)
        swarm.note = swarm_note

        results.append(
            {
                "instance_id": iid,
                "repo": instance["repo"],
                "image": image,
                "file_context_paths": list(ctx),
                "champion": asdict(champ),
                "swarm": asdict(swarm),
            }
        )

    n_inst = len(results)
    champ_pass = sum(1 for r in results if r["champion"]["passed"])
    swarm_pass = sum(1 for r in results if r["swarm"]["passed"])
    champ_rate = champ_pass / n_inst if n_inst else 0.0
    swarm_rate = swarm_pass / n_inst if n_inst else 0.0
    total_tokens = sum(
        r["champion"]["tokens_spent"] + r["swarm"]["tokens_spent"] for r in results
    )
    return {
        "kind": "forge_v1_real_run",
        "timestamp": int(time.time()),
        "config": {
            "instances": instance_ids,
            "best_of_n": n,
            "budget_per_arm_tokens": budget,
            "grade_timeout_s": grade_timeout,
            "champion_model": CHAMPION_MODEL,
            "swarm_models": [SWARM_MODELS[0], swarm_second_model] if not single_family_standin
            else [SWARM_MODELS[0] + "@0.2", SWARM_MODELS[0] + "@0.9"],
            "swarm_is_single_family_standin": single_family_standin,
        },
        "n_instances": n_inst,
        "champion_pass_rate": champ_rate,
        "swarm_pass_rate": swarm_rate,
        "swarm_lift": swarm_rate - champ_rate,
        "total_live_tokens": total_tokens,
        "per_instance": results,
    }


def _gemini_price_usd(tokens: int) -> float:
    """Rough blended Gemini Flash cost. We only
    track a total token count, so use a blended ~$1/M as a coarse upper bound."""
    return tokens / 1_000_000 * 1.0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Forge v1 real swarm-vs-best-of-N run")
    ap.add_argument("--instances", nargs="*", default=DEFAULT_INSTANCES,
                    help="SWE-bench-Verified instance ids")
    ap.add_argument("-n", "--best-of-n", type=int, default=3, help="champion best-of-N (<=3 for a proof)")
    ap.add_argument("--budget", type=int, default=20000, help="token cap PER ARM (equal budget)")
    ap.add_argument("--grade-timeout", type=int, default=1800, help="swebench per-eval timeout (s)")
    ap.add_argument("--swarm-second-model", default=default_for_provider(ProviderType.OLLAMA),
                    help="second swarm family (must be a live key)")
    ap.add_argument("--single-family-standin", action="store_true",
                    help="if no 2nd live family: use gemini@2 temperatures (honest stand-in)")
    args = ap.parse_args(argv)

    t0 = time.time()
    result = run(
        args.instances,
        n=args.best_of_n,
        budget=args.budget,
        grade_timeout=args.grade_timeout,
        swarm_second_model=args.swarm_second_model,
        single_family_standin=args.single_family_standin,
    )
    wall = time.time() - t0
    result["total_wall_seconds"] = wall
    result["approx_usd"] = _gemini_price_usd(result["total_live_tokens"])

    out_dir = dharma_state_dir() / "forge_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"real_run_{result['timestamp']}.json"
    out_path.write_text(json.dumps(result, indent=2))

    print("\n" + "=" * 72)
    print("[run_real] FINAL REPORT")
    print(f"  instances           : {result['config']['instances']}")
    print(f"  best_of_n           : {result['config']['best_of_n']}")
    print(f"  budget/arm (tokens) : {result['config']['budget_per_arm_tokens']}")
    print(f"  swarm models        : {result['config']['swarm_models']} "
          f"(single-family stand-in: {result['config']['swarm_is_single_family_standin']})")
    for r in result["per_instance"]:
        print(f"  - {r['instance_id']}: champion_resolved={r['champion']['passed']} "
              f"swarm_resolved={r['swarm']['passed']} "
              f"(champ {r['champion']['tokens_spent']}tok/{r['champion']['wall_seconds']:.0f}s, "
              f"swarm {r['swarm']['tokens_spent']}tok/{r['swarm']['wall_seconds']:.0f}s)")
    print(f"  champion_pass_rate  : {result['champion_pass_rate']:.3f}")
    print(f"  swarm_pass_rate     : {result['swarm_pass_rate']:.3f}")
    print(f"  >>> swarm_lift      : {result['swarm_lift']:+.3f}")
    print(f"  total live tokens   : {result['total_live_tokens']}  (~${result['approx_usd']:.4f})")
    print(f"  total wall-clock    : {wall:.0f}s ({wall/60:.1f} min)")
    print(f"  result JSON         : {out_path}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
