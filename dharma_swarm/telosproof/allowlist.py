"""Deny-by-default ALLOW-LIST translator (TelosProof v1, increment 1).

THE v1 INSIGHT (from the adversarial review of v0)
--------------------------------------------------
v0 enumerates DANGER: it carries closed positive-marker vocabularies and asks
"does this diff contain a known-bad marker?". That is structurally bypassable —
any rename or synonym the proposer chooses steps outside the enumerated set.

v1 INVERTS the question to DENY-BY-DEFAULT. Instead of looking for red flags,
it demands a GREEN CREDENTIAL for *every* change-operation in a diff: is this
operation a member of a small, closed, hand-proven ALLOW-LIST of safe primitive
operations? If yes -> ``allowed``. If it is anything else — touches a safety
surface, carries a per-op danger locus, removes more than it adds, or simply
cannot be classified — it is ``unknown`` and routes to **REVIEW**. An unknown
operation is NEVER admitted to ``allowed``; ALLOW is a positive proof-of-safe-
vocabulary, not an absence-of-red-flag.

CARDINAL RULE (read before changing any matcher here)
-----------------------------------------------------
A false REVIEW (a safe patch waits for a human) is cheap. A false ALLOW (an
unknown op slips through) is the exact failure this layer exists to prevent.
Therefore every primitive matcher below is a SUFFICIENT condition for safety,
provable line-by-line — NOT a heuristic "probably fine". When in doubt whether
an op is a given primitive, do NOT classify it as that primitive: leave it
unknown. Under-include on purpose.

STRICTLY-STRONGER-THAN-v0 (load-bearing acceptance invariant)
-------------------------------------------------------------
Layer L0 below runs first and short-circuits: if the v0 ``ChangeSummary`` has
ANY danger flag set, or net-removes from a safety surface, the WHOLE changeset
is unknown -> REVIEW. This makes the allow-list's ALLOW set a strict SUBSET of
what v0 already passes — the translator can only ever be MORE conservative than
``telosproof_gate``, never less.

ADVISORY ONLY
-------------
Pure function. No side effects, no disk writes (invariant #7 binds the
translator too). ``DHARMA_PROOF_ENFORCE`` is read ONLY to set the severity of an
emitted ``ProofObligation`` — never to alter control flow. NOT imported by
``diff_applier`` / ``dgm_loop`` / ``evolution``. The translator NEVER returns
BLOCK — BLOCK remains v0/gate territory for hard-violated invariants. The
allow-list's job is the binary ALLOW-vs-REVIEW deny-by-default gate: an
allow-list models "provably safe", whose complement is "not proven safe = needs
a human/proof", i.e. REVIEW.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Optional

from dharma_swarm.models import GateDecision, ProofObligation
from dharma_swarm.telosproof.change_summary import (
    ChangeSummary,
    extract_change_summary,
)

# Reuse v0 internals by IMPORT — never redefine. The leading-underscore names
# are module-private in change_summary, but reusing them (rather than re-typing
# the vocabularies) is the whole point: a single source of truth for the
# safety-surface markers and persistence detection means this layer can never
# drift more-permissive than v0.
from dharma_swarm.telosproof.change_summary import (  # noqa: F401  (re-exported)
    _SAFETY_SURFACE_PATH_MARKERS,
    _PERSISTENCE_NEW_FILE_SUFFIXES,
    _PERSISTENCE_MARKERS,
    _OPEN_WRITE_RE,
    _AUTONOMY_MARKERS,
    _SHADOW_MARKERS,
    _is_substantive_code,
    _norm,
    _DEVNULL,
)

# Reuse the live protected-file set / classifier — never duplicate the list.
from dharma_swarm.dgm_loop import _is_protected_dgm_target

# L3-AST structural danger detection lives in ast_safety (split out to keep both
# modules under the 1000-line budget). ``_ast_danger_locus`` is the in-module
# entrypoint name the classifiers below call; it is re-exported here unchanged.
from dharma_swarm.telosproof.ast_safety import (  # noqa: F401  (re-exported)
    _ast_danger_locus,
    _DangerVisitor,
    _attr_chain_tail,
    _open_is_write_mode,
    _assign_target_is_elevation,
    _DANGER_CALL_NAMES,
    _DANGER_IMPORT_ROOTS,
    _ELEVATION_ATTR_FRAGMENTS,
    _ENVIRON_NAMES,
)


# ---------------------------------------------------------------------------
# Thin PUBLIC re-exports of v0 constants (so downstream Generators — the JSON
# Schema in schema/, the Lean inductive in lean/ — can reference them by a
# stable public name without reaching into change_summary's private surface).
# This module does NOT mutate change_summary; it only re-exposes.
# ---------------------------------------------------------------------------
SAFETY_SURFACE_PATH_MARKERS: tuple[str, ...] = tuple(_SAFETY_SURFACE_PATH_MARKERS)
PERSISTENCE_NEW_FILE_SUFFIXES: tuple[str, ...] = tuple(_PERSISTENCE_NEW_FILE_SUFFIXES)


# ---------------------------------------------------------------------------
# THE SAFE-PRIMITIVE VOCABULARY — the SINGLE Python source of truth.
# Byte-identical to the JSON Schema $defs.SafePrimitive.enum (Generator 4) and
# the Lean SafePrimitive constructors (Generator 2). The cross-language seam.
# ---------------------------------------------------------------------------
SAFE_PRIMITIVES: frozenset[str] = frozenset(
    {
        "add_pure_function",
        "edit_comment_or_docstring",
        "add_test",
        "edit_non_safety_file_body",
        "add_non_persistence_file",
    }
)


# ---------------------------------------------------------------------------
# Per-op danger-locus markers (L3). Reuse v0 marker tuples by import where they
# exist; the autonomy/shadow env tokens below are the same surface v0 scans, but
# we look for them at the per-line locus so the evidence string is precise. L0
# already catches the corresponding ChangeSummary flag; L3 is belt-and-suspenders
# so an unknown op's evidence points at the exact added line.
# ---------------------------------------------------------------------------
_PERSISTENCE_IMPORT_MARKERS: tuple[str, ...] = (
    "import sqlite3",
    "import aiosqlite",
    "from sqlalchemy",
    "import sqlalchemy",
    "import psycopg2",
    "import redis",
    "import shelve",
    "import pickle",
    "import dbm",
    "import lmdb",
)
_ENV_FLAG_MARKERS: tuple[str, ...] = (
    "os.environ",
    "os.getenv",
    "environ[",
    "setenv",
)
_AUTONOMY_SHADOW_TOKENS: tuple[str, ...] = tuple(_AUTONOMY_MARKERS) + tuple(_SHADOW_MARKERS)


# ---------------------------------------------------------------------------
# Diff-parsing toolkit (per-file blocks + per-file body lines). Uses the SAME
# _body_lines split semantics v0 uses, re-derived here scoped to a single file
# block so classification is per-file. We re-implement the tiny header walk
# rather than import the private _extract_paths, because we need per-block path
# + new/deleted attribution that the public ChangeSummary aggregates away.
# ---------------------------------------------------------------------------
_DIFF_GIT_RE = re.compile(r"^diff --git a/(?P<a>\S+) b/(?P<b>\S+)", re.MULTILINE)
_MINUS_HEADER_RE = re.compile(r"^--- (?:a/)?(?P<path>\S+)", re.MULTILINE)
_PLUS_HEADER_RE = re.compile(r"^\+\+\+ (?:b/)?(?P<path>\S+)", re.MULTILINE)
_NEW_FILE_RE = re.compile(r"^new file mode", re.MULTILINE)
_DELETED_FILE_RE = re.compile(r"^deleted file mode", re.MULTILINE)
# A NEW top-level function added on a '+' line (def / async def at column 0).
_TOPLEVEL_DEF_RE = re.compile(r"^(?:async\s+)?def\s+\w+\s*\(")
# A NEW test function (def test_*).
_TEST_DEF_RE = re.compile(r"^(?:async\s+)?def\s+test_\w*\s*\(")


@dataclass(frozen=True)
class _FileBlock:
    """One per-file slice of a unified diff, with body lines already split."""

    path: str
    is_new: bool
    is_deleted: bool
    added: tuple[str, ...]
    removed: tuple[str, ...]


def _block_body_lines(block: str) -> tuple[list[str], list[str]]:
    """Return (added_content_lines, removed_content_lines) for one block.

    SAME semantics as change_summary._body_lines: exactly the two prefixes
    ``+++``/``---`` are headers; everything else starting with a single +/- is
    body. Re-derived (not imported) only because we operate per-block.
    """
    added: list[str] = []
    removed: list[str] = []
    for line in block.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
    return added, removed


def _split_blocks(diff_text: str) -> list[str]:
    """Split a unified diff into per-file blocks (git or plain)."""
    blocks = re.split(r"(?=^diff --git )", diff_text, flags=re.MULTILINE)
    if len(blocks) == 1 and not diff_text.lstrip().startswith("diff --git"):
        return [diff_text]
    # The first element of re.split with a lookahead can be an empty preamble.
    return [b for b in blocks if b.strip()]


def _parse_file_blocks(diff_text: str) -> list[_FileBlock]:
    """Parse a diff into typed per-file blocks.

    Raises on a structurally malformed block (a block that contains hunk body
    lines but resolves to no usable path) so R4 (cannot-classify -> REVIEW) can
    fire deterministically rather than silently dropping the block.
    """
    out: list[_FileBlock] = []
    for block in _split_blocks(diff_text):
        gm = _DIFF_GIT_RE.search(block)
        minus = _MINUS_HEADER_RE.search(block)
        plus = _PLUS_HEADER_RE.search(block)

        minus_path = _norm(minus.group("path")) if minus else None
        plus_path = _norm(plus.group("path")) if plus else None

        is_new = bool(_NEW_FILE_RE.search(block)) or (minus_path == _DEVNULL)
        is_del = bool(_DELETED_FILE_RE.search(block)) or (plus_path == _DEVNULL)

        # Resolve the canonical path for this block (prefer the non-/dev/null
        # side; fall back to the git header).
        path: Optional[str] = None
        for cand in (plus_path, minus_path):
            if cand and cand != _DEVNULL:
                path = cand
                break
        if path is None and gm:
            for cand in (_norm(gm.group("b")), _norm(gm.group("a"))):
                if cand and cand != _DEVNULL:
                    path = cand
                    break

        added, removed = _block_body_lines(block)

        if path is None:
            # A block with body content but no resolvable path is malformed.
            # Surface it as a malformed-block signal (caught -> REVIEW via R4).
            if added or removed:
                raise ValueError("malformed diff block: body lines with no path")
            # An empty/headerless preamble fragment with no body -> skip.
            continue

        out.append(
            _FileBlock(
                path=path,
                is_new=is_new,
                is_deleted=is_del,
                added=tuple(added),
                removed=tuple(removed),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Operation:
    """One classified change-operation.

    ``primitive`` is a SAFE_PRIMITIVES member when the op is positively proven
    safe, and ``None`` when the op is unknown (== REVIEW). ``locus`` is a short
    human-readable evidence string pointing at WHY the classification landed.
    """

    file: str
    primitive: Optional[str]
    locus: str


@dataclass(frozen=True)
class ClassificationResult:
    """The deny-by-default verdict over a whole changeset.

    ``decision`` is ALLOW iff ``unknown == ()`` AND no deny-by-default guard
    fired; otherwise REVIEW. The translator never returns BLOCK.
    """

    allowed: tuple[Operation, ...]
    unknown: tuple[Operation, ...]
    decision: GateDecision

    def to_proof_obligation(self, severity: Optional[str] = None) -> ProofObligation:
        """Adapt the result into a ProofObligation for gate reuse.

        ``severity`` defaults to the DHARMA_PROOF_ENFORCE-derived value
        (advisory unless enforcement is explicitly requested). The flag is read
        ONLY here, ONLY to set severity — it never alters classification.
        """
        sev = severity if severity is not None else _severity_from_env()
        satisfied = self.decision is GateDecision.ALLOW
        if satisfied:
            evidence = [f"{op.primitive}: {op.locus}" for op in self.allowed]
            predicate = "all_operations_are_safe_primitives"
        else:
            evidence = [f"unknown[{op.file}]: {op.locus}" for op in self.unknown]
            predicate = "deny_by_default_unknown_operation"
        return ProofObligation(
            gate_name="telosproof_allowlist",
            obligation_type="safety_contract",
            predicate=predicate,
            satisfied=satisfied,
            evidence_required=evidence,
            severity=sev,
        )


def _severity_from_env() -> str:
    """Read DHARMA_PROOF_ENFORCE (default off) -> severity string only."""
    raw = os.environ.get("DHARMA_PROOF_ENFORCE", "0").strip().lower()
    return "enforcing" if raw not in ("", "0", "false", "no", "off") else "advisory"


# ---------------------------------------------------------------------------
# Per-file primitive classification (L2 + L3 fused per file)
# ---------------------------------------------------------------------------

def _line_has_danger_locus(line: str) -> Optional[str]:
    """L3: return a danger-locus evidence string if an ADDED line is unsafe.

    Checks: write-mode open / persistence import or call / env-flag reference /
    autonomy or shadow token. Reuses v0 marker tuples / regex by import.
    Returns None when the line carries no per-op danger locus.
    """
    low = line.lower()
    if _OPEN_WRITE_RE.search(line):
        return "write-mode open() on added line"
    for m in _PERSISTENCE_IMPORT_MARKERS:
        if m in low:
            return f"persistence import on added line ({m!r})"
    for m in _PERSISTENCE_MARKERS:
        if m in low:
            return f"persistence call on added line ({m!r})"
    for m in _ENV_FLAG_MARKERS:
        if m in low:
            return f"env-flag reference on added line ({m!r})"
    for m in _AUTONOMY_SHADOW_TOKENS:
        if m in low:
            return f"autonomy/shadow token on added line ({m!r})"
    return None


def _added_has_danger_locus(added: tuple[str, ...]) -> Optional[str]:
    """L3 over a whole hunk: first danger-locus evidence, or None."""
    for ln in added:
        locus = _line_has_danger_locus(ln)
        if locus is not None:
            return locus
    return None


# ---------------------------------------------------------------------------
# L3-AST structural body-level danger detection: see ast_safety.py.
# ``_ast_danger_locus`` (imported above) walks a parseable source body for any
# write / persist / spawn / exec / mutate-env / elevate op and is the structural
# replacement for the leaky literal token list. The classifiers below call it.
# ---------------------------------------------------------------------------


# Match the `+` body lines that belong to ONE newly-added top-level function:
# from a top-level `def`/`async def` line until (exclusive) the next top-level
# `def`/`class` line. Used to reconstruct a parseable function source from the
# added lines of a pure-addition hunk.
def _added_function_sources(added: tuple[str, ...]) -> list[str]:
    """Reconstruct each newly-added top-level function's source from added lines.

    Operates on the raw added (post-'+'-strip) lines. A top-level def starts a
    new function block; subsequent indented (or blank) lines belong to it until
    the next column-0 def/class/decorator. Returns one dedented source string per
    function. If the added lines do not parse as a standalone module, the WHOLE
    added block is returned verbatim as a single source so the AST parse fails
    upstream and routes to REVIEW (cannot-prove-safe).
    """
    sources: list[str] = []
    current: list[str] = []
    in_func = False
    for ln in added:
        is_toplevel_def = bool(_TOPLEVEL_DEF_RE.match(ln))
        is_toplevel_other = (
            ln
            and not ln[0].isspace()
            and not is_toplevel_def
            and not ln.startswith("@")
        )
        if is_toplevel_def:
            if current:
                sources.append("\n".join(current))
            current = [ln]
            in_func = True
            continue
        if in_func:
            if is_toplevel_other:
                # A new top-level non-def line ends the function block.
                sources.append("\n".join(current))
                current = []
                in_func = False
            else:
                current.append(ln)
    if current:
        sources.append("\n".join(current))
    if not sources:
        # No reconstructable function — hand the whole block back so the caller's
        # AST parse decides (likely unparseable -> REVIEW).
        return ["\n".join(added)]
    return sources


def _is_comment_or_docstring_only(lines: tuple[str, ...]) -> bool:
    """True iff every line is non-substantive (comment/docstring/blank).

    Reuses change_summary._is_substantive_code: an op is comment/docstring-only
    iff it contains ZERO substantive lines. An empty tuple is vacuously True.
    """
    return all(not _is_substantive_code(ln) for ln in lines)


def _pure_function_addition_locus(
    added: tuple[str, ...], removed: tuple[str, ...]
) -> Optional[str]:
    """Return None iff the hunk is a PROVABLY-safe pure top-level function add.

    Sufficient-safe conditions (ALL must hold); otherwise a danger-evidence
    string is returned (the op is NOT add_pure_function):
      * no removed lines (a pure addition; any removal -> not this primitive);
      * at least one added line is a top-level ``def`` / ``async def``;
      * no added line carries a per-op danger locus (L3 token belt-and-suspenders);
      * AST-LEVEL PROOF: every reconstructed added-function body parses AND
        contains NO write / persist / spawn / exec / mutate-env / elevate
        operation through ANY surface. An unparseable body cannot be proven safe.

    This is the FN2/FN3/FN4 fix: the body is structurally proven safe via the
    `ast` module, not merely scanned for a small literal token list. Renamed,
    aliased, chained, or low-level write/persist/spawn/exec/elevate forms are all
    caught structurally; what cannot be parsed is treated as maximally unsafe.
    """
    if removed:
        return "pure-addition required: hunk removes lines"
    if not any(_TOPLEVEL_DEF_RE.match(ln) for ln in added):
        return "no top-level def in added lines"
    # Belt: cheap per-line literal markers (kept; they only ever ADD review).
    line_locus = _added_has_danger_locus(added)
    if line_locus is not None:
        return f"line-level danger locus: {line_locus}"
    # Suspenders: AST structural proof over each reconstructed function body.
    for src in _added_function_sources(added):
        ast_locus = _ast_danger_locus(src)
        if ast_locus is not None:
            if ast_locus == "<unparseable>":
                return "added function body is not AST-parseable (cannot prove safe)"
            return f"AST danger: {ast_locus}"
    return None


def _is_pure_function_addition(added: tuple[str, ...], removed: tuple[str, ...]) -> bool:
    """True iff the hunk is a PROVABLY-safe pure top-level function addition."""
    return _pure_function_addition_locus(added, removed) is None


def _is_test_addition(block: _FileBlock) -> bool:
    """True iff the op is a test addition under tests/.

    Two sufficient-safe forms:
      * a NEW file matching tests/test_*.py;
      * a pure addition (no removed lines) of a ``def test_*`` inside an existing
        tests/ file, with no per-op danger locus.
    """
    path = block.path
    posix = PurePosixPath(path)
    # Path must live under a tests/ directory and be a test_*.py file.
    parts = posix.parts
    under_tests = "tests" in parts
    is_testfile = posix.name.startswith("test_") and posix.suffix == ".py"
    if not (under_tests and is_testfile):
        return False
    if block.is_new:
        # Brand-new test file: pure addition by construction; still require the
        # full line-level + AST belt so a "test" file that imports sqlite / opens
        # a store / spawns / execs is unknown.
        return _new_pyfile_added_danger_locus(block) is None
    # Existing test file: require pure addition of a def test_* with no removal,
    # line-level clean, AND AST-clean over the added function bodies.
    if block.removed:
        return False
    if not any(_TEST_DEF_RE.match(ln) for ln in block.added):
        return False
    if _added_has_danger_locus(block.added) is not None:
        return False
    return _pure_function_addition_locus(block.added, block.removed) is None


def _is_add_non_persistence_file(block: _FileBlock) -> bool:
    """True iff the op is a brand-new non-persistence, non-test source/text file.

    Sufficient-safe conditions (ALL must hold):
      * the block is a NEW file;
      * its suffix is NOT in _PERSISTENCE_NEW_FILE_SUFFIXES;
      * no added line carries a per-op danger locus (write open / persistence /
        env-flag / autonomy / shadow).
    (A new file under tests/ is handled by _is_test_addition first.)
    """
    if not block.is_new:
        return False
    suffix = PurePosixPath(block.path).suffix.lower()
    if suffix in _PERSISTENCE_NEW_FILE_SUFFIXES:
        return False
    return _new_pyfile_added_danger_locus(block) is None


def _count_substantive(lines: tuple[str, ...]) -> int:
    return sum(1 for ln in lines if _is_substantive_code(ln))


def _dedent_added_block(added: tuple[str, ...]) -> str:
    """Join added lines and strip the common leading indentation.

    A mid-function diff hunk's added lines keep their original indentation, which
    would never parse as a standalone module. We remove the minimum common indent
    across non-blank lines so a self-contained statement block (e.g. an addition-
    only body edit) becomes AST-parseable. Fragments that are still syntactically
    incomplete simply fail to parse (caller treats as "<unparseable>", which for
    the body-edit primitive falls back to the line-level + zero-removal floor).
    """
    nonblank = [ln for ln in added if ln.strip()]
    if not nonblank:
        return ""
    indent = min(len(ln) - len(ln.lstrip()) for ln in nonblank)
    return "\n".join(ln[indent:] if ln.strip() else "" for ln in added)


def _new_pyfile_added_danger_locus(block: _FileBlock) -> Optional[str]:
    """Combined line-level + AST danger evidence for a NEW-file/full-content add.

    For a brand-new ``.py`` file (or any block whose added lines constitute the
    whole file content), the added lines ARE a complete module, so an AST parse
    is meaningful: we structurally prove the absence of any write/persist/spawn/
    exec/mutate-env/elevate op, and treat an unparseable ``.py`` body as
    maximally unsafe. For non-``.py`` additions the AST step is skipped and only
    the line-level token belt applies (a JSON/text file has no Python semantics
    to prove, and its persistence-suffix gating happens at the call site).
    """
    line_locus = _added_has_danger_locus(block.added)
    if line_locus is not None:
        return f"line-level danger locus: {line_locus}"
    if PurePosixPath(block.path).suffix.lower() == ".py":
        ast_locus = _ast_danger_locus("\n".join(block.added))
        if ast_locus is not None:
            if ast_locus == "<unparseable>":
                return "new .py file is not AST-parseable (cannot prove safe)"
            return f"AST danger: {ast_locus}"
    return None


def _is_non_safety_body_edit(block: _FileBlock) -> bool:
    """True iff a substantive body edit to a non-safety file is PROVABLY-safe.

    FN1 FIX — the cardinal hardening. The old floor only forbade a *net* removal
    (``removed_sub > added_sub``), which ALLOWED deleting a real safety/approval
    guard whenever it was balanced by an equal-or-greater count of added
    substantive lines. The adversarial critic demonstrated removing
    ``if not self.gate.check(plan): raise`` from a live orchestrator/swarm file
    while adding two unrelated substantive lines -> ALLOW. Deletions are EXACTLY
    where safety is silently lost; a balanced delete+add is NEVER this primitive.

    Conditions (ALL must hold), otherwise -> unknown -> REVIEW:
      * not a new file and not a deletion (those are other primitives / unknown);
      * ZERO removed SUBSTANTIVE lines. ANY gross or net removal of substantive
        code disqualifies this primitive. (Pure-comment/blank removals do not
        count as substantive and are tolerated — they cannot delete a guard.)
      * the added lines carry no per-op danger locus AND, treated as additive
        statements, contain no AST-level write/persist/spawn/exec/mutate-env/
        elevate operation. A balanced delete+add is already excluded by the
        zero-removal floor; this also forbids an addition-only body edit from
        smuggling a dangerous control-flow/guard mutation.

    Safety-surface and protected-file gating happens in L1 BEFORE this is ever
    called, so by the time we reach here the file is already proven non-safety.
    """
    if block.is_new or block.is_deleted:
        return False
    # FN1: ANY removed substantive line -> not this primitive (deletions are
    # where safety is silently lost). Net-vs-gross no longer matters; a single
    # removed substantive line is disqualifying.
    if _count_substantive(block.removed) > 0:
        return False
    if _added_has_danger_locus(block.added) is not None:
        return False
    # A hunk that introduces a top-level def is FUNCTION-ADDITION territory, not
    # a body edit. It must clear the full pure-function-addition proof (which
    # includes the AST body proof AND the unparseable->REVIEW rule); otherwise it
    # is NOT this primitive. This stops a malformed/dangerous top-level def from
    # being silently re-blessed as a "body edit" when the function-addition path
    # rejected it.
    if any(_TOPLEVEL_DEF_RE.match(ln) for ln in block.added):
        return _pure_function_addition_locus(block.added, block.removed) is None
    # AST belt over the added lines (an addition-only body edit must still not
    # introduce a write/persist/spawn/exec/mutate-env/elevate op). Parse the
    # added lines as a dedented statement block; if they are a syntactically
    # incomplete fragment (common for mid-function hunks) we cannot prove them
    # safe at the AST level, so we fall back to the line-level + zero-removal
    # floor, which is already sufficient for the FN1 guarantee.
    src = _dedent_added_block(block.added)
    ast_locus = _ast_danger_locus(src)
    if ast_locus is not None and ast_locus != "<unparseable>":
        return False
    return True


def _classify_block(block: _FileBlock) -> Operation:
    """Classify a single per-file block into exactly one primitive, or unknown.

    Order matters: more-specific primitives are tried first. Each matcher is a
    SUFFICIENT safety condition. The first that matches wins; if none matches the
    op is unknown (primitive=None) and routes to REVIEW.
    """
    path = block.path

    # --- L1 PER-FILE SAFETY-SURFACE GUARD (deny-by-default) ----------------
    # Any protected file, safety-surface path, or telosproof/* file: ALL of its
    # operations are unknown regardless of how benign the body looks.
    surface = _safety_surface_reason(path)
    if surface is not None:
        return Operation(file=path, primitive=None, locus=surface)

    # --- L2/L3 PER-FILE CLASSIFICATION (try specific -> general) -----------
    # add_test (path-gated to tests/, includes new-file form).
    if _is_test_addition(block):
        return Operation(file=path, primitive="add_test", locus="test addition under tests/")

    # add_non_persistence_file (new non-store, non-test file).
    if block.is_new:
        if _is_add_non_persistence_file(block):
            return Operation(
                file=path,
                primitive="add_non_persistence_file",
                locus="new non-persistence file, no danger locus",
            )
        # A new file that is NOT a safe non-persistence file (persistence suffix,
        # or carries a danger locus) is unknown.
        loc = _added_has_danger_locus(block.added)
        if loc is not None:
            return Operation(file=path, primitive=None, locus=f"new file danger locus: {loc}")
        return Operation(
            file=path,
            primitive=None,
            locus="new file with persistence-store suffix",
        )

    # A deletion of an entire file is never a safe primitive -> unknown (R5).
    if block.is_deleted:
        return Operation(file=path, primitive=None, locus="whole-file deletion")

    # edit_comment_or_docstring (zero substantive added AND removed).
    if _is_comment_or_docstring_only(block.added) and _is_comment_or_docstring_only(
        block.removed
    ):
        # Even a comment-only edit must be L3-clean (a comment can't carry a
        # danger locus by construction, but check defensively).
        if _added_has_danger_locus(block.added) is None:
            return Operation(
                file=path,
                primitive="edit_comment_or_docstring",
                locus="comment/docstring-only edit",
            )

    # add_pure_function (pure addition introducing a top-level def, L3 clean).
    if _is_pure_function_addition(block.added, block.removed):
        return Operation(
            file=path,
            primitive="add_pure_function",
            locus="pure top-level function addition",
        )

    # edit_non_safety_file_body (substantive edit, L3 clean, not a net-removal).
    if _is_non_safety_body_edit(block):
        return Operation(
            file=path,
            primitive="edit_non_safety_file_body",
            locus="non-safety body edit (added>=removed, no danger locus)",
        )

    # --- nothing matched -> unknown (deny-by-default) ----------------------
    loc = _added_has_danger_locus(block.added)
    if loc is not None:
        return Operation(file=path, primitive=None, locus=f"danger locus: {loc}")
    removed_sub = _count_substantive(block.removed)
    added_sub = _count_substantive(block.added)
    if removed_sub > added_sub:
        return Operation(
            file=path,
            primitive=None,
            locus="net-removal (removed-substantive > added-substantive)",
        )
    return Operation(
        file=path,
        primitive=None,
        locus="unclassifiable change-operation (no safe primitive matched)",
    )


def _safety_surface_reason(path: str) -> Optional[str]:
    """L1: return an evidence string if a path is a safety surface, else None.

    A path is a safety surface if its basename is a DGM-protected file, its
    normalized path matches a safety-surface marker, or it is a telosproof/*
    file. Reuses the live frozenset / classifier and the imported markers.
    """
    try:
        if _is_protected_dgm_target(path):
            return f"DGM-protected file ({PurePosixPath(path).name})"
    except Exception:
        # An unparseable path is maximally unsafe (mirror v0 cardinal rule).
        return "unparseable path (treated as protected)"
    low = path.lower()
    for marker in _SAFETY_SURFACE_PATH_MARKERS:
        if marker in low:
            return f"safety-surface path marker ({marker!r})"
    if "telosproof" in low:
        return "telosproof/* file"
    return None


# ---------------------------------------------------------------------------
# L0 GLOBAL DENY GUARD — strictly-stronger-than-v0 backstop
# ---------------------------------------------------------------------------

_V0_DANGER_FLAGS: tuple[str, ...] = (
    "modifies_protected_files",
    "disables_receipts",
    "disables_rollback",
    "bypasses_human_approval",
    "raises_autonomy",
    "disables_shadow_mode",
    "creates_new_persistence",
)


def _l0_tripped_flags(summary: ChangeSummary) -> list[str]:
    """Return the v0 danger flags (+ net-removal backstop) that are set."""
    tripped = [f for f in _V0_DANGER_FLAGS if getattr(summary, f)]
    if summary.net_removes_from_safety_surface:
        tripped.append("net_removes_from_safety_surface")
    return tripped


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def classify_operations(
    summary_or_diff: "str | ChangeSummary",
    metadata: Optional[dict[str, Any]] = None,
) -> ClassificationResult:
    """Deny-by-default allow-list classification of a self-modification's body.

    Args:
        summary_or_diff: EITHER a raw unified-diff ``str`` (we call
            ``extract_change_summary`` internally AND re-parse the diff text for
            per-op classification) OR an already-extracted ``ChangeSummary``
            (we reuse it for L0; with no diff text we cannot do per-op L2/L3, so
            a non-trivial ChangeSummary with danger flags still routes to REVIEW
            via L0, and a clean ChangeSummary with touched paths routes to
            REVIEW because per-op safe-primitive proof is unavailable).
        metadata: Optional out-of-band context, forwarded to
            ``extract_change_summary`` when a raw diff is given.

    Returns:
        A :class:`ClassificationResult`. ``decision`` is ALLOW iff
        ``unknown == ()`` and no L0/L1/L3 guard fired; else REVIEW. Never BLOCK.

    Pure, advisory, no I/O. The cardinal rule: an operation not positively
    classified as a known-safe primitive is ALWAYS unknown and ALWAYS REVIEW.
    """
    metadata = metadata or {}

    # Resolve the ChangeSummary (L0 input) and the diff text (L1/L2/L3 input).
    diff_text: Optional[str]
    if isinstance(summary_or_diff, ChangeSummary):
        summary = summary_or_diff
        diff_text = None
    else:
        diff_text = summary_or_diff or ""
        try:
            summary = extract_change_summary(diff_text, metadata)
        except Exception as exc:  # R4: cannot extract -> REVIEW.
            op = Operation(
                file="<diff>",
                primitive=None,
                locus=f"extract_change_summary failed: {exc!r}",
            )
            return ClassificationResult(
                allowed=(), unknown=(op,), decision=GateDecision.REVIEW
            )

    # --- L0 GLOBAL DENY GUARD (runs first, short-circuits) -----------------
    tripped = _l0_tripped_flags(summary)
    if tripped:
        op = Operation(
            file="<changeset>",
            primitive=None,
            locus="v0 danger flag(s) set: " + ", ".join(tripped),
        )
        return ClassificationResult(
            allowed=(), unknown=(op,), decision=GateDecision.REVIEW
        )

    # --- Empty / no-op edge case -------------------------------------------
    # A genuinely empty changeset (no touched paths and, when available, no diff
    # body) is vacuously safe: allowed==() , decision=ALLOW. We only grant this
    # when we can CONFIRM the no-op — i.e. there are no touched paths. If a
    # ChangeSummary reports touched paths but we have no diff text to classify
    # per-op, we cannot confirm safety -> REVIEW.
    if diff_text is None:
        # Pre-extracted summary path: no per-op diff available.
        if not summary.touched_paths:
            return ClassificationResult(
                allowed=(), unknown=(), decision=GateDecision.ALLOW
            )
        op = Operation(
            file="<changeset>",
            primitive=None,
            locus="ChangeSummary supplied without diff text; per-op safe-"
            "primitive proof unavailable",
        )
        return ClassificationResult(
            allowed=(), unknown=(op,), decision=GateDecision.REVIEW
        )

    if not diff_text.strip():
        # Whitespace/empty diff with zero touched paths: vacuously safe.
        if not summary.touched_paths:
            return ClassificationResult(
                allowed=(), unknown=(), decision=GateDecision.ALLOW
            )

    # --- L1/L2/L3 PER-FILE CLASSIFICATION ----------------------------------
    try:
        blocks = _parse_file_blocks(diff_text)
    except Exception as exc:  # R4: malformed diff -> REVIEW.
        op = Operation(
            file="<diff>",
            primitive=None,
            locus=f"diff parse failed: {exc!r}",
        )
        return ClassificationResult(
            allowed=(), unknown=(op,), decision=GateDecision.REVIEW
        )

    if not blocks:
        # We only reach here with NON-empty, NON-whitespace diff text (the
        # genuinely empty/whitespace case already returned vacuous ALLOW above).
        # Non-empty text that yields no classifiable file blocks is UNPARSEABLE
        # — not a no-op — so it routes to REVIEW (R4: cannot-classify ->
        # maximally-unsafe), mirroring v0's cardinal rule. Vacuous ALLOW is NOT
        # granted here; that would let arbitrary non-diff text pass.
        op = Operation(
            file="<diff>",
            primitive=None,
            locus="non-empty text with no classifiable diff blocks (unparseable)",
        )
        return ClassificationResult(
            allowed=(), unknown=(op,), decision=GateDecision.REVIEW
        )

    allowed: list[Operation] = []
    unknown: list[Operation] = []
    for block in blocks:
        try:
            op = _classify_block(block)
        except Exception as exc:  # R4: any classification error -> unknown.
            unknown.append(
                Operation(
                    file=block.path,
                    primitive=None,
                    locus=f"classification error: {exc!r}",
                )
            )
            continue
        # Defensive: a primitive must be in the closed vocabulary to count.
        if op.primitive is not None and op.primitive in SAFE_PRIMITIVES:
            allowed.append(op)
        else:
            # Force unknown if a matcher ever returns an off-vocabulary name.
            if op.primitive is not None:
                op = Operation(
                    file=op.file,
                    primitive=None,
                    locus=f"off-vocabulary primitive {op.primitive!r} forced unknown",
                )
            unknown.append(op)

    decision = (
        GateDecision.ALLOW
        if not unknown and allowed
        else GateDecision.REVIEW
    )
    # A diff that produced blocks but classified to ZERO allowed ops and zero
    # unknowns (impossible by construction, but defensive) -> REVIEW.
    if not allowed and not unknown:
        decision = GateDecision.REVIEW
        unknown = [
            Operation(
                file="<diff>",
                primitive=None,
                locus="no operations classified from a non-empty diff",
            )
        ]

    return ClassificationResult(
        allowed=tuple(allowed),
        unknown=tuple(unknown),
        decision=decision,
    )


__all__ = [
    "SAFE_PRIMITIVES",
    "SAFETY_SURFACE_PATH_MARKERS",
    "PERSISTENCE_NEW_FILE_SUFFIXES",
    "Operation",
    "ClassificationResult",
    "classify_operations",
]
