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
- ``no_op_diff`` — the candidate changes no effective content; a baseline
  score from an empty proposal is not an improvement.
- ``provider_error`` — a typed transport failure, not a model proposal.
"""

from __future__ import annotations

import ast
import fnmatch
import math
import re
import shlex
import textwrap
from dataclasses import dataclass, field
from pathlib import PurePosixPath
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


def _in_scope(path: str, patterns: list[str]) -> bool:
    """A path is in scope if it matches a glob OR sits under a dir-prefix pattern.

    Supports both ``kernels/*.py`` (glob) and ``examples/foo/`` (directory
    prefix) so target evolve-path declarations can use either style.
    """
    if (
        not path
        or path.startswith("/")
        or "\\" in path
        or "\x00" in path
        or any(part in {"", ".", ".."} for part in path.split("/"))
        or PurePosixPath(path).as_posix() != path
    ):
        return False
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
        base = pat.rstrip("/")
        if base and (path == base or path.startswith(base + "/") or fnmatch.fnmatch(path, base + "/*")):
            return True
    return False


def _strip_git_prefix(path: str) -> str:
    return path[2:] if path.startswith(("a/", "b/")) else path


def _added_paths(diff: str) -> tuple[list[str], str | None]:
    """Return every path named by textual and structural git diff sections."""
    paths: list[str] = []
    malformed: str | None = None
    saw_git_section = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            saw_git_section = True
            try:
                tokens = shlex.split(line)
            except ValueError:
                tokens = []
            if len(tokens) != 4 or tokens[:2] != ["diff", "--git"]:
                malformed = "malformed diff --git section header"
                continue
            paths.extend(_strip_git_prefix(token) for token in tokens[2:])
        elif line.startswith("+++ ") or line.startswith("--- "):
            token = line[4:].strip()
            if token in ("/dev/null", ""):
                continue
            paths.append(_strip_git_prefix(token))
        elif line.startswith(("rename from ", "rename to ", "copy from ", "copy to ")):
            if not saw_git_section:
                malformed = "rename/copy metadata lacks a bound diff --git section"
            _, _, token = line.partition(" ")
            _, _, token = token.partition(" ")
            if not token:
                malformed = "malformed rename/copy path"
            else:
                paths.append(_strip_git_prefix(token))
        elif line.startswith("Binary files "):
            if not saw_git_section:
                malformed = "binary metadata lacks a bound diff --git section"
            match = re.fullmatch(r"Binary files (.+) and (.+) differ", line)
            if match is None:
                malformed = "malformed binary diff section"
            else:
                for token in match.groups():
                    if token != "/dev/null":
                        paths.append(_strip_git_prefix(token))
        elif line.startswith(
            (
                "old mode ",
                "new mode ",
                "new file mode ",
                "deleted file mode ",
                "similarity index ",
                "dissimilarity index ",
                "GIT binary patch",
            )
        ) and not saw_git_section:
            malformed = "structural git metadata lacks a bound diff --git section"
    return paths, malformed


def _has_effective_change(diff: str) -> bool:
    """Return whether a raw blob or unified diff contains changed content."""
    text = diff.strip()
    if not text:
        return False
    is_diff = "+++" in text or "---" in text or text.startswith(("diff ", "@@"))
    if not is_diff:
        return True
    for line in text.splitlines():
        if line.startswith("+") and not line.startswith("+++") and line[1:].strip():
            return True
        if line.startswith("-") and not line.startswith("---") and line[1:].strip():
            return True
    return False


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
) -> str | None:
    source = textwrap.dedent(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Added fragments are often not standalone modules (for example an
        # indented return inside an existing function). Fall back to a bounded
        # lexical scan instead of treating parse failure as permission.
        for module in sorted(forbidden_modules):
            if re.search(rf"\b(?:from|import)\s+{re.escape(module)}\b", source):
                return f"lexical import {module}"
            if re.search(rf"\b{re.escape(module)}(?:\.[A-Za-z_]\w*)+\s*\(", source):
                return f"lexical call through {module}"
        for call in sorted(forbidden_calls):
            if re.search(rf"(?:\b|\.){re.escape(call)}\s*\(", source):
                return f"lexical call {call}()"
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in forbidden_modules:
                    return f"import {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in forbidden_modules:
                return f"from {node.module} import ..."
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in forbidden_calls:
                return f"call {func.id}()"
            if isinstance(func, ast.Attribute):
                root = func.value
                while isinstance(root, ast.Attribute):
                    root = root.value
                if isinstance(root, ast.Name) and root.id in forbidden_modules:
                    return f"call {root.id}.{func.attr}()"
                if func.attr in forbidden_calls:
                    return f"attribute call {func.attr}()"
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
        fired.append("provider_error")
        details["provider_error"] = str(
            candidate.metadata.get("provider_error", "routes_exhausted")
        )
    elif not _has_effective_change(candidate.diff):
        fired.append("no_op_diff")
        details["no_op_diff"] = "candidate contains no effective content change"

    touched, malformed_diff = _added_paths(candidate.diff)
    if allowed_paths is not None:
        if malformed_diff is not None:
            fired.append("out_of_scope_diff")
            details["out_of_scope_diff"] = malformed_diff
        elif not touched:
            fired.append("out_of_scope_diff")
            details["out_of_scope_diff"] = (
                "candidate has no file header binding it to the declared evolve scope"
            )
        else:
            for path in touched:
                if not _in_scope(path, allowed_paths):
                    fired.append("out_of_scope_diff")
                    details["out_of_scope_diff"] = (
                        f"{path} not within allowed evolve paths {allowed_paths}"
                    )
                    break

    hit = _scan_forbidden_primitives(
        _added_python_source(candidate.diff), forbidden_modules, forbidden_calls
    )
    if hit is not None:
        fired.append("forbidden_primitive")
        details["forbidden_primitive"] = hit

    return TripwireReport(fired=tuple(fired), details=details)


def check_determinism(
    first: "EvalReceipt", second: "EvalReceipt", *, tol: float = 1e-9
) -> str | None:
    """Return ``"nondeterministic_score"`` if two same-seed runs disagree."""
    if not math.isfinite(first.fitness) or not math.isfinite(second.fitness):
        return "nondeterministic_score"
    if abs(first.fitness - second.fitness) > tol:
        return "nondeterministic_score"
    return None


def check_timing(receipt: "EvalReceipt", *, floor_s: float) -> str | None:
    """Return ``"suspicious_fast_eval"`` if the benchmark was implausibly fast."""
    if not math.isfinite(receipt.wall_clock_s) or not math.isfinite(floor_s):
        return "suspicious_fast_eval"
    if floor_s > 0 and receipt.wall_clock_s < floor_s:
        return "suspicious_fast_eval"
    return None
