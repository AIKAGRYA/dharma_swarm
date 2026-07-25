#!/usr/bin/env python3
"""Sattva Assurance Boundary V0 — contracts, not counts, on critical surfaces.

The quality ratchet (scripts/governance/hygiene/ratchet.py) preserves
floors repo-wide. This module is the complementary organ: a small, sharp
ASSURANCE BOUNDARY — the set of modules where the swarm's correctness
actually lives — inside which specific, machine-checkable contracts must
hold. Counts say "the swamp did not get larger"; contracts say "the
bridge holds". V0 boundary:

    dharma_swarm/spine/**          (dispatch: invoke_agent + EvidenceReceipt)
    dharma_swarm/memory_kernel/**  (memory front door: governed writes)
    dharma_swarm/a2a/**            (inter-agent transport and bridge)
    dharma_swarm/runtime_state.py  (runtime receipts + idempotency)
    dharma_swarm/runtime_provider.py (canonical provider door)

Contracts (AB-04/AB-05 hold at zero and fail this gate; AB-01/02/03 are
measured here and BANKED by the ratchet, which forbids them to grow):

    AB-01  Boundary record classes (.*Receipt/.*Record/.*Identity/.*Packet
           dataclasses) are frozen; receipt/record classes also carry a
           schema_version field. Provenance is structured data.
    AB-02  No broad exception handler (bare / Exception / BaseException)
           inside the boundary continues without re-raising, escalating,
           or emitting a witness/receipt/log call. (The 92% rule.)
    AB-03  No asyncio task is spawned fire-and-forget inside the
           boundary: every create_task/ensure_future result is held.
    AB-04  No direct LLM-provider import inside the boundary outside the
           canonical door (runtime_provider.py). One way, not two.
    AB-05  Every layer declared in ACTIVE_SURFACE_MANIFEST.yaml's
           correlation_spine resolves: receipt_module exists on disk,
           defines receipt_class, and the class carries the declared
           identity_field (or its alias). The join map cannot dangle.

All checks are AST-static: no boundary module is imported, so the gate
cannot be subverted by import-time side effects and runs anywhere the
interpreter runs (stdlib-only, per governance-surface law). Exit 0 =
all hold-at-zero contracts hold; exit 1 = a contract is violated, with
file:line evidence; exit 2 = the boundary could not be measured (a
crashing gate blocks; it never waves through).

Non-goals: this gate does not prove runtime joinability (that is
tests/test_spine_persistence_invariant.py's job), does not replace the
spine bypass report, and does not score anything.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = Path("ACTIVE_SURFACE_MANIFEST.yaml")
REPORT_SCHEMA_VERSION = "assurance_boundary_report.v1"

BOUNDARY_PACKAGES = ("dharma_swarm/spine", "dharma_swarm/memory_kernel", "dharma_swarm/a2a")
BOUNDARY_MODULES = ("dharma_swarm/runtime_state.py", "dharma_swarm/runtime_provider.py")
# The one sanctioned door for provider SDKs; everything else in the
# boundary must reach providers through it.
PROVIDER_DOOR = "dharma_swarm/runtime_provider.py"
PROVIDER_SDKS = ("anthropic", "openai", "google.generativeai", "litellm", "cohere", "mistralai")

RECORD_NAME_RE = re.compile(r".*(Receipt|Record|Identity|Packet)$")
# A call whose name suggests the failure was witnessed rather than
# swallowed: logging, receipt/witness emission, or explicit escalation.
WITNESS_CALL_RE = re.compile(
    r"(log|logger|logging|warn|error|exception|critical|receipt|witness|escalate|record_|emit|publish|notify)",
    re.IGNORECASE,
)

EXIT_HOLDS = 0
EXIT_VIOLATED = 1
EXIT_BROKEN = 2


class BrokenBoundary(RuntimeError):
    """The boundary could not be measured; the gate must block."""


@dataclass(frozen=True, slots=True)
class Violation:
    contract: str
    location: str
    detail: str

    def render(self) -> str:
        return f"{self.contract} {self.location}: {self.detail}"


@dataclass(frozen=True, slots=True)
class BoundaryReport:
    """Everything one run observed, split by enforcement semantics."""

    hold_at_zero: tuple[Violation, ...]  # AB-04, AB-05 — any entry fails the gate
    measured: dict[str, tuple[Violation, ...]]  # AB-01/02/03 — banked by the ratchet

    def measured_counts(self) -> dict[str, int]:
        return {contract: len(items) for contract, items in self.measured.items()}


# ---------------------------------------------------------------------------
# Boundary enumeration and parsing
# ---------------------------------------------------------------------------


def boundary_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for package in BOUNDARY_PACKAGES:
        root = repo_root / package
        if not root.is_dir():
            raise BrokenBoundary(f"boundary package missing: {package}")
        files.extend(sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts))
    for module in BOUNDARY_MODULES:
        path = repo_root / module
        if not path.is_file():
            raise BrokenBoundary(f"boundary module missing: {module}")
        files.append(path)
    return files


def _parse(path: Path, repo_root: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        raise BrokenBoundary(f"cannot parse {path.relative_to(repo_root)}: {exc}") from exc


def _rel(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


# ---------------------------------------------------------------------------
# AB-01: frozen, schema-versioned records
# ---------------------------------------------------------------------------


def _dataclass_decorator(node: ast.ClassDef) -> ast.expr | None:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        if name == "dataclass":
            return decorator
    return None


def _is_frozen(decorator: ast.expr) -> bool:
    if not isinstance(decorator, ast.Call):
        return False  # bare @dataclass defaults to frozen=False
    for keyword in decorator.keywords:
        if keyword.arg == "frozen":
            return isinstance(keyword.value, ast.Constant) and keyword.value.value is True
    return False


def _class_field_names(node: ast.ClassDef) -> set[str]:
    fields: set[str] = set()
    for statement in node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            fields.add(statement.target.id)
        elif isinstance(statement, ast.Assign):
            fields.update(t.id for t in statement.targets if isinstance(t, ast.Name))
    return fields


def check_record_discipline(tree: ast.Module, rel: str) -> Iterator[Violation]:
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and RECORD_NAME_RE.match(node.name)):
            continue
        decorator = _dataclass_decorator(node)
        if decorator is None:
            continue  # non-dataclass record types are AB-01 v1 scope, not v0
        if not _is_frozen(decorator):
            yield Violation("AB-01", f"{rel}:{node.lineno}", f"{node.name} dataclass is not frozen=True")
        if node.name.endswith(("Receipt", "Record")) and "schema_version" not in _class_field_names(node):
            yield Violation("AB-01", f"{rel}:{node.lineno}", f"{node.name} has no schema_version field")


# ---------------------------------------------------------------------------
# AB-02: broad swallows must witness
# ---------------------------------------------------------------------------

_BROAD = {"Exception", "BaseException"}


def _is_broad(handler: ast.ExceptHandler) -> bool:
    kind = handler.type
    if kind is None:
        return True
    if isinstance(kind, ast.Name):
        return kind.id in _BROAD
    if isinstance(kind, ast.Tuple):
        return any(isinstance(e, ast.Name) and e.id in _BROAD for e in kind.elts)
    return False


def _call_name(call: ast.Call) -> str:
    target = call.func
    parts: list[str] = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    return ".".join(reversed(parts))


def _handler_witnesses(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(handler):
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Call) and WITNESS_CALL_RE.search(_call_name(node)):
            return True
    return False


def check_broad_swallows(tree: ast.Module, rel: str) -> Iterator[Violation]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and _is_broad(node) and not _handler_witnesses(node):
            yield Violation(
                "AB-02", f"{rel}:{node.lineno}",
                "broad except continues without re-raise, escalation, or witness call",
            )


# ---------------------------------------------------------------------------
# AB-03: no fire-and-forget task spawns
# ---------------------------------------------------------------------------

_SPAWNERS = {"create_task", "ensure_future"}


def check_unsupervised_spawns(tree: ast.Module, rel: str) -> Iterator[Violation]:
    for node in ast.walk(tree):
        # A spawn whose entire statement is the bare call: the Task handle
        # is dropped on the floor, so no one can observe its failure.
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
            continue
        name = _call_name(node.value)
        if name.split(".")[-1] in _SPAWNERS:
            yield Violation(
                "AB-03", f"{rel}:{node.lineno}",
                f"{name}(...) result discarded — task failure is unobservable",
            )


# ---------------------------------------------------------------------------
# AB-04: provider SDKs only through the canonical door
# ---------------------------------------------------------------------------


def check_provider_door(tree: ast.Module, rel: str) -> Iterator[Violation]:
    if rel == PROVIDER_DOOR:
        return
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        for name in names:
            if any(name == sdk or name.startswith(sdk + ".") for sdk in PROVIDER_SDKS):
                yield Violation(
                    "AB-04", f"{rel}:{node.lineno}",
                    f"direct provider import '{name}' — route through {PROVIDER_DOOR}",
                )


# ---------------------------------------------------------------------------
# AB-05: declared correlation-spine layers resolve
# ---------------------------------------------------------------------------

_LAYER_KEY_RE = re.compile(
    r"^\s+(id|receipt_class|receipt_module|identity_field|identity_alias):\s*([\w.]+)\s*$"
)


def parse_spine_layers(repo_root: Path) -> list[dict[str, str]]:
    """Extract correlation_spine.layers from the manifest.

    The manifest is full YAML but governance scripts are stdlib-only, so
    this reads the five scalar keys each layer declares, keyed on the
    stable `- id:` item shape. Any structural surprise is BROKEN, not a
    silent empty result: zero layers would make AB-05 pass vacuously.
    """
    manifest = repo_root / MANIFEST_PATH
    if not manifest.is_file():
        raise BrokenBoundary(f"manifest missing: {MANIFEST_PATH}")
    in_spine = in_layers = False
    layers: list[dict[str, str]] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.startswith("correlation_spine:"):
            in_spine = True
            continue
        if in_spine and not line.startswith((" ", "#")) and line.strip():
            break  # next top-level key ends the block
        if not in_spine:
            continue
        if re.match(r"^\s{2}layers:\s*$", line):
            in_layers = True
            continue
        if in_layers and re.match(r"^\s{2}\w", line):
            in_layers = False  # sibling key of layers: ends the list
        if not in_layers:
            continue
        if re.match(r"^\s+-\s+id:", line):
            layers.append({"id": line.split(":", 1)[1].strip()})
            continue
        match = _LAYER_KEY_RE.match(line)
        if match and layers:
            layers[-1][match.group(1)] = match.group(2)
    if not layers:
        raise BrokenBoundary("correlation_spine.layers parsed to zero entries — manifest shape changed?")
    return layers


def check_spine_layers(repo_root: Path) -> Iterator[Violation]:
    for layer in parse_spine_layers(repo_root):
        layer_id = layer.get("id", "<unnamed>")
        module = layer.get("receipt_module")
        klass = layer.get("receipt_class")
        identity = layer.get("identity_field")
        if not (module and klass and identity):
            yield Violation("AB-05", f"layer {layer_id}", "layer missing receipt_module/receipt_class/identity_field")
            continue
        path = repo_root / (module.replace(".", "/") + ".py")
        if not path.is_file():
            yield Violation("AB-05", f"layer {layer_id}", f"receipt_module {module} has no file at {path.relative_to(repo_root)}")
            continue
        tree = _parse(path, repo_root)
        classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
        # The declared name may be a module-level alias of the real class
        # (e.g. ``EvidenceReceipt = ClosureEvidenceReceipt`` during a
        # rename deprecation window) — follow one hop.
        aliases = {
            target.id: node.value.id
            for node in tree.body
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        class_node = classes.get(klass) or classes.get(aliases.get(klass, ""))
        if class_node is None:
            yield Violation("AB-05", f"layer {layer_id}", f"{module} does not define class {klass}")
            continue
        fields = _class_field_names(class_node)
        accepted = {identity, layer.get("identity_alias", identity)}
        if not (fields & accepted):
            yield Violation(
                "AB-05", f"layer {layer_id}",
                f"{klass} carries none of the declared identity fields {sorted(accepted)}",
            )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run_boundary(repo_root: Path) -> BoundaryReport:
    measured: dict[str, list[Violation]] = {"AB-01": [], "AB-02": [], "AB-03": []}
    hold: list[Violation] = []
    for path in boundary_files(repo_root):
        rel = _rel(path, repo_root)
        tree = _parse(path, repo_root)
        measured["AB-01"].extend(check_record_discipline(tree, rel))
        measured["AB-02"].extend(check_broad_swallows(tree, rel))
        measured["AB-03"].extend(check_unsupervised_spawns(tree, rel))
        hold.extend(check_provider_door(tree, rel))
    hold.extend(check_spine_layers(repo_root))
    return BoundaryReport(
        hold_at_zero=tuple(hold),
        measured={k: tuple(v) for k, v in measured.items()},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sattva Assurance Boundary V0 contract gate.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument(
        "--contract", help="show evidence for one contract id (AB-01..AB-05)"
    )
    args = parser.parse_args(argv)

    try:
        report = run_boundary(args.repo_root.resolve())
    except BrokenBoundary as exc:
        print(f"assurance-boundary: BROKEN — {exc}", file=sys.stderr)
        return EXIT_BROKEN

    if args.contract:
        wanted = args.contract.upper()
        items = report.measured.get(wanted, ()) or tuple(
            v for v in report.hold_at_zero if v.contract == wanted
        )
        for violation in items:
            print(violation.render())
        print(f"{wanted}: {len(items)} finding(s)")
        return EXIT_HOLDS

    if args.json:
        print(
            json.dumps(
                {
                    "schema_version": REPORT_SCHEMA_VERSION,
                    "holds": not report.hold_at_zero,
                    "hold_at_zero_violations": [v.render() for v in report.hold_at_zero],
                    "measured_counts": report.measured_counts(),
                },
                indent=2,
            )
        )
    else:
        for contract, count in sorted(report.measured_counts().items()):
            print(f"  {contract} (measured, ratchet-banked): {count}")
        print(f"  AB-04/AB-05 (hold at zero): {len(report.hold_at_zero)} violation(s)")
        for violation in report.hold_at_zero:
            print(f"    {violation.render()}")

    return EXIT_VIOLATED if report.hold_at_zero else EXIT_HOLDS


if __name__ == "__main__":
    raise SystemExit(main())
