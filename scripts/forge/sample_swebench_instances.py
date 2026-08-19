#!/usr/bin/env python3
"""Pre-registered, seeded, stratified sampler for SWE-bench-Verified instances.

Produces the FROZEN instance list + sampling receipt for the 50-instance
swarm-vs-single benchmark (yes-sheet 2026-08-18 row 1). The sample is
stratified jointly by repository and by gold-patch size bucket so it cannot be
cherry-picked toward easy repos or tiny patches, and it is fully deterministic
given ``--seed``. The receipt JSON records seed, strata populations, quotas,
dataset identity, and the frozen EXPLORE/CONFIRM split (via
``forge_v2.provenance.split_explore_confirm``); commit the receipt BEFORE any
benchmark run so the pre-registration is on record.

Offline contract: with ``--listing`` this needs no network and no ``datasets``
import. Without ``--listing`` it tries the HF ``datasets`` library; if that is
unavailable it prints fetch instructions and exits 3 — it NEVER fabricates a
sample.

Usage
-----
    # On a box with the dataset available (network or HF cache):
    python3 scripts/forge/sample_swebench_instances.py \
        --n 50 --n-explore 20 --seed 20260819 \
        --dump-listing reports/governance/forge_benchmark/swebench_verified_listing.json

    # Fully offline, from a previously dumped listing:
    python3 scripts/forge/sample_swebench_instances.py \
        --n 50 --n-explore 20 --seed 20260819 \
        --listing reports/governance/forge_benchmark/swebench_verified_listing.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.forge_v1.forge_v2.provenance import split_explore_confirm  # noqa: E402
from dharma_swarm.forge_v1.swebench_real import DATASET_NAME, SPLIT  # noqa: E402

SCHEMA_VERSION = 1

# Gold-patch size buckets, by changed (added+removed) diff lines. Thresholds
# are frozen here and copied into every receipt so a later edit is visible.
SIZE_BUCKETS = (("S", 10), ("M", 40), ("L", None))  # S: <=10, M: 11..40, L: >40

DEFAULT_OUT_DIR = REPO_ROOT / "reports" / "governance" / "forge_benchmark"

FETCH_INSTRUCTIONS = """\
Cannot sample: the `datasets` library is unavailable and no --listing file was
given. This sampler NEVER fabricates instance ids. To proceed, either:
  1) pip install datasets            # then re-run this command; or
  2) on any connected machine run:
       python3 scripts/forge/sample_swebench_instances.py \\
           --n 50 --seed <seed> --dump-listing swebench_verified_listing.json
     copy the listing JSON here, and re-run with --listing <path>.
