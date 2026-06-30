"""Information-theoretic and linear-algebra primitives for the formal gates.

Kept separate from :mod:`dharma_swarm.telos_formal` so each module stays small
and the math is independently testable.  No domain logic here -- just entropy,
density-operator validation, effective rank, and commutator norms.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

__all__ = [
    "EPS",
    "commutator_frobenius_norm",
    "effective_rank",
    "shannon_entropy",
    "validate_density_matrix",
    "von_neumann_entropy",
]

# Numerical tolerance for floating-point identity (PSD/trace/Hermitian checks).
EPS = 1e-9


def shannon_entropy(distribution: Sequence[float], base: float = 2.0) -> float:
    """Shannon entropy ``H = -sum p_i log_base p_i`` of a probability vector."""
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


def validate_density_matrix(rho: np.ndarray) -> np.ndarray:
    """Validate ``rho`` is a density operator; return its real eigenvalues."""
    mat = np.asarray(rho, dtype=np.complex128)
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError("density matrix must be square")
    hermitian = (mat + mat.conj().T) / 2.0
    if not np.allclose(mat, mat.conj().T, atol=1e-7):
        raise ValueError("density matrix must be Hermitian")
    trace = complex(np.trace(hermitian))
    if abs(trace - 1.0) > 1e-6:
        raise ValueError(f"density matrix must have unit trace (got {trace:.6g})")
    eigenvalues = np.linalg.eigvalsh(hermitian)
    if np.any(eigenvalues < -1e-7):
        raise ValueError("density matrix must be positive-semidefinite")
    return np.clip(eigenvalues.real, 0.0, None)


def von_neumann_entropy(rho: np.ndarray, base: float = 2.0) -> float:
    """Von Neumann entropy ``S(rho) = -tr(rho log rho)`` of a density operator."""
    eigenvalues = validate_density_matrix(rho)
    return shannon_entropy(eigenvalues, base=base)


def effective_rank(gram: np.ndarray) -> float:
    """Effective rank of a Gram/correlation matrix (Roy & Vetterli, 2007)."""
    mat = np.asarray(gram, dtype=np.float64)
    symmetric = (mat + mat.T) / 2.0
    eigenvalues = np.linalg.eigvalsh(symmetric)
    eigenvalues = np.clip(eigenvalues.real, 0.0, None)
    total = float(eigenvalues.sum())
    if total <= EPS:
        return 0.0
    p = eigenvalues / total
    nonzero = p[p > EPS]
    entropy_nats = float(-np.sum(nonzero * np.log(nonzero)))
    return float(math.exp(entropy_nats))


def commutator_frobenius_norm(left: np.ndarray, right: np.ndarray) -> float:
    """Return ``||[left, right]||_F`` for square matrices."""
    left_mat = np.asarray(left)
    right_mat = np.asarray(right)
    commutator = left_mat @ right_mat - right_mat @ left_mat
    return float(np.linalg.norm(commutator, ord="fro"))
