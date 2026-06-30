"""Information-theoretic and linear-algebra primitives for the formal gates.

Kept separate from :mod:`dharma_swarm.telos_formal` so each module stays small
and the math is independently testable.  No domain logic here -- just entropy,
density-operator validation, and effective rank.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

__all__ = [
    "EPS",
    "effective_rank",
    "shannon_entropy",
    "von_neumann_entropy",
]

# Numerical tolerance for floating-point identity (PSD/trace/Hermitian checks).
EPS = 1e-9


def shannon_entropy(distribution: Sequence[float], base: float = 2.0) -> float:
    """Shannon entropy ``H = -sum p_i log_base p_i`` of a probability vector.

    The input is normalized to sum to 1 first.  Zero-probability events
    contribute zero (``0 log 0 := 0``).  Raises ``ValueError`` on negative
    mass or an all-zero vector.
    """
    arr = np.asarray(distribution, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError("distribution must be one-dimensional")
    if np.any(arr < -EPS):
        raise ValueError("distribution has negative mass")
    arr = np.clip(arr, 0.0, None)
    total = float(arr.sum())
    if total <= EPS:
        raise ValueError("distribution has zero total mass")
    p = arr / total
    nonzero = p[p > EPS]
    return float(-np.sum(nonzero * (np.log(nonzero) / math.log(base))))


def von_neumann_entropy(rho: np.ndarray, base: float = 2.0) -> float:
    """Von Neumann entropy ``S(rho) = -tr(rho log rho)`` of a density operator.

    ``rho`` must be Hermitian, positive-semidefinite, and unit-trace.  The
    entropy is computed from the eigenvalues, so a *pure* state (one eigenvalue
    = 1, rest = 0) yields exactly ``0`` -- which is what the humility gate
    forbids.  A maximally mixed state on ``n`` levels yields ``log_base n``.
    """
    eigenvalues = validate_density_matrix(rho)
    return shannon_entropy(eigenvalues, base=base)


def validate_density_matrix(rho: np.ndarray) -> np.ndarray:
    """Validate ``rho`` is a density operator; return its real eigenvalues."""
    mat = np.asarray(rho, dtype=np.complex128)
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError("density matrix must be square")
    if not np.allclose(mat, mat.conj().T, atol=1e-7):
        raise ValueError("density matrix must be Hermitian")
    trace = complex(np.trace(mat))
    if abs(trace - 1.0) > 1e-6:
        raise ValueError(f"density matrix must have unit trace (got {trace:.6g})")
    eigenvalues = np.linalg.eigvalsh(mat)
    if np.any(eigenvalues < -1e-7):
        raise ValueError("density matrix must be positive-semidefinite")
    return np.clip(eigenvalues.real, 0.0, None)


def effective_rank(gram: np.ndarray) -> float:
    """Effective rank of a Gram/correlation matrix (Roy & Vetterli, 2007).

    ``erank = exp(H(normalized eigenvalues))`` in nats.  A set of perfectly
    collinear vectors has effective rank ~1 (one direction); a set of mutually
    orthogonal vectors of equal norm has effective rank = n.  This is the
    measure that makes "many-sidedness" ungameable: pasting the same opinion
    under three labels keeps the effective rank at 1.
    """
    mat = np.asarray(gram, dtype=np.float64)
    eigenvalues = np.linalg.eigvalsh(mat)
    eigenvalues = np.clip(eigenvalues.real, 0.0, None)
    total = float(eigenvalues.sum())
    if total <= EPS:
        return 0.0
    p = eigenvalues / total
    nonzero = p[p > EPS]
    entropy_nats = float(-np.sum(nonzero * np.log(nonzero)))
    return float(math.exp(entropy_nats))
