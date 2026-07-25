#!/usr/bin/env python3
"""Check risk-triggered AgentOps packet scope for one CI event range.

This checker proves one narrow proposition: when a pull request or merge group
changes a path already classified as hot by Merge Master Mike, changed Session
Entry packets cover the governed event paths exactly once and forbid none of
the event.  It does not attest that local preflight/closeout ran, execute
packet-declared gates, or grant merge authority.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.onboarding.contract import (  # noqa: E402
    detect_surface_collisions,
    matching_patterns,
    parse_work_packet,
)
from dharma_swarm.operator_core.onboarding.models import (  # noqa: E402
    AgentOpsError,
    WorkPacket,
)
PACKET_PREFIX = "reports/agentops/work_packets/"
RISK_POLICY_PATH = "scripts/runtime/pr_merge_control.py"
LIVE_TRACK_STATUSES = frozenset({"ACTIVE", "SHIPPABLE"})
EVENT_NAMES = frozenset({"pull_request", "merge_group"})
SHA_RE = re.compile(r"[0-9a-f]{40}")
SCHEMA = "dharma.agentops_packet_scope.v1"


class PacketScopeError(ValueError):
    """The CI event or repository state cannot be evaluated safely."""


@dataclass(frozen=True)
class PacketBinding:
    path: str
    packet: WorkPacket


def _git(
    repo_root: Path,
    args: list[str],
    *,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    result = subprocess.run(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            *args,
        ],
        cwd=repo_root,
        capture_output=True,
        text=text,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode("utf-8", "replace")
        stdout = result.stdout if text else result.stdout.decode("utf-8", "replace")
        raise PacketScopeError(f"git {' '.join(args)} failed: {(stderr or stdout).strip()}")
    return result


def _exact_commit(repo_root: Path, value: str, *, field: str) -> str:
    if SHA_RE.fullmatch(value) is None:
        raise PacketScopeError(f"{field} must be an exact lowercase 40-character SHA")
    result = _git(repo_root, ["rev-parse", "--verify", f"{value}^{{commit}}"])
    if result.stdout.strip() != value:
        raise PacketScopeError(f"{field} does not resolve exactly: {value}")
    return value


def _nul_paths(repo_root: Path, args: list[str]) -> list[str]:
    raw = _git(repo_root, args, text=False).stdout
    if not raw:
        return []
    if not raw.endswith(b"\0"):
        raise PacketScopeError("Git pathname output was not NUL terminated")
    try:
        paths = [part.decode("utf-8", "strict") for part in raw[:-1].split(b"\0")]
    except UnicodeDecodeError as exc:
        raise PacketScopeError("Git reported a non-UTF-8 path") from exc
    for path in paths:
        components = path.split("/")
        if (
            not path
            or path.startswith("/")
            or "\\" in path
            or any(component in {"", ".", ".."} for component in components)
        ):
            raise PacketScopeError(f"Git reported an unsafe path: {path!r}")
    return paths


def _changed_paths(
    repo_root: Path,
    *,
    event_name: str,
    event_base: str,
    event_head: str,
) -> tuple[str, list[str]]:
    if event_name not in EVENT_NAMES:
        raise PacketScopeError(f"unsupported event name: {event_name}")
    base = _exact_commit(repo_root, event_base, field="event base")
    head = _exact_commit(repo_root, event_head, field="event head")
    checked_out = _git(repo_root, ["rev-parse", "HEAD"]).stdout.strip()
    if checked_out != head:
        raise PacketScopeError(
            f"checked-out HEAD {checked_out} does not equal declared event head {head}"
        )
    if _git(repo_root, ["status", "--porcelain"], check=True).stdout:
        raise PacketScopeError("packet-scope evaluation requires a clean checkout")

    if event_name == "pull_request":
        diff_base = _git(repo_root, ["merge-base", base, head]).stdout.strip()
        diff_base = _exact_commit(repo_root, diff_base, field="pull-request merge base")
    else:
        ancestry = _git(
            repo_root, ["merge-base", "--is-ancestor", base, head], check=False
        )
        if ancestry.returncode != 0:
            raise PacketScopeError("merge-group base is not an ancestor of its head")
        diff_base = base

    paths = _nul_paths(
        repo_root,
        [
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--no-renames",
            "--name-only",
            "-z",
            f"{diff_base}..{head}",
            "--",
        ],
    )
    return diff_base, sorted(set(paths))


def _hot_patterns_at(repo_root: Path, commit: str) -> tuple[str, ...]:
    """Read Mike's literal policy at one commit without executing event code."""
    raw = _git(repo_root, ["show", f"{commit}:{RISK_POLICY_PATH}"], text=False).stdout
    try:
        module = ast.parse(raw.decode("utf-8"), filename=f"{commit}:{RISK_POLICY_PATH}")
    except (UnicodeError, SyntaxError) as exc:
        raise PacketScopeError(f"cannot parse risk policy at {commit}: {exc}") from exc
    for node in module.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "HOT_PATH_PATTERNS" for target in targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (TypeError, ValueError) as exc:
            raise PacketScopeError("HOT_PATH_PATTERNS must remain a literal sequence") from exc
        if not isinstance(value, (list, tuple)) or not value or not all(
            isinstance(pattern, str) and pattern for pattern in value
        ):
            raise PacketScopeError("HOT_PATH_PATTERNS must be a non-empty string sequence")
        return tuple(value)
    raise PacketScopeError(f"HOT_PATH_PATTERNS is absent from {commit}:{RISK_POLICY_PATH}")


