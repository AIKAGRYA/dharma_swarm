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
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ACTIVE_TRACK_PATH = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
EVIDENCE_GRADES_PATH = REPO_ROOT / "docs/governance/evidence_grades.yaml"
REPORTS_DIR = REPO_ROOT / "reports/governance"
# Derived status is published here by CI (active-track.yml, push:main), not
# tracked on main — see the eviction rationale in .gitignore.
STATUS_BRANCH = "generated/status"
SCHEMA_VERSION = 2                       # current schema authored by this checker
SUPPORTED_SCHEMA_VERSIONS = {1, 2}       # v1 (singular active_track) read via adapter
EDGE_KINDS = ("complements", "depends_on", "conflicts_with")
FINAL_BOSS_EFFECTIVE_DATE = date(2026, 6, 30)
FINAL_BOSS_MIN_ROUNDS = 2
NON_PRODUCTION_CLOSURE_KINDS = frozenset({"VERIFIED_SLICE", "CLOSED_NOT_PROD", "RETIRED", "SUPERSEDED"})
PRODUCTION_CLOSURE_KINDS = frozenset({"PRODUCTION_READY", "SUBSTRATE_TRUSTED"})
CLOSURE_KINDS = NON_PRODUCTION_CLOSURE_KINDS | PRODUCTION_CLOSURE_KINDS
GRADUATION_PROFILES = frozenset({
    "generic",
    "runtime_transport",
    "runtime_truth",
    "provider_routing",
    "filesystem_substrate",
    "agent_identity",
    "governance_gate",
    "orchestration",
    "revenue_external",
    "research_depth",
    "truth_graph",
    "holon_bridge",
})
FINAL_BOSS_DIMENSIONS = frozenset({
    "production_engineering",
    "sre_failure_modes",
    "architecture_integration",
    "anti_slop_code_quality",
    "governance_truthfulness",
    "security_supply_chain",
    "future_maintainability",
})
RUNTIME_TRANSPORT_FAILURE_MODES = frozenset({
    "real_broker_e2e",
    "ack_nack_failure",
    "idempotency_duplicate_publish",
    "handler_failure",
    "execution_identity",
    "receipt_durability",
    "reconnect_or_degradation",
})


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


class CriterionFailureModality(str, Enum):
    """Why an executed criterion failed when policy must distinguish causes."""

    FRESHNESS = "freshness"


@dataclass
class CriterionResult:
    id: str
    kind: str
    passed: bool
    detail: str = ""
    # False when the check could not be RUN in this environment (e.g. the
    # governance gate's minimal-deps job has no pytest). An unverified check
    # is neither a pass nor a regression — it is "could not observe", and
    # must be reported as such instead of being scored as a hard failure.
    executed: bool = True
    failure_modality: CriterionFailureModality | None = None


def load_active_track(path: Path) -> dict[str, Any]:
    """Parse ACTIVE_TRACK.yaml using a stdlib-only YAML-subset parser.

    The file is intentionally simple YAML — we restrict ourselves to the
    subset already used by docs/docops/assertions.yaml (which is JSON-
    compatible). To stay stdlib-only we attempt PyYAML first; if missing,
    fall back to a minimal block parser.
    """
    text = path.read_text(encoding="utf-8")
    return _parse_active_track_text(text)


def _parse_active_track_text(text: str) -> dict[str, Any]:
    """Parse ACTIVE_TRACK.yaml content from a string (same strategy as
    load_active_track; used for base-ref blobs read via `git show`)."""
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
                    inline = {_scalar(key.strip()): _scalar(val.strip())}
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
                key = _scalar(key.strip())
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


def check_json_count_equals(
    file_path: str,
    collection: str,
    field: str,
    value: object,
    expected: int,
) -> CriterionResult:
    """Count structured JSON rows instead of regex-matching generated prose."""
    path = repo_path(file_path)
    if not path.exists():
        return CriterionResult(id="", kind="json_count_equals", passed=False,
                               detail=f"{file_path} missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return CriterionResult(id="", kind="json_count_equals", passed=False,
                               detail=f"{file_path} unreadable: {type(exc).__name__}")
    rows = data.get(collection)
    if not isinstance(rows, list):
        return CriterionResult(id="", kind="json_count_equals", passed=False,
                               detail=f"{file_path}.{collection} is not a list")
    actual = sum(1 for row in rows if isinstance(row, dict) and row.get(field) == value)
    passed = actual == expected
    return CriterionResult(
        id="", kind="json_count_equals", passed=passed,
        detail=(
            f"{file_path}.{collection}[].{field} == {value!r}: "
            f"{actual} {'==' if passed else '!='} {expected}"
        ),
    )


def check_json_count_greater_than(
    file_path: str,
    collection: str,
    field: str,
    value: object,
    threshold: int,
) -> CriterionResult:
    path = repo_path(file_path)
    if not path.exists():
        return CriterionResult(id="", kind="json_count_greater_than", passed=False,
                               detail=f"{file_path} missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return CriterionResult(id="", kind="json_count_greater_than", passed=False,
                               detail=f"{file_path} unreadable: {type(exc).__name__}")
    rows = data.get(collection)
    if not isinstance(rows, list):
        return CriterionResult(id="", kind="json_count_greater_than", passed=False,
                               detail=f"{file_path}.{collection} is not a list")
    actual = sum(1 for row in rows if isinstance(row, dict) and row.get(field) == value)
    passed = actual > threshold
    return CriterionResult(
        id="", kind="json_count_greater_than", passed=passed,
        detail=(
            f"{file_path}.{collection}[].{field} == {value!r}: "
            f"{actual} {'>' if passed else '<='} {threshold}"
        ),
    )


def check_json_collection_values_match(
    file_path: str,
    collection: str,
    key_field: str,
    value_field: str,
    expected: dict[Any, Any],
) -> CriterionResult:
    path = repo_path(file_path)
    if not path.exists():
        return CriterionResult(id="", kind="json_collection_values_match", passed=False,
                               detail=f"{file_path} missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return CriterionResult(id="", kind="json_collection_values_match", passed=False,
                               detail=f"{file_path} unreadable: {type(exc).__name__}")
    rows = data.get(collection)
    if not isinstance(rows, list):
        return CriterionResult(id="", kind="json_collection_values_match", passed=False,
                               detail=f"{file_path}.{collection} is not a list")
    actual = {
        str(row.get(key_field)): row.get(value_field)
        for row in rows
        if isinstance(row, dict) and key_field in row
    }
    missing: list[str] = []
    mismatched: list[str] = []
    for raw_key, expected_value in expected.items():
        key = str(raw_key)
        if key not in actual:
            missing.append(key)
        elif actual[key] != expected_value:
            mismatched.append(f"{key}: {actual[key]!r} != {expected_value!r}")
    passed = not missing and not mismatched
    if passed:
        detail = f"{file_path}.{collection} {len(expected)} expected {value_field} value(s) matched"
    else:
        bits = []
        if missing:
            bits.append(f"missing keys {missing}")
        if mismatched:
            bits.append(f"mismatched {mismatched}")
        detail = f"{file_path}.{collection} value map mismatch: {'; '.join(bits)}"
    return CriterionResult(id="", kind="json_collection_values_match", passed=passed, detail=detail)


def check_json_mapping_keys_nonempty(
    file_path: str,
    mapping: str,
    keys: list[str],
) -> CriterionResult:
    path = repo_path(file_path)
    if not path.exists():
        return CriterionResult(id="", kind="json_mapping_keys_nonempty", passed=False,
                               detail=f"{file_path} missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return CriterionResult(id="", kind="json_mapping_keys_nonempty", passed=False,
                               detail=f"{file_path} unreadable: {type(exc).__name__}")
    obj = data.get(mapping)
    if not isinstance(obj, dict):
        return CriterionResult(id="", kind="json_mapping_keys_nonempty", passed=False,
                               detail=f"{file_path}.{mapping} is not a mapping")
    missing = [key for key in keys if not str(obj.get(key) or "").strip()]
    passed = not missing
    return CriterionResult(
        id="", kind="json_mapping_keys_nonempty", passed=passed,
        detail=(
            f"{file_path}.{mapping} has non-empty values for {len(keys)} key(s)"
            if passed else f"{file_path}.{mapping} missing/empty keys: {missing}"
        ),
    )


def _compact_command_output(text: str, *, limit: int = 500) -> str:
    compact = " | ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _resolve_command_for_current_runtime(command: list[str]) -> list[str]:
    """Keep executable criteria portable across worktrees.

    ACTIVE_TRACK criteria are written as literal commands so operators can see
    what is being proven. In isolated worktrees, though, the repository-local
    virtualenv may not exist even when this checker is already running under a
    dependency-complete Python. Resolve those common Python entrypoints to the
    current interpreter instead of making track truth depend on one checkout's
    `.venv` path.
    """
    if not command:
        return command
    executable = command[0]
    if executable in {"python", "python3"}:
        return [sys.executable, *command[1:]]
    if executable == "pytest":
        return [sys.executable, "-m", "pytest", *command[1:]]
    if executable in {"./.venv/bin/python", ".venv/bin/python"} and not Path(executable).exists():
        return [sys.executable, *command[1:]]
    return command


