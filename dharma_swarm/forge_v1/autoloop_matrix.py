"""Matrix and multi-instance runners for Forge autoloop."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor

from dharma_swarm.forge_v1.autoloop import (
    CHAMPION,
    RUN_ROOT,
    SWARM,
    _champion_best_of_n,
    _persist,
    _safe,
    _swarm_arm,
    grade,
    propose,
    pull_context,
    spec_for,
)


def run_multi(
    instance_ids: list[str],
    *,
    champion: dict = CHAMPION,
    swarm_specs: list[dict] = SWARM,
    best_of_n: int = 3,
    budget: int = 120_000,
    grade_timeout: int = 1800,
    label: str = "multi",
) -> dict:
    """Nonstop multi-instance lift engine: for each instance run champion
    best-of-N vs the decorrelated swarm (one round each), Docker-grade applying
    patches, and aggregate the real benchmark numbers across instances:
        champion_pass_rate, swarm_pass_rate, swarm_lift = swarm - champion.
    The aggregate is rewritten after every instance, so a kill mid-run still
    leaves a valid partial scoreboard (resumable by re-running remaining ids)."""
    out = RUN_ROOT / f"multi_{label}_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=True)
    agg = {
        "kind": "forge_v1_autoloop_multi",
        "champion_model": champion["model"],
        "swarm_models": [s["model"] for s in swarm_specs],
        "best_of_n": best_of_n,
        "budget_per_arm": budget,
        "instances_requested": list(instance_ids),
        "per_instance": [],
    }
    for iid in instance_ids:
        print(f"\n{'#'*64}\n[multi] instance {iid}", flush=True)
        try:
            inst, ctx = pull_context(iid)
        except Exception as e:
            print(f"[multi] {iid} context pull FAILED: {type(e).__name__}: {e}", flush=True)
            agg["per_instance"].append({"instance": iid, "error": f"context: {e}"})
            (out / "aggregate.json").write_text(json.dumps(agg, indent=2))
            continue
        champ = _champion_best_of_n(inst, ctx, out, champion=champion, n=best_of_n,
                                    budget=budget, grade_timeout=grade_timeout, round_tag=_safe(iid))
        swarm = _swarm_arm(inst, ctx, out, swarm_specs=swarm_specs, budget=budget,
                           grade_timeout=grade_timeout, round_tag=_safe(iid))
        agg["per_instance"].append({"instance": iid, "champion": champ, "swarm": swarm})
        done = [r for r in agg["per_instance"] if "error" not in r]
        n = len(done)
        cp = sum(1 for r in done if r["champion"]["passed"])
        sp = sum(1 for r in done if r["swarm"]["passed"])
        agg["n_graded_instances"] = n
        agg["champion_pass_rate"] = cp / n if n else 0.0
        agg["swarm_pass_rate"] = sp / n if n else 0.0
        agg["swarm_lift"] = agg["swarm_pass_rate"] - agg["champion_pass_rate"]
        (out / "aggregate.json").write_text(json.dumps(agg, indent=2))
        print(f"[multi] {iid}: champ_passed={champ['passed']} swarm_passed={swarm['passed']} "
              f"| running champ={agg['champion_pass_rate']:.3f} swarm={agg['swarm_pass_rate']:.3f} "
              f"lift={agg['swarm_lift']:+.3f}", flush=True)
    print(f"\n[multi] DONE -> {out}/aggregate.json", flush=True)
    print(f"[multi] champion_pass_rate={agg.get('champion_pass_rate')} "
          f"swarm_pass_rate={agg.get('swarm_pass_rate')} swarm_lift={agg.get('swarm_lift')}", flush=True)
    return agg


def _matrix_aggregate(per: dict, instances_done: list[str], model_ids: list[str]) -> dict:
    """From the {(instance,model)->resolved} cells, compute per-model pass rates,
    the swarm (union) pass rate, the champion (best single model) pass rate, and
    lift = swarm - champion. Lift>0 means the diverse swarm solves instances no
    single model does — the honest Transcendence signal."""
    n = len(instances_done)
    per_model = {}
    for m in model_ids:
        solved = sum(1 for iid in instances_done if per.get((iid, m)))
        per_model[m] = (solved / n) if n else 0.0
    champion_model = max(per_model, key=per_model.get) if per_model else None
    champion_rate = per_model.get(champion_model, 0.0)
    swarm_solved = sum(1 for iid in instances_done if any(per.get((iid, m)) for m in model_ids))
    swarm_rate = (swarm_solved / n) if n else 0.0
    return {
        "n_instances": n,
        "per_model_pass_rate": per_model,
        "champion_model": champion_model,
        "champion_pass_rate": champion_rate,
        "swarm_pass_rate": swarm_rate,
        "swarm_lift": swarm_rate - champion_rate,
    }


def run_matrix(
    instance_ids: list[str],
    model_ids: list[str],
    *,
    grade_timeout: int = 1800,
    label: str = "matrix",
) -> dict:
    """The 'throw the WHOLE swarm at it' experiment: grade EVERY model on EVERY
    instance (one shot each), building a resolution matrix. Reveals exactly which
    decorrelated model solves which instance, and whether the swarm-as-union beats
    the best single model (lift). Resumable: matrix.json is rewritten after each
    cell, so a kill leaves a valid partial."""
    out = RUN_ROOT / f"matrix_{label}_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=True)
    specs = [spec_for(m) for m in model_ids]
    matrix = {
        "kind": "forge_v1_autoloop_matrix",
        "models": model_ids,
        "instances_requested": list(instance_ids),
        "cells": [],
    }
    per: dict = {}
    instances_done: list[str] = []
    for iid in instance_ids:
        print(f"\n{'#'*64}\n[matrix] instance {iid}", flush=True)
        try:
            inst, ctx = pull_context(iid)
        except Exception as e:
            print(f"[matrix] {iid} context pull FAILED: {type(e).__name__}: {e}", flush=True)
            continue
        # PROPOSE all models in parallel (independent provider APIs) so the slow
        # coding endpoints overlap the fast ones; GRADE serially (one Docker ctx).
        with ThreadPoolExecutor(max_workers=max(1, len(specs))) as ex:
            proposals = list(ex.map(lambda s: (s, *propose(inst, ctx, s)), specs))
        for spec, prop, rec in proposals:
            m = spec["model"]
            _persist(out, prop, rec, tag=f"{_safe(iid)}_{_safe(m)}")
            resolved, gsec, gerr = False, 0.0, None
            if prop.patch.strip():
                resolved, gsec, gerr = grade(inst, prop.patch, timeout=grade_timeout)
            per[(iid, m)] = resolved
            matrix["cells"].append({
                "instance": iid, "model": m,
                "applies": bool(prop.patch.strip()), "resolved": resolved,
                "propose_error": prop.error, "grade_error": gerr,
                "tokens": prop.tokens, "stop_reason": prop.stop_reason,
                "rounds": getattr(prop, "n_edit_blocks", None),
                "propose_seconds": rec["seconds"], "grade_seconds": gsec,
            })
            print(f"   [matrix] {iid} | {m:24} applies={bool(prop.patch.strip())} "
                  f"resolved={resolved} ({rec['seconds']}s+{gsec}s)"
                  f"{' ERR:'+(prop.error or gerr or '')[:50] if (prop.error or gerr) else ''}", flush=True)
            matrix["aggregate"] = _matrix_aggregate(per, instances_done, model_ids)
            (out / "matrix.json").write_text(json.dumps(matrix, indent=2))
        instances_done.append(iid)
        matrix["aggregate"] = _matrix_aggregate(per, instances_done, model_ids)
        (out / "matrix.json").write_text(json.dumps(matrix, indent=2))
        agg = matrix["aggregate"]
        print(f"[matrix] after {iid}: champion={agg['champion_model']} "
              f"champ_rate={agg['champion_pass_rate']:.3f} swarm_rate={agg['swarm_pass_rate']:.3f} "
              f"lift={agg['swarm_lift']:+.3f}", flush=True)
    print(f"\n[matrix] DONE -> {out}/matrix.json", flush=True)
    agg = matrix.get("aggregate", {})
    print(f"[matrix] per_model={agg.get('per_model_pass_rate')}", flush=True)
    print(f"[matrix] champion_pass_rate={agg.get('champion_pass_rate')} "
          f"swarm_pass_rate={agg.get('swarm_pass_rate')} swarm_lift={agg.get('swarm_lift')}", flush=True)
    return matrix
