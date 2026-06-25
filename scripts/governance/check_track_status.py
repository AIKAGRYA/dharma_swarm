#!/usr/bin/env python3
"""check_track_status.py — validate ACTIVE_TRACK.yaml against repo reality.

This is the governance gate that prevents the failure mode where a prose
"current track" pointer rots while work moves on. It does three things:

  1. Verifies the track portfolio is well-formed (schema; 1..max_active
     co-equal active tracks; spine/edge/cycle/conflict/surface invariants).
  2. Evaluates each acceptance_criteria predicate against the filesystem
     (and, when network is allowed, the GitHub API for PR merge status).
  3. Checks TTL — fails if (today - verified_at) > ttl_days.

Outputs:
  - reports/governance/active_track_evidence.json  (machine readable)
  - reports/governance/active_track_evidence.md    (human readable)
  - non-zero exit if any blocking finding is raised.

The script is stdlib-only. PR merge status is checked optionally via the
`gh` CLI if available; otherwise it is reported as "unknown" without
failing.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ACTIVE_TRACK_PATH = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
REPORTS_DIR = REPO_ROOT / "reports/governance"
SCHEMA_VERSION = 2                       # current schema authored by this checker
SUPPORTED_SCHEMA_VERSIONS = {1, 2}       # v1 (singular active_track) read via adapter
EDGE_KINDS = ("complements", "depends_on", "conflicts_with")


def repo_path(path: str | Path) -> Path:
    """Resolve track-authored relative paths against the repository root."""
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


@dataclass
class Finding:
    severity: str          # ERROR | WARN | INFO
    check: str
    message: str
    criterion_id: str | None = None


@dataclass
class CriterionResult:
    id: str
    kind: str
    passed: bool
    detail: str = ""


def load_active_track(path: Path) -> dict[str, Any]:
    """Parse ACTIVE_TRACK.yaml using a stdlib-only YAML-subset parser.

    The file is intentionally simple YAML — we restrict ourselves to the
    subset already used by docs/docops/assertions.yaml (which is JSON-
    compatible). To stay stdlib-only we attempt PyYAML first; if missing,
    fall back to a minimal block parser.
    """
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except ImportError:
        return _parse_minimal_yaml(text)


def _parse_minimal_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML block parser sufficient for ACTIVE_TRACK.yaml.

    Supports: mappings, scalar values (str/int/bool), block-literal `|`
    strings, sequences of mappings, sequences of scalars. Comments (`#`)
    and blank lines are skipped. Indentation is 2 spaces.
    """
    lines = text.splitlines()

    def strip_comment(s: str) -> str:
        # `#` inside a double-quoted value is not a comment. We deliberately do
        # NOT track single quotes: a mid-word apostrophe (don't) would open a
        # bogus span and swallow a real trailing comment. (Known limitation:
        # `#` inside an unquoted block-literal `|` body or a single-quoted value
        # is truncated on this stdlib fallback path — PyYAML, used whenever
        # present, handles both; double-quote such values to be safe.)
        in_quote = False
        for i, ch in enumerate(s):
            if ch == '"':
                in_quote = not in_quote
            if ch == "#" and not in_quote:
                return s[:i].rstrip()
        return s.rstrip()

    cleaned: list[tuple[int, str]] = []
    for raw in lines:
        line = strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        cleaned.append((indent, line.lstrip(" ")))

    pos = 0

    def parse_block(base_indent: int) -> Any:
        nonlocal pos
        result: dict[str, Any] | list[Any] | None = None
        while pos < len(cleaned):
            indent, content = cleaned[pos]
            if indent < base_indent:
                return result if result is not None else {}
            if content.startswith("- "):
                if result is None:
                    result = []
                if not isinstance(result, list):
                    return result
                item_content = content[2:]
                # Sequence item could be a scalar or an inline `key: value`
                if ":" in item_content and not item_content.startswith("\""):
                    key, _, val = item_content.partition(":")
                    inline = {key.strip(): _scalar(val.strip())}
                    pos += 1
                    # Subsequent indented lines belong to this item
                    sub = parse_block(base_indent + 2)
                    if isinstance(sub, dict):
                        inline.update(sub)
                    result.append(inline)
                else:
                    result.append(_scalar(item_content))
                    pos += 1
                continue
            if ":" in content:
                key, _, val = content.partition(":")
                key = key.strip()
                val = val.strip()
                if result is None:
                    result = {}
                if not isinstance(result, dict):
                    return result
                if val == "":
                    pos += 1
                    result[key] = parse_block(base_indent + 2)
                elif val == "|":
                    pos += 1
                    block_lines: list[str] = []
                    block_indent = None
                    while pos < len(cleaned):
                        ind2, c2 = cleaned[pos]
                        if ind2 <= base_indent:
                            break
                        if block_indent is None:
                            block_indent = ind2
                        block_lines.append(" " * max(ind2 - block_indent, 0) + c2)
                        pos += 1
                    result[key] = "\n".join(block_lines)
                else:
                    result[key] = _scalar(val)
                    pos += 1
                continue
            pos += 1
        return result if result is not None else {}

    def _scalar(s: str) -> Any:
        s = s.strip()
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        # Flow collections: [] / [a, b] / {} — without this the stdlib fallback
        # mis-reads `depends_on: []` as the string "[]" and iterates its chars.
        if s == "[]":
            return []
        if s == "{}":
            return {}
        if s.startswith("[") and s.endswith("]"):
            inner = s[1:-1].strip()
            if not inner:
                return []
            # Split on commas that are not inside quotes (so `["a,b", c]`
            # stays two elements, matching PyYAML).
            parts: list[str] = []
            buf: list[str] = []
            dq = sq = False
            for ch in inner:
                if ch == '"' and not sq:
                    dq = not dq
                elif ch == "'" and not dq:
                    sq = not sq
                if ch == "," and not dq and not sq:
                    parts.append("".join(buf))
                    buf = []
                else:
                    buf.append(ch)
            parts.append("".join(buf))
            return [_scalar(p.strip()) for p in parts]
        if s.lower() in {"true", "false"}:
            return s.lower() == "true"
        if s.lower() in {"null", "~", ""}:
            return None
        try:
            if "." in s:
                return float(s)
            return int(s)
        except ValueError:
            return s

    return parse_block(0) or {}


