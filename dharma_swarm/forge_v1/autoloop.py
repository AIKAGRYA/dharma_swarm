"""Forge v1 — autoresearch loop (Karpathy-style closed hill-climb).

Goal: drive the REAL SWE-bench-Verified swarm-vs-best-of-N number from 0 toward
a positive value, nonstop, with a real verifier in the loop.

Two coupled loops:
  INNER (fast, offline, free):  propose -> capture RAW output -> parse -> apply.
      Every attempt is persisted with the model's full raw text + stop_reason, so
      a non-applying proposal is never opaque (truncation vs format-miss vs empty
      are distinguished). This is where prompt/parser/roster get iterated.
  OUTER (slow, real, ~11 min/grade under qemu): Docker-grade ONLY the patches
      that actually apply, via the official swebench harness. A patch that does
      not apply is never sent to Docker.

Why this exists: the 2026-06-28/29 runs scored 0/0 not because the models can't
code, but because (a) the champion/2nd models (kimi-for-coding, glm) TIMED OUT or
TRUNCATED on the 78KB full-file context, and (b) the raw output was never saved,
so the failure was unreadable. Probed 2026-06-29: Max-plan (claude-opus-4.8) and
codex (gpt-5.5) models CANNOT be called nested inside a Claude Code session
(they time out); gemini-2.5-flash / glm-5.2 / kimi-for-coding all parse+apply on
small inputs. gemini-2.5-flash has a ~1M context and is the champion that can eat
the whole file.

Artifacts: ~/.dharma/forge_v1/autoloop/<run>/ (raw text, patches, scoreboard).
Never the repo.

CLI:
  python -m dharma_swarm.forge_v1.autoloop capture --instance django__django-12209
  python -m dharma_swarm.forge_v1.autoloop grade   --patch <file> --instance ...
  python -m dharma_swarm.forge_v1.autoloop loop     --instance django__django-12209 --max-rounds 6
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
if str(WT) not in sys.path:
    sys.path.insert(0, str(WT))

# The instance Docker images live on the forge-swebench colima profile, not the
# default context. Make every docker call (context pull + grade) target it.
os.environ.setdefault("DOCKER_CONTEXT", os.environ.get("FORGE_DOCKER_CONTEXT", "colima-forge-swebench"))

from dharma_swarm.api_keys import bootstrap_runtime_env  # noqa: E402

bootstrap_runtime_env()

from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402
from dharma_swarm.forge_v1.harness import TokenBroker, BudgetExhausted  # noqa: E402
from dharma_swarm.forge_v1.run_real import (  # noqa: E402
    DIFF_MAX_TOKENS,
    SweBenchProposer,
    _read_files_from_image,
    _target_paths_from_gold,
)
from dharma_swarm.forge_v1.swebench_real import verified_instances, verify_prediction  # noqa: E402

RUN_ROOT = dharma_state_dir() / "forge_v1" / "autoloop"
DEFAULT_INSTANCE = "django__django-12209"

# Live + callable roster (probed 2026-06-29). gemini eats the full file (1M ctx)
# and emits a clean SEARCH/REPLACE block. glm-5.2 is a REASONING model that thinks
# in the output channel, so it needs a large output budget or it truncates before
# emitting the block (observed: 8192 tokens -> stop_reason=length, 0 blocks).
# kimi-for-coding REQUIRES temperature=1 and TIMES OUT on the 78KB full file, so it
# is not in the default swarm (kept as an opt-in for windowed-context experiments).
CHAMPION = {"model": "gemini-2.5-flash", "temperature": 0.2, "max_tokens": 8192, "timeout_s": 150, "continue_rounds": 2, "family": "deepmind"}
# The WHOLE callable, decorrelated swarm. Each member's wall is recoded around:
#  - gemini: fine (1M ctx, clean format).
#  - glm-5.2: reasoning model — narrates the fix then ends the turn without the
#    block; the finish-the-block continuation (continue_rounds) pushes it to emit.
#  - moonshotai/kimi-k2.6 via NVIDIA NIM: decorrelated moonshot family, avoids the
#    kimi-for-coding endpoint that times out on the 78KB file.
SWARM = [
    {"model": "gemini-2.5-flash", "temperature": 0.2, "max_tokens": 8192, "timeout_s": 150, "continue_rounds": 2, "family": "deepmind"},
    {"model": "glm-5.2", "temperature": 0.2, "max_tokens": 16000, "timeout_s": 240, "continue_rounds": 3, "family": "zai"},
    {"model": "moonshotai/kimi-k2.6", "temperature": 0.3, "max_tokens": 8192, "timeout_s": 240, "continue_rounds": 3, "family": "moonshot-nvidia"},
]


def _safe(name: str) -> str:
    return name.replace("/", "_").replace(":", "_")


def spec_for(model_id: str, temperature: float | None = None) -> dict:
    """Sensible per-model defaults (output budget, timeout, continuation rounds)
    encoding each family's known wall. Used by the CLI to build champion/swarm
    rosters from bare model ids."""
    s = {"model": model_id, "temperature": 0.2, "max_tokens": 8192, "timeout_s": 600, "continue_rounds": 3}
    if model_id == "gemini-2.5-flash":
        s.update(max_tokens=8192, timeout_s=300, continue_rounds=2)
    elif model_id.startswith("glm"):
        s.update(max_tokens=16000, timeout_s=600, continue_rounds=3)   # reasoning + flaky latency: give it room
    elif model_id == "moonshotai/kimi-k2.6":
        s.update(max_tokens=8192, timeout_s=480, continue_rounds=3)
    elif model_id == "kimi-for-coding":
        # The PAID Moonshot coding endpoint (kimi-for-coding -> k2.7). Powerful
        # coding specialist, but its endpoint HANGS on the full 78KB file (times
        # out at 600s, 0 tokens — input-size wall, not funds). So feed it a
        # windowed slice located by keyword density. Endpoint forces temp=1.
        # Endpoint hangs above ~13KB prompt (works 35-58s below) — built for
        # interactive Claude-Code use, not batch. Small target files (most of
        # SWE-bench) pass through whole; only oversized files (django base.py 78KB)
        # get an ~11KB keyword window (proven to respond). Fail fast on the hang.
        s.update(temperature=1.0, max_tokens=8192, timeout_s=150, continue_rounds=2,
                 window_chars=11000)
    if temperature is not None:
        s["temperature"] = temperature
    return s


_COMMON_WORDS = {
    "this", "that", "with", "from", "when", "then", "should", "would", "could",
    "change", "behaviour", "behavior", "description", "model", "models", "field",
    "value", "values", "example", "following", "instance", "being", "saved",
    "have", "does", "note", "case", "using", "code", "python", "https", "ticket",
    "issue", "your", "will", "into", "what", "which", "there", "where", "return",
    "result", "output", "expected", "actual", "above", "below", "method", "class",
    "function", "error", "raise", "raises", "test", "tests", "object", "objects",
}


def _keywords(problem: str) -> list[str]:
    """Distinctive identifiers/symbols from the bug report — used to locate the
    relevant region of a too-large file for small-context models."""
    kws = set()
    for m in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", problem or ""):
        if len(m) >= 4 and m.lower() not in _COMMON_WORDS:
            kws.add(m)
    return list(kws)


def window_context(file_context: dict[str, str], problem: str, *, max_chars: int = 24000,
                   radius_lines: int = 160) -> dict[str, str]:
    """Return a reduced view of each file for endpoints that hang on huge input:
    the contiguous line window (≈2*radius_lines) with the highest density of
    bug-report keywords. The window is a VERBATIM substring of the file, so a
    SEARCH block copied from it still matches the full file at apply time. Files
    already under max_chars pass through unchanged."""
    kws = _keywords(problem)
    out: dict[str, str] = {}
    for path, content in file_context.items():
        if len(content) <= max_chars or not kws:
            out[path] = content
            continue
        lines = content.splitlines(keepends=True)
        score = [sum(1 for k in kws if k in ln) for ln in lines]
        win = min(len(lines), 2 * radius_lines)
        cur = sum(score[:win])
        best, best_lo = cur, 0
        for lo in range(1, len(lines) - win + 1):
            cur += score[lo + win - 1] - score[lo - 1]
            if cur > best:
                best, best_lo = cur, lo
        windowed = "".join(lines[best_lo:best_lo + win])
        out[path] = windowed[:max_chars]
    return out


def pull_context(instance_id: str):
    inst = verified_instances(instance_ids=[instance_id])[0]
    paths = _target_paths_from_gold(inst)
    ctx = _read_files_from_image(inst, paths)
    return inst, ctx


def propose(inst: dict, ctx: dict, spec: dict):
    """One proposal. Returns (Proposal, record-dict). NEVER raises — a provider
    construction/routing failure is captured as an errored Proposal so one bad
    model can't kill a multi-model run (matters for parallel proposals)."""
    from dharma_swarm.forge_v1.run_real import Proposal
    t0 = time.time()
    # Small-context endpoints (kimi-for-coding hangs on the 78KB file) get a
    # windowed view located by bug-report keyword density; edits still apply
    # against the full file. window_chars=0/None -> full file.
    window_chars = spec.get("window_chars")
    prompt_ctx = None
    if window_chars:
        prompt_ctx = window_context(ctx, inst.get("problem_statement", ""), max_chars=window_chars)
    try:
        proposer = SweBenchProposer(
            spec["model"],
            temperature=spec.get("temperature", 0.2),
            max_tokens=spec.get("max_tokens", DIFF_MAX_TOKENS),
            timeout_s=spec.get("timeout_s"),
            continue_rounds=spec.get("continue_rounds", 3),
        )
        prop = proposer.propose(inst, ctx, prompt_context=prompt_ctx)
    except Exception as e:
        prop = Proposal(model=spec["model"], patch="", tokens=0,
                        error=f"construct: {type(e).__name__}: {e}")
    rec = {
        "model": prop.model,
        "temperature": spec.get("temperature", 0.2),
        "max_tokens": spec.get("max_tokens", DIFF_MAX_TOKENS),
        "tokens": prop.tokens,
        "stop_reason": prop.stop_reason,
        "n_edit_blocks": prop.n_edit_blocks,
        "patch_len": len(prop.patch),
        "applies": bool(prop.patch.strip()),
        "error": prop.error,
        "prompt_chars": prop.prompt_chars,
        "raw_len": len(prop.raw_text or ""),
        "seconds": round(time.time() - t0, 1),
    }
    return prop, rec


