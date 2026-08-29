"""Ring-1 tripwires — the reward-hacking / scope-violation detectors.

Every serious evolutionary-code system that skipped these has been gamed
(Sakana's CUDA Engineer found a memory exploit in its own evaluator; OpenEvolve's
flagship MLX result was three eval-validity bugs; Heuresis measured a ~2.5%
fabrication rate where fakes reached the archive). These checks run BEFORE the
blind evaluator's score is trusted, and any trip forces fitness to zero
(:func:`dharma_swarm.foundry.evaluator.blind_evaluate`).

Checks:

- ``out_of_scope_diff`` — the candidate touched a path outside the target's
  declared evolve paths (the classic "edit the grader" hack).
- ``forbidden_primitive`` — added Python code imports/calls an escape hatch
  (``os``/``sys``/``subprocess``/``socket``/``ctypes``/``eval``/``exec``/...),
  the vector used to forge logs or read the scoring code.
- ``nondeterministic_score`` — two runs at the same seed disagree (randomness
  hack).
- ``suspicious_fast_eval`` — the evaluation returned faster than physically
  plausible (a hardcoded answer, not a real benchmark).
- ``no_op_diff`` — the candidate changes nothing. Without this, an empty diff
  scores baseline fitness and enters the archive as a "win" — the exact
  "vacuous fitness / phantom applied" failure the organism's own history
  records (empty diffs auto-passed in an earlier evolution lane; see
  docs/vision_maps/MASTER_2026-06-10_leverage_synthesis.md F4).
"""

from __future__ import annotations

import ast
import fnmatch
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from dharma_swarm.foundry.evaluator import Candidate, EvalReceipt


DEFAULT_FORBIDDEN_MODULES: frozenset[str] = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "socket",
        "ctypes",
        "shutil",
        "importlib",
        "builtins",
        "multiprocessing",
        "resource",
    }
)
DEFAULT_FORBIDDEN_CALLS: frozenset[str] = frozenset(
    {"eval", "exec", "compile", "__import__", "getattr", "setattr", "globals", "vars"}
)


@dataclass(frozen=True)
class TripwireReport:
    """Which tripwires fired and why."""

    fired: tuple[str, ...] = ()
    details: dict[str, str] = field(default_factory=dict)

    @property
    def clean(self) -> bool:
        return not self.fired


@dataclass(frozen=True)
class DiffPathReport:
    """Static proof that every unified-diff header addresses one safe path.

    The path check deliberately runs before any applier or canonicalizer.  Git's
    ``--unsafe-paths`` and patch(1)'s fuzz are never a security boundary.
    """

    paths: tuple[str, ...] = ()
    category: str = ""
    detail: str = ""

    @property
    def clean(self) -> bool:
        return not self.category


_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


def _header_path(raw: str, *, side: str) -> tuple[str, str]:
    """Return ``(normalized_path, error)`` for one ---/+++ token."""
    # Timestamps are separated by a tab in portable unified diffs.  Spaces in
    # paths are intentionally unsupported: accepting git's quoted path grammar
    # would create a second, easy-to-desynchronise parser in this safety gate.
    token = raw.split("\t", 1)[0].strip()
    if not token:
        return "", "empty diff header"
    if token == "/dev/null":
        return "", "file creation/deletion is outside the single-file mutation contract"
    if token.startswith(("/", "\\")) or _WINDOWS_DRIVE.match(token):
        return "", f"absolute diff path rejected: {token!r}"
    expected_prefix = "a/" if side == "old" else "b/"
    if not token.startswith(expected_prefix):
        return "", f"{side} header must begin with {expected_prefix!r}"
    token = token[2:]
    if not token or "\\" in token or "\x00" in token:
        return "", f"non-portable diff path rejected: {token!r}"
    pure = PurePosixPath(token)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        return "", f"traversal diff path rejected: {token!r}"
    normalized = pure.as_posix()
    if normalized != token:
        return "", f"non-canonical diff path rejected: {token!r}"
    return normalized, ""


def _path_within_tree(tree_root: Path, rel_path: str) -> tuple[bool, str]:
    """Reject symlink components and resolved containment escapes."""
    root = Path(tree_root).resolve()
    cursor = root
    for part in PurePosixPath(rel_path).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return False, f"symlink component rejected: {rel_path!r}"
    try:
        resolved = (root / rel_path).resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError):
        return False, f"resolved diff path escapes target tree: {rel_path!r}"
    return True, ""


