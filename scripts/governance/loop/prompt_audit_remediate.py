#!/usr/bin/env python3
"""Stage 3 — prompt-audit-remediate (Implementer) for the Cybernetic Ratchet Loop.

For each IMPLEMENT finding in ``accepted_findings.jsonl``:

1. Determine ``proof_mode`` (natural|synthetic|none). ``proof_mode=none`` routes
   the finding to DEFER — no fix is attempted (spec §6.2 proof ladder).
2. Create an isolated git worktree off ``base_ref``
   (``git worktree add <path> -b fix/<id> base_ref``). The worktree is a /tmp
   path, NOT the user's working tree.
3. Set up the proof scenario (gate script) in the worktree.
4. Capture ``red_before`` (gate must exit non-zero on the unfixed state).
   No red-before → the fix is not accepted.
5. Apply the fix in the worktree.
6. Capture ``green_after`` (gate must exit zero on the fixed state).
   No green-after → the fix is not accepted.
7. Enforce write-set: every changed file must be within the warrant's
   ``write_set``. Violation → reject (non-zero exit).
8. Run the §8 anti-gaming checklist on the fix diff. Violation → REJECT the
   fix (non-zero exit, archived with evidence) — not merely flagged.
9. Write ``fix_proposal_<finding_id>.yaml`` (§6.2 schema).
10. Clean up the fix worktree.

Worktree creation failure aborts gracefully (non-zero exit, no fix_proposal).
The user's working tree is NEVER touched.

Usage:
    python3 scripts/governance/loop/prompt_audit_remediate.py \\
        --warrant <warrant.yaml> --run-id <run_id> \\
        [--repo-root <path>] [--worktree-root <path>]

Exit codes:
    0   all IMPLEMENT findings processed (accepted or deferred)
    1   at least one fix was rejected (write-set, anti-gaming, no red/green)
    2   warrant invalid/expired, no accepted_findings, or hard error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path

from scripts.governance.loop.agent_backend import (
    ApiBackend,
    BackendError,
    DroidBackend,
)
from scripts.governance.loop.anti_gaming import run_anti_gaming_check
from scripts.governance.loop.oracle import CIOracle
from scripts.governance.loop.runs import Run, RunManager
from scripts.governance.loop.warrant import Warrant, WarrantError

DEFAULT_PYTHON = os.environ.get("LOOP_PYTHON", sys.executable)
DEFAULT_WORKTREE_ROOT = "/tmp"

CHECKLIST_ITEMS = (
    "no_new_skips",
    "no_new_xfails",
    "no_weakened_assertions",
    "no_deleted_tests",
    "no_widened_budgets",
    "fix_addresses_root_cause",
)
VALID_PROOF_MODES = ("natural", "synthetic", "none")


def _emit_error(message: str) -> int:
    sys.stderr.write(message + "\n")
    return 2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Implementer backend interface
# ---------------------------------------------------------------------------


@dataclass
class ImplementerPlan:
    """The Implementer's plan for a finding (determined before any worktree work)."""

    proof_mode: str  # natural | synthetic | none
    gate_command: str  # command to run for red-before / green-after


class ImplementerBackend(ABC):
    """Abstract base for the Implementer agent role.

    In Phase 1 only the ``StubImplementer`` is available. It emits a canned
    synthetic proof scenario (a gate script + a fix marker) that demonstrates
    red-before/green-after deterministically.
    """

    @abstractmethod
    def plan(self, finding: dict, write_set: list[str]) -> ImplementerPlan:
        """Determine proof_mode and the gate command for the finding.

        If ``proof_mode`` is ``none``, the finding routes to DEFER and no
        worktree is created.
        """

    @abstractmethod
    def setup_proof(self, worktree_path: Path, finding: dict) -> None:
        """Set up the proof scenario in the worktree (e.g. write a gate script).

        Called BEFORE red-before is run. For synthetic proof, this writes the
        constructed failing case. For natural proof, this is a no-op (the
        existing suite is the gate).
        """

    @abstractmethod
    def apply_fix(self, worktree_path: Path, finding: dict) -> list[str]:
        """Apply the fix in the worktree.

        Called AFTER red-before, BEFORE green-after. Returns a list of changed
        file paths (relative to the worktree root).
        """


