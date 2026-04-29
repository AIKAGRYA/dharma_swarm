"""Tests for register_disciplines: schema stability + corrects field.

Slice 0 of Plan v3 — these tests pin down the v3 RegisterMark shape so every
later slice (StrangeLoop, TelosGatekeeper, digest, identity RM) writes and
reads the same event shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.register_disciplines import (
    DisciplineResult,
    PLANES,
    RECOMMENDED_ACTIONS,
    RegisterMark,
    SEVERITIES,
    SUBJECT_TYPES,
    detect_methodological_collapse,
    flag_felt_relief,
    make_register_mark,
    write_register_mark,
)


# ---------------------------------------------------------------------------
# RegisterMark shape
# ---------------------------------------------------------------------------


class TestRegisterMarkShape:
    def test_default_mark_has_all_v3_fields(self):
        m = RegisterMark()
        d = m.to_dict()
        for key in (
            "ts", "mark_id", "plane", "discipline", "subject_type",
            "subject_id", "decision_point", "flagged", "confidence",
            "severity", "recommended_action", "actual_action", "override",
            "override_reason", "corrects", "links", "explanation", "markers",
        ):
            assert key in d, f"missing v3 field: {key}"

    def test_corrects_defaults_to_none(self):
        m = RegisterMark()
        assert m.corrects is None
        assert m.to_dict()["corrects"] is None

    def test_links_serialize_empty_when_unset(self):
        m = RegisterMark()
        assert m.to_dict()["links"] == {}

    def test_links_drop_empty_subfields_on_serialize(self):
        m = RegisterMark(links={"task_id": "t1", "artifact_path": ""})
        d = m.to_dict()
        assert d["links"] == {"task_id": "t1"}


# ---------------------------------------------------------------------------
# make_register_mark — derives defaults from DisciplineResult
# ---------------------------------------------------------------------------


class TestMakeRegisterMark:
    def test_builds_from_discipline_result(self):
        r = DisciplineResult(
            flagged=True,
            confidence=0.82,
            explanation="rescue-relief detected",
            markers=["distinction-introducing", "rescue-pressure"],
            discipline="flag_felt_relief",
        )
        m = make_register_mark(
            r,
            plane="evolution",
            subject_type="mutation",
            subject_id="mut-42",
            decision_point="strange_loop.diagnose_propose",
        )
        assert m.flagged is True
        assert m.confidence == 0.82
        assert m.discipline == "flag_felt_relief"
        assert m.plane == "evolution"
        assert m.subject_type == "mutation"
        assert m.subject_id == "mut-42"
        assert m.decision_point == "strange_loop.diagnose_propose"
        # severity for conf 0.82 → "hold"
        assert m.severity == "hold"
        # recommended_action for flag_felt_relief @ hold → "extend_measurement"
        assert m.recommended_action == "extend_measurement"
        # corrects defaults to None
        assert m.corrects is None
        # mark_id is stable, 16 hex chars
        assert isinstance(m.mark_id, str) and len(m.mark_id) == 16

    def test_severity_buckets(self):
        # not flagged → note
        r0 = DisciplineResult(flagged=False, confidence=0.0, explanation="", discipline="x")
        assert make_register_mark(r0).severity == "note"
        # 0.6 flagged → warn
        r1 = DisciplineResult(flagged=True, confidence=0.6, explanation="", discipline="x")
        assert make_register_mark(r1).severity == "warn"
        # 0.75 flagged → hold
        r2 = DisciplineResult(flagged=True, confidence=0.75, explanation="", discipline="x")
        assert make_register_mark(r2).severity == "hold"
        # 0.9 flagged → block
        r3 = DisciplineResult(flagged=True, confidence=0.9, explanation="", discipline="x")
        assert make_register_mark(r3).severity == "block"

    def test_recommended_action_per_discipline(self):
        # methodological_collapse @ flagged → rewrite
        r = DisciplineResult(flagged=True, confidence=0.8, explanation="", discipline="methodological_collapse")
        assert make_register_mark(r).recommended_action == "rewrite"
        r = detect_methodological_collapse(
            frameworks=["empirical", "contemplative"],
            conclusion="The data shows the benchmark accuracy proves it.",
        )
        assert r.flagged
        assert r.discipline == "detect_methodological_collapse"
        assert make_register_mark(r).recommended_action == "rewrite"
        # substrate_test_required @ flagged → substrate_test
        r = DisciplineResult(flagged=True, confidence=0.8, explanation="", discipline="substrate_test_required")
        assert make_register_mark(r).recommended_action == "substrate_test"
        # mahakali_gate @ block → refuse
        r = DisciplineResult(flagged=True, confidence=0.95, explanation="", discipline="mahakali_gate")
        assert make_register_mark(r).recommended_action == "refuse"
        # mahakali_gate @ hold → hold (not refuse)
        r = DisciplineResult(flagged=True, confidence=0.75, explanation="", discipline="mahakali_gate")
        assert make_register_mark(r).recommended_action == "hold"

    def test_unknown_plane_falls_back_to_register(self):
        r = DisciplineResult(flagged=False, confidence=0.0, explanation="", discipline="x")
        m = make_register_mark(r, plane="garbage")
        assert m.plane == "register"

    def test_unknown_subject_type_falls_back_to_other(self):
        r = DisciplineResult(flagged=False, confidence=0.0, explanation="", discipline="x")
        m = make_register_mark(r, subject_type="garbage")
        assert m.subject_type == "other"

    def test_explicit_kwargs_override_derived_defaults(self):
        r = DisciplineResult(flagged=True, confidence=0.9, explanation="", discipline="flag_felt_relief")
        m = make_register_mark(r, severity="warn", recommended_action="continue")
        assert m.severity == "warn"
        assert m.recommended_action == "continue"


# ---------------------------------------------------------------------------
# corrects field — the load-bearing causality link
# ---------------------------------------------------------------------------


class TestCorrectsField:
    def test_walk_back_mark_carries_corrects(self):
        # Earlier flag
        r1 = DisciplineResult(
            flagged=True, confidence=0.85, explanation="rescue-relief",
            discipline="flag_felt_relief",
        )
        first = make_register_mark(r1, subject_id="mut-99")

        # Later walk-back resolves it
        r2 = DisciplineResult(
            flagged=False, confidence=0.2, explanation="walked back",
            discipline="flag_felt_relief",
        )
        walkback = make_register_mark(
            r2,
            subject_id="mut-99",
            actual_action="reverted mutation",
            corrects=first.mark_id,
        )
        assert walkback.corrects == first.mark_id
        assert walkback.to_dict()["corrects"] == first.mark_id

    def test_override_event_can_carry_corrects(self):
        r = DisciplineResult(
            flagged=True, confidence=0.9, explanation="mahakali block",
            discipline="mahakali_gate",
        )
        first = make_register_mark(r, subject_id="essay-c1")

        r_override = DisciplineResult(
            flagged=True, confidence=0.9, explanation="proceeding anyway",
            discipline="mahakali_gate",
        )
        ov = make_register_mark(
            r_override,
            subject_id="essay-c1",
            actual_action="proceeded",
            override=True,
            override_reason="evidence packet ready",
            corrects=first.mark_id,
        )
        assert ov.override is True
        assert ov.override_reason == "evidence packet ready"
        assert ov.corrects == first.mark_id


# ---------------------------------------------------------------------------
# write_register_mark — JSONL append, never raises
# ---------------------------------------------------------------------------


class TestWriteRegisterMark:
    def test_append_jsonl(self, tmp_path: Path):
        log = tmp_path / "register_marks.jsonl"
        r = DisciplineResult(flagged=True, confidence=0.8, explanation="x", discipline="flag_felt_relief")
        m = make_register_mark(r, subject_id="s1")
        ok = write_register_mark(m, log_path=log)
        assert ok
        lines = log.read_text().strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        for key in ("ts", "mark_id", "plane", "discipline", "flagged", "corrects"):
            assert key in parsed

    def test_appends_not_overwrites(self, tmp_path: Path):
        log = tmp_path / "register_marks.jsonl"
        r = DisciplineResult(flagged=False, confidence=0.0, explanation="", discipline="x")
        for i in range(3):
            m = make_register_mark(r, subject_id=f"s{i}")
            assert write_register_mark(m, log_path=log)
        assert len(log.read_text().strip().splitlines()) == 3

    def test_creates_parent_dir(self, tmp_path: Path):
        log = tmp_path / "nested" / "deeper" / "register_marks.jsonl"
        r = DisciplineResult(flagged=False, confidence=0.0, explanation="", discipline="x")
        m = make_register_mark(r)
        assert write_register_mark(m, log_path=log)
        assert log.exists()

    def test_does_not_raise_on_unwritable_path(self, tmp_path: Path):
        # /dev/null/foo is not creatable on macOS
        bad = Path("/dev/null/cannot_create_here.jsonl")
        r = DisciplineResult(flagged=False, confidence=0.0, explanation="", discipline="x")
        m = make_register_mark(r)
        # Must NOT raise; returns False
        result = write_register_mark(m, log_path=bad)
        assert result is False


# ---------------------------------------------------------------------------
# Integration: real discipline → mark → write → read round-trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_flag_felt_relief_to_mark_to_jsonl(self, tmp_path: Path):
        log = tmp_path / "register_marks.jsonl"
        result = flag_felt_relief(
            decision_context=(
                "Hubinger counterexample shows mesa-optimizers harm despite "
                "self-modeling. The systemic-non-harm claim is refuted."
            ),
            proposed_action=(
                "Actually it's not self-modeling; the more discriminating "
                "version is witness-position. If we distinguish between "
                "sophisticated self-modeling and witness-position, the claim "
                "survives."
            ),
        )
        assert result.flagged
        m = make_register_mark(
            result,
            plane="register",
            subject_type="proposal",
            subject_id="post-hoc-rescue-001",
            decision_point="manual:test",
            actual_action="held",
        )
        assert write_register_mark(m, log_path=log)
        parsed = json.loads(log.read_text().strip())
        assert parsed["discipline"] == "flag_felt_relief"
        assert parsed["flagged"] is True
        assert parsed["severity"] in ("warn", "hold", "block")
        assert parsed["recommended_action"] in RECOMMENDED_ACTIONS
        assert parsed["plane"] in PLANES
        assert parsed["subject_type"] in SUBJECT_TYPES
        assert parsed["severity"] in SEVERITIES
        assert parsed["corrects"] is None
        assert isinstance(parsed["markers"], list)
        assert isinstance(parsed["links"], dict)
