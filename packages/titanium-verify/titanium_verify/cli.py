"""Command-line entry point for titanium-verify.

Usage:
    python -m titanium_verify.cli verify --package telos_kernel --property purity
    python -m titanium_verify.cli verify --package-path /path/to/pkg --dotted foo
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path

from titanium_verify.report import Report, Verdict
from titanium_verify.verifier import verify_package


def _resolve_package_path(dotted: str) -> Path:
    """Locate the on-disk directory backing a dotted package name."""
    spec = importlib.util.find_spec(dotted)
    if spec is None or spec.submodule_search_locations is None:
        raise FileNotFoundError(f"cannot locate package: {dotted}")
    # Handle _NamespacePath by taking the first entry.
    locations = list(spec.submodule_search_locations)
    if not locations:
        raise FileNotFoundError(f"package {dotted} has no on-disk root")
    return Path(locations[0])


def _report_to_dict(r: Report) -> dict:
    return {
        "package": r.package,
        "property": r.property_name,
        "verdict": r.verdict.value,
        "functions_checked": r.functions_checked,
        "functions_verified": r.functions_verified,
        "counterexamples": [
            {
                "function": c.function_qualname,
                "property": c.property_name,
                "witness": c.witness,
                "detail": c.detail,
            }
            for c in r.counterexamples
        ],
        "per_function": [
            {
                "qualname": f.qualname,
                "verdict": f.verdict.value,
                "detail": f.detail,
                "solver_time_ms": round(f.solver_time_ms, 3),
            }
            for f in r.per_function
        ],
        "total_time_ms": round(r.total_time_ms, 3),
        "tool_version": r.tool_version,
    }


def _print_summary(r: Report) -> None:
    print(f"titanium-verify {r.tool_version}")
    print(f"package: {r.package}")
    print(f"property: {r.property_name}")
    print(f"result: {r.verdict.value}")
    print(f"functions_checked: {r.functions_checked}")
    print(f"functions_verified: {r.functions_verified}")
    print(f"counterexamples: {len(r.counterexamples)}")
    print(f"time: {r.total_time_ms:.1f}ms")
    if r.counterexamples:
        print("\ncounterexamples:")
        for c in r.counterexamples:
            print(f"  - {c.function_qualname}: {c.detail}")
    rejected = [f for f in r.per_function if f.verdict == Verdict.REJECTED]
    if rejected:
        print("\nrejected (frontend could not analyze):")
        for f in rejected:
            print(f"  - {f.qualname}: {f.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="titanium-verify")
    sub = parser.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="Verify a package.")
    v.add_argument("--package", dest="package", help="Dotted package name to verify.")
    v.add_argument("--package-path", dest="package_path", help="Direct path to package root.")
    v.add_argument("--dotted", dest="dotted_prefix", help="Dotted prefix (required with --package-path).")
    v.add_argument("--property", default="purity", help="Property to check (default: purity)")
    v.add_argument("--json", action="store_true", help="Emit machine-readable JSON report to stdout.")

    args = parser.parse_args(argv)

    if args.cmd == "verify":
        if args.package:
            pkg_root = _resolve_package_path(args.package)
            dotted = args.package
        elif args.package_path and args.dotted_prefix:
            pkg_root = Path(args.package_path).resolve()
            dotted = args.dotted_prefix
        else:
            parser.error("either --package or (--package-path and --dotted) is required")
        report = verify_package(pkg_root, dotted, property_name=args.property)
        if args.json:
            print(json.dumps(_report_to_dict(report), indent=2))
        else:
            _print_summary(report)
        # Exit codes: 0 verified, 1 refuted, 2 unknown/rejected.
        if report.verdict == Verdict.VERIFIED:
            return 0
        if report.verdict == Verdict.REFUTED:
            return 1
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