class StubImplementer(ImplementerBackend):
    """M1 stub: emits a canned synthetic proof scenario.

    The stub writes a gate script that checks for the existence of a marker
    file. Before the fix (red-before), the marker doesn't exist → exit 1.
    After the fix (green-after), the marker exists → exit 0.

    Both the gate script and the marker file are written under
    ``scripts/governance/loop/`` (within the typical write-set).
    """

    def plan(self, finding: dict, write_set: list[str]) -> ImplementerPlan:
        fid = finding.get("finding_id", "unknown")
        gate_script = f"scripts/governance/loop/fix_gate_{fid}.py"
        gate_command = f'"{DEFAULT_PYTHON}" {gate_script}'
        return ImplementerPlan(proof_mode="synthetic", gate_command=gate_command)

    def setup_proof(self, worktree_path: Path, finding: dict) -> None:
        fid = finding.get("finding_id", "unknown")
        gate_dir = worktree_path / "scripts" / "governance" / "loop"
        gate_dir.mkdir(parents=True, exist_ok=True)
        gate_script = gate_dir / f"fix_gate_{fid}.py"
        gate_script.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            f'marker = Path(__file__).parent / "fix_marker_{fid}.txt"\n'
            "if marker.exists():\n"
            '    print("OK: fix marker found")\n'
            "    sys.exit(0)\n"
            'print("FAIL: fix marker not found")\n'
            "sys.exit(1)\n"
        )

    def apply_fix(self, worktree_path: Path, finding: dict) -> list[str]:
        fid = finding.get("finding_id", "unknown")
        gate_dir = worktree_path / "scripts" / "governance" / "loop"
        gate_dir.mkdir(parents=True, exist_ok=True)
        marker = gate_dir / f"fix_marker_{fid}.txt"
        marker.write_text(f"fix applied for {fid}\n")
        return [
            f"scripts/governance/loop/fix_gate_{fid}.py",
            f"scripts/governance/loop/fix_marker_{fid}.txt",
        ]


class DroidImplementer(StubImplementer):
    """Implementer wrapper that invokes Droid in an isolated role session."""

    def __init__(
        self,
        droid_path: str | Path | None = None,
        cwd: str | Path | None = None,
    ) -> None:
        self.backend = DroidBackend(droid_path=droid_path, cwd=cwd)
        self._last_invocation = None

    def plan(self, finding: dict, write_set: list[str]) -> ImplementerPlan:
        prompt = (
            "ROLE: Implementer\n"
            "Propose a minimal fix under the warrant write_set. "
            "Do not claim truth; deterministic gates decide.\n"
            f"finding: {finding}\n"
            f"write_set: {write_set}\n"
        )
        self._last_invocation = self.backend.invoke(
            "implementer",
            prompt,
            {
                "finding_id": finding.get("finding_id"),
                "severity": finding.get("severity"),
                "write_set": write_set,
            },
        )
        return super().plan(finding, write_set)

    def invocation_receipt(self) -> dict | None:
        if self._last_invocation is None:
            return None
        return self._last_invocation.to_receipt()


class ApiImplementer(StubImplementer):
    """Keyless-safe API implementer wrapper."""

    def __init__(self) -> None:
        self.backend = ApiBackend()
        self._last_invocation = None

    def plan(self, finding: dict, write_set: list[str]) -> ImplementerPlan:
        self._last_invocation = self.backend.invoke(
            "implementer",
            "ROLE: Implementer\nAPI backend degradation-safe proposal request.",
            {
                "finding_id": finding.get("finding_id"),
                "severity": finding.get("severity"),
                "write_set": write_set,
            },
        )
        if self._last_invocation.return_code != 0:
            raise BackendError(self._last_invocation.stdout)
        return super().plan(finding, write_set)

    def invocation_receipt(self) -> dict | None:
        if self._last_invocation is None:
            return None
        return self._last_invocation.to_receipt()


