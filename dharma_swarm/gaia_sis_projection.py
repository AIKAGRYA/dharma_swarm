"""SIS debit projector — the read-only wire from a dispatch receipt to its ecological cost.

This is SEED-1 of the Verified Nature House / SIS field: the single highest-leverage
build that ``08_LOOP_TRACE`` identified. The verification spine already emits one
``EvidenceReceipt`` per dispatch carrying ``provider``, ``model``, ``input_tokens``,
``output_tokens`` — i.e. everything a per-inference energy/carbon estimate needs. But
nothing reads it for that purpose, and the GAIA credit-world never imports the spine.
The throat (where compute is measured) and the credit-world (where restoration is
priced) are two unwired worlds. **This module is the missing converter** — the swarm
metering its own compute, the strange loop showing up as accounting.

Doctrine (binding):
  * **Projection only.** Pure functions over already-emitted receipts (duck-typed: any
    object or dict with provider/model/token fields). It imports neither ``spine`` nor
    ``gaia_ledger`` and mutates nothing — it cannot become an authority.
  * **Never a single number.** Every estimate carries a p05/p95 band. Per-inference
    energy is contested by ~10x across authoritative bodies and ~65x across deployed
    models; provider telemetry is private. These are decision-useful, **rebuttable**
    estimates, **never legal-grade**.
  * **Mints nothing.** A debit is gross emitted carbon; it is not a welfare-ton and is
    not offset here. Only an externally-countersigned restoration credit mints value.

Seed energy figures are public estimates (model-tiered Wh/inference), labelled with the
declared ~40-50% (and where contested, multiplicative) uncertainty. Sources are carried
on every estimate. The model->energy table is the one genuinely new artifact; it is a
seed, and it says so on every number it produces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

# --- Seed constants (public estimates; rebuttable; NOT legal-grade) -----------------

# Per-inference energy, Wh, central estimate keyed by model-family substring, with a
# multiplicative p05/p95 band that reflects the *real* disagreement in the literature
# (Epoch/Altman ~0.3 Wh vs IEA ~2.9 Wh on a single query; ~65x spread across models;
# Luccioni FAccT 2024). Numbers seeded from 08_SATTVA_ECONOMICS.md (operator-Mac seed,
# not yet metabolised to main -> hard-labelled seed) and public LCA disclosures.
_MODEL_ENERGY_WH: dict[str, dict[str, Any]] = {
    "haiku":   {"wh": 0.22, "lo": 0.4, "hi": 2.5, "src": "08_SATTVA_ECONOMICS seed (Mac, unmetabolised)"},
    "sonnet":  {"wh": 0.95, "lo": 0.4, "hi": 3.0, "src": "08_SATTVA_ECONOMICS seed; cf. Google 0.24 Wh / IEA 2.9 Wh"},
    "opus":    {"wh": 4.05, "lo": 0.4, "hi": 2.5, "src": "08_SATTVA_ECONOMICS seed (model-tiered)"},
    "gpt-4":   {"wh": 0.42, "lo": 0.3, "hi": 70.0, "src": "Jegham 2025 (0.42 Wh; worst-case >29 Wh)"},
    "gemini":  {"wh": 0.24, "lo": 0.4, "hi": 12.0, "src": "Google 2025 median (excludes tail/image)"},
    "llama":   {"wh": 0.30, "lo": 0.3, "hi": 5.0, "src": "ML.ENERGY leaderboard order-of-magnitude"},
    "qwen":    {"wh": 0.30, "lo": 0.3, "hi": 5.0, "src": "open-weight proxy (ML.ENERGY order-of-magnitude)"},
}
_DEFAULT_ENERGY_WH = {"wh": 1.0, "lo": 0.3, "hi": 10.0, "src": "no model match -> generic ~1 Wh placeholder (widest band)"}

_PUE = 1.15            # datacentre power-usage effectiveness (typical; provider-private)
_GRID_GCO2_PER_KWH = 175.0   # grid carbon intensity, gCO2e/kWh (varies ~5x by region/time)
_GRID_LO, _GRID_HI = 0.4, 2.6   # grid-intensity multiplicative band
_REFERENCE_TOTAL_TOKENS = 500  # the table values are calibrated to a ~typical response
_NON_MODEL_PROVIDERS = {"a2a", "nats", "spine", "transport", "kernel"}
_UNMETERED_ENERGY_WH = {
    "wh": 0.0,
    "lo": 1.0,
    "hi": 1.0,
    "src": "no model or token usage -> unmetered non-model receipt",
}

REBUTTABLE_NOTE = (
    "estimate, rebuttable, NOT legal-grade (~1-2 orders-of-magnitude uncertainty; "
    "provider telemetry is private)"
)


# --- The estimate ------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CarbonEstimate:
    """A per-dispatch SIS debit estimate. Always a band, never a single number."""

    trace_id: str
    provider: str
    model: str
    energy_wh: float
    gco2: float            # central estimate
    p05_gco2: float        # low end of the honest band
    p95_gco2: float        # high end of the honest band
    method: str
    source: str

    def to_compute_unit_dict(self) -> dict[str, float | str]:
        """Project to a ``gaia_ledger.ComputeUnit``-shaped dict (energy_mwh,
        carbon_intensity) — the bridge between the throat and the credit-world that
        ``08`` found missing. Returns a plain dict the ledger *could* consume; this
        module never imports or mutates the ledger (projection only)."""
        energy_mwh = self.energy_wh / 1_000_000.0
        carbon_intensity = (self.gco2 / 1_000_000.0) / energy_mwh if energy_mwh else 0.0
        return {
            "provider": self.provider,
            "energy_mwh": energy_mwh,
            "carbon_intensity": carbon_intensity,
        }

    def footprint_line(self) -> str:
        """The one line that prints on every verification this organ produces.
        An intelligence that would verify ecology first shows its own bill."""
        return (
            f"SIS debit ~{self.gco2:.3g} gCO2e "
            f"(p05 {self.p05_gco2:.2g} – p95 {self.p95_gco2:.2g}) "
            f"[{self.model or 'unknown'}; {REBUTTABLE_NOTE}]"
        )


@dataclass(frozen=True, slots=True)
class SisDebit:
    """Aggregate debit over a set of receipts. The recursive n=1 lives here."""

    count: int
    total_gco2: float
    lower_bound_gco2: float
    upper_bound_gco2: float
    total_energy_wh: float
    by_model: dict[str, float] = field(default_factory=dict)

    @property
    def p05_gco2(self) -> float:
        """Compatibility alias for the summed conservative lower bound."""
        return self.lower_bound_gco2

    @property
    def p95_gco2(self) -> float:
        """Compatibility alias for the summed conservative upper bound."""
        return self.upper_bound_gco2

    def footprint_report(self) -> str:
        head = (
            f"SIS self-debit over {self.count} dispatch(es): "
            f"~{self.total_gco2:.3g} gCO2e "
            f"(lower {self.lower_bound_gco2:.2g} – upper {self.upper_bound_gco2:.2g}), "
            f"~{self.total_energy_wh:.3g} Wh. {REBUTTABLE_NOTE}."
        )
        lines = [head]
        for model, g in sorted(self.by_model.items(), key=lambda kv: -kv[1]):
            lines.append(f"  - {model}: ~{g:.3g} gCO2e")
        lines.append(
            "  (gross emitted carbon, not a welfare-ton; mints nothing; "
            "offset only by externally-countersigned restoration above quorum)"
        )
        return "\n".join(lines)


# --- The projection (pure, duck-typed over EvidenceReceipt or dict) -----------------

def _get(receipt: Any, key: str) -> Any:
    if isinstance(receipt, Mapping):
        return receipt.get(key)
    return getattr(receipt, key, None)


def _model_entry(model: str) -> dict[str, Any]:
    m = (model or "").lower()
    for substr, entry in _MODEL_ENERGY_WH.items():
        if substr in m:
            return entry
    return _DEFAULT_ENERGY_WH


def _token_count(value: Any) -> float:
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return 0.0


def estimate_receipt(receipt: Any) -> CarbonEstimate:
    """Project one already-emitted receipt to an estimated SIS debit. Pure; read-only."""
    model = _get(receipt, "model") or ""
    provider = _get(receipt, "provider") or ""
    trace_id = _get(receipt, "trace_id") or ""
    in_tok = _get(receipt, "input_tokens")
    out_tok = _get(receipt, "output_tokens")
    total_tokens = _token_count(in_tok) + _token_count(out_tok)

    provider_key = str(provider).strip().lower()
    if not model and total_tokens == 0 and provider_key in _NON_MODEL_PROVIDERS:
        entry = _UNMETERED_ENERGY_WH
    else:
        entry = _model_entry(model)
    base_wh = float(entry["wh"])
    # Crude, honestly-banded scaling: energy tracks total receipt tokens against a reference.
    scale = 1.0
    if total_tokens > 0:
        scale = max(0.1, min(10.0, total_tokens / _REFERENCE_TOTAL_TOKENS))
    energy_wh = base_wh * scale

    def _g(grid: float) -> float:
        return (energy_wh / 1000.0) * _PUE * grid  # Wh->kWh * PUE * gCO2/kWh

    central = _g(_GRID_GCO2_PER_KWH)
    p05 = _g(_GRID_GCO2_PER_KWH * _GRID_LO) * float(entry["lo"])
    p95 = _g(_GRID_GCO2_PER_KWH * _GRID_HI) * float(entry["hi"])
    return CarbonEstimate(
        trace_id=trace_id,
        provider=provider,
        model=model,
        energy_wh=energy_wh,
        gco2=central,
        p05_gco2=min(p05, central),
        p95_gco2=max(p95, central),
        method=(
            f"Wh(model)xPUE({_PUE})xgrid({_GRID_GCO2_PER_KWH}gCO2/kWh), "
            f"input+output-token-scaled; band = grid x model-energy contestation"
        ),
        source=str(entry["src"]),
    )


def aggregate(receipts: Iterable[Any]) -> SisDebit:
    """Aggregate a set of receipts into the SIS self-debit (the recursive n=1)."""
    n = 0
    tot = p05 = p95 = wh = 0.0
    by_model: dict[str, float] = {}
    for r in receipts:
        e = estimate_receipt(r)
        n += 1
        tot += e.gco2
        p05 += e.p05_gco2
        p95 += e.p95_gco2
        wh += e.energy_wh
        by_model[e.model or "unknown"] = by_model.get(e.model or "unknown", 0.0) + e.gco2
    return SisDebit(
        count=n, total_gco2=tot, lower_bound_gco2=p05, upper_bound_gco2=p95,
        total_energy_wh=wh, by_model=by_model,
    )


def footprint_report(receipts: Iterable[Any]) -> str:
    """The printable footprint — the thing that goes on every SIS verification."""
    return aggregate(receipts).footprint_report()


if __name__ == "__main__":  # pragma: no cover - the recursive n=1 demonstration
    # Illustration over a representative receipt set (estimate, not a measured claim).
    sample = [
        {"trace_id": "demo-1", "provider": "example", "model": "sonnet-family", "output_tokens": 600},
        {"trace_id": "demo-2", "provider": "example", "model": "opus-family", "output_tokens": 1800},
        {"trace_id": "demo-3", "provider": "example", "model": "haiku-family", "output_tokens": 200},
    ]
    print(footprint_report(sample))
    print("\n(illustrative seed estimate; the swarm metering its own compute — SEED-1)")
