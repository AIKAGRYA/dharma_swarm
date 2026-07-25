#!/usr/bin/env python3
"""CI parity guard — required-check set vs live branch protection.

Honest survivor of the dead TLA+ merge-pipeline idea. The literal claim
(a formal model of the merge pipeline is worth building) was self-refuted:
the model is a map, not the territory, and the territory can drift out from
under it. What survives is a check whose oracle is external and checkable:
the live GitHub branch-protection JSON plus the workflow YAML on disk.

This gate asserts three things and exits non-zero on any drift:

  1. Parity. The required-status-check contexts declared in the committed
     expected-guard manifest EQUAL the ``required_status_checks.contexts``
     GitHub is actually enforcing on the protected branch. A manifest that
     drifts away from live protection (a context added, dropped, or renamed
     on either side) turns the check red. The manifest is the human-readable
     intent; branch protection is ground truth; they must agree.

  2. Producing-job integrity. Every required context maps to a real job in a
     workflow file, and that job's effective check name still matches the
     context (a job rename that would silently orphan a required context is
     drift).

  3. Structural false-green defenses on required jobs:
       * a job-level ``continue-on-error: true`` on any required job — the
         "structurally cannot fail" bug (a required check that can never go
         red is a false-green sensor);
       * ANY ``continue-on-error: true`` (job or step) on a
         regression-sensitive required job — such a gate must be able to fail
         hard everywhere, because a base change can regress it;
       * a ``github.event_name != 'merge_group'`` self-skip on a
         regression-sensitive required job — the job would be reported
         "skipped = satisfied" in the merge queue, blind to a regression the
         base change introduces after the PR run went green.

Dead ``merge_group:`` triggers (a workflow subscribed to ``merge_group`` whose
every job self-skips on ``merge_group``, so the trigger can never run work)
are surfaced as WARNINGS. They are coherence noise, not a false-green risk, so
they do not fail the gate by default.

Oracle: ``gh api repos/<slug>/branches/<branch>/protection`` (external,
checkable) + ``.github/workflows/*.yml`` (in-repo, checkable). No modelling of
the merge pipeline — only assertions against observable facts.

Usage:
    # Compare the committed manifest against a protection JSON on disk / stdin
    python3 scripts/governance/check_ci_parity.py \
        --protection-json protection.json

    # Fetch live protection itself (needs a token with Administration: read)
    python3 scripts/governance/check_ci_parity.py --live

    # Structural checks only when no protection source is available (CI
    # fallback until an Administration:read token is provisioned). Prints a
    # loud "PARITY NOT VERIFIED" notice; never claims parity passed.
    python3 scripts/governance/check_ci_parity.py --allow-missing-live

Exit codes:
    0   aligned (or structural-only run with no structural drift)
    1   drift detected
    2   environment error (no protection source and live not allowed to miss)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------
# Minimal YAML-subset parser (stdlib-only). Handles the block mappings, block
# sequences, block scalars (| and >), quoted scalars, and flow sequences that
# GitHub Actions workflow files use. It is deliberately scoped to that subset;
# it is not a general YAML implementation.
# --------------------------------------------------------------------------


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _strip_inline_comment(value: str) -> str:
    """Drop a trailing ``# ...`` comment that is outside any quotes."""
    in_single = in_double = False
    for i, ch in enumerate(value):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or value[i - 1] in " \t":
                return value[:i].rstrip()
    return value.rstrip()


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _parse_flow_seq(value: str) -> list[str]:
    inner = value.strip()[1:-1]
    if not inner.strip():
        return []
    return [_unquote(part) for part in inner.split(",")]


