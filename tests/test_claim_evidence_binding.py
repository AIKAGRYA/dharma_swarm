"""Tests for the Pudgala Forge graded claim/evidence binding (Phase 1).

These guard the anti-slop bar itself: existence-only evidence is not closure,
self-owned tests are not independent oracles, and a machine receipt that is
tampered or stale is not evidence. They are small and fast — structural
invariants over the extended governance gate, not the live portfolio contents.

This module is the *independent oracle* (oracle_source: ci) for the proposed
anti-slop-pudgala-forge track: it is authored to verify the kernel, not by the
code's owner asserting its own correctness.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))

from check_track_status import (  # type: ignore  # noqa: E402
    check_receipt_valid,
    evaluate_track,
    grade_of_criterion,
    grade_name,
    CriterionResult,
)

from dharma_swarm.spine.receipt import (  # noqa: E402
    VerifiedMachineReceipt,
    append_machine_receipt,
)


# --------------------------------------------------------------------------- #
# Grade ladder + graded conjunct                                              #
# --------------------------------------------------------------------------- #

def _passing(kind: str) -> CriterionResult:
    return CriterionResult(id="x", kind=kind, passed=True, detail="")


def test_grade_of_unknown_kind_is_s0() -> None:
    assert grade_of_criterion({"kind": "wat"}, _passing("wat"), {}) == 0


def test_grade_of_failing_criterion_is_zero() -> None:
    failing = CriterionResult(id="x", kind="commit_on_main", passed=False)
    assert grade_of_criterion({"kind": "commit_on_main"}, failing, {}) == 0


def test_existence_kinds_grade_below_landed() -> None:
    assert grade_of_criterion({"kind": "file_exists"}, _passing("file_exists"), {}) == 0
    assert grade_of_criterion({"kind": "file_contains"}, _passing("file_contains"), {}) == 1
    assert grade_of_criterion({"kind": "commit_on_main"}, _passing("commit_on_main"), {}) == 2


def test_self_owned_test_is_downgraded_from_s3_to_s2() -> None:
    track = {"owner": "@alice"}
    # No oracle_source declared -> not independent -> downgraded.
    assert grade_of_criterion({"kind": "test_passes"}, _passing("test_passes"), track) == 2
    # oracle_source == owner -> still not independent -> downgraded.
    crit = {"kind": "test_passes", "oracle_source": "@alice"}
    assert grade_of_criterion(crit, _passing("test_passes"), track) == 2


def test_independent_oracle_keeps_s3() -> None:
    track = {"owner": "@alice"}
    crit = {"kind": "test_passes", "oracle_source": "ci"}
    assert grade_of_criterion(crit, _passing("test_passes"), track) == 3


def test_track_on_file_contains_only_is_not_shippable() -> None:
    track = {
        "id": "t-existence",
        "status": "ACTIVE",
        "owner": "@alice",
        "completion_criteria": [
            {"id": "c1", "kind": "file_contains",
             "file": "docs/governance/evidence_grades.yaml", "pattern": "grades"},
        ],
    }
    r = evaluate_track(track)
    assert r["strongest_grade"] == 1
    assert r["min_evidence_grade"] == 2  # default floor S2
    assert not r["shippable"]
    assert any("strongest evidence" in b for b in r["ship_blocks"])


def test_track_on_commit_on_main_meets_floor() -> None:
    # commit_on_main against a bogus sha fails verification, so use a passing
    # stub by monkey-free construction: a real commit check would need git.
    # Instead assert the grade math: a passing commit_on_main is S2 == floor.
    track = {
        "id": "t-landed",
        "status": "ACTIVE",
        "owner": "@alice",
        "min_evidence_grade": 2,
        "completion_criteria": [{"id": "c1", "kind": "commit_on_main", "commit": "HEAD"}],
    }
    r = evaluate_track(track)
    # HEAD is an ancestor of HEAD, so the criterion passes -> S2 -> meets floor
    # (no open blockers, rigorous evidence present).
    assert r["strongest_grade"] >= 2
    assert not any("strongest evidence" in b for b in r["ship_blocks"])


def test_grade_name_is_human_readable() -> None:
    assert grade_name(0).startswith("S0")
    assert grade_name(2).startswith("S2")


# --------------------------------------------------------------------------- #
# VerifiedMachineReceipt: chain, digest, freshness                            #
# --------------------------------------------------------------------------- #

def test_machine_receipt_roundtrips_and_chains(tmp_path: Path) -> None:
    log = tmp_path / "receipts.jsonl"
    c1 = append_machine_receipt(
        VerifiedMachineReceipt(claim_id="C1", command="pytest a", exit_code=0), path=log)
    c2 = append_machine_receipt(
        VerifiedMachineReceipt(claim_id="C1", command="pytest b", exit_code=0), path=log)
    assert c1.verify() and c2.verify()
    assert c2.prev_digest == c1.digest          # linked
    assert c1.prev_digest == ""                  # genesis


def test_checker_accepts_intact_chain(tmp_path: Path) -> None:
    log = tmp_path / "receipts.jsonl"
    append_machine_receipt(
        VerifiedMachineReceipt(claim_id="C1", command="x", exit_code=0), path=log)
    res = check_receipt_valid(str(log), ["claim_id", "command"], expect_chain=True)
    assert res.passed, res.detail


def test_checker_rejects_tampered_digest(tmp_path: Path) -> None:
    log = tmp_path / "receipts.jsonl"
    append_machine_receipt(
        VerifiedMachineReceipt(claim_id="C1", command="x", exit_code=0), path=log)
    rows = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
    rows[0]["command"] = "rm -rf /"            # tamper, keep stale digest
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    res = check_receipt_valid(str(log), [], expect_chain=True)
    assert not res.passed
    assert "digest mismatch" in res.detail


def test_checker_rejects_broken_chain_link(tmp_path: Path) -> None:
    log = tmp_path / "receipts.jsonl"
    append_machine_receipt(VerifiedMachineReceipt(claim_id="C1", command="x"), path=log)
    append_machine_receipt(VerifiedMachineReceipt(claim_id="C1", command="y"), path=log)
    rows = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
    # Re-digest row 1 with a wrong prev_digest so its own digest stays valid but
    # the link is broken.
    from dharma_swarm.spine.receipt import _stable_digest  # type: ignore
    rows[1]["prev_digest"] = "deadbeef"
    payload = {k: v for k, v in rows[1].items() if k != "digest"}
    rows[1]["digest"] = _stable_digest(payload)
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    res = check_receipt_valid(str(log), [], expect_chain=True)
    assert not res.passed
    assert "broken" in res.detail


def test_checker_rejects_stale_receipt(tmp_path: Path) -> None:
    log = tmp_path / "receipt.json"
    # Single-object receipt with an old produced_at and a matching digest.
    from dharma_swarm.spine.receipt import _stable_digest  # type: ignore
    row = {"claim_id": "C1", "produced_at": "2000-01-01T00:00:00Z"}
    row["digest"] = _stable_digest({k: v for k, v in row.items() if k != "digest"})
    log.write_text(json.dumps(row))
    res = check_receipt_valid(str(log), ["claim_id"], expect_digest=True, fresh_ttl_days=7)
    assert not res.passed
    assert "stale" in res.detail


def test_checker_accepts_fresh_single_receipt(tmp_path: Path) -> None:
    from dharma_swarm.spine.receipt import _stable_digest, _utc_now  # type: ignore
    log = tmp_path / "receipt.json"
    row = {"claim_id": "C1", "produced_at": _utc_now()}
    row["digest"] = _stable_digest({k: v for k, v in row.items() if k != "digest"})
    log.write_text(json.dumps(row))
    res = check_receipt_valid(str(log), ["claim_id"], expect_digest=True, fresh_ttl_days=7)
    assert res.passed, res.detail
