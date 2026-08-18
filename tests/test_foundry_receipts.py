"""Tests for the seven-link foundry improvement receipt."""

from __future__ import annotations

import json

from dharma_swarm.foundry.receipts import (
    FoundryReceipt,
    StratifiedFields,
    benchmark_link,
    disclosure_link,
    external_ci_link,
    guardian_countersign_link,
    merge_event_link,
    pre_registration_link,
    report_render_link,
    write_receipt,
)


def _base_receipt() -> FoundryReceipt:
    return FoundryReceipt(
        receipt_id="r1", target_id="openevolve-mlx", candidate_id="c1",
        stratified=StratifiedFields(counterparty="algorithmicsuperintelligence"),
        pre_registration=pre_registration_link(
            target_id="openevolve-mlx", resolved_sha="deadbeef",
            tree_digest="sha256:abc", baseline_metric=1.0,
            oracle_cmd=["python", "-m", "unittest"], seed=7,
        ),
        benchmark=benchmark_link(
            baseline_metric=1.0, candidate_metric=1.09, runs=5,
            coefficient_of_variation=0.02, repro_cmd=["make", "bench"],
            isolation_level="docker_nonet",
        ),
        disclosure=disclosure_link(test_results="all green"),
    )


def test_links_present_counts():
    receipt = _base_receipt()
    assert set(receipt.links_present()) == {"pre_registration", "benchmark", "disclosure"}


def test_not_externally_confirmed_without_merge():
    assert _base_receipt().externally_confirmed() is False


def test_externally_confirmed_on_independent_merge():
    receipt = _base_receipt()
    receipt.merge_event = merge_event_link(
        repo="algorithmicsuperintelligence/openevolve",
        pr_url="https://github.com/x/y/pull/1", state="MERGED",
        author="dharma-bot", merged_by="codelion",
        merge_commit_sha="abc123", merged_at="2026-08-20T00:00:00Z",
    )
    assert receipt.externally_confirmed() is True


def test_self_merge_is_not_external_confirmation():
    receipt = _base_receipt()
    receipt.merge_event = merge_event_link(
        repo="x/y", pr_url="u", state="MERGED",
        author="dharma-bot", merged_by="dharma-bot",
        merge_commit_sha="abc", merged_at="t",
    )
    assert receipt.externally_confirmed() is False


def test_independent_leaderboard_record_confirms():
    receipt = _base_receipt()
    receipt.external_ci = external_ci_link(url="https://algotune.io/x", status="independent_record")
    assert receipt.externally_confirmed() is True


def test_seal_is_deterministic_and_sensitive():
    receipt = _base_receipt()
    # Same content sealed twice -> identical digest (deterministic).
    assert receipt.seal() == receipt.seal()
    before = receipt.seal()
    # Mutating any link changes the seal (tamper-evident).
    receipt.benchmark = benchmark_link(
        baseline_metric=1.0, candidate_metric=2.0, runs=5,
        coefficient_of_variation=0.02, repro_cmd=["make", "bench"],
        isolation_level="docker_nonet",
    )
    assert receipt.seal() != before


def test_write_receipt_persists_sealed(tmp_path):
    receipt = _base_receipt()
    receipt.guardian_countersign = guardian_countersign_link(
        cycle_file="cycle-003-fitness-quorum-guard.json", verified=True
    )
    receipt.report_render = report_render_link(path="card.md", digest="sha256:z")
    path = write_receipt(receipt, state_root=tmp_path)
    payload = json.loads(path.read_text())
    assert payload["schema_version"] == "foundry_improvement.v1"
    assert payload["sealed_digest"].startswith("sha256:")
    assert payload["stratified"]["domain"] == "external_code_contribution"
