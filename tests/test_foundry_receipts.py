"""Tests for the seven-link foundry improvement receipt."""

from __future__ import annotations

import json
import difflib
import hashlib

import pytest

from dharma_swarm.foundry.receipts import (
    FoundryReceipt,
    ReceiptChainError,
    StratifiedFields,
    benchmark_link,
    disclosure_link,
    external_ci_link,
    guardian_countersign_link,
    merge_event_link,
    pre_registration_link,
    report_render_link,
    audit_receipts,
    quarantine_legacy_state,
    seedability_report,
    verify_receipt_chain,
    write_receipt,
)
from dharma_swarm.foundry.artifacts import build_lineage
from dharma_swarm.foundry.target_ingest import compute_tree_digest


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


def test_receipts_are_unique_append_only_and_hash_chained(tmp_path):
    first_path = write_receipt(_base_receipt(), state_root=tmp_path)
    second_receipt = _base_receipt()
    second_receipt.receipt_id = "r2"
    second_path = write_receipt(second_receipt, state_root=tmp_path)

    assert first_path != second_path
    assert first_path.exists() and second_path.exists()
    first = json.loads(first_path.read_text())
    second = json.loads(second_path.read_text())
    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert first["prev_receipt_digest"] == "genesis"
    assert second["prev_receipt_digest"] == first["sealed_digest"]
    ok, detail = verify_receipt_chain(tmp_path)
    assert ok, detail


def test_duplicate_receipt_identity_is_rejected_before_append(tmp_path):
    first = write_receipt(_base_receipt(), state_root=tmp_path)
    with pytest.raises(ReceiptChainError, match="duplicate_receipt_ids"):
        write_receipt(_base_receipt(), state_root=tmp_path)
    assert list(tmp_path.glob("*.json")) == [first]


def test_receipt_audit_detects_tamper_missing_orphan_and_duplicate(tmp_path):
    receipt = _base_receipt()
    first_path = write_receipt(receipt, state_root=tmp_path / "receipts")
    second_receipt = _base_receipt()
    second_receipt.receipt_id = "r2"
    second_path = write_receipt(second_receipt, state_root=tmp_path / "receipts")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    referenced = artifacts / f"{'a' * 64}.patch"
    referenced.write_text("referenced", encoding="utf-8")
    referenced.unlink()
    (artifacts / "orphan.patch").write_text("orphan", encoding="utf-8")

    payload = json.loads(first_path.read_text())
    payload["disclosure"] = disclosure_link(diff_sha256="a" * 64)
    payload["candidate_id"] = "tampered"
    first_path.write_text(json.dumps(payload), encoding="utf-8")
    second = json.loads(second_path.read_text())
    second["receipt_id"] = "r1"
    second_path.write_text(json.dumps(second), encoding="utf-8")

    audit = audit_receipts(tmp_path)
    assert not audit.ok
    assert audit.invalid_receipts
    assert audit.missing_artifacts
    assert audit.orphan_artifacts
    assert audit.duplicate_receipt_ids == ("r1",)


def test_legacy_receipt_is_compatibility_anchor_not_rewritten(tmp_path):
    legacy = tmp_path / "old-logical-name.json"
    legacy.write_text(json.dumps({"receipt_id": "old", "target_id": "t"}))
    before = legacy.read_bytes()

    path = write_receipt(_base_receipt(), state_root=tmp_path)
    payload = json.loads(path.read_text())
    assert payload["sequence"] == 1
    assert payload["prev_receipt_digest"].startswith("sha256:")
    assert legacy.read_bytes() == before
    audit = audit_receipts(tmp_path)
    assert audit.legacy_receipts == 1


def test_malformed_sequence_is_reported_not_raised(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"receipt_id": "bad", "sequence": {"oops": 1}}))
    audit = audit_receipts(tmp_path)
    assert not audit.ok
    assert any("malformed sequence" in item for item in audit.invalid_receipts)


def test_orphan_artifact_blocks_new_receipt(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "orphan.patch").write_text("orphan", encoding="utf-8")
    with pytest.raises(ReceiptChainError, match="orphan_artifacts"):
        write_receipt(_base_receipt(), state_root=tmp_path / "receipts")


