"""Mutation-kill regression suite for the TelosProof safety kernel.

PURPOSE
-------
This file exists to KILL surviving mutants in the telosproof package — with an
absolute priority on the class of mutant that would flip a gate decision toward
LESS-SAFE (a previously-REVIEW/BLOCK case returning ALLOW). The cardinal rule of
the kernel is: false-positives (a safe patch flagged for review) are acceptable;
false-negatives (a dangerous patch reported safe) are FORBIDDEN. A surviving
mutant that turns a danger check permissive is the exact false-negative this
kernel exists to prevent, so every such mutant gets a dedicated regression here.

Each test below is written so that:
  * it PASSES against the real (unmutated) telosproof code, and
  * it FAILS (catches the regression) if the corresponding mutant were live —
    i.e. it asserts a property that the mutant would break.

The structure mirrors the safety surfaces:
  * change_summary.py danger-flag setters + diff parser
  * allowlist.py deny-by-default classifier + per-primitive matchers
  * ast_safety.py danger visitor

Decision-flip-to-less-safe kills are grouped first and marked CLASS-A.
"""

from __future__ import annotations

import pytest

from dharma_swarm.models import GateDecision
from dharma_swarm.telosproof import (
    extract_change_summary,
    telosproof_gate,
)
from dharma_swarm.telosproof.allowlist import (
    classify_operations,
)
from dharma_swarm.telosproof import change_summary as cs
from dharma_swarm.telosproof import ast_safety as astsafe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _violated(result) -> set[str]:
    return set(result.gate_results.keys())


def _blocked(result) -> bool:
    """True iff the gate refused to pass (BLOCK or REVIEW) — never silent ALLOW."""
    return result.decision in (GateDecision.BLOCK, GateDecision.REVIEW)


def _allowed_prims(result) -> set:
    return {op.primitive for op in result.allowed}


def _wrap(path: str, added: list[str] = None, removed: list[str] = None,
          new_file: bool = False, deleted_file: bool = False) -> str:
    """Build a minimal valid unified diff for one file."""
    added = added or []
    removed = removed or []
    lines = [f"diff --git a/{path} b/{path}"]
    if new_file:
        lines.append("new file mode 100644")
        lines.append("--- /dev/null")
        lines.append(f"+++ b/{path}")
    elif deleted_file:
        lines.append("deleted file mode 100644")
        lines.append(f"--- a/{path}")
        lines.append("+++ /dev/null")
    else:
        lines.append(f"--- a/{path}")
        lines.append(f"+++ b/{path}")
    lines.append("@@ -1,3 +1,4 @@")
    lines.append(" context_line")
    for r in removed:
        lines.append("-" + r)
    for a in added:
        lines.append("+" + a)
    return "\n".join(lines) + "\n"


# Self-credential lines so invariant (8) never masks the danger flag under test.
# (8) is self-satisfiable by design; supplying it isolates the REAL danger check.
_CRED = ["    # replay_command: pytest -q", "    # rollback_plan: git revert HEAD"]


# ===========================================================================
# CLASS-A KILLS — change_summary.py danger-flag setters + diff parser.
# Each test below drives a SPECIFIC danger flag through a SINGLE detection
# token/branch so that a mutant corrupting that token/branch flips the gate
# decision BLOCK->ALLOW. A surviving such mutant is the exact false-negative
# the kernel forbids. We assert BOTH the non-ALLOW decision AND the specific
# violated predicate, so the assertion is tight enough to catch the flip.
# ===========================================================================


