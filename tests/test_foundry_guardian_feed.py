"""Tests for the One Wire guardian feed — including a round-trip against archive."""

from __future__ import annotations

from dharma_swarm.foundry.guardian_feed import (
    GUARDIAN_RECEIPT_RELPATH,
    REQUIRED_CONFIRMED,
    REQUIRED_DOMAINS,
    build_guardian_receipt,
    count_quorum,
    write_guardian_receipt,
)


def _confirmed(domain: str, i: int) -> dict:
    return {
        "externally_confirmed": True,
        "stratified": {"domain": domain},
        "merge_event": {"state": "MERGED", "independent": True},
        "receipt_id": f"r{i}",
    }


def _lab_local(i: int) -> dict:
    return {"externally_confirmed": False, "stratified": {"domain": "external_code_contribution"},
            "receipt_id": f"lab{i}"}


def test_lab_local_receipts_do_not_count():
    q = count_quorum([_lab_local(1), _lab_local(2)])
    assert q.confirmed == 0
    assert q.domains == 0
    assert not q.eligible


def test_quorum_counts_confirmed_across_domains():
    receipts = [
        _confirmed("external_code_contribution", 1),
        _confirmed("external_code_contribution", 2),
        _confirmed("external_code_contribution", 3),
        _confirmed("paid_governance_engagement", 4),
        _confirmed("externally_reviewed_research", 5),
    ]
    q = count_quorum(receipts)
    assert q.confirmed == 5
    assert q.domains == 3
    assert q.eligible


def test_authority_not_granted_by_default_even_when_eligible():
    receipts = [_confirmed("d1", 1), _confirmed("d1", 2), _confirmed("d1", 3),
                _confirmed("d2", 4), _confirmed("d3", 5)]
    payload = build_guardian_receipt(receipts)  # no grant
    assert payload["authority_result"]["eligible_to_set_archive_fitness"] is True
    assert payload["authority_result"]["fitness_authority_granted"] is False


def test_grant_requires_both_flag_and_eligibility():
    ineligible = [_confirmed("d1", 1)]  # N=1, M=1
    payload = build_guardian_receipt(ineligible, grant_authority=True)
    assert payload["authority_result"]["fitness_authority_granted"] is False


def test_receipt_path_matches_archive():
    from dharma_swarm import archive

    # archive dropped ONE_WIRE_REQUIRED_CONFIRMED/DOMAINS in efca57e40 (quorum
    # arithmetic is no longer the authority channel; the explicit operator flag
    # is). The load-bearing shared contract is the receipt path.
    assert GUARDIAN_RECEIPT_RELPATH == archive.ONE_WIRE_GUARDIAN_RECEIPT


def test_written_receipt_no_longer_authorizes_without_operator_flag(tmp_path):
    from dharma_swarm import archive

    # efca57e40 (11->9 silvering): archive authorizes only a literal top-level
    # "operator_approved": true. guardian_feed still writes the legacy quorum
    # shape (nested authority_result), so its receipts are inert until the
    # sublimation-forge track re-adopts the operator flag in its own packet —
    # the integration deliberately does not edit that sibling-owned surface.
    receipts = [_confirmed("d1", 1), _confirmed("d1", 2), _confirmed("d1", 3),
                _confirmed("d2", 4), _confirmed("d3", 5)]
    payload = build_guardian_receipt(receipts, grant_authority=True)
    write_guardian_receipt(payload, state_dir=tmp_path)

    authority = archive.read_one_wire_fitness_authority(tmp_path)
    assert authority.exists
    assert authority.operator_approved is False
    assert authority.allowed is False
    assert "operator_approved" in authority.blocker


def test_ineligible_receipt_denied_by_real_guard(tmp_path):
    from dharma_swarm import archive

    payload = build_guardian_receipt([_confirmed("d1", 1)], grant_authority=True)
    write_guardian_receipt(payload, state_dir=tmp_path)
    authority = archive.read_one_wire_fitness_authority(tmp_path)
    assert authority.allowed is False
