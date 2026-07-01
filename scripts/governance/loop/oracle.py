#!/usr/bin/env python3
"""Thin interface to deterministic oracles (spec R3, architecture §11).

The oracle is the only source of truth for gate verdicts in the loop (Core
Invariant: the LLM proposes, a deterministic oracle disposes). ``run_gate``
runs a real command and returns its exit code as the verdict — never an LLM
opinion. A non-zero exit is a fail; zero is a pass.

``Oracle`` is an abstract base class. ``CIOracle`` (default) runs real
pytest/governance commands directly and captures their exit codes. The
interface is structured so a ``ForgeOracle`` subclass (calling pudgala-forge's
``check_claim_evidence_binding.py``) could be added later without changing
callers — there is NO hard dependency on the unmerged pudgala-forge branch.

Usage:
    python3 scripts/governance/loop/oracle.py run "<command>" [--cwd <dir>]
    python3 scripts/governance/loop/oracle.py collect-only
    python3 scripts/governance/loop/oracle.py test-hygiene

Exit codes:
    The ``run`` subcommand exits with the gate's real exit code (0 = pass,
    non-zero = fail). ``--help`` exits 0.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_PYTHON = os.environ.get("LOOP_PYTHON", sys.executable)
DEFAULT_GATE_TIMEOUT = 300


def _default_repo_root() -> Path:
    # scripts/governance/loop/oracle.py -> repo root is 4 parents up.
    return Path(__file__).resolve().parents[3]


@dataclass
class GateResult:
    """The deterministic verdict of a single gate run.

    The exit code IS the verdict. ``passed`` and ``verdict`` are derived purely
    from ``exit_code`` — there is no opinion field that can override it.
    """

    exit_code: int
    stdout: str
    stderr: str
    command: str = ""
    cwd: str = ""

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    @property
    def verdict(self) -> str:
        return "pass" if self.exit_code == 0 else "fail"

    def to_dict(self) -> dict:
        """Serialise to a receipt dict (evidence-linked, replayable)."""
        d = asdict(self)
        d["passed"] = self.passed
        d["verdict"] = self.verdict
        return d


class GateTimeoutError(Exception):
    """Raised when a gate command exceeds the configured subprocess timeout.

    This prevents a hung gate (e.g. ``sleep`` or an infinite loop) from
    hanging the loop forever. The error message names the command and the
    timeout so the operator can diagnose the hang.
    """


class Oracle(ABC):
    """Abstract deterministic oracle.

    Subclasses implement ``run_gate`` to invoke a real, non-LLM gate and
    capture its exit code. The exit code is the verdict — never an LLM opinion.
    """

    @abstractmethod
    def run_gate(self, command: str, cwd: str | None = None) -> GateResult:
        """Run ``command`` and return a GateResult with the real exit code."""


class CIOracle(Oracle):
    """Default oracle: runs real pytest/governance commands and captures exit codes.

    Uses the active interpreter, or ``LOOP_PYTHON`` when set, for
    pytest/governance script invocations. Sets ``PYTHONPATH`` to the repo root
    so first-party imports resolve.
    """

    def __init__(
        self,
        python: str = DEFAULT_PYTHON,
        repo_root: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | float | None = DEFAULT_GATE_TIMEOUT,
    ) -> None:
        self.python = python
        self.repo_root = repo_root or _default_repo_root()
        self.env = env
        self.timeout = timeout

    def _build_env(self) -> dict[str, str]:
        full = os.environ.copy()
        full["PYTHONPATH"] = str(self.repo_root)
        if self.env:
            full.update(self.env)
        return full

    def run_gate(self, command: str, cwd: str | None = None, timeout: int | float | None = None) -> GateResult:
        work_cwd = cwd or str(self.repo_root)
        effective_timeout = timeout if timeout is not None else self.timeout
        args = shlex.split(command)
        try:
            proc = subprocess.run(
                args,
                shell=False,
                capture_output=True,
                text=True,
                cwd=work_cwd,
                env=self._build_env(),
                timeout=effective_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise GateTimeoutError(
                f"gate timed out after {effective_timeout}s: {command!r}"
            ) from exc
        return GateResult(
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            command=command,
            cwd=work_cwd,
        )

    # --- convenience gate builders (real governance commands) ---

    def collect_only(self) -> GateResult:
        """pytest --collect-only with strict markers (the collection gate)."""
        return self.run_gate(
            f'"{self.python}" -m pytest --collect-only -q --strict-markers'
        )

    def test_hygiene(self) -> GateResult:
        """check_test_hygiene.py governance gate."""
        return self.run_gate(
            f'"{self.python}" scripts/governance/check_test_hygiene.py'
        )

    def module_budget(
        self,
        base_ref: str | None = None,
        head_ref: str | None = None,
    ) -> GateResult:
        """check_module_budget.py governance gate (optionally scoped to a diff)."""
        cmd = f'"{self.python}" scripts/governance/check_module_budget.py'
        if base_ref:
            cmd += f" --base-ref {base_ref}"
        if head_ref:
            cmd += f" --head-ref {head_ref}"
        return self.run_gate(cmd)

    def governance_all(self) -> GateResult:
        """make governance-all — the full cheap-tier governance suite."""
        return self.run_gate("make governance-all")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _emit_error(message: str) -> int:
    sys.stderr.write(message + "\n")
    return 2


def _cmd_run(args) -> int:
    oracle = CIOracle()
    result = oracle.run_gate(args.command, cwd=args.cwd)
    payload = result.to_dict()
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return result.exit_code


def _cmd_collect_only(args) -> int:
    oracle = CIOracle()
    result = oracle.collect_only()
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.exit_code


def _cmd_test_hygiene(args) -> int:
    oracle = CIOracle()
    result = oracle.test_hygiene()
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic oracle interface: run a gate and return its exit code as the verdict.",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    p_run = sub.add_parser("run", help="run an arbitrary gate command and print its GateResult as JSON")
    p_run.add_argument("command", help="the shell command to run as the gate")
    p_run.add_argument("--cwd", default=None, help="working directory for the command")

    sub.add_parser("collect-only", help="run pytest --collect-only --strict-markers")

    sub.add_parser("test-hygiene", help="run check_test_hygiene.py")

    args = parser.parse_args(argv)

    if args.action == "run":
        return _cmd_run(args)
    if args.action == "collect-only":
        return _cmd_collect_only(args)
    if args.action == "test-hygiene":
        return _cmd_test_hygiene(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
