#!/usr/bin/env python3
"""Integrity check for docs/governance/AGENT_ONLINE.{md,yaml}.

This checker keeps the one-node onboarding contract load-bearing by ensuring:
1) AGENT_ONLINE.yaml has the required keys
2) all referenced paths exist in the repo
3) AGENT_ONLINE.md contains the declared paths and commands
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_TOP_KEYS = {
    "version",
    "updated_at",
    "canonical_markdown",
    "precedence",
    "mandatory_read_order",
    "coverage_map",
    "hard_fail_surfaces",
    "required_commands",
    "minimum_commands",
    "exemption_surfaces",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json_yaml(path: Path) -> dict[str, Any]:
    """Load .yaml content as JSON-compatible YAML.

    The AGENT_ONLINE machine surface is intentionally kept JSON-compatible
    to avoid extra parser dependencies in CI.
    """
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path} must remain JSON-compatible YAML for dependency-free CI parsing."
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must parse to a top-level object.")
    return payload


def _collect_paths(payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    paths.extend(str(p) for p in payload.get("precedence", []))
    paths.append(str(payload.get("canonical_markdown", "")))
    for row in payload.get("mandatory_read_order", []):
        if isinstance(row, dict):
            paths.append(str(row.get("path", "")))
    coverage = payload.get("coverage_map", {})
    if isinstance(coverage, dict):
        paths.extend(str(v) for v in coverage.values())
    for key in ("hard_fail_surfaces", "exemption_surfaces"):
        paths.extend(str(p) for p in payload.get(key, []))
    return [p for p in paths if p and "*" not in p]


def main() -> int:
    root = _repo_root()
    md_path = root / "docs/governance/AGENT_ONLINE.md"
    yaml_path = root / "docs/governance/AGENT_ONLINE.yaml"

    errors: list[str] = []

    if not md_path.exists():
        errors.append("missing docs/governance/AGENT_ONLINE.md")
    if not yaml_path.exists():
        errors.append("missing docs/governance/AGENT_ONLINE.yaml")
    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        return 1

    try:
        payload = _read_json_yaml(yaml_path)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    missing_keys = sorted(REQUIRED_TOP_KEYS.difference(payload.keys()))
    if missing_keys:
        for key in missing_keys:
            print(f"ERROR: missing key in AGENT_ONLINE.yaml: {key}")
        return 1

    missing_paths = []
    for rel in _collect_paths(payload):
        if not (root / rel).exists():
            missing_paths.append(rel)
    if missing_paths:
        for rel in missing_paths:
            print(f"ERROR: referenced path does not exist: {rel}")
        return 1

    md_text = md_path.read_text(encoding="utf-8")

    for row in payload.get("mandatory_read_order", []):
        if isinstance(row, dict):
            rel = str(row.get("path", ""))
            if rel and rel not in md_text:
                errors.append(f"AGENT_ONLINE.md missing mandatory path reference: {rel}")

    for command in payload.get("required_commands", []):
        cmd = str(command)
        if cmd and cmd not in md_text:
            errors.append(f"AGENT_ONLINE.md missing required command: {cmd}")

    for command in payload.get("minimum_commands", []):
        cmd = str(command)
        if cmd and cmd not in md_text:
            errors.append(f"AGENT_ONLINE.md missing minimum command: {cmd}")

    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        return 1

    print("AGENT_ONLINE integrity check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
