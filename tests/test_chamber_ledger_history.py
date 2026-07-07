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


def test_velocity_values_from_ours_when_delta_is_none():
    # R1-3: velocity was dead because only `delta` (always None) was read.
    # A capability whose measured `ours` changes must now produce a rate.
    prior = [{"generated_at": "2026-07-07T00:00:00Z",
              "capabilities": {"ingest": {"delta": None, "ours": 0.0}}}]
    v = compute_velocity(prior, {"ingest": {"delta": None, "ours": 4.0}},
                         "2026-07-09T00:00:00Z")
    cap = v["capabilities"]["ingest"]
    assert cap["status"] == "VALUED"
    assert cap["d_delta_dt_per_day"] == 2.0  # (4-0)/2 days
    assert v["valued"] == 1


def test_velocity_equal_timestamps_unvalued_with_reason():
    # R1-5: identical second-granularity timestamps cannot define a rate.
    prior = [{"generated_at": "2026-07-07T00:00:00Z",
              "capabilities": {"cap": {"delta": None, "ours": 1.0}}}]
    v = compute_velocity(prior, {"cap": {"delta": None, "ours": 2.0}},
                         "2026-07-07T00:00:00Z")
    cap = v["capabilities"]["cap"]
    assert cap["status"] == "UNVALUED"
    assert "clock-second" in cap["requires"]


def test_velocity_series_sorted_by_time_not_insertion():
    # R1-5: out-of-order history rows must be time-sorted before differencing.
    from dharma_swarm.chamber.ledger_history import history_values
    rows = [
        {"generated_at": "2026-07-09T00:00:00Z", "capabilities": {"c": {"ours": 3.0}}},
        {"generated_at": "2026-07-07T00:00:00Z", "capabilities": {"c": {"ours": 1.0}}},
    ]
    series = history_values(rows)
    assert [v for _, v in series["c"]] == [1.0, 3.0]  # time order
