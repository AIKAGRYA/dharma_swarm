"""Step 01: Load CAIS MASK dataset, verify access, stratify, split.

Run AFTER clicking 'Agree and access repository' at https://huggingface.co/datasets/cais/MASK.
This script is the first verification gate — if access isn't granted, this errors clearly
and tells you what to do.

Usage:
    cd ~/dharma_swarm/experiments/mask_rv_whitebox
    python3 01_load_mask.py

Outputs:
    cache/mask_raw.parquet — full downloaded MASK dataset
    cache/mask_stratified.json — stratified n=200 (or whatever target_n is in config)
    cache/mask_split.json — train/test indices, seeded

Pre-registration: cabinet/research/preregistrations/2026-05-14_mask_rv_whitebox_vs_blackbox.md
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import yaml


SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def ensure_dirs(cfg: dict) -> None:
    for key in ("cache_dir", "results_dir", "figures_dir"):
        p = Path(os.path.expanduser(cfg["paths"][key]))
        p.mkdir(parents=True, exist_ok=True)


def verify_hf_access(cfg: dict) -> None:
    """Cheap auth probe — fails clearly if access isn't granted yet."""
    import requests

    token = os.environ.get("HF_TOKEN")
    if not token:
        token_path = Path.home() / ".cache" / "huggingface" / "token"
        if token_path.exists():
            token = token_path.read_text().strip()
    if not token:
        sys.exit("ERROR: HF_TOKEN not set in env and ~/.cache/huggingface/token not found.")

    hf_id = cfg["dataset"]["hf_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Metadata API (different host prefix)
    meta_url = f"https://huggingface.co/api/datasets/{hf_id}"
    r = requests.get(meta_url, headers=headers)
    if r.status_code != 200:
        sys.exit(f"ERROR: metadata API returned HTTP {r.status_code} for {hf_id}")
    meta = r.json()
    print(f"[OK] Metadata reachable: gated={meta.get('gated')}, downloads={meta.get('downloads')}")

    # README file (resolve endpoint)
    readme_url = f"https://huggingface.co/datasets/{hf_id}/resolve/main/README.md"
    r = requests.head(readme_url, headers=headers, allow_redirects=True)
    if r.status_code == 200:
        print(f"[OK] README file readable")
    else:
        print(f"[WARN] README HEAD returned HTTP {r.status_code} (non-fatal; continuing)")

    # Probe an actual data file — this is the real gating test
    probe_url = f"https://huggingface.co/datasets/{hf_id}/resolve/main/continuations/test-00000-of-00001.parquet"
    r = requests.head(probe_url, headers=headers, allow_redirects=True)
    if r.status_code == 200:
        print(f"[OK] Data files accessible — gating cleared.")
    else:
        print(f"[BLOCKED] HTTP {r.status_code} on parquet. Visit:")
        print(f"    https://huggingface.co/datasets/{hf_id}")
        print("    and click 'Agree and access repository'.")
        sys.exit(1)


def download_and_stratify(cfg: dict) -> None:
    from datasets import load_dataset
    import pandas as pd

    hf_id = cfg["dataset"]["hf_id"]
    cache_dir = Path(os.path.expanduser(cfg["paths"]["cache_dir"]))

    # MASK has 6 configs (= "6 archetypes" per the dataset card)
    MASK_CONFIGS = [
        "continuations",
        "disinformation",
        "doubling_down_known_facts",
        "known_facts",
        "provided_facts",
        "statistics",
    ]

    print(f"\n[01] Downloading {hf_id} ({len(MASK_CONFIGS)} configs)...")
    frames = []
    for cfg_name in MASK_CONFIGS:
        try:
            ds = load_dataset(hf_id, cfg_name)
            split = next(iter(ds.keys()))  # usually 'test'
            sub = ds[split].to_pandas()
            sub["_config"] = cfg_name  # stratification axis = the archetype
            sub["_orig_split"] = split
            frames.append(sub)
            print(f"     {cfg_name}: {len(sub)} rows; cols: {list(sub.columns)}")
        except Exception as e:
            print(f"     [WARN] {cfg_name} failed: {type(e).__name__}: {str(e)[:120]}")
    if not frames:
        sys.exit("ERROR: no MASK configs loaded.")

    # Union — handles column-set differences across configs
    df = pd.concat(frames, ignore_index=True, sort=False)
    print(f"\n[02] Combined: n={len(df)}; union cols: {list(df.columns)}")

    # Save raw
    raw_path = cache_dir / "mask_raw.parquet"
    df.to_parquet(raw_path)
    print(f"     wrote {raw_path}")

    # Stratify by config (= archetype). Override stratify_by in config.yaml when archetype isn't a column.
    stratify_col = cfg["dataset"]["stratify_by"]
    if stratify_col not in df.columns and stratify_col == "archetype":
        print(f"\n[03] Stratify column 'archetype' not present; falling back to '_config' (the 6 MASK archetypes are the 6 HF configs).")
        stratify_col = "_config"
    target_n = cfg["dataset"]["target_n"]
    if stratify_col not in df.columns:
        print(f"\n[WARN] stratify column '{stratify_col}' not found.")
        print(f"       Available columns: {list(df.columns)}")
        print(f"       Falling back to uniform random sample.")
        sample = df.sample(n=min(target_n, len(df)), random_state=cfg["dataset"]["split_seed"])
    else:
        groups = df.groupby(stratify_col)
        per_group = max(1, target_n // len(groups))
        parts = []
        for name, g in groups:
            parts.append(g.sample(n=min(per_group, len(g)), random_state=cfg["dataset"]["split_seed"]))
        sample = pd.concat(parts, ignore_index=True)
        print(f"\n[04] Stratified by '{stratify_col}': {len(groups)} groups, ~{per_group} per group")
        print(f"     groups: {list(groups.groups.keys())}")
        print(f"     per-group sampled: {sample.groupby(stratify_col).size().to_dict()}")

    print(f"     final stratified n={len(sample)}")

    # Save stratified
    strat_path = cache_dir / "mask_stratified.parquet"
    sample.to_parquet(strat_path)
    print(f"     wrote {strat_path}")

    # Train/test split (seeded)
    import numpy as np
    rng = np.random.default_rng(cfg["dataset"]["split_seed"])
    n = len(sample)
    indices = rng.permutation(n)
    n_train = int(n * cfg["dataset"]["train_test_split"])
    train_idx = indices[:n_train].tolist()
    test_idx = indices[n_train:].tolist()
    split = {"train_idx": train_idx, "test_idx": test_idx, "n_train": n_train, "n_test": n - n_train, "seed": cfg["dataset"]["split_seed"]}
    split_path = cache_dir / "mask_split.json"
    with open(split_path, "w") as f:
        json.dump(split, f, indent=2)
    print(f"\n[05] Train/test split (seed={cfg['dataset']['split_seed']}): train={n_train}, test={n - n_train}")
    print(f"     wrote {split_path}")


def main() -> int:
    cfg = load_config()
    print(f"=== MASK Whitebox-vs-Blackbox: Step 01 — Load Dataset ===")
    print(f"Config: {CONFIG_PATH}")
    print(f"Pre-reg: {cfg['experiment']['preregistration']}")
    print(f"Lock status: {cfg['experiment']['prereg_lock_status']}")
    print()

    ensure_dirs(cfg)
    verify_hf_access(cfg)
    download_and_stratify(cfg)

    print("\n[DONE] Step 01 complete. Next: run 02_run_inference.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
