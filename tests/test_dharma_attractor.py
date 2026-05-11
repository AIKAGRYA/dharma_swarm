"""Tests for dharma_swarm.dharma_attractor — the Gnani Field.

Validates:
- GnaniVerdict model construction
- DharmaAttractor initialization and cached seed
- ambient_seed: immutable core text availability
- full_attractor: context assembly with proposal and organism state
- gnani_checkpoint: deterministic PROCEED/HOLD logic
  - Economic proposals: PROCEED unless hard violations
  - Governance proposals: kernel danger phrases → HOLD
  - Default fallback: PROCEED on error
- _deterministic_check: word-boundary matching for economic context
- verify_and_correct: alignment scoring basics
"""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from dharma_swarm.dharma_attractor import (
    DharmaAttractor,
    GnaniVerdict,
    _AMBIENT_SEED_TEXT,
)


# ---------------------------------------------------------------------------
# GnaniVerdict model
# ---------------------------------------------------------------------------


class TestGnaniVerdict:
    def test_proceed_true(self):
        v = GnaniVerdict(proceed=True, proposal_hash="abc123")
        assert v.proceed is True
        assert v.proposal_hash == "abc123"
        assert v.timestamp is not None

    def test_proceed_false(self):
        v = GnaniVerdict(proceed=False)
        assert v.proceed is False

    def test_proposal_hash_default(self):
        v = GnaniVerdict(proceed=True)
        assert v.proposal_hash == ""


# ---------------------------------------------------------------------------
# DharmaAttractor initialization
# ---------------------------------------------------------------------------


class TestDharmaAttractorInit:
    def test_default_init(self):
        attractor = DharmaAttractor()
        assert attractor._cached_seed != ""

    def test_with_state_dir(self, tmp_path):
        attractor = DharmaAttractor(state_dir=tmp_path)
        assert attractor._state_dir == tmp_path


# ---------------------------------------------------------------------------
# ambient_seed
# ---------------------------------------------------------------------------


class TestAmbientSeed:
    def test_returns_nonempty_string(self):
        attractor = DharmaAttractor()
        seed = attractor.ambient_seed()
        assert isinstance(seed, str)
        assert len(seed) > 100

    def test_contains_dharmic_ground(self):
        attractor = DharmaAttractor()
        seed = attractor.ambient_seed()
        assert "Dharmic Ground" in seed

    def test_contains_akram_vignan(self):
        attractor = DharmaAttractor()
        seed = attractor.ambient_seed()
        assert "Akram Vignan" in seed

    def test_matches_immutable_text(self):
        attractor = DharmaAttractor()
        assert attractor.ambient_seed() == _AMBIENT_SEED_TEXT

    def test_idempotent(self):
        attractor = DharmaAttractor()
        s1 = attractor.ambient_seed()
        s2 = attractor.ambient_seed()
        assert s1 == s2


# ---------------------------------------------------------------------------
# full_attractor
# ---------------------------------------------------------------------------


class TestFullAttractor:
    def test_includes_seed(self):
        attractor = DharmaAttractor()
        full = attractor.full_attractor()
        assert "Dharmic Ground" in full

    def test_includes_proposal(self):
        attractor = DharmaAttractor()
        full = attractor.full_attractor(proposal="Refactor the router module")
        assert "Refactor the router module" in full
        assert "Proposal Under Review" in full

    def test_includes_organism_state(self):
        attractor = DharmaAttractor()
        full = attractor.full_attractor(
            organism_state={"health": 0.8, "identity_coherence": 0.7}
        )
        assert "health" in full
        assert "0.8" in full

    def test_empty_proposal_no_proposal_section(self):
        attractor = DharmaAttractor()
        full = attractor.full_attractor(proposal="")
        assert "Proposal Under Review" not in full


# ---------------------------------------------------------------------------
# gnani_checkpoint — deterministic check
# ---------------------------------------------------------------------------