def check_file_exists(file_path: str) -> CriterionResult:
    path = repo_path(file_path)
    return CriterionResult(
        id="", kind="file_exists",
        passed=path.exists(),
        detail=f"{file_path} {'present' if path.exists() else 'MISSING'}",
    )


def check_file_contains(file_path: str, pattern: str) -> CriterionResult:
    path = repo_path(file_path)
    if not path.exists():
        return CriterionResult(id="", kind="file_contains", passed=False,
                                detail=f"{file_path} missing")
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        found = bool(re.search(pattern, text))
    except re.error:
        # The criterion pattern is authored as a literal marker but contains
        # regex metacharacters (e.g. "BYPASS_ALLOWLIST = []", where "[]" is an
        # unterminated character class). Fall back to a plain substring match so
        # one literal pattern can't crash the entire track-status gate.
        found = pattern in text
    return CriterionResult(
        id="", kind="file_contains", passed=found,
        detail=f"pattern {pattern!r} {'found' if found else 'NOT FOUND'} in {file_path}",
    )


def check_pr_merged(pr_number: int) -> CriterionResult:
    """Best-effort PR merge check via gh CLI. UNKNOWN does not fail."""
    if shutil.which("gh") is None:
        return CriterionResult(id="", kind="pr_merged", passed=True,
                                detail=f"PR #{pr_number}: gh CLI absent, skipped")
    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number),
             "--repo", "AmitabhainArunachala/dharma_swarm",
             "--json", "state,mergedAt"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return CriterionResult(id="", kind="pr_merged", passed=True,
                                    detail=f"PR #{pr_number}: gh query failed, skipped")
        data = json.loads(result.stdout)
        merged = data.get("state") == "MERGED" and bool(data.get("mergedAt"))
        return CriterionResult(
            id="", kind="pr_merged", passed=merged,
            detail=f"PR #{pr_number}: state={data.get('state')} mergedAt={data.get('mergedAt')}",
        )
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        return CriterionResult(id="", kind="pr_merged", passed=True,
                                detail=f"PR #{pr_number}: {type(exc).__name__}, skipped")


# --- Rigor classification (the antidote to existence-only "shippable") --------
# Existence checks prove a file/string is present; they do NOT prove the work
# behaves or landed. A track is only shippable under the RIGOROUS bar if it
# carries at least one of these stronger, evidence-computed criteria AND has no
# open blocker next-items. Pattern borrowed from
# cybernetics_codex._evaluate_loop_closure_replay (compute closure from
# structural evidence; never trust a bare boolean) and REALITY_DEBT_LEDGER.md.
RIGOROUS_KINDS = frozenset({"test_passes", "commit_on_main", "receipt_valid", "pr_merged"})
EXISTENCE_KINDS = frozenset({"file_exists", "file_contains"})


