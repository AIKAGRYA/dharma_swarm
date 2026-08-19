"""Hermetic tests for scripts/forge/sample_swebench_instances.py.

No network, no `datasets` import required: the sampler's pure machinery is
tested directly and the end-to-end path runs from a local listing file. The
offline-degrade path is exercised by forcing DatasetUnavailable."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.forge_v1.forge_v2.provenance import split_explore_confirm  # noqa: E402

SCRIPT_PATH = REPO_ROOT / "scripts" / "forge" / "sample_swebench_instances.py"
spec = importlib.util.spec_from_file_location("sample_swebench_instances", SCRIPT_PATH)
sampler = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["sample_swebench_instances"] = sampler
spec.loader.exec_module(sampler)


# --------------------------------------------------------------------------- #
# pure machinery
# --------------------------------------------------------------------------- #
def test_changed_lines_counts_hunk_lines_not_headers() -> None:
    diff = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,3 +1,4 @@\n"
        " context\n"
        "-old\n"
        "+new\n"
        "+added\n"
    )
    assert sampler.changed_lines(diff) == 3
    assert sampler.changed_lines("") == 0


def test_size_bucket_thresholds() -> None:
    assert sampler.size_bucket(0) == "S"
    assert sampler.size_bucket(10) == "S"
    assert sampler.size_bucket(11) == "M"
    assert sampler.size_bucket(40) == "M"
    assert sampler.size_bucket(41) == "L"
    assert sampler.size_bucket(4000) == "L"


def test_allocate_quotas_sums_to_n_and_respects_populations() -> None:
    pops = {("django", "S"): 30, ("django", "L"): 10, ("sympy", "S"): 10}
    quotas = sampler.allocate_quotas(pops, 10)
    assert sum(quotas.values()) == 10
    assert all(quotas[k] <= pops[k] for k in pops)
    # proportional: django/S holds 60% of the population
    assert quotas[("django", "S")] == 6
    # asking for more than the population returns everything
    assert sampler.allocate_quotas({("a", "S"): 3}, 50) == {("a", "S"): 3}
    # a stratum can never be over-drawn even when others are exhausted
    quotas2 = sampler.allocate_quotas({("a", "S"): 2, ("b", "S"): 100}, 50)
    assert sum(quotas2.values()) == 50
    assert quotas2[("a", "S")] <= 2


def _rows(n_per_repo: int = 30) -> list[dict]:
    rows = []
    for repo in ("django/django", "sympy/sympy"):
        for i in range(n_per_repo):
            # spread sizes across all three buckets
            size = (i % 3) * 20 + 1  # 1, 21, 41 -> S, M, L
            rows.append(
                {
                    "instance_id": f"{repo.split('/')[0]}__x-{i}",
                    "repo": repo,
                    "patch_changed_lines": size,
                }
            )
    return rows


def test_stratified_sample_is_deterministic_and_seed_sensitive() -> None:
    rows = _rows()
    ids_a, table_a = sampler.stratified_sample(rows, 20, seed=42)
    ids_b, table_b = sampler.stratified_sample(rows, 20, seed=42)
    assert ids_a == ids_b
    assert table_a == table_b
    ids_c, _ = sampler.stratified_sample(rows, 20, seed=43)
    assert ids_a != ids_c
    assert len(ids_a) == 20 == len(set(ids_a))
    population = {r["instance_id"] for r in rows}
    assert set(ids_a) <= population
    # both repos and every size bucket are represented (anti-cherry-pick)
    sampled_strata = {(t["repo"], t["size_bucket"]) for t in table_a if t["quota"] > 0}
    assert {s[0] for s in sampled_strata} == {"django/django", "sympy/sympy"}
    assert {s[1] for s in sampled_strata} == {"S", "M", "L"}


def test_build_receipt_freezes_split_and_never_overdraws() -> None:
    rows = _rows()
    receipt = sampler.build_receipt(
        rows, n=20, n_explore=8, seed=7, listing_source="test",
        dataset_revision="rev", created_at=123.0,
    )
    assert receipt["n"] == 20 and receipt["seed"] == 7
    assert receipt["instance_ids"] == receipt["explore"] + receipt["confirm"]
    assert (receipt["explore"], receipt["confirm"]) == tuple(
        split_explore_confirm(receipt["instance_ids"], 8)
    )
    assert receipt["listing_sha256"] == sampler.listing_sha256(
        sampler.normalize_rows(rows)
    )
    with pytest.raises(ValueError):
        sampler.build_receipt(rows, n=1000, n_explore=1, seed=7,
                              listing_source="t", dataset_revision="r", created_at=0.0)
    with pytest.raises(ValueError):
        sampler.build_receipt(rows, n=20, n_explore=21, seed=7,
                              listing_source="t", dataset_revision="r", created_at=0.0)


def test_normalize_rows_rejects_duplicates_and_incomplete_rows() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        sampler.normalize_rows(
            [
                {"instance_id": "a", "repo": "r", "patch_changed_lines": 1},
                {"instance_id": "a", "repo": "r", "patch_changed_lines": 2},
            ]
        )
    with pytest.raises(ValueError, match="neither patch nor patch_changed_lines"):
        sampler.normalize_rows([{"instance_id": "a", "repo": "r"}])


# --------------------------------------------------------------------------- #
# end-to-end offline path
# --------------------------------------------------------------------------- #
def test_main_offline_from_listing_writes_receipt(tmp_path: Path) -> None:
    listing = tmp_path / "listing.json"
    listing.write_text(json.dumps({"instances": _rows()}))
    out = tmp_path / "sample.json"
    rc = sampler.main(
        ["--n", "20", "--n-explore", "8", "--seed", "99",
         "--listing", str(listing), "--out", str(out)]
    )
    assert rc == 0
    receipt = json.loads(out.read_text())
    assert receipt["kind"] == "swebench_verified_preregistered_sample"
    assert len(receipt["instance_ids"]) == 20
    assert len(receipt["explore"]) == 8 and len(receipt["confirm"]) == 12
    assert receipt["dataset"] == "princeton-nlp/SWE-bench_Verified"
    assert receipt["listing_source"] == str(listing)
    # deterministic given the seed: a second run writes an identical sample
    out2 = tmp_path / "sample2.json"
    assert sampler.main(
        ["--n", "20", "--n-explore", "8", "--seed", "99",
         "--listing", str(listing), "--out", str(out2)]
    ) == 0
    r2 = json.loads(out2.read_text())
    assert r2["instance_ids"] == receipt["instance_ids"]
    assert r2["strata"] == receipt["strata"]


def test_main_degrades_to_instructions_when_datasets_unavailable(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    def unavailable():
        raise sampler.DatasetUnavailable("no datasets in this environment")

    monkeypatch.setattr(sampler, "load_rows_from_datasets", unavailable)
    out = tmp_path / "sample.json"
    rc = sampler.main(["--n", "50", "--seed", "1", "--out", str(out)])
    assert rc == 3
    assert not out.exists()  # never fakes a sample
    err = capsys.readouterr().err
    assert "pip install datasets" in err
    assert "--listing" in err
