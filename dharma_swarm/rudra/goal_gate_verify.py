"""RUDRA GoalGate verification leaf: freeze, fresh detached verify, promote.

Leaf module of ``goal_gate``: owns the candidate freeze and terminal
verification mixin (spec section 8) and the one epistemic type edge,
``promote`` (spec section 9). It never imports the gate-core module — the
dependency direction is ``goal_gate`` -> ``goal_gate_verify`` ->
``goal_gate_admission`` only. The host class provides ``repo_path``,
``state_root``, ``env``, ``evaluate``, and ``_porcelain_paths``.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md sections 8-9.
"""

from __future__ import annotations

import os
import stat
import time
import uuid
from pathlib import Path

from dharma_swarm.rudra.contracts import (
    GateResult,
    GoalGatePassed,
    ReportedCompletion,
    ReproducedCompletion,
    _GATE_TOKEN,
    sha256_json,
)
from dharma_swarm.rudra.goal_gate_admission import (
    AdmittedMission,
    GoalGateError,
    _git,
    sha256_file,
)
from dharma_swarm.rudra.workcell import Workcell, init_private_git, run_git


class PromotionRejected(ValueError):
    pass


class CandidateRejected(ValueError):
    """Final verification red; the candidate is preserved as evidence."""


class GoalGateVerify:
    """Candidate freeze and terminal evaluation mixin (spec 8) plus the
    sole completion constructor (spec 9)."""

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
        ancestor = run_git(
            ["merge-base", "--is-ancestor", contract.repository.base_sha, candidate],
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
        # Fresh detached verification gitdir at the candidate, built per run;
        # the mutation gitdir is never reused for final verification (R7/R8).
        init_private_git(
            vgit,
            vroot,
            alternates=[
                f"{mutation.private_git}/objects",
                f"{self.repo_path}/.git/objects",
            ],
            ref_steps=[["update-ref", "--no-deref", "HEAD", candidate_sha]],
            env=self.env,
        )
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
            for name in (*dirnames, *filenames):
                path = Path(dirpath) / name
                restore = 0o700 if path.is_dir() else 0o200
                try:
                    mode = stat.S_IMODE(path.stat().st_mode)
                    path.chmod(mode & ~0o222 if read_only else mode | restore)
                except OSError:
                    pass

    # --- The one epistemic type edge (spec 9) -------------------------------

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
