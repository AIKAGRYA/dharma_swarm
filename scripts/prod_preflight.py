#!/usr/bin/env python3
"""Run the release-candidate production preflight gate.

This is intentionally an orchestrator around existing gates, not a new source
of truth. The report records what ran, what failed, and enough output tail to
debug without hiding failures behind a green aggregate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


OUTPUT_TAIL_CHARS = 12_000


@dataclass(frozen=True)
class PreflightGate:
    name: str
    command: tuple[str, ...]
    required: bool = True

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": list(self.command),
            "required": self.required,
        }


@dataclass(frozen=True)
class GateResult:
    gate: PreflightGate
    returncode: int
    elapsed_seconds: float
    stdout_tail: str
    stderr_tail: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_json(self) -> dict[str, Any]:
        return {
            **self.gate.to_json(),
            "ok": self.ok,
            "returncode": self.returncode,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }


def build_gate_plan(*, quick: bool, include_security: bool) -> tuple[PreflightGate, ...]:
    gates: list[PreflightGate] = [
        PreflightGate("memory_kernel_readiness", ("make", "memory-kernel-readiness")),
        PreflightGate("operator_prod_smoke", ("make", "operator-prod-smoke")),
        PreflightGate("docops_integrity", ("make", "docops-integrity")),
        PreflightGate("test_hygiene", ("make", "test-hygiene")),
        PreflightGate("module_budget", ("make", "module-budget")),
        PreflightGate("diff_check", ("git", "diff", "--check")),
        PreflightGate(
            "focused_recursive_operator_tests",
            (
                "pytest",
                "-q",
                "tests/test_operator_prod_smoke.py",
                "tests/test_recursive_discovery.py",
                "tests/test_swarm_integrity_benchmark.py",
                "--tb=line",
            ),
        ),
    ]
    if not quick:
        gates.append(
            PreflightGate(
                "control_surface_tests",
                (
                    "pytest",
                    "-q",
                    "tests/test_control_surface.py",
                    "--tb=line",
                ),
            )
        )
    if include_security:
        gates.extend(
            [
                PreflightGate("semgrep_strict", ("make", "semgrep-strict")),
                PreflightGate("gitleaks", ("make", "gitleaks")),
            ]
        )
    return tuple(gates)


def run_gate(repo_root: Path, gate: PreflightGate) -> GateResult:
    started = time.monotonic()
    completed = subprocess.run(
        list(gate.command),
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - started
    return GateResult(
        gate=gate,
        returncode=completed.returncode,
        elapsed_seconds=elapsed,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
    )


def _tail(output: str) -> str:
    if len(output) <= OUTPUT_TAIL_CHARS:
        return output
    return output[-OUTPUT_TAIL_CHARS:]


def git_value(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def build_report(
    *,
    repo_root: Path,
    gates: tuple[PreflightGate, ...],
    results: tuple[GateResult, ...],
    quick: bool,
    include_security: bool,
) -> dict[str, Any]:
    failed_required = [
        result.gate.name for result in results if result.gate.required and not result.ok
    ]
    return {
        "schema_version": "dharma_prod_preflight.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "repo_root": str(repo_root),
        "ok": not failed_required,
        "failed_required_gates": failed_required,
        "mode": {
            "quick": quick,
            "include_security": include_security,
        },
        "git": {
            "branch": git_value(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
            "head": git_value(repo_root, "rev-parse", "HEAD"),
            "status_short": git_value(repo_root, "status", "--short"),
        },
        "planned_gates": [gate.to_json() for gate in gates],
        "results": [result.to_json() for result in results],
    }


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--report-json",
        type=Path,
        default=Path("reports/prod_preflight/latest.json"),
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip the slower control-surface pytest shard.",
    )
    parser.add_argument(
        "--include-security",
        action="store_true",
        help="Also run semgrep-strict and gitleaks.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    report_path = args.report_json
    if not report_path.is_absolute():
        report_path = repo_root / report_path

    gates = build_gate_plan(quick=args.quick, include_security=args.include_security)
    results = tuple(run_gate(repo_root, gate) for gate in gates)
    report = build_report(
        repo_root=repo_root,
        gates=gates,
        results=results,
        quick=args.quick,
        include_security=args.include_security,
    )
    write_report(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