# ---------------------------------------------------------------------------
# (6) shadow-mode disable — _added_shadow_disable + _body_lines.
# Each disable token below is ISOLATED: the line contains exactly that token
# (and "shadow"), is NOT caught by the prior _SHADOW_DISABLE_TOKENS net, and so
# sets disables_shadow_mode SOLELY via _added_shadow_disable. A mutant that
# corrupts that token, lower-cases via .upper(), or returns False makes the
# function miss -> disables_shadow_mode=False -> ALLOW. Self-credentialed so
# invariant (6) is the SOLE gate between BLOCK and ALLOW.
# Kills: _added_shadow_disable mutmut_2..6,13..25; _body_lines mutmut_12.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "token_name,shadow_line",
    [
        ("false", "cfg.shadow = is_false_flag"),   # 'false'
        ("eq_space_0", "shadow_budget = 0"),        # '= 0'
        ("eq_0", "shadow_x=0"),                      # '=0'
        ("dq0", 'cfg.shadow = X"0"X'),               # '"0"'
        ("sq0", "cfg.shadow = X'0'X"),               # "'0'"
        ("none", "cfg.shadow = anone_value"),        # 'none'
        ("disable", "shadow_disable_flag()"),        # 'disable'
        ("off", "shadow_offset = y"),                # 'off'
    ],
)
def test_classA_shadow_disable_each_token_blocks(token_name, shadow_line):
    """A shadow-disable token in isolation must trip invariant (6) -> BLOCK.

    Asserts disables_shadow_mode is set AND the gate BLOCKs via the shadow
    predicate. Kills every per-token corruption of _added_shadow_disable, the
    .upper() lower-casing mutant, and the `return False` short-circuit, plus the
    _body_lines line[2:] off-by-one that drops the leading char of the body.
    """
    diff = _wrap("boot.py", added=[shadow_line] + _CRED)
    summary = extract_change_summary(diff)
    assert summary.disables_shadow_mode is True, (
        f"shadow token {token_name!r} not detected by change_summary"
    )
    result = telosproof_gate(diff)
    assert result.decision is GateDecision.BLOCK, (
        f"CLASS-A FALSE-NEGATIVE: shadow-disable via {token_name!r} did not BLOCK"
    )
    assert "does_not_disable_shadow_mode" in _violated(result)


def test_classA_shadow_disable_primary_net_blocks():
    """The primary shadow net (`shadow_mode = False`) must also BLOCK.

    Guards the prior _SHADOW_DISABLE_TOKENS path independently of the
    belt-and-suspenders _added_shadow_disable.
    """
    diff = _wrap("boot.py", added=["shadow_mode = False"] + _CRED)
    result = telosproof_gate(diff)
    assert result.decision is GateDecision.BLOCK
    assert "does_not_disable_shadow_mode" in _violated(result)


# ---------------------------------------------------------------------------
# (2) receipt disable — _body_lines added/removed split.
# Removing a receipt emitter must set disables_receipts. The _body_lines
# off-by-one (line[2:]) drops the leading char so "emit_receipt(r)" becomes
# "mit_receipt(r)" still containing "receipt"... so we use a marker whose
# detection depends on the FULL leading text. We assert several removed-marker
# forms so a body-split corruption is caught on at least one.
# Kills: _body_lines mutmut_16 (removed.append off-by-one).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "marker",
    ["emit_receipt(r)", "write_receipt(r)", "log_receipt(r)",
     "emit_witness(e)", "record_receipt(r)"],
)
def test_classA_receipt_removal_blocks(marker):
    diff = _wrap("runner.py", removed=[marker], added=_CRED)
    summary = extract_change_summary(diff)
    assert summary.disables_receipts is True, f"{marker!r} not flagged"
    result = telosproof_gate(diff)
    assert result.decision is GateDecision.BLOCK
    assert "does_not_disable_receipt_emission" in _violated(result)


# ---------------------------------------------------------------------------
# (3) rollback disable — backup-writer removal + create_backup marker.
# The canonical `backup = t.with_suffix('.bak'); shutil.copy2(...)` removal
# carries none of the named rollback markers and is caught only by
# _removes_backup_writer (co-occurrence) feeding disables_rollback=True in
# extract_change_summary. A mutant setting disables_rollback to False/None, or
# breaking _removes_backup_writer, flips BLOCK->ALLOW.
# Kills: extract_change_summary mutmut_48/49; _removes_backup_writer mutmut_5.
# ---------------------------------------------------------------------------

def test_classA_backup_writer_removal_blocks():
    diff = _wrap(
        "applier.py",
        removed=["backup = t.with_suffix(t.suffix + '.bak')",
                 "shutil.copy2(str(t), str(backup))"],
        added=_CRED,
    )
    summary = extract_change_summary(diff)
    assert summary.disables_rollback is True
    result = telosproof_gate(diff)
    assert result.decision is GateDecision.BLOCK
    assert "does_not_disable_rollback" in _violated(result)


def test_classA_create_backup_marker_removal_blocks():
    """A removed `create_backup(p)` marker must also set disables_rollback.

    Kills extract_change_summary mutmut_48/49 via the named-marker path too.
    """
    diff = _wrap("applier.py", removed=["create_backup(p)"], added=_CRED)
    summary = extract_change_summary(diff)
    assert summary.disables_rollback is True
    result = telosproof_gate(diff)
    assert result.decision is GateDecision.BLOCK
    assert "does_not_disable_rollback" in _violated(result)


