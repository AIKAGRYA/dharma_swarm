"""Conservative static extraction of a self-modification's BODY-level shape.

``extract_change_summary`` parses a unified diff with regex / static
heuristics and produces a :class:`ChangeSummary` — a frozen, hashable record
of *what the patch literally touches and which dangerous markers it
adds or removes*. It makes NO claim about intent.

THE CARDINAL RULE (read before changing any heuristic in this file)
-------------------------------------------------------------------
False-positives are ACCEPTABLE: a perfectly safe patch may be flagged for
human review. False-negatives are FORBIDDEN: a dangerous patch must never be
reported as safe. Therefore, whenever a flag cannot be *confidently determined
safe*, it defaults to the DANGEROUS value.

Concretely:

* The four "disables_* / bypasses_* / raises_* / creates_*" danger flags are
  set ``True`` the moment a suggestive marker appears on EITHER a removed (``-``)
  line (e.g. a safety check being deleted) OR an added (``+``) line (e.g. a
  guard being set to a permissive value). We do not try to prove the marker is
  benign; we assume the worst.

* The two "has_*" credential flags (replay / rollback metadata) start ``False``
  and only flip to ``True`` on positive evidence. A patch with no rollback plan
  is therefore treated as lacking one (the conservative, review-triggering
  state), not silently assumed safe.

Every heuristic below carries an inline note describing its conservatism
direction so a future reader can audit the false-negative guarantee.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Frozen body-summary record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChangeSummary:
    """Immutable, hashable summary of a patch's body-level shape.

    Path fields are tuples (frozen-dataclass requires hashable fields). All
    boolean fields are conservative: danger flags default DANGEROUS-on-doubt,
    credential flags default to "absent" until positively proven present.
    """

    # --- touched-path inventory (body, not intent) ---
    touched_paths: tuple[str, ...] = ()
    added_paths: tuple[str, ...] = ()
    deleted_paths: tuple[str, ...] = ()

    # --- danger flags (True == dangerous; conservative on doubt) ---
    modifies_protected_files: bool = False
    disables_receipts: bool = False
    disables_rollback: bool = False
    bypasses_human_approval: bool = False
    raises_autonomy: bool = False
    disables_shadow_mode: bool = False
    creates_new_persistence: bool = False

    # --- credential flags (True == safety metadata present; absent on doubt) ---
    has_replay_command: bool = False
    has_rollback_plan: bool = False

    # --- structural backstop (attacks A/E) ---
    # True when the diff NET-REMOVES lines from a file on a safety surface
    # (path matches _SAFETY_SURFACE_PATH_MARKERS). Deny-by-default: forces the
    # gate to REVIEW regardless of vocabulary, catching synonym/rename bypass
    # that the closed positive-marker vocabularies cannot.
    net_removes_from_safety_surface: bool = False


# ---------------------------------------------------------------------------
# Regex toolkit for unified-diff parsing
# ---------------------------------------------------------------------------

# File headers in a unified diff. We read both the `diff --git a/x b/y` line
# and the `--- a/x` / `+++ b/y` pair, because real-world diffs (git, hg, plain)
# vary. Reading every form is conservative: missing a header would *under*-count
# touched files, so we union all of them.
_DIFF_GIT_RE = re.compile(r"^diff --git a/(?P<a>\S+) b/(?P<b>\S+)", re.MULTILINE)
_MINUS_HEADER_RE = re.compile(r"^--- (?:a/)?(?P<path>\S+)", re.MULTILINE)
_PLUS_HEADER_RE = re.compile(r"^\+\+\+ (?:b/)?(?P<path>\S+)", re.MULTILINE)
# new-file / deleted-file markers (git extended headers)
_NEW_FILE_RE = re.compile(r"^new file mode", re.MULTILINE)
_DELETED_FILE_RE = re.compile(r"^deleted file mode", re.MULTILINE)
# /dev/null sentinels (plain diffs use these instead of git extended headers)
_DEVNULL = "/dev/null"


def _norm(path: str) -> str:
    """Strip a/ b/ prefixes and normalise; never raise."""
    path = path.strip()
    if path.startswith("a/") or path.startswith("b/"):
        path = path[2:]
    return path


def _body_lines(diff_text: str) -> tuple[list[str], list[str]]:
    """Return (added_content_lines, removed_content_lines).

    Only real hunk-body lines are returned — header lines `+++`/`---` are
    excluded so they cannot pollute marker detection. Conservative direction:
    if in doubt about whether a line is a header, we treat `+++`/`---` (exactly
    those two prefixes) as headers and EVERYTHING ELSE starting with a single
    +/- as body. Missing a body line would risk a false-negative, so the net is
    cast wide.
    """
    added: list[str] = []
    removed: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue  # file headers, not content
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
    return added, removed


# ---------------------------------------------------------------------------
# Marker vocabularies (lowercased substring matches)
# ---------------------------------------------------------------------------
# Each vocabulary is intentionally BROAD. A broad vocabulary over-flags (more
# false-positives) which is the acceptable failure direction. A narrow
# vocabulary would risk missing a dangerous edit (false-negative) — forbidden.

# (2) receipt emission being disabled / removed
_RECEIPT_MARKERS = (
    "emit_receipt",
    "write_receipt",
    "receipt_emit",
    "log_receipt",
    "emit_witness",
    "write_witness",
    "witness_log",
    "record_receipt",
)
# permissive assignments that would silence receipts
_RECEIPT_DISABLE_ASSIGN = (
    "emit_receipts = false",
    "receipts_enabled = false",
    "emit_receipt = false",
    "enable_receipts = false",
    "skip_receipt",
    "no_receipt",
)

# (3) rollback being disabled / removed
_ROLLBACK_MARKERS = (
    ".rollback(",
    "def rollback",
    "rollback(",
    "restore_from_backup",
    "backup_paths",
    "create_backup",
)
_ROLLBACK_DISABLE_ASSIGN = (
    "rollback_enabled = false",
    "enable_rollback = false",
    "skip_rollback",
    "no_rollback",
    "disable_rollback",
    "rollback = none",
)

# (4) human approval being bypassed
_APPROVAL_MARKERS = (
    "require_human_approval",
    "human_approval",
    "needs_approval",
    "await_approval",
    "request_approval",
    "human_in_the_loop",
    "manual_review",
)
_APPROVAL_BYPASS_ASSIGN = (
    "require_human_approval = false",
    "human_approval = false",
    "needs_approval = false",
    "auto_approve = true",
    "skip_approval",
    "bypass_approval",
    "approval_required = false",
)

# (5) autonomy level being raised
_AUTONOMY_MARKERS = (
    "autonomy",
    "dgc_autonomy_level",
    "autonomy_level",
    "autonomylevel",
    # The live shadow logic in dgm_loop reads DGC_AUTONOMY_LEVEL; setting it to
    # >= 2 (with DHARMA_EVOLUTION_SHADOW='0') silently disables shadow mode even
    # though the line says nothing about "shadow". Treat the env name itself as
    # an autonomy marker so a numeric raise on it is caught.
    "dgc_autonomy",
)
# Bare 'level' alone is too broad, but a few var names commonly stand in for an
# autonomy level when the word 'autonomy' is renamed away. A numeric raise on
# any of these is caught by the dedicated numeric-raise detector below.
_AUTONOMY_LEVEL_VARNAMES = (
    "dgc_autonomy_level",
    "autonomy_level",
    "autonomylevel",
)
# Raising = added line that pushes autonomy UP. We treat ANY added line that
# mentions autonomy alongside an increase token as dangerous. Conservative: a
# benign autonomy *read* on an added line will false-positive, which is fine.
_AUTONOMY_RAISE_TOKENS = (
    "full",
    "aggressive",
    "= 2",
    "=2",
    ">= 2",
    "= 3",
    "=3",
    "+= 1",
    "+=1",
    "increase",
    "raise",
    "elevate",
    "unlock",
)

# (6) shadow mode being disabled
_SHADOW_MARKERS = (
    "shadow_mode",
    "dharma_evolution_shadow",
    "shadow",
)
_SHADOW_DISABLE_TOKENS = (
    "shadow_mode = false",
    "shadow_mode=false",
    "dharma_evolution_shadow",  # any edit to the env flag is suspicious
    "shadow = false",
    "shadow_mode = none",
    "disable_shadow",
    "no_shadow",
    'shadow", "0"',
    "shadow','0'",
    '= "0"',
)

# (7) new persistence substrate being created.
# NOTE: a BARE ``open(`` is intentionally NOT here — a read-only open is not a
# new persistence substrate and flagging every read produced unacceptable
# noise. Write-mode opens are matched separately by ``_OPEN_WRITE_RE`` below.
_PERSISTENCE_MARKERS = (
    "sqlite3.connect",
    "aiosqlite.connect",
    "create_engine(",
    "sessionmaker(",
    "psycopg2.connect",
    "redis.redis",
    "pathlib.path",
    ".write_text(",
    ".write_bytes(",
    "json.dump(",
    "pickle.dump(",
    "shelve.open(",
    "create table",
    "new_database",
    "new_db",
)
# Write-mode open() only: open(..., 'w'/'a'/'x'/'+') in any quote style. A
# read-only open (no mode, or 'r'/'rb') does NOT match — that was the noise
# source. The mode argument may be a second positional or a `mode=` kwarg.
_OPEN_WRITE_RE = re.compile(
    r"""open\s*\([^)]*?,\s*(?:mode\s*=\s*)?["'][rbt]*[wax+][wax+rbt]*["']""",
    re.IGNORECASE,
)
# persistence-file extensions appearing as NEW added files. The set is the
# dominant store formats; missing one is a false-negative (forbidden), so the
# net is cast wide across structured, append-log, columnar, and key-value
# on-disk formats.
_PERSISTENCE_NEW_FILE_SUFFIXES = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".jsonl",
    ".sql",
    # Dominant store formats the adversarial review found missing:
    ".json",
    ".ndjson",
    ".log",
    ".csv",
    ".parquet",
    ".pkl",
    ".dbm",
    ".lmdb",
    ".leveldb",
)

