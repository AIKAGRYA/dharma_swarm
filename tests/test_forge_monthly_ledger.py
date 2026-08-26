"""Hermetic tests for the Forge monthly spend meter (forge_v2/monthly_ledger.py)
and its refuse-to-start wiring in forge_v2/runner.py. No network, no Docker,
no clock dependence: month keys and roots are always explicit."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.forge_v1.forge_v2 import monthly_ledger as ml
from dharma_swarm.forge_v1.forge_v2 import runner


# --------------------------------------------------------------------------- #
# pure helpers
# --------------------------------------------------------------------------- #
def test_month_key_derives_from_explicit_timestamp() -> None:
    assert ml.month_key(0) == "1970-01"
    # 2026-08-19T00:00:00Z
    assert ml.month_key(1786752000) == "2026-08"


def test_ledger_path_validates_month_and_uses_template(tmp_path: Path) -> None:
    p = ml.ledger_path("2026-08", root=tmp_path)
    assert p == tmp_path / "2026-08.jsonl"
    for bad in ("2026-13", "2026-00", "202608", "aug-2026", "2026-8"):
        with pytest.raises(ValueError):
            ml.ledger_path(bad, root=tmp_path)


def test_worst_case_run_usd_is_attempts_times_cap() -> None:
    # 50 instances x 3 replicates x 2 arms at $0.25/attempt
    assert ml.worst_case_run_usd(0.25, n_instances=50, replicates=3) == 75.0
    assert ml.worst_case_run_usd(0.25, n_instances=50, replicates=1) == 25.0
    with pytest.raises(ValueError):
        ml.worst_case_run_usd(-0.1, n_instances=1, replicates=1)


# --------------------------------------------------------------------------- #
# ledger append + aggregation
# --------------------------------------------------------------------------- #
def test_record_and_aggregate_month_spend(tmp_path: Path) -> None:
    assert ml.month_spend_usd("2026-08", root=tmp_path) == 0.0
    ml.record_run_spend(usd=1.25, shadow_usd=0.10, month="2026-08",
                        timestamp=1000.0, label="a", root=tmp_path)
    ml.record_run_spend(usd=0.0, shadow_usd=0.65, month="2026-08",
                        timestamp=2000.0, label="b", root=tmp_path)
    assert ml.month_spend_usd("2026-08", root=tmp_path) == pytest.approx(2.0)
    assert ml.remaining_monthly_usd(200.0, "2026-08", root=tmp_path) == pytest.approx(198.0)
    # months are isolated files
    assert ml.month_spend_usd("2026-09", root=tmp_path) == 0.0
    rows = [json.loads(x) for x in (tmp_path / "2026-08.jsonl").read_text().splitlines()]
    assert [r["label"] for r in rows] == ["a", "b"]
    assert all(r["kind"] == "forge_run_spend" for r in rows)


def test_malformed_ledger_row_fails_closed(tmp_path: Path) -> None:
    path = ml.ledger_path("2026-08", root=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"total_usd": 1.0}\nnot json\n')
    with pytest.raises(ValueError, match="malformed spend ledger row"):
        ml.month_spend_usd("2026-08", root=tmp_path)
    path.write_text('{"month": "2026-08"}\n')
    with pytest.raises(ValueError, match="without usd fields"):
        ml.month_spend_usd("2026-08", root=tmp_path)


def test_remaining_never_negative(tmp_path: Path) -> None:
    ml.record_run_spend(usd=300.0, shadow_usd=0.0, month="2026-08",
                        timestamp=0.0, root=tmp_path)
    assert ml.remaining_monthly_usd(200.0, "2026-08", root=tmp_path) == 0.0


# --------------------------------------------------------------------------- #
# admission gate
# --------------------------------------------------------------------------- #
def test_admission_allows_run_that_fits(tmp_path: Path) -> None:
    gate = ml.check_run_admission(75.0, monthly_cap_usd=200.0, month="2026-08",
                                  root=tmp_path)
    assert gate.allowed is True
    assert gate.remaining_usd == pytest.approx(200.0)


def test_admission_refuses_run_exceeding_remainder(tmp_path: Path) -> None:
    ml.record_run_spend(usd=150.0, shadow_usd=0.0, month="2026-08",
                        timestamp=0.0, root=tmp_path)
    gate = ml.check_run_admission(75.0, monthly_cap_usd=200.0, month="2026-08",
                                  root=tmp_path)
    assert gate.allowed is False
    assert "exceeds the remaining" in gate.reason
    assert gate.spent_usd == pytest.approx(150.0)
    # a smaller run still fits (boundary inclusive)
    assert ml.check_run_admission(50.0, monthly_cap_usd=200.0, month="2026-08",
                                  root=tmp_path).allowed is True


def test_admission_refuses_uncapped_and_degenerate_runs(tmp_path: Path) -> None:
    assert ml.check_run_admission(None, monthly_cap_usd=200.0, month="2026-08",
                                  root=tmp_path).allowed is False
    assert ml.check_run_admission(10.0, monthly_cap_usd=0.0, month="2026-08",
                                  root=tmp_path).allowed is False
    assert ml.check_run_admission(-1.0, monthly_cap_usd=200.0, month="2026-08",
                                  root=tmp_path).allowed is False


# --------------------------------------------------------------------------- #
# runner wiring (no model/Docker path is ever reached)
# --------------------------------------------------------------------------- #
def _refusing_gate() -> ml.MonthlyGate:
    return ml.MonthlyGate(False, "test refusal", "2026-08", 200.0, 200.0, 0.0, 75.0)


def test_runner_refuses_before_any_roster_or_model_work(monkeypatch) -> None:
    monkeypatch.setattr(runner, "check_run_admission", lambda *a, **k: _refusing_gate())
    monkeypatch.setattr(
        runner, "_resolve_high_slot_pair",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("roster reached")),
    )
    result = runner.run(
        ["django__django-12209"], n_explore=1, replicates=1, budget_cap=1000,
        budget_usd=0.25, per_call_tokens=100, k_self_moa=1, grade_timeout=1,
        timeout_s=1, strategy="explore", roster_n=1, gen_id="g", ver_id="v",
        label="test",
    )
    assert result["refused"] == "monthly_cap"
    assert result["monthly_gate"]["reason"] == "test refusal"


def test_runner_cli_defaults_monthly_cap_to_200_and_exits_2_on_refusal(monkeypatch) -> None:
    captured: dict = {}

    def fake_run(ids, **kwargs):
        captured["ids"] = ids
        captured.update(kwargs)
        return {"refused": "monthly_cap", "monthly_gate": {}}

    monkeypatch.setattr(runner, "run", fake_run)
    rc = runner.main(["--instances", "a,b"])
    assert rc == 2
    assert captured["ids"] == ["a", "b"]
    assert captured["monthly_cap_usd"] == 200.0


def test_runner_cli_monthly_cap_flag_overrides(monkeypatch) -> None:
    captured: dict = {}

    def fake_run(ids, **kwargs):
        captured.update(kwargs)
        return {"closeout": "measured_negative"}

    monkeypatch.setattr(runner, "run", fake_run)
    rc = runner.main(["--instances", "a", "--monthly-cap-usd", "12.5"])
    assert rc == 0
    assert captured["monthly_cap_usd"] == 12.5
