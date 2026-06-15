import importlib.util
import json
import sqlite3
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "version_metrics_rollup",
    Path(__file__).resolve().parents[2] / "scripts" / "runtime" / "version_metrics_rollup.py",
)
rollup = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rollup)


def _entry(build_id=None, pass_rate=1.0, status="applied", gates_failed=None, rollback=None):
    e = {
        "timestamp": "2026-06-14T00:00:00+00:00",
        "status": status,
        "test_results": {"pass_rate": pass_rate},
        "fitness": {"dharmic_alignment": 0.5, "elegance": 0.4, "swabhaav_alignment": 0.3},
        "promotion_state": "candidate",
        "gates_failed": gates_failed or [],
        "rollback_reason": rollback,
    }
    if build_id:
        e["daemon_version"] = build_id
    return e


def _write_archive(tmp_path, entries):
    p = tmp_path / "arch.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return p


def _write_db(tmp_path, runs):
    p = tmp_path / "r.db"
    conn = sqlite3.connect(p)
    conn.execute(
        "CREATE TABLE delegation_runs (run_id TEXT, status TEXT, started_at TEXT, "
        "metadata_json TEXT, receipt_json TEXT)"
    )
    for i, (status, meta, receipt) in enumerate(runs):
        conn.execute(
            "INSERT INTO delegation_runs VALUES (?,?,?,?,?)",
            (str(i), status, "2026-06-14T00:00:00+00:00", json.dumps(meta), json.dumps(receipt)),
        )
    conn.commit()
    conn.close()
    return p


def test_rollup_two_tagged_versions_valid_json(tmp_path):
    entries = [_entry("0.1.0+aaa", pass_rate=0.9), _entry("0.1.0+aaa", pass_rate=1.0),
               _entry("0.1.0+bbb", pass_rate=0.2)]
    arch = _write_archive(tmp_path, entries)
    db = _write_db(tmp_path, [
        ("completed", {"daemon_version": "0.1.0+aaa"}, {"status": "ok", "latency_ms": 100, "cost_usd": 0.01}),
    ])
    out = rollup.build_rollup(arch, db, "0.1.0+aaa")
    assert out["schema_version"] == 1
    assert out["window"]["n_entries"] == 2
    assert out["verified_metrics"]["correctness_mean"] == 0.95
    assert out["verified_metrics"]["cost_observed"] is True
    assert out["generated_at"]


def test_rollup_timestamp_fallback_for_untagged(tmp_path):
    entries = [_entry(None, pass_rate=0.8), _entry(None, pass_rate=0.6)]
    arch = _write_archive(tmp_path, entries)
    db = _write_db(tmp_path, [
        ("completed", {}, {"status": "ok", "latency_ms": 100, "cost_usd": 0.01}),
    ])
    out = rollup.build_rollup(arch, db, "0.1.0+missing",
                              window_start="2026-06-13", window_end="2026-06-15")
    assert out["used_timestamp_fallback"] is True
    assert out["window"]["n_entries"] == 2
    assert out["window"]["n_runs"] == 1


def test_missing_build_id_does_not_claim_untagged_history_without_window(tmp_path):
    entries = [_entry(None, pass_rate=0.8)]
    arch = _write_archive(tmp_path, entries)
    db = _write_db(tmp_path, [
        ("completed", {}, {"status": "ok", "latency_ms": 100, "cost_usd": 0.01}),
    ])

    out = rollup.build_rollup(arch, db, "0.1.0+missing")

    assert out["used_timestamp_fallback"] is True
    assert out["window"]["n_entries"] == 0
    assert out["window"]["n_runs"] == 0
    assert out["verified_metrics"]["receipt_ok_rate"] == 0.0


def test_verified_metrics_only_from_grounded_fields(tmp_path):
    entries = [_entry("0.1.0+x", gates_failed=["telos:BLOCK"]), _entry("0.1.0+x", rollback="reverted")]
    arch = _write_archive(tmp_path, entries)
    db = _write_db(tmp_path, [])
    out = rollup.build_rollup(arch, db, "0.1.0+x")
    vm = out["verified_metrics"]
    assert vm["gate_allow_rate"] == 0.5  # one of two entries had a gate failure
    assert vm["rollback_rate"] > 0.0
    # heuristic dims recorded but separate
    assert "dharmic_alignment" in out["heuristic_metrics"]
    assert "dharmic_alignment" not in vm


def test_free_model_cost_unobserved(tmp_path):
    arch = _write_archive(tmp_path, [_entry("0.1.0+free")])
    db = _write_db(tmp_path, [
        ("completed", {"daemon_version": "0.1.0+free"}, {"status": "ok", "latency_ms": 50, "cost_usd": None}),
    ])
    out = rollup.build_rollup(arch, db, "0.1.0+free")
    assert out["verified_metrics"]["cost_observed"] is False
