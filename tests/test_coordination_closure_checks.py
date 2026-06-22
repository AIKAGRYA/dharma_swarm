"""Wire the hermetic closure checks (Deliverable F) into the test suite.

These mirror scripts/governance/check_arena_replay.py,
check_council_invariants.py, and check_routing_receipt.py — they must stay
green in CI without keys/GPU/network."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / "scripts" / "governance" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_check_arena_replay_passes():
    mod = _load("check_arena_replay")
    assert mod.check() == []
    assert mod.main() == 0


def test_check_council_invariants_passes():
    mod = _load("check_council_invariants")
    assert mod.check() == []
    assert mod.main() == 0


def test_check_routing_receipt_passes():
    mod = _load("check_routing_receipt")
    assert mod.check() == []
    assert mod.main() == 0