"""


class DatasetUnavailable(RuntimeError):
    """Raised when neither --listing nor the `datasets` library can supply rows."""


# --------------------------------------------------------------------------- #
# pure sampling machinery (hermetically testable)
# --------------------------------------------------------------------------- #
def changed_lines(diff_text: str) -> int:
    """Count added+removed lines in a unified diff, excluding file headers."""
    n = 0
    for line in (diff_text or "").splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") or line.startswith("-"):
            n += 1
    return n


def size_bucket(n_changed: int) -> str:
    """Bucket a changed-line count using the frozen SIZE_BUCKETS thresholds."""
    for name, upper in SIZE_BUCKETS:
        if upper is None or n_changed <= upper:
            return name
    raise AssertionError("SIZE_BUCKETS must end with an unbounded bucket")


def allocate_quotas(populations: dict[tuple[str, str], int], n: int) -> dict[tuple[str, str], int]:
    """Proportional stratum quotas summing to ``n`` (largest-remainder method,
    deterministic tie-break on stratum key). A quota never exceeds its stratum
    population; any overflow re-distributes to the remaining strata."""
    total = sum(populations.values())
    if total <= 0:
        return {k: 0 for k in populations}
    if n >= total:
        return dict(populations)
    keys = sorted(populations)
    quotas = {k: 0 for k in keys}
    remaining_n = n
    open_keys = [k for k in keys if populations[k] > 0]
    # Iterate because capping a quota at its population frees remainder that
    # must flow to other strata; each pass either finishes or closes a stratum.
    while remaining_n > 0 and open_keys:
        open_total = sum(populations[k] - quotas[k] for k in open_keys)
        if open_total <= 0:
            break
        shares = {
            k: remaining_n * (populations[k] - quotas[k]) / open_total for k in open_keys
        }
        base = {k: int(shares[k]) for k in open_keys}
        leftover = remaining_n - sum(base.values())
        by_frac = sorted(open_keys, key=lambda k: (-(shares[k] - base[k]), k))
        for k in by_frac[:leftover]:
            base[k] += 1
        progressed = False
        for k in open_keys:
            take = min(base[k], populations[k] - quotas[k])
            if take > 0:
                quotas[k] += take
                remaining_n -= take
                progressed = True
        open_keys = [k for k in open_keys if quotas[k] < populations[k]]
        if not progressed:
            break
    return quotas


def stratified_sample(
    rows: list[dict], n: int, seed: int
) -> tuple[list[str], list[dict]]:
    """Deterministic stratified sample of ``n`` instance ids from ``rows``
    (each row: instance_id, repo, patch_changed_lines). Returns the frozen
    ordered id list and the strata table for the receipt."""
    strata: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        key = (str(row["repo"]), size_bucket(int(row["patch_changed_lines"])))
        strata.setdefault(key, []).append(str(row["instance_id"]))
    populations = {k: len(v) for k, v in strata.items()}
    quotas = allocate_quotas(populations, n)

    sampled: list[str] = []
    table: list[dict] = []
    for key in sorted(strata):
        repo, bucket = key
        pool = sorted(strata[key])
        rng = random.Random(f"{seed}:{repo}:{bucket}")
        picked = sorted(rng.sample(pool, quotas[key])) if quotas[key] else []
        sampled.extend(picked)
        table.append(
            {
                "repo": repo,
                "size_bucket": bucket,
                "population": populations[key],
                "quota": quotas[key],
                "sampled": picked,
            }
        )
    # Frozen presentation order: one seeded shuffle so the EXPLORE/CONFIRM
    # prefix split is not biased by stratum sort order.
    order_rng = random.Random(f"{seed}:order")
    order_rng.shuffle(sampled)
    return sampled, table


def normalize_rows(raw_rows: list[dict]) -> list[dict]:
    """Reduce listing rows to the minimal deterministic schema."""
    rows = []
    for row in raw_rows:
        iid = row.get("instance_id")
        repo = row.get("repo")
        if not iid or not repo:
            raise ValueError(f"listing row missing instance_id/repo: {row!r}")
        if "patch_changed_lines" in row:
            n_changed = int(row["patch_changed_lines"])
        elif "patch" in row:
            n_changed = changed_lines(str(row["patch"]))
        else:
            raise ValueError(
                f"listing row for {iid} has neither patch nor patch_changed_lines"
            )
        rows.append(
            {"instance_id": str(iid), "repo": str(repo), "patch_changed_lines": n_changed}
        )
    rows.sort(key=lambda r: r["instance_id"])
    ids = [r["instance_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("listing contains duplicate instance_id values")
    return rows


def listing_sha256(rows: list[dict]) -> str:
    """Deterministic digest of the normalized listing, source-independent."""
    payload = json.dumps(rows, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_receipt(
    rows: list[dict],
    *,
    n: int,
    n_explore: int,
    seed: int,
    listing_source: str,
    dataset_revision: str,
    created_at: float,
) -> dict:
    """Assemble the frozen sample + pre-registration receipt. Rows are
    re-normalized here so the receipt is independent of input row order."""
    rows = normalize_rows(rows)
    if n_explore < 0 or n_explore > n:
        raise ValueError(f"n_explore must be in [0, {n}], got {n_explore}")
    if n > len(rows):
        raise ValueError(f"asked for n={n} but the listing has only {len(rows)} instances")
    sampled_ids, strata_table = stratified_sample(rows, n, seed)
    explore, confirm = split_explore_confirm(sampled_ids, n_explore)
    return {
        "kind": "swebench_verified_preregistered_sample",
        "schema_version": SCHEMA_VERSION,
        "dataset": DATASET_NAME,
        "split": SPLIT,
        "dataset_revision": dataset_revision,
        "listing_source": listing_source,
        "listing_instances": len(rows),
        "listing_sha256": listing_sha256(rows),
        "seed": seed,
        "n": n,
        "n_explore": n_explore,
        "size_bucket_thresholds": {
            name: (f"<={upper} changed lines" if upper is not None else "unbounded")
            for name, upper in SIZE_BUCKETS
        },
        "strata": strata_table,
        "instance_ids": sampled_ids,
        "explore": explore,
        "confirm": confirm,
        "created_at_unix": int(created_at),
        "generated_by": "scripts/forge/sample_swebench_instances.py",
        "note": (
            "instance_ids is EXPLORE then CONFIRM in frozen order; passing "
            "--n-explore to the forge_v2 runner reproduces exactly this split "
            "via provenance.split_explore_confirm. 50 instances is a pipeline "
            "shakedown sample, not a C2-clearing sample."
        ),
    }


# --------------------------------------------------------------------------- #
# listing sources (network-optional)
# --------------------------------------------------------------------------- #
def load_listing_file(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_rows = data["instances"] if isinstance(data, dict) else data
    return normalize_rows(raw_rows)


def load_rows_from_datasets() -> tuple[list[dict], str]:
    """Load the listing through the HF ``datasets`` library (network or local
    HF cache). Raises DatasetUnavailable when the library is not importable or
    the dataset cannot be loaded; the caller degrades to instructions."""
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise DatasetUnavailable(f"datasets not importable: {exc}") from exc
    try:
        ds = load_dataset(DATASET_NAME, split=SPLIT)
    except Exception as exc:  # offline / cache miss / auth — degrade, never fake
        raise DatasetUnavailable(f"load_dataset failed: {exc}") from exc
    rows = normalize_rows(
        [
            {"instance_id": r["instance_id"], "repo": r["repo"], "patch": r["patch"]}
            for r in ds
        ]
    )
    version = str(getattr(getattr(ds, "info", None), "version", "") or "unknown")
    fingerprint = str(getattr(ds, "_fingerprint", "") or "unknown")
    return rows, f"version={version} fingerprint={fingerprint}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=50, help="sample size")
    ap.add_argument("--n-explore", type=int, default=20,
                    help="EXPLORE prefix size; the rest is the frozen CONFIRM split")
    ap.add_argument("--seed", type=int, default=20260819, help="deterministic sampling seed")
    ap.add_argument("--listing", type=Path, default=None,
                    help="offline listing JSON (list of {instance_id, repo, patch|patch_changed_lines})")
    ap.add_argument("--out", type=Path, default=None,
                    help="receipt output path (default: reports/governance/forge_benchmark/"
                         "swebench_verified_sample_n<N>_seed<SEED>.json)")
    ap.add_argument("--dump-listing", type=Path, default=None,
                    help="also write the normalized listing JSON here for offline reuse")
    args = ap.parse_args(argv)

    if args.listing is not None:
        rows = load_listing_file(args.listing)
        listing_source = str(args.listing)
        dataset_revision = "unknown (offline listing; see listing_sha256)"
    else:
        try:
            rows, dataset_revision = load_rows_from_datasets()
        except DatasetUnavailable as exc:
            print(f"[sampler] {exc}", file=sys.stderr)
            print(FETCH_INSTRUCTIONS, file=sys.stderr)
            return 3
        listing_source = "datasets:load_dataset"

    if args.dump_listing is not None:
        args.dump_listing.parent.mkdir(parents=True, exist_ok=True)
        args.dump_listing.write_text(
            json.dumps({"instances": rows}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"[sampler] wrote listing ({len(rows)} instances) -> {args.dump_listing}")

    receipt = build_receipt(
        rows,
        n=args.n,
        n_explore=args.n_explore,
        seed=args.seed,
        listing_source=listing_source,
        dataset_revision=dataset_revision,
        created_at=time.time(),
    )
    out = args.out or (
        DEFAULT_OUT_DIR / f"swebench_verified_sample_n{args.n}_seed{args.seed}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"[sampler] frozen {args.n}-instance sample (seed={args.seed}) -> {out}")
    print(f"[sampler] explore={len(receipt['explore'])} confirm={len(receipt['confirm'])} "
          f"strata={len(receipt['strata'])}")
    print("[sampler] commit this receipt BEFORE running the benchmark (pre-registration).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
