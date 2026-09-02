"""Behavioral tests for the read-only Helm doctor's pure classification core.

Claim boundary: proves freshness/seat/report classification on injected data;
the tmux/process observation path is exercised live by scripts, not here.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "helm_doctor",
    Path(__file__).resolve().parents[1] / "scripts" / "verify" / "helm_doctor.py",
)
doctor = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(doctor)


def test_key_freshness_typed_states() -> None:
    now = 1_000_000.0
    fresh = doctor.key_freshness(
        {"last_test_ts": now - 100,
         "rows": {"claude_code": {"status": "live"}, "kimi_code": {"status": "auth-fail"}}},
        now=now,
    )
    assert fresh["state"] == "fresh"
    assert fresh["live_providers"] == ["claude_code"]

    stale = doctor.key_freshness({"last_test_ts": now - 5000}, now=now)
    assert stale["state"] == "stale"
    assert "dkeys test" in stale["detail"]

    assert doctor.key_freshness(None, now=now)["state"] == "unknown"
    assert doctor.key_freshness({}, now=now)["state"] == "unknown"


def test_seat_truth_never_invents_counts(tmp_path: Path) -> None:
    assert doctor.seat_truth(None)["state"] == "unknown"

    bad = tmp_path / "seat.json"
    bad.write_text("{not json", encoding="utf-8")
    assert doctor.seat_truth(bad)["state"] == "unknown"

    untyped = tmp_path / "untyped.json"
    untyped.write_text(json.dumps({"on_call_count": "0", "route_verifications": []}),
                       encoding="utf-8")
    assert doctor.seat_truth(untyped)["state"] == "unknown"

    good = tmp_path / "good.json"
    good.write_text(json.dumps({"on_call_count": 0,
                                "route_verifications": [{}] * 7,
                                "state": "LIVE_DEGRADED"}),
                    encoding="utf-8")
    reported = doctor.seat_truth(good)
    assert (reported["state"], reported["verified"], reported["total"]) == ("reported", 0, 7)


@pytest.mark.parametrize(
    ("sessions", "keys_state", "expected"),
    [
        ([{"socket": "s", "session": "x", "pane_alive": True, "bridge": "live"}], "fresh", False),
        ([{"socket": "s", "session": "x", "pane_alive": True, "bridge": "down"}], "fresh", True),
        ([], "stale", True),
        ([], "unknown", False),  # unknown is typed absence, never punished
    ],
)
def test_attention_flag_is_down_or_stale_only(sessions, keys_state, expected) -> None:
    report = doctor.build_report(
        sessions=sessions, keys={"state": keys_state}, seats={"state": "unknown", "detail": "-"},
    )
    assert report["attention_needed"] is expected
    assert report["authority"] == "READ_ONLY_OBSERVATION"
