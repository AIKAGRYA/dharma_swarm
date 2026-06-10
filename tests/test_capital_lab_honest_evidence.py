"""R3 honest-evidence gate — the KEYSTONE green-condition (authored by the planner).

These are BEHAVIORAL acceptance tests, not unit tests the builder can trivially
satisfy. They define "correct" for the BS-detector and cannot be gamed without
actually implementing a real Deflated Sharpe Ratio + leakage detection:

  1. A known-OVERFIT strategy (best of many random trials) MUST be rejected.
  2. A known-REAL signal (genuine edge, one trial) MUST be accepted.
  3. A strategy using FUTURE-leaked information MUST be caught.
  4. More trials MUST monotonically lower the deflated significance (the
     multiple-testing teeth).

The builder implements `dharma_swarm/capital_lab/honest_evidence.py` to pass
these. The builder did NOT write these tests — that separation is the point.

Required interface (the builder must provide):
    deflated_sharpe_ratio(returns, n_trials, trials_sharpe_std=None,
                          periods_per_year=252, sr_benchmark=0.0) -> float   # DSR in [0,1]
    detect_leakage(signal, forward_returns, contemporaneous_returns) -> tuple[str, ...]
    evaluate_strategy(returns, n_trials, trials_sharpe_std=None,
                     leakage=None, dsr_threshold=0.95) -> EvidenceVerdict
    EvidenceVerdict: frozen dataclass with at least .passed (bool),
                    .deflated_sharpe (float), .reasons (tuple[str,...])
"""

from __future__ import annotations

import numpy as np

# Direct import: this file is HARD-RED until the builder ships honest_evidence.py.
# (Skipping would let the runner mistake "not built" for "done" — the green-condition
# is PASSED, never skipped.)
from dharma_swarm.capital_lab import honest_evidence as honest


def _best_of_random(n_trials: int, n_obs: int, seed: int):
    """Return (returns_of_best_trial, std_of_trial_sharpes) for n_trials pure-noise
    strategies — a textbook overfit: the winner looks great in-sample by luck."""
    rng = np.random.default_rng(seed)
    trials = rng.normal(0.0, 0.01, size=(n_trials, n_obs))  # zero true edge
    sharpes = trials.mean(axis=1) / (trials.std(axis=1) + 1e-12)
    best = int(np.argmax(sharpes))
    return trials[best], float(np.std(sharpes, ddof=1))


def _real_edge(n_obs: int, seed: int):
    """A single strategy with a genuine, modest positive edge (not selected)."""
    rng = np.random.default_rng(seed)
    return rng.normal(0.0006, 0.01, size=n_obs)  # ~0.95 daily-annualized SR-ish, real


def test_rejects_known_overfit_strategy():
    returns, sr_std = _best_of_random(n_trials=200, n_obs=750, seed=7)
    v = honest.evaluate_strategy(returns, n_trials=200, trials_sharpe_std=sr_std,
                                 dsr_threshold=0.95)
    assert v.passed is False, "overfit best-of-200 must be rejected"
    assert v.deflated_sharpe < 0.95


def test_accepts_known_real_signal():
    returns = _real_edge(n_obs=1500, seed=3)
    v = honest.evaluate_strategy(returns, n_trials=1, dsr_threshold=0.95)
    assert v.passed is True, "a genuine single-trial edge must be accepted"
    assert v.deflated_sharpe >= 0.95


def test_more_trials_monotonically_lower_significance():
    # same observed strategy, evaluated as if found among more trials -> lower DSR
    returns = _real_edge(n_obs=1500, seed=3)
    dsr_1 = honest.deflated_sharpe_ratio(returns, n_trials=1)
    dsr_50 = honest.deflated_sharpe_ratio(returns, n_trials=50, trials_sharpe_std=0.5)
    dsr_500 = honest.deflated_sharpe_ratio(returns, n_trials=500, trials_sharpe_std=0.5)
    assert dsr_1 >= dsr_50 >= dsr_500, "more trials must not increase deflated significance"


def test_leakage_trap_catches_future_information():
    rng = np.random.default_rng(11)
    fwd = rng.normal(0, 0.01, size=1000)              # tomorrow's return
    leaked_signal = fwd.copy()                         # signal IS the future -> leakage
    flags = honest.detect_leakage(leaked_signal, forward_returns=fwd,
                                  contemporaneous_returns=rng.normal(0, 0.01, size=1000))
    assert len(flags) > 0, "a signal equal to future returns must raise a leakage flag"


def test_clean_signal_has_no_leakage_flag():
    rng = np.random.default_rng(12)
    fwd = rng.normal(0, 0.01, size=1000)
    honest_signal = rng.normal(0, 1, size=1000)        # independent of the future
    flags = honest.detect_leakage(honest_signal, forward_returns=fwd,
                                  contemporaneous_returns=rng.normal(0, 0.01, size=1000))
    assert len(flags) == 0, "a clean signal must not raise leakage (no false positive)"


def test_leaked_strategy_is_rejected_even_with_high_sharpe():
    # a leaked strategy can show a gorgeous Sharpe but MUST still fail the gate
    rng = np.random.default_rng(5)
    fwd = rng.normal(0.0, 0.01, size=1200)
    leaked_returns = np.abs(fwd) * 0.8                 # "perfect" lookahead pnl
    v = honest.evaluate_strategy(leaked_returns, n_trials=1,
                                 leakage=("uses_future_label",), dsr_threshold=0.95)
    assert v.passed is False, "leakage must veto even a high-Sharpe strategy"