# ---------------------------------------------------------------------------
# (4) approval bypass — `auto_approve = True` added line.
# The danger is set via the OR of added/removed _APPROVAL_BYPASS_ASSIGN scans.
# A mutant turning the `or` into `and` (mutmut_51/52) requires BOTH branches,
# so a single added `auto_approve = True` no longer fires -> ALLOW. Asserts
# BOTH the v0 gate BLOCKs AND the allowlist REVIEWs (deny-by-default).
# Kills: extract_change_summary mutmut_51/52.
# ---------------------------------------------------------------------------

def test_classA_approval_bypass_added_blocks():
    diff = _wrap("router.py", added=["auto_approve = True"] + _CRED)
    summary = extract_change_summary(diff)
    assert summary.bypasses_human_approval is True
    result = telosproof_gate(diff)
    assert result.decision is GateDecision.BLOCK
    assert "does_not_bypass_human_approval" in _violated(result)
    # Allowlist deny-by-default must also refuse it.
    assert classify_operations(diff).decision is GateDecision.REVIEW


# ---------------------------------------------------------------------------
# (7) persistence — write-mode open() on an added line.
# The _OPEN_WRITE_RE (via _added_line_opens_for_write) must match write/append
# opens. A mutant breaking the regex search flips creates_new_persistence to
# False for an open(...,'w')/open(...,mode='a') that carries no other
# persistence marker -> ALLOW.
# Kills: _added_line_opens_for_write mutmut_2.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "open_line",
    ["f = open('out.txt', 'w')", "f = open('o', mode='a')"],
)
def test_classA_write_mode_open_blocks(open_line):
    diff = _wrap("store.py", added=[open_line] + _CRED)
    summary = extract_change_summary(diff)
    assert summary.creates_new_persistence is True, f"{open_line!r} not flagged"
    result = telosproof_gate(diff)
    assert result.decision is GateDecision.BLOCK
    assert "creates_no_new_persistence_substrate" in _violated(result)


# ===========================================================================
# STRUCTURAL HARDENING — path inventory + net-removal backstop.
# These raise the kill rate AND tighten the path-classification surface that
# feeds invariant (1) (protected-file) and the structural deny-by-default
# backstop. They assert concrete ChangeSummary path tuples / flags so a parser
# mutant that mis-attributes added/deleted/touched paths is caught.
# ===========================================================================

NEW_FILE_DIFF = """\
diff --git a/dharma_swarm/new_mod.py b/dharma_swarm/new_mod.py
new file mode 100644
--- /dev/null
+++ b/dharma_swarm/new_mod.py
@@ -0,0 +1,1 @@
+x = 1
"""

DELETED_FILE_DIFF = """\
diff --git a/dharma_swarm/old_mod.py b/dharma_swarm/old_mod.py
deleted file mode 100644
--- a/dharma_swarm/old_mod.py
+++ /dev/null
@@ -1,1 +0,0 @@
-x = 1
"""

MODIFY_DIFF = """\
diff --git a/dharma_swarm/mod.py b/dharma_swarm/mod.py
--- a/dharma_swarm/mod.py
+++ b/dharma_swarm/mod.py
@@ -1,1 +1,2 @@
 x = 1
+y = 2
"""


def test_extract_paths_new_file_attribution():
    s = extract_change_summary(NEW_FILE_DIFF)
    assert s.touched_paths == ("dharma_swarm/new_mod.py",)
    assert s.added_paths == ("dharma_swarm/new_mod.py",)
    assert s.deleted_paths == ()


def test_extract_paths_deleted_file_attribution():
    s = extract_change_summary(DELETED_FILE_DIFF)
    assert s.touched_paths == ("dharma_swarm/old_mod.py",)
    assert s.added_paths == ()
    assert s.deleted_paths == ("dharma_swarm/old_mod.py",)


def test_extract_paths_modify_is_neither_added_nor_deleted():
    s = extract_change_summary(MODIFY_DIFF)
    assert s.touched_paths == ("dharma_swarm/mod.py",)
    assert s.added_paths == ()
    assert s.deleted_paths == ()


def test_extract_paths_devnull_never_in_touched():
    # /dev/null must never leak into any path tuple.
    for diff in (NEW_FILE_DIFF, DELETED_FILE_DIFF):
        s = extract_change_summary(diff)
        assert "/dev/null" not in s.touched_paths
        assert "/dev/null" not in s.added_paths
        assert "/dev/null" not in s.deleted_paths


