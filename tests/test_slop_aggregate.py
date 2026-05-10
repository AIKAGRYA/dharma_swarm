"""Tests for noisy-OR aggregation + agreement cap."""

from __future__ import annotations

from dharma_swarm.slop.aggregate import (
    AGREEMENT_THRESHOLD,
    FAMILY_WEIGHTS,
    MIN_AGREEMENT,
    WARN_BAND_CAP,
    aggregate_path,
    aggregate_results,
    family_score,
)
from dharma_swarm.slop.models import (
    DetectorFamily,
    DetectorResult,
    Finding,
    Severity,
)


def make_finding(
    path: str,
    family: DetectorFamily,
    confidence: float,
    tool: str = "test-tool",
    issue_type: str = "test_issue",
) -> Finding:
    return Finding(
        tool=tool,
        family=family,
        issue_type=issue_type,
        path=path,
        line=1,
        symbol=None,
        severity=Severity.MEDIUM,
        confidence=confidence,
        evidence="test",
    )


class TestFamilyScore:
    def test_empty_returns_zero(self) -> None:
        assert family_score([]) == 0.0

    def test_single_finding(self) -> None:
        f = make_finding("a.py", DetectorFamily.AI_SLOP, 0.7)
        assert family_score([f]) == 0.7

    def test_takes_max(self) -> None:
        fs = [
            make_finding("a.py", DetectorFamily.AI_SLOP, 0.3),
            make_finding("a.py", DetectorFamily.AI_SLOP, 0.9),
            make_finding("a.py", DetectorFamily.AI_SLOP, 0.5),
        ]
        assert family_score(fs) == 0.9


