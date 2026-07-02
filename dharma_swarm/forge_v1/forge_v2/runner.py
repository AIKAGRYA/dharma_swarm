"""Forge v2 first slice: mission_class=verifier_role, self_moa vs verify_chain.

End-to-end falsification run that emits the minimum-verifier-run proof: matched
budget, Docker grade, paired bootstrap CI of (verify_chain - self_moa), cross-
family critic gate, full receipts + ledger + closeout + auto next experiment.
A CI lower bound <= 0 is a SUCCESSFUL run — the null survived.

Run:
  PYTHONPATH=$PWD DOCKER_CONTEXT=colima-forge-swebench python -m \
    dharma_swarm.forge_v1.forge_v2.runner \
    --instances django__django-12209,sympy__sympy-22914,sympy__sympy-19954,django__django-11141,sympy__sympy-15599 \
    --n-explore 3 --replicates 3 --budget 60000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
if str(WT) not in sys.path:
    sys.path.insert(0, str(WT))
os.environ.setdefault("DOCKER_CONTEXT", os.environ.get("FORGE_DOCKER_CONTEXT", "colima-forge-swebench"))

from dharma_swarm.api_keys import bootstrap_runtime_env  # noqa: E402

bootstrap_runtime_env()

from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402
from dharma_swarm.forge_v1.autoloop import grade, pull_context, _safe  # noqa: E402
from dharma_swarm.forge_v1.canonical import _call, _provider_for_slot, pool_slots, KIMI_TEMP1  # noqa: E402
from dharma_swarm.model_pool import (  # noqa: E402
    default_for_provider,
    forge_default_high_slot_verifier_id,
    forge_high_slot_model_ids,
)
from dharma_swarm.models import ProviderType  # noqa: E402

from .arms import (
    DEFAULT_WINDOW_CHARS,
    GEN_TEMPLATE,
    SYNTH_TEMPLATE,
    VERIFY_TEMPLATE,
    mixed_moa_arm,
    self_moa_arm,
    verify_chain_arm,
)
from .budget import Budget
from .critic import _family, refute_pass
from .pr_suite_grader import (
    grade_pr_suite_prediction,
    is_pr_suite_task,
    is_pr_suite_task_id,
    load_pr_suite_context,
)
from .provenance import aggregate_contamination_states, contamination_state, split_explore_confirm
from .receipts import AttemptReceipt, Ledger, RunReceipt, scaffold_parity_hash
from .stats import paired_bootstrap_ci, positive_claim_gate, replicate_variance

RUN_ROOT = dharma_state_dir() / "forge_v1" / "forge_v2"
_TIER = {"frontier": 0, "strong": 1, "fast": 2, "free": 3, "local": 4}
FORGE_HIGH_SLOT_MIN_RELEASE_DATE = "2026-04-01"
DEFAULT_FORGE_HIGH_SLOT_PROBE_TIMEOUT_S = 20
DEFAULT_FORGE_GENERATOR_MODEL = default_for_provider(ProviderType.ZHIPU)
DEFAULT_FORGE_VERIFIER_MODEL = forge_default_high_slot_verifier_id()
FORGE_HIGH_SLOT_MODEL_IDS = forge_high_slot_model_ids()


class _SimpleSlot:
    """Minimal ModelSlot stand-in so a pinned model id (reproducible first slice)
    can be used directly, without depending on a stochastic pool draw."""

    def __init__(self, model_id, provider, tier="strong"):
        self.model_id = model_id
        self.provider = provider
        self.tier = tier


def _prefix_provider(model_id: str):
    """Prefix routing for capable models that are NOT discrete model_pool entries
    (mirrors providers._provider_for_model). Lets a capable model — e.g. gemini-* —
    be CHAMPIONED as generator/verifier instead of being locked out of the roster."""
    from dharma_swarm.model_hierarchy import ProviderType

    mid = (model_id or "").strip().lower()
    if mid.startswith("gemini"):
        return ProviderType.GOOGLE_AI
    if mid.startswith("gpt") or mid.startswith("o1") or mid.startswith("o3"):
        return ProviderType.OPENAI
    if mid.startswith("claude") or mid.startswith("opus") or mid.startswith("sonnet"):
        return ProviderType.ANTHROPIC
    if mid.startswith("glm-5.2") or mid.startswith("zai/") or mid.startswith("z-ai/"):
        return ProviderType.ZHIPU
    if mid in {"kimi-for-coding", "kimi-code"} or mid.startswith("kimi_code/") or mid.startswith("kimi-code/"):
        return ProviderType.KIMI_CODE
    if mid.startswith("nvidia/") or mid.startswith("meta/") or "llama" in mid:
        return ProviderType.NVIDIA_NIM
    if "/" in mid:
        return ProviderType.OPENROUTER
    return None


def _slot_for_id(model_id: str):
    """Resolve a pinned model id to a (model_id, provider) slot. Prefer the model
    pool (hierarchy-true); fall back to PREFIX routing so a capable model that is
    not a discrete pool entry (e.g. gemini-2.5-flash) can still be pinned."""
    from dharma_swarm.model_pool import entry_for_model_id

    entry = entry_for_model_id(model_id)
    if entry is not None and entry.routes:
        route = next((r for r in entry.routes if r.model_id == model_id), entry.routes[0])
        return _SimpleSlot(route.model_id, route.provider, getattr(entry, "tier", "strong"))
    prov = _prefix_provider(model_id)
    if prov is not None:
        return _SimpleSlot(model_id, prov, "frontier")
    return None


def _dedupe_model_ids(model_ids: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for model_id in model_ids:
        mid = (model_id or "").strip()
        key = mid.lower()
        if not mid or key in seen:
            continue
        seen.add(key)
        out.append(mid)
    return out


def _is_high_slot_model_id(model_id: str) -> bool:
    """True iff ``model_id`` is allowed for Forge generator/verifier slots.

    Forge high slots are deliberately stricter than the general Dharma router:
    they may use only the operator-curated post-2026-04 frontier ladder. Older or
    sub-floor models can still be used as delegated workhorses elsewhere, but not
    as the top-level evolution grader/generator unless explicitly overridden.
    """
    if os.environ.get("FORGE_ALLOW_LEGACY_HIGH_SLOT") == "1":
        return True
    mid = (model_id or "").strip()
    if mid in FORGE_HIGH_SLOT_MODEL_IDS:
        return True
    return False


def _high_slot_candidate_ids(*preferred_ids: str | None) -> list[str]:
    preferred = [model_id for model_id in preferred_ids if model_id]
    return _dedupe_model_ids([*preferred, *FORGE_HIGH_SLOT_MODEL_IDS])


def _high_slot_probe_timeout_s(timeout_s: int) -> int:
    configured = int(
        os.environ.get(
            "FORGE_HIGH_SLOT_PROBE_TIMEOUT_S",
            str(DEFAULT_FORGE_HIGH_SLOT_PROBE_TIMEOUT_S),
        )
    )
    return max(1, min(int(timeout_s), configured))


def _probe(slot, timeout_s=40) -> bool:
    try:
        prov, wire = _provider_for_slot(slot, timeout_s=timeout_s)
        temp = 1.0 if slot.model_id in KIMI_TEMP1 else 0.2
        # 256 (not 16): reasoning models (gemini-2.5-*) spend tokens on internal
        # thinking before visible output; 16 truncates to empty -> false-negative.
        from dharma_swarm.models import LLMRequest

        req = LLMRequest(
            model=wire,
            messages=[{"role": "user", "content": "Reply with the single word OK."}],
            max_tokens=256,
            temperature=temp,
        )

        async def _once():
            return await asyncio.wait_for(prov.complete(req), timeout=timeout_s)

        response = asyncio.run(_once())
        return bool((getattr(response, "content", "") or "").strip())
    except Exception:
        return False


def _resolve_high_slot_pair(gen_id: str | None, ver_id: str | None, *, timeout_s: int):
    """Resolve Forge's generator/verifier through the recent-frontier ladder.

    This is not the general Dharma Swarm fallback router. It is the stricter
    Forge high-slot policy: exact pins are tried first only if they satisfy the
    recent-frontier floor; then the curated >=2026-04 ladder is probed. The first
    callable model becomes generator, and the first callable cross-family model
    becomes verifier.
    """
    callable_slots: list = []
    rows: list[dict] = []
    probe_timeout_s = _high_slot_probe_timeout_s(timeout_s)
    for model_id in _high_slot_candidate_ids(gen_id, ver_id):
        slot = _slot_for_id(model_id)
        row = {
            "role": "forge_high_slot_candidate",
            "model_id": model_id,
            "high_slot_min_release_date": FORGE_HIGH_SLOT_MIN_RELEASE_DATE,
            "probe_timeout_s": probe_timeout_s,
        }
        if slot is None:
            row.update({"callable": False, "error": "unresolved_model_id"})
            rows.append(row)
            continue
        row["provider"] = getattr(slot.provider, "value", str(slot.provider))
        if not _is_high_slot_model_id(slot.model_id):
            row.update({"callable": False, "error": "below_recent_high_slot_floor"})
            rows.append(row)
            continue
        ok = _probe(slot, timeout_s=probe_timeout_s)
        row["callable"] = ok
        rows.append(row)
        if ok:
            callable_slots.append(slot)
            if len({_family(candidate.model_id) for candidate in callable_slots}) >= 2:
                break

    gen = callable_slots[0] if callable_slots else None
    ver = None
    if gen is not None:
        gfam = _family(gen.model_id)
        ver = next((slot for slot in callable_slots[1:] if _family(slot.model_id) != gfam), None)
    return gen, ver, callable_slots, rows


def _callable_roster(n: int, strategy: str, timeout_s: int = 40) -> tuple[list, list]:
    """pool_slots -> probe reachable. Returns (callable_slots, probe_rows)."""
    slots = pool_slots(n=n, strategy=strategy)
    seen, uniq = set(), []
    for s in slots:
        if s.model_id in seen:
            continue
        seen.add(s.model_id)
        uniq.append(s)
    callable_slots, rows = [], []
    for s in uniq:
        try:
            prov, wire = _provider_for_slot(s, timeout_s=timeout_s)
            temp = 1.0 if s.model_id in KIMI_TEMP1 else 0.2
            text, _, _ = _call(prov, wire, "Reply with the single word OK.",
                               max_tokens=256, temperature=temp, timeout_s=timeout_s)
            ok = bool((text or "").strip())
            rows.append({"model_id": s.model_id, "provider": s.provider.value, "callable": ok})
            if ok:
                callable_slots.append(s)
        except Exception as e:
            rows.append({"model_id": s.model_id, "provider": s.provider.value, "callable": False,
                         "error": f"{type(e).__name__}"})
    return callable_slots, rows


def _pick_generator_verifier(callable_slots, gen_id=None, ver_id=None):
    by_id = {s.model_id: s for s in callable_slots}
    if gen_id and gen_id in by_id:
        gen = by_id[gen_id]
    else:
        gen = min(callable_slots, key=lambda s: _TIER.get(getattr(s.tier, "value", str(s.tier)), 9))
    gfam = _family(gen.model_id)
    if ver_id and ver_id in by_id:
        ver = by_id[ver_id]
    else:
        ver = next((s for s in callable_slots if _family(s.model_id) != gfam), None)
    return gen, ver


def _resolve_pinned_slots(model_ids: list[str], *, timeout_s: int) -> tuple[list, list[dict]]:
    slots, probe_rows = [], []
    for model_id in model_ids:
        slot = _slot_for_id(model_id)
        ok = slot is not None and _probe(slot, timeout_s=timeout_s)
        probe_rows.append({"role": "mixed_moa", "model_id": model_id, "callable": ok})
        if ok:
            slots.append(slot)
    return slots, probe_rows


def _pick_mix_slots(callable_slots, gen, *, mix_ids: list[str] | None, timeout_s: int) -> tuple[list, list[dict]]:
    if mix_ids:
        slots, rows = _resolve_pinned_slots(mix_ids, timeout_s=timeout_s)
    else:
        rows = []
        slots = list(callable_slots)
    by_id = {s.model_id: s for s in slots}
    by_id.setdefault(gen.model_id, gen)
    slots = list(by_id.values())
    families, selected = set(), []
    for slot in sorted(slots, key=lambda s: _TIER.get(getattr(s.tier, "value", str(s.tier)), 9)):
        fam = _family(slot.model_id)
        if fam in families and len(selected) >= 2:
            continue
        families.add(fam)
        selected.append(slot)
        if len(selected) >= 4:
            break
    return selected, rows


def _pull_task_context(instance_id: str):
    if is_pr_suite_task_id(instance_id):
        return load_pr_suite_context(instance_id)
    return pull_context(instance_id)


def _grade_task(inst: dict, patch: str, *, timeout: int) -> tuple[bool, float, str | None]:
    if is_pr_suite_task(inst):
        result = grade_pr_suite_prediction(inst, patch, timeout=timeout)
        if result.error:
            return bool(result.resolved), result.seconds, f"{result.error}; receipt={result.receipt_path}"
        return bool(result.resolved), result.seconds, f"receipt={result.receipt_path}"
    return grade(inst, patch, timeout=timeout)


def run(instance_ids, *, n_explore, replicates, budget_cap, budget_usd, per_call_tokens, k_self_moa,
        grade_timeout, timeout_s, strategy, roster_n, gen_id, ver_id, label,
        arm="verify_chain", mix_ids: list[str] | None = None, window_chars: int | None = None):
    out = RUN_ROOT / f"{label}_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(out / "ledger.jsonl")
    parity = scaffold_parity_hash(GEN_TEMPLATE, SYNTH_TEMPLATE, VERIFY_TEMPLATE)
    context_window_chars = int(DEFAULT_WINDOW_CHARS if window_chars is None else window_chars)
    if context_window_chars <= 0:
        raise ValueError("window_chars must be positive")

    if arm not in {"verify_chain", "mixed_moa"}:
        raise ValueError(f"unknown Forge v2 arm: {arm}")

    # Reproducible fast path: walk the explicit recent-frontier ladder instead
    # of drawing a stochastic roster or silently downgrading to old workhorse
    # lanes. The old stochastic census is opt-in for experiments only.
    if gen_id or ver_id or os.environ.get("FORGE_ALLOW_STOCHASTIC_HIGH_SLOT") != "1":
        gen, ver, callable_slots, probe_rows = _resolve_high_slot_pair(
            gen_id,
            ver_id,
            timeout_s=timeout_s,
        )
        if gen_id and (gen is None or gen.model_id != gen_id):
            print(f"[forge_v2] generator {gen_id} not callable; trying recent-frontier fallback", flush=True)
        if ver_id and (ver is None or ver.model_id != ver_id):
            print(f"[forge_v2] verifier {ver_id} not callable; trying recent-frontier fallback", flush=True)
    else:
        print(f"[forge_v2] roster census (strategy={strategy}, n={roster_n}) ...", flush=True)
        callable_slots, probe_rows = _callable_roster(roster_n, strategy)
        gen, ver = _pick_generator_verifier(callable_slots, gen_id, ver_id)
    mix_slots: list = []
    if arm == "mixed_moa" and gen is not None:
        mix_slots, mix_probe_rows = _pick_mix_slots(callable_slots, gen, mix_ids=mix_ids, timeout_s=timeout_s)
        probe_rows.extend(mix_probe_rows)
        if len({_family(s.model_id) for s in mix_slots}) < 2:
            mix_slots = []

    needs_verifier = arm == "verify_chain"
    if gen is None or (needs_verifier and ver is None) or (arm == "mixed_moa" and not mix_slots):
        rr = RunReceipt(mission_class="verifier_role", timestamp=int(time.time()),
                        closeout="blocked_with_evidence",
                        arm=arm, class_null="self_moa", artifact_dir=str(out),
                        next_experiment="no callable cross-family model set inside the Forge "
                                        f"recent-frontier floor (min_release_date={FORGE_HIGH_SLOT_MIN_RELEASE_DATE}); "
                                        "restore a high-slot provider key or pin an explicit allowed route")
        (out / "decision_record.json").write_text(json.dumps(asdict(rr), indent=2, default=str))
        print("[forge_v2] BLOCKED: no callable cross-family model set.", flush=True)
        return asdict(rr)
    if arm == "verify_chain":
        selection_reasons = (f"arm=verify_chain; generator={gen.model_id} (strongest callable tier "
                             f"{getattr(gen.tier,'value',gen.tier)}); verifier={ver.model_id} "
                             f"(callable, family {_family(ver.model_id)} != generator family {_family(gen.model_id)}); "
                             f"context_window_chars={context_window_chars}; "
                             f"callable_roster={[s.model_id for s in callable_slots]}")
        print(f"[forge_v2] arm=verify_chain generator={gen.model_id}  verifier={ver.model_id}", flush=True)
    else:
        selection_reasons = (f"arm=mixed_moa; selector={gen.model_id}; mix_models="
                             f"{[s.model_id for s in mix_slots]} (cross-family diversity control); "
                             f"context_window_chars={context_window_chars}; "
                             f"callable_roster={[s.model_id for s in callable_slots]}")
        print(f"[forge_v2] arm=mixed_moa selector={gen.model_id}  models={[s.model_id for s in mix_slots]}", flush=True)

    explore, confirm = split_explore_confirm(instance_ids, n_explore)
    split_of = {**{i: "explore" for i in explore}, **{i: "confirm" for i in confirm}}

    attempts = []
    diffs = []                 # (verify_chain.resolved - self_moa.resolved) per (task,replicate)
    diffs_by_split = {"explore": [], "confirm": []}
    sm_rates, vc_rates = [], []
    any_invalid = False
    contamination_by_task = {}

    for iid in instance_ids:
        print(f"\n[forge_v2] instance {iid} (split={split_of[iid]})", flush=True)
        inst, ctx = _pull_task_context(iid)
        contamination = contamination_state(inst)
        contamination_by_task[iid] = contamination
        for r in range(replicates):
            # --- self_moa (class_null) ---
            b_sm = Budget(cap_tokens=budget_cap, cap_usd=budget_usd)
            t0 = time.time()
            sm = self_moa_arm(gen, inst, ctx, b_sm, k=k_self_moa, per_call_tokens=per_call_tokens,
                              timeout_s=timeout_s, window_chars=context_window_chars)
            b_sm.wall_seconds = time.time() - t0
            sm_resolved, sm_secs, sm_err = (False, 0.0, None)
            if sm["final_patch"].strip() and not b_sm.invalid:
                sm_resolved, sm_secs, sm_err = _grade_task(inst, sm["final_patch"], timeout=grade_timeout)
            # --- tested arm ---
            b_arm = Budget(cap_tokens=budget_cap, cap_usd=budget_usd)
            t0 = time.time()
            if arm == "verify_chain":
                arm_result = verify_chain_arm(gen, ver, inst, ctx, b_arm, per_call_tokens=per_call_tokens,
                                              timeout_s=timeout_s, window_chars=context_window_chars)
                arm_verifier = ver.model_id
            else:
                arm_result = mixed_moa_arm(mix_slots, gen, inst, ctx, b_arm, per_call_tokens=per_call_tokens,
                                           timeout_s=timeout_s, window_chars=context_window_chars)
                arm_verifier = None
            b_arm.wall_seconds = time.time() - t0
            arm_resolved, arm_secs, arm_err = (False, 0.0, None)
            if arm_result["final_patch"].strip() and not b_arm.invalid:
                arm_resolved, arm_secs, arm_err = _grade_task(inst, arm_result["final_patch"], timeout=grade_timeout)

            any_invalid = any_invalid or b_sm.invalid or b_arm.invalid
            for arm_name, slot_v, fp, res, secs, err, bud in [
                ("self_moa", None, sm["final_patch"], sm_resolved, sm_secs, sm_err, b_sm),
                (arm, arm_verifier, arm_result["final_patch"], arm_resolved, arm_secs, arm_err, b_arm),
            ]:
                rec = AttemptReceipt(
                    task_id=iid, mission_class="verifier_role", split=split_of[iid], arm=arm_name,
                    class_null="self_moa", replicate=r, generator=gen.model_id, verifier=slot_v,
                    selection_reasons=selection_reasons, scaffold_parity_hash=parity,
                    contamination_state=contamination, budget=bud.to_dict(), resolved=bool(res),
                    grade_seconds=round(secs, 1), grade_error=err, patch_len=len(fp),
                    invalid=bud.invalid, invalid_reason=bud.invalid_reason,
                )
                rid = ledger.append(rec)
                d = asdict(rec)
                d["_row_id"] = rid
                attempts.append(d)
            diff = (1.0 if arm_resolved else 0.0) - (1.0 if sm_resolved else 0.0)
            diffs.append(diff)
            diffs_by_split[split_of[iid]].append(diff)
            sm_rates.append(1.0 if sm_resolved else 0.0)
            vc_rates.append(1.0 if arm_resolved else 0.0)
            print(f"   rep {r}: self_moa={'PASS' if sm_resolved else 'fail'} "
                  f"{arm}={'PASS' if arm_resolved else 'fail'} "
                  f"(sm_tok={b_sm.spent} arm_tok={b_arm.spent})", flush=True)

    ci = paired_bootstrap_ci(diffs)
    split_contrasts = {name: paired_bootstrap_ci(vals) for name, vals in diffs_by_split.items()}
    var = {"self_moa": replicate_variance(sm_rates), "verify_chain": replicate_variance(vc_rates)}
    run_contamination = aggregate_contamination_states(contamination_by_task)

    # critic gate only on a POSITIVE interpretation
    critic = {"ran": False}
    positive_interpretation = positive_claim_gate(ci, split_contrasts)
    if positive_interpretation:
        claim = (f"{arm} beats its class_null self_moa on verifier_role "
                 f"(paired lift mean={ci['mean']}, CI lower={ci['lower']}, n={ci['n']})")
        critic = {"ran": True, **refute_pass(claim, {"ci": ci, "variance": var, "n_pairs": ci["n"],
                                                      "contamination": run_contamination},
                                          generator_family=_family(gen.model_id))}

    # closeout
    if any_invalid:
        closeout = "invalid_budget"
    elif run_contamination.get("state") == "contaminated_quarantine":
        closeout = "contaminated_quarantine"
    elif positive_interpretation and not critic.get("refuted_majority", True):
        closeout = "positive_lift_candidate"
    elif ci["upper"] < 0:
        closeout = "measured_negative"
    elif ci["n"] < 10:
        closeout = "inconclusive_low_power"
    elif ci["mean"] <= 0:
        closeout = "measured_negative"
    else:
        closeout = "inconclusive_low_power"

    if closeout == "positive_lift_candidate":
        nxt = ("CONFIRM the EXPLORE pocket on >=20 POST-CUTOFF held-out instances (contamination control), "
               "then ablate the winning arm's key variable under the same budget.")
    elif closeout == "measured_negative":
        nxt = (f"null (self_moa) survived against {arm}. Reallocate: run this arm ONLY on tasks where "
               "self_moa<1.0; rotate in mixed_moa if not tested; raise N for power.")
    elif closeout == "invalid_budget":
        nxt = "raise budget cap or lower per_call_tokens/k so both arms fit; re-run (this run is disqualified)."
    else:
        nxt = (f"under-powered (n={ci['n']}, CI width={round(ci['upper']-ci['lower'],3)}). Raise instances and "
               f"replicates until CI excludes 0, or accept measured_negative if mean stays <=0.")

    rr = RunReceipt(
        mission_class="verifier_role", arm=arm, class_null="self_moa",
        timestamp=int(time.time()), n_pairs=ci["n"], comparisons_count=1,
        contrast_vs_class_null=ci, split_contrasts=split_contrasts,
        replicate_variance=var, critic_verdict=critic,
        contamination_state=run_contamination,
        budget_matched_proof={"cap_tokens": budget_cap, "cap_usd": budget_usd, "any_invalid": any_invalid,
                              "window_chars": context_window_chars,
                              "self_moa_pass_rate": round(sum(sm_rates) / len(sm_rates), 3) if sm_rates else 0.0,
                              f"{arm}_pass_rate": round(sum(vc_rates) / len(vc_rates), 3) if vc_rates else 0.0,
                              "arm_pass_rate": round(sum(vc_rates) / len(vc_rates), 3) if vc_rates else 0.0},
        closeout=closeout, next_experiment=nxt, attempts=attempts,
        artifact_dir=str(out),
    )
    run_row = ledger.append(rr)
    rr.ledger_row_ids = [run_row]
    (out / "decision_record.json").write_text(json.dumps(asdict(rr), indent=2, default=str))
    (out / "roster_probe.json").write_text(json.dumps(probe_rows, indent=2))

    print(f"\n{'='*64}\n[forge_v2] DECISION RECORD", flush=True)
    print(f"  mission_class : verifier_role   arm={arm}  generator={gen.model_id}", flush=True)
    print(f"  pairs={ci['n']}  self_moa={rr.budget_matched_proof['self_moa_pass_rate']}  "
          f"{arm}={rr.budget_matched_proof['arm_pass_rate']}", flush=True)
    print(f"  lift ({arm} - self_moa): mean={ci['mean']}  CI=[{ci['lower']},{ci['upper']}]  p<=0={ci['p_le_0']}", flush=True)
    print(f"  critic: {critic.get('n_refuted','-')}/{critic.get('n_critics','-')} refuted" if critic.get("ran") else "  critic: not run (no positive)", flush=True)
    print(f"  contamination: {run_contamination.get('state')}", flush=True)
    print(f"  >>> CLOSEOUT: {closeout}", flush=True)
    print(f"  next_experiment: {nxt}", flush=True)
    print(f"  -> {out}/decision_record.json", flush=True)
    return asdict(rr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Forge v2 first slice: verifier_role self_moa vs verify_chain")
    ap.add_argument("--instances", required=True)
    ap.add_argument("--n-explore", type=int, default=3)
    ap.add_argument("--replicates", type=int, default=3)
    ap.add_argument("--budget", type=int, default=60000)
    ap.add_argument("--budget-usd", type=float, default=0.25)
    ap.add_argument("--per-call-tokens", type=int, default=6000)
    ap.add_argument("--k-self-moa", type=int, default=3)
    ap.add_argument("--grade-timeout", type=int, default=1200)
    ap.add_argument("--timeout-s", type=int, default=240)
    ap.add_argument("--strategy", default="explore")
    ap.add_argument("--roster-n", type=int, default=14)
    ap.add_argument("--generator", default=DEFAULT_FORGE_GENERATOR_MODEL, help="pin generator model id (reproducible)")
    ap.add_argument("--verifier", default=DEFAULT_FORGE_VERIFIER_MODEL, help="pin verifier model id (cross-family)")
    ap.add_argument("--arm", default="verify_chain", choices=["verify_chain", "mixed_moa"])
    ap.add_argument("--mix-models", default="", help="comma-separated pinned model ids for mixed_moa")
    ap.add_argument(
        "--window-chars",
        type=int,
        default=DEFAULT_WINDOW_CHARS,
        help="Track A context-window genome field, applied symmetrically to all arms",
    )
    ap.add_argument("--label", default="verifier_role")
    a = ap.parse_args(argv)
    ids = [x.strip() for x in a.instances.split(",") if x.strip()]
    mix_ids = [x.strip() for x in a.mix_models.split(",") if x.strip()]
    run(ids, n_explore=a.n_explore, replicates=a.replicates, budget_cap=a.budget,
        budget_usd=a.budget_usd,
        per_call_tokens=a.per_call_tokens, k_self_moa=a.k_self_moa, grade_timeout=a.grade_timeout,
        timeout_s=a.timeout_s, strategy=a.strategy, roster_n=a.roster_n, gen_id=a.generator,
        ver_id=a.verifier, label=a.label, arm=a.arm, mix_ids=mix_ids, window_chars=a.window_chars)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