@pytest.mark.parametrize(
    "surface_path",
    ["dgm_loop", "diff_applier", "telos_gates", "dharma_kernel",
     "telosproof", "approval", "consent", "witness", "receipt",
     "rollback", "ledger"],
)
def test_net_removal_from_each_safety_surface_marker(surface_path):
    """A NET removal from a file matching each safety-surface marker trips the
    structural backstop -> net_removes_from_safety_surface=True, and the gate
    routes to a non-ALLOW verdict. Self-credentialed so the backstop is isolated.
    """
    path = f"dharma_swarm/x_{surface_path}_y.py"
    diff = _wrap(path, removed=["guard_a()", "guard_b()"], added=_CRED)
    s = extract_change_summary(diff)
    assert s.net_removes_from_safety_surface is True, surface_path
    result = telosproof_gate(diff)
    assert result.decision in (GateDecision.BLOCK, GateDecision.REVIEW)


def test_net_removal_pure_rename_does_not_trip_backstop():
    """A pure rename (equal add/remove) on a safety surface is NOT a net removal.

    Guards the `removed > substantive_added` comparison from being mutated into
    `>=` (which would over-fire) — the comment notes a rename must not trip it.
    This is the conservative-direction boundary the function documents.
    """
    diff = """\
diff --git a/dharma_swarm/dgm_loop.py b/dharma_swarm/dgm_loop.py
--- a/dharma_swarm/dgm_loop.py
+++ b/dharma_swarm/dgm_loop.py
@@ -1,2 +1,2 @@
-old_name()
+new_name()
"""
    s = extract_change_summary(diff)
    assert s.net_removes_from_safety_surface is False


def test_net_removal_comment_padding_does_not_offset():
    """Comment-only additions must NOT offset a guard removal on a safety surface.

    The attack-A shape: delete a guard, add credential comments to balance the
    line count. _is_substantive_code excludes comments, so removed(2) >
    substantive_added(0) still trips the backstop.
    """
    diff = """\
diff --git a/dharma_swarm/approval_gate.py b/dharma_swarm/approval_gate.py
--- a/dharma_swarm/approval_gate.py
+++ b/dharma_swarm/approval_gate.py
@@ -1,4 +1,4 @@
 keep()
-if not approve(plan):
-    raise PermissionError()
+# replay_command: pytest -q
+# rollback_plan: git revert HEAD
"""
    s = extract_change_summary(diff)
    assert s.net_removes_from_safety_surface is True
    result = telosproof_gate(diff)
    assert result.decision in (GateDecision.BLOCK, GateDecision.REVIEW)


@pytest.mark.parametrize(
    "code_line,is_code",
    [
        ("x = compute()", True),
        ("    return value", True),
        ("# a pure comment", False),
        ("    # indented comment", False),
        ("", False),
        ("   ", False),
        ('"""docstring"""', False),
        ("'''docstring'''", False),
        ("// c-style comment", False),
        ("* javadoc star", False),
    ],
)
def test_is_substantive_code_classification(code_line, is_code):
    """_is_substantive_code underpins the comment-padding defense; assert its
    classification directly so a mutated comment-prefix set is caught."""
    assert cs._is_substantive_code(code_line) is is_code


# ===========================================================================
# ast_safety danger-visitor hardening — each danger surface routes to REVIEW
# via the allowlist's pure-function-addition AST proof. These exercise the
# DangerVisitor over a NEW function body and assert REVIEW (never ALLOW), so a
# mutant that drops a danger name/import/elevation-fragment is caught.
# (The v0 gate may not catch a new-function body — that is the FN gap the
# allowlist AST layer closes — so we assert on the allowlist decision.)
# ===========================================================================

def _new_fn(body_lines):
    added = ["", "def harmful(x):"] + ["    " + ln for ln in body_lines]
    return _wrap("dharma_swarm/helpers.py", added=added)


