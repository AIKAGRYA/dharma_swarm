"""Tests for scripts/governance/track_coherence.py — the unified coherence projection."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

_MOD = Path(__file__).resolve().parents[1] / "scripts" / "governance" / "track_coherence.py"
_spec = importlib.util.spec_from_file_location("track_coherence", _MOD)
tc = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules["track_coherence"] = tc
_spec.loader.exec_module(tc)


def _write_audit(d: Path, name: str, opinion: str, holds: bool, tid: str = "t1"):
    (d / f"{name}.audit.json").write_text(json.dumps({
        "schema": "dharma_track_audit.v1",
        "tracks": {tid: {"audit_opinion": opinion, "completion_claim_holds": holds}},
    }))


def test_audit_consensus_majority_and_conservative_tiebreak(tmp_path, monkeypatch):
    monkeypatch.setattr(tc, "AUDIT_DIR", tmp_path)
    _write_audit(tmp_path, "a", "CLEAN", True)
    _write_audit(tmp_path, "b", "QUALIFIED", True)
    _write_audit(tmp_path, "c", "QUALIFIED", False)
    con = tc.audit_consensus()["t1"]
    assert con["opinion"] == "QUALIFIED"     # plurality
    assert con["claim_holds"] is True        # 2/3 hold
    assert con["holds_votes"] == "2/3"
    assert con["runs"] == 3


def test_audit_consensus_tie_breaks_to_worse(tmp_path, monkeypatch):
    monkeypatch.setattr(tc, "AUDIT_DIR", tmp_path)
    _write_audit(tmp_path, "a", "CLEAN", True)
    _write_audit(tmp_path, "b", "ADVERSE", False)
    con = tc.audit_consensus()["t1"]
    assert con["opinion"] == "ADVERSE"       # 1-1 tie -> more conservative
    assert con["claim_holds"] is False       # 1/2 is not > half


def test_days_since_handles_bad_input():
    assert tc._days_since(None) is None
    assert tc._days_since("not-a-date") is None
    assert isinstance(tc._days_since("2026-01-01"), int)


def test_every_member_maps_to_one_umbrella():
    members = [m for u in tc.UMBRELLAS.values() for m in u["members"]]
    assert len(members) == len(set(members))      # no track in two umbrellas
    for u in tc.UMBRELLAS.values():
        assert u["keystone"] in u["members"]


def test_build_smoke_structure_and_invariants():
    data = tc.build(tc._load_checker())
    assert set(data) >= {"portfolio", "umbrellas", "tracks", "generated_at"}
    states = set(tc.STATE_ORDER)
    for t in data["tracks"]:
        assert t["coherence_state"] in states
        assert t["umbrella"] in tc.UMBRELLAS or t["umbrella"] is None
        assert "/" in t["presence"]
    # Umbrella rollup is the worst (lowest STATE_ORDER index) of its members.
    by_id = {t["id"]: t for t in data["tracks"]}
    for u in data["umbrellas"]:
        member_states = [by_id[m]["coherence_state"] for m in u["members"]]
        worst = min(member_states, key=lambda s: tc.STATE_ORDER.index(s))
        assert u["rollup_state"] == worst


def test_run_writes_artifacts():
    rc = tc.run(argparse.Namespace(json=False))
    assert rc == 0
    assert tc.OUT_JSON.exists() and tc.OUT_MD.exists()