def grade(inst: dict, patch: str, *, timeout: int) -> tuple[bool, float, str | None]:
    """Docker-grade ONE patch via the official swebench harness. Never fakes."""
    t0 = time.time()
    try:
        resolved = verify_prediction(inst, patch, timeout=timeout)
        return bool(resolved), round(time.time() - t0, 1), None
    except Exception as e:
        return False, round(time.time() - t0, 1), f"{type(e).__name__}: {e}"


def _persist(out: Path, prop, rec: dict, tag: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{tag}_{_safe(prop.model)}"
    (out / f"{stem}_raw.txt").write_text(prop.raw_text or "")
    if prop.patch.strip():
        (out / f"{stem}.patch").write_text(prop.patch)
    (out / f"{stem}.json").write_text(json.dumps({**rec, "patch": prop.patch}, indent=2))


# --------------------------------------------------------------------------- #
# capture (inner loop only — no Docker)
# --------------------------------------------------------------------------- #
def run_capture(instance_id: str, specs: list[dict], label: str = "probe") -> tuple[Path, list[dict]]:
    out = RUN_ROOT / f"capture_{label}_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=True)
    inst, ctx = pull_context(instance_id)
    ctx_chars = sum(len(v) for v in ctx.values())
    print(f"[capture] {instance_id} files={list(ctx)} chars={ctx_chars}", flush=True)
    records = []
    for i, spec in enumerate(specs):
        print(f"[capture] {spec['model']} T={spec.get('temperature')} maxtok={spec.get('max_tokens')} ...", flush=True)
        prop, rec = propose(inst, ctx, spec)
        _persist(out, prop, rec, tag=f"{i:02d}")
        records.append(rec)
        print("   " + json.dumps(rec), flush=True)
    (out / "capture_summary.json").write_text(
        json.dumps({"instance": instance_id, "context_chars": ctx_chars, "records": records}, indent=2)
    )
    print(f"[capture] -> {out}", flush=True)
    return out, records


# --------------------------------------------------------------------------- #
# the loop (inner + outer): champion best-of-N vs decorrelated swarm, graded
# --------------------------------------------------------------------------- #
def _champion_best_of_n(inst, ctx, out, *, champion, n, budget, grade_timeout, round_tag):
    """Sample the champion up to n times (temperature ladder), grade each applying
    patch, keep the first that resolves. Equal-budget via TokenBroker."""
    broker = TokenBroker(cap=budget)
    samples = []
    passed = False
    for i in range(n):
        spec = dict(champion)
        # Temperature ladder gives best-of-N genuine diversity instead of N
        # identical greedy samples.
        spec["temperature"] = round(min(1.0, champion.get("temperature", 0.2) + 0.2 * i), 2)
        prop, rec = propose(inst, ctx, spec)
        _persist(out, prop, rec, tag=f"{round_tag}_champ{i}")
        try:
            broker.charge(prop.tokens)
        except BudgetExhausted as e:
            rec["graded"] = False
            rec["budget_exhausted"] = str(e)
            samples.append(rec)
            break
        if prop.patch.strip():
            resolved, secs, gerr = grade(inst, prop.patch, timeout=grade_timeout)
            rec["graded"] = True
            rec["resolved"] = resolved
            rec["grade_seconds"] = secs
            rec["grade_error"] = gerr
            print(f"   champ[{i}] {spec['model']}@T{spec['temperature']} patch_len={rec['patch_len']} "
                  f"-> resolved={resolved} ({secs}s){' ERR:'+gerr if gerr else ''}", flush=True)
            samples.append(rec)
            if resolved:
                passed = True
                break
        else:
            rec["graded"] = False
            print(f"   champ[{i}] {spec['model']}@T{spec['temperature']} NO PATCH: {rec['error']}", flush=True)
            samples.append(rec)
    return {"arm": "champion_best_of_n", "passed": passed, "tokens": broker.spent, "samples": samples}


def _swarm_arm(inst, ctx, out, *, swarm_specs, budget, grade_timeout, round_tag):
    """Each decorrelated model proposes once; grade each applying patch; keep the
    first that resolves. Same budget as champion."""
    broker = TokenBroker(cap=budget)
    samples = []
    passed = False
    for i, spec in enumerate(swarm_specs):
        prop, rec = propose(inst, ctx, spec)
        _persist(out, prop, rec, tag=f"{round_tag}_swarm{i}")
        try:
            broker.charge(prop.tokens)
        except BudgetExhausted as e:
            rec["graded"] = False
            rec["budget_exhausted"] = str(e)
            samples.append(rec)
            break
        if prop.patch.strip():
            resolved, secs, gerr = grade(inst, prop.patch, timeout=grade_timeout)
            rec["graded"] = True
            rec["resolved"] = resolved
            rec["grade_seconds"] = secs
            rec["grade_error"] = gerr
            print(f"   swarm[{i}] {spec['model']} patch_len={rec['patch_len']} "
                  f"-> resolved={resolved} ({secs}s){' ERR:'+gerr if gerr else ''}", flush=True)
            samples.append(rec)
            if resolved:
                passed = True
                break
        else:
            rec["graded"] = False
            print(f"   swarm[{i}] {spec['model']} NO PATCH: {rec['error']}", flush=True)
            samples.append(rec)
    return {"arm": "swarm", "passed": passed, "tokens": broker.spent, "samples": samples}


def run_loop(
    instance_id: str,
    *,
    champion: dict = CHAMPION,
    swarm_specs: list[dict] = SWARM,
    best_of_n: int = 3,
    budget: int = 120_000,
    grade_timeout: int = 1800,
    max_rounds: int = 6,
    stop_on_first_pass: bool = True,
    label: str = "run",
) -> dict:
    out = RUN_ROOT / f"loop_{label}_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=True)
    inst, ctx = pull_context(instance_id)
    ctx_chars = sum(len(v) for v in ctx.values())
    print(f"[loop] {instance_id} files={list(ctx)} chars={ctx_chars}  out={out}", flush=True)

    scoreboard = {
        "instance": instance_id,
        "context_chars": ctx_chars,
        "champion_model": champion["model"],
        "swarm_models": [s["model"] for s in swarm_specs],
        "best_of_n": best_of_n,
        "budget_per_arm": budget,
        "rounds": [],
    }
    best = {"champion_passed": False, "swarm_passed": False}

    for rnd in range(1, max_rounds + 1):
        round_tag = f"r{rnd:02d}"
        print(f"\n{'='*64}\n[loop] ROUND {rnd}/{max_rounds}", flush=True)
        champ = _champion_best_of_n(
            inst, ctx, out, champion=champion, n=best_of_n, budget=budget,
            grade_timeout=grade_timeout, round_tag=round_tag,
        )
        swarm = _swarm_arm(
            inst, ctx, out, swarm_specs=swarm_specs, budget=budget,
            grade_timeout=grade_timeout, round_tag=round_tag,
        )
        rrec = {"round": rnd, "champion": champ, "swarm": swarm}
        scoreboard["rounds"].append(rrec)
        best["champion_passed"] = best["champion_passed"] or champ["passed"]
        best["swarm_passed"] = best["swarm_passed"] or swarm["passed"]
        scoreboard["champion_passed"] = best["champion_passed"]
        scoreboard["swarm_passed"] = best["swarm_passed"]
        scoreboard["swarm_lift"] = (1.0 if best["swarm_passed"] else 0.0) - (1.0 if best["champion_passed"] else 0.0)
        (out / "scoreboard.json").write_text(json.dumps(scoreboard, indent=2))
        print(f"[loop] round {rnd}: champion_passed={champ['passed']} swarm_passed={swarm['passed']} "
              f"| cumulative champ={best['champion_passed']} swarm={best['swarm_passed']}", flush=True)
        if stop_on_first_pass and (best["champion_passed"] or best["swarm_passed"]):
            print(f"[loop] POSITIVE NUMBER reached at round {rnd} — stopping.", flush=True)
            break

    scoreboard["finished"] = True
    (out / "scoreboard.json").write_text(json.dumps(scoreboard, indent=2))
    print(f"\n[loop] DONE. champion_passed={best['champion_passed']} swarm_passed={best['swarm_passed']} "
          f"lift={scoreboard.get('swarm_lift')}  -> {out}", flush=True)
    return scoreboard


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
        instances_done.append(iid)
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Forge v1 autoresearch loop")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("capture", help="propose-only (no Docker); save raw outputs")
    c.add_argument("--instance", default=DEFAULT_INSTANCE)
    c.add_argument("--models", default="gemini-2.5-flash,glm-5.2")
    c.add_argument("--max-tokens", type=int, default=8192)
    c.add_argument("--label", default="probe")

    g = sub.add_parser("grade", help="Docker-grade one patch file")
    g.add_argument("--instance", default=DEFAULT_INSTANCE)
    g.add_argument("--patch", required=True)
    g.add_argument("--grade-timeout", type=int, default=1800)

    lp = sub.add_parser("loop", help="full autoresearch loop (champion vs swarm, graded)")
    lp.add_argument("--instance", default=DEFAULT_INSTANCE)
    lp.add_argument("--best-of-n", type=int, default=3)
    lp.add_argument("--budget", type=int, default=120_000)
    lp.add_argument("--grade-timeout", type=int, default=1800)
    lp.add_argument("--max-rounds", type=int, default=6)
    lp.add_argument("--label", default="run")
    lp.add_argument("--keep-going", action="store_true", help="do not stop on first pass (chase lift)")

    mx = sub.add_parser("matrix", help="grade EVERY model on EVERY instance (decorrelation + lift matrix)")
    mx.add_argument("--instances", required=True, help="comma-separated SWE-bench Verified instance ids")
    mx.add_argument("--models", default="kimi-for-coding,moonshotai/kimi-k2.6,glm-5.2,gemini-2.5-flash",
                    help="comma-separated swarm model ids to test on every instance")
    mx.add_argument("--grade-timeout", type=int, default=1800)
    mx.add_argument("--label", default="matrix")

    mu = sub.add_parser("multi", help="nonstop multi-instance lift engine (aggregate pass rates + lift)")
    mu.add_argument("--instances", required=True, help="comma-separated SWE-bench Verified instance ids")
    mu.add_argument("--champion", default="moonshotai/kimi-k2.6",
                    help="single champion model id (best-of-N arm)")
    mu.add_argument("--swarm", default="moonshotai/kimi-k2.6,glm-5.2,gemini-2.5-flash",
                    help="comma-separated decorrelated swarm model ids")
    mu.add_argument("--best-of-n", type=int, default=3)
    mu.add_argument("--budget", type=int, default=120_000)
    mu.add_argument("--grade-timeout", type=int, default=1800)
    mu.add_argument("--label", default="multi")

    args = ap.parse_args(argv)

    if args.cmd == "capture":
        specs = []
        for m in [x.strip() for x in args.models.split(",") if x.strip()]:
            t = 1.0 if m == "kimi-for-coding" else 0.2
            specs.append({"model": m, "temperature": t, "max_tokens": args.max_tokens,
                          "timeout_s": 200})
        run_capture(args.instance, specs, label=args.label)
        return 0

    if args.cmd == "grade":
        inst = verified_instances(instance_ids=[args.instance])[0]
        patch = Path(args.patch).read_text()
        resolved, secs, err = grade(inst, patch, timeout=args.grade_timeout)
        print(json.dumps({"instance": args.instance, "resolved": resolved,
                          "grade_seconds": secs, "error": err}, indent=2))
        return 0

    if args.cmd == "loop":
        run_loop(
            args.instance,
            best_of_n=args.best_of_n,
            budget=args.budget,
            grade_timeout=args.grade_timeout,
            max_rounds=args.max_rounds,
            stop_on_first_pass=not args.keep_going,
            label=args.label,
        )
        return 0

    if args.cmd == "matrix":
        ids = [x.strip() for x in args.instances.split(",") if x.strip()]
        models = [x.strip() for x in args.models.split(",") if x.strip()]
        run_matrix(ids, models, grade_timeout=args.grade_timeout, label=args.label)
        return 0

    if args.cmd == "multi":
        ids = [x.strip() for x in args.instances.split(",") if x.strip()]
        champion = spec_for(args.champion)
        swarm = [spec_for(m.strip()) for m in args.swarm.split(",") if m.strip()]
        run_multi(
            ids,
            champion=champion,
            swarm_specs=swarm,
            best_of_n=args.best_of_n,
            budget=args.budget,
            grade_timeout=args.grade_timeout,
            label=args.label,
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
