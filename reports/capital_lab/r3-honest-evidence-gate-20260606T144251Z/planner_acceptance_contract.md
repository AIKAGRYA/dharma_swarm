# R3 Honest-Evidence Gate — Planner Acceptance Contract

- mission_id: `20260606T144251Z-capital-lab-r3-honest-evidence-gate-keystone-bs--8524e4`
- planner: opus_composer
- lane: `~/dharma_capital_lab` (branch `capital-lab/build`)

## The goal (the keystone)

Build `dharma_swarm/capital_lab/honest_evidence.py` — the BS-detector that separates
real edge from the Profit Mirage. Per the deep strategy library, this is the single
most load-bearing component: almost every strategy is decayed/crowded, so the moat
is the honest gate, not the strategies.

## The green-condition (non-negotiable, authored by the planner — DO NOT EDIT)

`tests/test_capital_lab_honest_evidence.py` MUST go from red to **all-passed**:

```
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_capital_lab_honest_evidence.py -q
```

The builder must NOT modify the test file. It encodes the behavioral spec:
1. A known-OVERFIT strategy (best of 200 random trials) is **rejected**.
2. A known-REAL single-trial edge is **accepted**.
3. More trials **monotonically lower** the deflated significance.
4. A future-leaked signal is **caught**; a clean signal raises **no** false positive.
5. Leakage **vetoes** even a high-Sharpe strategy.

## Required interface (the tests import these)

- `deflated_sharpe_ratio(returns, n_trials, trials_sharpe_std=None, periods_per_year=252, sr_benchmark=0.0) -> float` — the real **Bailey–López de Prado** DSR (Φ of the deflated, skew/kurtosis-adjusted statistic; `SR0` grows with `n_trials`). Returns a probability in [0,1].
- `detect_leakage(signal, forward_returns, contemporaneous_returns) -> tuple[str, ...]` — flags signals correlated with the FUTURE beyond a threshold; no false positives on independent signals.
- `evaluate_strategy(returns, n_trials, trials_sharpe_std=None, leakage=None, dsr_threshold=0.95) -> EvidenceVerdict` — `passed=True` only if DSR ≥ threshold AND no leakage.
- `EvidenceVerdict` — frozen dataclass with at least `.passed: bool`, `.deflated_sharpe: float`, `.reasons: tuple[str,...]`.

## Hard constraints

- Fixture/synthetic/free-data only. `live_readiness=0`, `live_authority=false`, no broker, no live keys.
- Real formulas (cite the source in a docstring) — no stubs, no hardcoded pass. The behavioral tests cannot be satisfied without a genuine DSR.
- Keep the module under 500 lines; follow the existing `capital_lab` style (frozen dataclasses, typed, no gratuitous comments).
- Adversary (hermes-m5/GLM) must independently try to break it: a wrong DSR sign, a gameable leakage check, a threshold that lets the overfit through.

## Definition of done

`pytest tests/test_capital_lab_honest_evidence.py` all-passed AND the full
`tests/test_capital_lab_*.py` suite still green AND ruff F-clean AND the adversary
finds no way to make the overfit pass or the real one fail.
