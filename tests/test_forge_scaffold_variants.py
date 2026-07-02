from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.forge_v1.forge_v2 import scaffold_variants as sv


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


BASELINE = {
    "arm": "verify_chain",
    "generator": "glm-5.2",
    "verifier": "kimi-k2.7-code:cloud",
    "selection_strategy": "verify_chain",
    "window_chars": 11000,
}


def test_static_sanity_check_accepts_baseline() -> None:
    check = sv.static_sanity_check(BASELINE)
    assert check["ok"] is True
    assert check["blockers"] == []


def test_static_sanity_check_rejects_invalid_arm() -> None:
    check = sv.static_sanity_check({**BASELINE, "arm": "oracle_peek"})
    assert check["ok"] is False
    assert "invalid_arm:oracle_peek" in check["blockers"]


def test_static_sanity_check_rejects_self_moa_as_tested_candidate_arm() -> None:
    check = sv.static_sanity_check({**BASELINE, "arm": "self_moa", "selection_strategy": "self_moa"})
    assert check["ok"] is False
    assert "invalid_arm:self_moa" in check["blockers"]


def test_static_sanity_check_rejects_divergent_selection_strategy() -> None:
    # selection_strategy mirrors arm; the runner dispatches on arm only, so a
    # divergent selection_strategy would run identically to the parent (a no-op
    # EXPLORE candidate).  It must be receipted as broken, not queued for grade.
    check = sv.static_sanity_check({**BASELINE, "selection_strategy": "mixed_moa"})
    assert check["ok"] is False
    assert any(b.startswith("selection_strategy_not_executable:") for b in check["blockers"])


def test_static_sanity_check_allows_selection_strategy_mirroring_arm() -> None:
    # The harmless mirror (selection_strategy == arm) that the baseline carries
    # must remain ok so we do not reject legitimate carried metadata.
    check = sv.static_sanity_check({**BASELINE, "selection_strategy": "verify_chain"})
    assert check["ok"] is True
    assert check["blockers"] == []


def test_static_sanity_check_rejects_unwired_structural_fields() -> None:
    # Fields in the mutation menu that the Forge runner never reads make a
    # candidate a behavioral no-op; queuing them would spend grade budget to
    # measure the baseline.  Each must be receipted as not-executable.
    for field in ("retry_policy", "patch_format_policy"):
        check = sv.static_sanity_check({**BASELINE, field: "single_repair"})
        assert check["ok"] is False, field
        assert f"genome_field_not_executable:{field}" in check["blockers"], field


def test_generate_variants_only_marks_runner_executable_fields_ok() -> None:
    # Regression guard: the only single-field mutations that survive as static-ok
    # are ones the runner actually consumes (verifier, window_chars).  If a future
    # change wires another field, wire it in runner.run and drop it from
    # UNWIRED_GENOME_FIELDS in the SAME change.
    gen = sv.generate_variants(BASELINE, max_variants=40, max_fields_per_mutation=1)
    ok_fields = {f for v in gen["variants"] if v["static_check"]["ok"] for f in v["mutated_fields"]}
    assert ok_fields == {"verifier", "window_chars"}


def test_static_sanity_check_rejects_verify_chain_without_verifier() -> None:
    check = sv.static_sanity_check({"arm": "verify_chain", "generator": "glm-5.2"})
    assert check["ok"] is False
    assert "verify_chain_requires_verifier" in check["blockers"]


def test_static_sanity_check_rejects_mixed_moa_without_mix_models() -> None:
    check = sv.static_sanity_check({"arm": "mixed_moa", "generator": "glm-5.2"})
    assert check["ok"] is False
    assert "mixed_moa_requires_mix_models" in check["blockers"]


def test_static_sanity_check_rejects_out_of_band_window() -> None:
    low = sv.static_sanity_check({**BASELINE, "window_chars": 500})
    high = sv.static_sanity_check({**BASELINE, "window_chars": 999999})
    assert low["ok"] is False and any("window_chars_out_of_band" in b for b in low["blockers"])
    assert high["ok"] is False and any("window_chars_out_of_band" in b for b in high["blockers"])


def test_static_sanity_check_rejects_missing_generator() -> None:
    check = sv.static_sanity_check({"arm": "self_moa"})
    assert check["ok"] is False
    assert "missing_generator" in check["blockers"]


def test_generate_variants_yields_10_to_30_distinct_candidates() -> None:
    gen = sv.generate_variants(BASELINE, max_variants=30, max_fields_per_mutation=2)
    assert 10 <= gen["variant_count"] <= 30
    keys = [v["candidate_key"] for v in gen["variants"]]
    assert len(keys) == len(set(keys))  # all distinct
    assert gen["parent_sha256"] not in keys  # parent never emitted as its own variant
    # at least one statically-ok variant exists (directional candidates to explore)
    assert gen["static_ok_count"] >= 1


def test_generate_variants_is_deterministic() -> None:
    a = sv.generate_variants(BASELINE, max_variants=15)
    b = sv.generate_variants(BASELINE, max_variants=15)
    assert [v["candidate_key"] for v in a["variants"]] == [v["candidate_key"] for v in b["variants"]]


def test_generate_variants_single_field_only() -> None:
    gen = sv.generate_variants(BASELINE, max_variants=30, max_fields_per_mutation=1)
    assert all(len(v["mutated_fields"]) == 1 for v in gen["variants"])


def test_generate_variants_rejects_bad_args() -> None:
    import pytest

    with pytest.raises(ValueError):
        sv.generate_variants(BASELINE, max_variants=0)
    with pytest.raises(ValueError):
        sv.generate_variants(BASELINE, max_fields_per_mutation=3)


def test_archive_generated_variants_writes_scaffold_rows(tmp_path: Path) -> None:
    gen = sv.generate_variants(BASELINE, max_variants=12, max_fields_per_mutation=1)
    summary = sv.archive_generated_variants(
        gen,
        archive_root=tmp_path,
        parent_id="parent-genome",
        receipt_links=["/tmp/phase3.md"],
    )
    assert summary["archived"] == gen["variant_count"]
    rows = _read_jsonl(tmp_path / "scaffold_genomes.jsonl")
    assert len(rows) == gen["variant_count"]
    # every archived row is shadow-only and non-live-applied
    for row in rows:
        payload = row["test_results"]
        assert payload["track"] == "scaffold_genome"
        assert payload["live_apply_allowed"] is False
        assert payload["parent_id"] == "parent-genome"
        assert payload["evaluation"]["evaluated"] is False


def test_archive_generated_variants_receipts_broken_variants(tmp_path: Path) -> None:
    # Force a generation set that includes at least one broken variant by using a
    # self_moa parent with no verifier: switching arm to verify_chain (a menu
    # mutation) with no verifier yields a statically-broken child.
    parent = {"arm": "self_moa", "generator": "glm-5.2", "selection_strategy": "self_moa"}
    gen = sv.generate_variants(parent, max_variants=30, max_fields_per_mutation=1)
    assert gen["static_broken_count"] >= 1
    summary = sv.archive_generated_variants(gen, archive_root=tmp_path, parent_id=None)
    assert summary["static_broken"] == gen["static_broken_count"]
    rows = _read_jsonl(tmp_path / "scaffold_genomes.jsonl")
    broken = [r for r in rows if r["test_results"]["evaluation"]["closeout"] == "blocked_with_evidence"]
    assert len(broken) == gen["static_broken_count"]
