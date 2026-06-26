"""PR 1 verifier — operator_input_receipt.v0 + lifecycle receipt + fixtures.

Deterministic, no-network. Proves source receipts define themselves without
mutating trusted state and that source-rights enforcement holds.
"""

from __future__ import annotations

import json

import pytest

from dharma_swarm.idea_spark import (
    IDEA_SPARK_CANDIDATE_SCHEMA,
    OPERATOR_INPUT_LIFECYCLE_RECEIPT_SCHEMA,
    OPERATOR_INPUT_RECEIPT_SCHEMA,
    IdeaSparkCandidate,
    OperatorInputLifecycleReceipt,
    OperatorInputReceipt,
    content_hash,
    derive_candidate_id,
    derive_correlation_id,
    derive_input_id,
)
from dharma_swarm.idea_spark.fixtures import ALL_FIXTURES, NOTE_FIXTURE, URL_FIXTURE
from dharma_swarm.idea_spark.schemas import is_valid_lifecycle_id, sanitize_lifecycle_id
from dharma_swarm.idea_spark.store import (
    build_operator_input_receipt,
    load_input_receipts,
    load_lifecycle_receipt,
    read_input_receipt,
    update_lifecycle_receipt,
    write_input_receipt,
)


def test_schema_versions_are_pinned() -> None:
    assert OPERATOR_INPUT_RECEIPT_SCHEMA == "operator_input_receipt.v0"
    assert IDEA_SPARK_CANDIDATE_SCHEMA == "idea_spark_candidate.v0"
    assert OPERATOR_INPUT_LIFECYCLE_RECEIPT_SCHEMA == "operator_input_lifecycle_receipt.v0"


def test_content_hash_is_sha256_prefixed_and_deterministic() -> None:
    first = content_hash("hello world")
    assert first.startswith("sha256:")
    assert first == content_hash("hello world")
    assert first != content_hash("hello world!")


def test_id_derivation_is_deterministic_and_grammar_clean() -> None:
    digest = content_hash("an operator idea")
    input_id = derive_input_id("note", "operator://note/x", digest)
    corr = derive_correlation_id("operator://note/x", digest)
    candidate_id = derive_candidate_id(input_id, "An Operator   Idea")
    # Re-derivation is stable.
    assert input_id == derive_input_id("note", "operator://note/x", digest)
    assert corr == derive_correlation_id("operator://note/x", digest)
    # Normalized claim collapses whitespace/case.
    assert candidate_id == derive_candidate_id(input_id, "an operator idea")
    # Every lifecycle id is a clean MemoryKernel source_atom_id.
    for value in (input_id, corr, candidate_id):
        assert is_valid_lifecycle_id(value), value


def test_sanitize_lifecycle_id_coerces_foreign_ids() -> None:
    dirty = "/Users/dhyana/secret path=value"
    clean = sanitize_lifecycle_id(dirty)
    assert is_valid_lifecycle_id(clean)
    assert " " not in clean and "/" not in clean and "=" not in clean


def test_operator_supplied_receipt_keeps_none_redaction() -> None:
    receipt = NOTE_FIXTURE.build_receipt()
    assert receipt.schema_version == "operator_input_receipt.v0"
    assert receipt.source_rights == "operator_supplied"
    assert receipt.redaction_policy == "none"
    assert receipt.content_hash.startswith("sha256:")


def test_public_web_input_does_not_retain_raw_and_summarizes() -> None:
    # Even if a caller tries to attach raw storage, non-ownable rights clear it.
    receipt = build_operator_input_receipt(
        source_kind="url",
        source_ref=URL_FIXTURE.source_ref,
        content=URL_FIXTURE.content,
        source_rights="public_excerpt",
        captured_by="operator",
        captured_at="2026-06-26T00:00:00Z",
        raw_storage_ref="/Users/dhyana/full_page.html",
    )
    assert receipt.raw_storage_ref == ""
    assert receipt.redaction_policy == "summary_only"


