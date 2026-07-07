"""E6 velocity — chained history, UNVALUED->VALUED transition, d(delta)/dt."""

from __future__ import annotations

from dharma_swarm.chamber.chain import read_chain
from dharma_swarm.chamber.ledger_history import append_history, compute_velocity


def test_history_appends_chained_rows(tmp_path):
    path = tmp_path / "history.jsonl"
    r1 = append_history(path, generated_at="2026-07-07T00:00:00Z",
                        receipt_digest="a" * 64,
                        capabilities={"cap": {"delta": -1.0, "ours": 1.0}})
    r2 = append_history(path, generated_at="2026-07-08T00:00:00Z",
                        receipt_digest="b" * 64,
                        capabilities={"cap": {"delta": -0.5, "ours": 1.5}})
    assert r2["prev_digest"] == r1["digest"]
    assert len(read_chain(path)) == 2


def test_velocity_unvalued_below_two_points():
    v = compute_velocity([], {"cap": {"delta": -1.0, "ours": 1.0}},
                         "2026-07-07T00:00:00Z")
    assert v["capabilities"]["cap"]["status"] == "UNVALUED"
    assert v["valued"] == 0 and v["renders_in_history"] == 1
    assert v["loop_latency"]["status"] == "UNVALUED"


def test_velocity_values_from_second_numeric_point():
    prior = [{"generated_at": "2026-07-07T00:00:00Z",
              "capabilities": {"cap": {"delta": -1.0, "ours": None}}}]
    v = compute_velocity(prior, {"cap": {"delta": -0.5, "ours": None}},
                         "2026-07-09T00:00:00Z")
    cap = v["capabilities"]["cap"]
    assert cap["status"] == "VALUED"
    assert cap["d_delta_dt_per_day"] == 0.25  # (-0.5 - -1.0) / 2 days
    assert cap["closing"] is False  # delta rising = eroding, not closing
    assert v["valued"] == 1


def test_velocity_none_delta_never_fabricates():
    prior = [{"generated_at": "2026-07-07T00:00:00Z",
              "capabilities": {"cap": {"delta": None, "ours": None}}}]
    v = compute_velocity(prior, {"cap": {"delta": None, "ours": None}},
                         "2026-07-08T00:00:00Z")
    assert v["capabilities"]["cap"]["status"] == "UNVALUED"
    assert v["capabilities"]["cap"]["points"] == 0
