"""Step 03: Compute R_V scalars from cached activations.

For each probe:
  1. Load h_early (window × hidden) and h_late (window × hidden) from npz
  2. Compute Participation Ratio (PR) at each layer
  3. R_V = PR_late / PR_early

PR definition (per geometric_lens/metrics.py):
  PR = (Σλᵢ²)² / Σ(λᵢ²)²
  where λᵢ are singular values from SVD of the (window × hidden) slab,
  transposed and SVD'd in float64 for numerical stability.

R_V < 1 = contraction (late layer is lower-dim than early)
R_V > 1 = expansion

Usage:
    cd ~/dharma_swarm/experiments/mask_rv_whitebox
    python3 03_compute_rv.py

Outputs:
    cache/rv_scalars.parquet — per-probe (task_id, rv, pr_early, pr_late, label)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import yaml


SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def participation_ratio(activations: np.ndarray, window_size: int = 16) -> float:
    """Participation Ratio: PR = (Σλᵢ²)² / Σ(λᵢ²)².

    Faithful re-implementation of geometric_lens/metrics.py:participation_ratio.
    SVD computed in float64 for numerical stability. Returns NaN on degenerate input.

    Args:
        activations: shape (T, D) where T is tokens, D is hidden.
        window_size: number of trailing tokens to use.

    Returns:
        PR scalar (float). NaN on failure or degenerate input.
    """
    if activations is None:
        return float("nan")
    if activations.ndim == 3:
        activations = activations[0]
    if activations.ndim != 2:
        return float("nan")

    T, D = activations.shape
    if T < window_size:
        return float("nan")

    W = min(window_size, T)
    v = activations[-W:, :].astype(np.float64)

    if not np.isfinite(v).all():
        return float("nan")

    try:
        # SVD on v.T (D × W), get singular values
        # NOTE: SVD of (D × W) and (W × D) give same singular values
        U, S, Vt = np.linalg.svd(v.T, full_matrices=False)
    except np.linalg.LinAlgError:
        return float("nan")

    S_sq = S ** 2
    total = S_sq.sum()
    if total < 1e-10:
        return float("nan")

    pr = (S_sq.sum() ** 2) / (S_sq ** 2).sum()
    return float(pr)


def main() -> int:
    import pandas as pd

    cfg = load_config()
    cache_dir = Path(os.path.expanduser(cfg["paths"]["cache_dir"]))
    results_dir = Path(os.path.expanduser(cfg["paths"]["results_dir"]))
    inference_path = results_dir / "inference_results.jsonl"
    if not inference_path.exists():
        sys.exit(f"ERROR: {inference_path} missing — run 02_run_inference.py first.")

    window_size = cfg["whitebox"]["window_size"]
    early_layer = cfg["whitebox"]["early_layer"]
    late_layer = cfg["whitebox"]["late_layer"]
    print(f"[main] R_V_residual: early=L{early_layer}, late=L{late_layer}, window={window_size}")

    rows = []
    with open(inference_path) as f:
        records = [json.loads(line) for line in f if line.strip()]
    print(f"[main] loaded {len(records)} inference results from {inference_path}")

    n_nan_pr_early = 0
    n_nan_pr_late = 0
    for rec in records:
        npz_path = rec["activations_npz"]
        try:
            d = np.load(npz_path)
            h_early = d["h_early"]
            h_late = d["h_late"]
        except Exception as e:
            print(f"[err] {rec['task_id']}: failed to load {npz_path}: {e}")
            continue

        pr_early = participation_ratio(h_early, window_size=window_size)
        pr_late = participation_ratio(h_late, window_size=window_size)
        if np.isnan(pr_early):
            n_nan_pr_early += 1
        if np.isnan(pr_late):
            n_nan_pr_late += 1
        rv = pr_late / pr_early if (pr_early > 0 and np.isfinite(pr_early) and np.isfinite(pr_late)) else float("nan")

        rows.append({
            "task_id": rec["task_id"],
            "config": rec["config"],
            "type": rec.get("type"),
            "rv": rv,
            "pr_early": pr_early,
            "pr_late": pr_late,
            "label": rec["label_info"]["label"],
            "is_refusal": rec["is_refusal"],
        })

    df = pd.DataFrame(rows)
    out_path = cache_dir / "rv_scalars.parquet"
    df.to_parquet(out_path)
    print(f"[main] wrote {out_path}")
    print(f"[main] R_V distribution:")
    print(df["rv"].describe().to_string())
    print(f"[main] NaN counts: pr_early={n_nan_pr_early}, pr_late={n_nan_pr_late}")
    print(f"[main] R_V mean by label: {df.groupby('label')['rv'].mean().to_dict()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
