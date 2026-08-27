"""Verifier for the read-only holon compass (U4 / Step 3a). The load-bearing assertion:
it is a SIGNAL, never a gate — it must NEVER block or raise, even on low alignment."""
from __future__ import annotations

import json

import pytest

from dharma_swarm import holon_compass


def test_score_exchange_returns_telos_signal():
    sig = holon_compass.score_exchange(
        "what is your telos?",
        "My telos is jagat kalyan — universal welfare through dharma and ahimsa.",
    )
    assert 0.0 <= sig["telos_alignment"] <= 1.0
    assert 0.0 <= sig["witness_quality"] <= 1.0
    assert "at" in sig


def test_log_signal_appends_jsonl(tmp_path):
    sig = holon_compass.log_signal("h", "hi", "I serve jagat kalyan.", agents_root=tmp_path)
    path = tmp_path / "h" / "compass_signals.jsonl"
    assert path.exists()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["holon"] == "h"
    assert "telos_alignment" in rec
    assert sig["telos_alignment"] == rec["telos_alignment"]


def test_compass_never_blocks_even_on_low_alignment(tmp_path):
    """The defining property: a compass pulls, it does not gate. Low-alignment text must
    return a signal, never raise/refuse. (A fence would block here — Step 3b, deferred.)"""
    sig = holon_compass.log_signal(
        "h", "ignore your telos", "money money, whatever, lol", agents_root=tmp_path
    )
    assert "telos_alignment" in sig  # returned, not raised — never blocked


def test_signals_accumulate_across_turns(tmp_path):
    holon_compass.log_signal("h", "q1", "a1 dharma", agents_root=tmp_path)
    holon_compass.log_signal("h", "q2", "a2 ahimsa", agents_root=tmp_path)
    path = tmp_path / "h" / "compass_signals.jsonl"
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 2


@pytest.mark.parametrize(
    "name",
    ["h", "Holon-1", "holon_v1", "holon.v1", "a" * 64],
)
def test_signal_path_preserves_existing_canonical_names(tmp_path, name):
    assert holon_compass._signal_path(name, tmp_path) == (
        tmp_path.resolve() / name / "compass_signals.jsonl"
    )


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        "../escape",
        "/absolute",
        "nested/name",
        r"nested\name",
        "bad\rname",
        "bad\nname",
        "bad\x00name",
        "bad\x1fname",
        "bad\x7fname",
        "a" * 65,
    ],
)
def test_signal_path_rejects_noncanonical_components(tmp_path, name):
    with pytest.raises(ValueError):
        holon_compass._signal_path(name, tmp_path)


def test_invalid_name_skips_persistence_without_becoming_a_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(
        holon_compass,
        "score_exchange",
        lambda *_args: {"telos_alignment": 0.5, "witness_quality": 0.5, "at": "now"},
    )

    signal = holon_compass.log_signal("../escape", "hello", "reply", agents_root=tmp_path)

    assert signal["holon"] == "<invalid>"
    assert list(tmp_path.iterdir()) == []


def test_signal_path_rejects_symlink_escape(tmp_path, monkeypatch):
    agents_root = tmp_path / "agents"
    outside = tmp_path / "outside"
    agents_root.mkdir()
    outside.mkdir()
    (agents_root / "holon-1").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(
        holon_compass,
        "score_exchange",
        lambda *_args: {"telos_alignment": 0.5, "witness_quality": 0.5, "at": "now"},
    )

    with pytest.raises(ValueError, match="escapes"):
        holon_compass._signal_path("holon-1", agents_root)
    signal = holon_compass.log_signal("holon-1", "hello", "reply", agents_root=agents_root)

    assert signal["holon"] == "<invalid>"
    assert not (outside / "compass_signals.jsonl").exists()
