"""RUDRA GoalGate admission leaf: binding, digests, and mission intake.

Leaf module of ``goal_gate``: owns ``GoalGateError``, ``AdmittedMission``,
the admission mixin (spec section 8 steps 1-10), and the hashing/git
helpers shared by the gate core and the verification leaf. It never
imports the gate-core or verification modules — the dependency direction
is ``goal_gate`` -> ``goal_gate_verify`` -> ``goal_gate_admission`` only.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md section 8.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from dharma_swarm.rudra.contracts import (
    AdmissionError,
    AdmissionReject,
    GateResult,
    RudraMissionContract,
    derive_attempt_key,
    derive_mission_key,
    parse_mission,
)
from dharma_swarm.rudra.workcell import (
    Journal,
    Workcell,
    WorkcellError,
    require_git_ok,
    run_git,
)


class GoalGateError(RuntimeError):
    pass


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
    try:
        return require_git_ok(
            run_git(list(args), cwd=root, env=env, timeout=timeout), args[0]
        )
    except WorkcellError as exc:
        raise GoalGateError(str(exc)) from exc


class GoalGateAdmission:
    """Admission mixin (spec 8 steps 1-10). Host class provides
    ``repo_path``, ``state_root``, ``env``, and ``evaluate``."""

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

    # --- Binding (spec 8 steps 2, 5) ---------------------------------------

    def _bind_repository(self, contract: RudraMissionContract) -> None:
        actual = _git(self.repo_path, self.env, "config", "--get", "remote.origin.url").strip()
        expected = contract.repository.canonical_remote
        if actual.removesuffix(".git") != expected.removesuffix(".git"):
            # A match only under case folding is rejected as a collision too.
            raise AdmissionError(
                AdmissionReject.REJECT_INVALID,
                f"canonical remote mismatch: {actual!r} != {expected!r}",
            )
        probe = run_git(
            ["cat-file", "-e", f"{contract.repository.base_sha}^{{commit}}"],
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
