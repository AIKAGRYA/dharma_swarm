"""E3 micro-prediction lane — emit path, oracle-rule enforcement, incidents."""

from __future__ import annotations

import json

import pytest

import dharma_swarm.ginko_brier as gb
from dharma_swarm.chamber.predictions import (
    OracleRuleViolation,
    emit_micro_prediction,
    resolve_with_bronze,
)


@pytest.fixture(autouse=True)
def isolated_ginko(tmp_path, monkeypatch):
    """Point the EXISTING ginko store at tmp — no new truth store, no real
    ~/.dharma mutation."""
    monkeypatch.setattr(gb, "GINKO_DIR", tmp_path)
    monkeypatch.setattr(gb, "PREDICTIONS_FILE", tmp_path / "predictions.jsonl")
    monkeypatch.setattr(gb, "DASHBOARD_FILE", tmp_path / "brier_dashboard.json")
    monkeypatch.setattr(gb, "NOTIFICATIONS_FILE",
                        tmp_path / "resolved_notifications.jsonl")


def _bronze(agent="dharma_swarm.world_radar.bronze", url="https://a.example"):
    return {
        "prov": {"agent": {"id": agent, "type": "software_agent"}},
        "corroboration": {"independent_source_urls": [url]},
        "content_hash": "b" * 64,
    }


def _emit():
    return emit_micro_prediction(
        question="Will story X reach 500 points by 2026-07-14?",
        probability=0.3,
        resolve_by="2026-07-14T00:00:00Z",
        bronze_receipt_sha="a" * 64,
        resolution_criterion="hn_points('X') >= 500 in a later bronze fetch",
    )


def test_emit_records_via_existing_ginko_store():
    pred = _emit()
    assert pred.source == "chamber.zeitgeist"
    assert pred.metadata["bronze_receipt_sha"] == "a" * 64
    assert pred.metadata["resolution_criterion"]
    assert len(gb.get_pending_predictions()) == 1


def test_emit_requires_criterion_and_backpointer():
    with pytest.raises(ValueError, match="resolution_criterion"):
        emit_micro_prediction(question="q", probability=0.5,
                              resolve_by="2026-07-14T00:00:00Z",
                              bronze_receipt_sha="a" * 64,
                              resolution_criterion="  ")
    with pytest.raises(ValueError, match="bronze_receipt_sha"):
        emit_micro_prediction(question="q", probability=0.5,
                              resolve_by="2026-07-14T00:00:00Z",
                              bronze_receipt_sha="",
                              resolution_criterion="c")


def test_resolution_with_fetcher_evidence_k2_succeeds(tmp_path):
    pred = _emit()
    resolved = resolve_with_bronze(
        pred.id, 1.0,
        [_bronze(url="https://a.example"), _bronze(url="https://b.example")],
        incident_path=tmp_path / "incidents.jsonl",
    )
    assert resolved is not None and resolved.outcome == 1.0
    assert resolved.brier_score == pytest.approx((0.3 - 1.0) ** 2)
    assert not (tmp_path / "incidents.jsonl").exists()


def test_self_authored_resolution_is_incident_and_refused(tmp_path):
    pred = _emit()
    incident = tmp_path / "incidents.jsonl"
    with pytest.raises(OracleRuleViolation, match="not a fetcher organ"):
        resolve_with_bronze(
            pred.id, 1.0,
            [_bronze(agent="chamber.zeitgeist"), _bronze(url="https://b.example")],
            incident_path=incident,
        )
    lines = [json.loads(ln) for ln in incident.read_text().splitlines()]
    assert lines and lines[0]["prediction_id"] == pred.id
    assert len(gb.get_pending_predictions()) == 1  # stays UNRESOLVED


def test_insufficient_corroboration_is_refused(tmp_path):
    pred = _emit()
    with pytest.raises(OracleRuleViolation, match="k=1 < required 2"):
        resolve_with_bronze(pred.id, 1.0, [_bronze()],
                            incident_path=tmp_path / "i.jsonl")


def test_duplicate_source_urls_do_not_count_as_independent(tmp_path):
    pred = _emit()
    with pytest.raises(OracleRuleViolation, match="independent source"):
        resolve_with_bronze(
            pred.id, 1.0,
            [_bronze(url="https://same.example"), _bronze(url="https://same.example")],
            incident_path=tmp_path / "i.jsonl",
        )


@pytest.mark.parametrize("evidence", [
    [{"prov": None}, {"prov": None}],                       # present-but-null
    ["not-a-dict", "also-not"],                             # non-dict element
    [{"prov": {"agent": {"id": "x"}}, "corroboration": None},
     {"prov": {"agent": {"id": "y"}}, "corroboration": None}],
    [{"prov": {"agent": {"id": "dharma_swarm.world_radar"}},
      "corroboration": {"independent_source_urls": "not-a-list"}},
     {"prov": {"agent": {"id": "dharma_swarm.world_radar"}},
      "corroboration": {"independent_source_urls": "x"}}],
])
def test_malformed_evidence_fails_closed_not_crash(tmp_path, evidence):
    # R1-1/R3-N1: malformed bronze must raise OracleRuleViolation (with an
    # incident), never a bare AttributeError that fails open.
    pred = _emit()
    with pytest.raises(OracleRuleViolation):
        resolve_with_bronze(pred.id, 1.0, evidence,
                            incident_path=tmp_path / "i.jsonl")
    assert (tmp_path / "i.jsonl").exists()
    assert len(gb.get_pending_predictions()) == 1  # unresolved
