"""Tests for the SIS debit projector (SEED-1).

The contract under test is the doctrine: projection-only, never-a-single-number,
duck-typed over EvidenceReceipt-or-dict, and a clean bridge to the GAIA ComputeUnit
shape — the wire 08_LOOP_TRACE found missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dharma_swarm.gaia_sis_projection import (
    CarbonEstimate,
    aggregate,
    estimate_receipt,
    footprint_report,
)


@dataclass
class _FakeReceipt:
    """Minimal stand-in for spine.EvidenceReceipt (duck-typed; no spine import)."""

    trace_id: str = ""
    provider: str = ""
    model: str = ""
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


def test_estimate_is_a_band_never_a_single_number():
    e = estimate_receipt(_FakeReceipt(model="claude-sonnet", output_tokens=500))
    assert e.p05_gco2 < e.gco2 < e.p95_gco2  # honest uncertainty, both sides
    assert e.gco2 > 0
    assert "rebuttable" in e.footprint_line().lower()
    assert "NOT legal-grade".lower() in e.footprint_line().lower()


def test_works_on_dict_and_object_identically():
    obj = estimate_receipt(_FakeReceipt(model="claude-opus", output_tokens=1000))
    dct = estimate_receipt(
        {"model": "claude-opus", "output_tokens": 1000, "provider": "anthropic"}
    )
    assert abs(obj.gco2 - dct.gco2) < 1e-9  # duck-typed: same result either shape


def test_model_tiering_orders_opus_above_haiku():
    haiku = estimate_receipt(_FakeReceipt(model="claude-haiku", output_tokens=500))
    opus = estimate_receipt(_FakeReceipt(model="claude-opus", output_tokens=500))
    assert opus.gco2 > haiku.gco2  # power-tiered energy => bigger debit


def test_unknown_model_falls_back_and_says_so():
    e = estimate_receipt(_FakeReceipt(model="some-unmapped-model", output_tokens=500))
    assert e.gco2 > 0
    assert "no model match" in e.source.lower()  # honest about the fallback


def test_compute_unit_bridge_shape_matches_gaia_ledger():
    # The bridge 08 found missing: project to ComputeUnit(provider, energy_mwh, carbon_intensity).
    e = estimate_receipt(_FakeReceipt(provider="anthropic", model="claude-sonnet", output_tokens=500))
    cu = e.to_compute_unit_dict()
    assert set(cu) == {"provider", "energy_mwh", "carbon_intensity"}
    assert cu["provider"] == "anthropic"
    assert cu["energy_mwh"] > 0 and cu["carbon_intensity"] > 0
    # round-trips: energy_mwh * carbon_intensity (tCO2e) ~= gco2 (g) / 1e6
    assert abs(cu["energy_mwh"] * cu["carbon_intensity"] - e.gco2 / 1_000_000.0) < 1e-12


def test_compute_unit_bridge_validates_against_real_ledger_model():
    # Review fix proof: the projected dict must construct a REAL gaia_ledger.ComputeUnit
    # (pydantic validation), not merely match a hand-asserted key set. The import lives
    # in the test only; the module itself stays projection-only.
    try:
        from dharma_swarm.gaia_ledger import ComputeUnit
    except Exception:  # pragma: no cover - ledger optional in minimal envs
        import pytest

        pytest.skip("gaia_ledger not importable in this environment")
    e = estimate_receipt(
        _FakeReceipt(provider="anthropic", model="claude-sonnet", output_tokens=500)
    )
    cu = ComputeUnit(**e.to_compute_unit_dict())
    assert cu.provider == "anthropic"
    assert cu.energy_mwh > 0 and cu.carbon_intensity > 0
    # the ledger's own derived quantity agrees with the projector's central estimate
    assert abs(cu.co2e_tons - e.gco2 / 1_000_000.0) < 1e-12


def test_prompt_tokens_drive_energy_scaling():
    prompt_heavy = estimate_receipt(
        _FakeReceipt(model="claude-sonnet", input_tokens=100_000, output_tokens=10)
    )
    terse = estimate_receipt(_FakeReceipt(model="claude-sonnet", output_tokens=10))

    assert prompt_heavy.energy_wh > terse.energy_wh
    assert "input+output-token-scaled" in prompt_heavy.method


def test_transport_receipt_without_model_or_tokens_is_unmetered():
    e = estimate_receipt(_FakeReceipt(provider="nats"))

    assert e.energy_wh == 0.0
    assert e.gco2 == 0.0
    assert "unmetered non-model receipt" in e.source


def test_aggregate_is_the_recursive_n1():
    receipts = [
        _FakeReceipt(model="claude-sonnet", output_tokens=600),
        _FakeReceipt(model="claude-opus", output_tokens=1800),
        _FakeReceipt(model="claude-haiku", output_tokens=200),
    ]
    debit = aggregate(receipts)
    assert debit.count == 3
    assert debit.lower_bound_gco2 < debit.total_gco2 < debit.upper_bound_gco2
    assert debit.p05_gco2 == debit.lower_bound_gco2
    assert debit.p95_gco2 == debit.upper_bound_gco2
    assert len(debit.by_model) == 3
    report = footprint_report(receipts)
    assert "mints nothing" in report  # the debit is not a welfare-ton
    assert "self-debit" in report
    assert "lower" in report and "upper" in report


def test_projection_imports_neither_spine_nor_ledger():
    # Doctrine: a projection cannot become an authority. The module must not couple to
    # the owned spine/ledger surfaces.
    import dharma_swarm.gaia_sis_projection as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "import spine" not in src and "from dharma_swarm.spine" not in src
    assert "import gaia_ledger" not in src and "from dharma_swarm.gaia_ledger" not in src