def is_hot_path(path: str, patterns: Iterable[str]) -> bool:
    """Apply Mike's existing prefix semantics to one event path."""
    return any(path == pattern or path.startswith(pattern) for pattern in patterns)


def _git_blob(repo_root: Path, commit: str, path: str) -> bytes:
    rows = _nul_paths(
        repo_root,
        ["ls-tree", "-z", commit, "--", path],
    )
    if len(rows) != 1:
        raise PacketScopeError(f"packet is absent or ambiguous at event head: {path}")
    metadata, separator, observed_path = rows[0].partition("\t")
    fields = metadata.split()
    if (
        not separator
        or observed_path != path
        or len(fields) != 3
        or fields[0] != "100644"
        or fields[1] != "blob"
    ):
        raise PacketScopeError(f"packet must be a regular 100644 event-head blob: {path}")
    return _git(repo_root, ["show", f"{commit}:{path}"], text=False).stdout


def _track_rows(repo_root: Path, commit: str) -> list[dict[str, Any]]:
    raw = _git(
        repo_root,
        ["show", f"{commit}:docs/governance/ACTIVE_TRACK.yaml"],
        text=False,
    ).stdout
    try:
        text = raw.decode("utf-8")
        try:
            document = json.loads(text)
        except json.JSONDecodeError:
            import yaml  # type: ignore[import-not-found]

            document = yaml.safe_load(text)
    except Exception as exc:
        raise PacketScopeError(f"cannot parse ACTIVE_TRACK.yaml at {commit}: {exc}") from exc
    rows = document.get("active_tracks") if isinstance(document, dict) else None
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise PacketScopeError(f"ACTIVE_TRACK.yaml at {commit} has no active_tracks list")
    return [dict(row) for row in rows]


def _live(row: Mapping[str, Any] | None) -> bool:
    return row is not None and str(row.get("status", "")).upper() in LIVE_TRACK_STATUSES


def _validate_track_binding(
    binding: PacketBinding,
    *,
    base_rows: list[dict[str, Any]],
    head_rows: list[dict[str, Any]],
    changed_paths: list[str],
) -> list[str]:
    packet = binding.packet
    entry = packet.session_entry
    assert entry is not None
    base_by_id = {str(row.get("id")): row for row in base_rows}
    head_by_id = {str(row.get("id")): row for row in head_rows}
    base_track = base_by_id.get(entry.active_track)
    head_track = head_by_id.get(entry.active_track)
    selected = head_track if _live(head_track) else base_track if _live(base_track) else None
    errors: list[str] = []
    if selected is None:
        errors.append(f"{binding.path}: active_track has no live endpoint")
        return errors
    if selected.get("owner") != entry.owner:
        errors.append(f"{binding.path}: owner does not match active-track authority")

    sibling_patterns: dict[str, list[str]] = {}
    for track_id in sorted(set(base_by_id) | set(head_by_id)):
        if track_id == entry.active_track:
            continue
        surfaces = {
            str(surface)
            for row in (base_by_id.get(track_id), head_by_id.get(track_id))
            if _live(row)
            for surface in (row or {}).get("owned_surfaces", [])
        }
        if surfaces:
            sibling_patterns[track_id] = sorted(surfaces)
    # forbidden_files completeness is owed only for sibling patterns that match
    # a path this event actually changes. Safety for touched surfaces comes from
    # detect_surface_collisions below, which grades the real changed paths
    # against live sibling ownership regardless of the packet's declaration;
    # requiring every live sibling surface forced a full packet re-bind
    # (forbidden_files + digest) whenever an unrelated sibling surface entered
    # the portfolio after the packet's base_ref (campaign item 2b).
    required_forbidden = {
        pattern
        for patterns in sibling_patterns.values()
        for pattern in patterns
        if any(matching_patterns(path, [pattern]) for path in changed_paths)
    }
    missing = sorted(required_forbidden - set(packet.forbidden_files))
    if missing:
        errors.append(f"{binding.path}: forbidden_files omit sibling surfaces {missing}")
    collisions = detect_surface_collisions(
        allowed_patterns=packet.allowed_files,
        sibling_patterns=sibling_patterns,
        actual_paths=changed_paths,
    )
    if collisions:
        errors.append(f"{binding.path}: ownership collision {collisions}")
    return errors


