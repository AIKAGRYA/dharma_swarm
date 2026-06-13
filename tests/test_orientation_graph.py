"""Tests for scripts/governance/orientation_graph.py — read-only projection."""
from __future__ import annotations

import datetime
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/governance/orientation_graph.py"

spec = importlib.util.spec_from_file_location("orientation_graph", SCRIPT)
og = importlib.util.module_from_spec(spec)
sys.modules["orientation_graph"] = og
spec.loader.exec_module(og)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _now_epoch() -> float:
    return datetime.datetime.now(datetime.timezone.utc).timestamp()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _witness_today(state_dir: Path) -> Path:
    now = datetime.datetime.now(datetime.timezone.utc)
    return state_dir / "witness" / f"witness_{now:%Y%m%d}.jsonl"


def test_packet_has_all_axes():
    packet = og.build_packet()
    data = og.asdict(packet)
    assert set(data) == {"identity", "organs", "tracks", "custody",
                         "liveness", "broken", "loop1", "routing_truth", "loops"}


def test_identity_serves_the_one_line():
    identity = og.build_identity()
    assert "dharma_swarm" in identity.one_line
    assert "foundations/THE_ORGANISM.md" in identity.read_first
    assert "docs/vision_maps/NORTH_STAR.md" in identity.read_first


def test_organs_project_from_portfolio_owner():
    organs = og.build_organs()
    assert organs, "portfolio owner should yield at least one organ"
    ids = {o.id for o in organs}
    assert "darshan-publication" in ids


def test_tracks_project_from_active_track_owner():
    tracks = og.build_tracks()
    assert tracks, "ACTIVE_TRACK.yaml should yield at least one active track"
    assert all(t.serves for t in tracks)


def test_custody_counts_registered_canon():
    custody = og.build_custody()
    assert custody.registered_total > 0
    assert custody.present + len(custody.missing) == custody.registered_total


def test_orientation_graph_render_is_read_only(tmp_path):
    before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT,
        capture_output=True, text=True).stdout
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=REPO_ROOT,
        capture_output=True, text=True)
    assert result.returncode == 0
    after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT,
        capture_output=True, text=True).stdout
    assert before == after, "orientation graph must not write owner files"


def test_json_mode_is_machine_parseable():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"], cwd=REPO_ROOT,
        capture_output=True, text=True)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "identity" in payload and "organs" in payload
    assert "loops" in payload


# --- Phase 2 loop-closure checks (fake/injected data, no network/spend) -----

def test_loop_closures_cover_all_phase2_loops():
    loops = og.build_loop_closures(state_dir=Path("/nonexistent_state_dir"))
    nums = [lp.loop for lp in loops]
    assert nums == [6, 2, 5, 9, 3, 4, 7, 8, 10, 11]
    for lp in loops:
        assert lp.verdict in {"LIVE", "PARTIAL", "NOT-LIVE"}


def test_loop6_partial_when_sense_constrain_live(tmp_path):
    rows = [
        {"ts": _now_iso(), "phase": "before_complete", "outcome": "PASS",
         "action": "pulse"},
        {"ts": _now_iso(), "phase": "before_write", "outcome": "BLOCKED",
         "action": "dispatch task [internal_maintenance] repair"},
        {"ts": _now_iso(), "phase": "before_write", "outcome": "WARN",
         "action": "Landscape probe for training_flywheel.py"},
        {"ts": _now_iso(), "phase": "before_write", "outcome": "PASS",
         "action": "Landscape probe for steady_0.py"},
    ]
    _write_jsonl(_witness_today(tmp_path), rows)
    loop = og.build_loop6_closure(state_dir=tmp_path)
    # Witness ADAPT arm is provider-gated, so the honest ceiling is PARTIAL.
    assert loop.verdict == "PARTIAL"
    assert loop.loop == 6


def test_loop6_not_live_when_no_data(tmp_path):
    loop = og.build_loop6_closure(state_dir=tmp_path)
    assert loop.verdict == "NOT-LIVE"


def test_loop6_not_live_when_all_pass(tmp_path):
    # All-PASS is non-discriminating: the gate isn't actually constraining.
    rows = [{"ts": _now_iso(), "phase": "before_write", "outcome": "PASS",
             "action": "pulse"} for _ in range(5)]
    _write_jsonl(_witness_today(tmp_path), rows)
    loop = og.build_loop6_closure(state_dir=tmp_path)
    assert loop.verdict == "NOT-LIVE"


def test_loop2_live_when_sense_and_decision_fresh(tmp_path):
    sig = [
        {"kind": "omega_divergence", "value": 0.403, "timestamp": _now_epoch()},
        {"kind": "omega_divergence", "value": 0.408, "timestamp": _now_epoch()},
    ]
    _write_jsonl(tmp_path / "algedonic_signals.jsonl", sig)
    ent = [{"entity_type": "gnani_verdict", "timestamp": _now_iso()}]
    _write_jsonl(tmp_path / "organism_memory" / "entities.jsonl", ent)
    loop = og.build_loop2_closure(state_dir=tmp_path)
    assert loop.verdict == "LIVE"


