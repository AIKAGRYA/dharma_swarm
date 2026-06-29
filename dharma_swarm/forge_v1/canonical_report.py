"""Receipt/report helpers for Forge canonical runs."""
from __future__ import annotations

import json
from pathlib import Path


def _agg(manifest: dict) -> dict:
    per = manifest["per_instance"]
    n = len(per)
    arm_names = ["frontier_single_full_budget", "best_of_n_same_model", "same_budget_self_moa",
                 "swarm_union_verifier_gated", "planner_builder_verifier_no_a2a"]
    rates = {a: (sum(1 for p in per if p["arms"].get(a)) / n if n else 0.0) for a in arm_names}
    control_max = max(rates["frontier_single_full_budget"], rates["best_of_n_same_model"], rates["same_budget_self_moa"])
    swarm_best = max(rates["swarm_union_verifier_gated"], rates["planner_builder_verifier_no_a2a"])
    return {"n_instances": n, "arm_pass_rates": rates, "control_max": control_max,
            "swarm_best": swarm_best, "canonical_lift": swarm_best - control_max}


def _write_packet(out: Path, manifest: dict) -> None:
    agg = _agg(manifest)
    manifest["aggregate"] = agg
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    lines = ["# Control Comparison", "", f"instances: {agg['n_instances']}", ""]
    for a, r in agg["arm_pass_rates"].items():
        lines.append(f"- {a}: {r:.3f}")
    lines += ["", f"control_max = {agg['control_max']:.3f}", f"swarm_best = {agg['swarm_best']:.3f}",
              f"**canonical_lift = {agg['canonical_lift']:+.3f}**"]
    (out / "control_comparison.md").write_text("\n".join(lines))


def _finalize(out: Path, manifest: dict) -> None:
    agg = manifest.get("aggregate") or _agg(manifest)
    lift = agg["canonical_lift"]
    n = agg["n_instances"]
    if n < 100:
        closeout = "inconclusive_low_power" if lift <= 0 else "positive_lift_candidate"
    else:
        closeout = "positive_lift_candidate" if lift > 0 else "measured_negative"
    manifest["closeout"] = closeout
    dr = [f"# Decision Record", "", f"closeout: **{closeout}**",
          f"canonical_lift: {lift:+.3f}  (swarm_best {agg['swarm_best']:.3f} - control_max {agg['control_max']:.3f})",
          f"instances: {n}  (claim gate requires >=100 paired tasks; this is {'BELOW' if n<100 else 'at/above'} threshold)",
          "", "Arms run: frontier_single, best_of_n_same, self_moa, swarm_union, planner_builder_verifier_no_a2a.",
          "NOT YET run (next phase): full_a2a_swarm (real coordination spine), topology_variants, DarwinEngine cycles.",
          "Per claim gates, no public 'beats best single model' claim is licensed from this run."]
    (out / "decision_record.md").write_text("\n".join(dr))
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\n[canonical] DONE closeout={closeout} canonical_lift={lift:+.3f} -> {out}", flush=True)
