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

import dataclasses
import json
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))

from check_track_status import (  # type: ignore  # noqa: E402
    CriterionResult,
    check_mutation_score_gte,
    check_receipt_valid,
    evaluate_track,
    grade_name,
    grade_of_criterion,
)

from dharma_swarm.spine.receipt import (  # noqa: E402
    VerifiedMachineReceipt,
    _canonical_json as _spine_canonical_json,
    _read_verified_machine_receipt_chain,
    _stable_digest as _spine_stable_digest,
    append_machine_receipt,
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


def test_resolve_enforcement_precedence(tmp_path: Path) -> None:
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
    pattern = tmp_path / "AI-M1.yaml"
    pattern.write_text(json.dumps({"stage": "enforced"}), encoding="utf-8")
    assert binding_stage(pattern) == "enforced"
    assert binding_stage(tmp_path / "missing.json") == "advisory"
    # The shipped AI-M1 pattern is advisory today, so the bare gate stays advisory.
    assert binding_stage() == "advisory"


def test_receipt_command_line_records_actual_flags() -> None:
    from check_claim_evidence_binding import receipt_command_line  # type: ignore  # noqa: E402

    assert (
        receipt_command_line(
            ["scripts/governance/check_claim_evidence_binding.py", "--warn-only", "--emit-receipt"],
            executable="python3",
        )
        == "python3 scripts/governance/check_claim_evidence_binding.py --warn-only --emit-receipt"
    )


def test_mutation_score_gte_grades_s6_and_reads_report(tmp_path: Path) -> None:
    """S6 (P3-09) is ACTIVE: a passing mutation_score_gte grades S6, and the gate
    READS a mutation-score report — above threshold passes; below / missing /
    stale fail (fail-closed). The slow mutmut run that produces the report is a
    separate `make mutation-test` step (the gate never runs mutmut inline)."""

    assert grade_of_criterion({"kind": "mutation_score_gte"}, _passing("mutation_score_gte"), {}) == 6
    assert grade_name(6).startswith("S6")

    rpt = tmp_path / "mutation_score.json"
    rpt.write_text(
        json.dumps(
            {
                "score": 0.72,
                "killed": 36,
                "total": 50,
                "produced_at": "2026-06-25T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    assert check_mutation_score_gte(str(rpt), 0.6).passed
    assert not check_mutation_score_gte(str(rpt), 0.8).passed
    assert not check_mutation_score_gte(str(tmp_path / "nope.json"), 0.6).passed
    old = tmp_path / "old.json"
    old.write_text(
        json.dumps({"score": 0.99, "produced_at": "2020-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    assert not check_mutation_score_gte(str(old), 0.6, fresh_ttl_days=1).passed


def test_run_mutation_score_build_report() -> None:
    """The mutmut-3.5 runner projects `mutmut export-cicd-stats` into the report
    the S6 gate reads."""
    from run_mutation_score import build_report  # type: ignore  # noqa: E402

    stats = {
        "killed": 36,
        "caught_by_type_check": 0,
        "survived": 12,
        "timeout": 1,
        "suspicious": 1,
        "skipped": 4,
        "total": 54,
    }
    report = build_report(stats, threshold=0.6, command="mutmut run")
    assert report["killed"] == 36 and report["total"] == 50
    assert report["score"] == 0.72 and report["passed"] is True
    assert "produced_at" in report
    assert build_report({"total": 0}, threshold=0.6, command="x")["score"] == 0.0


def test_single_owner_no_second_strength_ladder() -> None:
    """Anti-drift guard from the #685/#693/#695 convergence weave: exactly ONE
    source of kind->strength. track_acceptance_strength_report reads its strengths
    from evidence_grades.yaml (the single config), NOT a hard-coded second ladder
    that can silently diverge (the reviewed defect). And the thin CLI consumes
    evaluate_track — it never re-implements the verdict (the only real drift risk
    is a future second evaluator; this test fails if one appears)."""
    from check_track_status import load_active_track  # type: ignore  # noqa: E402
    import track_acceptance_strength_report as tas  # type: ignore  # noqa: E402

    raw = load_active_track(REPO_ROOT / "docs/governance/evidence_grades.yaml")
    kind_maturity = raw.get("kind_maturity")
    assert isinstance(kind_maturity, dict) and kind_maturity, (
        "evidence_grades.yaml must carry kind_maturity (the single source)"
    )
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


def test_empty_grade_config_preserves_builtin_ladder(tmp_path: Path) -> None:
    import check_track_status as cts  # type: ignore  # noqa: E402

    old_path = cts.EVIDENCE_GRADES_PATH
    old_cache = cts._GRADE_LADDER_CACHE
    try:
        grade_file = tmp_path / "evidence_grades.yaml"
        grade_file.write_text("schema_version: 1\ngrades: []\n", encoding="utf-8")
        cts.EVIDENCE_GRADES_PATH = grade_file
        cts._GRADE_LADDER_CACHE = None
        assert (
            grade_of_criterion(
                {"kind": "test_passes", "oracle_source": "ci"},
                _passing("test_passes"),
                {},
            )
            == 3
        )
        assert (
            grade_of_criterion(
                {"kind": "commit_on_main"},
                _passing("commit_on_main"),
                {},
            )
            == 2
        )
    finally:
        cts.EVIDENCE_GRADES_PATH = old_path
        cts._GRADE_LADDER_CACHE = old_cache


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
            {
                "id": "c1",
                "kind": "file_contains",
                "file": "docs/governance/evidence_grades.yaml",
                "pattern": "grades",
            },
        ],
    }
    result = evaluate_track(track)
    assert result["strongest_grade"] == 1
    assert result["min_evidence_grade"] == 2
    assert not result["shippable"]
    assert any("strongest evidence" in block for block in result["ship_blocks"])


def test_track_meets_floor_on_receipt_valid_s2(tmp_path: Path) -> None:
    # Deterministic S2 evidence without depending on git ancestry: a valid
    # chained machine receipt (receipt_valid -> S2, a RIGOROUS kind). Proves the
    # graded conjunct is satisfied when strongest_grade meets the floor.
    log = tmp_path / "receipt.jsonl"
    append_machine_receipt(
        VerifiedMachineReceipt(claim_id="C1", command="x", exit_code=0), path=log
    )
    track = {
        "id": "t-landed",
        "status": "ACTIVE",
        "owner": "@alice",
        "min_evidence_grade": 2,
        "completion_criteria": [
            {
                "id": "c1",
                "kind": "receipt_valid",
                "file": str(log),
                "requires_keys": ["claim_id"],
                "expect_chain": True,
            },
        ],
    }
    result = evaluate_track(track)
    assert result["strongest_grade"] >= 2
    assert not any("strongest evidence" in block for block in result["ship_blocks"])
    assert result["shippable"]


def test_track_meets_s6_floor_on_mutation_score(tmp_path: Path) -> None:
    from dharma_swarm.spine.receipt import _utc_now  # type: ignore

    report = tmp_path / "mutation_score.json"
    report.write_text(
        json.dumps(
            {
                "score": 0.75,
                "killed": 3,
                "total": 4,
                "produced_at": _utc_now(),
            }
        ),
        encoding="utf-8",
    )
    track = {
        "id": "t-mutated",
        "status": "ACTIVE",
        "owner": "@alice",
        "min_evidence_grade": 6,
        "completion_criteria": [
            {
                "id": "c1",
                "kind": "mutation_score_gte",
                "file": str(report),
                "threshold": 0.6,
                "fresh_ttl_days": 7,
            },
        ],
    }
    result = evaluate_track(track)
    assert result["strongest_grade"] == 6
    assert result["shippable"], result["ship_blocks"]


def test_grade_name_is_human_readable() -> None:
    assert grade_name(0).startswith("S0")
    assert grade_name(2).startswith("S2")


# --------------------------------------------------------------------------- #
# VerifiedMachineReceipt: chain, digest, freshness                            #
# --------------------------------------------------------------------------- #


def test_machine_receipt_roundtrips_and_chains(tmp_path: Path) -> None:
    log = tmp_path / "receipts.jsonl"
    c1 = append_machine_receipt(
        VerifiedMachineReceipt(claim_id="C1", command="pytest a", exit_code=0), path=log
    )
    c2 = append_machine_receipt(
        VerifiedMachineReceipt(claim_id="C1", command="pytest b", exit_code=0), path=log
    )
    assert c1.verify() and c2.verify()
    assert c2.prev_digest == c1.digest
    assert c1.prev_digest == ""


def test_checker_accepts_intact_chain(tmp_path: Path) -> None:
    log = tmp_path / "receipts.jsonl"
    append_machine_receipt(
        VerifiedMachineReceipt(claim_id="C1", command="x", exit_code=0), path=log
    )
    res = check_receipt_valid(str(log), ["claim_id", "command"], expect_chain=True)
    assert res.passed, res.detail


def test_checker_rejects_tampered_digest(tmp_path: Path) -> None:
    log = tmp_path / "receipts.jsonl"
    append_machine_receipt(
        VerifiedMachineReceipt(claim_id="C1", command="x", exit_code=0), path=log
    )
    rows = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    rows[0]["command"] = "rm -rf /"
    log.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    res = check_receipt_valid(str(log), [], expect_chain=True)
    assert not res.passed
    assert "digest mismatch" in res.detail


def test_checker_rejects_non_object_chain_row(tmp_path: Path) -> None:
    log = tmp_path / "receipts.jsonl"
    log.write_text("[]\n", encoding="utf-8")
    res = check_receipt_valid(str(log), [], expect_chain=True)
    assert not res.passed
    assert "not a JSON object" in res.detail


def test_checker_rejects_missing_genesis_anchor(tmp_path: Path) -> None:
    from dharma_swarm.spine.receipt import _stable_digest  # type: ignore

    log = tmp_path / "receipts.jsonl"
    row = {"claim_id": "C1", "command": "x", "prev_digest": "external"}
    row["digest"] = _stable_digest(row)
    log.write_text(json.dumps(row) + "\n", encoding="utf-8")
    res = check_receipt_valid(str(log), [], expect_chain=True)
    assert not res.passed
    assert "genesis anchor" in res.detail


def test_checker_rejects_broken_chain_link(tmp_path: Path) -> None:
    from dharma_swarm.spine.receipt import _stable_digest  # type: ignore

    log = tmp_path / "receipts.jsonl"
    append_machine_receipt(VerifiedMachineReceipt(claim_id="C1", command="x"), path=log)
    append_machine_receipt(VerifiedMachineReceipt(claim_id="C1", command="y"), path=log)
    rows = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    # Re-digest row 1 with a wrong prev_digest so its own digest stays valid but
    # the link is broken.
    rows[1]["prev_digest"] = "deadbeef"
    payload = {k: v for k, v in rows[1].items() if k != "digest"}
    rows[1]["digest"] = _stable_digest(payload)
    log.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    res = check_receipt_valid(str(log), [], expect_chain=True)
    assert not res.passed
    assert "broken" in res.detail


def test_append_machine_receipt_refuses_to_extend_tampered_earlier_row(tmp_path: Path) -> None:
    log = tmp_path / "receipts.jsonl"
    append_machine_receipt(VerifiedMachineReceipt(claim_id="C1", command="x"), path=log)
    append_machine_receipt(VerifiedMachineReceipt(claim_id="C1", command="y"), path=log)
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[0]["command"] = "tampered earlier row"
    log.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="row 0 digest is broken"):
        append_machine_receipt(VerifiedMachineReceipt(claim_id="C1", command="z"), path=log)


def test_checker_rejects_stale_receipt(tmp_path: Path) -> None:
    from dharma_swarm.spine.receipt import _stable_digest  # type: ignore

    log = tmp_path / "receipt.json"
    row = {"claim_id": "C1", "produced_at": "2000-01-01T00:00:00Z"}
    row["digest"] = _stable_digest({k: v for k, v in row.items() if k != "digest"})
    log.write_text(json.dumps(row), encoding="utf-8")
    res = check_receipt_valid(str(log), ["claim_id"], expect_digest=True, fresh_ttl_days=7)
    assert not res.passed
    assert "stale" in res.detail


def test_checker_accepts_fresh_single_receipt(tmp_path: Path) -> None:
    from dharma_swarm.spine.receipt import _stable_digest, _utc_now  # type: ignore

    log = tmp_path / "receipt.json"
    row = {"claim_id": "C1", "produced_at": _utc_now()}
    row["digest"] = _stable_digest({k: v for k, v in row.items() if k != "digest"})
    log.write_text(json.dumps(row), encoding="utf-8")
    res = check_receipt_valid(str(log), ["claim_id"], expect_digest=True, fresh_ttl_days=7)
    assert res.passed, res.detail


# --------------------------------------------------------------------------- #
# Mutation score report                                                       #
# --------------------------------------------------------------------------- #


def test_checker_accepts_passing_mutation_score(tmp_path: Path) -> None:
    from dharma_swarm.spine.receipt import _utc_now  # type: ignore

    report = tmp_path / "mutation_score.json"
    report.write_text(
        json.dumps(
            {
                "score": 0.75,
                "killed": 3,
                "total": 4,
                "produced_at": _utc_now(),
            }
        ),
        encoding="utf-8",
    )
    res = check_mutation_score_gte(str(report), 0.6, fresh_ttl_days=7)
    assert res.passed, res.detail
    assert "0.75 >= 0.60" in res.detail


def test_checker_rejects_low_mutation_score(tmp_path: Path) -> None:
    from dharma_swarm.spine.receipt import _utc_now  # type: ignore

    report = tmp_path / "mutation_score.json"
    report.write_text(
        json.dumps(
            {
                "score": 0.5,
                "killed": 1,
                "total": 2,
                "produced_at": _utc_now(),
            }
        ),
        encoding="utf-8",
    )
    res = check_mutation_score_gte(str(report), 0.6, fresh_ttl_days=7)
    assert not res.passed
    assert "0.50 < 0.60" in res.detail


def test_checker_rejects_stale_mutation_score(tmp_path: Path) -> None:
    report = tmp_path / "mutation_score.json"
    report.write_text(
        json.dumps(
            {
                "score": 1.0,
                "killed": 2,
                "total": 2,
                "produced_at": "2000-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
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


# --------------------------------------------------------------------------- #
# Tamper battery: kills the mutation survivors in the machine-receipt verifier #
# (_read_verified_machine_receipt_chain + VerifiedMachineReceipt.verify). The  #
# base mutation smoke left 41 survivors (0.64) concentrated in the chain path; #
# these three relations pin each failure edge one test per edge.              #
# --------------------------------------------------------------------------- #


_COVERED_FIELDS = [
    f.name for f in dataclasses.fields(VerifiedMachineReceipt) if f.name != "digest"
]


def _distinct_value(value: object) -> object:
    """A value of the same shape that is guaranteed to differ from ``value``."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return value + "X"
    if isinstance(value, dict):
        return {**value, "_tamper": "1"}
    if value is None:
        return "not-none"
    return value  # pragma: no cover - no other field types on the dataclass


@pytest.mark.parametrize("field_name", _COVERED_FIELDS)
def test_mutating_any_covered_field_breaks_verify(field_name: str) -> None:
    """Completeness relation: the digest covers EVERY field except ``digest``,
    so mutating any one of them after with_chain() must flip verify() to False.
    A digest that ignores a field (a dropped term in the payload) is caught by
    the corresponding parametrization."""
    base = VerifiedMachineReceipt(
        claim_id="C1",
        command="pytest -k thing",
        cwd="/repo",
        git_sha="abc123",
        git_dirty=False,
        actor="agent",
        model="opus",
        exit_code=0,
        stdout_stderr_hash="deadbeef",
        finished_at="2026-01-01T00:00:00Z",
        generated_by="gen",
        verified_by="ver",
        tool_versions={"python": "3.13"},
        artifact_hashes={"a.txt": "1"},
        attributes={"prov:wasGeneratedBy": "x"},
    ).with_chain("")
    assert base.verify()

    tampered = dataclasses.replace(
        base, **{field_name: _distinct_value(getattr(base, field_name))}
    )
    assert not tampered.verify(), f"mutating {field_name} did not break verify()"


def _valid_chain_lines(count: int) -> list[str]:
    prev = ""
    lines: list[str] = []
    for i in range(count):
        receipt = VerifiedMachineReceipt(
            claim_id=f"C{i}", command=f"cmd-{i}", exit_code=i
        ).with_chain(prev)
        prev = receipt.digest
        lines.append(_spine_canonical_json(receipt.to_dict()))
    return lines


_VALID_CHAIN_TEXT = "\n".join(_valid_chain_lines(3)) + "\n"
_VALID_CHAIN_BYTES = _VALID_CHAIN_TEXT.encode("utf-8")
_VALID_CHAIN_ROWS = [
    json.loads(line) for line in _VALID_CHAIN_TEXT.splitlines() if line.strip()
]


@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    pos=st.integers(min_value=0, max_value=len(_VALID_CHAIN_BYTES) - 1),
    new_byte=st.integers(min_value=0, max_value=255),
)
def test_single_byte_flip_is_never_silently_accepted(
    tmp_path: Path, pos: int, new_byte: int
) -> None:
    """Metamorphic property that cannot be satisfied by error-text theater: flip
    ANY one byte of a valid chain and the read must either raise, or return the
    byte-identical receipt rows (a benign line-separator flip that changed no
    payload). What it must NEVER do is return DIFFERENT rows without raising —
    that is silent tamper acceptance and kills the whole broken-digest / broken-
    link mutant class at once."""
    original = _VALID_CHAIN_BYTES
    if new_byte == original[pos]:
        return  # not a mutation
    mutated = bytearray(original)
    mutated[pos] = new_byte
    log = tmp_path / "flip.jsonl"
    log.write_bytes(bytes(mutated))

    try:
        rows = _read_verified_machine_receipt_chain(log)
    except ValueError:
        return  # tamper detected -- the intended behavior
    assert rows == _VALID_CHAIN_ROWS, (
        f"byte flip at {pos} changed receipt content but was accepted silently"
    )


def _row_with_valid_digest(payload: dict) -> dict:
    row = dict(payload)
    row["digest"] = _spine_stable_digest(payload)
    return row


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(_spine_canonical_json(row) for row in rows) + "\n", encoding="utf-8"
    )


def test_reader_rejects_non_json_line(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    log.write_text("this is not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-JSON"):
        _read_verified_machine_receipt_chain(log)


def test_reader_rejects_non_object_row(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    log.write_text("[1, 2, 3]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a JSON object"):
        _read_verified_machine_receipt_chain(log)


def test_reader_rejects_empty_digest(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    row = {"claim_id": "C0", "command": "x", "prev_digest": "", "digest": ""}
    _write_rows(log, [row])
    with pytest.raises(ValueError, match="digest is broken"):
        _read_verified_machine_receipt_chain(log)


def test_reader_rejects_nonempty_wrong_digest(tmp_path: Path) -> None:
    """The `or`->`and` survivor: a non-empty but WRONG digest must be rejected.
    With `and`, `not stored` is False and the check short-circuits, silently
    accepting a forged digest."""
    log = tmp_path / "log.jsonl"
    row = {"claim_id": "C0", "command": "x", "prev_digest": "", "digest": "0" * 64}
    _write_rows(log, [row])
    with pytest.raises(ValueError, match="digest is broken"):
        _read_verified_machine_receipt_chain(log)


def test_reader_rejects_row0_nonempty_prev_digest(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    row = _row_with_valid_digest(
        {"claim_id": "C0", "command": "x", "prev_digest": "deadbeef"}
    )
    _write_rows(log, [row])
    with pytest.raises(ValueError, match="non-empty prev_digest"):
        _read_verified_machine_receipt_chain(log)


def test_reader_rejects_broken_chain_link(tmp_path: Path) -> None:
    """The `!=`->`==` survivor: row 1 whose own digest is valid but whose
    prev_digest does not match row 0's digest must be rejected."""
    log = tmp_path / "log.jsonl"
    row0 = _row_with_valid_digest({"claim_id": "C0", "command": "x", "prev_digest": ""})
    row1 = _row_with_valid_digest(
        {"claim_id": "C1", "command": "y", "prev_digest": "deadbeef"}
    )
    _write_rows(log, [row0, row1])
    with pytest.raises(ValueError, match="prev_digest is broken"):
        _read_verified_machine_receipt_chain(log)


def test_reader_accepts_valid_multirow_chain(tmp_path: Path) -> None:
    """Negative control: a genuinely valid multi-row chain must NOT raise and
    must return every row. This kills always-raise mutants and pins that the
    correct `!=` link check accepts a matching link."""
    log = tmp_path / "log.jsonl"
    log.write_text(_VALID_CHAIN_TEXT, encoding="utf-8")
    rows = _read_verified_machine_receipt_chain(log)
    assert len(rows) == 3
    assert [r["claim_id"] for r in rows] == ["C0", "C1", "C2"]


def test_reader_skips_blank_lines(tmp_path: Path) -> None:
    """Blank lines are ignored, not treated as broken rows (guards the
    `if not line.strip(): continue` edge)."""
    log = tmp_path / "log.jsonl"
    lines = _valid_chain_lines(2)
    log.write_text(lines[0] + "\n\n   \n" + lines[1] + "\n", encoding="utf-8")
    rows = _read_verified_machine_receipt_chain(log)
    assert len(rows) == 2