def _parse_block(lines: list[tuple[int, str, int]], start: int, indent: int,
                 end: int) -> tuple[Any, int]:
    """Parse a block (mapping or sequence) whose children sit at ``indent``.

    ``lines`` is a list of ``(indent, text, original_lineno)`` for non-blank,
    non-comment-only lines. Returns ``(value, next_index)``.
    """
    # Decide mapping vs sequence by the first child line.
    i = start
    while i < end and lines[i][0] < indent:
        i = i + 1
    if i >= end or lines[i][0] != indent:
        return None, start
    is_seq = lines[i][1].lstrip().startswith("- ") or lines[i][1].strip() == "-"

    if is_seq:
        seq: list[Any] = []
        i = start
        while i < end:
            cur_indent, text, _ = lines[i]
            if cur_indent < indent:
                break
            if cur_indent > indent:
                i = i + 1
                continue
            stripped = text.strip()
            if not stripped.startswith("-"):
                break
            remainder = stripped[1:].strip()
            if remainder == "":
                child, i = _parse_block(lines, i + 1, indent + 2, end)
                seq.append(child)
                continue
            # Inline item. If it looks like "key: ...", treat the dash line as
            # the first entry of a mapping whose keys align at the column just
            # after the dash.
            child_indent = cur_indent + (len(text) - len(text.lstrip()) - cur_indent) + 2
            synthetic = " " * child_indent + remainder
            lines2 = lines[:i] + [(child_indent, synthetic, lines[i][2])] + lines[i + 1:]
            if ":" in remainder and not remainder.startswith("{"):
                child, ni = _parse_block(lines2, i, child_indent, end)
                seq.append(child)
                i = ni
            else:
                seq.append(_unquote(remainder))
                i = i + 1
        return seq, i

    mapping: dict[str, Any] = {}
    i = start
    while i < end:
        cur_indent, text, _ = lines[i]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            i = i + 1
            continue
        stripped = text.strip()
        if stripped.startswith("- "):
            break
        if ":" not in stripped:
            i = i + 1
            continue
        key, _, rawval = stripped.partition(":")
        key = _unquote(key.strip())
        val = _strip_inline_comment(rawval).strip()
        if val in ("|", ">", "|-", ">-", "|+", ">+"):
            # Block scalar: gather deeper lines as raw text.
            scalar_lines: list[str] = []
            j = i + 1
            while j < end and (lines[j][0] > indent):
                scalar_lines.append(lines[j][1][indent + 2:] if len(lines[j][1]) > indent + 2 else lines[j][1].strip())
                j = j + 1
            mapping[key] = "\n".join(scalar_lines)
            i = j
        elif val.startswith("[") and val.endswith("]"):
            mapping[key] = _parse_flow_seq(val)
            i = i + 1
        elif val == "":
            # Nested block, or an empty value (key with nothing under it).
            j = i + 1
            while j < end and lines[j][0] > indent:
                j = j + 1
            if j > i + 1:
                child, _ = _parse_block(lines, i + 1, lines[i + 1][0], end)
                mapping[key] = child
                i = j
            else:
                mapping[key] = None
                i = i + 1
        else:
            mapping[key] = _unquote(val)
            i = i + 1
    return mapping, i


def parse_yaml(text: str) -> dict[str, Any]:
    raw_lines = text.splitlines()
    lines: list[tuple[int, str, int]] = []
    in_scalar_indent: int | None = None
    for lineno, raw in enumerate(raw_lines):
        if raw.strip() == "":
            continue
        indent = _indent_of(raw)
        # Keep comment-only lines out of the structural stream, but never
        # discard a line that belongs to an active block scalar body.
        if in_scalar_indent is not None and indent > in_scalar_indent:
            lines.append((indent, raw, lineno))
            continue
        in_scalar_indent = None
        if raw.lstrip().startswith("#"):
            continue
        content = _strip_inline_comment(raw.lstrip())
        if content == "":
            continue
        # Detect the start of a block scalar to protect its body lines.
        if content.rstrip().endswith(("|", ">", "|-", ">-", "|+", ">+")):
            in_scalar_indent = indent
        lines.append((indent, " " * indent + content, lineno))
    if not lines:
        return {}
    result, _ = _parse_block(lines, 0, 0, len(lines))
    return result if isinstance(result, dict) else {}


# --------------------------------------------------------------------------
# Workflow model
# --------------------------------------------------------------------------


@dataclass
class Step:
    name: str
    if_text: str
    continue_on_error: bool


@dataclass
class Job:
    job_id: str
    name: str
    if_text: str
    continue_on_error: bool
    steps: list[Step] = field(default_factory=list)
    has_matrix: bool = False

    @property
    def effective_base_name(self) -> str:
        return self.name if self.name else self.job_id

    def self_skips_merge_group(self) -> bool:
        return _is_merge_group_self_skip(self.if_text)


@dataclass
class Workflow:
    path: Path
    name: str
    triggers: set[str]
    jobs: dict[str, Job]


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _is_merge_group_self_skip(if_text: str) -> bool:
    if not if_text:
        return False
    flat = " ".join(if_text.split())
    return (
        "github.event_name != 'merge_group'" in flat
        or 'github.event_name != "merge_group"' in flat
    )


def _extract_triggers(on_value: Any) -> set[str]:
    if on_value is None:
        return set()
    if isinstance(on_value, str):
        return {on_value.strip()}
    if isinstance(on_value, list):
        return {str(v).strip() for v in on_value}
    if isinstance(on_value, dict):
        return {str(k).strip() for k in on_value.keys()}
    return set()


