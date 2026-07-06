#!/usr/bin/env python3
"""Fail-closed verdict helper. Codifies invariant AI-N1.

AI-N1: a green verdict requires evidence. A check that reports success while
having measured nothing is a hard failure, not a pass. Absence of input must
never read as green -- a sensor with no reading must alarm, not report "all
clear".

This module is stdlib-only so any governance gate can import it early in CI.
Gates call :func:`emit_verdict` with the outcome they computed and the count
of items they actually measured; a green-with-zero-measurements verdict raises
:class:`NakedGreenError`, which callers convert into a non-zero exit.
"""

from __future__ import annotations


class NakedGreenError(RuntimeError):
    """Raised when a gate reports green having measured nothing (AI-N1)."""


def emit_verdict(*, gate: str, green: bool, items_measured: int) -> None:
    """Enforce AI-N1 for a gate's computed verdict.

    Parameters
    ----------
    gate:
        Human-readable gate name, used in the error message.
    green:
        Whether the gate computed a passing result.
    items_measured:
        Count of inputs the gate actually inspected to reach ``green``.

    Raises
    ------
    NakedGreenError
        If ``green`` is true while ``items_measured`` is zero or negative.
        A non-green verdict with zero measurements is allowed (a gate that
        found nothing to check and is failing closed is behaving correctly).
    """

    if green and items_measured <= 0:
        raise NakedGreenError(
            f"{gate}: green verdict with {items_measured} items measured -- "
            "absence is never green (AI-N1)"
        )