def validate_diff_paths(
    diff: str,
    *,
    expected_path: str | None = None,
    allowed_paths: list[str] | None = None,
    tree_root: Path | None = None,
) -> DiffPathReport:
    """Parse and validate unified-diff headers without touching the target.

    Every file must have one adjacent ``--- a/...`` / ``+++ b/...`` pair with
    identical normalized paths and at least one hunk.  Absolute paths,
    traversal, creations/deletions, quoted/ambiguous headers, mismatched pairs,
    and symlink components fail closed.
    """
    if not diff.strip():
        return DiffPathReport(category="no_op_diff", detail="empty diff")
    lines = diff.splitlines()
    paths: list[str] = []
    index = 0
    saw_header = False
    while index < len(lines):
        line = lines[index]
        if line.startswith("--- "):
            saw_header = True
            if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
                return DiffPathReport(category="malformed_diff", detail="--- header lacks adjacent +++ header")
            old_path, old_error = _header_path(line[4:], side="old")
            new_path, new_error = _header_path(lines[index + 1][4:], side="new")
            if old_error or new_error:
                return DiffPathReport(
                    category="unsafe_diff_path",
                    detail=old_error or new_error,
                )
            if old_path != new_path:
                return DiffPathReport(
                    category="mismatched_diff_headers",
                    detail=f"old={old_path!r} new={new_path!r}",
                )
            if expected_path is not None and old_path != expected_path:
                return DiffPathReport(
                    category="mismatched_diff_headers",
                    detail=f"expected={expected_path!r} actual={old_path!r}",
                )
            if allowed_paths is not None and not _in_scope(old_path, allowed_paths):
                return DiffPathReport(
                    category="out_of_scope_diff",
                    detail=f"{old_path} not within allowed evolve paths {allowed_paths}",
                )
            if tree_root is not None:
                contained, detail = _path_within_tree(Path(tree_root), old_path)
                if not contained:
                    return DiffPathReport(category="symlink_escape", detail=detail)
            # A second header before a hunk is malformed.  Metadata lines such
            # as ``index`` may precede the pair, but content may not follow it
            # without a hunk.
            cursor = index + 2
            saw_hunk = False
            while cursor < len(lines) and not lines[cursor].startswith("--- "):
                if lines[cursor].startswith("@@ "):
                    saw_hunk = True
                cursor += 1
            if not saw_hunk:
                return DiffPathReport(category="malformed_diff", detail=f"no hunk for {old_path}")
            paths.append(old_path)
            index = cursor
            continue
        if line.startswith("+++ "):
            return DiffPathReport(category="malformed_diff", detail="orphan +++ header")
        index += 1
    if not saw_header or not paths:
        return DiffPathReport(category="extraction_failure", detail="no unified-diff header pair")
    if len(set(paths)) != len(paths):
        return DiffPathReport(category="malformed_diff", detail="duplicate file header pair")
    return DiffPathReport(paths=tuple(paths))


def _in_scope(path: str, patterns: list[str]) -> bool:
    """A path is in scope if it matches a glob OR sits under a dir-prefix pattern.

    Supports both ``kernels/*.py`` (glob) and ``examples/foo/`` (directory
    prefix) so target evolve-path declarations can use either style.
    """
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
        base = pat.rstrip("/")
        if pat.endswith("/") and base and (
            path == base or path.startswith(base + "/")
        ):
            return True
    return False


def _added_paths(diff: str) -> list[str]:
    """Paths a unified diff touches (from ``+++ b/<path>`` headers)."""
    paths: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            token = line[4:].strip()
            if token in ("/dev/null", ""):
                continue
            if token.startswith(("a/", "b/")):
                token = token[2:]
            paths.append(token)
    return paths


def _has_effective_change(diff: str) -> bool:
    """True if the diff (or raw blob) contains any actual content change.

    A unified diff must have at least one ``+``/``-`` content line (headers
    don't count). A raw non-diff blob counts as content if it is non-blank.
    """
    text = diff.strip()
    if not text:
        return False
    is_diff = "+++" in text or "---" in text or text.startswith(("diff ", "@@"))
    if not is_diff:
        return True
    for line in text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            if line[1:].strip():
                return True
        if line.startswith("-") and not line.startswith("---"):
            if line[1:].strip():
                return True
    return False


