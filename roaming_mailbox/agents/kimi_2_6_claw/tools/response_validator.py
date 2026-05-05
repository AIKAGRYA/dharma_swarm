#!/usr/bin/env python3
"""
Standalone Mailbox Response Schema Validator
Agent: kimi_2_6_claw
Scope: roaming_mailbox/agents/kimi_2_6_claw/tools/ only

Validates JSON response files in the Dharma Swarm roaming mailbox format.
Provides --self-test against kimi_2_6_claw's own response artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Schema Definition ───────────────────────────────────────────────────────

REQUIRED_RESPONSE_KEYS = [
    "task_id",
    "responder",
    "summary",
    "body",
    "status",
    "created_at",
]

VALID_STATUSES = {"responded", "claimed", "queued", "failed"}


@dataclass(frozen=True)
class ValidationError:
    file: str
    path: str
    message: str


@dataclass
class ValidationResult:
    file: str
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)


# ── Validator Core ──────────────────────────────────────────────────────────

class ResponseValidator:
    """Validates a single mailbox response JSON file."""

    def __init__(self, *, strict: bool = False) -> None:
        self.strict = strict

    def validate_file(self, path: Path) -> ValidationResult:
        errors: list[ValidationError] = []
        file_id = path.name

        # 1. File must exist and be readable JSON
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as e:
            errors.append(ValidationError(file_id, "", f"Invalid JSON: {e}"))
            return ValidationResult(file_id, False, errors)
        except FileNotFoundError:
            errors.append(ValidationError(file_id, "", "File not found"))
            return ValidationResult(file_id, False, errors)

        # 2. Must be a dict
        if not isinstance(data, dict):
            errors.append(ValidationError(file_id, "", f"Top-level must be object, got {type(data).__name__}"))
            return ValidationResult(file_id, False, errors)

        # 3. Required keys
        for key in REQUIRED_RESPONSE_KEYS:
            if key not in data:
                errors.append(ValidationError(file_id, f".{key}", f"Missing required key: '{key}'"))

        # 4. Type checks for string fields
        string_fields = ["task_id", "responder", "summary", "body", "status", "created_at"]
        for key in string_fields:
            if key in data and not isinstance(data[key], str):
                errors.append(ValidationError(file_id, f".{key}", f"Must be string, got {type(data[key]).__name__}"))

        # 5. Status enum
        if "status" in data:
            if data["status"] not in VALID_STATUSES:
                errors.append(
                    ValidationError(
                        file_id,
                        ".status",
                        f"Invalid status '{data['status']}', expected one of: {VALID_STATUSES}",
                    )
                )

        # 6. Metadata must be dict if present
        if "metadata" in data and not isinstance(data["metadata"], dict):
            errors.append(ValidationError(file_id, ".metadata", "Must be object"))

        # 7. Strict: validate ISO-8601-ish created_at
        if self.strict and "created_at" in data and isinstance(data["created_at"], str):
            try:
                datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            except ValueError:
                errors.append(ValidationError(file_id, ".created_at", "Invalid ISO-8601 timestamp"))

        valid = len(errors) == 0
        return ValidationResult(file_id, valid, errors)


# ── Batch Runner ────────────────────────────────────────────────────────────

class BatchValidator:
    """Validates all response files in a directory."""

    def __init__(self, validator: ResponseValidator) -> None:
        self.validator = validator

    def run(self, responses_dir: Path) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        if not responses_dir.exists():
            return results

        for path in sorted(responses_dir.glob("*.json")):
            results.append(self.validator.validate_file(path))

        return results


# ── Self-Test: Validate Kimi 2.6 Claw's Own Artifacts ────────────────────────

def self_test() -> int:
    """Validate all response files produced by kimi_2_6_claw."""

    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    # Walk up from: roaming_mailbox/agents/kimi_2_6_claw/tools/validator.py
    # → roaming_mailbox/agents/kimi_2_6_claw/
    # → roaming_mailbox/agents/
    # → roaming_mailbox/
    # → repo_root

    agent_dir = Path(__file__).resolve().parent.parent
    responses_dir = agent_dir.parent.parent / "responses"

    print(f"🔍 Self-test: validating responses in {responses_dir}")
    print(f"   Agent directory: {agent_dir}")

    if not responses_dir.exists():
        print("❌ No responses directory found — nothing to validate.")
        return 1

    validator = ResponseValidator(strict=True)
    batch = BatchValidator(validator)
    results = batch.run(responses_dir)

    if not results:
        print("⚠️  No .json response files found.")
        return 1

    passed = 0
    failed = 0

    for r in results:
        if r.valid:
            print(f"  ✅ {r.file}")
            passed += 1
        else:
            print(f"  ❌ {r.file}")
            for e in r.errors:
                print(f"      → {e.path}: {e.message}")
            failed += 1

    print(f"\n{'─' * 50}")
    print(f"Results: {passed} passed, {failed} failed, {len(results)} total")

    if failed == 0:
        print("🖤 All kimi_2_6_claw responses are schema-valid.")
        return 0
    else:
        print("⚠️  Some responses failed validation — review needed.")
        return 1


# ── CLI ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Dharma Swarm roaming mailbox response JSON files."
    )
    parser.add_argument("--self-test", action="store_true", help="Validate kimi_2_6_claw's own response artifacts")
    parser.add_argument("--file", type=Path, help="Validate a single response file")
    parser.add_argument("--dir", type=Path, help="Validate all .json files in a directory")
    parser.add_argument("--strict", action="store_true", help="Enable strict mode (ISO-8601 timestamp validation)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    validator = ResponseValidator(strict=args.strict)
    results: list[ValidationResult] = []

    if args.file:
        results.append(validator.validate_file(args.file))
    elif args.dir:
        batch = BatchValidator(validator)
        results = batch.run(args.dir)
    else:
        parser.print_help()
        return 2

    # Output
    if args.json:
        out = [
            {
                "file": r.file,
                "valid": r.valid,
                "errors": [{"path": e.path, "message": e.message} for e in r.errors],
            }
            for r in results
        ]
        print(json.dumps(out, indent=2))
    else:
        for r in results:
            status = "✅" if r.valid else "❌"
            print(f"{status} {r.file}")
            for e in r.errors:
                print(f"   → {e.path}: {e.message}")

    return 0 if all(r.valid for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
