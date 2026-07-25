#!/usr/bin/env python3
"""Run the deterministic anti-vibe quality membrane gates."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class GateResult:
    name: str
    command: list[str]
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _run(name: str, command: list[str], *, cwd: Path) -> GateResult:
    print(f"==> {name}: {' '.join(command)}", flush=True)
    proc = subprocess.run(command, cwd=str(cwd), check=False)
    return GateResult(name=name, command=command, returncode=proc.returncode)


def run_quality_membrane(repo_root: Path) -> list[GateResult]:
    py = sys.executable
    commands: list[tuple[str, list[str]]] = [
        (
            "runtime_names",
            [
                py,
                "-m",
                "ruff",
                "check",
                "--select",
                "F821,F811",
                "dharma_swarm",
                "api",
                "scripts",
                "tests",
            ],
        ),
        (
            "module_coherence",
            [py, "scripts/governance/check_module_coherence.py", "--repo-root", "."],
        ),
        (
            "a2a_and_module_contract_tests",
            [
                py,
                "-m",
                "pytest",
                "tests/test_a2a_readiness_gate.py",
                "tests/test_a2a_task_lifecycle.py",
                "tests/test_module_coherence_gate.py",
                "-q",
                "--tb=line",
            ],
        ),
        (
            "docops_integrity",
            [py, "scripts/docops/check_docops_integrity.py"],
        ),
        (
            "hygiene_delta_ratchet",
            [
                py,
                "scripts/governance/hygiene/delta_ratchet.py",
                "--base-ref",
                # Honors GITHUB_BASE_REF set by CI; falls back to origin/main locally.
                # The script itself reads the env var if --base-ref is omitted; we
                # pass it explicitly for visibility in the printed command line.
                os.environ.get("GITHUB_BASE_REF", "origin/main"),
                "--head-ref",
                "HEAD",
            ],
        ),
    ]

    results: list[GateResult] = []
    for name, command in commands:
        result = _run(name, command, cwd=repo_root)
        results.append(result)
        if not result.ok:
            break
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--json", action="store_true", help="Print a JSON summary after running")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    results = run_quality_membrane(repo_root)
    payload = {
        "status": "pass" if all(result.ok for result in results) else "fail",
        "gates": [asdict(result) for result in results],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("quality_membrane_status=" + payload["status"])
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
