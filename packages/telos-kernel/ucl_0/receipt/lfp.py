"""Knaster-Tarski least fixed point admission for UCL-0 P0.

The admission operator is monotone over receipt-id sets, so iteration reaches
the least fixed point for a finite candidate store. This is the concrete P0
form of [Tarski 1955](https://projecteuclid.org/journals/pacific-journal-of-mathematics/volume-5/issue-2/A-lattice-theoretical-fixpoint-theorem-and-its-applications/pjm/1103044538.full).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ucl_0.receipt.identity import receipt_id
from ucl_0.receipt.types import Receipt, is_well_formed


def phi_step(candidates: Sequence[Receipt], admitted: Iterable[bytes]) -> set[bytes]:
    base_set = set(admitted)
    next_set = set(base_set)
    for receipt in candidates:
        candidate_id = receipt_id(receipt)
        if candidate_id in next_set:
            continue
        if is_well_formed(receipt) and all(item in base_set for item in receipt.predecessors):
            next_set.add(candidate_id)
    return next_set


def least_fixed_point(candidates: Sequence[Receipt], initial: Iterable[bytes] = ()) -> set[bytes]:
    current = set(initial)
    while True:
        next_set = phi_step(candidates, current)
        if next_set == current:
            return current
        current = next_set
