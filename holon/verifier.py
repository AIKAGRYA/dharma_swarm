"""Strict standalone verifier for the Holon package."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


FORBIDDEN_IMPORT_PREFIXES = ("dharma_swarm",)
FORBIDDEN_CORE_TOKENS = ("dash" "board", "A" "PEX", "control" "_surface")
REQUIRED_FILES = ("pyproject.toml", "README.md", "cli.py", "holon_runtime.py", "receipts.py")


@dataclass(frozen=True)
class VerificationFinding:
    status: str
    code: str
    message: str
    path: str = ""


@dataclass
class VerificationReport:
    status: str
    findings: list[VerificationFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "findings": [finding.__dict__ for finding in self.findings],
        }


def verify_standalone(package_root: Path | None = None) -> VerificationReport:
    root = (package_root or Path(__file__).resolve().parent).resolve()
    findings: list[VerificationFinding] = []
    for relative in REQUIRED_FILES:
        path = root / relative
        findings.append(
            VerificationFinding(
                "pass" if path.exists() else "fail",
                "required_file_present" if path.exists() else "required_file_missing",
                f"{relative} {'present' if path.exists() else 'missing'}",
                str(path),
            )
        )
    for path in _python_files(root):
        rel = path.relative_to(root).as_posix()
        if rel.startswith("tests/") or rel.startswith("adapters/"):
            continue
        findings.extend(_check_imports(path))
        if path.name != "verifier.py":
            findings.extend(_check_tokens(path))
    status = "pass" if not any(item.status == "fail" for item in findings) else "fail"
    return VerificationReport(status=status, findings=findings)


def verify_standalone_json(package_root: Path | None = None) -> str:
    return json.dumps(verify_standalone(package_root).to_dict(), sort_keys=True, indent=2)


def _python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _check_imports(path: Path) -> list[VerificationFinding]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [VerificationFinding("fail", "syntax_error", str(exc), str(path))]
    findings: list[VerificationFinding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                findings.extend(_import_findings(path, alias.name))
        elif isinstance(node, ast.ImportFrom):
            findings.extend(_import_findings(path, node.module or ""))
        elif isinstance(node, ast.Call):
            findings.extend(_dynamic_import_findings(path, node))
    if not findings:
        findings.append(VerificationFinding("pass", "no_forbidden_imports", "no forbidden imports", str(path)))
    return findings


def _import_findings(path: Path, imported: str) -> list[VerificationFinding]:
    for prefix in FORBIDDEN_IMPORT_PREFIXES:
        if imported == prefix or imported.startswith(prefix + "."):
            return [
                VerificationFinding(
                    "fail",
                    "forbidden_parent_import",
                    f"forbidden import {imported}",
                    str(path),
                )
            ]
    return []


def _dynamic_import_findings(path: Path, node: ast.Call) -> list[VerificationFinding]:
    imported = _dynamic_import_target(node)
    if not imported:
        return []
    findings = _import_findings(path, imported)
    return [
        VerificationFinding(
            "fail",
            "forbidden_dynamic_parent_import",
            finding.message.replace("forbidden import", "forbidden dynamic import"),
            finding.path,
        )
        for finding in findings
    ]


def _dynamic_import_target(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name) and node.func.id == "__import__":
        return _first_string_arg(node)
    if (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "import_module"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "importlib"
    ):
        return _first_string_arg(node)
    return ""


def _first_string_arg(node: ast.Call) -> str:
    if not node.args:
        return ""
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return ""


def _check_tokens(path: Path) -> list[VerificationFinding]:
    text = path.read_text(encoding="utf-8")
    normalized = text.casefold()
    findings = [
        VerificationFinding(
            "fail",
            "forbidden_core_token",
            f"forbidden core token {token}",
            str(path),
        )
        for token in FORBIDDEN_CORE_TOKENS
        if token.casefold() in normalized
    ]
    if not findings:
        findings.append(VerificationFinding("pass", "no_forbidden_core_tokens", "no forbidden core tokens", str(path)))
    return findings
