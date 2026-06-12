"""Verifier for the holon kill-switch (U7). Pure signaling — no loop, no animation."""
from __future__ import annotations

from dharma_swarm import holon_killswitch as ks


def test_request_and_detect_kill(tmp_path):
    assert ks.is_kill_requested("h", agents_root=tmp_path) is False
    path = ks.request_kill("h", reason="operator stop", agents_root=tmp_path)
    assert path.exists()
    assert ks.is_kill_requested("h", agents_root=tmp_path) is True
    rec = ks.read_kill("h", agents_root=tmp_path)
    assert rec["holon"] == "h"
    assert rec["reason"] == "operator stop"
    assert "requested_at" in rec


def test_request_kill_idempotent(tmp_path):
    ks.request_kill("h", agents_root=tmp_path)
    ks.request_kill("h", agents_root=tmp_path)  # second call must not crash
    assert ks.is_kill_requested("h", agents_root=tmp_path) is True


def test_clear_kill_idempotent(tmp_path):
    ks.request_kill("h", agents_root=tmp_path)
    assert ks.clear_kill("h", agents_root=tmp_path) is True
    assert ks.is_kill_requested("h", agents_root=tmp_path) is False
    assert ks.clear_kill("h", agents_root=tmp_path) is False  # nothing to clear → False


def test_read_kill_absent_returns_none(tmp_path):
    assert ks.read_kill("nope", agents_root=tmp_path) is None