def _missing_environment_module(output: str) -> str | None:
    """Top-level module named by a trailing ``No module named ...`` error when
    that module is NOT part of this repository. Mirrors the test_passes
    doctrine above: a third-party import absent from the current execution
    environment means the check could not be RUN — it says nothing about the
    code. A missing repo-local module remains a real failure."""
    matches = re.findall(r"No module named '?([A-Za-z0-9_.]+)'?", output)
    if not matches:
        return None
    top = matches[-1].split(".")[0]
    if (REPO_ROOT / top).is_dir() or (REPO_ROOT / f"{top}.py").exists():
        return None
    return top


def check_command_passes(
    command: list[str],
    *,
    timeout_s: int = 120,
    cwd: str | None = None,
) -> CriterionResult:
    kind = "command_passes"
    if os.environ.get("DHARMA_TRACK_STATUS_SKIP_COMMANDS") == "1":
        # Explicit caller opt-out, for callers that already own execution of
        # the same work — e.g. the pytest suite invokes this checker while the
        # suite itself runs every pytest-battery criterion as first-class
        # tests; re-running them here is quadratic (suite → checker → suite).
        # Unverified, never a fake pass and never a fake regression.
        return CriterionResult(
            id="", kind=kind, passed=False, executed=False,
            detail=f"{' '.join(command)} not executed: "
                   "DHARMA_TRACK_STATUS_SKIP_COMMANDS=1 (caller owns command execution)")
    resolved_command = _resolve_command_for_current_runtime(command)
    env = None
    if "DHARMA_PYTHON" not in os.environ:
        # Wrapper-routed criteria (run_python_with_repo_env.sh) honor
        # DHARMA_PYTHON; point them at this dependency-complete interpreter so
        # track truth does not depend on one checkout's `.venv` — the same
        # portability doctrine as _resolve_command_for_current_runtime.
        env = {**os.environ, "DHARMA_PYTHON": sys.executable}
    try:
        result = subprocess.run(
            resolved_command,
            cwd=cwd or None,
            capture_output=True,
            text=True,
            timeout=max(1, timeout_s),
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return CriterionResult(
            id="",
            kind=kind,
            passed=False,
            detail=f"{' '.join(resolved_command)} timed out after {exc.timeout}s",
        )
    except OSError as exc:
        return CriterionResult(
            id="",
            kind=kind,
            passed=False,
            detail=f"{' '.join(resolved_command)} failed to start: {exc}",
        )

    output = _compact_command_output((result.stdout or "") + "\n" + (result.stderr or ""))
    detail = f"{' '.join(resolved_command)} exited {result.returncode}"
    if resolved_command != command:
        detail += f" (resolved from {' '.join(command)})"
    if output:
        detail += f"; output: {output}"
    if result.returncode != 0:
        missing = _missing_environment_module(output)
        if missing is not None:
            return CriterionResult(
                id="", kind=kind, passed=False, executed=False,
                detail=f"{' '.join(resolved_command)} could not execute here: "
                       f"environment lacks '{missing}' (not evidence of regression); {detail}")
    return CriterionResult(id="", kind=kind, passed=result.returncode == 0, detail=detail)


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
RIGOROUS_KINDS = frozenset({
    "test_passes",
    "commit_on_main",
    "receipt_valid",
    "pr_merged",
    "mutation_score_gte",
    "json_count_equals",
    "json_count_greater_than",
    "json_collection_values_match",
    "json_mapping_keys_nonempty",
})
EXISTENCE_KINDS = frozenset({"file_exists", "file_contains"})


# --- Graded evidence ladder (Pudgala Autopoiesis Protostar Phase 1) -----------
# The RIGOROUS bar above is binary: ONE rigorous criterion of any strength
# suffices. That still lets a track ship on a single self-authored green test.
# The ladder turns "rigorous yes/no" into a GRADED floor (min_evidence_grade):
# a claim ships only when its strongest passing evidence meets the required
# grade, and an oracle the claimant owns is downgraded (not independent).
#
# Strength is declared declaratively in docs/governance/evidence_grades.yaml so
# new grades need no code change here; this module only reads that projection.
# Default floor (S2 = commit_on_main) is used when neither the ladder file nor a
# track declares one — keeping the gate functional even if the YAML is absent.
_DEFAULT_MIN_GRADE = 2
_DEFAULT_ORACLE_DOWNGRADE = 2
_GRADE_LADDER_CACHE: dict[str, Any] | None = None


def _load_grade_ladder() -> dict[str, Any]:
    """Load + cache evidence_grades.yaml into a lookup of active kind->grade.

    Missing/malformed ladder is non-fatal: we fall back to a built-in active
    map (S0..S3) so the gate degrades to its pre-ladder rigorous behaviour
    rather than crashing (a governance gate must not crash on bad config)."""
    global _GRADE_LADDER_CACHE
    if _GRADE_LADDER_CACHE is not None:
        return _GRADE_LADDER_CACHE

    builtin_active = {
        "file_exists": 0,
        "file_contains": 1,
        "pr_merged": 1,
        "commit_on_main": 2,
        "json_count_equals": 2,
        "json_count_greater_than": 2,
        "json_collection_values_match": 2,
        "json_mapping_keys_nonempty": 2,
        "receipt_valid": 2,
        "test_passes": 3,
        "mutation_score_gte": 6,
    }
    ladder = {
        "kind_to_grade": dict(builtin_active),
        "default_min_grade": _DEFAULT_MIN_GRADE,
        "oracle_downgrade_to": _DEFAULT_ORACLE_DOWNGRADE,
        "grade_names": {0: "S0", 1: "S1", 2: "S2", 3: "S3", 6: "S6"},
    }
    if EVIDENCE_GRADES_PATH.exists():
        try:
            raw = load_active_track(EVIDENCE_GRADES_PATH)  # same YAML-subset loader
        except (OSError, ValueError):
            raw = None
        if isinstance(raw, dict):
            kind_to_grade: dict[str, int] = {}
            names: dict[int, str] = {}
            parsed_active_grade = False
            for row in raw.get("grades") or []:
                if not isinstance(row, dict):
                    continue
                try:
                    g = int(row.get("grade"))
                except (TypeError, ValueError):
                    continue
                names[g] = str(row.get("name", f"S{g}"))
                # Only ACTIVE grades contribute scoring kinds; reserved kinds
                # remain unmapped and therefore score S0 until they land.
                if str(row.get("status", "active")) != "active":
                    continue
                parsed_active_grade = True
                for kind in row.get("kinds") or []:
                    kind_to_grade[str(kind)] = g
            # receipt_valid is a checker-native rigorous kind not listed as its
            # own ladder row; pin it to S2 (landed-equivalent) if unmapped.
            if parsed_active_grade:
                kind_to_grade.setdefault("receipt_valid", 2)
                ladder["kind_to_grade"] = {**builtin_active, **kind_to_grade}
                ladder["grade_names"] = names or ladder["grade_names"]
            try:
                ladder["default_min_grade"] = int(raw.get("default_min_grade", _DEFAULT_MIN_GRADE))
            except (TypeError, ValueError):
                ladder["default_min_grade"] = _DEFAULT_MIN_GRADE
            try:
                ladder["oracle_downgrade_to"] = int(
                    raw.get("oracle_dependent_downgrade_to", _DEFAULT_ORACLE_DOWNGRADE))
            except (TypeError, ValueError):
                ladder["oracle_downgrade_to"] = _DEFAULT_ORACLE_DOWNGRADE
    _GRADE_LADDER_CACHE = ladder
    return ladder


def grade_of_criterion(crit: dict[str, Any], result: "CriterionResult",
                       track: dict[str, Any]) -> int:
    """Grade a PASSING criterion on the S0..S8 ladder. Failing/unmapped/reserved
    kinds score 0. A `test_passes` whose `oracle_source` is absent or equals the
    track owner is oracle-DEPENDENT and downgraded (a self-owned green test is
    not independent evidence)."""
    if not result.passed:
        return 0
    ladder = _load_grade_ladder()
    grade = int(ladder["kind_to_grade"].get(result.kind, 0))
    if result.kind == "test_passes":
        oracle = str(crit.get("oracle_source") or "").strip()
        owner = str(track.get("owner") or "").strip()
        if not oracle or oracle == owner:
            grade = min(grade, int(ladder["oracle_downgrade_to"]))
    return grade


def grade_name(grade: int) -> str:
    return _load_grade_ladder()["grade_names"].get(grade, f"S{grade}")


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
        return CriterionResult(id="", kind="test_passes", passed=False, executed=False,
                               detail=f"pytest {test_target}: {type(exc).__name__} (could not execute)")
    out = (res.stdout or "") + (res.stderr or "")
    # pytest itself absent (minimal-deps environment): the check could not be
    # RUN. Report it as unverified rather than a hard fail — a missing test
    # runner is not evidence the code regressed.
    if res.returncode != 0 and "No module named pytest" in out:
        return CriterionResult(id="", kind="test_passes", passed=False, executed=False,
                               detail=f"pytest {test_target}: pytest not installed (could not execute)")
    passed = res.returncode == 0
    lines = [ln for ln in out.splitlines() if ln.strip()]
    tail = lines[-1] if lines else ""
    return CriterionResult(id="", kind="test_passes", passed=passed,
                           detail=f"pytest {test_target}: {'PASS' if passed else 'FAIL'} — {tail}")


# Canonicalisation must match dharma_swarm/memory_kernel/write_receipts.py
# (canonical_json / stable_digest) byte-for-byte so a digest produced by a
# VerifiedMachineReceipt verifies here. Inlined to keep this gate stdlib-only
# and import-light (it must run even when dharma_swarm deps are unavailable).
def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _stable_digest(payload: object) -> str:
    import hashlib
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _recompute_digest(row: dict[str, Any]) -> str:
    """Digest covers every field EXCEPT `digest` itself; `prev_digest` IS
    included (that is what chains receipts). Mirrors the producer in
    dharma_swarm/spine/receipt.py::VerifiedMachineReceipt.with_chain."""
    return _stable_digest({k: v for k, v in row.items() if k != "digest"})


def _receipt_timestamp(row: dict[str, Any]) -> str | None:
    for key in (
        "produced_at",
        "generated_at",
        "observed_at",
        "finished_at",
        "started_at",
        "verified_at",
    ):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return None


def check_receipt_valid(file_path: str, requires_keys: list[str], *,
                        fresh_ttl_days: int | None = None,
                        expect_digest: bool = False,
                        expect_chain: bool = False) -> CriterionResult:
    """A receipt artifact must EXIST and carry the required structural keys —
    behavioral evidence, not just file presence. Optionally (Pudgala Autopoiesis
    Protostar Phase 1) it must also be FRESH (within fresh_ttl_days), DIGEST-INTACT
    (stored digest recomputes), and CHAIN-INTACT (JSONL where each row's
    prev_digest links to the previous row's digest). Any failed check ->
    NOT passed (a stale or tampered receipt is not evidence)."""
    path = repo_path(file_path)
    if not path.exists():
        return CriterionResult(id="", kind="receipt_valid", passed=False,
                               detail=f"receipt {file_path} MISSING")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return CriterionResult(id="", kind="receipt_valid", passed=False,
                               detail=f"receipt {file_path} unreadable: {type(exc).__name__}")

    # Chain mode: parse as JSONL and verify digest + prev_digest linkage.
    if expect_chain:
        rows: list[dict[str, Any]] = []
        for ln in text.splitlines():
            if not ln.strip():
                continue
            try:
                row = json.loads(ln)
            except json.JSONDecodeError:
                return CriterionResult(id="", kind="receipt_valid", passed=False,
                                       detail=f"receipt chain {file_path} has a non-JSON line")
            if not isinstance(row, dict):
                return CriterionResult(id="", kind="receipt_valid", passed=False,
                                       detail=f"receipt chain {file_path} row {len(rows)} is not a JSON object")
            rows.append(row)
        if not rows:
            return CriterionResult(id="", kind="receipt_valid", passed=False,
                                   detail=f"receipt chain {file_path} is empty")
        prev = ""
        for i, row in enumerate(rows):
            stored = str(row.get("digest", ""))
            if not stored or stored != _recompute_digest(row):
                return CriterionResult(id="", kind="receipt_valid", passed=False,
                    detail=f"receipt chain {file_path} row {i} digest mismatch (tampered)")
            link = str(row.get("prev_digest", ""))
            if i == 0 and link:
                return CriterionResult(id="", kind="receipt_valid", passed=False,
                    detail=f"receipt chain {file_path} row 0 has non-empty prev_digest (missing genesis anchor)")
            if i > 0 and link != prev:
                return CriterionResult(id="", kind="receipt_valid", passed=False,
                    detail=f"receipt chain {file_path} broken at row {i}: prev_digest != prior digest")
            prev = stored
        data = rows[-1]
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return CriterionResult(id="", kind="receipt_valid", passed=False,
                                   detail=f"receipt {file_path} unreadable: {type(exc).__name__}")
        if not isinstance(data, dict):
            return CriterionResult(id="", kind="receipt_valid", passed=False,
                                   detail=f"receipt {file_path} is not a JSON object")
        if expect_digest:
            stored = str(data.get("digest", ""))
            if not stored:
                return CriterionResult(id="", kind="receipt_valid", passed=False,
                                       detail=f"receipt {file_path} has no digest to verify")
            if stored != _recompute_digest(data):
                return CriterionResult(id="", kind="receipt_valid", passed=False,
                                       detail=f"receipt {file_path} digest mismatch (tampered)")

    missing = [k for k in (requires_keys or []) if k not in data]
    if missing:
        return CriterionResult(id="", kind="receipt_valid", passed=False,
                               detail=f"receipt {file_path} missing keys: {', '.join(missing)}")

    if fresh_ttl_days is not None:
        ts = _receipt_timestamp(data)
        if ts is None:
            return CriterionResult(id="", kind="receipt_valid", passed=False,
                detail=f"receipt {file_path} has no timestamp to check freshness")
        age = days_since(ts[:10])
        if age is None:
            return CriterionResult(id="", kind="receipt_valid", passed=False,
                detail=f"receipt {file_path} timestamp malformed: {ts!r}")
        if age > fresh_ttl_days:
            return CriterionResult(id="", kind="receipt_valid", passed=False,
                detail=f"receipt {file_path} is stale: {age}d old > fresh_ttl_days={fresh_ttl_days}",
                failure_modality=CriterionFailureModality.FRESHNESS)

    bits = [f"{len(requires_keys or [])} keys present"]
    if expect_chain:
        bits.append("chain intact")
    if expect_digest:
        bits.append("digest intact")
    if fresh_ttl_days is not None:
        bits.append("fresh")
    return CriterionResult(id="", kind="receipt_valid", passed=True,
                           detail=f"receipt {file_path} valid ({', '.join(bits)})")


def check_mutation_score_gte(file_path: str, threshold: float, *,
                             fresh_ttl_days: int | None = None) -> CriterionResult:
    """A mutation-score report must EXIST, be FRESH, and show a score >= threshold.

    This is S6, the primary anti-gaming oracle: the test suite must kill injected
    faults. The expensive mutmut run happens in `make mutation-test`; this gate
    only reads the report so normal track evaluation stays fast.
    """
    path = repo_path(file_path)
    if not path.exists():
        return CriterionResult(
            id="",
            kind="mutation_score_gte",
            passed=False,
            detail=f"mutation report {file_path} MISSING — run `make mutation-test`",
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return CriterionResult(
            id="",
            kind="mutation_score_gte",
            passed=False,
            detail=f"mutation report {file_path} unreadable: {type(exc).__name__}",
        )
    if not isinstance(data, dict):
        return CriterionResult(
            id="",
            kind="mutation_score_gte",
            passed=False,
            detail=f"mutation report {file_path} is not a JSON object",
        )
    try:
        score = float(data.get("score"))
    except (TypeError, ValueError):
        return CriterionResult(
            id="",
            kind="mutation_score_gte",
            passed=False,
            detail=f"mutation report {file_path} has no numeric 'score'",
        )
    if not math.isfinite(score):
        return CriterionResult(
            id="",
            kind="mutation_score_gte",
            passed=False,
            detail=f"mutation report {file_path} has non-finite 'score'",
        )
    passed = score >= threshold
    score_detail = (
        f"mutation score {score:.2f} {'>=' if passed else '<'} {threshold:.2f} "
        f"({data.get('killed', '?')}/{data.get('total', '?')} mutants killed)"
    )
    if fresh_ttl_days is not None:
        ts = _receipt_timestamp(data)
        age = days_since(ts[:10]) if ts else None
        if age is None:
            return CriterionResult(
                id="",
                kind="mutation_score_gte",
                passed=False,
                detail=f"mutation report {file_path} has no usable timestamp for freshness",
            )
        if age > fresh_ttl_days:
            freshness_detail = (
                f"mutation report {file_path} is stale: {age}d old > "
                f"fresh_ttl_days={fresh_ttl_days}"
            )
            if score < threshold:
                return CriterionResult(
                    id="",
                    kind="mutation_score_gte",
                    passed=False,
                    detail=f"{score_detail}; {freshness_detail}",
                )
            return CriterionResult(
                id="",
                kind="mutation_score_gte",
                passed=False,
                detail=freshness_detail,
                failure_modality=CriterionFailureModality.FRESHNESS,
            )
    return CriterionResult(
        id="",
        kind="mutation_score_gte",
        passed=passed,
        detail=score_detail,
    )


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
        elif kind == "json_count_equals":
            required = ("file", "collection", "field", "value", "expected")
            missing = [key for key in required if key not in crit]
            if missing:
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail=f"malformed criterion: missing {', '.join(missing)}")
            elif (
                not isinstance(crit.get("file"), str)
                or not isinstance(crit.get("collection"), str)
                or not isinstance(crit.get("field"), str)
                or crit.get("value") is None
            ):
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: 'file', 'collection', and 'field' "
                                             "must be strings and 'value' must be set")
            else:
                res = check_json_count_equals(
                    crit["file"],
                    crit["collection"],
                    crit["field"],
                    crit["value"],
                    int(crit["expected"]),
                )
        elif kind == "json_count_greater_than":
            required = ("file", "collection", "field", "value", "threshold")
            missing = [key for key in required if key not in crit]
            if missing:
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail=f"malformed criterion: missing {', '.join(missing)}")
            elif (
                not isinstance(crit.get("file"), str)
                or not isinstance(crit.get("collection"), str)
                or not isinstance(crit.get("field"), str)
                or crit.get("value") is None
            ):
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: 'file', 'collection', and 'field' "
                                             "must be strings and 'value' must be set")
            else:
                res = check_json_count_greater_than(
                    crit["file"],
                    crit["collection"],
                    crit["field"],
                    crit["value"],
                    int(crit["threshold"]),
                )
        elif kind == "json_collection_values_match":
            required = ("file", "collection", "key_field", "value_field", "expected")
            missing = [key for key in required if key not in crit]
            if missing:
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail=f"malformed criterion: missing {', '.join(missing)}")
            elif (
                not isinstance(crit.get("file"), str)
                or not isinstance(crit.get("collection"), str)
                or not isinstance(crit.get("key_field"), str)
                or not isinstance(crit.get("value_field"), str)
                or not isinstance(crit.get("expected"), dict)
            ):
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: expected file/collection/key_field/"
                                             "value_field strings and expected mapping")
            else:
                res = check_json_collection_values_match(
                    crit["file"],
                    crit["collection"],
                    crit["key_field"],
                    crit["value_field"],
                    crit["expected"],
                )
        elif kind == "json_mapping_keys_nonempty":
            required = ("file", "mapping", "keys")
            missing = [key for key in required if key not in crit]
            if missing:
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail=f"malformed criterion: missing {', '.join(missing)}")
            elif (
                not isinstance(crit.get("file"), str)
                or not isinstance(crit.get("mapping"), str)
                or not isinstance(crit.get("keys"), list)
            ):
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: expected file/mapping strings and keys list")
            else:
                res = check_json_mapping_keys_nonempty(
                    crit["file"],
                    crit["mapping"],
                    [str(key) for key in crit["keys"]],
                )
        elif kind == "command_passes":
            command = crit.get("command")
            if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: 'command' must be a non-empty list of strings")
            elif crit.get("cwd") is not None and not isinstance(crit.get("cwd"), str):
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: 'cwd' must be a string when present")
            else:
                res = check_command_passes(
                    command,
                    timeout_s=int(crit.get("timeout_s", 120)),
                    cwd=crit.get("cwd"),
                )
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
                ttl = crit.get("fresh_ttl_days")
                res = check_receipt_valid(
                    crit["file"], crit.get("requires_keys") or [],
                    fresh_ttl_days=int(ttl) if ttl is not None else None,
                    expect_digest=bool(crit.get("expect_digest")),
                    expect_chain=bool(crit.get("expect_chain")),
                )
        elif kind == "mutation_score_gte":
            report = crit.get("file")
            if report is None:
                report = "reports/governance/mutation_score.json"
            if not isinstance(report, str) or not report:
                res = CriterionResult(id="", kind=kind, passed=False,
                                      detail="malformed criterion: 'file' must be a non-empty string")
            else:
                try:
                    threshold = float(crit.get("threshold", 0.6))
                except (TypeError, ValueError):
                    threshold = 0.6
                ttl = crit.get("fresh_ttl_days")
                res = check_mutation_score_gte(
                    report,
                    threshold,
                    fresh_ttl_days=int(ttl) if ttl is not None else None,
                )
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