# (8) replay / rollback metadata present (CREDENTIAL — positive evidence only)
_REPLAY_MARKERS = (
    "replay_command",
    "replay:",
    "replay =",
    "replay=",
    '"replay"',
    "'replay'",
    "how_to_replay",
    "reproduce_command",
)
_ROLLBACK_PLAN_MARKERS = (
    "rollback_plan",
    "rollback:",
    "rollback_command",
    "how_to_rollback",
    '"rollback"',
    "'rollback'",
    "revert_command",
)

# ---------------------------------------------------------------------------
# Removed-line safety-primitive markers (attacks B + D)
# ---------------------------------------------------------------------------
# These detect the LOSS of a real safety mechanism whose removal carries none
# of the named-vocabulary markers above — e.g. a local-var backup writer or an
# inline witness write. Scanned ONLY on removed ('-') lines: their disappearance
# is the danger. Conservative: a removed line that merely *mentions* one of
# these idioms false-positives, which is acceptable.

# Backup / rollback writers expressed in plain code (no 'rollback' word):
_BACKUP_WRITER_MARKERS = (
    ".bak",
    ".copy2(",
    "copy2(",
    "copyfile(",
    "make_backup",
    "create_backup",
)
# Co-occurrence form: a '.bak'-style suffix builder plus a copy call across the
# removed hunk. Matched at the hunk level (not per-line) by
# ``_removes_backup_writer``.
_BACKUP_SUFFIX_MARKERS = (
    "with_suffix",
    ".bak",
    "+ '.bak'",
    '+ ".bak"',
)
_BACKUP_COPY_MARKERS = (
    "shutil.copy2",
    ".copy2(",
    "copy2(",
    "copyfile(",
)

