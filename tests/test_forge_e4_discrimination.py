from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.forge_v1.forge_v2 import e4_discrimination


def _ci(n: int = 500, mean: float = 0.1, lower: float = 0.08, upper: float = 0.12) -> dict:
    return {"n": n, "mean": mean, "lower": lower, "upper": upper, "p_le_0": 0.01}


def test_e4_discrimination_passes_non_overlapping_full_confirm() -> None:
    receipt = e4_discrimination.evaluate_discrimination(
        {"confirm_ci": _ci(mean=0.10, lower=0.08, upper=0.12)},
        {"confirm_ci": _ci(mean=0.02, lower=0.0, upper=0.03)},
        good_id="good-scaffold",
        bad_id="bad-scaffold",
    )

    assert receipt["decision"] == "pass"
    assert receipt["promotion_gate_satisfied"] is True
    assert receipt["delta_mean"] == pytest.approx(0.08)
    assert receipt["ci_gap"] == pytest.approx(0.05)
    assert receipt["blockers"] == []
    assert receipt["payload_sha256"]


def test_e4_discrimination_refuses_overlapping_confirm_intervals() -> None:
    receipt = e4_discrimination.evaluate_discrimination(
        {"confirm_ci": _ci(mean=0.07, lower=0.03, upper=0.11)},
        {"confirm_ci": _ci(mean=0.02, lower=0.0, upper=0.05)},
    )

    assert receipt["decision"] == "refused"
    assert receipt["promotion_gate_satisfied"] is False
    assert "confirm_cis_overlap" in receipt["blockers"]


def test_e4_discrimination_refuses_underpowered_confirm() -> None:
    receipt = e4_discrimination.evaluate_discrimination(
        {"confirm_ci": _ci(n=135, mean=0.12, lower=0.08, upper=0.16)},
        {"confirm_ci": _ci(n=135, mean=0.01, lower=-0.01, upper=0.02)},
    )

    assert receipt["decision"] == "refused"
    assert "good_confirm_n<500" in receipt["blockers"]
    assert "bad_confirm_n<500" in receipt["blockers"]


def test_e4_discrimination_refuses_small_effect_even_without_overlap() -> None:
    receipt = e4_discrimination.evaluate_discrimination(
        {"confirm_ci": _ci(mean=0.06, lower=0.055, upper=0.065)},
        {"confirm_ci": _ci(mean=0.02, lower=0.005, upper=0.015)},
    )

    assert receipt["decision"] == "refused"
    assert "delta_mean<min_effect" in receipt["blockers"]


def test_e4_discrimination_cli_exits_nonzero_on_refusal(tmp_path: Path, capsys) -> None:
    good = tmp_path / "good.json"
    bad = tmp_path / "bad.json"
    good.write_text(json.dumps({"confirm_ci": _ci(n=135)}), encoding="utf-8")
    bad.write_text(json.dumps({"confirm_ci": _ci(n=135, mean=0.0, lower=-0.01, upper=0.01)}), encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        raise SystemExit(
            e4_discrimination.main(["--good", str(good), "--bad", str(bad), "--json"])
        )

    assert exc.value.code == 1
    assert "good_confirm_n<500" in capsys.readouterr().out