def test_link_only_rights_force_link_only_policy() -> None:
    receipt = build_operator_input_receipt(
        source_kind="youtube_transcript",
        source_ref="https://youtu.be/abc",
        content="operator one-line summary of the talk",
        source_rights="link_only",
        captured_by="operator",
        captured_at="2026-06-26T00:00:00Z",
    )
    assert receipt.redaction_policy == "link_only"
    assert receipt.raw_storage_ref == ""


def test_all_fixtures_build_with_valid_ids(tmp_path) -> None:
    for fixture in ALL_FIXTURES:
        receipt = fixture.build_receipt()
        assert is_valid_lifecycle_id(receipt.input_id)
        assert is_valid_lifecycle_id(receipt.correlation_id)
        if fixture.expected_redaction is not None:
            assert receipt.redaction_policy == fixture.expected_redaction


def test_receipt_round_trip_and_immutability(tmp_path) -> None:
    receipt = NOTE_FIXTURE.build_receipt()
    path = write_input_receipt(receipt, tmp_path)
    assert path.exists()
    # Idempotent re-write of identical content is allowed.
    write_input_receipt(receipt, tmp_path)
    loaded = read_input_receipt(receipt.input_id, tmp_path)
    assert loaded == receipt
    assert load_input_receipts(tmp_path) == [receipt]

    # A conflicting receipt under the same id is refused.
    tampered = receipt.model_copy(update={"captured_by": "someone_else"})
    with pytest.raises(ValueError, match="conflicting immutable"):
        write_input_receipt(tampered, tmp_path)


def test_re_ingest_identical_content_at_a_later_time_is_idempotent(tmp_path) -> None:
    # Same content, different (unpinned) capture time -> same input_id; the
    # second write is a no-op, not a conflict (captured_at is volatile).
    first = NOTE_FIXTURE.build_receipt(captured_at="2026-06-26T00:00:00Z")
    later = NOTE_FIXTURE.build_receipt(captured_at="2026-06-27T09:30:00Z")
    assert first.input_id == later.input_id
    write_input_receipt(first, tmp_path)
    write_input_receipt(later, tmp_path)  # must not raise
    # The original receipt (and its captured_at) is preserved.
    stored = read_input_receipt(first.input_id, tmp_path)
    assert stored is not None
    assert stored.captured_at == "2026-06-26T00:00:00Z"


def test_lifecycle_receipt_update_merges_and_persists(tmp_path) -> None:
    corr = "corr_testlifecycle01"
    first = update_lifecycle_receipt(
        corr,
        tmp_path,
        status="captured",
        input_id="input_abc",
        evidence_paths=["a.json"],
    )
    assert isinstance(first, OperatorInputLifecycleReceipt)
    assert first.status == "captured"
    assert first.input_id == "input_abc"

    second = update_lifecycle_receipt(
        corr,
        tmp_path,
        status="staged",
        candidate_id="cand_xyz",
        evidence_paths=["b.json"],
    )
    # Non-empty new fields applied; list fields unioned; earlier fields kept.
    assert second.status == "staged"
    assert second.input_id == "input_abc"
    assert second.candidate_id == "cand_xyz"
    assert set(second.evidence_paths) == {"a.json", "b.json"}

    reloaded = load_lifecycle_receipt(corr, tmp_path)
    assert reloaded == second


def test_writing_a_receipt_does_not_touch_home(tmp_path) -> None:
    # The receipt file lands strictly under the supplied state root.
    receipt = NOTE_FIXTURE.build_receipt()
    path = write_input_receipt(receipt, tmp_path)
    assert str(tmp_path) in str(path)
    raw = json.loads(path.read_text())
    assert raw["schema_version"] == "operator_input_receipt.v0"


def test_candidate_model_embeds_triage_dict() -> None:
    candidate = IdeaSparkCandidate(
        candidate_id="cand_1",
        correlation_id="corr_1",
        title="t",
        claim="c",
        triage={"schema_version": "idea_spark_triage.v0", "decision": "incubate"},
    )
    assert candidate.schema_version == "idea_spark_candidate.v0"
    assert candidate.triage["schema_version"] == "idea_spark_triage.v0"
    assert candidate.routing_status == "unrouted"
    assert candidate.authority_level == "observation"