# Receipt / witness / ledger WRITE sinks expressed as a generic write call.
# A removed line that writes via .write_text/.write_bytes AND references a
# witness/receipt/ledger surface is a receipt-emission removal regardless of
# whether it used one of the named _RECEIPT_MARKERS verbs.
_WRITE_SINK_MARKERS = (
    ".write_text(",
    ".write_bytes(",
    ".write(",
    ".append(",
    ".publish(",
    ".emit(",
    ".dump(",
)
_RECEIPT_SURFACE_MARKERS = (
    "witness",
    "receipt",
    "ledger",
    "audit",
    "provenance",
)

# ---------------------------------------------------------------------------
# Safety-surface path patterns (attacks A + E — deny-by-default backstop)
# ---------------------------------------------------------------------------
# Files whose modification touches the self-modification safety machinery, or
# whose NAME implies a safety role. A diff that NET-REMOVES lines from any of
# these is forced to REVIEW regardless of vocabulary — this is the structural
# backstop that catches synonym/rename bypass an enumeration never can.
# Matched on substring of the normalised path (case-insensitive).
_SAFETY_SURFACE_PATH_MARKERS = (
    "dgm_loop",
    "diff_applier",
    "telos_gates",
    "dharma_kernel",
    "telosproof",
    "approval",
    "consent",
    "witness",
    "receipt",
    "rollback",
    "ledger",
)


