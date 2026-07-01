#!/usr/bin/env python3
"""Wire ratcheted loop gates into the blocking CI workflow.

Adds one fail-closed GitHub Actions step per ratcheted finding and validates the
workflow YAML after writing. The workflow starts with the cheap-tier anchors
from spec §9.2 plus the Phase-0 F1/F2/F3 gates.

Exit codes:
    0   workflow valid and gate present
    2   malformed YAML, invalid workflow structure, or write failure
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

DEFAULT_WORKFLOW = Path(".github/workflows/loop-ratchet-gates.yml")
JOB_ID = "loop-ratchet-gates"


class WorkflowError(RuntimeError):
    """Raised when the CI workflow is malformed or cannot be updated."""


class _WorkflowDumper(yaml.SafeDumper):
    pass


def _str_presenter(dumper: yaml.SafeDumper, data: str):
    if data == "on":
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_WorkflowDumper.add_representer(str, _str_presenter)


def _base_workflow() -> dict:
    return {
        "name": "loop-ratchet-gates",
        "on": {
            "push": {"branches": ["main", "ratchet/**", "governance/**"]},
            "pull_request": {
                "branches": ["main", "promote/**", "governance/**", "ratchet/**"]
            },
            "merge_group": None,
        },
        "concurrency": {
            "group": "loop-ratchet-gates-${{ github.ref }}",
            "cancel-in-progress": True,
        },
        "permissions": {"contents": "read", "pull-requests": "read"},
        "jobs": {
            JOB_ID: {
                "name": "Cybernetic loop ratchet gates",
                "runs-on": "ubuntu-latest",
                "timeout-minutes": 20,
                "steps": [
                    {
                        "name": "Checkout (full history)",
                        "uses": "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5",
                        "with": {"fetch-depth": 0},
                    },
                    {
                        "name": "Set up Python",
                        "uses": "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
                        "with": {"python-version": "3.11"},
                    },
                    {
                        "name": "Set up Go",
                        "uses": "actions/setup-go@40f1582b2485089dde7abd97c1529aa768e1baff",
                        "with": {"go-version": "1.26"},
                    },
                    {"name": "Install dev package", "run": 'python -m pip install -e ".[dev]"'},
                    {
                        "name": "Install gitleaks CLI",
                        "run": (
                            'mkdir -p "$HOME/.local/bin"\n'
                            'GOBIN="$HOME/.local/bin" go install '
                            "github.com/zricethezav/gitleaks/v8@v8.30.1\n"
                            'echo "$HOME/.local/bin" >> "$GITHUB_PATH"\n'
                        ),
                    },
                    {
                        "name": "Select comparison refs",
                        "id": "refs",
                        "run": (
                            "set -euo pipefail\n"
                            'if [ "${{ github.event_name }}" = "merge_group" ]; then\n'
                            '  echo "base=${{ github.event.merge_group.base_sha }}" >> "$GITHUB_OUTPUT"\n'
                            '  echo "head=${{ github.event.merge_group.head_sha }}" >> "$GITHUB_OUTPUT"\n'
                            'elif [ "${{ github.event_name }}" = "pull_request" ]; then\n'
                            '  echo "base=${{ github.event.pull_request.base.sha }}" >> "$GITHUB_OUTPUT"\n'
                            '  echo "head=${{ github.event.pull_request.head.sha }}" >> "$GITHUB_OUTPUT"\n'
                            "else\n"
                            '  echo "base=${{ github.event.before }}" >> "$GITHUB_OUTPUT"\n'
                            '  echo "head=${{ github.sha }}" >> "$GITHUB_OUTPUT"\n'
                            "fi\n"
                        ),
                    },
                    {
                        "name": "Pytest collection (strict markers)",
                        "run": "PYTHONPATH=. python -m pytest --collect-only -q --strict-markers",
                    },
                    {
                        "name": "Hygiene integrity",
                        "run": "PYTHONPATH=. python scripts/governance/hygiene/check_hygiene_integrity.py",
                    },
                    {
                        "name": "Test hygiene",
                        "run": "PYTHONPATH=. python scripts/governance/check_test_hygiene.py",
                    },
                    {
                        "name": "Module budget",
                        "run": (
                            "PYTHONPATH=. python scripts/governance/check_module_budget.py \\\n"
                            '  --base-ref "${{ steps.refs.outputs.base }}" \\\n'
                            '  --head-ref "${{ steps.refs.outputs.head }}"\n'
                        ),
                    },
                    {
                        "name": "Repo xray",
                        "run": "PYTHONPATH=. python scripts/repo_xray.py --format json --write /tmp/repo_xray.json",
                    },
                    {"name": "Governance bundle", "run": "make governance-all"},
                    {
                        "name": "Phase-0 F1 marker strictness ratchet",
                        "id": "phase0_f1_marker_strictness",
                        "run": "PYTHONPATH=. python -m pytest --collect-only -q --strict-markers",
                    },
                    {
                        "name": "Phase-0 F2 property collection ratchet",
                        "id": "phase0_f2_property_collection",
                        "run": "PYTHONPATH=. python scripts/governance/hygiene/ratchet.py --json",
                    },
                    {
                        "name": "Phase-0 F3 importorskip allowlist ratchet",
                        "id": "phase0_f3_importorskip_allowlist",
                        "run": "PYTHONPATH=. python scripts/governance/check_test_hygiene.py",
                    },
                ],
            }
        },
    }


def gate_step_id(gate_id: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]+", "_", gate_id.lower()).strip("_")
    return f"ratchet_{value or 'gate'}"


def load_workflow(path: Path) -> dict:
    if not path.exists():
        return _base_workflow()
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise WorkflowError(f"YAML parse failed for {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkflowError(f"workflow {path} must be a mapping")
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    validate_workflow(data)
    return data


def validate_workflow(workflow: dict) -> None:
    if not isinstance(workflow.get("on"), dict):
        raise WorkflowError("workflow must define an 'on' trigger mapping")
    for trigger in ("push", "pull_request", "merge_group"):
        if trigger not in workflow["on"]:
            raise WorkflowError(f"workflow missing trigger: {trigger}")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or JOB_ID not in jobs:
        raise WorkflowError(f"workflow missing jobs.{JOB_ID}")
    job = jobs[JOB_ID]
    if not isinstance(job, dict):
        raise WorkflowError(f"workflow jobs.{JOB_ID} must be a mapping")
    if not job.get("runs-on"):
        raise WorkflowError(f"workflow jobs.{JOB_ID} missing runs-on")
    steps = job.get("steps")
    if not isinstance(steps, list):
        raise WorkflowError(f"workflow jobs.{JOB_ID}.steps must be a list")
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            raise WorkflowError(f"workflow jobs.{JOB_ID}.steps[{idx}] must be a mapping")
        if "run" not in step and "uses" not in step:
            raise WorkflowError(
                f"workflow jobs.{JOB_ID}.steps[{idx}] must define run or uses"
            )


def add_gate_step(workflow: dict, gate_id: str, name: str, command: str) -> bool:
    validate_workflow(workflow)
    steps = workflow["jobs"][JOB_ID]["steps"]
    step_id = gate_step_id(gate_id)
    for step in steps:
        if step.get("id") == step_id:
            step["name"] = f"Ratcheted gate: {name}"
            step["run"] = command
            return False
    steps.append({
        "name": f"Ratcheted gate: {name}",
        "id": step_id,
        "run": command,
    })
    return True


def write_workflow(path: Path, workflow: dict) -> None:
    validate_workflow(workflow)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(workflow, Dumper=_WorkflowDumper, sort_keys=False))
    validate_workflow(load_workflow(path))


def wire_gate(path: Path, gate_id: str, name: str, command: str) -> bool:
    workflow = load_workflow(path)
    added = add_gate_step(workflow, gate_id, name, command)
    write_workflow(path, workflow)
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Add a ratcheted gate step to loop-ratchet-gates.yml and validate YAML.",
    )
    parser.add_argument("--workflow", default=str(DEFAULT_WORKFLOW), help="workflow YAML path")
    parser.add_argument("--gate-id", required=True, help="stable finding/gate id")
    parser.add_argument("--name", required=True, help="human-readable gate name")
    parser.add_argument("--run", required=True, help="fail-closed command for the gate step")
    args = parser.parse_args(argv)

    try:
        added = wire_gate(Path(args.workflow), args.gate_id, args.name, args.run)
    except WorkflowError as exc:
        sys.stderr.write(f"wire-ci-gate YAML error: {exc}\n")
        return 2
    sys.stdout.write(
        f"wire-ci-gate {'added' if added else 'updated'} {gate_step_id(args.gate_id)} in {args.workflow}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
