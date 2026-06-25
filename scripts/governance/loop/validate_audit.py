#!/usr/bin/env python3
"""Hard run-abort gate for audit output (spec §5).

Loads ``schemas/expert_audit_output.schema.json`` and validates an audit JSON
document against it with ``jsonschema`` (Draft 2020-12). A schema-invalid audit
is a hard abort: no partial artifacts are accepted by the loop.

Usage:
    python3 scripts/governance/loop/validate_audit.py <audit.json>

Exit codes:
    0   the audit JSON is schema-conformant
    2   the audit JSON is schema-invalid (or unreadable / missing) — a
        structured error listing is printed to stdout
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

SCHEMA_REL = Path("schemas") / "expert_audit_output.schema.json"


def _schema_path(repo_root: Path | None = None) -> Path:
    root = repo_root or _default_repo_root()
    return root / SCHEMA_REL


def _default_repo_root() -> Path:
    # scripts/governance/loop/validate_audit.py -> repo root is 4 parents up.
    return Path(__file__).resolve().parents[3]


def _load_schema(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _format_path(absolute_path) -> str:
    parts = [str(p) for p in absolute_path]
    return "/".join(parts) if parts else "<root>"


@dataclass
class ValidationResult:
    """Outcome of validating one audit document."""

    valid: bool
    errors: list[dict] = field(default_factory=list)

    def to_structured(self) -> dict:
        return {"valid": self.valid, "errors": self.errors}


def _structured_errors(exc: jsonschema.ValidationError) -> list[dict]:
    errs: list[dict] = []
    for err in exc.errors:
        errs.append(
            {
                "path": _format_path(err.absolute_path),
                "message": err.message,
                "validator": err.validator,
                "validator_value": err.validator_value,
            }
        )
    return errs


def validate_audit_doc(doc: object, repo_root: Path | None = None) -> ValidationResult:
    """Validate an in-memory audit document against the schema."""
    schema = _load_schema(_schema_path(repo_root))
    validator = jsonschema.Draft202012Validator(schema)
    collected = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    if not collected:
        return ValidationResult(valid=True, errors=[])
    return ValidationResult(valid=False, errors=_structured_errors_from_list(collected))


def _structured_errors_from_list(errs: list[jsonschema.ValidationError]) -> list[dict]:
    out: list[dict] = []
    for err in errs:
        out.append(
            {
                "path": _format_path(err.absolute_path),
                "message": err.message,
                "validator": err.validator,
                "validator_value": err.validator_value,
            }
        )
    return out


def validate_audit_file(path: Path, repo_root: Path | None = None) -> ValidationResult:
    """Load and validate an audit JSON file. File/parse errors are reported as
    a non-valid result with a structured error (so the CLI maps them to exit 2)."""
    if not path.exists():
        return ValidationResult(
            valid=False,
            errors=[{"path": "<file>", "message": f"audit file not found: {path}", "validator": "exists"}],
        )
    try:
        with path.open() as f:
            doc = json.load(f)
    except json.JSONDecodeError as exc:
        return ValidationResult(
            valid=False,
            errors=[{"path": "<file>", "message": f"invalid JSON: {exc.msg} (line {exc.lineno})", "validator": "json"}],
        )
    return validate_audit_doc(doc, repo_root=repo_root)


def _emit(result: ValidationResult) -> int:
    payload = result.to_structured()
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.valid else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate an audit JSON against expert_audit_output.schema.json (hard run-abort gate).",
    )
    parser.add_argument("audit_json", help="path to the audit JSON file to validate")
    args = parser.parse_args(argv)
    result = validate_audit_file(Path(args.audit_json))
    return _emit(result)


if __name__ == "__main__":
    sys.exit(main())