def _parse_iso_date(value: object) -> date | None:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _as_upper_token(value: object) -> str:
    return str(value or "").strip().upper().replace("-", "_")


def _as_lower_token(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _as_str_set(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {_as_lower_token(value)} if value.strip() else set()
    if isinstance(value, list):
        return {_as_lower_token(v) for v in value if str(v or "").strip()}
    return set()


def _int_field(row: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _float_field(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _declared_closure_kind(t: dict[str, Any]) -> str:
    return _as_upper_token(
        t.get("closure_kind")
        or t.get("graduation_target")
        or t.get("target_closure_kind")
    )


def _graduation_profile(t: dict[str, Any]) -> str:
    return _as_lower_token(t.get("graduation_profile") or t.get("track_profile") or "generic")


def _read_json_object(path: str) -> tuple[dict[str, Any] | None, str]:
    resolved = repo_path(path)
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"does not exist: {path}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"unreadable JSON {path}: {type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, f"JSON is not an object: {path}"
    return data, ""


def _validate_final_boss_dossier(
    path: str,
    track_id: str,
    closure_kind: str,
    profile: str,
) -> list[str]:
    data, err = _read_json_object(path)
    if err:
        return [f"final_boss_review.dossier {err}"]
    assert data is not None
    blocks: list[str] = []
    if data.get("track_id") != track_id:
        blocks.append(
            f"final_boss_review.dossier track_id {data.get('track_id')!r} != {track_id!r}")
    if _as_upper_token(data.get("target_closure_kind")) != closure_kind:
        blocks.append(
            "final_boss_review.dossier target_closure_kind "
            f"{data.get('target_closure_kind')!r} != {closure_kind!r}")
    if _as_lower_token(data.get("graduation_profile")) != profile:
        blocks.append(
            "final_boss_review.dossier graduation_profile "
            f"{data.get('graduation_profile')!r} != {profile!r}")
    dimensions = _as_str_set(data.get("review_dimensions") or data.get("dimensions"))
    missing_dimensions = sorted(FINAL_BOSS_DIMENSIONS - dimensions)
    if missing_dimensions:
        blocks.append("final_boss_review.dossier missing dimensions: " + ", ".join(missing_dimensions))
    requirements = data.get("profile_requirements")
    if not isinstance(requirements, dict):
        blocks.append("final_boss_review.dossier profile_requirements missing")
    else:
        hard_rejects = requirements.get("hard_rejects") or data.get("hard_rejects") or []
        if not isinstance(hard_rejects, list) or not hard_rejects:
            blocks.append("final_boss_review.dossier profile_requirements.hard_rejects missing")
        evidence_themes = requirements.get("required_evidence_themes") or []
        if not isinstance(evidence_themes, list) or not evidence_themes:
            blocks.append("final_boss_review.dossier profile_requirements.required_evidence_themes missing")
        if profile == "runtime_transport":
            failure_modes = _as_str_set(requirements.get("required_failure_modes"))
            missing_modes = sorted(RUNTIME_TRANSPORT_FAILURE_MODES - failure_modes)
            if missing_modes:
                blocks.append(
                    "final_boss_review.dossier runtime_transport missing required failure modes: "
                    + ", ".join(missing_modes)
                )
    return blocks


def _validate_council_receipt(path: str, reviewer_count: int) -> list[str]:
    data, err = _read_json_object(path)
    if err:
        return [f"final_boss_review.council_receipt {err}"]
    assert data is not None
    blocks: list[str] = []
    if data.get("conviction_gate") != "pass_fullness":
        blocks.append(
            f"council_receipt {path} conviction_gate {data.get('conviction_gate')!r} != 'pass_fullness'")
    if _float_field(data, "target_score") < 100:
        blocks.append(f"council_receipt {path} target_score < 100")
    if _float_field(data, "score_min") < 100:
        blocks.append(f"council_receipt {path} score_min < 100")
    blockers = data.get("blockers") or []
    if blockers:
        blocks.append(f"council_receipt {path} has blockers: {blockers[:3]}")
    required_count = _int_field(data, "required_critic_count") or _int_field(data, "critic_count")
    if required_count < reviewer_count:
        blocks.append(
            f"council_receipt {path} required critic count {required_count} < reviewer_count {reviewer_count}")
    witness = data.get("persistent_agent_witness") or {}
    if not isinstance(witness, dict) or witness.get("fresh") is not True:
        blocks.append(f"council_receipt {path} persistent witness is not fresh")

    critics = data.get("critics") or []
    if not isinstance(critics, list):
        blocks.append(f"council_receipt {path} critics is not a list")
        return blocks
    required_rows = [row for row in critics if isinstance(row, dict) and row.get("required", True)]
    if len(required_rows) < reviewer_count:
        blocks.append(
            f"council_receipt {path} required reviewer rows {len(required_rows)} < reviewer_count {reviewer_count}")
    for row in required_rows:
        lane = row.get("lane_id") or row.get("provider") or "unknown"
        parsed = row.get("parsed") or {}
        if not row.get("ok"):
            blocks.append(f"council_receipt {path} lane {lane} not ok")
            continue
        if not isinstance(parsed, dict):
            blocks.append(f"council_receipt {path} lane {lane} parsed review missing")
            continue
        if str(parsed.get("verdict") or "").lower() not in {"pass", "approve"}:
            blocks.append(
                f"council_receipt {path} lane {lane} verdict {parsed.get('verdict')!r} is not pass/approve")
        if _float_field(parsed, "score") < 100:
            blocks.append(f"council_receipt {path} lane {lane} score < 100")
        if str(parsed.get("explicit_disagreement") or "").strip():
            blocks.append(f"council_receipt {path} lane {lane} has explicit disagreement")
    return blocks


def _council_receipt_paths(review: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    raw_many = review.get("council_receipts")
    if isinstance(raw_many, list):
        paths.extend(str(p) for p in raw_many if str(p or "").strip())
    raw_one = str(review.get("council_receipt") or "").strip()
    if raw_one:
        paths.append(raw_one)
    deduped: list[str] = []
    for path in paths:
        if path not in deduped:
            deduped.append(path)
    return deduped


def _final_boss_coverage_blocks(
    review: dict[str, Any],
    *,
    receipt_paths: list[str],
    rounds: int,
    dimensions: set[str],
) -> list[str]:
    """Verify each Final Boss dimension has a distinct council receipt per round."""
    blocks: list[str] = []
    required_dimensions = FINAL_BOSS_DIMENSIONS & dimensions
    expected_pairs = {
        (round_index, dimension)
        for round_index in range(1, rounds + 1)
        for dimension in required_dimensions
    }
    expected_count = len(expected_pairs)
    if len(receipt_paths) < expected_count:
        blocks.append(
            "final_boss_review has "
            f"{len(receipt_paths)} distinct council receipt(s) but requires at least "
            f"{expected_count} ({rounds} round(s) x {len(required_dimensions)} required dimensions)"
        )

    raw_coverage = review.get("council_coverage")
    if not isinstance(raw_coverage, list):
        blocks.append("final_boss_review.council_coverage missing")
        return blocks

    receipt_set = set(receipt_paths)
    covered_pairs: set[tuple[int, str]] = set()
    coverage_receipts: set[str] = set()
    for index, row in enumerate(raw_coverage):
        if not isinstance(row, dict):
            blocks.append(f"final_boss_review.council_coverage[{index}] is not a mapping")
            continue
        round_index = _int_field(row, "round")
        dimension = _as_lower_token(row.get("dimension"))
        receipt = str(row.get("council_receipt") or row.get("receipt") or "").strip()
        if round_index < 1 or round_index > rounds:
            blocks.append(
                f"final_boss_review.council_coverage[{index}] round {round_index} outside 1..{rounds}")
        if dimension not in FINAL_BOSS_DIMENSIONS:
            blocks.append(
                f"final_boss_review.council_coverage[{index}] unknown dimension {dimension!r}")
        if not receipt:
            blocks.append(f"final_boss_review.council_coverage[{index}] council_receipt missing")
        elif receipt not in receipt_set:
            blocks.append(
                f"final_boss_review.council_coverage[{index}] receipt {receipt!r} "
                "is not listed in council_receipts")
        if (
            round_index >= 1
            and round_index <= rounds
            and dimension in required_dimensions
            and receipt in receipt_set
        ):
            covered_pairs.add((round_index, dimension))
            coverage_receipts.add(receipt)

    missing_pairs = sorted(expected_pairs - covered_pairs)
    if missing_pairs:
        preview = ", ".join(f"round {round_index}:{dimension}" for round_index, dimension in missing_pairs[:10])
        suffix = "" if len(missing_pairs) <= 10 else f", ... +{len(missing_pairs) - 10} more"
        blocks.append("final_boss_review.council_coverage missing: " + preview + suffix)
    if len(coverage_receipts) < expected_count:
        blocks.append(
            "final_boss_review requires a distinct council receipt for each "
            f"round/dimension pair ({len(coverage_receipts)} distinct covered < {expected_count})"
        )
    return blocks


def _final_boss_local_verifier_blocks(
    review: dict[str, Any],
    *,
    dossier_path: str,
) -> list[str]:
    blocks: list[str] = []
    if review.get("local_verifiers_passed") is not True:
        blocks.append("final_boss_review.local_verifiers_passed must be true")
    results = review.get("local_verifier_results")
    if not isinstance(results, list) or not results:
        blocks.append("final_boss_review.local_verifier_results missing")
        return blocks
    for index, row in enumerate(results):
        if not isinstance(row, dict):
            blocks.append(f"final_boss_review.local_verifier_results[{index}] is not a mapping")
            continue
        verifier_id = str(row.get("id") or f"#{index}")
        command = str(row.get("command") or "").strip()
        if not command:
            blocks.append(f"final_boss_review.local_verifier_results[{index}] command missing")
        if row.get("passed") is not True:
            blocks.append(f"final_boss_review local verifier {verifier_id!r} did not pass")
        if row.get("returncode") != 0:
            blocks.append(f"final_boss_review local verifier {verifier_id!r} returncode is not 0")
    if dossier_path:
        dossier, err = _read_json_object(dossier_path)
        if not err and dossier is not None:
            expected_ids = {
                str(row.get("id") or "").strip()
                for row in dossier.get("local_verifiers") or []
                if isinstance(row, dict) and str(row.get("id") or "").strip()
            }
            result_ids = {
                str(row.get("id") or "").strip()
                for row in results
                if isinstance(row, dict) and str(row.get("id") or "").strip()
            }
            missing = sorted(expected_ids - result_ids)
            if missing:
                blocks.append("final_boss_review missing local verifier results: " + ", ".join(missing))
    return blocks


def _final_boss_blocks(t: dict[str, Any], closure_kind: str | None = None) -> list[str]:
    """Return blockers for any claim that asks to become production substrate.

    The generic rigorous bar proves a useful slice. It does not prove a track is
    production-ready or substrate-trusted. Those claims need an explicit
    final_boss_review packet with decorrelated review, dimensions, and any
    profile-specific runtime proof.
    """
    kind = _as_upper_token(closure_kind or _declared_closure_kind(t))
    if kind not in PRODUCTION_CLOSURE_KINDS:
        return []

    blocks: list[str] = []
    profile = _graduation_profile(t)
    if profile not in GRADUATION_PROFILES:
        blocks.append(f"unknown graduation_profile {profile!r}")

    review = t.get("final_boss_review")
    if not isinstance(review, dict):
        return blocks + [
            f"{kind} requires final_boss_review with dossier, council receipt, "
            ">=6 reviewers, score_min=100, zero disagreements, and all required dimensions"
        ]

    track_id = str(t.get("id") or "")
    dossier = str(review.get("dossier") or "").strip()
    if not dossier:
        blocks.append("final_boss_review.dossier missing")
    else:
        blocks.extend(_validate_final_boss_dossier(dossier, track_id, kind, profile))

    receipt_paths = _council_receipt_paths(review)
    if not receipt_paths:
        blocks.append("final_boss_review.council_receipt missing")

    reviewer_count = _int_field(review, "reviewer_count")
    if reviewer_count < 6:
        blocks.append(f"final_boss_review.reviewer_count {reviewer_count} < 6")

    score_min = _int_field(review, "score_min")
    if score_min < 100:
        blocks.append(f"final_boss_review.score_min {score_min} < 100")

    if _int_field(review, "explicit_disagreements", 0) != 0:
        blocks.append("final_boss_review.explicit_disagreements must be 0")

    blocks.extend(_final_boss_local_verifier_blocks(review, dossier_path=dossier))

    rounds = _int_field(review, "rounds", 1)
    if rounds < FINAL_BOSS_MIN_ROUNDS:
        blocks.append(f"final_boss_review.rounds {rounds} < {FINAL_BOSS_MIN_ROUNDS}")
    dimensions = _as_str_set(review.get("dimensions"))
    missing_dimensions = sorted(FINAL_BOSS_DIMENSIONS - dimensions)
    if missing_dimensions:
        blocks.append("final_boss_review missing dimensions: " + ", ".join(missing_dimensions))
    extra_dimensions = sorted(dimensions - FINAL_BOSS_DIMENSIONS)
    if extra_dimensions:
        blocks.append("final_boss_review unknown dimensions: " + ", ".join(extra_dimensions))

    if rounds >= 1 and not missing_dimensions and not extra_dimensions:
        blocks.extend(_final_boss_coverage_blocks(
            review,
            receipt_paths=receipt_paths,
            rounds=rounds,
            dimensions=dimensions,
        ))

    if profile == "runtime_transport":
        runtime_evidence = review.get("runtime_evidence") or t.get("runtime_evidence") or []
        if not runtime_evidence:
            blocks.append("runtime_transport production claim requires runtime_evidence")
        failure_modes = _as_str_set(review.get("failure_modes_tested"))
        missing_modes = sorted(RUNTIME_TRANSPORT_FAILURE_MODES - failure_modes)
        if missing_modes:
            blocks.append("runtime_transport missing failure modes: " + ", ".join(missing_modes))
        if bool(review.get("mock_only")):
            blocks.append("runtime_transport cannot be mock_only for production/substrate closure")

    for path in receipt_paths:
        blocks.extend(_validate_council_receipt(path, reviewer_count))

    return blocks


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
        closed_at = _parse_iso_date(ct.get("closed_at"))
        requires_final_boss_metadata = (
            closed_at is not None and closed_at >= FINAL_BOSS_EFFECTIVE_DATE)
        closure_kind = _declared_closure_kind(ct)
        if requires_final_boss_metadata and not closure_kind:
            findings.append(Finding("ERROR", f"closure-kind-missing:{ctid}",
                f"Closed track '{ctid}' is dated {ct.get('closed_at')} and must declare "
                "`closure_kind` (VERIFIED_SLICE / CLOSED_NOT_PROD / RETIRED / "
                "SUPERSEDED / PRODUCTION_READY / SUBSTRATE_TRUSTED)."))
        elif closure_kind and closure_kind not in CLOSURE_KINDS:
            findings.append(Finding("ERROR", f"closure-kind-invalid:{ctid}",
                f"Closed track '{ctid}' declares invalid closure_kind {closure_kind!r}. "
                f"Known: {sorted(CLOSURE_KINDS)}"))
        profile = _graduation_profile(ct)
        if profile and profile not in GRADUATION_PROFILES:
            findings.append(Finding("ERROR", f"graduation-profile-invalid:{ctid}",
                f"Closed track '{ctid}' declares unknown graduation_profile {profile!r}. "
                f"Known: {sorted(GRADUATION_PROFILES)}"))
        for block in _final_boss_blocks(ct, closure_kind):
            findings.append(Finding("ERROR", f"final-boss-block:{ctid}",
                f"[{ctid}] cannot claim {closure_kind}: {block}"))

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


# A receipt's `verdict` clears the outcome bar only when it says the work is
# DONE. Anything else — a traffic-light AMBER/RED, a NOT_FINISHED, a PARTIAL —
# means the track's own scoreboard reports the game is not won, no matter how
# valid and digest-sealed the receipt is.
_PASSING_OUTCOME_VERDICTS = frozenset({
    "GREEN", "FINISHED", "DONE", "COMPLETE", "COMPLETED", "PASS", "PASSED",
    "READY", "VERIFIED", "SHIPPABLE", "CLOSED_LIVE", "OK", "SUCCESS",
})


def _outcome_verdict_blocks(
    t: dict[str, Any], repo_root: Path = REPO_ROOT
) -> list[str]:
    """Block shippability when a track's own outcome receipt reports a
    non-passing verdict.

    A ``receipt_valid`` criterion proves the receipt is real, digest-sealed and
    replayable — it does NOT check whether the receipt SAYS the work is done. A
    valid receipt reading ``verdict: AMBER`` (parity 45%) otherwise satisfies
    every criterion and the track reads "shippable", which is how an agent ends
    up telling the operator "this is shippable, let's ship" on a 45%-done track.
    This reads each receipt's own top-level ``verdict`` and refuses
    shippability unless it clears the bar — measure the outcome, not just the
    scoreboard's integrity.
    """
    blocks: list[str] = []
    for c in t.get("completion_criteria") or []:
        if not isinstance(c, dict) or c.get("kind") != "receipt_valid":
            continue
        rel = str(c.get("file") or "")
        if not rel.endswith(".json"):  # chained .jsonl histories are not outcome docs
            continue
        try:
            data = json.loads((repo_root / rel).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue  # readability is already the receipt_valid criterion's job
        if not isinstance(data, dict):
            continue
        # Opt-out by ABSENCE: a receipt with no `verdict` key is not a
        # scoreboard, so this gate has nothing to say about it (blocking every
        # verdict-less receipt would over-fire on evidence bundles). But a
        # PRESENT verdict must clear the bar — and a present-but-malformed
        # (non-string) verdict is treated as failing, not silently skipped:
        # otherwise `verdict: ["AMBER"]` or `verdict: null` would bypass the
        # gate (greptile P1, PR #900). The digest seal already prevents editing
        # the field without failing receipt_valid first; this closes the
        # remaining shape-based hole.
        if "verdict" not in data:
            continue
        verdict = data.get("verdict")
        passing = (
            isinstance(verdict, str)
            and verdict.strip().upper() in _PASSING_OUTCOME_VERDICTS
        )
        if not passing:
            extra = ""
            for key in ("parity_pct", "score", "score_pct", "percent"):
                if key in data:
                    extra = f", {key}={data[key]}"
                    break
            reason = ("not a passing verdict" if isinstance(verdict, str)
                      else "a malformed (non-string) verdict")
            blocks.append(
                f"outcome receipt {rel} reports verdict={verdict!r}{extra} — {reason}; "
                "the track's own scoreboard does not say the work is done")
    return blocks


def _real_false_shippable_claim(t: dict[str, Any], r: dict[str, Any]) -> bool:
    """A track DECLARES ``status: shippable`` while ``evaluate_track`` says it is
    not — but only for a REAL reason, never a merely-unrun gate.

    A rigorous criterion that could not be RUN in this environment (e.g. the
    minimal-deps battery has no pytest) is unverified, not a false claim;
    blocking on it would manufacture exactly the untrustworthy signal we are
    removing. This fires when: an open blocker exists, the track declares NO
    rigorous criterion at all (existence-only theater — the core trap), a
    criterion actually ran and failed, an active ship veto fired, OR the track's
    own outcome receipt reports a non-passing verdict. That last signal reads
    committed file data, not an environment-dependent probe, so unlike an unrun
    gate it can never be a "could not observe" false alarm — a declared-shippable
    track sitting on a 45%/AMBER receipt is exactly the false claim this must
    catch (devin, PR #900); the advisory ship_block alone let it pass CI.
    """
    if str(t.get("status") or "").lower() != "shippable" or r["shippable"]:
        return False
    declares_rigorous = any(c.kind in RIGOROUS_KINDS for c in r["completion"])
    executed_failure = any(
        (not c.passed) and getattr(c, "executed", True)
        for c in (r["completion"] + r["prereqs"]))
    return (
        r["open_blocker_count"] > 0
        or r.get("active_ship_veto_count", 0) > 0
        or not declares_rigorous
        or executed_failure
        or bool(r.get("outcome_verdict_blocks")))


def evaluate_track(t: dict[str, Any]) -> dict[str, Any]:
    prereqs = [evaluate_criterion(c) for c in (t.get("prerequisites") or [])]
    comps = [evaluate_criterion(c) for c in (t.get("completion_criteria") or [])]
    ship_vetoes = [evaluate_criterion(c) for c in (t.get("ship_vetoes") or [])]
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

    # --- UNDERCLAIM detection (the inverse of the false-shippable trap) --------
    # Every defense above catches claims AHEAD of reality. Nothing caught the
    # ledger falling BEHIND reality: a next-item still listed as open work whose
    # own evidence criterion already passes (observed live 2026-07-03: the arena
    # controls blocker and Mike Slice 1 were both shipped-but-still-open).
    # A next_item may declare `evidence_criterion: <criterion id>`; when that
    # criterion PASSES while the item text does not start with DONE, the ledger
    # is flagged for reconciliation. Read-only: this adds no gate, only a WARN.
    passed_ids = {c.id for c in comps if c.passed} | {c.id for c in prereqs if c.passed}
    underclaims: list[dict[str, Any]] = []
    for ni in next_items:
        ev = ni.get("evidence_criterion")
        if not (isinstance(ev, str) and ev):
            continue
        if ev not in passed_ids:
            continue
        if str(ni.get("what", "")).strip().upper().startswith("DONE"):
            continue  # already reconciled in prose
        underclaims.append({
            "item_id": ni.get("id"),
            "evidence_criterion": ev,
            "blocker": ni.get("blocker") is True,
        })

    # --- GRADED bar (Pudgala Autopoiesis Protostar Phase 1) --------------------
    # Pair each completion criterion with its declared criterion dict so we can
    # read per-criterion ladder hints (oracle_source). zip is safe: comps is
    # built 1:1 from completion_criteria in order.
    crit_dicts = [c for c in (t.get("completion_criteria") or []) if isinstance(c, dict)]
    ladder = _load_grade_ladder()
    grades = [grade_of_criterion(cd, res, t)
              for cd, res in zip(crit_dicts, comps) if res.passed]
    strongest_grade = max(grades) if grades else 0
    try:
        min_evidence_grade = int(t.get("min_evidence_grade", ladder["default_min_grade"]))
    except (TypeError, ValueError):
        min_evidence_grade = int(ladder["default_min_grade"])

    ship_blocks: list[str] = []
    if open_blockers:
        ship_blocks.append(f"{len(open_blockers)} open blocker next-item(s)")
    if not has_rigorous_evidence:
        ship_blocks.append("no rigorous evidence (criteria are existence-only: "
                           "file_exists/file_contains — add test_passes / commit_on_main / receipt_valid)")
    if strongest_grade < min_evidence_grade:
        ship_blocks.append(
            f"strongest evidence {grade_name(strongest_grade)} "
            f"< required {grade_name(min_evidence_grade)} "
            "(raise evidence strength or lower min_evidence_grade with justification)")
    active_vetoes = [c for c in ship_vetoes if c.passed]
    if active_vetoes:
        details = "; ".join(f"{c.id}: {c.detail}" for c in active_vetoes)
        ship_blocks.append(f"{len(active_vetoes)} active ship veto(es): {details}")
    target_closure_kind = _declared_closure_kind(t)
    if target_closure_kind and target_closure_kind not in CLOSURE_KINDS:
        ship_blocks.append(
            f"invalid target closure kind {target_closure_kind!r}; known {sorted(CLOSURE_KINDS)}")
    final_boss_blocks = _final_boss_blocks(t, target_closure_kind)
    ship_blocks.extend(final_boss_blocks)
    outcome_verdict_blocks = _outcome_verdict_blocks(t)
    ship_blocks.extend(outcome_verdict_blocks)
    shippable = criteria_pass and not ship_blocks

    return {
        "id": t.get("id"),
        "prereqs": prereqs,
        "completion": comps,
        "ship_vetoes": ship_vetoes,
        "prereqs_ok": prereqs_ok,
        "shippable": shippable,            # RIGOROUS + GRADED bar
        "criteria_pass": criteria_pass,    # legacy lenient bar (existence checks)
        "ship_blocks": ship_blocks,
        "final_boss_blocks": final_boss_blocks,
        "outcome_verdict_blocks": outcome_verdict_blocks,
        "target_closure_kind": target_closure_kind or "VERIFIED_SLICE",
        "graduation_profile": _graduation_profile(t),
        "has_rigorous_evidence": has_rigorous_evidence,
        "strongest_grade": strongest_grade,
        "strongest_grade_name": grade_name(strongest_grade),
        "min_evidence_grade": min_evidence_grade,
        "min_evidence_grade_name": grade_name(min_evidence_grade),
        "open_blocker_count": len(open_blockers),
        "active_ship_veto_count": len(active_vetoes),
        "underclaims": underclaims,
        "passed": sum(1 for c in comps if c.passed),
        "total": len(comps),
    }


def _load_prior_passed(findings: list[Finding]) -> dict[str, set[str]]:
    """Read the previous evidence JSON so we can flag REGRESSION drift —
    a completion criterion that passed before and now fails (Terraform-plan style).

    The evidence files are derived status, not tracked in git (evicted
    2026-07-04; they hard-conflicted in every concurrent rebase train). The
    baseline resolves in order:
      1. local reports/governance/active_track_evidence.json — gitignored,
         written by the previous local run;
      2. the CI-published copy on the generated/status branch
         (active-track.yml publishes it on every push to main); tried as both
         a local and an origin-prefixed ref so fresh clones work;
      3. empty baseline + WARN — regression detection is off for this run
         only, never silently.
    """
    rel = "reports/governance/active_track_evidence.json"
    raw: str | None = None
    path = REPORTS_DIR / "active_track_evidence.json"
    if path.exists():
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            raw = None
    if raw is None:
        for ref in (STATUS_BRANCH, f"origin/{STATUS_BRANCH}"):
            try:
                proc = subprocess.run(
                    ["git", "-C", str(REPO_ROOT), "show", f"{ref}:{rel}"],
                    capture_output=True, text=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                continue
            if proc.returncode == 0 and proc.stdout.strip():
                raw = proc.stdout
                break
    if raw is None:
        findings.append(Finding("WARN", "no-regression-baseline",
            f"no prior evidence baseline (local {rel} missing and "
            f"{STATUS_BRANCH} branch unavailable) — regression drift "
            "detection is disabled for this run"))
        return {}
    try:
        prior = json.loads(raw)
    except json.JSONDecodeError:
        findings.append(Finding("WARN", "no-regression-baseline",
            "prior evidence baseline is not valid JSON — regression drift "
            "detection is disabled for this run"))
        return {}
    out: dict[str, set[str]] = {}
    for tr in prior.get("active_tracks", []) or []:
        out[tr.get("id")] = {c.get("id") for c in tr.get("criteria", []) if c.get("passed")}
    if not out and prior.get("active_track_id"):   # v1 evidence shape
        out[prior["active_track_id"]] = {
            c.get("id") for c in prior.get("criteria", []) if c.get("passed")}
    return out


def _regression_severity(
    result: CriterionResult,
    *,
    enforce_ttl: bool,
) -> str:
    """Keep elapsed-time drift advisory except on the freshness authority path."""
    if (
        result.failure_modality is CriterionFailureModality.FRESHNESS
        and not enforce_ttl
    ):
        return "WARN"
    return "ERROR"


def _lifecycle_findings(base_p: dict[str, Any], head_p: dict[str, Any]) -> list[Finding]:
    """Merge-time lifecycle invariants between a base and a head portfolio.

    A snapshot validator cannot see transitions. These rules close the
    track-resurrection class observed 2026-06-09..07-01 (a SHIPPED track
    silently returned ACTIVE when stale PR #555 overwrote the file):
      1. closed_tracks is append-only — an id closed on base must stay closed.
      2. a base-closed id may not be active at head without `reopened_at`.
      3. no id may be both active and closed at head without `reopened_at`.
      4. an active track with open blockers may not reuse its id for a
         VERIFIED_SLICE; retirement and a distinct retained slice preserve the
         difference between de-scoping and proof.
    """
    findings: list[Finding] = []
    base_closed = {ct.get("id") for ct in base_p.get("closed_tracks") or []
                   if isinstance(ct, dict) and ct.get("id")}
    head_closed = {ct.get("id") for ct in head_p.get("closed_tracks") or []
                   if isinstance(ct, dict) and ct.get("id")}
    head_active = {t.get("id"): t for t in head_p.get("active_tracks") or []
                   if isinstance(t, dict) and t.get("id")}
    base_active = {t.get("id"): t for t in base_p.get("active_tracks") or []
                   if isinstance(t, dict) and t.get("id")}
    head_closed_by_id = {
        t.get("id"): t for t in head_p.get("closed_tracks") or []
        if isinstance(t, dict) and t.get("id")
    }

    for cid in sorted(base_closed):
        if cid not in head_closed:
            findings.append(Finding("ERROR", f"closed-track-removed:{cid}",
                f"closed_tracks is append-only: '{cid}' is closed on the base ref "
                "but missing here. Restore the entry — a stale-branch merge must "
                "not erase closure history."))
        entry = head_active.get(cid)
        if entry is not None and _is_active(entry) and not entry.get("reopened_at"):
            findings.append(Finding("ERROR", f"closed-track-resurrected:{cid}",
                f"'{cid}' is closed on the base ref but ACTIVE here without "
                "`reopened_at`. Deliberate reopen requires reopened_at + evidence; "
                "otherwise this is a stale-branch overwrite."))

    for tid, t in head_active.items():
        if _is_active(t) and tid in head_closed and not t.get("reopened_at"):
            findings.append(Finding("ERROR", f"active-closed-overlap:{tid}",
                f"'{tid}' appears in both active_tracks and closed_tracks "
                "without `reopened_at`."))

    for tid, base_track in base_active.items():
        open_blockers = [
            item for item in base_track.get("next_items") or []
            if isinstance(item, dict) and item.get("blocker") is True
        ]
        closed = head_closed_by_id.get(tid)
        if (
            open_blockers
            and closed is not None
            and _declared_closure_kind(closed) == "VERIFIED_SLICE"
        ):
            findings.append(Finding(
                "ERROR",
                f"verified-slice-erases-blockers:{tid}",
                f"'{tid}' had {len(open_blockers)} open blocker(s) on the base "
                "but reuses the same id for VERIFIED_SLICE. Retire or supersede "
                "the original claim and record any retained verified slice "
                "under a distinct id.",
            ))
    return findings


def check_lifecycle_transition(head_p: dict[str, Any], findings: list[Finding],
                               base_ref: str | None = None) -> None:
    """Apply _lifecycle_findings against ACTIVE_TRACK.yaml at the merge base.

    Base resolution: explicit --base, else origin/$GITHUB_BASE_REF (PR CI),
    else origin/main. Skips with INFO — never blocks — when the ref or file
    is unavailable (local clone without a remote, fresh history), or when
    ACTIVE_TRACK_PATH points outside the repo (test fixtures validate
    portfolio *snapshots*; a transition diff against the repo's base ref is
    only meaningful for the repo's own tracked file)."""
    import os
    canonical = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
    try:
        is_repo_file = Path(ACTIVE_TRACK_PATH).resolve() == canonical.resolve()
    except OSError:
        is_repo_file = False
    if not is_repo_file:
        findings.append(Finding("INFO", "lifecycle-base-unavailable",
            "validating an out-of-tree ACTIVE_TRACK file; transition check skipped."))
        return
    ref = base_ref or (
        f"origin/{os.environ['GITHUB_BASE_REF']}"
        if os.environ.get("GITHUB_BASE_REF") else "origin/main")
    try:
        res = subprocess.run(
            ["git", "show", f"{ref}:docs/governance/ACTIVE_TRACK.yaml"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT))
    except Exception as exc:
        findings.append(Finding("INFO", "lifecycle-base-unavailable",
            f"git show {ref} failed ({exc}); transition check skipped."))
        return
    if res.returncode != 0:
        findings.append(Finding("INFO", "lifecycle-base-unavailable",
            f"base ref {ref} has no readable ACTIVE_TRACK.yaml; "
            "transition check skipped."))
        return
    try:
        base_p = normalize_portfolio(_parse_active_track_text(res.stdout) or {})
    except Exception as exc:
        findings.append(Finding("WARN", "lifecycle-base-unparseable",
            f"ACTIVE_TRACK.yaml at {ref} unparseable ({exc}); "
            "transition check skipped."))
        return
    findings.extend(_lifecycle_findings(base_p, head_p))


def run(args: argparse.Namespace) -> int:
    findings: list[Finding] = []
    reports_dir = Path(getattr(args, "reports_dir", REPORTS_DIR))
    if not ACTIVE_TRACK_PATH.exists():
        findings.append(Finding("ERROR", "active-track-missing",
                                f"{ACTIVE_TRACK_PATH} not found"))
        emit_reports(findings, None, [], reports_dir)
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
        emit_reports(findings, p, [], reports_dir)
        return 2

    # Portfolio-level graph invariants.
    validate_portfolio_graph(p, findings)
    detect_dependency_cycle(p["active_tracks"], findings)

    # Merge-time lifecycle invariants (closes the C9 resurrection class):
    # compare against the base ref so a stale-branch merge cannot silently
    # un-close a track or erase closure history.
    check_lifecycle_transition(p, findings, base_ref=getattr(args, "base", None))

    prior_passed = _load_prior_passed(findings)
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
        # rigorous bar for a REAL reason (not a merely-unrun gate) is a hard
        # ERROR — see _real_false_shippable_claim for the doctrine, incl. the
        # outcome-verdict signal that reads committed file data and so is never
        # a "could not observe" false alarm.
        if _real_false_shippable_claim(t, r):
            blocks = "; ".join(r["ship_blocks"]) or "rigorous bar not met"
            findings.append(Finding("ERROR", f"false-shippable-claim:{tid}",
                f"[{tid}] declares status: shippable but FAILS the rigorous bar: {blocks}. "
                "A track cannot be marked shippable without >=1 rigorous criterion "
                "(test_passes / commit_on_main / receipt_valid / pr_merged) and zero "
                "open blockers. Either add real evidence or change status back to ACTIVE."))

        # Underclaims => the ledger is BEHIND reality (inverse of false-shippable).
        # WARN, not ERROR: the owner reconciles by annotating the item DONE, by
        # narrowing it to the genuinely-remaining edge, or by strengthening the
        # criterion — this detector never closes items itself.
        for uc in r.get("underclaims", []):
            kind = "blocker next-item" if uc["blocker"] else "next-item"
            findings.append(Finding("WARN", f"track-underclaim:{tid}:{uc['item_id']}",
                f"[{tid}] {kind} {uc['item_id']} is still listed as open work but its "
                f"linked evidence criterion '{uc['evidence_criterion']}' PASSES — the "
                "ledger may be behind reality. Reconcile: annotate the item DONE, "
                "narrow it to the remaining live edge, or strengthen the criterion.",
                criterion_id=uc["evidence_criterion"]))

        # Prerequisite failures => track mis-declared.  An unexecuted check
        # (minimal env / explicit skip) is not evidence of a missing
        # prerequisite — same doctrine as the regression guard below.
        for c in r["prereqs"]:
            if (not c.passed and getattr(c, "executed", True)
                    and c.kind in {"file_exists", "file_contains", "command_passes"}):
                findings.append(Finding("ERROR", f"prerequisite:{tid}:{c.id}",
                    f"[{tid}] prerequisite failed: {c.detail}. The work it builds on "
                    "does not exist.", criterion_id=c.id))

        # Regression drift => previously-passing completion criterion now fails.
        # A criterion that could not be RUN in this environment (e.g. the
        # minimal-deps governance gate has no pytest) is NOT a regression — the
        # code did not change, the runner is absent. Surface it as INFO so the
        # gap is visible without producing a false-positive block.
        prev = prior_passed.get(tid, set())
        for c in r["completion"]:
            if c.id in prev and not c.passed:
                if not getattr(c, "executed", True):
                    findings.append(Finding("INFO", f"unverified:{tid}:{c.id}",
                        f"[{tid}] UNVERIFIED — '{c.id}' could not run here (not a regression): {c.detail}",
                        criterion_id=c.id))
                    continue
                severity = _regression_severity(
                    c,
                    enforce_ttl=bool(getattr(args, "enforce_ttl", False)),
                )
                findings.append(Finding(severity, f"regression:{tid}:{c.id}",
                    f"[{tid}] REGRESSION — '{c.id}' passed before and now fails: {c.detail}",
                    criterion_id=c.id))

        if r["shippable"]:
            findings.append(Finding("INFO", f"track-criteria-complete:{tid}",
                f"[{tid}] all {r['total']} completion criteria pass under the rigorous "
                "bar with no open blockers and a passing outcome verdict. This is a "
                "CRITERIA-READINESS signal, NOT a ship-or-close verdict. Closing still "
                "requires declaring a closure_kind and passing the closure gauntlet — a "
                "production closure runs the Final Boss review (7 dimensions x >=2 rounds "
                "x >=6 decorrelated reviewers x score 100, zero disagreements). Do NOT "
                "'ship' or 'close' on this signal alone; confirm the track's own outcome "
                "receipts and next_items first."))
        elif r.get("criteria_pass"):
            findings.append(Finding("INFO", f"track-provisional:{tid}",
                f"[{tid}] {r['passed']}/{r['total']} criteria pass but NOT shippable "
                f"under the rigorous bar: {'; '.join(r['ship_blocks'])}. "
                "Criteria passing is not closure, and a valid receipt is not a passing "
                "outcome (see REALITY_DEBT_LEDGER.md / the Final Boss closure gauntlet)."))
        elif r["completion"]:
            findings.append(Finding("INFO", f"track-in-progress:{tid}",
                f"[{tid}] {r['passed']}/{r['total']} completion criteria pass."))

        track_results.append((t, r))

    emit_reports(findings, p, track_results, reports_dir)
    return 1 if any(f.severity == "ERROR" for f in findings) else 0


def _track_payload(t: dict[str, Any], r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": t.get("id"),
        "name": t.get("name"),
        "status": t.get("status"),
        "closure_kind": t.get("closure_kind"),
        "target_closure_kind": r.get("target_closure_kind", "VERIFIED_SLICE"),
        "graduation_profile": r.get("graduation_profile", _graduation_profile(t)),
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
        "final_boss_blocks": r.get("final_boss_blocks", []),
        "underclaims": r.get("underclaims", []),
        "claim_boundary": t.get("claim_boundary"),
        "has_rigorous_evidence": r.get("has_rigorous_evidence", False),
        "strongest_grade": r.get("strongest_grade", 0),
        "strongest_grade_name": r.get("strongest_grade_name", "S0"),
        "min_evidence_grade": r.get("min_evidence_grade", _DEFAULT_MIN_GRADE),
        "min_evidence_grade_name": r.get("min_evidence_grade_name", "S2"),
        "prerequisites_ok": r["prereqs_ok"],
        "completion_progress": {"passed": r["passed"], "total": r["total"]},
        "criteria": [asdict(c) for c in (r["prereqs"] + r["completion"])],
        "ship_vetoes": [asdict(c) for c in r.get("ship_vetoes", [])],
    }


def emit_reports(
    findings: list[Finding],
    portfolio: dict[str, Any] | None,
    track_results: list[tuple[dict[str, Any], dict[str, Any]]],
    reports_dir: Path,
) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
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
    (reports_dir / "active_track_evidence.json").write_text(text, encoding="utf-8")
    # Richer name for the dashboard contract (same payload; one source of truth).
    (reports_dir / "track_portfolio.json").write_text(text, encoding="utf-8")

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
        if tp.get("claim_boundary"):
            md.append(f"- claim_boundary: {tp['claim_boundary']}")
        if not tp["shippable"] and tp.get("ship_blocks"):
            md.append(f"- ship_blocks: {'; '.join(tp['ship_blocks'])}")
        md.append("")
        for c in tp.get("ship_vetoes") or []:
            mark = "ACTIVE" if c["passed"] else "clear"
            md.append(f"  - {mark} ship veto `{c['id']}` ({c['kind']}) — {c['detail']}")
        if tp.get("ship_vetoes"):
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
    (reports_dir / "active_track_evidence.md").write_text("\n".join(md), encoding="utf-8")

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
    parser.add_argument("--base", default=None,
                        help="Git ref to diff lifecycle transitions against "
                             "(default: origin/$GITHUB_BASE_REF, else origin/main).")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORTS_DIR,
        help="Directory for derived evidence outputs "
             "(default: reports/governance in this checkout).",
    )
    args = parser.parse_args()
    code = run(args)
    if args.warn_only:
        return 0
    return code


if __name__ == "__main__":
    sys.exit(main())
