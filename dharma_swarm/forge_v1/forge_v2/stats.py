"""Statistical discipline (contract invariant 2 + F2 garden-of-forking-paths).

Paired bootstrap CI of (arm - class_null) over tasks x replicates; the headline
claim is the CI lower bound, not the raw mean. Benjamini-Hochberg FDR is provided
so that when MULTIPLE pockets are tested across the curve, significance is
corrected — the autoresearch loop cannot manufacture a winner by trying enough
arm x class cells.
"""
from __future__ import annotations

import random


def paired_bootstrap_ci(diffs: list[float], *, samples: int = 2000, seed: int = 0,
                        alpha: float = 0.05) -> dict:
    """Bootstrap the paired per-pair lift distribution. Each element is one
    (task,replicate)'s (arm - class_null). Pairing preserves task difficulty."""
    n = len(diffs)
    if n == 0:
        return {"n": 0, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0}
    mean = sum(diffs) / n
    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        draw = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(draw) / n)
    means.sort()
    lo_i = max(0, min(samples - 1, int((alpha / 2) * samples)))
    hi_i = max(0, min(samples - 1, int((1 - alpha / 2) * samples)))
    # one-sided bootstrap p for H0: mean <= 0
    p_le_0 = sum(1 for m in means if m <= 0) / samples
    return {"n": n, "mean": round(mean, 4), "lower": round(means[lo_i], 4),
            "upper": round(means[hi_i], 4), "p_le_0": round(p_le_0, 4)}


def benjamini_hochberg(pvals: list[float], alpha: float = 0.05) -> list[bool]:
    """FDR: return per-pvalue significance under BH. Use across all arm x class
    contrasts tested in a campaign so the curve can't be p-hacked."""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    thresh_rank = 0
    for rank, i in enumerate(order, start=1):
        if pvals[i] <= (rank / m) * alpha:
            thresh_rank = rank
    sig = [False] * m
    for rank, i in enumerate(order, start=1):
        sig[i] = rank <= thresh_rank
    return sig


def replicate_variance(values: list[float]) -> dict:
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": 0.0, "var": 0.0, "std": 0.0}
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return {"n": n, "mean": round(mean, 4), "var": round(var, 5), "std": round(var ** 0.5, 4)}


def positive_claim_gate(overall_ci: dict, split_contrasts: dict) -> bool:
    """A lift claim must clear the overall paired CI and the frozen CONFIRM
    split. EXPLORE-only pockets are hypotheses, not promoted claims."""
    confirm = split_contrasts.get("confirm", {})
    return (
        overall_ci.get("mean", 0.0) > 0
        and overall_ci.get("lower", 0.0) > 0
        and confirm.get("n", 0) > 0
        and confirm.get("mean", 0.0) > 0
        and confirm.get("lower", 0.0) > 0
    )
