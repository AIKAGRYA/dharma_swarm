"""RUDRA GoalGate: mission admission and the independent completion oracle.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md sections 8-9.

GoalGate is the sole completion constructor. Model prose, model JSON, tool
exit status, receipts, task state, and old verifier results are observations;
``ReproducedCompletion`` exists only when ``promote`` binds a fresh
``GoalGatePassed`` produced against the exact candidate commit in a fresh
detached verification workcell.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
from fnmatch import fnmatchcase
from pathlib import Path
from typing import ClassVar, Sequence

from pydantic import BaseModel, ConfigDict

from dharma_swarm.rudra.contracts import (
    AdmissionError,
    AdmissionReject,
    GateResult,
    GoalGatePassed,
    ReportedCompletion,
    ReproducedCompletion,
    RudraMissionContract,
    VerifierCommand,
    VerifierReceipt,
    _GATE_TOKEN,
    derive_attempt_key,
    derive_mission_key,
    parse_mission,
    sha256_json,
)
from dharma_swarm.rudra.workcell import (
    Journal,
    ProcessOwner,
    Workcell,
    hermetic_git_env,
    rudra_state_root,
)

# Environment names that never leak into a verifier subprocess (spec 8).
_SCRUB_ENV = frozenset({
    "PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS", "GIT_DIR", "GIT_WORK_TREE",
    "GIT_INDEX_FILE", "BASH_ENV", "ENV", "CDPATH", "SSH_AUTH_SOCK",
})
_SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
_FIXED_VERIFIER_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


class PromotionRejected(ValueError):
    pass


class CandidateRejected(ValueError):
    """Final verification red; the candidate is preserved as evidence."""


class AdmittedMission(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    contract: RudraMissionContract
    contract_digest: str
    mission_key: str
    attempt_key: str
    attempt_uuid: str
    mission_dir: str
    attempt_dir: str
    base_digests: dict[str, str]
    git_pointer_sha256: str
    baseline: GateResult | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _version_output(path: Path) -> str:
    proc = subprocess.run(
        [str(path), "--version"], capture_output=True, text=True, timeout=15,
    )
    return (proc.stdout or proc.stderr).strip()


def _git(root: Path, env: dict[str, str], *args: str, timeout: float = 60.0) -> str:
    proc = subprocess.run(
        ["/usr/bin/git", "-c", "core.hooksPath=/dev/null",
         "-c", "commit.gpgSign=false", *args],
        cwd=root, env=env, capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise GoalGateError(f"git {' '.join(args[:1])}: {proc.stderr.strip()}")
    return proc.stdout


class GoalGateError(RuntimeError):
    pass


class GoalGate:
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

    # ------------------------------------------------------------------
    # Admission (spec 8 steps 1-10)
    # ------------------------------------------------------------------

    def admit(self, proposal_text: str) -> AdmittedMission:
        contract = parse_mission(proposal_text)
        self._bind_repository(contract)
        self._bind_toolchain(contract)
        self._bind_verifier_executables(contract)
        contract_digest = contract.digest()
        mission_key = derive_mission_key(
            contract.repository.canonical_remote,
            contract.repository.base_sha,
            contract_digest,
        )
        attempt_uuid = str(uuid.uuid4())
        attempt_key = derive_attempt_key(mission_key, attempt_uuid)
        mission_dir = self.state_root / "missions" / mission_key
        attempt_dir = mission_dir / "attempts" / attempt_key
        attempt_dir.mkdir(parents=True, exist_ok=False)
        (mission_dir / "identity.json").write_text(contract.canonical_json() + "\n")
        proposal_path = mission_dir / "proposal.json"
        proposal_path.write_text(contract.canonical_json() + "\n")
        _fsync_file(proposal_path)
        journal = Journal(attempt_dir / "run.jsonl", mission_key, attempt_key)
        journal.append("PROPOSAL_VALIDATED", {"contract_digest": contract_digest})

        workcell = Workcell(
            attempt_dir, self.repo_path, contract.repository.base_sha, self.state_root
        )
        base_digests = self.base_digests()
        journal.effect_intent("workcell-create", {"base": contract.repository.base_sha})
        workcell.create()
        pointer_sha = sha256_file(workcell.worktree / ".git")
        journal.effect_result(
            "workcell-create",
            {"worktree": str(workcell.worktree), "pointer_sha256": pointer_sha},
        )
        admitted = AdmittedMission(
            contract=contract,
            contract_digest=contract_digest,
            mission_key=mission_key,
            attempt_key=attempt_key,
            attempt_uuid=attempt_uuid,
            mission_dir=str(mission_dir),
            attempt_dir=str(attempt_dir),
            base_digests=base_digests,
            git_pointer_sha256=pointer_sha,
        )
        baseline = self.evaluate(admitted, baseline=True)
        if baseline.green and contract.result.require_baseline_red:
            journal.append(
                "ADMISSION_REJECTED", {"code": str(AdmissionReject.ALREADY_SATISFIED)}
            )
            workcell.quarantine("baseline green under require_baseline_red")
            raise AdmissionError(
                AdmissionReject.ALREADY_SATISFIED,
                "gate is green at base; not a RUDRA success",
            )
        admitted_path = mission_dir / "admitted.json"
        admitted_path.write_text(contract.canonical_json() + "\n")
        _fsync_file(admitted_path)
        (attempt_dir / "attempt.json").write_text(
            json.dumps(
                {
                    "attempt_uuid": attempt_uuid,
                    "git_pointer_sha256": pointer_sha,
                    "base_digests": base_digests,
                },
                sort_keys=True,
            )
            + "\n"
        )
        _fsync_file(attempt_dir / "attempt.json")
        fd = os.open(mission_dir, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        journal.append("ADMITTED", {"contract_digest": contract_digest})
        return admitted.model_copy(update={"baseline": baseline})

    def rehash_admitted(self, admitted: AdmittedMission) -> None:
        """The admitted copy is rehashed before every effect (invariant 2)."""
        raw = (Path(admitted.mission_dir) / "admitted.json").read_bytes().strip()
        if hashlib.sha256(raw).hexdigest() != admitted.contract_digest:
            raise GoalGateError("admitted.json digest drift")

    def base_digests(self) -> dict[str, str]:
        head = (self.repo_path / ".git" / "HEAD").read_bytes()
        index = self.repo_path / ".git" / "index"
        status = _git(self.repo_path, self.env, "status", "--porcelain=v1", "-z")
        listing = _git(self.repo_path, self.env, "ls-files", "--stage", "-z")
        return {
            "head_sha256": hashlib.sha256(head).hexdigest(),
            "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest()
            if index.exists() else "",
            "status_sha256": hashlib.sha256(status.encode()).hexdigest(),
            "lsfiles_sha256": hashlib.sha256(listing.encode()).hexdigest(),
        }

    def prove_base_preserved(self, admitted: AdmittedMission) -> bool:
        return self.base_digests() == admitted.base_digests

    # ------------------------------------------------------------------
    # Binding
    # ------------------------------------------------------------------

    def _bind_repository(self, contract: RudraMissionContract) -> None:
        actual = _git(self.repo_path, self.env, "config", "--get", "remote.origin.url").strip()
        expected = contract.repository.canonical_remote
        if actual.removesuffix(".git") != expected.removesuffix(".git"):
            # A match only under case folding is rejected as a collision too.
            raise AdmissionError(
                AdmissionReject.REJECT_INVALID,
                f"canonical remote mismatch: {actual!r} != {expected!r}",
            )
        probe = subprocess.run(
            ["/usr/bin/git", "cat-file", "-e",
             f"{contract.repository.base_sha}^{{commit}}"],
            cwd=self.repo_path, env=self.env, timeout=15,
        )
        if probe.returncode != 0:
            raise AdmissionError(
                AdmissionReject.REJECT_INVALID,
                f"base {contract.repository.base_sha} not present locally",
            )

    def _bind_toolchain(self, contract: RudraMissionContract) -> None:
        lock = self.repo_path / contract.toolchain.lockfile.path
        if not lock.exists() or sha256_file(lock) != contract.toolchain.lockfile.sha256:
            raise AdmissionError(
                AdmissionReject.REJECT_INVALID, "lockfile digest mismatch"
            )
        for name, binding in contract.toolchain.executables.items():
            path = Path(binding.path)
            if not path.is_absolute():
                raise AdmissionError(
                    AdmissionReject.REJECT_INVALID, f"{name} path must be absolute"
                )
            if not path.exists():
                raise AdmissionError(
                    AdmissionReject.BLOCKED_ENVIRONMENT,
                    f"executable missing: {path}",
                )
            if sha256_file(path) != binding.sha256:
                raise AdmissionError(
                    AdmissionReject.REJECT_INVALID,
                    f"executable digest mismatch for {name}",
                )
            version = _version_output(path)
            if version != binding.version:
                raise AdmissionError(
                    AdmissionReject.BLOCKED_ENVIRONMENT,
                    f"executable {name} version drift: {version!r}",
                )

    def _bind_verifier_executables(self, contract: RudraMissionContract) -> None:
        bound = {b.path for b in contract.toolchain.executables.values()}
        for command in contract.acceptance.commands:
            argv0 = command.argv[0]
            if not Path(argv0).is_absolute() or argv0 not in bound:
                raise AdmissionError(
                    AdmissionReject.REJECT_INVALID,
                    f"verifier {command.id} executable not bound in toolchain",
                )

    # ------------------------------------------------------------------
    # Scope inventory (spec 8)
    # ------------------------------------------------------------------

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
                show = subprocess.run(
                    ["/usr/bin/git", "show",
                     f"{contract.repository.base_sha}:{path}"],
                    cwd=root, env=self.env, capture_output=True, text=True, timeout=30,
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

    # ------------------------------------------------------------------
    # Verifier execution (spec 8)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Candidate freeze and terminal evaluation (spec 8)
    # ------------------------------------------------------------------

    def freeze_candidate(self, admitted: AdmittedMission, gate: GateResult) -> str:
        """Stage only admitted changed paths in the private gitdir; commit on
        the private candidate ref with hooks and signing disabled."""
        contract = admitted.contract
        workcell = Workcell(
            Path(admitted.attempt_dir), self.repo_path,
            contract.repository.base_sha, self.state_root,
        )
        root = workcell.worktree
        if not gate.changed_paths:
            raise GoalGateError("cannot freeze an empty change set")
        attrs = _git(root, self.env, "check-attr", "filter", "--", *gate.changed_paths)
        lines = [ln for ln in attrs.splitlines() if ln.strip()]
        if len(lines) != len(gate.changed_paths) or any(
            not ln.endswith("filter: unspecified") for ln in lines
        ):
            raise GoalGateError("clean/smudge filter present in changed paths")
        workcell.git("add", "--", *gate.changed_paths)
        staged = workcell.git("diff", "--cached", "--name-only", "-z")
        if {p for p in staged.split("\0") if p} != set(gate.changed_paths):
            raise GoalGateError("staged set differs from admitted changed paths")
        workcell.git(
            "-c", "user.name=RUDRA", "-c", "user.email=rudra@localhost",
            "commit", "--no-verify", "--no-gpg-sign", "-q",
            "-m", f"rudra candidate {admitted.attempt_key}",
        )
        candidate = workcell.head_sha()
        workcell.git(
            "--git-dir", str(workcell.private_git), "update-ref",
            "refs/rudra/candidate", candidate,
        )
        ancestor = subprocess.run(
            ["/usr/bin/git", "merge-base", "--is-ancestor",
             contract.repository.base_sha, candidate],
            cwd=root, env=self.env,
        )
        if ancestor.returncode != 0:
            raise GoalGateError("candidate does not descend from the admitted base")
        if self._porcelain_paths(root):
            raise GoalGateError("workcell not clean after candidate commit")
        return candidate

    def verify_candidate(
        self, admitted: AdmittedMission, candidate_sha: str
    ) -> GoalGatePassed:
        """Fresh detached verification workcell at the candidate; full gate;
        any repository write invalidates the result."""
        contract = admitted.contract
        run_id = uuid.uuid4().hex
        attempt_dir = Path(admitted.attempt_dir)
        vroot = attempt_dir / "verification" / run_id / "repo"
        vgit = attempt_dir / "verification" / run_id / "private.git"
        vroot.mkdir(parents=True)
        vgit.mkdir(parents=True)
        mutation = Workcell(
            attempt_dir, self.repo_path, contract.repository.base_sha, self.state_root
        )
        _git(attempt_dir, self.env, "init", "--bare", str(vgit))
        alternates = vgit / "objects" / "info" / "alternates"
        alternates.parent.mkdir(parents=True, exist_ok=True)
        alternates.write_text(
            f"{mutation.private_git}/objects\n{self.repo_path}/.git/objects\n"
        )
        (vroot / ".git").write_text(f"gitdir: {vgit}\n")
        _git(vroot, self.env, "--git-dir", str(vgit), "config", "core.worktree", str(vroot))
        _git(vroot, self.env, "--git-dir", str(vgit), "config", "core.bare", "false")
        _git(vroot, self.env, "--git-dir", str(vgit), "update-ref",
             "--no-deref", "HEAD", candidate_sha)
        _git(vroot, self.env, "read-tree", "HEAD")
        _git(vroot, self.env, "checkout-index", "-f", "-a")
        vpointer_sha = sha256_file(vroot / ".git")
        self._chmod_tree(vroot, read_only=True)
        try:
            tree_before = _git(vroot, self.env, "rev-parse", "HEAD^{tree}").strip()
            if self._porcelain_paths(vroot):
                raise GoalGateError("verification workcell not clean at start")
            gate = self.evaluate(
                admitted, root=vroot, gate_run_id=run_id, pointer_sha256=vpointer_sha
            )
            if self._porcelain_paths(vroot):
                raise GoalGateError("verification workcell mutated by a verifier")
            if sha256_file(vroot / ".git") != vpointer_sha:
                raise GoalGateError("verification workcell .git pointer mutated")
            if _git(vroot, self.env, "rev-parse", "HEAD^{tree}").strip() != tree_before:
                raise GoalGateError("verification workcell tree digest drifted")
        finally:
            self._chmod_tree(vroot, read_only=False)
        if not gate.green:
            raise CandidateRejected("; ".join(gate.reasons))
        return GoalGatePassed(
            mission_id=contract.mission_id,
            attempt_id=admitted.attempt_key,
            base_sha=contract.repository.base_sha,
            candidate_sha=candidate_sha,
            contract_digest=admitted.contract_digest,
            verification_workcell_id=run_id,
            workspace_digest=gate.subject_digest,
            changed_path_digest=sha256_json(gate.changed_paths),
            verifier_run_id=gate.verifier_run_id,
            ordered_verifier_receipt_digests=[
                sha256_json(r.model_dump(mode="json")) for r in gate.receipts
            ],
            codex_version=contract.executor.binary.version,
            schema_digest=contract.executor.protocol_schema_sha256,
            completed_at=time.time(),
        )

    def _chmod_tree(self, root: Path, *, read_only: bool) -> None:
        for dirpath, dirnames, filenames in os.walk(root):
            for name in dirnames:
                path = Path(dirpath) / name
                try:
                    mode = stat.S_IMODE(path.stat().st_mode)
                    path.chmod(mode & ~0o222 if read_only else mode | 0o700)
                except OSError:
                    pass
            for name in filenames:
                path = Path(dirpath) / name
                try:
                    mode = stat.S_IMODE(path.stat().st_mode)
                    path.chmod(mode & ~0o222 if read_only else mode | 0o200)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # The one epistemic type edge (spec 9)
    # ------------------------------------------------------------------

    def promote(
        self,
        reported: ReportedCompletion | None,
        passed: GoalGatePassed,
        admitted: AdmittedMission,
        current_workspace_digest: str,
    ) -> ReproducedCompletion:
        """Sole constructor of reproduced completion. No conversion method
        exists on ReportedCompletion; this boundary is the obligation."""
        if passed.contract_digest != admitted.contract_digest:
            raise PromotionRejected("contract digest mismatch")
        if passed.workspace_digest != current_workspace_digest:
            raise PromotionRejected("workspace digest is not current")
        if reported is not None and reported.candidate_sha != passed.candidate_sha:
            raise PromotionRejected("reported candidate differs from proven candidate")
        return ReproducedCompletion(
            _gate_token=_GATE_TOKEN,
            mission_id=passed.mission_id,
            attempt_id=passed.attempt_id,
            base_sha=passed.base_sha,
            candidate_sha=passed.candidate_sha,
            contract_digest=passed.contract_digest,
            workspace_digest=passed.workspace_digest,
            verifier_run_id=passed.verifier_run_id,
            gate_passed_digest=sha256_json(passed.model_dump(mode="json")),
        )
