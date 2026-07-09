"""TAM (Transdimensional Abundance Machine) Company-Builder Parity surface.

The instrument must be projection-only, deterministic, replay-checked, and
ungameable: uncited competitor cells render UNKNOWN/UNMEASURED (never a
guess), unmeasured rows can never inflate the headline, AHEAD must be earned
(RUNS organ + cited structural exceed-vector), and the history chain shows
whether the gap closes over time.
"""

from __future__ import annotations

import importlib.util
import json
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


def _sample_row(mod, **overrides):
    row = {
        "key": "sample", "capability": "sample capability",
        "ours_status": "RUNS", "ours_owner": "dharma_swarm/telos_gates.py",
        "ours_note": "", "comp_name": "Competitor", "comp_status": "CLAIMED",
        "comp_claim": "claims it", "comp_sources": ["https://example.com"],
        "comp_verification": "vendor-claim", "structural_exceed_cite": "",
    }
    row.update(overrides)
    return row


# ------------------------------------------------------------ honesty rules
def test_uncited_competitor_cell_is_unmeasured_never_a_guess():
    mod = _load("tam_ledger")
    row = _sample_row(mod, comp_status="CLAIMED", comp_sources=[])
    assert mod.parity_bucket(row) == mod.UNMEASURED
    row = _sample_row(mod, comp_status="UNKNOWN", comp_sources=[])
    assert mod.parity_bucket(row) == mod.UNMEASURED


def test_unmeasured_rows_stay_in_denominator_and_cannot_inflate():
    mod = _load("tam_ledger")
    measured = _sample_row(mod)  # RUNS vs CLAIMED -> AT_PARITY
    unmeasured = _sample_row(mod, key="u", comp_status="UNKNOWN", comp_sources=[])
    for row in (measured, unmeasured):
        row["bucket"] = mod.parity_bucket(row)
    parity = mod.compute_parity([measured, unmeasured])
    # 1.0 / 2 rows — the unmeasured row drags the number DOWN, never up
    assert parity["denominator"] == 2
    assert parity["parity_pct"] == 50.0


def test_ahead_must_be_earned_not_narrated():
    mod = _load("tam_ledger")
    # RUNS without a cited exceed-vector is only AT_PARITY
    row = _sample_row(mod)
    assert mod.parity_bucket(row) == mod.AT_PARITY
    # an exceed-vector claim on a non-running organ is a data error
    bad = _sample_row(mod, ours_status="ASPIRATION",
                      structural_exceed_cite="some/doc.md:1")
    try:
        mod.validate_row(bad)
        raise AssertionError("exceed-vector on a non-RUNS organ must raise")
    except ValueError:
        pass


def test_uncited_competitor_absent_cannot_shrink_denominator():
    mod = _load("tam_ledger")
    bad = _sample_row(mod, comp_status="ABSENT", comp_sources=[])
    try:
        mod.validate_row(bad)
        raise AssertionError("ABSENT without a cited clean negative must raise")
    except ValueError:
        pass


def test_frozen_axes_pass_validation_and_cite_everything():
    mod = _load("tam_ledger")
    rows = mod.build_rows()
    assert len(rows) >= 10
    keys = [r["key"] for r in rows]
    assert "honest_arr" in keys  # the headline differentiator row exists
    for r in rows:
        assert r["ours_owner"], f"{r['key']}: ours cell must cite a repo owner"
        if r["bucket"] != mod.UNMEASURED:
            assert r["comp_sources"], f"{r['key']}: measured competitor cell must cite a URL"


# ------------------------------------------------------------- determinism
def test_build_report_is_deterministic():
    mod = _load("tam_ledger")
    assert mod.build_report() == mod.build_report()


# --------------------------------------------------------- write/check/seal
def test_write_then_check_roundtrip_and_tamper_detection(tmp_path):
    mod = _load("tam_ledger")
    receipt = mod.write_surface(tmp_path)
    assert mod.check(tmp_path) == []
    # digest matches the house verifier convention
    from dharma_swarm.memory_kernel.write_receipts import stable_digest

    assert receipt["digest"] == stable_digest(
        {k: v for k, v in receipt.items() if k != "digest"}
    )
    # tampering with the headline must be caught
    path = tmp_path / mod.RECEIPT_NAME
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["parity_pct"] = 99.9
    path.write_text(json.dumps(tampered, indent=2, sort_keys=True), encoding="utf-8")
    findings = mod.check(tmp_path)
    assert any("digest mismatch" in f for f in findings)


def test_markdown_is_a_pure_render(tmp_path):
    mod = _load("tam_ledger")
    mod.write_surface(tmp_path)
    md = tmp_path / mod.MARKDOWN_NAME
    md.write_text(md.read_text(encoding="utf-8") + "edited\n", encoding="utf-8")
    findings = mod.check(tmp_path)
    assert any("pure render" in f for f in findings)


def test_history_chain_appends_velocity_and_detects_tamper(tmp_path):
    mod = _load("tam_ledger")
    mod.write_surface(tmp_path)
    mod.write_surface(tmp_path)  # second render -> velocity measurable
    history = mod.read_history(tmp_path / mod.HISTORY_NAME)
    assert len(history) == 2
    assert history[0]["prev_digest"] == ""
    assert history[1]["prev_digest"] == history[0]["digest"]
    vel = mod.compute_velocity(history)
    assert vel is not None and vel["direction"] == "flat"
    assert mod.check(tmp_path) == []
    # breaking the chain must be caught
    rows = [json.loads(ln) for ln in
            (tmp_path / mod.HISTORY_NAME).read_text(encoding="utf-8").splitlines()]
    rows[0]["parity_pct"] = 99.9
    (tmp_path / mod.HISTORY_NAME).write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")
    findings = mod.check(tmp_path)
    assert any("digest mismatch" in f or "chain broken" in f for f in findings)


# ------------------------------------------------- committed surface (repo)
def test_committed_surface_replays():
    """The surface committed under reports/governance/tam must replay exactly."""
    mod = _load("tam_ledger")
    assert mod.check(mod.DEFAULT_OUT_DIR) == []


def test_committed_receipt_passes_house_verifier():
    """check_track_status.check_receipt_valid must accept the receipt with
    expect_digest — the exact criterion wired into ACTIVE_TRACK.yaml."""
    cts = _load("check_track_status")
    res = cts.check_receipt_valid(
        "reports/governance/tam/tam_receipt.json",
        ["schema", "generated_at", "authority", "parity_pct", "lane_counts",
         "rows", "headline_differentiator", "baseline"],
        expect_digest=True,
    )
    assert res.passed, res.detail
    chain = cts.check_receipt_valid(
        "reports/governance/tam/tam_history.jsonl",
        ["schema", "generated_at", "parity_pct", "receipt_digest"],
        expect_chain=True,
    )
    assert chain.passed, chain.detail