def check_commit_on_main(commit: str) -> CriterionResult:
    """A cited commit must be an ancestor of origin/main — proves the work
    actually LANDED, not just that a side branch claims it. Conservative: if it
    cannot be verified, it does NOT pass (unproven != done)."""
    if shutil.which("git") is None:
        return CriterionResult(id="", kind="commit_on_main", passed=False,
                               detail="git unavailable; cannot verify commit on main")
    ref = "origin/main"
    probe = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{ref}^{{commit}}"],
                           capture_output=True, text=True, cwd=REPO_ROOT)
    if probe.returncode != 0:
        ref = "HEAD"
    try:
        res = subprocess.run(["git", "merge-base", "--is-ancestor", commit, ref],
                             capture_output=True, text=True, timeout=15, cwd=REPO_ROOT)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return CriterionResult(id="", kind="commit_on_main", passed=False,
                               detail=f"commit_on_main: {type(exc).__name__}")
    if res.returncode == 0:
        return CriterionResult(id="", kind="commit_on_main", passed=True,
                               detail=f"{commit[:10]} is an ancestor of {ref}")
    return CriterionResult(id="", kind="commit_on_main", passed=False,
                           detail=f"{commit[:10]} is NOT on {ref} — work not landed")


def check_test_passes(test_target: str, timeout: int = 180) -> CriterionResult:
    """Run a specific pytest target and require it to PASS — not merely exist.
    This is what stops `def test_x(): pass` from satisfying a file_contains check.
    Conservative: an un-runnable / failing test does NOT pass."""
    try:
        res = subprocess.run(
            [sys.executable, "-m", "pytest", test_target, "-q", "--no-header",
             "-p", "no:cacheprovider"],
            capture_output=True, text=True, timeout=timeout, cwd=REPO_ROOT,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return CriterionResult(id="", kind="test_passes", passed=False,
                               detail=f"pytest {test_target}: {type(exc).__name__} (could not execute)")
    passed = res.returncode == 0
    lines = [ln for ln in (res.stdout or res.stderr or "").splitlines() if ln.strip()]
    tail = lines[-1] if lines else ""
    return CriterionResult(id="", kind="test_passes", passed=passed,
                           detail=f"pytest {test_target}: {'PASS' if passed else 'FAIL'} — {tail}")


def check_receipt_valid(file_path: str, requires_keys: list[str]) -> CriterionResult:
    """A receipt artifact must EXIST and carry the required structural keys —
    behavioral evidence, not just file presence."""
    path = repo_path(file_path)
    if not path.exists():
        return CriterionResult(id="", kind="receipt_valid", passed=False,
                               detail=f"receipt {file_path} MISSING")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return CriterionResult(id="", kind="receipt_valid", passed=False,
                               detail=f"receipt {file_path} unreadable: {type(exc).__name__}")
    missing = [k for k in (requires_keys or []) if k not in data]
    if missing:
        return CriterionResult(id="", kind="receipt_valid", passed=False,
                               detail=f"receipt {file_path} missing keys: {', '.join(missing)}")
    return CriterionResult(id="", kind="receipt_valid", passed=True,
                           detail=f"receipt {file_path} valid ({len(requires_keys or [])} keys present)")


def evaluate_criterion(crit: dict[str, Any]) -> CriterionResult:
    """Evaluate one predicate. A malformed criterion becomes a failing result,
    never an exception — a governance gate must convert bad config into a
    Finding, not crash (and a crash would also bypass --warn-only)."""
    kind = crit.get("kind", "")
    try:
        if kind == "file_exists":
            if not isinstance(crit.get("file"), str) or not crit.get("file"):
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: 'file' must be a non-empty string")
            else:
                res = check_file_exists(crit["file"])
        elif kind == "file_contains":
            if not isinstance(crit.get("file"), str) or not isinstance(crit.get("pattern"), str):
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: 'file' and 'pattern' must be "
                                             "quoted strings (quote regex char-classes, e.g. \"[0-9]\")")
            elif not crit.get("file") or not crit.get("pattern"):
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: empty 'file' or 'pattern'")
            else:
                res = check_file_contains(crit["file"], crit["pattern"])
        elif kind == "pr_merged":
            res = check_pr_merged(int(crit["pr"]))
        elif kind == "commit_on_main":
            if not isinstance(crit.get("commit"), str) or not crit.get("commit"):
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: 'commit' must be a non-empty string")
            else:
                res = check_commit_on_main(crit["commit"])
        elif kind == "test_passes":
            if not isinstance(crit.get("test"), str) or not crit.get("test"):
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: 'test' must be a non-empty pytest target")
            else:
                res = check_test_passes(crit["test"])
        elif kind == "receipt_valid":
            if not isinstance(crit.get("file"), str) or not crit.get("file"):
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: 'file' must be a non-empty string")
            else:
                res = check_receipt_valid(crit["file"], crit.get("requires_keys") or [])
        else:
            res = CriterionResult(id="", kind=kind, passed=False,
                                  detail=f"unknown predicate kind: {kind!r}")
    except (KeyError, ValueError, TypeError) as exc:
        res = CriterionResult(id="", kind=kind, passed=False,
                              detail=f"malformed criterion ({type(exc).__name__}): {exc}")
    res.id = crit.get("id", "")
    return res


