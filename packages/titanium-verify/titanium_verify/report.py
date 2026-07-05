"""Verifier report types.

`Verdict.VERIFIED` means we have a mathematical proof of the property.
`Verdict.REFUTED` means we have a concrete counterexample.
`Verdict.UNKNOWN` means the solver timed out or returned unknown.
`Verdict.REJECTED` means the frontend saw a construct outside our
supported dialect — the file is *not* certified, but neither is it a
counterexample. Callers must treat REJECTED as a failure to prove.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class CounterExample:
    """A concrete input demonstrating property violation."""
    function_qualname: str  # e.g. "telos_kernel.notary.LocalFileAnchor.anchor"
    property_name: str      # e.g. "purity"
    witness: dict[str, Any] # SMT model bindings
    trace: tuple[str, ...]  # human-readable call trace
    detail: str = ""


@dataclass(frozen=True)
class FunctionResult:
    qualname: str
    verdict: Verdict
    detail: str = ""
    counterexample: CounterExample | None = None
    solver_time_ms: float = 0.0


@dataclass(frozen=True)
class Report:
    """Machine-readable verifier report.

    Immutable so that CI systems and downstream tools can hash it as-is.
    """
    package: str
    property_name: str
    verdict: Verdict
    functions_checked: int
    functions_verified: int
    counterexamples: tuple[CounterExample, ...] = ()
    per_function: tuple[FunctionResult, ...] = ()
    total_time_ms: float = 0.0
    tool_version: str = "0.1.0"

    @property
    def is_success(self) -> bool:
        return self.verdict == Verdict.VERIFIED