def _contains_any(haystack_lines: list[str], needles: tuple[str, ...]) -> bool:
    """True if any needle (lowercased substring) appears in any line."""
    for ln in haystack_lines:
        low = ln.lower()
        for n in needles:
            if n in low:
                return True
    return False


# ---------------------------------------------------------------------------
# Touched-path extraction
# ---------------------------------------------------------------------------

def _extract_paths(diff_text: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return (touched, added, deleted) path tuples.

    Conservative path handling:
      * touched   = union of every file referenced by any header form.
      * added     = files marked `new file mode` OR whose `---` side is /dev/null.
      * deleted   = files marked `deleted file mode` OR whose `+++` side is /dev/null.
    A file we cannot confidently classify as added/deleted still lands in
    `touched`, so it is never dropped from invariant (1)'s protected-file scan.
    """
    touched: set[str] = set()
    added: set[str] = set()
    deleted: set[str] = set()

    for m in _DIFF_GIT_RE.finditer(diff_text):
        touched.add(_norm(m.group("a")))
        touched.add(_norm(m.group("b")))

    # Walk per-file blocks so /dev/null sentinels can be attributed correctly.
    # We split on `diff --git` first; if there is no git header (plain diff) we
    # treat the whole text as one block.
    blocks = re.split(r"(?=^diff --git )", diff_text, flags=re.MULTILINE)
    if len(blocks) == 1 and not diff_text.lstrip().startswith("diff --git"):
        blocks = [diff_text]

    for block in blocks:
        minus = _MINUS_HEADER_RE.search(block)
        plus = _PLUS_HEADER_RE.search(block)
        minus_path = _norm(minus.group("path")) if minus else None
        plus_path = _norm(plus.group("path")) if plus else None

        for p in (minus_path, plus_path):
            if p and p != _DEVNULL:
                touched.add(p)

        is_new = bool(_NEW_FILE_RE.search(block)) or (minus_path == _DEVNULL)
        is_del = bool(_DELETED_FILE_RE.search(block)) or (plus_path == _DEVNULL)

        if is_new:
            target = plus_path if (plus_path and plus_path != _DEVNULL) else minus_path
            if target and target != _DEVNULL:
                added.add(target)
        if is_del:
            target = minus_path if (minus_path and minus_path != _DEVNULL) else plus_path
            if target and target != _DEVNULL:
                deleted.add(target)

    touched.discard(_DEVNULL)
    return (tuple(sorted(touched)), tuple(sorted(added)), tuple(sorted(deleted)))


# ---------------------------------------------------------------------------
# Public extraction entrypoint
# ---------------------------------------------------------------------------

def extract_change_summary(
    diff_text: str,
    metadata: Optional[dict[str, Any]] = None,
) -> ChangeSummary:
    """Parse *diff_text* into a conservative :class:`ChangeSummary`.

    Args:
        diff_text: A unified diff. May be empty.
        metadata: Optional out-of-band context. Recognised keys:
            ``replay_command`` / ``replay`` — positive evidence of a replay
            command (sets ``has_replay_command``); ``rollback_plan`` /
            ``rollback`` — positive evidence of a rollback plan (sets
            ``has_rollback_plan``). Metadata can only ever ADD positive
            credential evidence; it can never clear a danger flag, preserving
            the false-negative guarantee.

    Returns:
        A frozen :class:`ChangeSummary`. Note: protected-file detection
        (invariant 1) is computed in ``invariants.py`` against the live
        ``DGM_PROTECTED_FILES`` so the list is never duplicated; the
        ``modifies_protected_files`` flag here is a *body-level convenience
        mirror* that the invariant layer re-derives authoritatively.
    """
    diff_text = diff_text or ""
    metadata = metadata or {}

    touched, added, deleted = _extract_paths(diff_text)
    added_lines, removed_lines = _body_lines(diff_text)
    # For "removal of a safety mechanism" detection we scan removed lines; for
    # "addition of a permissive setting" we scan added lines. Several checks
    # scan both, accepting false-positives.
    all_body = added_lines + removed_lines

    # --- (1) protected files — body-level convenience mirror -------------
    # Authoritative check lives in invariants.py via _is_protected_dgm_target.
    # Here we conservatively flag if any touched path's basename *looks*
    # protected by reusing the live frozenset, imported lazily to avoid any
    # import cycle and to keep this module heuristic-only.
    modifies_protected = _touches_protected(touched)

    # --- (2) receipts disabled -------------------------------------------
    # Dangerous if a receipt-emitting marker is REMOVED, or a permissive
    # "no receipts" assignment is ADDED. Both directions -> True.
    disables_receipts = (
        _contains_any(removed_lines, _RECEIPT_MARKERS)
        or _contains_any(added_lines, _RECEIPT_DISABLE_ASSIGN)
        or _contains_any(removed_lines, _RECEIPT_DISABLE_ASSIGN)
    )

    # --- (2 cont.) receipt/witness WRITE removal (attack D) --------------
    # A removed line that writes to a witness/receipt/ledger surface via a
    # generic write sink (.write_text/.write_bytes/.publish/...) is a receipt-
    # emission removal even if it used no named _RECEIPT_MARKERS verb.
    if _removed_receipt_write(removed_lines):
        disables_receipts = True

    # --- (3) rollback disabled -------------------------------------------
    disables_rollback = (
        _contains_any(removed_lines, _ROLLBACK_MARKERS)
        or _contains_any(added_lines, _ROLLBACK_DISABLE_ASSIGN)
        or _contains_any(removed_lines, _ROLLBACK_DISABLE_ASSIGN)
    )
    # (3 cont.) real backup/rollback WRITER removal (attack B): a removed hunk
    # that drops a local-var backup writer (with_suffix + shutil.copy2, or a
    # '.bak'/'.copy2(' idiom) carries none of the named rollback markers.
    if _removes_backup_writer(removed_lines):
        disables_rollback = True

    # --- (4) human approval bypassed -------------------------------------
    bypasses_approval = (
        _contains_any(removed_lines, _APPROVAL_MARKERS)
        or _contains_any(added_lines, _APPROVAL_BYPASS_ASSIGN)
        or _contains_any(removed_lines, _APPROVAL_BYPASS_ASSIGN)
    )

    # --- (5) autonomy raised ---------------------------------------------
    # An ADDED line mentioning autonomy together with an increase token is
    # treated as a raise. We only look at added lines for the raise (a removed
    # autonomy line is not itself a raise), but the increase-token net is broad.
    # Plus (attack F): an added line that SETS an autonomy/level env var or var
    # to a literal int >= 2 — including the DGC_AUTONOMY_LEVEL env form that
    # carries no English 'autonomy' word in some rename variants.
    raises_autonomy = (
        _added_line_raises_autonomy(added_lines)
        or _added_line_numeric_autonomy_raise(added_lines)
    )

    # --- (6) shadow mode disabled ----------------------------------------
    # Any ADDED line that turns shadow off, or any edit (added/removed) that
    # touches the DHARMA_EVOLUTION_SHADOW env flag, is dangerous.
    disables_shadow = (
        _contains_any(added_lines, _SHADOW_DISABLE_TOKENS)
        or _contains_any(all_body, ("dharma_evolution_shadow",))
        and _contains_any(all_body, _SHADOW_MARKERS)
    )
    # Stronger, simpler net: any added line that sets a shadow marker to a
    # falsey/zero value. (Kept separate so the intent is auditable.)
    if _added_shadow_disable(added_lines):
        disables_shadow = True

    # --- (7) new persistence substrate -----------------------------------
    creates_persistence = (
        _contains_any(added_lines, _PERSISTENCE_MARKERS)
        or _added_line_opens_for_write(added_lines)
        or _added_file_is_persistence(added)
    )

    # --- structural backstop: net-removal from a safety surface (A/E) ----
    net_removes_safety = _net_removes_from_safety_surface(diff_text)

    # --- (8a) replay command present (CREDENTIAL) ------------------------
    has_replay = (
        _contains_any(added_lines, _REPLAY_MARKERS)
        or _metadata_truthy(metadata, ("replay_command", "replay"))
    )

    # --- (8b) rollback plan present (CREDENTIAL) -------------------------
    has_rollback_plan = (
        _contains_any(added_lines, _ROLLBACK_PLAN_MARKERS)
        or _metadata_truthy(metadata, ("rollback_plan", "rollback"))
    )

    return ChangeSummary(
        touched_paths=touched,
        added_paths=added,
        deleted_paths=deleted,
        modifies_protected_files=modifies_protected,
        disables_receipts=disables_receipts,
        disables_rollback=disables_rollback,
        bypasses_human_approval=bypasses_approval,
        raises_autonomy=raises_autonomy,
        disables_shadow_mode=disables_shadow,
        creates_new_persistence=creates_persistence,
        has_replay_command=has_replay,
        has_rollback_plan=has_rollback_plan,
        net_removes_from_safety_surface=net_removes_safety,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _touches_protected(touched: tuple[str, ...]) -> bool:
    """Body-level mirror of invariant (1). Reuses the LIVE frozenset.

    Imported lazily from dgm_loop so the protected list is never duplicated
    here. Conservative: matches on basename, so a touch of any file whose name
    collides with a protected name flags True (acceptable false-positive).
    """
    from dharma_swarm.dgm_loop import _is_protected_dgm_target

    for p in touched:
        try:
            if _is_protected_dgm_target(p):
                return True
        except Exception:
            # If classification fails for a weird path, treat as suspicious.
            # False-negative is forbidden, so an unparseable path -> flag.
            return True
    return False


def _added_line_raises_autonomy(added_lines: list[str]) -> bool:
    """True if an added line mentions autonomy alongside an increase token."""
    for ln in added_lines:
        low = ln.lower()
        if any(m in low for m in _AUTONOMY_MARKERS):
            if any(tok in low for tok in _AUTONOMY_RAISE_TOKENS):
                return True
    return False


def _added_shadow_disable(added_lines: list[str]) -> bool:
    """True if an added line sets a shadow marker to a falsey/zero value."""
    for ln in added_lines:
        low = ln.lower()
        if "shadow" not in low and "dharma_evolution_shadow" not in low:
            continue
        # Any added line touching shadow that also contains a disable token.
        if any(tok in low for tok in ("false", "= 0", "=0", '"0"', "'0'", "none", "disable", "off")):
            return True
    return False


def _added_file_is_persistence(added_paths: tuple[str, ...]) -> bool:
    """True if a newly added file has a persistence-store extension."""
    for p in added_paths:
        suffix = PurePosixPath(p).suffix.lower()
        if suffix in _PERSISTENCE_NEW_FILE_SUFFIXES:
            return True
    return False


def _metadata_truthy(metadata: dict[str, Any], keys: tuple[str, ...]) -> bool:
    """True if any of *keys* in metadata holds a truthy value."""
    for k in keys:
        v = metadata.get(k)
        if isinstance(v, str):
            if v.strip():
                return True
        elif v:
            return True
    return False


# --- attack B: backup/rollback WRITER removal on removed lines -------------

def _removes_backup_writer(removed_lines: list[str]) -> bool:
    """True if removed lines drop a backup/rollback writer.

    Two forms (conservative — either trips):
      * a single removed line containing a backup idiom ('.bak', '.copy2(',
        copyfile(...), make/create_backup);
      * the co-occurrence across the removed hunk of a '.bak'-style suffix
        builder AND a copy call (the canonical
        ``backup = target.with_suffix(...+'.bak'); shutil.copy2(...)`` pattern).
    """
    if _contains_any(removed_lines, _BACKUP_WRITER_MARKERS):
        return True
    has_suffix = _contains_any(removed_lines, _BACKUP_SUFFIX_MARKERS)
    has_copy = _contains_any(removed_lines, _BACKUP_COPY_MARKERS)
    return has_suffix and has_copy


# --- attack D: receipt/witness WRITE removal on removed lines --------------

def _removed_receipt_write(removed_lines: list[str]) -> bool:
    """True if a removed line writes to a witness/receipt/ledger surface.

    Matches a generic write sink (.write_text/.write_bytes/.publish/.emit/...)
    on the SAME removed line as a witness/receipt/ledger/audit/provenance
    reference. Catches deletion of an inline witness write that used no named
    receipt verb.
    """
    for ln in removed_lines:
        low = ln.lower()
        if any(sink in low for sink in _WRITE_SINK_MARKERS) and any(
            surface in low for surface in _RECEIPT_SURFACE_MARKERS
        ):
            return True
    return False


# --- attack F: numeric autonomy/level raise (env or var) ------------------

# An added line that assigns an autonomy/level env var or variable to an int
# literal >= 2. Covers os.environ['DGC_AUTONOMY_LEVEL'] = '2',
# autonomy_level = 3, DGC_AUTONOMY_LEVEL=2, etc. The value may be quoted (env
# string) or bare (int). 0 and 1 are NOT raises.
_NUMERIC_AUTONOMY_RE = re.compile(
    r"""(dgc_autonomy_level|autonomy_level|autonomylevel|dgc_autonomy)\b"""
    r"""['"\]]*\s*[:=]\s*['"]?\s*([2-9]|\d{2,})\b""",
    re.IGNORECASE,
)


def _added_line_numeric_autonomy_raise(added_lines: list[str]) -> bool:
    """True if an added line sets an autonomy/level name to a literal int >= 2."""
    for ln in added_lines:
        if _NUMERIC_AUTONOMY_RE.search(ln):
            return True
    return False


# --- attack C/noise: write-mode open() only -------------------------------

def _added_line_opens_for_write(added_lines: list[str]) -> bool:
    """True if an added line opens a file in a write/append/exclusive mode.

    Read-only opens (no mode arg, or 'r'/'rb') do NOT match — that narrowing is
    the noise reduction the review asked for.
    """
    for ln in added_lines:
        if _OPEN_WRITE_RE.search(ln):
            return True
    return False


# --- attacks A/E: net-removal from a safety surface (structural backstop) --

def _net_removes_from_safety_surface(diff_text: str) -> bool:
    """True if the diff NET-REMOVES body lines from any safety-surface file.

    Walks per-file blocks. For each file whose normalised path matches a
    safety-surface marker, counts added vs removed body lines; if removed >
    added for that file, the diff has net-removed safety-relevant code and the
    gate must REVIEW regardless of vocabulary. This is the deny-by-default
    backstop that catches synonym/rename bypass enumeration cannot.

    A pure rename (equal add/remove) does NOT trip this on its own — only a NET
    removal does — keeping false-positive noise bounded while still catching the
    "delete a guard, add a comment" shape (removes > adds).
    """
    blocks = re.split(r"(?=^diff --git )", diff_text, flags=re.MULTILINE)
    if len(blocks) == 1 and not diff_text.lstrip().startswith("diff --git"):
        blocks = [diff_text]

    for block in blocks:
        # Determine the file path(s) this block touches.
        paths: set[str] = set()
        gm = _DIFF_GIT_RE.search(block)
        if gm:
            paths.add(_norm(gm.group("a")))
            paths.add(_norm(gm.group("b")))
        minus = _MINUS_HEADER_RE.search(block)
        plus = _PLUS_HEADER_RE.search(block)
        if minus:
            p = _norm(minus.group("path"))
            if p != _DEVNULL:
                paths.add(p)
        if plus:
            p = _norm(plus.group("path"))
            if p != _DEVNULL:
                paths.add(p)

        if not _path_is_safety_surface(paths):
            continue

        added, removed = _body_lines(block)
        # Comment-only / blank added lines do NOT offset removed code: a
        # proposer can always pad a guard deletion with credential-comment lines
        # (the attack-A shape) to make removes == adds. Count only *substantive*
        # added lines toward the offset so a balanced "delete guard, add
        # comment" replace still registers as a net removal.
        substantive_added = sum(1 for ln in added if _is_substantive_code(ln))
        if len(removed) > substantive_added:
            return True
    return False


def _is_substantive_code(line: str) -> bool:
    """True if a body line is real code, not blank or a pure comment.

    Used so credential-comment padding cannot offset a guard removal on a
    safety surface. Conservative: anything that is not clearly blank/comment is
    treated as substantive (counts toward the offset), which only makes the
    backstop FIRE LESS — but a removed guard with comment-only additions always
    trips it.
    """
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("#", "//", "/*", "*", '"""', "'''")):
        return False
    return True


def _path_is_safety_surface(paths: set[str]) -> bool:
    """True if any path matches a safety-surface marker (case-insensitive)."""
    for p in paths:
        low = p.lower()
        if any(marker in low for marker in _SAFETY_SURFACE_PATH_MARKERS):
            return True
    return False
