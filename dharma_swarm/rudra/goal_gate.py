"""RUDRA GoalGate: mission admission and the independent completion oracle.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md sections 8-9.

GoalGate is the sole completion constructor: ``ReproducedCompletion`` exists
only when ``promote`` binds a fresh ``GoalGatePassed`` produced against the
exact candidate commit in a fresh detached verification workcell.

Decomposition (leaf modules, one-directional):
  goal_gate_admission — GoalGateError, AdmittedMission, admission mixin,
                        shared hashing/git helpers
  goal_gate_verify    — candidate freeze, fresh detached verification,
                        promote (the spec section 9 type edge)
This module keeps the gate core (scope inventory, verifier execution,
evaluation) and re-exports both leaves so every public name stays here.
"""

from __future__ import annotations

import re
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Sequence

from dharma_swarm.rudra.contracts import (
    AdmissionError,
    AdmissionReject,
    GateResult,
    GoalGatePassed as GoalGatePassed,
    VerifierCommand,
    VerifierReceipt,
    sha256_json,
)
from dharma_swarm.rudra.goal_gate_admission import (
    AdmittedMission as AdmittedMission,
    GoalGateAdmission,
    GoalGateError as GoalGateError,
    _fsync_file as _fsync_file,
    _git,
    sha256_file,
)
from dharma_swarm.rudra.goal_gate_verify import (
    CandidateRejected as CandidateRejected,
    GoalGateVerify,
    PromotionRejected as PromotionRejected,
)
from dharma_swarm.rudra.workcell import (
    ProcessOwner,
    Workcell,
    hermetic_git_env,
    rudra_state_root,
    run_git,
)

# Environment names that never leak into a verifier subprocess (spec 8).
_SCRUB_ENV = frozenset({
    "PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS", "GIT_DIR", "GIT_WORK_TREE",
    "GIT_INDEX_FILE", "BASH_ENV", "ENV", "CDPATH", "SSH_AUTH_SOCK",
})
_SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
_FIXED_VERIFIER_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