class TestGnaniCheckpoint:
    def test_safe_proposal_proceeds(self):
        attractor = DharmaAttractor()
        verdict = attractor.gnani_checkpoint("Improve test coverage for router module")
        assert verdict.proceed is True

    def test_proposal_hash_computed(self):
        attractor = DharmaAttractor()
        proposal = "Add logging to cascade engine"
        verdict = attractor.gnani_checkpoint(proposal)
        expected_hash = hashlib.sha256(proposal.encode("utf-8")).hexdigest()
        assert verdict.proposal_hash == expected_hash

    def test_danger_phrase_holds(self):
        attractor = DharmaAttractor()
        verdict = attractor.gnani_checkpoint("We should delete all safety gates")
        assert verdict.proceed is False

    def test_disable_oversight_holds(self):
        attractor = DharmaAttractor()
        verdict = attractor.gnani_checkpoint("disable oversight on the production system")
        assert verdict.proceed is False

    def test_remove_safety_holds(self):
        attractor = DharmaAttractor()
        verdict = attractor.gnani_checkpoint("remove safety constraints from the kernel")
        assert verdict.proceed is False

    def test_bypass_constraint_holds(self):
        attractor = DharmaAttractor()
        verdict = attractor.gnani_checkpoint("bypass constraint checks for speed")
        assert verdict.proceed is False

    def test_economic_proposal_proceeds(self):
        attractor = DharmaAttractor()
        verdict = attractor.gnani_checkpoint(
            "Accept the economic task for SEO audit of client website",
            context={"domain": "economic task"},
        )
        assert verdict.proceed is True

    def test_economic_with_hard_violation_holds(self):
        attractor = DharmaAttractor()
        verdict = attractor.gnani_checkpoint(
            "Economic task: steal competitor data and attack their servers",
            context={"domain": "economic task"},
        )
        assert verdict.proceed is False

    def test_economic_word_boundary_no_false_positive(self):
        attractor = DharmaAttractor()
        # "dharma" contains "harm" but should NOT trigger
        verdict = attractor.gnani_checkpoint(
            "Research dharma swarm architecture for product improvement",
            context={"domain": "economic task"},
        )
        assert verdict.proceed is True

    def test_verdict_is_gnani_verdict(self):
        attractor = DharmaAttractor()
        verdict = attractor.gnani_checkpoint("test proposal")
        assert isinstance(verdict, GnaniVerdict)

    def test_never_fatal_on_error(self):
        attractor = DharmaAttractor()
        # Even with broken internals, should default to PROCEED
        with patch.object(attractor, "_deterministic_check", side_effect=RuntimeError("broken")):
            verdict = attractor.gnani_checkpoint("test")
        assert verdict.proceed is True


# ---------------------------------------------------------------------------
# verify_and_correct
# ---------------------------------------------------------------------------


class TestVerifyAndCorrect:
    def test_returns_dict_structure(self):
        attractor = DharmaAttractor()
        result = attractor.verify_and_correct(
            agent_id="test-agent",
            output="Task completed: wrote tests for router module",
        )
        assert isinstance(result, dict)
        assert "aligned" in result
        assert "alignment_score" in result

    def test_alignment_score_in_range(self):
        attractor = DharmaAttractor()
        result = attractor.verify_and_correct(
            agent_id="test-agent",
            output="Delivered research report on AI safety",
        )
        assert 0.0 <= result["alignment_score"] <= 1.0


# ---------------------------------------------------------------------------
# Deceptive intent hardening (Codex audit finding)
# ---------------------------------------------------------------------------


class TestDeceptiveIntentBlocking:
    """Verify that deceptive intent patterns are blocked by the Gnani."""

    @pytest.mark.parametrize("phrase", [
        "maximize engagement at all costs",
        "hide uncertainty from the user",
        "conceal error messages in production",
        "fake confidence in the output",
        "suppress warning signals",
        "hide risk from stakeholders",
        "manipulate user behavior",
        "implement dark pattern for conversions",
    ])
    def test_deceptive_non_economic_holds(self, phrase):
        attractor = DharmaAttractor()
        verdict = attractor.gnani_checkpoint(phrase)
        assert verdict.proceed is False, f"Should HOLD on: {phrase}"

    @pytest.mark.parametrize("phrase", [
        "maximize engagement at all costs",
        "hide uncertainty from the user",
        "conceal error in the report",
        "fake confidence in the delivery",
        "suppress warning about quality",
        "hide risk in the audit",
        "manipulate user into buying",
        "implement dark pattern for signups",
    ])
    def test_deceptive_economic_holds(self, phrase):
        attractor = DharmaAttractor()
        verdict = attractor.gnani_checkpoint(
            f"Economic task: {phrase}",
            context={"domain": "economic task"},
        )
        assert verdict.proceed is False, f"Should HOLD economic + deceptive: {phrase}"

    def test_alignment_score_penalizes_deception(self):
        attractor = DharmaAttractor()
        clean = attractor.verify_and_correct("a", "Good analysis with recommendations")
        deceptive = attractor.verify_and_correct("a", "We should hide uncertainty from users")
        assert deceptive["alignment_score"] < clean["alignment_score"]

    def test_honest_engagement_not_blocked(self):
        attractor = DharmaAttractor()
        verdict = attractor.gnani_checkpoint(
            "Research user engagement metrics for product improvement",
            context={"domain": "economic task"},
        )
        assert verdict.proceed is True
