"""R3 honest-evidence gate — the BS-detector that separates real edge from the Profit Mirage.

Implements the Bailey & López de Prado Deflated Sharpe Ratio (DSR) with
skewness/kurtosis adjustment and multiple-testing correction, plus a
leakage detector that catches future-information contamination.

Reference: Bailey & López de Prado (2014), "The Deflated Sharpe Ratio:
Correcting for Selection Bias, Backtest Overfitting, and Non-Normality,"
Journal of Portfolio Management.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy import stats

# --- frozen verdict ----------------------------------------------------------


@dataclass(frozen=True)
class EvidenceVerdict:
    passed: bool
    deflated_sharpe: float
    reasons: tuple[str, ...]


# --- expected-maximum helpers ------------------------------------------------


def _expected_max_normals(n: int) -> float:
    """Expected maximum of n i.i.d. standard normal draws (asymptotic expansion)."""
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0 / np.sqrt(np.pi)
    log_n = np.log(float(n))
    sqrt_2log = np.sqrt(2.0 * log_n)
    euler = 0.5772156649015329
    term2 = (np.log(log_n) + np.log(4.0 * np.pi) - 2.0 * euler) / (2.0 * sqrt_2log)
    emax = sqrt_2log - term2
    return float(max(emax, 0.0))


def _expected_max_sr(n_trials: int, trials_sharpe_std: float) -> float:
    """Expected maximum annualized SR under the null across n_trials."""
    return trials_sharpe_std * _expected_max_normals(n_trials)


# --- core DSR ----------------------------------------------------------------


def deflated_sharpe_ratio(
    returns: np.ndarray | list,
    n_trials: int,
    trials_sharpe_std: float | None = None,
    periods_per_year: int = 252,
    sr_benchmark: float = 0.0,
) -> float:
    """Bailey–López de Prado Deflated Sharpe Ratio (probability in [0, 1]).

    Corrects the observed Sharpe ratio for:
      - non-normality (skewness & kurtosis adjustment),
      - multiple-testing bias (the expected maximum SR over *n_trials*
        independent trials under the null grows with *n_trials*).

    Returns the probability that the true Sharpe exceeds the benchmark
    after accounting for selection bias.
    """
    returns = np.asarray(returns, dtype=float)
    T = int(len(returns))
    if T < 2:
        return 0.0

    mu = float(np.mean(returns))
    sigma = float(np.std(returns, ddof=1))
    if sigma < 1e-15:
        return 0.0

    sr_daily = mu / sigma
    sr_annual = sr_daily * np.sqrt(periods_per_year)

    skew = float(stats.skew(returns))
    ex_kurt = float(stats.kurtosis(returns, fisher=True))

    var_sr_daily = (
        1.0 + 0.5 * sr_daily**2 - skew * sr_daily + ex_kurt * sr_daily**2 / 4.0
    ) / T
    if var_sr_daily <= 0.0:
        var_sr_daily = 1e-15
    se_daily = np.sqrt(var_sr_daily)
    se_annual = se_daily * np.sqrt(periods_per_year)

    if trials_sharpe_std is None:
        trials_sharpe_std = float(np.sqrt(periods_per_year / T))
    else:
        trials_sharpe_std = float(trials_sharpe_std) * np.sqrt(periods_per_year)

    emax = _expected_max_sr(n_trials, trials_sharpe_std)
    numerator = sr_annual - sr_benchmark - emax
    z_deflated = numerator / se_annual

    dsr = float(stats.norm.cdf(z_deflated))
    return float(max(min(dsr, 1.0), 0.0))


# --- leakage detection -------------------------------------------------------


def detect_leakage(
    signal: np.ndarray | list,
    forward_returns: np.ndarray | list,
    contemporaneous_returns: np.ndarray | list,
) -> tuple[str, ...]:
    """Flag a signal that is suspiciously correlated with *future* returns.

    Uses Pearson correlation with statistical significance testing: if the
    absolute correlation between *signal* and *forward_returns* is both
    practically large (|r| > 0.10) and statistically significant (p < 0.01),
    the signal is flagged as potential look-ahead leakage.

    Returns a (possibly empty) tuple of flag strings.
    """
    signal = np.asarray(signal, dtype=float)
    forward_returns = np.asarray(forward_returns, dtype=float)

    if len(signal) < 3 or len(forward_returns) < 3:
        return ()

    r, p = stats.pearsonr(signal, forward_returns)
    abs_r = abs(r)
    if abs_r > 0.10 and p < 0.01:
        return ("uses_future_label",)

    return ()


# --- one-stop evaluator ------------------------------------------------------


def evaluate_strategy(
    returns: np.ndarray | list,
    n_trials: int,
    trials_sharpe_std: float | None = None,
    leakage: tuple[str, ...] | None = None,
    dsr_threshold: float = 0.95,
) -> EvidenceVerdict:
    """Run the full honest-evidence gate on a strategy's returns.

    A strategy passes only when:
      1. Its Deflated Sharpe Ratio >= *dsr_threshold*.
      2. No leakage flags are present.

    Parameters
    ----------
    leakage : tuple of str or None
        Pre-computed leakage flags (e.g. from ``detect_leakage``).  When
        ``None``, leakage is not checked.
    """
    reasons: list[str] = []

    dsr = deflated_sharpe_ratio(
        returns,
        n_trials=n_trials,
        trials_sharpe_std=trials_sharpe_std,
    )

    if leakage:
        reasons.extend(leakage)

    if dsr < dsr_threshold:
        reasons.append(f"dsr={dsr:.4f}<{dsr_threshold}")

    passed = len(reasons) == 0
    return EvidenceVerdict(passed=passed, deflated_sharpe=dsr, reasons=tuple(reasons))
