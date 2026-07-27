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
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
if str(WT) not in sys.path:
    sys.path.insert(0, str(WT))

from dharma_swarm.api_keys import bootstrap_runtime_env  # noqa: E402

bootstrap_runtime_env()

from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402
from dharma_swarm.forge_v1.autoloop import grade, pull_context  # noqa: E402
from .arms import (  # noqa: E402
    DEFAULT_WINDOW_CHARS,
    GEN_TEMPLATE,
    SYNTH_TEMPLATE,
    VERIFY_TEMPLATE,
    mixed_moa_arm,
    self_moa_arm,
    verify_chain_arm,
)
from .budget import Budget  # noqa: E402
from .critic import _family, refute_pass  # noqa: E402
from .pr_suite_grader import (  # noqa: E402
    grade_pr_suite_prediction,
    is_pr_suite_task,
    is_pr_suite_task_id,
    load_pr_suite_context,
)
from .provenance import aggregate_contamination_states, contamination_state, split_explore_confirm  # noqa: E402
from .receipts import AttemptReceipt, Ledger, RunReceipt, scaffold_parity_hash  # noqa: E402
from .stats import paired_bootstrap_ci, positive_claim_gate, replicate_variance  # noqa: E402

RUN_ROOT = dharma_state_dir() / "forge_v1" / "forge_v2"
from .runner_slots import (  # noqa: E402
    DEFAULT_FORGE_GENERATOR_MODEL,
    DEFAULT_FORGE_VERIFIER_MODEL,
    FORGE_HIGH_SLOT_MIN_RELEASE_DATE,
    _callable_roster,
    _pick_generator_verifier,
    _pick_mix_slots,
    _resolve_high_slot_pair,
)

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