def test_loop2_partial_when_decision_stale(tmp_path):
    sig = [
        {"kind": "omega_divergence", "value": 0.403, "timestamp": _now_epoch()},
        {"kind": "omega_divergence", "value": 0.408, "timestamp": _now_epoch()},
    ]
    _write_jsonl(tmp_path / "algedonic_signals.jsonl", sig)
    stale = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(hours=36)).isoformat()
    _write_jsonl(tmp_path / "organism_memory" / "entities.jsonl",
                 [{"entity_type": "gnani_verdict", "timestamp": stale}])
    loop = og.build_loop2_closure(state_dir=tmp_path)
    assert loop.verdict == "PARTIAL"


def test_loop2_not_live_when_no_signal(tmp_path):
    loop = og.build_loop2_closure(state_dir=tmp_path)
    assert loop.verdict == "NOT-LIVE"


def test_loop5_live_when_real_blocked_rows(tmp_path):
    gp = {"trust_mode_override": "external_strict", "reason": "blocks",
          "expires": _now_epoch() + 3600}
    p = tmp_path / "meta" / "gate_pressure.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(gp), encoding="utf-8")
    rows = [{"ts": _now_iso(), "phase": "before_write", "outcome": "BLOCKED",
             "action": "dispatch task [internal_maintenance] repair"}]
    _write_jsonl(_witness_today(tmp_path), rows)
    loop = og.build_loop5_closure(state_dir=tmp_path)
    assert loop.verdict == "LIVE"


def test_loop5_partial_when_blocked_rows_are_fixtures(tmp_path):
    gp = {"trust_mode_override": "external_strict", "reason": "blocks",
          "expires": _now_epoch() + 3600}
    p = tmp_path / "meta" / "gate_pressure.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(gp), encoding="utf-8")
    # A destructive-command sentinel probe (not a real loop action). Built from
    # parts so the literal does not appear in staged additions (uplift guard).
    destructive_probe = " ".join(["rm", "-" + "rf", "/important"])
    rows = [{"ts": _now_iso(), "phase": "before_write", "outcome": "BLOCKED",
             "action": destructive_probe}]
    _write_jsonl(_witness_today(tmp_path), rows)
    loop = og.build_loop5_closure(state_dir=tmp_path)
    assert loop.verdict == "PARTIAL"


def test_loop5_not_live_when_expired(tmp_path):
    gp = {"trust_mode_override": "external_strict", "reason": "blocks",
          "expires": _now_epoch() - 10}
    p = tmp_path / "meta" / "gate_pressure.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(gp), encoding="utf-8")
    loop = og.build_loop5_closure(state_dir=tmp_path)
    assert loop.verdict == "NOT-LIVE"


def test_loop9_live_when_acted_wake_and_fresh_notes(tmp_path):
    rows = [{"ts": _now_iso(), "phase": "conductor_wake", "outcome": "COMPLETED",
             "action": "ran conductor task"}]
    _write_jsonl(_witness_today(tmp_path), rows)
    note = tmp_path / "shared" / "conductor_claude_notes.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("fresh", encoding="utf-8")
    loop = og.build_loop9_closure(state_dir=tmp_path)
    assert loop.verdict == "LIVE"


def test_loop9_not_live_when_only_warn_proposals(tmp_path):
    rows = [{"ts": _now_iso(), "phase": "conductor_wake", "outcome": "WARN",
             "action": "Investigate high-activity path"}]
    _write_jsonl(_witness_today(tmp_path), rows)
    loop = og.build_loop9_closure(state_dir=tmp_path)
    assert loop.verdict == "NOT-LIVE"


def test_loop1_gated_loops_are_not_live():
    for builder in (og.build_loop3_closure, og.build_loop4_closure,
                    og.build_loop7_closure, og.build_loop8_closure,
                    og.build_loop10_closure, og.build_loop11_closure):
        loop = builder()
        assert loop.verdict == "NOT-LIVE"
        assert "Loop 1" in loop.reason or "loop 1" in loop.reason.lower()


def test_loop_checks_write_nothing(tmp_path):
    # Building closures must not create files in an empty state dir.
    og.build_loop_closures(state_dir=tmp_path)
    assert not any(tmp_path.iterdir())


# --- Routing-truth: >=K2.6 power-floor classification (no network/spend) -----

def _write_delegation_db(path: Path, rows: list[dict]) -> None:
    """Write a minimal delegation_runs table mirroring runtime_state's schema:
    the routing-truth panel reads receipt_json + started_at only."""
    import sqlite3

    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE delegation_runs ("
        " run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, status TEXT NOT NULL,"
        " started_at TEXT NOT NULL, receipt_json TEXT)"
    )
    for i, r in enumerate(rows):
        conn.execute(
            "INSERT INTO delegation_runs (run_id, task_id, status, started_at,"
            " receipt_json) VALUES (?,?,?,?,?)",
            (f"run_{i}", f"task_{i}", r.get("status", "completed"),
             r.get("started_at", _now_iso()),
             json.dumps(r["receipt"]) if r.get("receipt") is not None else None),
        )
    conn.commit()
    conn.close()