def get_implementer(name: str | None = None) -> ImplementerBackend:
    """Return the implementer selected by ``name`` or ``LOOP_AGENT_BACKEND`` env var.

    Default is ``stub``. Unknown backends raise a clear error.
    """
    impl_name = name or os.environ.get("LOOP_AGENT_BACKEND", "stub")
    if impl_name == "stub":
        return StubImplementer()
    if impl_name == "droid":
        return DroidImplementer()
    if impl_name == "api":
        return ApiImplementer()
    raise NotImplementedError(
        f"unknown implementer backend {impl_name!r}; expected stub|droid|api"
    )


# ---------------------------------------------------------------------------
# Write-set checking (glob-aware)
# ---------------------------------------------------------------------------


def is_in_write_set(path: str, write_set: list[str]) -> bool:
    """Check if ``path`` matches any pattern in ``write_set`` (fnmatch glob)."""
    for pattern in write_set:
        if fnmatch(path, pattern):
            return True
        if path == pattern:
            return True
        if path.startswith(pattern.rstrip("*/") + "/"):
            return True
    return False


def check_write_set(changed_files: list[str], write_set: list[str]) -> list[str]:
    """Return the list of files that are OUTSIDE the write_set (violations)."""
    return [f for f in changed_files if not is_in_write_set(f, write_set)]


