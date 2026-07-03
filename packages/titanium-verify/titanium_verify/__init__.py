"""titanium-verify — bespoke sound verifier for the telos-kernel TCB dialect.

Public surface:
    * `verify_package(pkg_path, property_name)` — top-level entry.
    * `Verdict` — verifier verdict enum.
    * `Report` — machine-readable verifier report.

See README.md for what we prove and the trust base.
"""
from __future__ import annotations

from titanium_verify.frontend import Function, Module, parse_package
from titanium_verify.effects import Effect, EffectSet, analyze_effects
from titanium_verify.report import CounterExample, Report, Verdict
from titanium_verify.verifier import verify_package

__all__ = [
    "Function",
    "Module",
    "parse_package",
    "Effect",
    "EffectSet",
    "analyze_effects",
    "CounterExample",
    "Report",
    "Verdict",
    "verify_package",
]

__version__ = "0.1.0"