def load_workflow(path: Path) -> Workflow:
    doc = parse_yaml(path.read_text(encoding="utf-8"))
    # 'on' may be parsed as the string key 'on' or, per YAML 1.1, as bool True.
    on_value = doc.get("on")
    if on_value is None and True in doc:
        on_value = doc.get(True)
    triggers = _extract_triggers(on_value)
    jobs_raw = doc.get("jobs") or {}
    jobs: dict[str, Job] = {}
    if isinstance(jobs_raw, dict):
        for job_id, body in jobs_raw.items():
            if not isinstance(body, dict):
                continue
            steps: list[Step] = []
            steps_raw = body.get("steps") or []
            if isinstance(steps_raw, list):
                for st in steps_raw:
                    if not isinstance(st, dict):
                        continue
                    steps.append(
                        Step(
                            name=str(st.get("name", "")),
                            if_text=str(st.get("if", "") or ""),
                            continue_on_error=_as_bool(st.get("continue-on-error", False)),
                        )
                    )
            strategy = body.get("strategy") or {}
            has_matrix = isinstance(strategy, dict) and "matrix" in strategy
            jobs[str(job_id)] = Job(
                job_id=str(job_id),
                name=str(body.get("name", "") or ""),
                if_text=str(body.get("if", "") or ""),
                continue_on_error=_as_bool(body.get("continue-on-error", False)),
                steps=steps,
                has_matrix=has_matrix,
            )
    return Workflow(
        path=path,
        name=str(doc.get("name", path.stem)),
        triggers=triggers,
        jobs=jobs,
    )


# --------------------------------------------------------------------------
# Protection JSON + manifest
# --------------------------------------------------------------------------


def actual_contexts_from_protection(protection: dict[str, Any]) -> set[str]:
    rsc = protection.get("required_status_checks") or {}
    contexts = rsc.get("contexts")
    if contexts:
        return {str(c) for c in contexts}
    checks = rsc.get("checks") or []
    return {str(c.get("context")) for c in checks if c.get("context")}


def fetch_live_protection(repo: str, branch: str) -> dict[str, Any]:
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/branches/{branch}/protection"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "gh api branch-protection fetch failed "
            f"(rc={result.returncode}): {result.stderr.strip()}"
        )
    return json.loads(result.stdout)


def _context_base_name(context: str) -> str:
    """Strip a trailing matrix suffix ``ctx (a, b)`` -> ``ctx``."""
    if context.endswith(")") and " (" in context:
        return context[: context.rindex(" (")]
    return context


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------


@dataclass
class Report:
    drift: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parity_verified: bool = False


def run_check(
    manifest: dict[str, Any],
    workflows_dir: Path,
    protection: dict[str, Any] | None,
) -> Report:
    report = Report()
    entries = manifest.get("required_contexts") or []
    expected_contexts = {str(e["context"]) for e in entries}

    # (1) Parity: manifest vs live protection.
    if protection is not None:
        report.parity_verified = True
        actual = actual_contexts_from_protection(protection)
        missing = sorted(actual - expected_contexts)
        extra = sorted(expected_contexts - actual)
        for ctx in missing:
            report.drift.append(
                f"PARITY: context '{ctx}' is REQUIRED by branch protection "
                f"but absent from the expected-guard manifest"
            )
        for ctx in extra:
            report.drift.append(
                f"PARITY: context '{ctx}' is declared required in the manifest "
                f"but NOT enforced by branch protection"
            )

    # Load referenced workflows once.
    wf_cache: dict[str, Workflow] = {}

    def _load(wf_name: str) -> Workflow | None:
        if wf_name in wf_cache:
            return wf_cache[wf_name]
        wf_path = workflows_dir / wf_name
        if not wf_path.exists():
            return None
        wf = load_workflow(wf_path)
        wf_cache[wf_name] = wf
        return wf

    # (2) + (3) Producing-job integrity and structural false-green defenses.
    for entry in entries:
        context = str(entry["context"])
        wf_name = str(entry.get("workflow", ""))
        job_id = str(entry.get("job", ""))
        regression_sensitive = bool(entry.get("regression_sensitive", False))

        wf = _load(wf_name)
        if wf is None:
            report.drift.append(
                f"MAPPING: context '{context}' points at workflow "
                f"'{wf_name}' which does not exist under {workflows_dir}"
            )
            continue
        job = wf.jobs.get(job_id)
        if job is None:
            report.drift.append(
                f"MAPPING: context '{context}' points at job '{job_id}' in "
                f"'{wf_name}' which does not exist (available: "
                f"{sorted(wf.jobs)})"
            )
            continue

        if job.effective_base_name != _context_base_name(context):
            report.drift.append(
                f"MAPPING: context '{context}' expects producing job named "
                f"'{_context_base_name(context)}' but job '{job_id}' in "
                f"'{wf_name}' now renders as '{job.effective_base_name}'"
            )

        if job.continue_on_error:
            report.drift.append(
                f"FALSE-GREEN: required job '{job_id}' ({context}) in "
                f"'{wf_name}' has job-level continue-on-error: true — it can "
                f"never report failure"
            )

        if regression_sensitive:
            for st in job.steps:
                if st.continue_on_error:
                    report.drift.append(
                        f"FALSE-GREEN: regression-sensitive required job "
                        f"'{job_id}' ({context}) in '{wf_name}' has step "
                        f"'{st.name}' with continue-on-error: true — a "
                        f"base-change regression here would be swallowed"
                    )
            if job.self_skips_merge_group():
                report.drift.append(
                    f"MERGE-QUEUE-BLIND: regression-sensitive required job "
                    f"'{job_id}' ({context}) in '{wf_name}' self-skips on "
                    f"merge_group (if: github.event_name != 'merge_group'); a "
                    f"base change would be reported skipped=satisfied"
                )
        else:
            # Best-effort steps on a non-regression-sensitive gate are
            # allowed, but surface them so the classification stays honest.
            for st in job.steps:
                if st.continue_on_error:
                    report.warnings.append(
                        f"required job '{job_id}' ({context}) in '{wf_name}' "
                        f"has best-effort step '{st.name}' (continue-on-error) "
                        f"— allowed because the context is not regression-"
                        f"sensitive; verify the terminal gate step still fails"
                    )

    # Dead merge_group triggers (warning tier).
    for wf in wf_cache.values():
        if "merge_group" not in wf.triggers:
            continue
        if not wf.jobs:
            continue
        if all(job.self_skips_merge_group() for job in wf.jobs.values()):
            report.warnings.append(
                f"DEAD-TRIGGER: workflow '{wf.path.name}' subscribes to "
                f"merge_group but every job self-skips on merge_group — the "
                f"trigger can never run work"
            )

    return report


