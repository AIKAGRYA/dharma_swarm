"""Tests for the Pudgala Autopoiesis Protostar graded claim/evidence binding (Phase 1).

These guard the anti-slop bar itself: existence-only evidence is not closure,
self-owned tests are not independent oracles, and a machine receipt that is
tampered or stale is not evidence. They are small and fast — structural
invariants over the extended governance gate, not the live portfolio contents.

This module is the *independent oracle* (oracle_source: ci) for the proposed
anti-slop-pudgala-autopoiesis-protostar track: it is authored to verify the
kernel, not by the code's owner asserting its own correctness.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))

from check_track_status import (  # type: ignore  # noqa: E402
    check_mutation_score_gte,
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


def test_single_owner_no_second_strength_ladder() -> None:
    """The acceptance membrane must read kind strengths from the single config."""
    from check_track_status import load_active_track  # type: ignore  # noqa: E402
    import track_acceptance_strength_report as tas  # type: ignore  # noqa: E402

    raw = load_active_track(REPO_ROOT / "docs/governance/evidence_grades.yaml")
    kind_maturity = raw.get("kind_maturity")
    assert isinstance(kind_maturity, dict) and kind_maturity
    for kind, strength in tas.KIND_STRENGTH.items():
        assert int(kind_maturity.get(kind, -999)) == strength, (
            f"track_acceptance strength for {kind}={strength} drifted from "
            f"evidence_grades.yaml kind_maturity={kind_maturity.get(kind)}"
        )
    assert "mutation_score_gte" in tas.KIND_STRENGTH

    cli_src = (REPO_ROOT / "scripts/governance/check_claim_evidence_binding.py").read_text(
        encoding="utf-8"
    )
    assert "from check_track_status import" in cli_src and "evaluate_track" in cli_src
    assert "def evaluate_track" not in cli_src, "the thin CLI must not re-implement the evaluator"


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


def test_mutation_score_gte_is_s6() -> None:
    assert grade_of_criterion({"kind": "mutation_score_gte"}, _passing("mutation_score_gte"), {}) == 6
    assert grade_name(6).startswith("S6")


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


def test_track_meets_s6_floor_on_mutation_score(tmp_path: Path) -> None:
    report = tmp_path / "mutation_score.json"
    from dharma_swarm.spine.receipt import _utc_now  # type: ignore

    report.write_text(json.dumps({
        "score": 0.75,
        "killed": 3,
        "total": 4,
        "produced_at": _utc_now(),
    }))
    track = {
        "id": "t-mutated",
        "status": "ACTIVE",
        "owner": "@alice",
        "min_evidence_grade": 6,
        "completion_criteria": [
            {"id": "c1", "kind": "mutation_score_gte", "file": str(report),
             "threshold": 0.6, "fresh_ttl_days": 7},
        ],
    }
    r = evaluate_track(track)
    assert r["strongest_grade"] == 6
    assert r["shippable"], r["ship_blocks"]


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
    rows = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    rows[0]["command"] = "rm -rf /"            # tamper, keep stale digest
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    res = check_receipt_valid(str(log), [], expect_chain=True)
    assert not res.passed
    assert "digest mismatch" in res.detail


def test_checker_rejects_broken_chain_link(tmp_path: Path) -> None:
    log = tmp_path / "receipts.jsonl"
    append_machine_receipt(VerifiedMachineReceipt(claim_id="C1", command="x"), path=log)
    append_machine_receipt(VerifiedMachineReceipt(claim_id="C1", command="y"), path=log)
    rows = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
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


# --------------------------------------------------------------------------- #
# Mutation score report                                                       #
# --------------------------------------------------------------------------- #

def test_checker_accepts_passing_mutation_score(tmp_path: Path) -> None:
    from dharma_swarm.spine.receipt import _utc_now  # type: ignore

    report = tmp_path / "mutation_score.json"
    report.write_text(json.dumps({
        "score": 0.75,
        "killed": 3,
        "total": 4,
        "produced_at": _utc_now(),
    }))
    res = check_mutation_score_gte(str(report), 0.6, fresh_ttl_days=7)
    assert res.passed, res.detail
    assert "0.75 >= 0.60" in res.detail


def test_checker_rejects_low_mutation_score(tmp_path: Path) -> None:
    from dharma_swarm.spine.receipt import _utc_now  # type: ignore

    report = tmp_path / "mutation_score.json"
    report.write_text(json.dumps({
        "score": 0.5,
        "killed": 1,
        "total": 2,
        "produced_at": _utc_now(),
    }))
    res = check_mutation_score_gte(str(report), 0.6, fresh_ttl_days=7)
    assert not res.passed
    assert "0.50 < 0.60" in res.detail


def test_checker_rejects_stale_mutation_score(tmp_path: Path) -> None:
    report = tmp_path / "mutation_score.json"
    report.write_text(json.dumps({
        "score": 1.0,
        "killed": 2,
        "total": 2,
        "produced_at": "2000-01-01T00:00:00Z",
    }))
    res = check_mutation_score_gte(str(report), 0.6, fresh_ttl_days=7)
    assert not res.passed
    assert "stale" in res.detail


def test_mutation_score_report_builder_counts_bad_mutants_against_score() -> None:
    from run_mutation_score import build_report  # type: ignore

    report = build_report(
        {
            "killed": 3,
            "caught_by_type_check": 1,
            "survived": 1,
            "no_tests": 1,
            "timeout": 0,
            "suspicious": 0,
            "skipped": 2,
            "total": 8,
        },
        threshold=0.6,
        command="normalize-mutmut-stats",
    )
    assert report["killed"] == 4
    assert report["total"] == 6
    assert report["score"] == 0.666667
    assert report["passed"] is True
