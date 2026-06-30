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
E2_PLUS = {"E2_tested", "E3_cross_checked", "E4_regression_proven"}


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
    semantic_errors = _semantic_evidence_errors(doc)
    if not collected and not semantic_errors:
        return ValidationResult(valid=True, errors=[])
    return ValidationResult(
        valid=False,
        errors=[*_structured_errors_from_list(collected), *semantic_errors],
    )


def _semantic_evidence_errors(doc: object) -> list[dict]:
    """Cross-field evidence binding checks beyond JSON Schema.

    E2+ claims are only valid when backed by deterministic command receipts.
    The summary evidence floor gates the whole document, and each E2+ finding
    must bind to one or more indexes in ``scope.commands_run``.
    """
    if not isinstance(doc, dict):
        return []

    scope = doc.get("scope", {})
    commands_run = scope.get("commands_run", []) if isinstance(scope, dict) else []
    command_count = len(commands_run) if isinstance(commands_run, list) else 0
    errors: list[dict] = []

    summary = doc.get("summary", {})
    evidence_floor = summary.get("evidence_floor") if isinstance(summary, dict) else None
    if evidence_floor in E2_PLUS and command_count == 0:
        errors.append({
            "path": "summary/evidence_floor",
            "message": f"summary.evidence_floor={evidence_floor} requires at least one scope.commands_run receipt",
            "validator": "deterministic_evidence",
            "validator_value": "scope.commands_run minItems 1 for E2+",
        })

    findings = doc.get("findings", [])
    if not isinstance(findings, list):
        return errors
    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            continue
        evidence_level = finding.get("evidence_level")
        if evidence_level not in E2_PLUS:
            continue
        refs = finding.get("evidence_refs")
        if command_count == 0:
            errors.append({
                "path": f"findings/{idx}/evidence_refs",
                "message": f"finding evidence_level={evidence_level} requires scope.commands_run receipts",
                "validator": "deterministic_evidence",
                "validator_value": "scope.commands_run minItems 1 for E2+ findings",
            })
            continue
        if not isinstance(refs, list) or not refs:
            errors.append({
                "path": f"findings/{idx}/evidence_refs",
                "message": f"finding evidence_level={evidence_level} requires non-empty evidence_refs",
                "validator": "deterministic_evidence",
                "validator_value": "non-empty indexes into scope.commands_run",
            })
            continue
        bad_refs = [ref for ref in refs if not isinstance(ref, int) or ref < 0 or ref >= command_count]
        if bad_refs:
            errors.append({
                "path": f"findings/{idx}/evidence_refs",
                "message": f"evidence_refs {bad_refs} do not point to existing scope.commands_run receipts",
                "validator": "deterministic_evidence",
                "validator_value": f"0..{command_count - 1}",
            })
    return errors


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
