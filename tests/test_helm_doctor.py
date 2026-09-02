"""Behavioral tests for the read-only Helm doctor's pure classification core.

Claim boundary: proves freshness/seat/report classification on injected data;
the tmux/process observation path is exercised live by scripts, not here.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
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
    rows = {
        "claude_code": {"glyph": "✓", "status": "Max plan (keychain oauth)"},
        "codex (openai-pro)": {"glyph": "✓", "status": "oauth present (chatgpt)"},
        "deepseek": {"glyph": "✓", "status": "live"},
        "anthropic": {"glyph": "$", "status": "valid · funds=0"},
        "openai": {"glyph": "~", "status": "HTTP 429 rate-limited"},
        "groq": {"glyph": "✗", "status": "HTTP 404"},
        "qwen": {"glyph": "·", "status": "qwen dir, no creds"},
    }
    fresh = doctor.key_freshness({"last_test_ts": now - 100, "rows": rows}, now=now)
    assert fresh["state"] == "fresh"
    assert fresh["live_providers"] == ["claude_code", "codex (openai-pro)", "deepseek"]

    as_list = doctor.key_freshness(
        {"last_test_ts": now - 100,
         "rows": [{"name": name, **row} for name, row in rows.items()]},
        now=now,
    )
    assert as_list["live_providers"] == fresh["live_providers"]

    stale = doctor.key_freshness({"last_test_ts": now - 5000, "rows": rows}, now=now)
    assert stale["state"] == "stale"
    assert stale["live_providers"] == fresh["live_providers"]
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
        ([], "stale", False),  # stale is informational, never punished
        ([], "unknown", False),  # unknown is typed absence, never punished
    ],
)
def test_attention_flag_is_down_only(sessions, keys_state, expected) -> None:
    report = doctor.build_report(
        sessions=sessions, keys={"state": keys_state}, seats={"state": "unknown", "detail": "-"},
    )
    assert report["attention_needed"] is expected
    assert report["authority"] == "READ_ONLY_OBSERVATION"


def test_strict_exit_only_on_down(monkeypatch, capsys) -> None:
    monkeypatch.setattr(doctor, "observe_sessions", lambda: [])
    monkeypatch.setattr(doctor, "_load_key_status", lambda: {"last_test_ts": 1.0, "rows": {}})
    assert doctor.main(["--strict", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["key_oracle"]["state"] == "stale"

    monkeypatch.setattr(
        doctor, "observe_sessions",
        lambda: [{"socket": "s", "session": "helm", "pane_alive": True, "bridge": "down"}],
    )
    assert doctor.main(["--strict", "--json"]) == 1


def test_hung_probe_reads_as_unknown_not_crash(monkeypatch) -> None:
    def _hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(doctor.subprocess, "run", _hang)
    assert doctor._tmux("CODEX_MANAGED_x", "list-panes").returncode != 0
    assert doctor._descendants(1) == []