def _load_protection_arg(args: argparse.Namespace, manifest: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Return (protection_dict_or_None, env_error_or_None)."""
    if args.protection_json:
        if args.protection_json == "-":
            return json.loads(sys.stdin.read()), None
        return json.loads(Path(args.protection_json).read_text(encoding="utf-8")), None
    if args.live:
        repo = args.repo or manifest.get("repo", "")
        branch = args.branch or manifest.get("branch", "main")
        if not repo:
            return None, "no repo slug (pass --repo or set 'repo' in manifest)"
        try:
            return fetch_live_protection(repo, branch), None
        except Exception as exc:  # noqa: BLE001 - surface any fetch failure
            return None, f"live protection fetch failed: {exc}"
    return None, "no protection source"


def main(argv: list[str] | None = None) -> int:
    default_manifest = Path(__file__).resolve().parent / "ci_parity_manifest.json"
    default_workflows = Path(__file__).resolve().parents[2] / ".github" / "workflows"
    parser = argparse.ArgumentParser(description="CI parity guard")
    parser.add_argument("--manifest", default=str(default_manifest))
    parser.add_argument("--workflows-dir", default=str(default_workflows))
    parser.add_argument(
        "--protection-json",
        help="path to a branch-protection JSON, or '-' for stdin",
    )
    parser.add_argument("--live", action="store_true", help="fetch live protection via gh api")
    parser.add_argument("--repo", help="owner/name (overrides manifest 'repo')")
    parser.add_argument("--branch", help="protected branch (overrides manifest 'branch')")
    parser.add_argument(
        "--allow-missing-live",
        action="store_true",
        help="run structural checks only when no protection source is available",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    workflows_dir = Path(args.workflows_dir)

    protection, env_error = _load_protection_arg(args, manifest)
    if protection is None and not args.allow_missing_live:
        print(f"ci-parity: environment error — {env_error}", file=sys.stderr)
        return 2

    report = run_check(manifest, workflows_dir, protection)

    if args.json:
        print(json.dumps({
            "parity_verified": report.parity_verified,
            "drift": report.drift,
            "warnings": report.warnings,
        }, indent=2))
    else:
        if not report.parity_verified:
            print(
                "ci-parity: NOTICE — live branch-protection parity NOT "
                "verified (no protection source); structural checks only.\n"
                "Provision an Administration:read token and run with --live "
                "to enforce parity."
            )
        for w in report.warnings:
            print(f"ci-parity: warning: {w}")
        if report.drift:
            print("\nci-parity: DRIFT DETECTED")
            for d in report.drift:
                print(f"  - {d}")
        else:
            scope = "parity + structure" if report.parity_verified else "structure"
            print(f"ci-parity: OK ({scope} aligned)")

    return 1 if report.drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