def test_legacy_quarantine_is_lossless_and_leaves_stop_marker(tmp_path):
    receipts = tmp_path / "receipts"
    artifacts = tmp_path / "artifacts"
    receipts.mkdir()
    artifacts.mkdir()
    (receipts / "lost.json").write_text(json.dumps({
        "receipt_id": "lost",
        "target_id": "t",
        "disclosure": {"diff_sha256": "b" * 64},
    }))
    orphan = artifacts / "orphan.patch"
    orphan.write_text("preserve me", encoding="utf-8")

    planned = quarantine_legacy_state(tmp_path)
    assert planned["needed"] and not planned["applied"]
    assert (receipts / "lost.json").exists() and orphan.exists()

    applied = quarantine_legacy_state(tmp_path, apply=True)
    assert applied["applied"]
    assert applied["success_criteria_met"]
    assert applied["seedability_after"]["all_seedable_replay_verified"]
    assert (tmp_path / "QUARANTINE.json").exists()
    destinations = [tmp_path / move["destination"] for move in applied["moves"]]
    assert all(path.exists() for path in destinations)
    assert any(path.read_text() == "preserve me" for path in destinations)
    assert audit_receipts(tmp_path).ok


def test_legacy_champion_and_referenced_delta_are_both_nonseedable_quarantine(tmp_path):
    receipts = tmp_path / "receipts"
    artifacts = tmp_path / "artifacts"
    receipts.mkdir()
    artifacts.mkdir()
    delta = b"legacy delta without cumulative v2 lineage\n"
    sha = hashlib.sha256(delta).hexdigest()
    artifact = artifacts / f"{sha}.patch"
    artifact.write_bytes(delta)
    legacy = receipts / "legacy-champion.json"
    legacy.write_text(json.dumps({
        "receipt_id": "legacy-champion",
        "target_id": "target",
        "benchmark": {"candidate_metric": 99.0},
        "disclosure": {"diff_sha256": sha},
    }), encoding="utf-8")

    classification = seedability_report(tmp_path)
    assert classification["nonseedable_count"] == 1
    assert classification["records"][0]["classification"] == "legacy_nonseedable"
    plan = quarantine_legacy_state(tmp_path)
    assert {item["source"] for item in plan["moves"]} == {
        "receipts/legacy-champion.json", f"artifacts/{sha}.patch",
    }
    applied = quarantine_legacy_state(tmp_path, apply=True)
    assert applied["success_criteria_met"]
    assert not legacy.exists() and not artifact.exists()
    assert audit_receipts(tmp_path).ok


def test_authoritative_lineage_can_append_then_delta_tamper_fails_audit(tmp_path):
    base = tmp_path / "base"
    seeded = tmp_path / "seeded"
    for root in (base, seeded):
        (root / "src").mkdir(parents=True)
        (root / "src" / "x.py").write_text("VALUE = 1\n", encoding="utf-8")
    delta = "".join(difflib.unified_diff(
        ["VALUE = 1\n"], ["VALUE = 2\n"],
        fromfile="a/src/x.py", tofile="b/src/x.py",
    ))
    lineage = build_lineage(
        state_root=tmp_path / "state",
        target_id="target",
        resolved_sha="abc",
        base_root=base,
        seeded_root=seeded,
        base_tree_digest=compute_tree_digest(base, ["src/x.py"]),
        evolve_file="src/x.py",
        delta=delta,
        evaluator_id="test-evaluator",
        evaluator_config_digest="sha256:" + "c" * 64,
        evaluator_image_digest="sha256:" + "d" * 64,
        claimed_score=2.0,
        score_observations=[2.0, 2.0],
    )
    receipt = _base_receipt()
    receipt.receipt_id = "authoritative-unique"
    receipt.target_id = "target"
    receipt.artifact_lineage = lineage
    receipt.disclosure = disclosure_link(diff_sha256=lineage["cumulative_sha256"])
    write_receipt(
        receipt,
        state_root=tmp_path / "state" / "receipts",
        lineage_base_root=base,
    )
    assert audit_receipts(
        tmp_path / "state", replay_roots={"target": base}
    ).ok

    delta_path = tmp_path / "state" / lineage["delta_artifact"]
    delta_path.write_text("tampered\n", encoding="utf-8")
    audit = audit_receipts(
        tmp_path / "state", replay_roots={"target": base}
    )
    assert not audit.ok
    assert any("delta artifact sha256 mismatch" in item for item in audit.invalid_receipts)
