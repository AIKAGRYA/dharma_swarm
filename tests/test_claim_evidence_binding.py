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
    _canonical_json as _spine_canonical_json,
    _stable_digest as _spine_stable_digest,
)
from dharma_swarm.memory_kernel.write_receipts import (  # noqa: E402
    canonical_json as _wr_canonical_json,
    stable_digest as _wr_stable_digest,
)
from check_track_status import (  # type: ignore  # noqa: E402
    _canonical_json as _gate_canonical_json,
    _stable_digest as _gate_stable_digest,
)


def test_canonical_digest_byte_identical_across_three_owners() -> None:
    """The receipt digest is computed/verified in three places — the producer
    (spine/receipt.py), the gate (check_track_status.py), and canon
    (memory_kernel/write_receipts.py). They MUST canonicalise byte-for-byte or a
    produced VerifiedMachineReceipt silently fails verification. This pins the
    triplication so it cannot drift unnoticed (closes the duplication fragility)."""
    samples = [
        {"b": 1, "a": 2, "nested": {"y": [3, 2, 1], "x": "z"}},
        {"claim_id": "c", "command": "pytest -k x", "exit_code": 0, "prev_digest": ""},
        {"unicode": "réçu—✓", "bool": True, "none": None, "float": 1.5},
        {},
    ]
    for payload in samples:
        assert (
            _spine_canonical_json(payload)
            == _gate_canonical_json(payload)
            == _wr_canonical_json(payload)
        ), f"canonical_json drift across owners for {payload!r}"
        assert (
            _spine_stable_digest(payload)
            == _gate_stable_digest(payload)
            == _wr_stable_digest(payload)
        ), f"stable_digest drift across owners for {payload!r}"


def test_resolve_enforcement_precedence() -> None:
    """Stage-driven ratchet: --warn-only forces advisory; --enforce forces
    blocking; otherwise the AI-M1 hygiene stage drives it (block iff 'enforced').
    This is what lets `promote.py AI-M1 --stage enforced` flip the gate's teeth on
    without a code change, and keeps it advisory (safe in governance-all) today."""
    from check_claim_evidence_binding import (  # type: ignore  # noqa: E402
        binding_stage,
        resolve_enforcement,
    )

    assert resolve_enforcement(enforce_flag=False, warn_only_flag=False, stage="advisory") is False
    assert resolve_enforcement(enforce_flag=False, warn_only_flag=False, stage="enforced") is True
    assert resolve_enforcement(enforce_flag=True, warn_only_flag=False, stage="advisory") is True
    # --warn-only wins over everything (stays advisory even at the enforced stage):
    assert resolve_enforcement(enforce_flag=True, warn_only_flag=True, stage="enforced") is False
    # the shipped AI-M1 pattern is advisory today, so the bare gate stays advisory:
    assert binding_stage() == "advisory"


def test_mutation_score_gte_grades_s6_and_reads_report(tmp_path: Path) -> None:
    """S6 (P3-09) is ACTIVE: a passing mutation_score_gte grades S6, and the gate
    READS a mutation-score report — above threshold passes; below / missing /
    stale fail (fail-closed). The slow mutmut run that produces the report is a
    separate `make mutation-test` step (the gate never runs mutmut inline)."""
    from check_track_status import check_mutation_score_gte  # type: ignore  # noqa: E402

    assert grade_of_criterion({"kind": "mutation_score_gte"}, _passing("mutation_score_gte"), {}) == 6
    assert grade_name(6).startswith("S6")

    rpt = tmp_path / "mutation_score.json"
    rpt.write_text(json.dumps({"score": 0.72, "killed": 36, "total": 50,
                               "produced_at": "2026-06-25T00:00:00Z"}), encoding="utf-8")
    assert check_mutation_score_gte(str(rpt), 0.6).passed              # 0.72 >= 0.60
    assert not check_mutation_score_gte(str(rpt), 0.8).passed          # 0.72 <  0.80
    assert not check_mutation_score_gte(str(tmp_path / "nope.json"), 0.6).passed  # missing -> fail-closed
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"score": 0.99, "produced_at": "2020-01-01T00:00:00Z"}), encoding="utf-8")
    assert not check_mutation_score_gte(str(old), 0.6, fresh_ttl_days=1).passed   # stale -> fail


def test_parse_mutmut_summary_score() -> None:
    """The version-tolerant mutmut parser computes killed / (killed + survived +
    timeout + suspicious), excluding skipped — so the S6 score cannot drift
    silently across mutmut versions."""
    from mutation_score_report import parse_mutmut_summary  # type: ignore  # noqa: E402

    c = parse_mutmut_summary("⠋ 50/50  🎉 36  ⏰ 1  🤔 1  🙁 12  🔇 4")
    assert c["killed"] == 36 and c["survived"] == 12 and c["skipped"] == 4
    assert c["total"] == 50  # 36 + 12 + 1 + 1; skipped excluded
    assert c["score"] == 0.72
    assert parse_mutmut_summary("no mutants here")["score"] == 0.0


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


def test_track_meets_floor_on_receipt_valid_s2(tmp_path: Path) -> None:
    # Deterministic S2 evidence without depending on git ancestry: a valid
    # chained machine receipt (receipt_valid -> S2, a RIGOROUS kind). Proves the
    # graded conjunct is satisfied when strongest_grade meets the floor.
    log = tmp_path / "receipt.jsonl"
    append_machine_receipt(
        VerifiedMachineReceipt(claim_id="C1", command="x", exit_code=0), path=log)
    track = {
        "id": "t-landed",
        "status": "ACTIVE",
        "owner": "@alice",
        "min_evidence_grade": 2,
        "completion_criteria": [
            {"id": "c1", "kind": "receipt_valid", "file": str(log),
             "requires_keys": ["claim_id"], "expect_chain": True},
        ],
    }
    r = evaluate_track(track)
    assert r["strongest_grade"] >= 2
    assert not any("strongest evidence" in b for b in r["ship_blocks"])
    assert r["shippable"]


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