def _estimate_remediation_tokens(finding: dict, write_set: list[str]) -> int:
    """Conservative deterministic budget estimate before agent/worktree work.

    The loop cannot trust a model to report its own usage, so remediation spends
    an auditable local estimate derived from the payload handed to the
    implementer. This makes ``budget.max_tokens`` enforceable even with stub or
    degraded backends.
    """
    payload = json.dumps(
        {"finding": finding, "write_set": write_set},
        sort_keys=True,
        default=str,
    )
    return max(1, (len(payload) + 3) // 4)


# ---------------------------------------------------------------------------
# Git-diff path extraction (M2 hardening: replaces self-reported changed_files)
# ---------------------------------------------------------------------------

_DIFF_GIT_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")


def extract_changed_paths(diff_text: str) -> list[str]:
    """Extract changed file paths from a unified git diff.

    Parses ``diff --git a/<path> b/<path>`` header lines to determine which
    files were actually changed. This is the M2 hardening replacement for the
    implementer's self-reported ``changed_files`` list — the git diff cannot
    be gamed by an LLM implementer misreporting paths.
    """
    paths: list[str] = []
    seen: set[str] = set()
    for line in diff_text.splitlines():
        m = _DIFF_GIT_RE.match(line)
        if m:
            for path in (m.group(1), m.group(2)):
                if path and path != "/dev/null" and path not in seen:
                    paths.append(path)
                    seen.add(path)
    return paths


# ---------------------------------------------------------------------------
# Worktree management
# ---------------------------------------------------------------------------


def _run_scratch_token(run_dir: Path) -> str:
    """Stable per-run token for scratch refs that must not collide cross-run."""
    return hashlib.sha256(str(run_dir).encode("utf-8")).hexdigest()[:12]


def _worktree_path(worktree_root: Path, finding_id: str, run_dir: Path) -> Path:
    token = _run_scratch_token(run_dir)
    return worktree_root / f"ds_loop_fix_{_branch_safe(finding_id)}-{token}"


@dataclass
class WorktreeCreateResult:
    """Result of creating a temporary fix worktree."""

    ok: bool
    stderr: str = ""


def _branch_safe(value: str) -> str:
    """Return a conservative git-ref segment from a run/finding id."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "unknown"


def _fix_branch_name(run_id: str, finding_id: str, run_dir: Path) -> str:
    token = _run_scratch_token(run_dir)
    return f"fix/{_branch_safe(run_id)}-{_branch_safe(finding_id)}-{token}"


def create_worktree(
    repo_root: Path,
    worktree_path: Path,
    branch_name: str,
    base_ref: str,
) -> WorktreeCreateResult:
    """Create an isolated git worktree off ``base_ref``.

    Returns a structured result so callers can report the exact git failure.
    """
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "add", str(worktree_path),
         "-b", branch_name, base_ref],
        capture_output=True,
        text=True,
    )
    return WorktreeCreateResult(ok=proc.returncode == 0, stderr=proc.stderr.strip())


def cleanup_worktree(repo_root: Path, worktree_path: Path, branch_name: str) -> None:
    """Remove a fix worktree and its branch (best-effort, no raise)."""
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(worktree_path)],
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "branch", "-D", branch_name],
        capture_output=True,
        text=True,
    )


def get_worktree_diff(worktree_path: Path) -> str:
    """Get the unified diff of all changes (including new files) in the worktree."""
    # Stage all changes so new files appear in the diff with proper a/ b/ prefixes.
    subprocess.run(
        ["git", "-C", str(worktree_path), "add", "-A"],
        capture_output=True,
        text=True,
    )
    proc = subprocess.run(
        ["git", "-C", str(worktree_path), "diff", "--cached", "--no-color"],
        capture_output=True,
        text=True,
    )
    return proc.stdout


# ---------------------------------------------------------------------------
# Stage core
# ---------------------------------------------------------------------------


@dataclass
class FixProposal:
    """The §6.2 fix_proposal artifact."""

    run_id: str
    finding_id: str
    write_set_used: list[str] = field(default_factory=list)
    patch_ref: str = ""
    red_before: dict = field(default_factory=dict)
    green_after: dict = field(default_factory=dict)
    proof_mode: str = "none"
    anti_gaming_checklist: dict = field(default_factory=dict)
    implementer_invocation: dict | None = None

    def to_dict(self) -> dict:
        payload = {
            "run_id": self.run_id,
            "finding_id": self.finding_id,
            "write_set_used": self.write_set_used,
            "patch_ref": self.patch_ref,
            "red_before": self.red_before,
            "green_after": self.green_after,
            "proof_mode": self.proof_mode,
            "anti_gaming_checklist": self.anti_gaming_checklist,
        }
        if self.implementer_invocation is not None:
            payload["implementer_invocation"] = self.implementer_invocation
        return {"fix_proposal": payload}


def _relative_ref(run: Run, path: Path) -> str:
    try:
        return str(path.relative_to(run.run_dir))
    except ValueError:
        return str(path)


def _write_defer_record(run: Run, finding_id: str, reason: str) -> str:
    record = {
        "defer": {
            "finding_id": finding_id,
            "reason": reason,
            "timestamp_utc": _utc_now_iso(),
        }
    }
    path = run.run_dir / f"defer_{finding_id}.yaml"
    run.write_yaml(path, record)
    return _relative_ref(run, path)


def _find_stale_run_id(records: list[dict], expected_run_id: str) -> tuple[str, str] | None:
    for record in records:
        record_run_id = record.get("run_id")
        if record_run_id is not None and record_run_id != expected_run_id:
            return record.get("finding_id", "unknown"), str(record_run_id)
    return None


def _process_finding(
    finding: dict,
    warrant: Warrant,
    run: Run,
    implementer: ImplementerBackend,
    repo_root: Path,
    worktree_root: Path,
    oracle: CIOracle,
) -> tuple[int, str]:
    """Process a single IMPLEMENT finding.

    Returns (exit_code, status) where status is one of:
    accepted, rejected, deferred, error.
    """
    finding_id = finding.get("finding_id", "unknown")
    write_set = warrant.write_set

    # 1. Determine proof_mode.
    try:
        plan = implementer.plan(finding, write_set)
    except BackendError as exc:
        sys.stderr.write(f"finding {finding_id}: implementer backend failed — {exc}\n")
        return 2, "error"
    if plan.proof_mode not in VALID_PROOF_MODES:
        sys.stderr.write(
            f"finding {finding_id}: invalid proof_mode={plan.proof_mode!r}; "
            f"expected one of {VALID_PROOF_MODES}\n"
        )
        return 2, "error"
    if plan.proof_mode == "none":
        _write_defer_record(
            run,
            finding_id,
            "proof_mode=none — no red-before/green-after achievable",
        )
        sys.stdout.write(
            f"finding {finding_id}: proof_mode=none — routing to DEFER (no fix attempted)\n"
        )
        return 0, "deferred"

    # 2. Create isolated worktree off base_ref.
    base_ref = warrant.scope.get("base_ref", "HEAD")
    wt_path = _worktree_path(worktree_root, finding_id, run.run_dir)
    branch_name = _fix_branch_name(run.run_id, finding_id, run.run_dir)

    created = create_worktree(repo_root, wt_path, branch_name, base_ref)
    if not created.ok:
        detail = f" ({created.stderr})" if created.stderr else ""
        sys.stderr.write(
            f"finding {finding_id}: worktree creation failed at {wt_path} "
            f"off {base_ref}{detail} — aborting (no fix_proposal written)\n"
        )
        return 2, "error"

    try:
        # 3. Set up proof scenario.
        implementer.setup_proof(wt_path, finding)

        # 4. Capture red_before (must be non-zero).
        red_result = oracle.run_gate(plan.gate_command, cwd=str(wt_path))
        if red_result.exit_code == 0:
            sys.stderr.write(
                f"finding {finding_id}: red-before exit 0 — no red, fix not accepted\n"
            )
            return 1, "rejected"

        # 5. Apply the fix.
        #    The implementer's self-reported changed_files return value is
        #    intentionally NOT used for write-set enforcement (M2 hardening):
        #    an LLM implementer could misreport paths. The actual git diff
        #    (step 7 below) is the ground truth.
        implementer.apply_fix(wt_path, finding)

        # 6. Capture green_after (must be zero).
        green_result = oracle.run_gate(plan.gate_command, cwd=str(wt_path))
        if green_result.exit_code != 0:
            sys.stderr.write(
                f"finding {finding_id}: green-after exit {green_result.exit_code} — no green, fix not accepted\n"
            )
            return 1, "rejected"

        # 7. Enforce write-set from the ACTUAL git diff (M2 hardening).
        #    The implementer's self-reported changed_files list is NOT trusted —
        #    an LLM implementer could misreport paths. The git diff is the
        #    ground truth for what was actually changed.
        diff_text = get_worktree_diff(wt_path)
        diff_changed_paths = extract_changed_paths(diff_text)
        violations = check_write_set(diff_changed_paths, write_set)
        if violations:
            sys.stderr.write(
                f"finding {finding_id}: write-set violation (git-diff) — files outside warrant write_set: {violations}. "
                f"Fix REJECTED.\n"
            )
            return 1, "rejected"

        # 8. Run anti-gaming checklist on the fix diff (same diff as step 7).
        # Save the fix diff so Stage 4 (reaudit) can run the anti-gaming
        # checklist independently on the same diff.
        diff_path = run.fixes_dir / f"fix_diff_{finding_id}.patch"
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_text(diff_text)
        ag_result = run_anti_gaming_check(diff_text, finding=finding)
        if not ag_result.passed:
            failed_names = [f.name for f in ag_result.failures()]
            sys.stderr.write(
                f"finding {finding_id}: anti-gaming checklist FAILED — {failed_names}. "
                f"Fix REJECTED (archived with evidence).\n"
            )
            return 1, "rejected"

        # 9. Write fix_proposal.
        proposal = FixProposal(
            run_id=run.run_id,
            finding_id=finding_id,
            write_set_used=write_set,
            patch_ref=_relative_ref(run, diff_path),
            red_before={
                "command": plan.gate_command,
                "exit_code": red_result.exit_code,
                "key_output": red_result.stdout.strip()[:500],
            },
            green_after={
                "command": plan.gate_command,
                "exit_code": green_result.exit_code,
                "key_output": green_result.stdout.strip()[:500],
            },
            proof_mode=plan.proof_mode,
            anti_gaming_checklist=ag_result.to_dict(),
            implementer_invocation=(
                implementer.invocation_receipt()
                if hasattr(implementer, "invocation_receipt")
                else None
            ),
        )
        fp_path = run.fix_proposal_path(finding_id)
        run.write_yaml(fp_path, proposal.to_dict())
        run.add_finding(finding_id)
        sys.stdout.write(
            f"finding {finding_id}: fix accepted — fix_proposal written to {fp_path}\n"
        )
        return 0, "accepted"

    finally:
        # 10. Clean up the worktree (always, even on rejection).
        cleanup_worktree(repo_root, wt_path, branch_name)


def run_remediate(
    warrant_path: Path,
    run: Run,
    implementer: ImplementerBackend,
    repo_root: Path,
    worktree_root: Path,
) -> int:
    """Execute Stage 3 remediation for all IMPLEMENT findings.

    Returns 0 if all findings were accepted or deferred, 1 if any was rejected,
    2 on a hard error (warrant invalid, no accepted_findings, etc.).
    """
    # Re-validate the warrant on stage entry.
    try:
        warrant = Warrant.load_and_check(warrant_path)
    except WarrantError as exc:
        return _emit_error(f"warrant stage-entry refused: {exc}")

    # Load accepted_findings.jsonl.
    findings_path = run.accepted_findings_path()
    if not findings_path.is_file():
        return _emit_error(
            f"no accepted_findings.jsonl in {run.run_dir} — run prompt-audit-triage (Stage 2) first"
        )
    findings = run.read_jsonl(findings_path)
    stale = _find_stale_run_id(findings, run.run_id)
    if stale is not None:
        finding_id, stale_run_id = stale
        return _emit_error(
            f"accepted finding {finding_id!r} has run_id={stale_run_id!r}; "
            f"expected {run.run_id!r}"
        )

    # Filter to IMPLEMENT findings only.
    impl_findings = [f for f in findings if f.get("routing") == "IMPLEMENT"]
    if not impl_findings:
        sys.stdout.write(
            "no IMPLEMENT findings — nothing to remediate\n"
        )
        return 0

    # Check budget.
    write_set = warrant.write_set
    max_tokens = warrant.budget["max_tokens"]
    max_wall_clock_min = warrant.budget["max_wall_clock_min"]
    if max_tokens <= 0:
        for finding in impl_findings:
            _write_defer_record(
                run,
                finding.get("finding_id", "unknown"),
                "budget.max_tokens exhausted before remediation",
            )
        sys.stdout.write("budget.max_tokens exhausted — all IMPLEMENT findings routed to DEFER\n")
        return 0
    if max_wall_clock_min <= 0:
        for finding in impl_findings:
            _write_defer_record(
                run,
                finding.get("finding_id", "unknown"),
                "budget.max_wall_clock_min exhausted before remediation",
            )
        sys.stdout.write("budget.max_wall_clock_min exhausted — all IMPLEMENT findings routed to DEFER\n")
        return 0

    max_fixes = int(warrant.budget["max_fixes_per_run"])
    process_findings = impl_findings[:max_fixes]
    excess_findings = impl_findings[max_fixes:]
    for finding in excess_findings:
        _write_defer_record(
            run,
            finding.get("finding_id", "unknown"),
            f"budget.max_fixes_per_run exceeded: limit {max_fixes}; routed excess IMPLEMENT finding to DEFER",
        )
    if excess_findings:
        sys.stdout.write(
            f"budget.max_fixes_per_run limit {max_fixes}: "
            f"{len(excess_findings)} excess IMPLEMENT finding(s) routed to DEFER\n"
        )

    # Create the oracle for gate runs (PYTHONPATH = worktree at run time).
    oracle = CIOracle(python=DEFAULT_PYTHON, repo_root=repo_root)

    rejected = 0
    accepted = 0
    deferred = len(excess_findings)

    start = time.monotonic()
    used_tokens = 0
    for index, finding in enumerate(process_findings):
        elapsed_min = (time.monotonic() - start) / 60
        if elapsed_min > max_wall_clock_min:
            for remaining in process_findings[index:]:
                _write_defer_record(
                    run,
                    remaining.get("finding_id", "unknown"),
                    f"budget.max_wall_clock_min exceeded: elapsed {elapsed_min:.3f} > limit {max_wall_clock_min}",
                )
                deferred += 1
            break
        estimated_tokens = _estimate_remediation_tokens(finding, write_set)
        if used_tokens + estimated_tokens > max_tokens:
            for remaining in process_findings[index:]:
                remaining_estimate = _estimate_remediation_tokens(remaining, write_set)
                _write_defer_record(
                    run,
                    remaining.get("finding_id", "unknown"),
                    "budget.max_tokens exceeded: "
                    f"used {used_tokens}, next_estimate {remaining_estimate}, limit {max_tokens}",
                )
                deferred += 1
            sys.stdout.write(
                f"budget.max_tokens limit {max_tokens}: remaining IMPLEMENT finding(s) routed to DEFER\n"
            )
            break
        used_tokens += estimated_tokens
        rc, status = _process_finding(
            finding, warrant, run, implementer, repo_root, worktree_root, oracle,
        )
        if status == "accepted":
            accepted += 1
        elif status == "deferred":
            deferred += 1
        elif status == "rejected":
            rejected += 1
        elif status == "error":
            return 2

    sys.stdout.write(
        f"prompt-audit-remediate complete: {accepted} accepted, "
        f"{deferred} deferred, {rejected} rejected\n"
    )

    if rejected > 0:
        return 1
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stage 3 (Implementer): produce scoped fix proposals in isolated "
            "git worktrees with red-before/green-after proof + anti-gaming checks."
        ),
    )
    parser.add_argument("--warrant", required=True, help="path to the warrant YAML file")
    parser.add_argument("--run-id", required=True, help="the run id (locates the run dir)")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[3]),
        help="git repo root for worktree creation (default: mission worktree)",
    )
    parser.add_argument(
        "--worktree-root",
        default=DEFAULT_WORKTREE_ROOT,
        help=f"root dir for fix worktrees (default: {DEFAULT_WORKTREE_ROOT})",
    )
    parser.add_argument(
        "--backend",
        default=None,
        help="implementer backend name (stub|droid|api); defaults to LOOP_AGENT_BACKEND env or stub",
    )
    args = parser.parse_args(argv)

    warrant_path = Path(args.warrant)
    repo_root = Path(args.repo_root)
    worktree_root = Path(args.worktree_root)
    worktree_root.mkdir(parents=True, exist_ok=True)

    # Select the implementer backend.
    try:
        implementer = get_implementer(args.backend)
    except (BackendError, NotImplementedError) as exc:
        return _emit_error(f"implementer selection failed: {exc}")

    # Open the run dir.
    try:
        run = RunManager.open_run(args.run_id)
    except FileNotFoundError as exc:
        return _emit_error(str(exc))

    return run_remediate(warrant_path, run, implementer, repo_root, worktree_root)


if __name__ == "__main__":
    sys.exit(main())