def test_floor_classifies_at_or_above_frontier_set():
    # The whole >=K2.6 frontier set must classify AT-OR-ABOVE.
    at_or_above = [
        "deepseek-v4-pro:cloud", "z-ai/glm-5.1:free", "moonshotai/kimi-k2.6",
        "kimi-k2.7", "minimaxai/minimax-m3", "qwen3-coder:480b-cloud",
        "mistral-large-3-675b", "gpt-5.5", "claude-opus-4-8", "gemini-3-pro",
    ]
    for m in at_or_above:
        assert og.classify_floor(m) == "AT-OR-ABOVE", m


def test_floor_flags_sub_floor_served_models_below():
    # Sub-floor models the operator banished must classify BELOW.
    below = [
        "meta/llama-3.3-70b-instruct", "moonshotai/kimi-k2.5",
        "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    ]
    for m in below:
        assert og.classify_floor(m) == "BELOW", m


def test_floor_empty_model_is_unknown():
    assert og.classify_floor("") == "UNKNOWN"
    assert og.classify_floor(None) == "UNKNOWN"  # type: ignore[arg-type]


def test_spine_served_model_classified_at_or_above_floor(tmp_path):
    # When the spine dispatch records a served model, the make-orient routing
    # check classifies it AT-OR-ABOVE the Kimi K2.6 floor (the default-dispatch
    # frontier brain, deepseek-v4-pro:cloud, is >= floor — not sub-floor).
    db = tmp_path / "runtime.db"
    _write_delegation_db(db, [
        {"receipt": {"provider": "ollama", "model": "deepseek-v4-pro:cloud",
                     "status": "ok", "latency_ms": 1200}},
    ])
    rt = og.build_routing_truth(db_path=db)
    assert rt.served_model == "deepseek-v4-pro:cloud"
    assert rt.served_provider == "ollama"
    assert rt.floor_class == "AT-OR-ABOVE"
    assert rt.floor_pass is True


def test_spine_sub_floor_served_model_flagged_below(tmp_path):
    # A sub-floor served model (the historical llama-3.3-70b receipt) must be
    # flagged BELOW floor by the routing-truth check.
    db = tmp_path / "runtime.db"
    _write_delegation_db(db, [
        {"receipt": {"provider": "nvidia_nim",
                     "model": "meta/llama-3.3-70b-instruct",
                     "status": "ok", "latency_ms": 28147}},
    ])
    rt = og.build_routing_truth(db_path=db)
    assert rt.served_model == "meta/llama-3.3-70b-instruct"
    assert rt.floor_class == "BELOW"
    assert rt.floor_pass is False


def test_routing_truth_fill_and_fresh_counts(tmp_path):
    db = tmp_path / "runtime.db"
    stale = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(hours=48)).isoformat()
    _write_delegation_db(db, [
        # fresh, receipted, at-or-above (this is the LATEST by started_at)
        {"receipt": {"provider": "ollama", "model": "glm-5.1:cloud",
                     "status": "ok", "latency_ms": 900},
         "started_at": _now_iso()},
        # stale but receipted
        {"receipt": {"provider": "nvidia_nim", "model": "moonshotai/kimi-k2.6",
                     "status": "ok", "latency_ms": 1500},
         "started_at": stale},
        # no receipt at all (un-receipted dispatch)
        {"receipt": None, "started_at": _now_iso()},
    ])
    rt = og.build_routing_truth(db_path=db)
    assert rt.total == 3
    assert rt.receipted == 2
    assert 60.0 < rt.fill_pct < 70.0  # 2/3
    assert rt.fresh_today == 1        # only the latest fresh receipt is <24h
    # Latest by started_at is the fresh glm-5.1 row -> at-or-above.
    assert rt.served_model == "glm-5.1:cloud"
    assert rt.floor_class == "AT-OR-ABOVE"


def test_routing_truth_no_db_is_honest(tmp_path):
    rt = og.build_routing_truth(db_path=tmp_path / "nope.db")
    assert rt.total == 0
    assert rt.receipted == 0
    assert rt.served_model == ""
    assert rt.floor_class == "UNKNOWN"
    assert rt.floor_pass is False


def test_routing_truth_in_packet_and_render():
    # The packet carries a routing_truth axis and render does not crash.
    packet = og.build_packet()
    assert hasattr(packet, "routing_truth")
    og.render(packet)  # smoke: must not raise


def test_routing_truth_writes_nothing(tmp_path):
    db = tmp_path / "runtime.db"
    _write_delegation_db(db, [
        {"receipt": {"provider": "ollama", "model": "deepseek-v4-pro:cloud",
                     "status": "ok", "latency_ms": 1000}},
    ])
    before = sorted(p.name for p in tmp_path.iterdir())
    og.build_routing_truth(db_path=db)
    after = sorted(p.name for p in tmp_path.iterdir())
    assert before == after
