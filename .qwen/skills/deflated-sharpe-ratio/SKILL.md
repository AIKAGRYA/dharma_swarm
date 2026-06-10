---
name: deflated-sharpe-ratio
description: Implement the Bailey & López de Prado Deflated Sharpe Ratio with skew/kurtosis adjustment, expected-max correction, and correct units handling
source: auto-skill
extracted_at: '2026-06-07T00:30:00.000Z'
---

# Deflated Sharpe Ratio (Bailey & López de Prado)

Implementing the DSR for honest-evidence / BS-detector gates in backtesting pipelines.

## Core formula

The DSR is a probability in [0, 1] that the true Sharpe exceeds the benchmark
after accounting for non-normality and multiple-testing bias:

```
DSR = Φ( (SR_annual - SR_benchmark - E[max SR]) / SE_annual )
```

Where `E[max SR]` grows with `n_trials` — this is the teeth that rejects overfit strategies.

## 1. Compute annualized Sharpe

```python
sr_daily = mu / sigma              # daily Sharpe
sr_annual = sr_daily * sqrt(252)   # annualized
```

## 2. Standard error with skew/kurtosis adjustment

The SE of the daily SR, adjusted for non-normality:

```python
skew = stats.skew(returns)
ex_kurt = stats.kurtosis(returns, fisher=True)  # excess kurtosis

var_sr_daily = (1.0 + 0.5 * sr_daily**2 - skew * sr_daily + ex_kurt * sr_daily**2 / 4.0) / T
se_daily = sqrt(var_sr_daily)
se_annual = se_daily * sqrt(252)
```

Source: Bailey & López de Prado (2014), equation for σ(SR).

## 3. Expected maximum SR across n_trials

Expected maximum of `n` i.i.d. standard normal draws (asymptotic expansion):

```python
def _expected_max_normals(n):
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0 / sqrt(pi)   # exact
    log_n = log(n)
    sqrt_2log = sqrt(2 * log_n)
    euler = 0.5772156649015329
    # E[max] ≈ √(2·ln(n)) - (ln(ln(n)) + ln(4π) - 2γ) / (2·√(2·ln(n)))
    term2 = (log(log_n) + log(4*pi) - 2*euler) / (2 * sqrt_2log)
    return max(sqrt_2log - term2, 0.0)
```

Then: `E[max annualized SR] = trials_sharpe_std * _expected_max_normals(n_trials)`

## 4. Critical: units handling for `trials_sharpe_std`

**`trials_sharpe_std` must be annualized.** The SR in the numerator is annualized,
so the expected-max correction must also be in annualized terms.

When `trials_sharpe_std` is provided by the caller, it is assumed to be the std
of *non-annualized* (same-frequency-as-returns) Sharpes across trials. Scale it:

```python
if trials_sharpe_std is None:
    trials_sharpe_std = sqrt(252 / T)          # annualized, under normality
else:
    trials_sharpe_std = float(trials_sharpe_std) * sqrt(252)  # annualize
```

**Why:** callers may compute `trials_sharpe_std` as `std(daily_sharpes)`, not
`std(annualized_sharpes)`. Without annualization, the expected-max correction is
off by a factor of `√252 ≈ 15.87`, making the DSR fail to reject overfit strategies.

## 5. Final DSR

```python
emax = trials_sharpe_std * _expected_max_normals(n_trials)
z = (sr_annual - sr_benchmark - emax) / se_annual
dsr = clamp(stats.norm.cdf(z), 0.0, 1.0)
```

## Behavioral tests to verify correctness

- **Overfit rejection:** best of N random-noise trials → DSR < 0.95
- **Real edge acceptance:** single genuine-edge trial → DSR ≥ 0.95
- **Monotonicity:** more trials → lower DSR (never increases)
- **Leakage trap:** signal == future returns → flagged
- **No false positive:** independent signal → no flag
- **Leakage veto:** high-Sharpe strategy with leakage → rejected regardless