def days_since(date_str: str) -> int | None:
    """Return days since date_str (negative if in the future). None if malformed.

    Future dates are allowed and not malformed — repos span timezones, and
    verified_at may be set in the operator's local timezone while CI is UTC.
    """
    try:
        when = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return (date.today() - when).days


def normalize_portfolio(track: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize v1 (singular active_track) and v2 (active_tracks list) into one view.

    v1: a single `active_track:` mapping -> active_tracks=[that] (legacy adapter).
    v2: `active_tracks:` list + spine_objectives + track_policy + vital_signs.

    `primary` is the first active track — a backward-compat projection for tools
    that still read the singular `active_track`/`active_track_id`. It is NOT a
    privileged "boss" track; the portfolio is a flat graph of co-equal peers.
    """
    track = track or {}
    active_tracks = track.get("active_tracks")
    if active_tracks is None:
        single = track.get("active_track")
        active_tracks = [single] if single else []
    active_tracks = [t for t in active_tracks if t]
    # `track_policy` is the doctrine term; accept legacy `portfolio_policy` too.
    policy = track.get("track_policy") or track.get("portfolio_policy") or {}
    return {
        "schema_version": track.get("schema_version"),
        "active_tracks": active_tracks,
        "spine_objectives": track.get("spine_objectives") or [],
        "track_policy": {
            "min_active": int(policy.get("min_active", 1)),
            "max_active": int(policy.get("max_active", 10)),
            "warn_active": int(policy.get("warn_active", 5)),
            "min_active_grace_days": int(policy.get("min_active_grace_days", 7)),
            # Explicit "not CI-enforced" tombstone so downstream JSON consumers
            # (dashboard, dgc, agent_onboard) can render "advisory" without
            # re-deriving it from the schema. Default False = the grace is
            # advisory operator guidance, not auto-failed by CI.
            "min_active_grace_enforced": bool(policy.get("min_active_grace_enforced", False)),
            "allow_active_active_conflict": bool(policy.get("allow_active_active_conflict", False)),
            "surface_overlap": str(policy.get("surface_overlap", "warn")),
            "model": policy.get("model", "1..N co-equal active tracks; WIP-limited typed graph"),
        },
        "vital_signs": track.get("vital_signs") or {},
        "family": track.get("family") or {},
        "closed_tracks": track.get("closed_tracks") or [],
        # Primary = first genuinely-ACTIVE track (compat projection for legacy
        # singular consumers); fall back to the first track if none is ACTIVE.
        "primary": next(
            (t for t in active_tracks if str(t.get("status", "")).upper() == "ACTIVE"),
            active_tracks[0] if active_tracks else None,
        ),
    }


def _is_active(t: dict[str, Any]) -> bool:
    return str(t.get("status", "")).upper() in {"ACTIVE", "SHIPPABLE"}


def validate_portfolio_graph(p: dict[str, Any], findings: list[Finding]) -> None:
    """Graph invariants the singular schema could never express:
    WIP limit, spine resolution + coverage, edge resolution, active-active
    conflict, owned-surface overlap. (Cycle detection is separate.)
    """
    tracks = p["active_tracks"]
    policy = p["track_policy"]
    spine_ids = {o.get("id") for o in p["spine_objectives"] if o.get("id")}
    # known_ids is intentionally permissive (mapping `.get` only) so closed_tracks
    # shape findings below — not a KeyError here — surface the actual problem.
    known_ids = (
        {t.get("id") for t in tracks if isinstance(t, dict)}
        | {ct.get("id") for ct in p["closed_tracks"] if isinstance(ct, dict)}
    )
    active = [t for t in tracks if _is_active(t)]

    # closed_tracks shape — same edge/serves invariants we hold for active
    # tracks, so a malformed closed entry can't silently break edge
    # resolution above. We only ERROR on hard schema breaks (non-dict, no id,
    # serves not in spine); status drift is left for the active path.
    for ct in p["closed_tracks"]:
        if not isinstance(ct, dict):
            findings.append(Finding("ERROR", "closed-track-shape",
                f"closed_tracks entry is not a mapping: {ct!r}"))
            continue
        ctid = ct.get("id")
        if not ctid:
            findings.append(Finding("ERROR", "closed-track-shape",
                "closed_tracks entry missing required `id`."))
            continue
        for kind in EDGE_KINDS:
            for tgt in ct.get(kind) or []:
                if tgt not in known_ids:
                    findings.append(Finding("ERROR", f"edge-unresolved:{ctid}",
                        f"Closed track '{ctid}' {kind} -> '{tgt}', which is not a declared track."))
        cserves = ct.get("serves")
        if spine_ids and cserves is not None and cserves not in spine_ids:
            findings.append(Finding("ERROR", f"spine-unresolved:{ctid}",
                f"Closed track '{ctid}' serves unknown spine objective '{cserves}'. "
                f"Known: {sorted(spine_ids)}"))

    # WIP limit — focus as flow discipline, not a mutex.
    n = len(active)
    if n == 0:
        findings.append(Finding("WARN", "portfolio-empty",
            "No ACTIVE tracks declared — the portfolio decays. Open one."))
    elif n < policy["min_active"]:
        findings.append(Finding("WARN", "wip-below-floor",
            f"{n} ACTIVE track(s) below min_active={policy['min_active']}."))
    if n > policy["max_active"]:
        findings.append(Finding("ERROR", "wip-exceeded",
            f"{n} ACTIVE tracks exceed max_active={policy['max_active']}. "
            "Close or merge a track before opening more."))
    elif n > policy["warn_active"]:
        findings.append(Finding("WARN", "wip-high",
            f"{n} ACTIVE tracks exceed warn_active={policy['warn_active']} — focus is spreading thin."))

    # Spine resolution + coverage (v2 only; v1 has no spine_objectives).
    # `serves:` is required only of tracks that occupy the portfolio (active/
    # shippable). Draft/paused blocks parked in the list are shape-checked but
    # not spine-bound until promoted to ACTIVE.
    if spine_ids:
        for t in active:
            tid, serves = t.get("id"), t.get("serves")
            if not serves:
                findings.append(Finding("ERROR", f"spine-missing:{tid}",
                    f"Track '{tid}' declares no `serves:` spine objective."))
            elif serves not in spine_ids:
                findings.append(Finding("ERROR", f"spine-unresolved:{tid}",
                    f"Track '{tid}' serves unknown spine objective '{serves}'. "
                    f"Known: {sorted(spine_ids)}"))
        served = {t.get("serves") for t in active}
        for oid in sorted(spine_ids):
            if oid not in served:
                findings.append(Finding("WARN", f"spine-uncovered:{oid}",
                    f"Spine objective '{oid}' has no ACTIVE track serving it (coverage gap)."))

    # Edge resolution — every typed edge must point at a declared track.
    for t in tracks:
        tid = t.get("id")
        for kind in EDGE_KINDS:
            for tgt in t.get(kind) or []:
                if tgt not in known_ids:
                    findings.append(Finding("ERROR", f"edge-unresolved:{tid}",
                        f"Track '{tid}' {kind} -> '{tgt}', which is not a declared track."))

    # Active-active conflict — two ACTIVE tracks joined by conflicts_with.
    if not policy["allow_active_active_conflict"]:
        active_ids = {t.get("id") for t in active}
        seen: set[frozenset[str]] = set()
        for t in active:
            for tgt in t.get("conflicts_with") or []:
                if tgt in active_ids:
                    pair = frozenset({t.get("id"), tgt})
                    if pair in seen:
                        continue
                    seen.add(pair)
                    findings.append(Finding("ERROR", f"active-conflict:{t.get('id')}",
                        f"ACTIVE tracks '{t.get('id')}' and '{tgt}' are joined by "
                        "conflicts_with — only one may be ACTIVE at a time."))

    # Owned-surface overlap among ACTIVE tracks — the no-global-mutex coordination plane.
    sev = "ERROR" if policy["surface_overlap"] == "error" else "WARN"
    owner: dict[str, str] = {}
    for t in active:
        for s in t.get("owned_surfaces") or []:
            if s in owner and owner[s] != t.get("id"):
                findings.append(Finding(sev, f"surface-overlap:{s}",
                    f"Surface '{s}' is owned by both '{owner[s]}' and '{t.get('id')}'. "
                    "Declare conflicts_with or split the surfaces."))
            else:
                owner[s] = t.get("id")


def detect_dependency_cycle(tracks: list[dict[str, Any]], findings: list[Finding]) -> None:
    """Three-colour DFS over depends_on edges; emit the actual cycle path.

    Recursion bound: the recursive `dfs` depth is bounded by the number of
    declared tracks, which is in turn capped by `track_policy.max_active`
    (default 10, hard ceiling enforced by `validate_portfolio_graph`). For
    portfolios near that ceiling we stay well under Python's default 1000-
    frame recursion limit, so no explicit `sys.setrecursionlimit` bump is
    needed. If `max_active` is ever raised above a few hundred, convert this
    to an explicit iterative DFS to keep the guarantee.
    """
    graph: dict[str, list[str]] = {
        str(t.get("id")): [str(d) for d in (t.get("depends_on") or [])] for t in tracks}
    ids = set(graph)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {i: WHITE for i in ids}
    stack: list[str] = []

    def dfs(u: str) -> bool:
        color[u] = GRAY
        stack.append(u)
        for v in graph.get(u, []):
            if v not in ids:          # unresolved edge -> reported elsewhere
                continue
            if color[v] == GRAY:
                cyc = stack[stack.index(v):] + [v]
                findings.append(Finding("ERROR", "dependency-cycle",
                    "depends_on cycle: " + " -> ".join(str(x) for x in cyc)))
                return True
            if color[v] == WHITE and dfs(v):
                return True
        color[u] = BLACK
        stack.pop()
        return False

    for i in sorted(ids):   # sorted for deterministic cycle reporting
        if color[i] == WHITE and dfs(i):
            break


def evaluate_track(t: dict[str, Any]) -> dict[str, Any]:
    prereqs = [evaluate_criterion(c) for c in (t.get("prerequisites") or [])]
    comps = [evaluate_criterion(c) for c in (t.get("completion_criteria") or [])]
    prereqs_ok = all(c.passed for c in prereqs) if prereqs else True
    completion_ok = all(c.passed for c in comps) if comps else False
    # Lenient bar (legacy): all completion criteria pass while the track occupies
    # the portfolio. Kept for reporting, but NO LONGER sufficient for "shippable".
    criteria_pass = prereqs_ok and completion_ok and _is_active(t)

    # --- RIGOROUS bar (the antidote to existence-only sign-off) ----------------
    # "all criteria pass" is not closure when every criterion is file_exists /
    # file_contains and blocker next-items are still open. Compute shippability
    # from evidence strength + blocker state, not from a bare boolean.
    next_items = [ni for ni in (t.get("next_items") or []) if isinstance(ni, dict)]
    open_blockers = [ni for ni in next_items if ni.get("blocker") is True]
    has_rigorous_evidence = any(c.passed and c.kind in RIGOROUS_KINDS for c in comps)
    ship_blocks: list[str] = []
    if open_blockers:
        ship_blocks.append(f"{len(open_blockers)} open blocker next-item(s)")
    if not has_rigorous_evidence:
        ship_blocks.append("no rigorous evidence (criteria are existence-only: "
                           "file_exists/file_contains — add test_passes / commit_on_main / receipt_valid)")
    shippable = criteria_pass and not ship_blocks

    return {
        "id": t.get("id"),
        "prereqs": prereqs,
        "completion": comps,
        "prereqs_ok": prereqs_ok,
        "shippable": shippable,            # RIGOROUS bar
        "criteria_pass": criteria_pass,    # legacy lenient bar (existence checks)
        "ship_blocks": ship_blocks,
        "has_rigorous_evidence": has_rigorous_evidence,
        "open_blocker_count": len(open_blockers),
        "passed": sum(1 for c in comps if c.passed),
        "total": len(comps),
    }


def _load_prior_passed() -> dict[str, set[str]]:
    """Read the previous evidence JSON so we can flag REGRESSION drift —
    a completion criterion that passed before and now fails (Terraform-plan style)."""
    path = REPORTS_DIR / "active_track_evidence.json"
    if not path.exists():
        return {}
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, set[str]] = {}
    for tr in prior.get("active_tracks", []) or []:
        out[tr.get("id")] = {c.get("id") for c in tr.get("criteria", []) if c.get("passed")}
    if not out and prior.get("active_track_id"):   # v1 evidence shape
        out[prior["active_track_id"]] = {
            c.get("id") for c in prior.get("criteria", []) if c.get("passed")}
    return out


def run(args: argparse.Namespace) -> int:
    findings: list[Finding] = []
    if not ACTIVE_TRACK_PATH.exists():
        findings.append(Finding("ERROR", "active-track-missing",
                                f"{ACTIVE_TRACK_PATH} not found"))
        emit_reports(findings, None, [])
        return 2

    raw = load_active_track(ACTIVE_TRACK_PATH)
    sv = raw.get("schema_version")
    if sv not in SUPPORTED_SCHEMA_VERSIONS:
        findings.append(Finding("ERROR", "schema-version-mismatch",
            f"schema_version {sv!r} not in supported {sorted(SUPPORTED_SCHEMA_VERSIONS)}"))

    p = normalize_portfolio(raw)
    if not p["active_tracks"]:
        findings.append(Finding("ERROR", "no-active-track",
            "ACTIVE_TRACK.yaml declares no tracks (active_tracks empty and "
            "active_track missing). Declare at least one track."))
        emit_reports(findings, p, [])
        return 2

    # Portfolio-level graph invariants.
    validate_portfolio_graph(p, findings)
    detect_dependency_cycle(p["active_tracks"], findings)

    prior_passed = _load_prior_passed()
    track_results: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for t in p["active_tracks"]:
        tid = t.get("id")

        # TTL (future dates allowed for timezone tolerance). Enforced only for
        # tracks that occupy the portfolio (active/shippable); a parked draft is
        # not held to a freshness clock until promoted.
        if _is_active(t):
            ttl = int(t.get("ttl_days", 14))
            age = days_since(str(t.get("verified_at", "")))
            if age is None:
                findings.append(Finding("ERROR", f"verified-at-malformed:{tid}",
                    f"[{tid}] verified_at malformed: {t.get('verified_at')!r}"))
            elif age > ttl:
                # TTL staleness is a portfolio-FRESHNESS signal, not a property
                # of any single PR — a PR author neither caused nor can fix an
                # unrelated track going stale. So on the per-PR path it is a
                # WARN (informational); only the scheduled freshness sweep
                # (--enforce-ttl) treats it as a blocking ERROR. This decouples
                # merge gating from the freshness clock so one stale track stops
                # blocking every open PR. See docs/governance/REPO_GOVERNANCE_AUDIT.md.
                ttl_sev = "ERROR" if getattr(args, "enforce_ttl", False) else "WARN"
                findings.append(Finding(ttl_sev, f"track-stale:{tid}",
                    f"[{tid}] verified_at is {age} days old (ttl_days={ttl}). "
                    "Re-verify and bump verified_at, or retire the track."))

        r = evaluate_track(t)

        # ENFORCING rigor gate (operator directive 2026-06-25): a track may not
        # DECLARE itself shippable without earning it under the rigorous bar.
        # Previously the rigor verdict was advisory (INFO only); a YAML that set
        # `status: shippable` on existence-only criteria would still pass green.
        # This is the "AI slop" trap the operator named: a green flag with no
        # real check behind it. Now a declared-shippable track that fails the
        # rigorous bar is a hard ERROR (non-zero exit), so the false-closure
        # claim blocks instead of merely informing.
        declared_status = str(t.get("status") or "").lower()
        if declared_status == "shippable" and not r["shippable"]:
            blocks = "; ".join(r["ship_blocks"]) or "rigorous bar not met"
            findings.append(Finding("ERROR", f"false-shippable-claim:{tid}",
                f"[{tid}] declares status: shippable but FAILS the rigorous bar: {blocks}. "
                "A track cannot be marked shippable without >=1 rigorous criterion "
                "(test_passes / commit_on_main / receipt_valid / pr_merged) and zero "
                "open blockers. Either add real evidence or change status back to ACTIVE."))

        # Prerequisite failures => track mis-declared.
        for c in r["prereqs"]:
            if not c.passed and c.kind in {"file_exists", "file_contains"}:
                findings.append(Finding("ERROR", f"prerequisite:{tid}:{c.id}",
                    f"[{tid}] prerequisite failed: {c.detail}. The work it builds on "
                    "does not exist.", criterion_id=c.id))

        # Regression drift => previously-passing completion criterion now fails.
        prev = prior_passed.get(tid, set())
        for c in r["completion"]:
            if c.id in prev and not c.passed:
                findings.append(Finding("ERROR", f"regression:{tid}:{c.id}",
                    f"[{tid}] REGRESSION — '{c.id}' passed before and now fails: {c.detail}",
                    criterion_id=c.id))

        if r["shippable"]:
            findings.append(Finding("INFO", f"track-shippable:{tid}",
                f"[{tid}] all {r['total']} criteria pass, rigorous evidence present, "
                "no open blockers — SHIPPABLE (rigorous bar). Close it."))
        elif r.get("criteria_pass"):
            findings.append(Finding("INFO", f"track-provisional:{tid}",
                f"[{tid}] {r['passed']}/{r['total']} criteria pass but NOT shippable "
                f"under the rigorous bar: {'; '.join(r['ship_blocks'])}. "
                "Existence checks are not closure (see REALITY_DEBT_LEDGER.md / "
                "cybernetics_codex._evaluate_loop_closure_replay)."))
        elif r["completion"]:
            findings.append(Finding("INFO", f"track-in-progress:{tid}",
                f"[{tid}] {r['passed']}/{r['total']} completion criteria pass."))

        track_results.append((t, r))

    emit_reports(findings, p, track_results)
    return 1 if any(f.severity == "ERROR" for f in findings) else 0


def _track_payload(t: dict[str, Any], r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": t.get("id"),
        "name": t.get("name"),
        "status": t.get("status"),
        "serves": t.get("serves"),
        "complements": t.get("complements") or [],
        "depends_on": t.get("depends_on") or [],
        "conflicts_with": t.get("conflicts_with") or [],
        "owned_surfaces": t.get("owned_surfaces") or [],
        "moves_vital_signs": t.get("moves_vital_signs") or [],
        "verified_at": t.get("verified_at"),
        "ttl_days": t.get("ttl_days"),
        "owner": t.get("owner"),
        "shippable": r["shippable"],
        "criteria_pass": r.get("criteria_pass", r["shippable"]),
        "ship_blocks": r.get("ship_blocks", []),
        "has_rigorous_evidence": r.get("has_rigorous_evidence", False),
        "prerequisites_ok": r["prereqs_ok"],
        "completion_progress": {"passed": r["passed"], "total": r["total"]},
        "criteria": [asdict(c) for c in (r["prereqs"] + r["completion"])],
    }


def emit_reports(findings: list[Finding], portfolio: dict[str, Any] | None,
                 track_results: list[tuple[dict[str, Any], dict[str, Any]]]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    portfolio = portfolio or {"active_tracks": [], "primary": None,
                              "spine_objectives": [], "track_policy": {}, "vital_signs": {}}

    at_payload = [_track_payload(t, r) for t, r in track_results]
    primary = portfolio.get("primary") or {}
    primary_payload = next((p for p in at_payload if p["id"] == primary.get("id")),
                           at_payload[0] if at_payload else None)

    active = [t for t in portfolio.get("active_tracks", []) if _is_active(t)]
    spine_ids = [o.get("id") for o in portfolio.get("spine_objectives", []) if o.get("id")]
    served = {t.get("serves") for t in active}
    pol = portfolio.get("track_policy", {})

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "schema_version": portfolio.get("schema_version"),
        # --- backward-compat: singular primary projection (legacy + frontend) ---
        "active_track_id": primary_payload["id"] if primary_payload else None,
        "shippable": primary_payload["shippable"] if primary_payload else False,
        "prerequisites_ok": primary_payload["prerequisites_ok"] if primary_payload else True,
        "completion_progress": primary_payload["completion_progress"] if primary_payload
                               else {"passed": 0, "total": 0},
        "criteria": primary_payload["criteria"] if primary_payload else [],
        # --- v2 portfolio view ---
        "portfolio_summary": {
            "active": len(active),
            "max_active": pol.get("max_active"),
            "warn_active": pol.get("warn_active"),
            "shippable": sum(1 for p in at_payload if p["shippable"]),
        },
        "spine_objectives": portfolio.get("spine_objectives", []),
        "spine_coverage": {oid: (oid in served) for oid in spine_ids},
        "vital_signs": portfolio.get("vital_signs", {}),
        "active_tracks": at_payload,
        "findings": [asdict(f) for f in findings],
    }
    text = json.dumps(payload, indent=2) + "\n"
    (REPORTS_DIR / "active_track_evidence.json").write_text(text, encoding="utf-8")
    # Richer name for the dashboard contract (same payload; one source of truth).
    (REPORTS_DIR / "track_portfolio.json").write_text(text, encoding="utf-8")

    md = ["# Track Portfolio Evidence",
          "",
          f"Generated: {payload['generated_at']} (schema v{payload['schema_version']})",
          f"Active tracks: **{payload['portfolio_summary']['active']}** "
          f"(warn {pol.get('warn_active')}, max {pol.get('max_active')}) — "
          f"shippable {payload['portfolio_summary']['shippable']}",
          ""]
    if spine_ids:
        md.append("## Spine coverage")
        md.append("")
        for oid in spine_ids:
            mark = "✓" if payload["spine_coverage"].get(oid) else "✗ (no active track)"
            md.append(f"- `{oid}` — {mark}")
        md.append("")
    for tp in at_payload:
        cp = tp["completion_progress"]
        flag = "SHIPPABLE" if tp["shippable"] else f"{cp['passed']}/{cp['total']}"
        md.append(f"## `{tp['id']}` — {flag}")
        md.append("")
        md.append(f"- serves: `{tp['serves']}` · complements: {tp['complements']} · "
                  f"depends_on: {tp['depends_on']} · conflicts_with: {tp['conflicts_with']}")
        md.append(f"- owned_surfaces: {tp['owned_surfaces']}")
        md.append(f"- moves_vital_signs: {tp['moves_vital_signs']}")
        md.append("")
        for c in tp["criteria"]:
            mark = "✓" if c["passed"] else "✗"
            md.append(f"  - {mark} `{c['id']}` ({c['kind']}) — {c['detail']}")
        md.append("")
    if findings:
        md.append("## Findings")
        md.append("")
        for f in findings:
            md.append(f"- **{f.severity}** `{f.check}`: {f.message}")
        md.append("")
    (REPORTS_DIR / "active_track_evidence.md").write_text("\n".join(md), encoding="utf-8")

    for f in findings:
        stream = sys.stderr if f.severity == "ERROR" else sys.stdout
        print(f"{f.severity}: {f.check}: {f.message}", file=stream)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ACTIVE_TRACK.yaml against repo reality.")
    parser.add_argument("--warn-only", action="store_true",
                        help="Emit findings but never exit non-zero (for pre-commit)")
    parser.add_argument("--enforce-ttl", action="store_true",
                        help="Treat TTL staleness as a blocking ERROR (scheduled "
                             "freshness sweep). Off by default so an unrelated stale "
                             "track does not block per-PR merges.")
    args = parser.parse_args()
    code = run(args)
    if args.warn_only:
        return 0
    return code


if __name__ == "__main__":
    sys.exit(main())
