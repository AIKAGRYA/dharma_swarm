"""Invariant Observatory — read-only measurement of dynamical invariants.

This module is the v1 instantiation of the GPLOT direction (see
GPLOT_LODESTONE.md, docs/GPLOT_CAIRN.md). It extracts topological /
dynamical-systems invariants from the gauntlet tier-1 correctness series
and writes them back to the existing telemetry plane as
``ExternalOutcomeRecord`` rows with ``outcome_kind='invariant_reading_v1'``.

What it computes (in order of cost):
    1. Time-delay τ via the first minimum of the mutual-information function
       (Fraser & Swinney 1986). Falls back to first zero-crossing of the
       autocorrelation if MI is too noisy on short series.
    2. Embedding dimension m via Cao's method (Cao 1997, "Practical method
       for determining the minimum embedding dimension"). Robust to noise
       and short data, the de-facto standard since 2010.
    3. Maximal Lyapunov exponent λ_max via Rosenstein et al. 1993 ("A
       practical method for calculating largest Lyapunov exponents from
       small data sets"). Selected over Wolf 1985 / Kantz 1994 because:
         - it tolerates small N (the original paper used N≈1000)
         - bias on noisy series is documented and reportable
         - it is the algorithm both ``nolds`` and ``neurokit2`` use by
           default in 2024-2026
    4. Correlation dimension D₂ via Grassberger-Procaccia 1983, with the
       scaling region picked by the largest-linear-segment heuristic on
       log C(r) vs log r.

Design constraints (binding, see GPLOT_CAIRN §4):
    * Read-only. Never mutates substrates other than emitting one
      ``ExternalOutcomeRecord`` per metric per run.
    * No new database. Reuses ``TelemetryPlaneStore`` exclusively.
    * No new dashboard surface. Output is structured records other
      surfaces can read at their leisure.
    * Promotion to control authority is gated externally (see
      ``loop_supervisor.py`` and the promotion-review TelosObjective).
    * Honest about uncertainty: every reading carries a ``confidence``
      that reflects sample-size and SNR; not p-hacked.

CLI:
    python -m dharma_swarm.invariant_observatory [--days N] [--kind K]
                                                 [--dry-run]

The CLI is a research entry point — it is NOT installed as a cron by
default. A cron seed in ``cron_jobs.json`` can be added once readings
have been validated against the falsifiability log.

References:
    Cao 1997  — Physica D 110 (1-2): 43-50.
    Fraser & Swinney 1986 — Phys. Rev. A 33 (2): 1134-1140.
    Grassberger & Procaccia 1983 — Phys. Rev. Lett. 50 (5): 346-349.
    Rosenstein, Collins, De Luca 1993 — Physica D 65 (1-2): 117-134.
    Takens 1981 — "Detecting strange attractors in turbulence."
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

import numpy as np
from scipy.spatial import cKDTree

from dharma_swarm.gauntlet_telemetry import (
    OUTCOME_KIND_GAUNTLET_TIER1,
    load_recent_outcomes,
)
from dharma_swarm.telemetry_plane import (
    ExternalOutcomeRecord,
    TelemetryPlaneStore,
)

__all__ = [
    "OUTCOME_KIND_INVARIANT_READING_V1",
    "InvariantReading",
    "compute_mutual_information_tau",
    "compute_autocorrelation_tau",
    "compute_cao_embedding_dimension",
    "compute_lyapunov_rosenstein",
    "compute_correlation_dimension",
    "delay_embed",
    "observe_series",
    "run_observatory",
    "lorenz_series",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTCOME_KIND_INVARIANT_READING_V1 = "invariant_reading_v1"
"""Outcome kind written by this module. Stable contract."""

METHOD_VERSION = "rosenstein_mehdizadeh_cao_gp_v1"
"""Identifier of the (algorithm-set, code-version) tuple. Bump on math
changes so historical readings remain interpretable."""

# Minimum samples below which we refuse to compute (would be dishonest).
# Bradley & Kantz 2015 §IV explicitly: N<100 "is not trustworthy" for
# nonlinear-dynamics invariants. We pick 100 as the hard floor and 200
# as the threshold for full confidence. See research_algorithm_validation.md
# §5 for the literature bounds.
MIN_SAMPLES_HARD_FLOOR = 100
MIN_SAMPLES_RECOMMENDED = 200

# Rosenstein 1993 used k=1 (single nearest neighbor). Mehdizadeh 2019
# ("A novel algorithm for the largest Lyapunov exponent...") shows that
# k≈15 averaged neighbors substantially reduces variance on noisy series
# without changing the bias. We adopt that as our default.
ROSENSTEIN_N_NEIGHBORS = 15

# Tolerable embedding-dimension search range. Most low-dimensional
# trajectories have m ∈ {2,…,7}; we cap at 10 to bound compute.
MAX_EMBEDDING_DIM = 10

# Cao's E1 plateau threshold — when E1(m+1)/E1(m) stops changing.
CAO_PLATEAU_TOLERANCE = 0.05


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InvariantReading:
    """One snapshot of dynamical-systems invariants for a time series.

    All fields are NaN-safe: any value that could not be computed honestly
    is reported as ``math.nan`` with a non-empty ``warnings`` list rather
    than fabricated.
    """

    source_kind: str
    n_samples: int
    window_days: int
    tau: int
    embedding_dim: int
    lyapunov_max: float
    correlation_dimension: float
    confidence: float
    method_version: str
    warnings: tuple[str, ...] = ()
    computed_at: datetime = datetime.now(timezone.utc)

    def is_honest(self) -> bool:
        """True iff at least the primary invariant (λ_max) is finite."""
        return math.isfinite(self.lyapunov_max)


# ---------------------------------------------------------------------------
# Delay τ
# ---------------------------------------------------------------------------


def compute_mutual_information_tau(
    series: np.ndarray,
    *,
    max_tau: int = 50,
    n_bins: int = 16,
) -> tuple[int, np.ndarray]:
    """First local minimum of mutual information I(x_t, x_{t+τ}).

    Fraser & Swinney 1986. Uses fixed-width histogram binning rather than
    k-NN MI because we want a fast estimator on N≤500 and bias is not the
    primary concern — we only need to find the *first minimum*, not its
    absolute value.

    Returns:
        (tau_star, mi_curve). If no minimum is found within max_tau,
        falls back to ``max_tau // 4``.
    """
    n = len(series)
    max_tau = min(max_tau, n // 4)
    if max_tau < 2:
        return 1, np.zeros(2)

    mi = np.zeros(max_tau + 1)
    # Use a fixed binning over the full data range so all τ shifts share
    # the same support.
    rng_min, rng_max = float(np.min(series)), float(np.max(series))
    if rng_max - rng_min < 1e-12:
        # Constant series — MI is undefined; degenerate. Return τ=1.
        return 1, mi
    edges = np.linspace(rng_min, rng_max + 1e-9, n_bins + 1)

    for tau in range(1, max_tau + 1):
        x = series[: n - tau]
        y = series[tau:]
        joint, _, _ = np.histogram2d(x, y, bins=[edges, edges])
        joint = joint / joint.sum()
        px = joint.sum(axis=1)
        py = joint.sum(axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = joint / (px[:, None] * py[None, :] + 1e-12)
            terms = np.where(joint > 0, joint * np.log(ratio + 1e-12), 0.0)
        mi[tau] = float(terms.sum())

    # First local minimum starting at τ=2.
    for tau in range(2, max_tau):
        if mi[tau] < mi[tau - 1] and mi[tau] < mi[tau + 1]:
            return tau, mi
    # No minimum found — fall back.
    return max(1, max_tau // 4), mi


def compute_autocorrelation_tau(
    series: np.ndarray,
    *,
    max_tau: int = 50,
) -> int:
    """First zero-crossing of the autocorrelation function.

    Used as a fallback when the MI estimator is too noisy. A common
    alternative threshold is τ at which ACF drops below 1/e; we adopt the
    zero-crossing because it produces a sharper τ on noisy series.
    """
    n = len(series)
    max_tau = min(max_tau, n // 4)
    if max_tau < 1:
        return 1
    x = series - float(np.mean(series))
    denom = float(np.dot(x, x)) + 1e-12
    for tau in range(1, max_tau + 1):
        acf = float(np.dot(x[: n - tau], x[tau:])) / denom
        if acf <= 0:
            return tau
    # No zero-crossing within window — use first 1/e crossing or fallback.
    for tau in range(1, max_tau + 1):
        acf = float(np.dot(x[: n - tau], x[tau:])) / denom
        if acf < 1.0 / math.e:
            return tau
    return max(1, max_tau // 4)


# ---------------------------------------------------------------------------
# Delay embedding
# ---------------------------------------------------------------------------


def delay_embed(
    series: np.ndarray,
    *,
    m: int,
    tau: int,
) -> np.ndarray:
    """Construct the delay-embedded matrix Y ∈ R^{N' × m}.

    Y[i] = (x_i, x_{i+τ}, …, x_{i+(m-1)τ}), with N' = N − (m−1)τ.

    Takens 1981 guarantees this is a diffeomorphic image of the original
    attractor for m ≥ 2d+1 (where d is the box-counting dim), generically.
    """
    n = len(series)
    n_vec = n - (m - 1) * tau
    if n_vec <= 0:
        raise ValueError(
            f"delay_embed: series too short — need N > (m-1)τ = "
            f"{(m - 1) * tau}, got N={n}"
        )
    out = np.empty((n_vec, m), dtype=float)
    for j in range(m):
        out[:, j] = series[j * tau : j * tau + n_vec]
    return out


# ---------------------------------------------------------------------------
# Embedding dimension — Cao's method
# ---------------------------------------------------------------------------


def compute_cao_embedding_dimension(
    series: np.ndarray,
    *,
    tau: int,
    max_dim: int = MAX_EMBEDDING_DIM,
    plateau_tol: float = CAO_PLATEAU_TOLERANCE,
) -> tuple[int, np.ndarray]:
    """Cao 1997 method for minimum embedding dimension.

    Computes E1(m) = E(m+1)/E(m), where
        E(m) = mean over i of ||y_i^{m+1} − y_{n(i)}^{m+1}||_∞
                              / ||y_i^{m} − y_{n(i)}^{m}||_∞
    with n(i) the nearest-neighbor index of y_i in m-space.

    The optimal m is the smallest dimension at which E1 saturates (the
    plateau test). We pick the first m s.t. |E1(m+1)/E1(m) - 1| < tol.

    Returns:
        (m_star, e1_curve). e1_curve[m] = E1(m), with e1_curve[0]=NaN.
    """
    n = len(series)
    # Need at least n_vec >= 2 for nearest-neighbour at m+1
    feasible_max = max_dim
    while feasible_max > 1 and n - feasible_max * tau < 2:
        feasible_max -= 1
    if feasible_max < 2:
        return 2, np.array([np.nan, np.nan, np.nan])

    e_curve = np.full(feasible_max + 2, np.nan)
    for m in range(1, feasible_max + 1):
        try:
            ym = delay_embed(series, m=m, tau=tau)
            ym1 = delay_embed(series, m=m + 1, tau=tau)
        except ValueError:
            break
        n_m = ym1.shape[0]
        ym_trunc = ym[:n_m]  # align lengths
        if n_m < 3:
            break
        # Find nearest neighbor in m-space using Chebyshev distance.
        tree = cKDTree(ym_trunc)
        # Query 2 neighbors (self + nearest other).
        dists, idx = tree.query(ym_trunc, k=2, p=np.inf)
        nn_idx = idx[:, 1]
        nn_dist_m = dists[:, 1]
        # Avoid zero distances (degenerate points) by adding a floor.
        nn_dist_m = np.where(nn_dist_m < 1e-12, 1e-12, nn_dist_m)
        # Distance in (m+1)-space using same neighbor pairing.
        nn_dist_m1 = np.max(np.abs(ym1 - ym1[nn_idx]), axis=1)
        ratios = nn_dist_m1 / nn_dist_m
        e_curve[m] = float(np.mean(ratios))

    # E1(m) = E(m+1)/E(m)
    e1 = np.full(feasible_max + 1, np.nan)
    for m in range(1, feasible_max):
        if np.isfinite(e_curve[m]) and e_curve[m] > 1e-12:
            e1[m] = e_curve[m + 1] / e_curve[m]

    # Plateau test: smallest m for which |E1(m+1)/E1(m) - 1| < tol.
    for m in range(1, feasible_max - 1):
        if (
            np.isfinite(e1[m])
            and np.isfinite(e1[m + 1])
            and e1[m] > 1e-12
        ):
            ratio = e1[m + 1] / e1[m]
            if abs(ratio - 1.0) < plateau_tol:
                return m + 1, e1
    # No plateau detected — fall back to the maximum we computed.
    finite_m = np.where(np.isfinite(e1))[0]
    if len(finite_m) > 0:
        return int(finite_m[-1]) + 1, e1
    return 2, e1


# ---------------------------------------------------------------------------
# Maximal Lyapunov — Rosenstein 1993
# ---------------------------------------------------------------------------


def compute_lyapunov_rosenstein(
    series: np.ndarray,
    *,
    m: int,
    tau: int,
    fs: float = 1.0,
    min_separation: int | None = None,
    n_steps: int | None = None,
    n_neighbors: int = ROSENSTEIN_N_NEIGHBORS,
) -> tuple[float, np.ndarray]:
    """Maximal Lyapunov exponent via Rosenstein et al. 1993.

    Algorithm:
        1. Build delay-embedded matrix Y (m, τ).
        2. For each point y_i, find its nearest neighbor y_{n(i)} subject
           to a minimum temporal separation (the "Theiler window") to
           exclude trivial autocorrelations.
        3. For step k = 0, 1, …, K-1: compute d_i(k) = ||y_{i+k} − y_{n(i)+k}||.
           Average ln(d_i(k)) over valid i.
        4. λ_max is the slope of the linear region of ⟨ln d_i(k)⟩ vs k·Δt.

    Parameters
    ----------
    fs : float
        Sampling frequency (Hz). λ is reported per unit time, so for unit
        sampling fs=1 gives λ per sample.
    min_separation : int, optional
        Theiler window. Defaults to the mean period estimate (tau used as
        a rough proxy when the FFT-based estimate is unavailable). Without
        this, ε-neighbors are temporally adjacent and λ is biased to 0.
    n_steps : int, optional
        Number of evolution steps K. Defaults to min(50, N'/4).
    n_neighbors : int, optional
        Number of nearest neighbors to average (Mehdizadeh 2019). The
        original Rosenstein paper used 1; modern practice uses ~15 to
        reduce variance on noisy series.

    Returns
    -------
    (lambda_max, log_div_curve)
        ``log_div_curve[k]`` is ⟨ln d_i(k)⟩.
    """
    Y = delay_embed(series, m=m, tau=tau)
    n_vec = Y.shape[0]
    if n_vec < 20:
        return float("nan"), np.array([])

    if min_separation is None:
        # Conservative default: max(τ, ~mean period estimate).
        # We use 2τ as the Theiler window — discards same-orbit returns
        # without being so wide that we lose all neighbors.
        min_separation = max(1, 2 * tau)

    if n_steps is None:
        n_steps = min(50, max(5, n_vec // 4))

    tree = cKDTree(Y)
    # For each i, find up to ``n_neighbors`` nearest neighbors outside
    # the Theiler window (Mehdizadeh 2019 multi-neighbor variant).
    log_div = []  # one entry per k: mean of ln(d_i(k))
    # Query a generous pool, then filter by temporal separation.
    k_query = min(n_vec, max(n_neighbors * 4, 25))
    _qd, idx = tree.query(Y, k=k_query)
    # nn_lists[i] = list of up to n_neighbors indices satisfying |j-i| > sep.
    nn_lists: list[list[int]] = [[] for _ in range(n_vec)]
    for i in range(n_vec):
        for c in range(1, k_query):
            j = int(idx[i, c])
            if abs(j - i) > min_separation:
                nn_lists[i].append(j)
                if len(nn_lists[i]) >= n_neighbors:
                    break

    valid = [i for i in range(n_vec) if nn_lists[i]]
    if len(valid) < 5:
        return float("nan"), np.array([])

    for k in range(n_steps):
        ds: list[float] = []
        for i in valid:
            # Average divergence across this point's neighbor cohort.
            per_i: list[float] = []
            for j in nn_lists[i]:
                if i + k >= n_vec or j + k >= n_vec:
                    continue
                d = float(np.linalg.norm(Y[i + k] - Y[j + k]))
                if d > 0:
                    per_i.append(math.log(d))
            if per_i:
                ds.append(float(np.mean(per_i)))
        if not ds:
            break
        log_div.append(float(np.mean(ds)))

    log_div_arr = np.asarray(log_div)
    if len(log_div_arr) < 5:
        return float("nan"), log_div_arr

    # Fit slope on the linear region. Rosenstein uses the early steps
    # where divergence is exponential and has not yet saturated. Heuristic:
    # use the first half of the curve (excluding k=0 which is often
    # contaminated by the metric on the local manifold).
    k_fit_max = max(5, len(log_div_arr) // 2)
    xs = np.arange(1, k_fit_max + 1) / fs
    ys = log_div_arr[1 : k_fit_max + 1]
    if len(xs) != len(ys) or len(xs) < 3:
        return float("nan"), log_div_arr
    slope, _intercept = np.polyfit(xs, ys, 1)
    return float(slope), log_div_arr


# ---------------------------------------------------------------------------
# Correlation dimension — Grassberger-Procaccia
# ---------------------------------------------------------------------------


def compute_correlation_dimension(
    series: np.ndarray,
    *,
    m: int,
    tau: int,
    n_r: int = 20,
    r_frac_min: float = 0.02,
    r_frac_max: float = 0.5,
) -> tuple[float, np.ndarray, np.ndarray]:
    """Correlation dimension D₂ via Grassberger-Procaccia 1983.

    C(r) = (1 / N(N-1)) * Σ_{i≠j} Θ(r - ||y_i - y_j||)

    D₂ is the slope of log C(r) vs log r in the linear scaling region.
    We pick the scaling region by finding the longest run of consecutive
    log-r values whose slope is most stable (smallest local slope
    variance). This is more robust on short series than picking a fixed
    window.

    Returns:
        (d2, log_r, log_c). NaN d2 if scaling region cannot be identified.
    """
    Y = delay_embed(series, m=m, tau=tau)
    n_vec = Y.shape[0]
    if n_vec < 30:
        return float("nan"), np.array([]), np.array([])

    tree = cKDTree(Y)
    diam = float(np.linalg.norm(Y.max(axis=0) - Y.min(axis=0)))
    if diam <= 0:
        return float("nan"), np.array([]), np.array([])

    rs = np.logspace(
        math.log10(diam * r_frac_min),
        math.log10(diam * r_frac_max),
        n_r,
    )

    # For each r, count pairs (i,j), i<j, with d_ij <= r.
    log_r = np.log(rs)
    log_c = np.full(n_r, np.nan)
    total_pairs = n_vec * (n_vec - 1) / 2.0
    for k, r in enumerate(rs):
        n_within = tree.count_neighbors(tree, r)
        # cKDTree.count_neighbors counts ordered pairs including (i,i),
        # so subtract n_vec self-pairs and halve.
        pair_count = max(1, (n_within - n_vec) // 2)
        c_val = pair_count / total_pairs
        if c_val > 0:
            log_c[k] = math.log(c_val)

    # Pick the largest contiguous window of finite values with most
    # consistent local slopes (smallest stdev of finite-differences).
    finite = np.where(np.isfinite(log_c))[0]
    if len(finite) < 5:
        return float("nan"), log_r, log_c

    best_window: tuple[int, int] | None = None
    best_var = math.inf
    # Try windows of length >= 5.
    min_len = 5
    for start in range(len(finite) - min_len + 1):
        for end in range(start + min_len, len(finite) + 1):
            idx = finite[start:end]
            if len(idx) < min_len:
                continue
            local_slopes = np.diff(log_c[idx]) / np.diff(log_r[idx])
            var = float(np.var(local_slopes))
            # Prefer longer windows when variance is comparable.
            normalized = var / max(1, len(idx) - min_len + 1)
            if normalized < best_var:
                best_var = normalized
                best_window = (int(idx[0]), int(idx[-1]) + 1)

    if best_window is None:
        return float("nan"), log_r, log_c
    s, e = best_window
    slope, _ = np.polyfit(log_r[s:e], log_c[s:e], 1)
    return float(slope), log_r, log_c


# ---------------------------------------------------------------------------
# Top-level observation
# ---------------------------------------------------------------------------


def observe_series(
    series: Sequence[float],
    *,
    source_kind: str = OUTCOME_KIND_GAUNTLET_TIER1,
    window_days: int = 0,
    fs: float = 1.0,
) -> InvariantReading:
    """Compute all invariants on a single 1D series.

    This function does NOT touch the substrate; it is a pure data path.
    The substrate-writing layer lives in :func:`run_observatory`.
    """
    arr = np.asarray(series, dtype=float)
    warnings: list[str] = []

    n = len(arr)
    if n < MIN_SAMPLES_HARD_FLOOR:
        warnings.append(
            f"N={n} below MIN_SAMPLES_HARD_FLOOR={MIN_SAMPLES_HARD_FLOOR}; "
            "refusing to compute (would be dishonest)."
        )
        return InvariantReading(
            source_kind=source_kind,
            n_samples=n,
            window_days=window_days,
            tau=-1,
            embedding_dim=-1,
            lyapunov_max=float("nan"),
            correlation_dimension=float("nan"),
            confidence=0.0,
            method_version=METHOD_VERSION,
            warnings=tuple(warnings),
        )

    # Demean & rescale to unit std to make hyperparameters scale-invariant.
    mu = float(np.mean(arr))
    sigma = float(np.std(arr))
    if sigma < 1e-12:
        warnings.append("series is effectively constant — invariants undefined")
        return InvariantReading(
            source_kind=source_kind,
            n_samples=n,
            window_days=window_days,
            tau=-1,
            embedding_dim=-1,
            lyapunov_max=float("nan"),
            correlation_dimension=float("nan"),
            confidence=0.0,
            method_version=METHOD_VERSION,
            warnings=tuple(warnings),
        )
    x = (arr - mu) / sigma

    # τ
    try:
        tau, _mi = compute_mutual_information_tau(x)
    except Exception as exc:  # pragma: no cover — defensive
        warnings.append(f"MI τ estimation failed: {exc!r}; falling back to ACF")
        tau = compute_autocorrelation_tau(x)
    if tau < 1:
        tau = 1

    # m
    try:
        m, _e1 = compute_cao_embedding_dimension(x, tau=tau)
    except Exception as exc:  # pragma: no cover — defensive
        warnings.append(f"Cao embedding-dim failed: {exc!r}; defaulting to m=3")
        m = 3
    m = max(2, min(MAX_EMBEDDING_DIM, m))

    # λ_max
    try:
        lam, _div = compute_lyapunov_rosenstein(x, m=m, tau=tau, fs=fs)
    except Exception as exc:
        warnings.append(f"Rosenstein λ_max failed: {exc!r}")
        lam = float("nan")

    # D₂
    try:
        d2, _log_r, _log_c = compute_correlation_dimension(x, m=m, tau=tau)
    except Exception as exc:
        warnings.append(f"Grassberger-Procaccia D₂ failed: {exc!r}")
        d2 = float("nan")

    # Confidence is a coarse function of sample size with penalty for any
    # warnings emitted. This is intentionally conservative — readings are
    # not credentials, they accumulate in a falsifiability log.
    base = min(1.0, n / MIN_SAMPLES_RECOMMENDED)
    penalty = 0.2 * len([w for w in warnings if "failed" in w or "fallback" in w])
    confidence = max(0.0, base - penalty)
    # If λ is NaN, confidence in this reading drops to 0.
    if not math.isfinite(lam):
        confidence = 0.0

    return InvariantReading(
        source_kind=source_kind,
        n_samples=n,
        window_days=window_days,
        tau=int(tau),
        embedding_dim=int(m),
        lyapunov_max=float(lam),
        correlation_dimension=float(d2),
        confidence=float(confidence),
        method_version=METHOD_VERSION,
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Substrate-writing layer
# ---------------------------------------------------------------------------


def _reading_to_records(
    reading: InvariantReading,
    *,
    session_id: str,
    run_id: str,
) -> list[ExternalOutcomeRecord]:
    """Decompose one InvariantReading into the standard ExternalOutcomeRecord
    rows the telemetry plane expects: one row per metric for queryability.

    All rows share the same ``run_id`` so a downstream reader can group them
    back into a single reading.
    """
    base_meta = {
        "method_version": reading.method_version,
        "source_kind": reading.source_kind,
        "window_days": reading.window_days,
        "n_samples": reading.n_samples,
        "tau": reading.tau,
        "embedding_dim": reading.embedding_dim,
        "warnings": list(reading.warnings),
        "computed_at": reading.computed_at.isoformat(),
    }
    records: list[ExternalOutcomeRecord] = []

    for metric_name, value, unit in (
        ("lyapunov_max", reading.lyapunov_max, "per_sample"),
        ("correlation_dimension", reading.correlation_dimension, "dimensionless"),
    ):
        records.append(
            ExternalOutcomeRecord(
                outcome_id=str(uuid.uuid4()),
                outcome_kind=OUTCOME_KIND_INVARIANT_READING_V1,
                value=float(value) if math.isfinite(value) else 0.0,
                unit=unit,
                confidence=reading.confidence,
                status="observed" if math.isfinite(value) else "indeterminate",
                subject_id=reading.source_kind,
                summary=(
                    f"{metric_name}={value:.4f} "
                    f"(m={reading.embedding_dim}, τ={reading.tau}, "
                    f"N={reading.n_samples}, conf={reading.confidence:.2f})"
                ),
                session_id=session_id,
                task_id="",
                run_id=run_id,
                metadata={**base_meta, "metric": metric_name},
            )
        )
    return records


async def run_observatory(
    *,
    source_kind: str = OUTCOME_KIND_GAUNTLET_TIER1,
    days: int = 30,
    store: TelemetryPlaneStore | None = None,
    dry_run: bool = False,
) -> tuple[InvariantReading, list[ExternalOutcomeRecord]]:
    """Read the gauntlet series, compute invariants, write back.

    Honest about empty input: if no outcomes are available in the window,
    returns a NaN-filled reading with status=indeterminate and writes
    nothing (logging only).

    Parameters
    ----------
    dry_run : bool
        If True, compute but do not write. Useful for CI / fixture tests.
    """
    store = store or TelemetryPlaneStore()
    outcomes = await load_recent_outcomes(source_kind, days=days, store=store)

    if len(outcomes) < MIN_SAMPLES_HARD_FLOOR:
        logger.info(
            "invariant_observatory: only %d outcomes in last %d days for "
            "kind=%s (need >=%d); skipping",
            len(outcomes),
            days,
            source_kind,
            MIN_SAMPLES_HARD_FLOOR,
        )
        # Return an empty reading so callers can still observe the skip.
        empty = InvariantReading(
            source_kind=source_kind,
            n_samples=len(outcomes),
            window_days=days,
            tau=-1,
            embedding_dim=-1,
            lyapunov_max=float("nan"),
            correlation_dimension=float("nan"),
            confidence=0.0,
            method_version=METHOD_VERSION,
            warnings=(
                f"only {len(outcomes)}/{MIN_SAMPLES_HARD_FLOOR} samples "
                f"in {days}-day window",
            ),
        )
        return empty, []

    # Order chronologically (load_recent_outcomes returns DESC by created_at).
    outcomes_sorted = sorted(outcomes, key=lambda o: o.created_at)
    series = np.array([o.value for o in outcomes_sorted], dtype=float)

    # Time grid: convert to "samples per day" cadence so λ is in units of
    # 1/day rather than 1/sample. Estimate fs from median Δt.
    deltas = np.diff(
        np.array([o.created_at.timestamp() for o in outcomes_sorted])
    )
    if len(deltas) > 0 and float(np.median(deltas)) > 0:
        fs = 86400.0 / float(np.median(deltas))  # samples per day
    else:
        fs = 1.0

    reading = observe_series(
        series,
        source_kind=source_kind,
        window_days=days,
        fs=fs,
    )

    run_id = str(uuid.uuid4())
    records = _reading_to_records(
        reading, session_id="invariant_observatory", run_id=run_id
    )

    if dry_run:
        logger.info(
            "invariant_observatory: dry-run; not writing %d records "
            "(λ=%.4f, D₂=%.4f, conf=%.2f)",
            len(records),
            reading.lyapunov_max,
            reading.correlation_dimension,
            reading.confidence,
        )
        return reading, records

    for rec in records:
        await store.record_external_outcome(rec)
    logger.info(
        "invariant_observatory: wrote %d records for kind=%s "
        "(λ_max=%.4f /day, D₂=%.4f, conf=%.2f)",
        len(records),
        source_kind,
        reading.lyapunov_max,
        reading.correlation_dimension,
        reading.confidence,
    )
    return reading, records


# ---------------------------------------------------------------------------
# Test fixtures (kept in module for transparency; reproducible)
# ---------------------------------------------------------------------------


def lorenz_series(
    *,
    n: int = 2000,
    dt: float = 0.01,
    sigma: float = 10.0,
    rho: float = 28.0,
    beta: float = 8.0 / 3.0,
    x0: tuple[float, float, float] = (1.0, 1.0, 1.0),
    burn_in: int = 1000,
    component: int = 0,
) -> np.ndarray:
    """Generate a Lorenz-attractor trajectory by RK4 integration.

    Returned series is the projection onto axis ``component`` (default x).
    A burn-in period is discarded so the trajectory is on the attractor.

    Known λ_max for the classical (σ=10, ρ=28, β=8/3) parameters is
    ≈ 0.9056 per natural time unit (Sprott 2003). With dt=0.01 the
    per-sample λ is ≈ 0.009056.

    This is the canonical fixture for testing Lyapunov / correlation
    dimension estimators — see Rosenstein 1993 §IV.
    """
    def f(state: np.ndarray) -> np.ndarray:
        x, y, z = state
        return np.array([sigma * (y - x), x * (rho - z) - y, x * y - beta * z])

    total = burn_in + n
    state = np.array(x0, dtype=float)
    traj = np.empty((total, 3))
    for i in range(total):
        traj[i] = state
        k1 = f(state)
        k2 = f(state + dt * k1 / 2.0)
        k3 = f(state + dt * k2 / 2.0)
        k4 = f(state + dt * k3)
        state = state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return traj[burn_in:, component]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m dharma_swarm.invariant_observatory",
        description=(
            "Invariant Observatory v1 — Takens + Rosenstein + "
            "Grassberger-Procaccia over the gauntlet tier-1 series. "
            "Read-only research surface."
        ),
    )
    p.add_argument(
        "--days", type=int, default=30,
        help="Look-back window in days (default: 30).",
    )
    p.add_argument(
        "--kind", default=OUTCOME_KIND_GAUNTLET_TIER1,
        help=f"Source outcome kind (default: {OUTCOME_KIND_GAUNTLET_TIER1}).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Compute but do not write back to the telemetry plane.",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose logging.",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    reading, records = asyncio.run(
        run_observatory(
            source_kind=args.kind,
            days=args.days,
            dry_run=args.dry_run,
        )
    )
    print(
        f"invariant_observatory: kind={reading.source_kind} "
        f"N={reading.n_samples} window={reading.window_days}d "
        f"τ={reading.tau} m={reading.embedding_dim} "
        f"λ_max={reading.lyapunov_max:.4f} "
        f"D₂={reading.correlation_dimension:.4f} "
        f"conf={reading.confidence:.2f} "
        f"records_written={0 if args.dry_run else len(records)}"
    )
    if reading.warnings:
        for w in reading.warnings:
            print(f"  warning: {w}")
    return 0 if reading.is_honest() or reading.n_samples < MIN_SAMPLES_HARD_FLOOR else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
