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
from dataclasses import dataclass, field
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
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
        base = pat.rstrip("/")
        if base and (path == base or path.startswith(base + "/") or fnmatch.fnmatch(path, base + "/*")):
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
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Non-Python target (kernel, C++, config) — AST scan does not apply;
        # diff-scope still guards these.
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
    elif not _has_effective_change(candidate.diff):
        fired.append("no_op_diff")
        details["no_op_diff"] = "candidate contains no effective content change"

    touched = _added_paths(candidate.diff)
    if allowed_paths is not None:
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
    if abs(first.fitness - second.fitness) > tol:
        return "nondeterministic_score"
    return None


def check_timing(receipt: "EvalReceipt", *, floor_s: float) -> str | None:
    """Return ``"suspicious_fast_eval"`` if the benchmark was implausibly fast."""
    if floor_s > 0 and receipt.wall_clock_s < floor_s:
        return "suspicious_fast_eval"
    return None
