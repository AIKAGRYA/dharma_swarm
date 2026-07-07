"""E4 causal daily delta — chain integrity, genesis rule, causality mandate."""

from __future__ import annotations

import json

import pytest

from dharma_swarm.chamber.daily_delta import (
    BrokenChainError,
    CausalityError,
    append_daily_delta,
    read_chain,
)

DIG = "c" * 64


def _change(**over):
    base = {"surface": "router.policy", "before": "v1", "after": "v2",
            "caused_by": [DIG]}
    base.update(over)
    return base


def _append(path, date="2026-07-07", changes=None, ingest=10, improve=2.0):
    return append_daily_delta(
        path, date=date,
        yesterday={"bronze_receipts_landed": ingest, "gym_runs": []},
        behavior_changes=changes if changes is not None else [_change()],
        ingest_units=ingest, improvement_units=improve,
    )


def test_genesis_row_has_empty_prev_and_valid_digest(tmp_path):
    path = tmp_path / "deltas.jsonl"
    row = _append(path)
    assert row["prev_digest"] == "" and row["digest"]
    assert read_chain(path) == [row]


def test_chain_links_and_survives_multiple_days(tmp_path):
    path = tmp_path / "deltas.jsonl"
    r1 = _append(path, date="2026-07-07")
    r2 = _append(path, date="2026-07-08")
    assert r2["prev_digest"] == r1["digest"]
    assert [r["date"] for r in read_chain(path)] == ["2026-07-07", "2026-07-08"]


def test_metabolic_efficiency_computed(tmp_path):
    row = _append(tmp_path / "d.jsonl", ingest=10, improve=2.0)
    assert row["metabolic_efficiency"] == {
        "ingest_units": 10, "improvement_units": 2.0, "ratio": 0.2}


def test_empty_caused_by_is_refused(tmp_path):
    with pytest.raises(CausalityError, match="empty caused_by"):
        _append(tmp_path / "d.jsonl", changes=[_change(caused_by=[])])


def test_non_digest_cause_is_refused(tmp_path):
    with pytest.raises(CausalityError, match="not a sha256"):
        _append(tmp_path / "d.jsonl", changes=[_change(caused_by=["vibes"])])


def test_delta_empty_day_is_written_honestly(tmp_path):
    row = _append(tmp_path / "d.jsonl", changes=[])
    assert row["behavior_changes"] == []  # visible flatline, never skipped


def test_tampered_chain_refuses_append_and_read(tmp_path):
    path = tmp_path / "deltas.jsonl"
    _append(path, date="2026-07-07")
    text = path.read_text().replace("2026-07-07", "2026-07-06")
    path.write_text(text)
    with pytest.raises(BrokenChainError):
        read_chain(path)
    with pytest.raises(BrokenChainError):
        _append(path, date="2026-07-08")


def test_concurrent_appends_do_not_fork_the_chain(tmp_path):
    # R1-2/R4: parallel writers must serialize; the chain stays readable.
    import concurrent.futures as cf
    from dharma_swarm.chamber.chain import append_chained, read_chain
    path = tmp_path / "concurrent.jsonl"

    def worker(i):
        return append_chained(path, {"schema": "t.v1", "i": i})

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(worker, range(40)))
    rows = read_chain(path)  # raises BrokenChainError if the chain forked
    assert len(rows) == 40
    assert {r["i"] for r in rows} == set(range(40))


def test_non_dict_chain_row_is_rejected(tmp_path):
    from dharma_swarm.chamber.chain import BrokenChainError, read_chain
    path = tmp_path / "bad.jsonl"
    path.write_text("123\n", encoding="utf-8")
    with pytest.raises(BrokenChainError, match="not a JSON object"):
        read_chain(path)


def test_checker_compatible_expect_chain(tmp_path, monkeypatch):
    """The chain must pass the REAL governance checker's expect_chain mode."""
    import importlib.util
    import sys
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "check_track_status",
        Path(__file__).resolve().parents[1] / "scripts/governance/check_track_status.py")
    cts = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("check_track_status", cts)
    spec.loader.exec_module(cts)
    path = tmp_path / "deltas.jsonl"
    _append(path, date="2026-07-07")
    _append(path, date="2026-07-08")
    monkeypatch.setattr(cts, "REPO_ROOT", tmp_path, raising=False)
    result = cts.check_receipt_valid(
        "deltas.jsonl", ["schema", "date", "metabolic_efficiency"],
        expect_chain=True)
    assert result.passed, result.detail