def _load_binding(
    repo_root: Path,
    *,
    path: str,
    event_name: str,
    diff_base: str,
    event_base: str,
    event_head: str,
    changed_paths: list[str],
) -> tuple[PacketBinding | None, list[str]]:
    errors: list[str] = []
    try:
        raw = _git_blob(repo_root, event_head, path)
        payload = json.loads(raw.decode("utf-8"))
        packet = parse_work_packet(payload)
    except (PacketScopeError, UnicodeError, json.JSONDecodeError, AgentOpsError,
            AttributeError, TypeError) as exc:
        return None, [f"{path}: invalid Session Entry packet: {exc}"]
    if packet.session_entry is None:
        return None, [f"{path}: changed high-risk packet lacks session_entry"]
    canonical = f"{PACKET_PREFIX}{packet.id}.json"
    if path != canonical:
        errors.append(f"{path}: packet id/path custody mismatch; expected {canonical}")
    if path not in packet.allowed_files:
        errors.append(f"{path}: packet must allow its exact canonical path")
    if matching_patterns(path, packet.forbidden_files):
        errors.append(f"{path}: packet forbids its own canonical path")
    if not packet.approval.before_merge:
        errors.append(f"{path}: approval.before_merge must remain true")
    entry = packet.session_entry
    if entry.collision.checked_at_sha != packet.base_ref:
        errors.append(f"{path}: collision baseline does not equal packet base_ref")
    if entry.collision.status != "clear" or entry.collision.details:
        errors.append(f"{path}: collision declaration is not clear")

    if SHA_RE.fullmatch(packet.base_ref) is None:
        errors.append(f"{path}: base_ref is not an exact commit SHA")
        return None, errors
    packet_commit = _git(
        repo_root,
        ["rev-parse", "--verify", f"{packet.base_ref}^{{commit}}"],
        check=False,
    )
    if packet_commit.returncode != 0 or packet_commit.stdout.strip() != packet.base_ref:
        errors.append(f"{path}: base_ref does not resolve exactly")
        return None, errors
    if event_name == "pull_request":
        # base_ref need only be an ANCESTOR of the live merge base, not equal to
        # it. When main advances and the PR is brought up to date, the merge
        # base moves forward while the packet's provenance floor is unchanged;
        # requiring byte-equality forced a full packet re-bind (base_ref +
        # collision.checked_at_sha + digest) on every such advance. The scope
        # diff already runs against the live merge base (diff_base..head above),
        # so an ancestor floor preserves containment while ending that churn.
        # Mirrors the merge_group ancestor check below.
        ancestry = _git(
            repo_root,
            ["merge-base", "--is-ancestor", packet.base_ref, diff_base],
            check=False,
        )
        if ancestry.returncode != 0:
            errors.append(
                f"{path}: base_ref is not an ancestor of pull-request merge base {diff_base}"
            )
    else:
        ancestry = _git(
            repo_root,
            ["merge-base", "--is-ancestor", packet.base_ref, event_base],
            check=False,
        )
        if ancestry.returncode != 0:
            errors.append(f"{path}: base_ref is not an ancestor of merge-group base")

    binding = PacketBinding(path=path, packet=packet)
    errors.extend(
        _validate_track_binding(
            binding,
            # Read the base endpoint of sibling ownership at the LIVE merge base,
            # not at packet.base_ref. base_ref may be an ancestor of the merge
            # base; a sibling surface added between base_ref and the merge base
            # (and removed by this PR at head) would otherwise be absent from
            # both endpoints, letting an ownership collision through (P1 review
            # on PR #1046, 2026-07-19). diff_base is the conservative base.
            base_rows=_track_rows(repo_root, diff_base),
            head_rows=_track_rows(repo_root, event_head),
            changed_paths=changed_paths,
        )
    )
    return (binding if not errors else None), errors