@pytest.mark.parametrize(
    "body",
    [
        ["exec(x, {})"],
        ["return eval(x)"],
        ["return compile(x, '<s>', 'exec')"],
        ["m = __import__(x)"],
        ["setattr(ctx, 'autonomy_level', 3)"],
        ["delattr(ctx, 'guard')"],
        ["ctx.permissions = 'root'"],
        ["cfg.shadow_mode = False"],
        ["cfg.bypass_flag = True"],
        ["cfg.approval_required = False"],
        ["import os", "os.environ['DGC_AUTONOMY_LEVEL'] = '3'"],
        ["import os", "os.environ.pop('SAFE')"],
        ["open('o', 'w').write(x)"],
        ["open('o', mode='a')"],
        ["import io", "io.FileIO('o', 'w').write(b'd')"],
        ["from pathlib import Path", "Path('o').write_text(x)"],
        ["import os", "os.mkdir('d')"],
        ["import os", "os.remove('a')"],
        ["import os", "os.system('rm -rf /')"],
        ["import subprocess", "subprocess.run(cmd, shell=True)"],
        ["import subprocess", "subprocess.Popen(cmd)"],
        ["import os", "os.putenv('X', '1')"],
        ["import sqlite3", "sqlite3.connect('x.db')"],
        ["import sqlite3 as _db", "_db.connect('x.db')"],
        ["from sqlalchemy import create_engine", "create_engine('x')"],
        ["import redis", "redis.Redis().set('k', 'v')"],
        ["import redis as _r", "_r.Redis()"],
        ["import shelve", "shelve.open('s')"],
        ["import pickle", "pickle.dump(o, f)"],
        ["import shutil", "shutil.copy(a, b)"],
        ["import tempfile", "tempfile.mkstemp()"],
        ["import socket", "socket.socket()"],
        ["import multiprocessing", "multiprocessing.Process()"],
    ],
)
def test_ast_danger_body_reviews(body):
    """A NEW pure-function body doing real harm must REVIEW, never ALLOW."""
    body = body + ["return None"]
    diff = _new_fn(body)
    result = classify_operations(diff)
    assert result.decision is GateDecision.REVIEW, (
        f"AST FALSE-NEGATIVE: body {body!r} classified "
        f"{[op.primitive for op in result.allowed]}"
    )
    assert "add_pure_function" not in _allowed_prims(result)


def test_ast_unparseable_body_reviews():
    diff = _wrap(
        "dharma_swarm/helpers.py",
        added=["", "def broken(:", "    not valid @@@", "    return"],
    )
    assert classify_operations(diff).decision is GateDecision.REVIEW


def test_ast_clean_pure_function_still_allows():
    """Positive control: a genuinely pure new function must STILL ALLOW so the
    AST hardening did not over-correct into reviewing everything."""
    diff = _wrap(
        "dharma_swarm/helpers.py",
        added=["", "def clamp(x, lo, hi):", "    return max(lo, min(hi, x))"],
    )
    result = classify_operations(diff)
    assert result.decision is GateDecision.ALLOW, result.unknown
    assert "add_pure_function" in _allowed_prims(result)


def test_open_is_write_mode_direct():
    """Direct unit assertions on _open_is_write_mode so a mode-parsing mutant is
    caught even where a redundant path would otherwise mask it."""
    import ast
    def mode_of(src):
        call = ast.parse(src).body[0].value
        return astsafe._open_is_write_mode(call)
    assert mode_of("open('p')") is False           # no mode -> read-only
    assert mode_of("open('p', 'r')") is False       # explicit read
    assert mode_of("open('p', 'rb')") is False
    assert mode_of("open('p', 'w')") is True        # write
    assert mode_of("open('p', 'a')") is True        # append
    assert mode_of("open('p', 'x')") is True        # exclusive
    assert mode_of("open('p', 'r+')") is True       # update
    assert mode_of("open('p', mode='w')") is True
    assert mode_of("open('p', m)") is True           # non-literal -> conservative


# ===========================================================================
# REGRESSION — FIXED. An aliased `from os import environ as E; E['K'] = V`
# (and `from os import system as s; s(...)`) inside a NEW function was a real
# FALSE-NEGATIVE: the danger visitor only matched the literal imported name, so
# the alias escaped. ast_safety._DangerVisitor now tracks import aliases and
# resolves local names back to the imported identity (_aliases/_resolve), so the
# whole aliased-import danger class REVIEWs. This test locks the fix.
# ===========================================================================

def test_aliased_environ_mutation_reviews():
    diff = _wrap(
        "dharma_swarm/helpers.py",
        added=[
            "",
            "def tweak():",
            "    from os import environ as E",
            "    E['PATH'] = '/evil'",
            "    return None",
        ],
    )
    result = classify_operations(diff)
    # DESIRED (currently failing) behavior: an env mutation must REVIEW.
    assert result.decision is GateDecision.REVIEW, (
        "aliased os.environ mutation must not be ALLOWed; "
        f"got {[op.primitive for op in result.allowed]}"
    )
