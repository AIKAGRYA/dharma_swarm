"""Tests for scripts/governance/agent_onboard.py.

The onboarding command must never hard-gate. It surfaces the current
operating reality from the existing owners; it owns no facts of its own.
These tests guard that contract.
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ONBOARD_SCRIPT = REPO_ROOT / "scripts/governance/agent_onboard.py"


def _load_module():
    """Import agent_onboard.py without executing main()."""
    spec = importlib.util.spec_from_file_location("agent_onboard", ONBOARD_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# End-to-end: the command must exit 0 even when state is stale
# ---------------------------------------------------------------------------

def test_onboard_exits_zero_in_repo():
    """agent_onboard.py must always exit 0; staleness is informational."""
    result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        f"agent_onboard.py must never hard-gate (exit={result.returncode})\n"
        f"stdout tail:\n{result.stdout[-400:]}\nstderr tail:\n{result.stderr[-400:]}"
    )


def test_onboard_renders_required_sections():
    """All owner-section headers must appear in the rendered output."""
    result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    required = [
        "DHARMA SWARM — AGENT ONBOARDING",
        "ACTIVE PORTFOLIO",
        "LIVE OPS SNAPSHOT",
        "LIVE OPS COCKPIT",
        "SURFACE MANIFEST HEALTH",
        "BROKEN REGISTER",
        "LIVING AXIOMS",
        "TOOLING-FIRST CONTEXT PASS",
        "HYGIENE SYSTEM",
        "ENFORCEMENT",
        "DEPTH POINTERS",
        "WHAT TO DO NEXT",
    ]
    for header in required:
        assert header in result.stdout, f"missing onboarding section: {header}"


def test_tooling_first_includes_wiki_and_memory():
    """The TOOLING-FIRST section must list wiki and memory MCP tools."""
    result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert "wiki show" in result.stdout, "TOOLING-FIRST must mention wiki show"
    assert "wiki search" in result.stdout, "TOOLING-FIRST must mention wiki search"
    assert "memory MCP" in result.stdout, "TOOLING-FIRST must mention memory MCP"
    assert "Tool availability" in result.stdout, "TOOLING-FIRST must probe tool availability"


def test_onboard_prints_single_command_memory():
    """The first screen must make make onboard the only command to remember."""
    result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert "Remember only: make onboard" in result.stdout
    assert "Next command : make agent-build-" in result.stdout
    assert "If unsure    : rerun make onboard" in result.stdout


def test_onboard_surfaces_ai_hygiene_tranche():
    """The front door must surface AI-agent hygiene, not only VC-* signals."""
    result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert "AI-agent governance" in result.stdout
    assert "AI_AGENT_GOVERNANCE.md" in result.stdout
    assert "anti_ai_slop_futureproof_deep_dive_2026-06-07.md" in result.stdout
    assert "anti_ai_slop_control_backlog_2026-06-08.md" in result.stdout
    assert "anti_ai_slop_scan_snapshot_2026-06-08.json" in result.stdout
    assert "AI-agent review signals" in result.stdout
    assert "AI-A1" in result.stdout
    assert "agent-build-preflight" in result.stdout
    assert "agent-build-closeout" in result.stdout


# ---------------------------------------------------------------------------
# Fixture-driven unit tests for the parsers
# ---------------------------------------------------------------------------

BR_SAMPLE = """# BROKEN REGISTER

## OPEN ITEMS

### BR-001 — first thing
- **status:** OPEN — first one

### BR-002 — second thing
- **status:** PARTIAL — half-done

### BR-003 — third thing
- **status:** INVESTIGATING — looking at it

## CLOSED ITEMS

### BR-100 — was broken, now fine
- **status:** FIXED 2026-05-01 — done

### BR-101 — also fixed
- **status:** **FIXED 2026-05-10** — done
"""


def test_broken_register_parser_counts(tmp_path, monkeypatch):
    mod = _load_module()
    br = tmp_path / "BROKEN_REGISTER.md"
    br.write_text(BR_SAMPLE, encoding="utf-8")
    monkeypatch.setattr(mod, "BROKEN_REGISTER", br)

    info = mod._parse_broken_register()
    assert info["present"] is True
    assert info["total"] == 5
    assert info["open_count"] == 3
    assert info["closed_count"] == 2
    assert len(info["top_open"]) == 3
    assert info["top_open"][0]["status_word"] == "OPEN"


def test_broken_register_parser_missing_file(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "BROKEN_REGISTER", tmp_path / "does_not_exist.md")
    info = mod._parse_broken_register()
    assert info == {"present": False}


# ---------------------------------------------------------------------------
# Active track surface
# ---------------------------------------------------------------------------

def test_active_track_evidence_is_consumed_when_present():
    """When evidence JSON exists, the script must reference its ID."""
    if not (REPO_ROOT / "reports/governance/active_track_evidence.json").exists():
        pytest.skip("evidence file not present in this checkout")
    result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    # The active portfolio section must render (id is data-dependent, so assert
    # the section header rather than a hard-coded track id).
    assert "ACTIVE PORTFOLIO" in result.stdout


# ---------------------------------------------------------------------------
# The onboarding command must not own any fact
# ---------------------------------------------------------------------------

def test_onboard_does_not_write_to_owners():
    """Run the script and ensure none of the owner files are mutated."""
    import hashlib

    owner_files = [
        REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml",
        REPO_ROOT / "docs/state/LIVE_OPS_DASHBOARD.md",
        REPO_ROOT / "docs/state/BROKEN_REGISTER.md",
        REPO_ROOT / "ACTIVE_SURFACE_MANIFEST.yaml",
    ]

    def digest(p: Path) -> str | None:
        if not p.exists():
            return None
        return hashlib.sha256(p.read_bytes()).hexdigest()

    before = {p: digest(p) for p in owner_files}
    subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    after = {p: digest(p) for p in owner_files}
    for p in owner_files:
        assert before[p] == after[p], f"agent_onboard.py must not mutate owner file {p}"


def test_runtime_truth_render_is_read_only(tmp_path, monkeypatch, capsys):
    """Runtime truth rows are projections and must not mutate owner files."""
    mod = _load_module()
    monkeypatch.setenv("DHARMA_STATE_DIR", str(tmp_path / "state"))

    owner_files = [
        REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml",
        REPO_ROOT / "ACTIVE_SURFACE_MANIFEST.yaml",
        REPO_ROOT / "tests/test_spine_persistence_invariant.py",
    ]

    def digest(path: Path) -> str | None:
        if not path.exists():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()

    before = {path: digest(path) for path in owner_files}
    rows = mod.render_runtime_truth(
        {
            "active_track_id": "runtime-truth-reconciliation-2026-06",
            "prerequisites_ok": True,
            "shippable": False,
            "completion_progress": {"passed": 5, "total": 11},
            "criteria": [
                {"id": "runtime_truth_packet_defined", "passed": True},
                {"id": "onboard_runtime_truth_render", "passed": False},
            ],
        },
        {"active_track": {"id": "runtime-truth-reconciliation-2026-06"}},
    )
    after = {path: digest(path) for path in owner_files}
    output = capsys.readouterr().out
    json_lines = [
        json.loads(line.strip())
        for line in output.splitlines()
        if line.strip().startswith("{")
    ]

    assert before == after
    assert "RUNTIME TRUTH PACKETS" in output
    assert "Compact:" in output
    assert "Machine rows (JSONL):" in output
    assert rows == json_lines
    assert any(row["surface_id"] == "runtime_state.store" for row in rows)
    assert all(row["is_authoritative"] is False for row in rows)
    assert all(row["is_projection"] is True for row in rows)