def has_effective_change(diff: str) -> bool:
    """Public static predicate used before proposal application/canonicalization."""
    return _has_effective_change(diff)


def _added_python_source(diff: str) -> str:
    """The added lines of a unified diff, as candidate Python source.

    Non-diff input (a bare code blob) is returned as-is so the scanner also
    works on raw candidate source.
    """
    if "\n+" not in diff and not diff.startswith("+"):
        return diff
    out: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            out.append(line[1:])
    return "\n".join(out)


def _scan_forbidden_primitives(
    source: str,
    forbidden_modules: frozenset[str],
    forbidden_calls: frozenset[str],
) -> tuple[str, str] | None:
    source = textwrap.dedent(source)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return (
            "static_source_invalid",
            f"Python candidate source does not parse at line {exc.lineno or 0}",
        )

    def attribute_root(node: ast.AST) -> str:
        while isinstance(node, ast.Attribute):
            node = node.value
        return node.id if isinstance(node, ast.Name) else ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in forbidden_modules:
                    return "forbidden_primitive", f"import {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in forbidden_modules:
                return "forbidden_primitive", f"from {node.module} import ..."
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in forbidden_calls:
                return "forbidden_primitive", f"call {func.id}()"
            if isinstance(func, ast.Attribute):
                root = attribute_root(func)
                if func.attr in forbidden_calls:
                    return "forbidden_primitive", f"attribute call .{func.attr}()"
                if root in forbidden_modules:
                    return (
                        "forbidden_primitive",
                        f"forbidden module attribute call {root}.{func.attr}()",
                    )
    return None


def scan_tripwires(
    candidate: "Candidate",
    *,
    allowed_paths: list[str] | None = None,
    forbidden_modules: frozenset[str] = DEFAULT_FORBIDDEN_MODULES,
    forbidden_calls: frozenset[str] = DEFAULT_FORBIDDEN_CALLS,
) -> TripwireReport:
    """Static ring-1 checks on a candidate diff (scope + forbidden primitives)."""
    fired: list[str] = []
    details: dict[str, str] = {}

    proposal_status = str(candidate.metadata.get("proposal_status", ""))
    if proposal_status == "provider_error":
        # Infrastructure failure is not a model no-op. Keeping this typed lets
        # the daemon alert/fail over without teaching the archive that an empty
        # transport response was a proposed code change.
        fired.append("provider_error")
        details["provider_error"] = str(
            candidate.metadata.get("provider_error", "routes_exhausted")
        )
    elif proposal_status in {
        "no_op_diff",
        "empty_response",
        "extraction_failure",
        "malformed_diff",
        "apply_failure",
        "canonicalization_failure",
        "unsafe_diff_path",
        "mismatched_diff_headers",
        "symlink_escape",
        "out_of_scope_diff",
    }:
        fired.append(proposal_status)
        details[proposal_status] = str(
            candidate.metadata.get("proposal_error", proposal_status)
        )
    else:
        path_report = validate_diff_paths(candidate.diff, allowed_paths=allowed_paths)
        if not path_report.clean:
            fired.append(path_report.category)
            details[path_report.category] = path_report.detail
        elif not _has_effective_change(candidate.diff):
            fired.append("no_op_diff")
            details["no_op_diff"] = "candidate contains no effective content change"

    if not fired and (
        not path_report.paths
        or any(path.endswith(".py") for path in path_report.paths)
    ):
        applied_source = candidate.metadata.get("applied_source")
        source = (
            applied_source
            if isinstance(applied_source, str)
            else _added_python_source(candidate.diff)
        )
        hit = _scan_forbidden_primitives(
            source, forbidden_modules, forbidden_calls
        )
        if hit is not None:
            category, detail = hit
            fired.append(category)
            details[category] = detail

    return TripwireReport(fired=tuple(fired), details=details)


def check_determinism(
    first: "EvalReceipt", second: "EvalReceipt", *, tol: float = 1e-9
) -> str | None:
    """Return ``"nondeterministic_score"`` if two same-seed runs disagree."""
    if abs(first.fitness - second.fitness) > tol:
        return "nondeterministic_score"
    return None


def check_timing(receipt: "EvalReceipt", *, floor_s: float) -> str | None:
    """Return ``"suspicious_fast_eval"`` if the benchmark was implausibly fast."""
    if floor_s > 0 and receipt.wall_clock_s < floor_s:
        return "suspicious_fast_eval"
    return None
