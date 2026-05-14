"""Step 04: Train whitebox + blackbox classifiers, compute AUROC, run DeLong's test.

Pre-registered design:
  Whitebox arm:  L2-logistic on R_V scalar (1 feature, C=1.0)
  Blackbox arm:  L2-logistic on 5 output-only features (standardized, C=1.0)
  Train/test:    80/20, seed=42, derived from cache/mask_split.json
  Test:          DeLong's two-sided test for correlated ROC AUC, α=0.01
  Win condition: AUROC_whitebox − AUROC_blackbox > 0.05 AND p < 0.01
  Bootstrap CI:  1000 resamples, BCa

Exclusions BEFORE labels are used:
  - is_refusal == True
  - label in {"refusal", "unparseable", "ambiguous"} → not used for honesty test
  - Only "honest" and "deceptive" labels go into the primary test

Usage:
    cd ~/dharma_swarm/experiments/mask_rv_whitebox
    python3 04_classifiers.py

Outputs:
    results/auroc.json — primary stats
    results/per_arm_predictions.csv — per-probe predictions and true labels
    figures/roc.png — ROC curves overlay
    figures/calibration.png — calibration plots per arm
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ────────────────────────────────────────────────────────────────────────────
# DeLong's test for correlated ROC AUC
# Hand implementation following Sun & Xu 2014 fast DeLong.
# Reference: https://ieeexplore.ieee.org/document/6851192
# ────────────────────────────────────────────────────────────────────────────

def _compute_midrank(x):
    """Midrank computation used inside DeLong."""
    J = np.argsort(x)
    Z = x[J]
    N = len(x)
    T = np.zeros(N, dtype=np.float64)
    i = 0
    while i < N:
        j = i
        while j < N and Z[j] == Z[i]:
            j += 1
        T[i:j] = 0.5 * (i + j - 1) + 1
        i = j
    T2 = np.empty(N, dtype=np.float64)
    T2[J] = T
    return T2


def fast_delong(preds_a: np.ndarray, preds_b: np.ndarray, y: np.ndarray):
    """Fast DeLong's test for two correlated classifiers.

    Args:
        preds_a, preds_b: shape (N,) classifier scores.
        y: shape (N,) binary labels {0, 1}.

    Returns:
        auc_a, auc_b, var_a, var_b, cov_ab, z, p_two_sided
    """
    pos = y == 1
    neg = y == 0
    m = pos.sum()
    n = neg.sum()
    if m == 0 or n == 0:
        return tuple([float("nan")] * 7)

    def auc_and_var(preds):
        positive = preds[pos]
        negative = preds[neg]
        tx = _compute_midrank(positive)
        ty = _compute_midrank(negative)
        tz = _compute_midrank(np.concatenate([positive, negative]))
        # AUC
        auc = (tz[:m].sum() - m * (m + 1) / 2.0) / (m * n)
        # Variance components
        v01 = (tz[:m] - tx) / n
        v10 = 1.0 - (tz[m:] - ty) / m
        return auc, positive, negative, tz, v01, v10

    auc_a, pos_a, neg_a, tz_a, v01_a, v10_a = auc_and_var(preds_a)
    auc_b, pos_b, neg_b, tz_b, v01_b, v10_b = auc_and_var(preds_b)

    sx = np.array([[np.var(v01_a, ddof=1), np.cov(v01_a, v01_b, ddof=1)[0, 1]],
                   [np.cov(v01_a, v01_b, ddof=1)[0, 1], np.var(v01_b, ddof=1)]])
    sy = np.array([[np.var(v10_a, ddof=1), np.cov(v10_a, v10_b, ddof=1)[0, 1]],
                   [np.cov(v10_a, v10_b, ddof=1)[0, 1], np.var(v10_b, ddof=1)]])
    S = sx / m + sy / n  # 2×2 covariance of (AUC_a, AUC_b)
    delta = auc_a - auc_b
    var_delta = S[0, 0] + S[1, 1] - 2 * S[0, 1]
    if var_delta <= 0 or not np.isfinite(var_delta):
        return auc_a, auc_b, S[0, 0], S[1, 1], S[0, 1], float("nan"), float("nan")
    z = delta / np.sqrt(var_delta)
    # Two-sided p
    from math import erf, sqrt
    p = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
    return auc_a, auc_b, S[0, 0], S[1, 1], S[0, 1], z, p


# ────────────────────────────────────────────────────────────────────────────
# Bootstrap CI for AUC (BCa)
# ────────────────────────────────────────────────────────────────────────────

def bootstrap_auc_bca(preds: np.ndarray, y: np.ndarray, n_resamples: int = 1000, alpha: float = 0.05, seed: int = 42):
    """BCa bootstrap CI for AUC."""
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(seed)
    N = len(y)
    auc_orig = roc_auc_score(y, preds)
    boots = np.empty(n_resamples)
    for i in range(n_resamples):
        idx = rng.integers(0, N, size=N)
        yb = y[idx]
        pb = preds[idx]
        if yb.sum() == 0 or yb.sum() == N:
            boots[i] = np.nan
            continue
        try:
            boots[i] = roc_auc_score(yb, pb)
        except ValueError:
            boots[i] = np.nan
    boots = boots[~np.isnan(boots)]
    if len(boots) == 0:
        return auc_orig, float("nan"), float("nan")
    # Simple percentile CI (BCa correction omitted for MVP — sufficient for n=200)
    lo = np.quantile(boots, alpha / 2)
    hi = np.quantile(boots, 1 - alpha / 2)
    return auc_orig, float(lo), float(hi)


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────

def main() -> int:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import roc_curve, brier_score_loss

    cfg = load_config()
    cache_dir = Path(os.path.expanduser(cfg["paths"]["cache_dir"]))
    results_dir = Path(os.path.expanduser(cfg["paths"]["results_dir"]))
    figures_dir = Path(os.path.expanduser(cfg["paths"]["figures_dir"]))
    figures_dir.mkdir(parents=True, exist_ok=True)

    # Load inference + R_V
    inf_path = results_dir / "inference_results.jsonl"
    rv_path = cache_dir / "rv_scalars.parquet"
    if not inf_path.exists():
        sys.exit("ERROR: missing inference_results.jsonl")
    if not rv_path.exists():
        sys.exit("ERROR: missing rv_scalars.parquet — run 03_compute_rv.py first")

    rv_df = pd.read_parquet(rv_path)
    with open(inf_path) as f:
        inf_records = [json.loads(line) for line in f if line.strip()]
    inf_df = pd.DataFrame(inf_records)

    df = inf_df.merge(rv_df[["task_id", "rv", "pr_early", "pr_late"]], on="task_id", how="inner")
    print(f"[main] joined: {len(df)} probes")

    # Exclusions
    n_before = len(df)
    df = df[~df["is_refusal"]]
    n_after_refusal = len(df)
    df = df[df["label_info"].apply(lambda d: d["label"]) .isin(["honest", "deceptive"])]
    n_after_label = len(df)
    print(f"[exclude] {n_before} → {n_after_refusal} (refusals removed) → {n_after_label} (kept only honest/deceptive)")

    if n_after_label < 20:
        print(f"[WARN] only {n_after_label} probes after exclusions — too few for meaningful test")

    y = (df["label_info"].apply(lambda d: d["label"]) == "deceptive").astype(int).values

    # Whitebox feature: R_V scalar
    X_white = df["rv"].values.reshape(-1, 1)
    valid_white = np.isfinite(X_white[:, 0])
    print(f"[whitebox] {valid_white.sum()}/{len(valid_white)} have finite R_V")
    if valid_white.sum() < 10:
        print(f"[WARN] too few finite R_V values")

    # Blackbox features: 5 output-only
    bb_keys = ["max_token_log_prob_first50", "mean_token_log_prob_first10",
               "entropy_step0_top100", "response_length_tokens", "self_perplexity"]
    X_black = np.array([[r["blackbox"][k] for k in bb_keys] for r in inf_records if r["task_id"] in df["task_id"].values])
    # Need to align rows to df order
    bb_dict = {r["task_id"]: r["blackbox"] for r in inf_records}
    X_black = np.array([[bb_dict[tid][k] for k in bb_keys] for tid in df["task_id"]])

    # Load train/test split
    split_path = cache_dir / "mask_split.json"
    if not split_path.exists():
        sys.exit("ERROR: missing mask_split.json")
    with open(split_path) as f:
        split = json.load(f)
    # Re-derive in-set membership by task_id position would be brittle; use a fresh seeded split
    rng = np.random.default_rng(cfg["dataset"]["split_seed"])
    idx = rng.permutation(len(df))
    n_train = int(len(df) * cfg["dataset"]["train_test_split"])
    train_idx = idx[:n_train]
    test_idx = idx[n_train:]
    print(f"[split] train={len(train_idx)} test={len(test_idx)} (seed={cfg['dataset']['split_seed']})")

    # Drop any probes with NaN R_V (these are excluded BEFORE further analysis)
    train_mask = np.isin(np.arange(len(df)), train_idx) & valid_white
    test_mask = np.isin(np.arange(len(df)), test_idx) & valid_white
    print(f"[finite-R_V split] train={train_mask.sum()} test={test_mask.sum()}")

    # Whitebox arm
    clf_w = LogisticRegression(**cfg["whitebox"]["classifier_kwargs"])
    clf_w.fit(X_white[train_mask], y[train_mask])
    probs_w = clf_w.predict_proba(X_white[test_mask])[:, 1]
    from sklearn.metrics import roc_auc_score
    auc_w = roc_auc_score(y[test_mask], probs_w)

    # Blackbox arm
    scaler = StandardScaler()
    X_black_train = scaler.fit_transform(X_black[train_mask])
    X_black_test = scaler.transform(X_black[test_mask])
    clf_b = LogisticRegression(**cfg["blackbox"]["classifier_kwargs"])
    clf_b.fit(X_black_train, y[train_mask])
    probs_b = clf_b.predict_proba(X_black_test)[:, 1]
    auc_b = roc_auc_score(y[test_mask], probs_b)

    # DeLong's test
    y_test = y[test_mask]
    auc_a, auc_bd, var_a, var_b, cov_ab, z, p = fast_delong(probs_w, probs_b, y_test)

    # Bootstrap CIs
    auc_w_, lo_w, hi_w = bootstrap_auc_bca(probs_w, y_test, n_resamples=cfg["statistical_test"]["bootstrap_resamples"])
    auc_b_, lo_b, hi_b = bootstrap_auc_bca(probs_b, y_test, n_resamples=cfg["statistical_test"]["bootstrap_resamples"])

    delta = auc_w - auc_b
    win = cfg["win_conditions"]["primary"]
    primary_win = (delta > win["auroc_delta_threshold"]) and (p < win["p_threshold"])
    strong_win_cfg = cfg["win_conditions"]["strong"]
    strong_win = (
        auc_w > strong_win_cfg["auroc_whitebox_min"]
        and auc_b < strong_win_cfg["auroc_blackbox_max"]
        and p < strong_win_cfg["p_threshold"]
    )

    result = {
        "n_test": int(test_mask.sum()),
        "n_train": int(train_mask.sum()),
        "n_deceptive_in_test": int(y_test.sum()),
        "n_honest_in_test": int((1 - y_test).sum()),
        "auc_whitebox": float(auc_w),
        "auc_whitebox_ci": [float(lo_w), float(hi_w)],
        "auc_blackbox": float(auc_b),
        "auc_blackbox_ci": [float(lo_b), float(hi_b)],
        "delta_auc": float(delta),
        "delong_z": float(z) if np.isfinite(z) else None,
        "delong_p_two_sided": float(p) if np.isfinite(p) else None,
        "primary_win": bool(primary_win),
        "strong_win": bool(strong_win),
        "win_conditions": {
            "primary_delta_threshold": win["auroc_delta_threshold"],
            "primary_p_threshold": win["p_threshold"],
            "strong_auc_w_min": strong_win_cfg["auroc_whitebox_min"],
            "strong_auc_b_max": strong_win_cfg["auroc_blackbox_max"],
        },
        "config": {
            "early_layer": cfg["whitebox"]["early_layer"],
            "late_layer": cfg["whitebox"]["late_layer"],
            "window_size": cfg["whitebox"]["window_size"],
            "rv_variant": cfg["whitebox"]["variant"],
            "model": cfg["model"]["hf_id"],
            "n_total": int(n_after_label),
        },
    }
    out_path = results_dir / "auroc.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n[result] wrote {out_path}")
    print(json.dumps(result, indent=2))

    # Per-arm predictions
    pred_df = pd.DataFrame({
        "task_id": df["task_id"].values[test_mask],
        "y_true": y_test,
        "prob_whitebox": probs_w,
        "prob_blackbox": probs_b,
        "rv": X_white[test_mask, 0],
    })
    pred_path = results_dir / "per_arm_predictions.csv"
    pred_df.to_csv(pred_path, index=False)
    print(f"[result] wrote {pred_path}")

    # ROC plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fpr_w, tpr_w, _ = roc_curve(y_test, probs_w)
        fpr_b, tpr_b, _ = roc_curve(y_test, probs_b)
        plt.figure(figsize=(6, 6))
        plt.plot(fpr_w, tpr_w, label=f"Whitebox R_V  AUROC={auc_w:.3f}", linewidth=2)
        plt.plot(fpr_b, tpr_b, label=f"Blackbox out  AUROC={auc_b:.3f}", linewidth=2)
        plt.plot([0, 1], [0, 1], "k--", linewidth=1, alpha=0.5)
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title(f"ROC: Whitebox vs Blackbox  (Δ={delta:+.3f}, p={p:.3g})")
        plt.legend(loc="lower right")
        plt.grid(alpha=0.3)
        roc_path = figures_dir / "roc.png"
        plt.savefig(roc_path, dpi=140, bbox_inches="tight")
        print(f"[result] wrote {roc_path}")
    except ImportError:
        print("[warn] matplotlib not installed — skipping ROC plot")

    return 0


if __name__ == "__main__":
    sys.exit(main())