class TestAggregatePath:
    def test_empty_findings_zero_score(self) -> None:
        s = aggregate_path("a.py", [])
        assert s.p == 0.0
        assert s.p_raw == 0.0
        assert s.agreement == 0
        assert s.capped is False

    def test_single_family_below_warn_cap_uncapped(self) -> None:
        f = make_finding("a.py", DetectorFamily.AI_SLOP, 0.5)
        s = aggregate_path("a.py", [f])
        assert s.agreement == 1
        assert s.capped is False
        expected_p = round(1.0 - (1.0 - 0.20 * 0.5), 4)
        assert s.p == expected_p

    def test_single_family_high_score_capped_at_warn_band(self) -> None:
        f = make_finding("a.py", DetectorFamily.STRUCTURE, 0.99)
        s = aggregate_path("a.py", [f])
        assert s.agreement == 1
        assert s.p_raw < 0.50
        assert s.capped is False or s.p == WARN_BAND_CAP

    def test_two_families_agreement_uncaps(self) -> None:
        fs = [
            make_finding("a.py", DetectorFamily.STRUCTURE, 0.9),
            make_finding("a.py", DetectorFamily.AI_SLOP, 0.9),
        ]
        s = aggregate_path("a.py", fs)
        assert s.agreement >= MIN_AGREEMENT
        assert s.capped is False
        assert s.p == s.p_raw

    def test_three_families_high_confidence_in_warn_band(self) -> None:
        fs = [
            make_finding("a.py", DetectorFamily.STRUCTURE, 0.9),
            make_finding("a.py", DetectorFamily.AI_SLOP, 0.9),
            make_finding("a.py", DetectorFamily.DEAD_CODE, 0.9),
        ]
        s = aggregate_path("a.py", fs)
        assert s.agreement == 3
        assert s.capped is False
        assert 0.30 <= s.p < 0.50

    def test_five_families_high_confidence_can_block(self) -> None:
        fs = [
            make_finding("a.py", DetectorFamily.STRUCTURE, 0.9),
            make_finding("a.py", DetectorFamily.AI_SLOP, 0.9),
            make_finding("a.py", DetectorFamily.DEAD_CODE, 0.9),
            make_finding("a.py", DetectorFamily.COMPLEXITY, 0.9),
            make_finding("a.py", DetectorFamily.BOUNDARY, 0.9),
        ]
        s = aggregate_path("a.py", fs)
        assert s.agreement == 5
        assert s.p >= 0.50
        assert s.capped is False

    def test_seven_families_strong_evidence_reaches_block_not_refactor(self) -> None:
        """Codex's weights are intentionally conservative: even 7 families at
        0.95 confidence stay in BLOCK band (0.50-0.80), not REFACTOR (>=0.80).
        REFACTOR is reserved for screaming evidence (most/all 11 families
        agreeing at high confidence), preventing trigger-happy auto-PRs.
        """
        fs = [
            make_finding("a.py", fam, 0.95)
            for fam in (
                DetectorFamily.STRUCTURE,
                DetectorFamily.AI_SLOP,
                DetectorFamily.DEAD_CODE,
                DetectorFamily.COMPLEXITY,
                DetectorFamily.BOUNDARY,
                DetectorFamily.SECURITY,
                DetectorFamily.DUPLICATION,
            )
        ]
        s = aggregate_path("a.py", fs)
        assert 0.50 <= s.p < 0.80
        assert s.capped is False

    def test_all_eleven_families_extreme_can_refactor(self) -> None:
        fs = [make_finding("a.py", fam, 0.99) for fam in DetectorFamily]
        s = aggregate_path("a.py", fs)
        assert s.p >= 0.80

    def test_below_agreement_threshold_does_not_count(self) -> None:
        fs = [
            make_finding("a.py", DetectorFamily.STRUCTURE, AGREEMENT_THRESHOLD - 0.01),
            make_finding("a.py", DetectorFamily.AI_SLOP, AGREEMENT_THRESHOLD - 0.01),
        ]
        s = aggregate_path("a.py", fs)
        assert s.agreement == 0

    def test_noisy_or_monotone_with_added_evidence(self) -> None:
        f1 = make_finding("a.py", DetectorFamily.STRUCTURE, 0.5)
        f2 = make_finding("a.py", DetectorFamily.AI_SLOP, 0.5)
        s_one = aggregate_path("a.py", [f1])
        s_two = aggregate_path("a.py", [f1, f2])
        assert s_two.p_raw >= s_one.p_raw

    def test_warn_band_cap_value(self) -> None:
        assert WARN_BAND_CAP == 0.49

    def test_min_agreement_is_two(self) -> None:
        assert MIN_AGREEMENT == 2


class TestAggregateResults:
    def test_groups_by_path(self) -> None:
        r = DetectorResult(
            tool="t",
            family=DetectorFamily.AI_SLOP,
            findings=[
                make_finding("a.py", DetectorFamily.AI_SLOP, 0.5),
                make_finding("b.py", DetectorFamily.AI_SLOP, 0.7),
            ],
            duration_sec=0.1,
            exit_code=0,
        )
        scores = aggregate_results([r])
        assert set(scores.keys()) == {"a.py", "b.py"}
        assert scores["b.py"].family_scores["ai_slop"] == 0.7

    def test_combines_across_detector_results(self) -> None:
        r1 = DetectorResult(
            tool="t1",
            family=DetectorFamily.STRUCTURE,
            findings=[make_finding("a.py", DetectorFamily.STRUCTURE, 0.8)],
            duration_sec=0.1,
            exit_code=0,
        )
        r2 = DetectorResult(
            tool="t2",
            family=DetectorFamily.AI_SLOP,
            findings=[make_finding("a.py", DetectorFamily.AI_SLOP, 0.7)],
            duration_sec=0.1,
            exit_code=0,
        )
        scores = aggregate_results([r1, r2])
        assert scores["a.py"].agreement == 2
        assert scores["a.py"].capped is False


class TestWeights:
    def test_all_families_have_weights(self) -> None:
        for f in DetectorFamily:
            assert f in FAMILY_WEIGHTS, f"missing weight for {f}"

    def test_weights_in_unit_interval(self) -> None:
        for w in FAMILY_WEIGHTS.values():
            assert 0.0 < w <= 1.0
