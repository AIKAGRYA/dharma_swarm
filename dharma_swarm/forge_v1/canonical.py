"""Forge v1 — CANONICAL measurement core (built to reports/forge/FORGE_CANONICAL_INDEX.md).

This is the honest Level-4 external measurement: it draws its roster from the FULL
model pool (evolution_roster.select_models_for_cycle), empirically filters to the
subset CALLABLE from this environment (a census — the honest answer to "why only
a few models?"), then runs the canonical CONTROL ARMS at matched token budget,
Docker-graded by the official SWE-bench harness, and emits the canonical receipt
packet + a valid closeout state.

Arms (subset of the canon's required arms that are buildable without the live A2A
spine; full_a2a_swarm + topology_variants are the next phase):
  - frontier_single_full_budget : strongest reachable model, ONE attempt at budget
  - best_of_n_same_model        : strongest model, best-of-N to budget (sampling control)
  - same_budget_self_moa        : best-of-N samples on one model + a SYNTHESIS pass (self-aggregation)
  - swarm_union_verifier_gated   : the diverse reachable roster, each proposes, verifier keeps first pass
  - planner_builder_verifier_no_a2a : a real 3-role pipeline (plan -> build -> verify-repair), no bus

Lift (canonical) = best(swarm arms) - max(single-model controls), per the contract:
  lift = full_swarm - max(best_single_full_budget, same_budget_self_moa).

CLI:
  python -m dharma_swarm.forge_v1.canonical census --strategy explore -n 12
  python -m dharma_swarm.forge_v1.canonical run --instances django__django-12209 --budget 60000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
if str(WT) not in sys.path:
    sys.path.insert(0, str(WT))

from dharma_swarm.api_keys import bootstrap_runtime_env  # noqa: E402

bootstrap_runtime_env()

from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402
from dharma_swarm.forge_v1.autoloop import grade, pull_context, _safe, window_context  # noqa: E402
from dharma_swarm.forge_v1.harness import BudgetExhausted, TokenBroker  # noqa: E402
from dharma_swarm.forge_v1.providers import _complete_and_close, _usage_tokens  # noqa: E402
from dharma_swarm.forge_v1.run_real import (  # noqa: E402
    _rate_limit_wait_s,
    apply_edit_blocks,
    build_repair_prompt,
    compute_unified_diff,
    parse_edit_blocks,
    parse_full_files,
)
from dharma_swarm.model_pool import (  # noqa: E402
    FORGE_KIMI_CODE_MODEL_ID,
    FORGE_KIMI_K3_LOGICAL_ID,
    FORGE_KIMI_K3_OPENROUTER_MODEL_ID,
)

RUN_ROOT = dharma_state_dir() / "forge_v1" / "canonical"
LEDGER = dharma_state_dir() / "forge_v1" / "FORGE_BUILD_LEDGER.md"

# K3 has a 1M-token Kimi Code context window, so it no longer inherits the old
# K2.7 windowing workaround. It still requires temperature=1 on Kimi endpoints.
WINDOW_MODELS: frozenset[str] = frozenset()
KIMI_TEMP1 = {
    FORGE_KIMI_CODE_MODEL_ID,
    FORGE_KIMI_K3_LOGICAL_ID,
    FORGE_KIMI_K3_OPENROUTER_MODEL_ID,
}


# --------------------------------------------------------------------------- #
# Roster from the FULL pool, routed via each slot's OWN provider (hierarchy-true)
# --------------------------------------------------------------------------- #
def pool_slots(n: int, strategy: str = "explore"):
    from dharma_swarm.evolution_roster import select_models_for_cycle

    return select_models_for_cycle(n=n, strategy=strategy)


def _provider_for_slot(slot, *, timeout_s: int):
    """Build a live provider from a ModelSlot using its OWN provider type (not
    prefix-matching) — the hierarchy-true path. Raises if no live key/config."""
    from dharma_swarm.runtime_provider import (
        create_runtime_provider,
        resolve_runtime_provider_config,
    )

    cfg = resolve_runtime_provider_config(slot.provider, model=slot.model_id, timeout_seconds=timeout_s)
    if not cfg.available:
        raise RuntimeError(f"provider {slot.provider.value} has no live key/config")
    return create_runtime_provider(cfg), (cfg.default_model or slot.model_id)


def _call(provider, wire: str, prompt_or_messages, *, max_tokens: int, temperature: float,
          timeout_s: int) -> tuple[str, int, str | None]:
    """One live call with hard timeout + 429 backoff. Returns (text, tokens, stop_reason)."""
    from dharma_swarm.models import LLMRequest

    messages = ([{"role": "user", "content": prompt_or_messages}]
                if isinstance(prompt_or_messages, str) else prompt_or_messages)
    req = LLMRequest(model=wire, messages=messages, max_tokens=max_tokens, temperature=temperature)

    async def _c():
        return await _complete_and_close(provider, req, timeout_s=timeout_s)

    for attempt in range(4):
        try:
            r = asyncio.run(_c())
            return (r.content or ""), _usage_tokens(r.usage), getattr(r, "stop_reason", None)
        except Exception as e:
            w = _rate_limit_wait_s(e)
            if w is None or attempt >= 3:
                raise
            time.sleep(w)
    return "", 0, None


# --------------------------------------------------------------------------- #
# Census: which of the full pool is callable from HERE (the honest answer)
# --------------------------------------------------------------------------- #
def census(strategy: str = "explore", n: int = 12, *, timeout_s: int = 40) -> dict:
    slots = pool_slots(n=n, strategy=strategy)
    # dedupe by model_id, preserve order
    seen, uniq = set(), []
    for s in slots:
        if s.model_id in seen:
            continue
        seen.add(s.model_id)
        uniq.append(s)
    rows = []
    for s in uniq:
        row = {"model_id": s.model_id, "provider": s.provider.value, "tier": getattr(s.tier, "value", str(s.tier))}
        try:
            prov, wire = _provider_for_slot(s, timeout_s=timeout_s)
        except Exception as e:
            row["status"] = "no_route"
            row["detail"] = f"{type(e).__name__}: {str(e)[:60]}"
            rows.append(row)
            continue
        temp = 1.0 if s.model_id in KIMI_TEMP1 else 0.2
        t0 = time.time()
        try:
            text, toks, _ = _call(prov, wire, "Reply with the single word OK.",
                                   max_tokens=16, temperature=temp, timeout_s=timeout_s)
            row["seconds"] = round(time.time() - t0, 1)
            row["status"] = "callable" if (text or "").strip() else "empty"
            row["sample"] = (text or "").strip()[:24]
        except Exception as e:
            row["seconds"] = round(time.time() - t0, 1)
            row["status"] = "error"
            row["detail"] = f"{type(e).__name__}: {str(e)[:60]}"
        rows.append(row)
    callable_ids = [r["model_id"] for r in rows if r.get("status") == "callable"]
    return {"strategy": strategy, "n_requested": n, "n_pool_unique": len(uniq),
            "n_callable": len(callable_ids), "callable": callable_ids, "rows": rows}


# --------------------------------------------------------------------------- #
# Slot-aware proposal (build prompt -> call w/ finish-the-block continuation ->
# parse -> apply against FULL file -> diff). Returns a graded-ready patch.
# --------------------------------------------------------------------------- #
def _propose_slot(slot, inst: dict, ctx: dict, *, max_tokens: int, timeout_s: int,
                  continue_rounds: int = 2, window_chars: int | None = None,
                  extra_instruction: str = "") -> dict:
    temp = 1.0 if slot.model_id in KIMI_TEMP1 else 0.2
    prompt_ctx = ctx
    if (slot.model_id in WINDOW_MODELS) or window_chars:
        prompt_ctx = window_context(ctx, inst.get("problem_statement", ""),
                                    max_chars=window_chars or 11000)
    base_prompt = build_repair_prompt(inst, prompt_ctx)
    if extra_instruction:
        base_prompt = extra_instruction + "\n\n" + base_prompt
    rec = {"model": slot.model_id, "provider": slot.provider.value, "tokens": 0,
           "patch": "", "error": None, "seconds": 0.0}
    t0 = time.time()
    try:
        prov, wire = _provider_for_slot(slot, timeout_s=timeout_s)
    except Exception as e:
        rec["error"] = f"route: {type(e).__name__}: {e}"
        rec["seconds"] = round(time.time() - t0, 1)
        return rec
    messages = [{"role": "user", "content": base_prompt}]
    accumulated, total = "", 0
    try:
        for rnd in range(continue_rounds + 1):
            text, toks, stop = _call(prov, wire, messages, max_tokens=max_tokens,
                                     temperature=temp, timeout_s=timeout_s)
            total += toks
            accumulated += (("\n" if accumulated else "") + text)
            if parse_edit_blocks(accumulated) or parse_full_files(accumulated):
                break
            if rnd >= continue_rounds:
                break
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content":
                          "Now output ONLY the SEARCH/REPLACE edit block(s) in the exact format, "
                          "nothing else: <<<<<<< SEARCH path=<file>\\n<exact original>\\n=======\\n"
                          "<replacement>\\n>>>>>>> REPLACE"}]
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[:80]}"
        rec["tokens"] = total
        rec["seconds"] = round(time.time() - t0, 1)
        return rec
    rec["tokens"] = total
    rec["raw_len"] = len(accumulated)
    edits = parse_edit_blocks(accumulated)
    new_files, err = (apply_edit_blocks(ctx, edits) if edits else (parse_full_files(accumulated), None))
    if edits and err:
        rec["error"] = err
    elif not edits and not new_files:
        rec["error"] = "no edit block"
    else:
        patch = compute_unified_diff(ctx, new_files)
        rec["patch"] = patch
        if not patch.strip():
            rec["error"] = "no change vs base"
    rec["seconds"] = round(time.time() - t0, 1)
    return rec


def _grade_patch(inst, patch, broker, grade_timeout, samples, label):
    """Charge tokens, grade if non-empty, append a sample. Returns resolved bool or None(budget)."""
    if not patch.strip():
        return False
    try:
        resolved, secs, gerr = grade(inst, patch, timeout=grade_timeout)
    except Exception as e:
        resolved, secs, gerr = False, 0.0, f"{type(e).__name__}: {e}"
    samples.append({"arm": label, "resolved": resolved, "grade_seconds": secs, "grade_error": gerr,
                    "patch_len": len(patch)})
    return resolved


# --------------------------------------------------------------------------- #
# The arms
# --------------------------------------------------------------------------- #
def arm_best_of_n(slot, inst, ctx, *, n, budget, grade_timeout, per_call_tokens, timeout_s, out, tag):
    broker = TokenBroker(cap=budget)
    samples = []
    passed = False
    for i in range(n):
        rec = _propose_slot(slot, inst, ctx, max_tokens=per_call_tokens, timeout_s=timeout_s)
        try:
            broker.charge(rec["tokens"])
        except BudgetExhausted:
            break
        _persist_rec(out, rec, f"{tag}_{i}")
        if rec["patch"].strip():
            r = _grade_patch(inst, rec["patch"], broker, grade_timeout, samples, tag)
            samples[-1]["model"] = slot.model_id
            if r:
                passed = True
                break
        else:
            samples.append({"arm": tag, "model": slot.model_id, "resolved": False,
                            "error": rec.get("error"), "patch_len": 0})
    return {"arm": tag, "model": slot.model_id, "passed": passed,
            "tokens": broker.spent, "samples": samples}


def arm_self_moa(slot, inst, ctx, *, n, budget, grade_timeout, per_call_tokens, timeout_s, out, tag):
    """Same model, N samples, then a SYNTHESIS pass that picks/merges the best fix —
    self-aggregation control (distinct from best-of-N's verifier selection)."""
    broker = TokenBroker(cap=budget)
    samples = []
    candidates = []
    for i in range(n):
        rec = _propose_slot(slot, inst, ctx, max_tokens=per_call_tokens, timeout_s=timeout_s)
        try:
            broker.charge(rec["tokens"])
        except BudgetExhausted:
            break
        if rec["patch"].strip():
            candidates.append(rec["patch"])
    # Synthesis: give the model its own candidates, ask for the single best edit.
    passed = False
    if candidates:
        synth_instr = ("You produced these candidate fixes (unified diffs). Synthesize the SINGLE best, "
                       "correct, minimal fix and output it as SEARCH/REPLACE edit block(s) only:\n\n"
                       + "\n\n--- candidate ---\n".join(c[:1500] for c in candidates[:4]))
        srec = _propose_slot(slot, inst, ctx, max_tokens=per_call_tokens, timeout_s=timeout_s,
                             extra_instruction=synth_instr)
        try:
            broker.charge(srec["tokens"])
        except BudgetExhausted:
            srec = {"patch": candidates[0]}  # fall back to first candidate if budget spent
        _persist_rec(out, srec, f"{tag}_synth")
        patch = srec.get("patch") or (candidates[0] if candidates else "")
        if patch.strip():
            passed = bool(_grade_patch(inst, patch, broker, grade_timeout, samples, tag))
            if samples:
                samples[-1]["model"] = slot.model_id
    return {"arm": tag, "model": slot.model_id, "passed": passed,
            "tokens": broker.spent, "n_candidates": len(candidates), "samples": samples}


def arm_swarm_union(slots, inst, ctx, *, budget, grade_timeout, per_call_tokens, timeout_s, out, tag):
    """Diverse reachable roster: each proposes once; verifier keeps the first resolve."""
    broker = TokenBroker(cap=budget)
    samples = []
    passed = False
    edges = []
    for s in slots:
        rec = _propose_slot(s, inst, ctx, max_tokens=per_call_tokens, timeout_s=timeout_s)
        try:
            broker.charge(rec["tokens"])
        except BudgetExhausted:
            break
        _persist_rec(out, rec, f"{tag}_{_safe(s.model_id)}")
        if rec["patch"].strip():
            r = _grade_patch(inst, rec["patch"], broker, grade_timeout, samples, tag)
            samples[-1]["model"] = s.model_id
            edges.append({"from": s.model_id, "to": "verifier", "kind": "proposal", "resolved": bool(r)})
            if r:
                passed = True
                break
        else:
            samples.append({"arm": tag, "model": s.model_id, "resolved": False,
                            "error": rec.get("error"), "patch_len": 0})
    return {"arm": tag, "passed": passed, "tokens": broker.spent, "samples": samples, "edges": edges}


def arm_pbv(slots, inst, ctx, *, budget, grade_timeout, per_call_tokens, timeout_s, out, tag):
    """planner -> builder -> verifier pipeline (a REAL coordination topology, no A2A bus).
    planner: analyze bug + name the exact lines/approach. builder: emit SEARCH/REPLACE given the plan.
    verifier: review+repair the builder's edits. Uses up to 3 decorrelated reachable models."""
    if len(slots) < 1:
        return {"arm": tag, "passed": False, "tokens": 0, "samples": []}
    planner = slots[0]
    builder = slots[1 % len(slots)]
    verifier = slots[2 % len(slots)]
    broker = TokenBroker(cap=budget)
    edges = []
    roles = {"planner": planner.model_id, "builder": builder.model_id, "verifier": verifier.model_id}

    def _invalid_budget(stage: str, exc: Exception, rec: dict | None = None) -> dict:
        if rec is not None:
            safe_rec = {**rec, "patch": "", "error": f"budget_exhausted:{stage}: {exc}"}
            _persist_rec(out, safe_rec, f"{tag}_{stage}_over_budget")
        edges.append({"from": roles.get(stage, stage), "to": tag, "kind": "budget_exhausted",
                      "error": str(exc)[:80]})
        return {"arm": tag, "passed": False, "tokens": broker.spent, "samples": [],
                "roles": roles, "edges": edges, "invalid": True,
                "error": f"{stage} exceeded token budget before grading"}
    # 1) planner
    pctx = window_context(ctx, inst.get("problem_statement", ""), max_chars=11000) \
        if planner.model_id in WINDOW_MODELS else ctx
    plan_prompt = (f"You are the PLANNER. Repo {inst['repo']}. Bug:\n{inst['problem_statement'][:2000]}\n\n"
                   f"Source:\n" + "\n".join(f"```\n{c[:12000]}\n```" for c in pctx.values()) +
                   "\n\nIdentify the EXACT function and lines to change and the minimal fix approach. "
                   "Be concrete (file path, surrounding code). Do NOT write the diff.")
    plan = ""
    try:
        prov, wire = _provider_for_slot(planner, timeout_s=timeout_s)
        temp = 1.0 if planner.model_id in KIMI_TEMP1 else 0.2
        plan, ptok, _ = _call(prov, wire, plan_prompt, max_tokens=per_call_tokens, temperature=temp, timeout_s=timeout_s)
        broker.charge(ptok)
        edges.append({"from": planner.model_id, "to": builder.model_id, "kind": "plan"})
    except Exception as e:
        plan = ""
        edges.append({"from": planner.model_id, "to": builder.model_id, "kind": "plan_failed", "error": str(e)[:60]})
    # 2) builder (given the plan)
    build_instr = f"A senior engineer analyzed this bug and produced this PLAN:\n{plan[:2500]}\n\nFollow the plan."
    brec = _propose_slot(builder, inst, ctx, max_tokens=per_call_tokens, timeout_s=timeout_s,
                         extra_instruction=build_instr)
    try:
        broker.charge(brec["tokens"])
    except BudgetExhausted as exc:
        return _invalid_budget("builder", exc, brec)
    _persist_rec(out, brec, f"{tag}_build")
    patch = brec["patch"]
    # 3) verifier repair (if builder produced something, ask verifier to review/fix)
    if patch.strip():
        vrec = _propose_slot(verifier, inst, ctx, max_tokens=per_call_tokens, timeout_s=timeout_s,
                             extra_instruction=("Another engineer proposed this patch:\n" + patch[:2000] +
                                                "\nReview it. If correct, reproduce it. If wrong, output the corrected SEARCH/REPLACE block(s)."))
        try:
            broker.charge(vrec["tokens"])
        except BudgetExhausted as exc:
            return _invalid_budget("verifier", exc, vrec)
        _persist_rec(out, vrec, f"{tag}_verify")
        if vrec["patch"].strip():
            patch = vrec["patch"]
            edges.append({"from": builder.model_id, "to": verifier.model_id, "kind": "review"})
    samples = []
    passed = False
    if patch.strip():
        passed = bool(_grade_patch(inst, patch, broker, grade_timeout, samples, tag))
    return {"arm": tag, "passed": passed, "tokens": broker.spent, "samples": samples,
            "roles": roles, "edges": edges}


def _persist_rec(out: Path, rec: dict, tag: str) -> None:
    try:
        (out / f"{tag}.json").write_text(json.dumps({k: v for k, v in rec.items() if k != "patch"}, indent=2, default=str))
        if rec.get("patch", "").strip():
            (out / f"{tag}.patch").write_text(rec["patch"])
    except OSError as e:
        print(f"[canonical] failed to persist {tag}: {e}", flush=True)


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
def run_canonical(instance_ids: list[str], *, strategy: str = "explore", roster_n: int = 12,
                  budget: int = 60000, per_call_tokens: int = 8192, best_of_n: int = 3,
                  grade_timeout: int = 1800, timeout_s: int = 300, label: str = "run") -> dict:
    out = RUN_ROOT / f"{label}_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=True)
    print(f"[canonical] census of pool (strategy={strategy}, n={roster_n}) ...", flush=True)
    cen = census(strategy=strategy, n=roster_n, timeout_s=60)
    print(f"[canonical] callable from here: {cen['n_callable']}/{cen['n_pool_unique']} -> {cen['callable']}", flush=True)
    (out / "model_roster.json").write_text(json.dumps(cen, indent=2))
    # map callable ids back to slots
    all_slots = pool_slots(n=roster_n, strategy=strategy)
    by_id = {}
    for s in all_slots:
        by_id.setdefault(s.model_id, s)
    callable_slots = [by_id[m] for m in cen["callable"] if m in by_id]
    if not callable_slots:
        manifest = {"closeout": "blocked_with_evidence", "reason": "no callable models in pool from this env", "census": cen}
        (out / "decision_record.md").write_text(json.dumps(manifest, indent=2))
        print("[canonical] BLOCKED: no callable models.", flush=True)
        return manifest
    # frontier_single control = STRONGEST callable model (by tier), not just first.
    _tier_rank = {"frontier": 0, "strong": 1, "fast": 2, "free": 3, "local": 4}
    champion = min(callable_slots, key=lambda s: _tier_rank.get(getattr(s.tier, "value", str(s.tier)), 9))

    manifest = {"kind": "forge_canonical_measurement", "instances": instance_ids,
                "strategy": strategy, "budget_per_arm": budget, "best_of_n": best_of_n,
                "callable_roster": cen["callable"], "champion": champion.model_id,
                "per_instance": []}
    for iid in instance_ids:
        print(f"\n{'#'*64}\n[canonical] instance {iid}", flush=True)
        inst, ctx = pull_context(iid)
        idir = out / _safe(iid)
        idir.mkdir(exist_ok=True)
        arms = {}
        arms["frontier_single_full_budget"] = arm_best_of_n(
            champion, inst, ctx, n=1, budget=budget, grade_timeout=grade_timeout,
            per_call_tokens=per_call_tokens, timeout_s=timeout_s, out=idir, tag="frontier_single")
        arms["best_of_n_same_model"] = arm_best_of_n(
            champion, inst, ctx, n=best_of_n, budget=budget, grade_timeout=grade_timeout,
            per_call_tokens=per_call_tokens, timeout_s=timeout_s, out=idir, tag="best_of_n")
        arms["same_budget_self_moa"] = arm_self_moa(
            champion, inst, ctx, n=best_of_n, budget=budget, grade_timeout=grade_timeout,
            per_call_tokens=per_call_tokens, timeout_s=timeout_s, out=idir, tag="self_moa")
        arms["swarm_union_verifier_gated"] = arm_swarm_union(
            callable_slots, inst, ctx, budget=budget, grade_timeout=grade_timeout,
            per_call_tokens=per_call_tokens, timeout_s=timeout_s, out=idir, tag="swarm_union")
        arms["planner_builder_verifier_no_a2a"] = arm_pbv(
            callable_slots, inst, ctx, budget=budget, grade_timeout=grade_timeout,
            per_call_tokens=per_call_tokens, timeout_s=timeout_s, out=idir, tag="pbv")
        manifest["per_instance"].append({"instance": iid, "arms": {k: v.get("passed") for k, v in arms.items()},
                                          "detail": arms})
        for k, v in arms.items():
            print(f"   {k:34} passed={v.get('passed')} tokens={v.get('tokens')}", flush=True)
        (out / "results.jsonl").write_text("\n".join(json.dumps(p) for p in manifest["per_instance"]))
        _write_packet(out, manifest)
    _finalize(out, manifest)
    return manifest


from dharma_swarm.forge_v1.canonical_report import _finalize, _write_packet  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Forge v1 canonical measurement core")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("census", help="which of the full pool is callable from here")
    c.add_argument("--strategy", default="explore")
    c.add_argument("-n", type=int, default=12)
    r = sub.add_parser("run", help="run the canonical control arms, graded")
    r.add_argument("--instances", required=True)
    r.add_argument("--strategy", default="explore")
    r.add_argument("--roster-n", type=int, default=12)
    r.add_argument("--budget", type=int, default=60000)
    r.add_argument("--per-call-tokens", type=int, default=8192)
    r.add_argument("--best-of-n", type=int, default=3)
    r.add_argument("--grade-timeout", type=int, default=1800)
    r.add_argument("--timeout-s", type=int, default=300)
    r.add_argument("--label", default="run")
    args = ap.parse_args(argv)

    if args.cmd == "census":
        cen = census(strategy=args.strategy, n=args.n)
        for row in cen["rows"]:
            mark = {"callable": "✓", "error": "✗", "no_route": "·", "empty": "~"}.get(row["status"], "?")
            print(f"  {mark} {row['model_id']:38} {row['provider']:12} {row.get('tier',''):8} "
                  f"{row['status']:10}{' '+str(row.get('detail',''))[:50] if row.get('detail') else ''}")
        print(f"\ncallable from here: {cen['n_callable']}/{cen['n_pool_unique']} -> {cen['callable']}")
        return 0
    if args.cmd == "run":
        ids = [x.strip() for x in args.instances.split(",") if x.strip()]
        run_canonical(ids, strategy=args.strategy, roster_n=args.roster_n, budget=args.budget,
                      per_call_tokens=args.per_call_tokens, best_of_n=args.best_of_n,
                      grade_timeout=args.grade_timeout, timeout_s=args.timeout_s, label=args.label)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
