"""Tests for scripts/governance/agent_onboard.py.

The onboarding command must never hard-gate. It surfaces the current
operating reality from the existing owners; it owns no facts of its own.
These tests guard that contract.
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ONBOARD_SCRIPT = REPO_ROOT / "scripts/governance/agent_onboard.py"


@pytest.fixture(autouse=True)
def _isolate_ops_dir(tmp_path, monkeypatch):
    """Every test (incl. subprocess runs, which inherit os.environ) writes
    its machine receipt to a tmp dir — never the live fleet receipt at
    ~/.dharma/ops/onboard_receipt.json that hermes-m5/loops consume."""
    monkeypatch.setenv("DHARMA_OPS_DIR", str(tmp_path / "ops"))


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
        "PARALLEL WORK LANES",
        "LIVE OPS SNAPSHOT",
        "LIVE OPS COCKPIT",
        "SURFACE MANIFEST HEALTH",
        "BROKEN REGISTER",
        "LIVING AXIOMS",
        "RECENT TRACK ACTIVITY",
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
    # Latest-by-glob, so a new dated snapshot never strands the front door.
    assert "anti_ai_slop_futureproof_deep_dive_" in result.stdout
    assert "anti_ai_slop_control_backlog_" in result.stdout
    assert "anti_ai_slop_scan_snapshot_" in result.stdout
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

def test_onboard_does_not_write_to_owners(tmp_path):
    """Run the script and ensure none of the owner files are mutated.

    AGENT_ONBOARD_NO_REFRESH=1 disables the (intentional, documented)
    evidence regeneration so this test can also assert the GENERATED
    evidence files stay untouched — onboard itself writes nothing in-repo;
    only the check_track_status.py owner may, when refresh is allowed.
    """
    owner_files = [
        REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml",
        REPO_ROOT / "docs/state/LIVE_OPS_DASHBOARD.md",
        REPO_ROOT / "docs/state/BROKEN_REGISTER.md",
        REPO_ROOT / "ACTIVE_SURFACE_MANIFEST.yaml",
        REPO_ROOT / "reports/governance/active_track_evidence.json",
        REPO_ROOT / "reports/governance/track_portfolio.json",
    ]

    def digest(p: Path) -> str | None:
        if not p.exists():
            return None
        return hashlib.sha256(p.read_bytes()).hexdigest()

    before = {p: digest(p) for p in owner_files}
    subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
        env={**os.environ, "AGENT_ONBOARD_NO_REFRESH": "1",
             "DHARMA_OPS_DIR": str(tmp_path)},
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

    assert before == after
    assert "RUNTIME TRUTH PACKETS" in output
    assert "Compact:" in output
    # Full rows live in the machine receipt now; stdout carries one digest
    # line per packet (the inline JSONL was ~44% of the output's tokens).
    assert "Packets (full rows in the onboard receipt):" in output
    assert any(row["surface_id"] == "runtime_state.store" for row in rows)
    assert all(row["is_authoritative"] is False for row in rows)
    assert all(row["is_projection"] is True for row in rows)


# ---------------------------------------------------------------------------
# CLI modes and the machine receipt
# ---------------------------------------------------------------------------

def test_fast_mode_exits_zero_and_skips_slow_sections(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT), "--fast"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
        env={**os.environ, "DHARMA_OPS_DIR": str(tmp_path)},
    )
    assert result.returncode == 0
    assert "skipped — --fast" in result.stdout
    assert "PARALLEL WORK LANES" in result.stdout
    # Slow probes must not run in fast mode.
    assert "DRIFT TRIAGE (skipped — --fast)" in result.stdout


def test_json_mode_emits_valid_receipt(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT), "--json", "--fast"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
        env={**os.environ, "DHARMA_OPS_DIR": str(tmp_path)},
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["schema"] == "dharma_swarm.onboard_receipt.v1"
    assert payload["authority"] == "projection_only"
    for key in ("repo", "work_lanes", "portfolio", "next_items", "broken_register"):
        assert key in payload, f"receipt missing key: {key}"
    # The same payload must land on disk for fleet consumers.
    receipt = tmp_path / "onboard_receipt.json"
    assert receipt.exists()
    on_disk = json.loads(receipt.read_text(encoding="utf-8"))
    assert on_disk["schema"] == payload["schema"]


def test_receipt_is_written_outside_the_repo(tmp_path):
    subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT), "--fast"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
        env={**os.environ, "DHARMA_OPS_DIR": str(tmp_path)},
    )
    assert (tmp_path / "onboard_receipt.json").exists()
    # Nothing new may appear inside the repo (read-only on owners).
    status = subprocess.run(
        ["git", "status", "--porcelain", "reports/", "docs/"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
    )
    new_files = [ln for ln in status.stdout.splitlines() if ln.startswith("??")]
    assert not any("onboard_receipt" in ln for ln in new_files)


# ---------------------------------------------------------------------------
# v2 portfolio correctness (the regressions that shipped silently with #555)
# ---------------------------------------------------------------------------

def test_malformed_evidence_degrades_instead_of_crashing(tmp_path, monkeypatch):
    """Valid-JSON-but-garbage evidence (e.g. a partial parallel write) must
    degrade — the exit-0 doctrine covers exactly this stale-state class."""
    mod = _load_module()
    bad = tmp_path / "evidence.json"
    bad.write_text(json.dumps({"active_tracks": [None, "oops", {"id": "ok", "shippable": False}]}),
                   encoding="utf-8")
    monkeypatch.setattr(mod, "EVIDENCE_JSON", bad)
    evidence = mod._load_evidence()
    assert evidence == {"active_tracks": [{"id": "ok", "shippable": False}]}
    # And the downstream consumers survive raw garbage fed directly.
    assert mod._collect_next_items({"active_tracks": [None, "oops"]}, {}) == []
    payload = mod._receipt_payload({}, {}, [], [None, {"number": 1}],
                                   {"active_tracks": [None]}, {})
    json.dumps(payload)  # must be serializable
    assert payload["open_prs"] == [{"number": 1, "title": None, "isDraft": None}]


def test_collect_next_items_skips_shippable_tracks():
    """next_items must come from UNSHIPPED tracks — a shippable track's
    next_items are already-done work and must never be served as guidance."""
    mod = _load_module()
    evidence = {
        "active_tracks": [
            {"id": "done-track", "shippable": True},
            {"id": "live-track", "shippable": False},
        ]
    }
    track = {
        "active_tracks": [
            {"id": "done-track", "next_items": [{"kind": "code", "what": "already shipped"}]},
            {"id": "live-track", "next_items": [{"kind": "code", "what": "real next step"}]},
        ]
    }
    items = mod._collect_next_items(evidence, track)
    whats = [i["what"] for i in items]
    assert "real next step" in whats
    assert "already shipped" not in whats
    assert items[0]["track_id"] == "live-track"


def test_collect_next_items_v1_fallback():
    mod = _load_module()
    track = {"active_track": {"id": "solo", "next_items": [{"kind": "code", "what": "v1 item"}]}}
    items = mod._collect_next_items(None, track)
    assert [i["what"] for i in items] == ["v1 item"]


def test_all_track_surfaces_reads_owned_surfaces():
    """v2 uses `owned_surfaces`; the v1-only `surfaces` read silently killed
    the RECENT TRACK ACTIVITY section when the portfolio shipped."""
    mod = _load_module()
    track = {
        "active_tracks": [
            {"id": "a", "owned_surfaces": ["dharma_swarm/spine/**", "scripts/x.py"]},
            {"id": "b", "surfaces": ["legacy/path.py"], },
            {"id": "c", "owned_surfaces": ["scripts/x.py"]},  # dedup
        ]
    }
    surfaces = mod._all_track_surfaces(track)
    assert surfaces == ["dharma_swarm/spine/**", "scripts/x.py", "legacy/path.py"]