class GoalGate(GoalGateAdmission, GoalGateVerify):
    """Admission + evaluation. Never trusts executor claims."""

    def __init__(
        self,
        repo_path: Path,
        state_dir: Path | None = None,
        process_owner: ProcessOwner | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.state_root = rudra_state_root(state_dir)
        if self.state_root.is_relative_to(self.repo_path):
            raise AdmissionError(
                AdmissionReject.BLOCKED_ENVIRONMENT,
                "state root must be outside the source repository",
            )
        self.git_home = self.state_root / "git-home"
        self.git_home.mkdir(parents=True, exist_ok=True)
        self.env = hermetic_git_env(self.git_home)
        self.owner = process_owner or ProcessOwner()

    # --- Scope inventory (spec 8) -------------------------------------------

    def workspace_snapshot(self, root: Path, base_sha: str) -> tuple[list[str], str, str]:
        """(changed paths, HEAD, digest) from raw git state, not a friendly diff.

        Covers committed diffs (base..HEAD) plus uncommitted porcelain state.
        """
        diff = _git(root, self.env, "diff", "--name-only", "-z", base_sha, "HEAD")
        committed = {p for p in diff.split("\0") if p}
        uncommitted = set(self._porcelain_paths(root))
        changed = sorted(committed | uncommitted)
        head = _git(root, self.env, "rev-parse", "HEAD").strip()
        digest = sha256_json({"changed": changed, "head": head})
        return changed, head, digest

    def _porcelain_paths(self, root: Path) -> list[str]:
        """porcelain-v2 -z: tracked, renamed, deleted, untracked entries."""
        raw = _git(
            root, self.env, "status", "--porcelain=v2", "-z", "--untracked-files=all"
        )
        fields = raw.split("\0")
        paths: list[str] = []
        index = 0
        while index < len(fields):
            entry = fields[index]
            index += 1
            if not entry:
                continue
            kind = entry[0]
            if kind in ("?", "!"):
                if kind == "?":
                    paths.append(entry[2:])
                continue
            if kind in ("1", "2", "u"):
                # `2` (rename/copy) is followed by a separate origPath field.
                body = entry.split(" ", 9)
                paths.append(body[-1] if kind != "2" else body[-1].split("\t")[0])
                if kind == "2":
                    index += 1  # skip origPath field
        return paths

    def _scope_check(
        self,
        admitted: AdmittedMission,
        root: Path,
        changed: list[str],
        pointer_sha256: str | None = None,
    ) -> list[str]:
        contract = admitted.contract
        scope = contract.scope
        reasons: list[str] = []

        def matches(path: str, patterns: Sequence[str]) -> bool:
            return any(fnmatchcase(path, pattern) for pattern in patterns)

        for path in changed:
            if matches(path, scope.forbidden_changed_paths):
                reasons.append(f"forbidden path changed: {path}")
            elif not matches(path, scope.allowed_changed_paths):
                reasons.append(f"changed path outside allowed set: {path}")
            if scope.reject_symlinks:
                full = root / path
                chain = [full, *full.parents]
                if any(
                    p.is_symlink()
                    for p in chain
                    if p.is_relative_to(root) or p == full
                ):
                    reasons.append(f"symlink in changed path: {path}")
        if len(changed) > scope.max_changed_files:
            reasons.append(f"changed file count {len(changed)} exceeds budget")
        if changed:
            diff = _git(root, self.env, "diff", contract.repository.base_sha, "HEAD")
            if len(diff.encode()) > scope.max_diff_bytes:
                reasons.append("diff byte budget exceeded")
        for literal in scope.forbidden_diff_literals:
            for path in changed:
                if not matches(path, scope.allowed_changed_paths):
                    continue
                target = root / path
                new_count = (
                    target.read_text(errors="replace").count(literal)
                    if target.is_file() else 0
                )
                show = run_git(
                    ["show", f"{contract.repository.base_sha}:{path}"],
                    cwd=root, env=self.env, timeout=30,
                )
                base_count = show.stdout.count(literal) if show.returncode == 0 else 0
                if new_count > base_count:
                    reasons.append(f"forbidden diff literal {literal!r} in {path}")
        flags = _git(root, self.env, "ls-files", "-v", "-z")
        for entry in flags.split("\0"):
            if entry and entry[0] not in ("H",):
                reasons.append(f"index flag anomaly {entry[0]} on {entry[2:]}")
        pointer = root / ".git"
        expected_pointer = (
            pointer_sha256
            if pointer_sha256 is not None
            else admitted.git_pointer_sha256
        )
        if pointer.is_file() and sha256_file(pointer) != expected_pointer:
            reasons.append(".git pointer mutated")
        return reasons

    # --- Verifier execution (spec 8) ----------------------------------------

    def scrubbed_environment(
        self, contract_env: dict[str, str], artifact_dir: Path
    ) -> dict[str, str]:
        (artifact_dir / "home").mkdir(parents=True, exist_ok=True)
        (artifact_dir / "tmp").mkdir(parents=True, exist_ok=True)
        env: dict[str, str] = {
            "PATH": _FIXED_VERIFIER_PATH,
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "HOME": str(artifact_dir / "home"),
            "TMPDIR": str(artifact_dir / "tmp"),
            "RUDRA_ARTIFACT_DIR": str(artifact_dir),
        }
        for name, value in contract_env.items():
            upper = name.upper()
            if (
                upper in _SCRUB_ENV
                or upper.startswith("GIT_CONFIG_")
                or any(marker in upper for marker in _SECRET_MARKERS)
            ):
                raise AdmissionError(
                    AdmissionReject.REJECT_INVALID, f"forbidden verifier env {name!r}"
                )
            env[name] = value
        return env

    def _run_verifier(
        self,
        admitted: AdmittedMission,
        command: VerifierCommand,
        cwd: Path,
        artifact_dir: Path,
        index: int,
    ) -> VerifierReceipt:
        contract = admitted.contract
        artifact_dir.mkdir(parents=True, exist_ok=True)
        env = self.scrubbed_environment(contract.acceptance.environment, artifact_dir)
        argv = [
            a.replace("${RUDRA_ARTIFACT_DIR}", str(artifact_dir)) for a in command.argv
        ]
        exe_digest = sha256_file(Path(argv[0]))
        stdout_path = artifact_dir / f"{index}.stdout"
        stderr_path = artifact_dir / f"{index}.stderr"
        started = time.time()
        timed_out = False
        exit_code: int | None = None
        with open(stdout_path, "wb") as out_fh, open(stderr_path, "wb") as err_fh:
            proc, handle = self.owner.spawn(
                argv, env=env, cwd=cwd, stdout=out_fh, stderr=err_fh
            )
            try:
                exit_code = proc.wait(timeout=command.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                self.owner.terminate_tree(handle)
        ended = time.time()
        cap = contract.budgets.max_captured_output_bytes
        failure: str | None = None
        if timed_out:
            failure = f"timeout after {command.timeout_seconds}s"
        elif stdout_path.stat().st_size > cap or stderr_path.stat().st_size > cap:
            failure = "captured output budget exceeded"
        elif exit_code != command.expect.exit_code:
            failure = f"exit {exit_code} != expected {command.expect.exit_code}"
        if failure is None:
            stdout_text = stdout_path.read_text(errors="replace")
            for pattern in command.expect.stdout_must_match:
                if not re.search(pattern, stdout_text, re.MULTILINE):
                    failure = f"stdout missing {pattern!r}"
                    break
        if failure is None and command.expect.structured_result is not None:
            failure = self._check_junit(command, artifact_dir)
        return VerifierReceipt(
            command_id=command.id,
            argv=argv,
            executable_sha256=exe_digest,
            cwd=str(cwd),
            env_digest=sha256_json(env),
            started_at=started,
            ended_at=ended,
            exit_code=exit_code,
            timed_out=timed_out,
            stdout_sha256=sha256_file(stdout_path),
            stderr_sha256=sha256_file(stderr_path),
            assertions_passed=failure is None,
            failure_reason=failure,
        )

    def _check_junit(self, command: VerifierCommand, artifact_dir: Path) -> str | None:
        assertion = command.expect.structured_result
        assert assertion is not None
        artifact = artifact_dir / assertion.artifact
        if not artifact.exists():
            return f"junit artifact missing: {assertion.artifact}"
        try:
            tree = ET.parse(artifact)
        except ET.ParseError as exc:
            return f"junit artifact unparsable: {exc}"
        cases: dict[str, str] = {}
        totals = {"passed": 0, "skipped": 0, "failures": 0, "errors": 0}
        for case in tree.getroot().iter("testcase"):
            key = f"{case.get('classname', '')}::{case.get('name', '')}"
            if case.find("failure") is not None:
                cases[key] = "failures"
            elif case.find("error") is not None:
                cases[key] = "errors"
            elif case.find("skipped") is not None:
                cases[key] = "skipped"
            else:
                cases[key] = "passed"
        for status in cases.values():
            totals[status] += 1
        for required in assertion.required_testcases:
            if required not in cases:
                return f"required testcase not executed: {required}"
            if cases[required] != "passed":
                return f"required testcase {required} status {cases[required]}"
        for name, required_count in assertion.require_counts.items():
            if totals.get(name) != required_count:
                return (
                    f"junit count {name}: observed {totals.get(name)} "
                    f"!= required {required_count}"
                )
        return None

    # --- Evaluation: always fresh, after the last mutation; nothing cached --

    def evaluate(
        self,
        admitted: AdmittedMission,
        *,
        baseline: bool = False,
        root: Path | None = None,
        gate_run_id: str | None = None,
        pointer_sha256: str | None = None,
    ) -> GateResult:
        """Run the full admitted gate. Verifiers always execute fresh, after
        the last workspace mutation; nothing cached is consulted."""
        contract = admitted.contract
        if root is None:
            root = Workcell(
                Path(admitted.attempt_dir), self.repo_path,
                contract.repository.base_sha, self.state_root,
            ).worktree
        run_id = gate_run_id or uuid.uuid4().hex
        artifact_dir = Path(admitted.attempt_dir) / "verifiers" / run_id
        changed, _head, digest = self.workspace_snapshot(
            root, contract.repository.base_sha
        )
        reasons: list[str] = []
        if not baseline:
            reasons += self._scope_check(admitted, root, changed, pointer_sha256)
            if contract.result.require_nonempty_diff and not changed:
                reasons.append("empty diff while nonempty diff required")
            for required in contract.scope.required_changed_paths:
                if not any(fnmatchcase(c, required) for c in changed):
                    reasons.append(f"required path unchanged: {required}")
        receipts: list[VerifierReceipt] = []
        cwd = (root / contract.acceptance.cwd).resolve()
        for index, command in enumerate(contract.acceptance.commands):
            receipt = self._run_verifier(admitted, command, cwd, artifact_dir, index)
            receipts.append(receipt)
            if receipt.failure_reason:
                reasons.append(f"{command.id}: {receipt.failure_reason}")
        return GateResult(
            green=not reasons,
            subject_digest=digest,
            changed_paths=changed,
            receipts=receipts,
            reasons=reasons,
            verifier_run_id=run_id,
        )