def evaluate(
    repo_root: Path,
    *,
    event_name: str,
    event_base: str,
    event_head: str,
) -> dict[str, Any]:
    root = repo_root.resolve()
    diff_base, changed = _changed_paths(
        root,
        event_name=event_name,
        event_base=event_base,
        event_head=event_head,
    )
    # Grade against the conservative endpoint union. A PR cannot weaken its
    # own trigger by deleting a base pattern, while newly added hot paths take
    # effect in the same event.
    hot_patterns = sorted(
        set(_hot_patterns_at(root, event_base))
        | set(_hot_patterns_at(root, event_head))
    )
    hot = sorted(path for path in changed if is_hot_path(path, hot_patterns))
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "claim": (
            "committed-range packet scope only; not local preflight/closeout, "
            "packet gate execution, human approval, or merge authority"
        ),
        "event_name": event_name,
        "event_base": event_base,
        "event_head": event_head,
        "diff_base": diff_base,
        "changed_paths": changed,
        "hot_paths": hot,
        "hot_patterns": hot_patterns,
        "packet_paths": [],
        "coverage": {},
        "errors": [],
    }
    if not hot:
        report.update({"status": "NOT_REQUIRED", "required": False, "passed": True})
        return report

    packet_paths = sorted(
        path
        for path in changed
        if path.startswith(PACKET_PREFIX) and path.endswith(".json")
    )
    report["packet_paths"] = packet_paths
    errors: list[str] = []
    bindings: list[PacketBinding] = []
    if not packet_paths:
        errors.append("high-risk event changes no Session Entry packet")
    if event_name == "pull_request" and len(packet_paths) != 1:
        errors.append("high-risk pull request must change exactly one Session Entry packet")
    for path in packet_paths:
        binding, packet_errors = _load_binding(
            root,
            path=path,
            event_name=event_name,
            diff_base=diff_base,
            event_base=event_base,
            event_head=event_head,
            changed_paths=changed,
        )
        errors.extend(packet_errors)
        if binding is not None:
            bindings.append(binding)

    governed = changed if event_name == "pull_request" else sorted(set(hot + packet_paths))
    coverage: dict[str, list[str]] = {}
    for path in governed:
        claimants = [
            binding.path
            for binding in bindings
            if matching_patterns(path, binding.packet.allowed_files)
            and not matching_patterns(path, binding.packet.forbidden_files)
        ]
        coverage[path] = sorted(claimants)
    report["coverage"] = coverage
    gaps = sorted(path for path, claimants in coverage.items() if not claimants)
    overlaps = {
        path: claimants for path, claimants in coverage.items() if len(claimants) > 1
    }
    if gaps:
        errors.append(f"packet coverage gap: {gaps}")
    if overlaps:
        errors.append(f"packet coverage overlap: {overlaps}")
    for binding in bindings:
        forbidden = sorted(
            path for path in changed if matching_patterns(path, binding.packet.forbidden_files)
        )
        if forbidden:
            errors.append(f"{binding.path}: full event changes forbidden paths {forbidden}")

    report["errors"] = errors
    report.update(
        {
            "status": "PASSED" if not errors else "FAILED",
            "required": True,
            "passed": not errors,
        }
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Risk-triggered AgentOps packet-scope CI checker"
    )
    parser.add_argument("--event-name", required=True, choices=sorted(EVENT_NAMES))
    parser.add_argument("--event-base", required=True)
    parser.add_argument("--event-head", required=True)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = evaluate(
            Path.cwd(),
            event_name=args.event_name,
            event_base=args.event_base,
            event_head=args.event_head,
        )
    except (PacketScopeError, AgentOpsError, UnicodeError, AttributeError, TypeError) as exc:
        report = {
            "schema": SCHEMA,
            "status": "CONFIG_ERROR",
            "required": None,
            "passed": False,
            "errors": [str(exc)],
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
