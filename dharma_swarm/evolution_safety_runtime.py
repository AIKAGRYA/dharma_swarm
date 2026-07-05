"""Runtime identity, receipts, and budget helpers for evolution safety."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.evolution_safety import (
    MutationDecision,
    _resolve,
    allow_live_mutation_env,
    autonomy_level,
    load_live_mutation_lease,
    self_improve_enabled,
    shadow_enabled,
)

_DEFAULT_MUTATION_RECEIPT_LOG = (
    Path.home() / ".dharma" / "evolution" / "mutation_receipts.jsonl"
)
_DEFAULT_EVALUATOR_MOUNT = Path("/mnt/dharma_eval")


def _git(args: list[str], cwd: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=8
        )
        if out.returncode != 0:
            return None
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


@dataclass(frozen=True)
class RuntimeCodeIdentity:
    repo_path: str
    git_sha: str
    branch: str
    dirty: bool | None
    untracked: bool | None
    ahead: int | None
    behind: int | None
    docker_image_digest: str
    evaluator_sha: str
    config_hash: str
    started_at: str
    mode: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def capture(
        cls,
        repo_path: Path | str | None = None,
        *,
        started_at: str = "",
        evaluator_mount: Path | None = None,
    ) -> "RuntimeCodeIdentity":
        """Never raises: unknown metadata becomes non_promotable."""
        rp = _resolve(repo_path or Path.cwd())
        sha = _git(["rev-parse", "HEAD"], rp) or "unknown"
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], rp) or "unknown"
        status = _git(["status", "--porcelain"], rp)
        if status is None:
            dirty = untracked = None
        else:
            lines = [ln for ln in status.splitlines() if ln.strip()]
            dirty = any(not ln.startswith("??") for ln in lines)
            untracked = any(ln.startswith("??") for ln in lines)
        ahead = behind = None
        lr = _git(["rev-list", "--left-right", "--count", "origin/main...HEAD"], rp)
        if lr and len(lr.split()) == 2:
            try:
                behind, ahead = (int(x) for x in lr.split())
            except ValueError:
                ahead = behind = None
        digest = os.environ.get("DHARMA_IMAGE_DIGEST", "") or _detect_docker_digest()
        ev = evaluator_status(evaluator_mount)
        config_hash = _config_hash()

        reasons: list[str] = []
        if sha == "unknown" or branch == "unknown":
            reasons.append("git_metadata_unavailable")
        if dirty:
            reasons.append("dirty_worktree")
        if untracked:
            reasons.append("untracked_files")
        if dirty is None or untracked is None:
            reasons.append("worktree_status_unknown")
        if behind is not None and behind > 0:
            reasons.append(f"behind_origin_main:{behind}")

        mode = "non_promotable" if reasons else os.environ.get("DHARMA_RUNTIME_MODE", "lab")
        return cls(
            repo_path=str(rp),
            git_sha=sha,
            branch=branch,
            dirty=dirty,
            untracked=untracked,
            ahead=ahead,
            behind=behind,
            docker_image_digest=digest,
            evaluator_sha=ev.get("sha", ""),
            config_hash=config_hash,
            started_at=started_at or _now_iso(),
            mode=mode,
            reason="; ".join(reasons),
        )


def _now_iso() -> str:
    from dharma_swarm.evolution_safety import _now_utc

    return _now_utc().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _detect_docker_digest() -> str:
    for p in (Path("/etc/dharma_image_digest"), Path("/app/.image_digest")):
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return ""


def _config_hash() -> str:
    keys = sorted(
        k
        for k in os.environ
        if k.startswith(("DHARMA_", "DGC_")) and "KEY" not in k and "SECRET" not in k
    )
    blob = "\n".join(f"{k}={os.environ[k]}" for k in keys)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def evaluator_status(mount: Path | None = None) -> dict[str, Any]:
    """Recognize a protected evaluator mount."""
    m = _resolve(mount or _DEFAULT_EVALUATOR_MOUNT)
    mounted = m.is_dir()
    if not mounted:
        return {
            "mounted": False,
            "read_only": False,
            "sha": "",
            "promotion_grade_available": False,
            "path": str(m),
        }
    read_only = not os.access(str(m), os.W_OK)
    sha = ""
    for name in ("EVALUATOR_SHA", ".evaluator_sha"):
        try:
            f = m / name
            if f.is_file():
                sha = f.read_text(encoding="utf-8").strip()
                break
        except OSError:
            continue
    if not sha:
        git_sha = _git(["rev-parse", "HEAD"], m)
        sha = git_sha or ""
    return {
        "mounted": True,
        "read_only": read_only,
        "sha": sha,
        "promotion_grade_available": bool(read_only and sha),
        "path": str(m),
    }


def source_mount_status(path: Path | str) -> dict[str, Any]:
    """A read-only source mount is safer but never sufficient on its own."""
    p = _resolve(path)
    exists = p.exists()
    read_only = exists and not os.access(str(p), os.W_OK)
    return {
        "path": str(p),
        "exists": exists,
        "read_only": read_only,
        "sufficient_alone": False,
    }


def write_mutation_receipt(
    decision: MutationDecision,
    *,
    actor: str = "",
    patch_hash: str = "",
    files_changed: list[str] | None = None,
    experiment_id: str = "",
    parent_id: str = "",
    candidate_id: str = "",
    code_identity: dict[str, Any] | None = None,
    tool_permissions: list[str] | None = None,
    budget_lease_id: str = "",
    evaluator_sha: str = "",
    archive_path: Path | str | None = None,
    runtime_state: Any | None = None,
) -> dict[str, Any]:
    """Write a receipt for a mutation attempt."""
    receipt = {
        "schema": "mutation_receipt.v1",
        "experiment_id": experiment_id,
        "mutation_attempt_id": f"mut_{uuid4().hex[:16]}",
        "parent_id": parent_id,
        "candidate_id": candidate_id,
        "code_identity": code_identity or {},
        "actor": actor,
        "target_workspace": decision.target_workspace,
        "patch_hash": patch_hash,
        "files_changed": files_changed or [],
        "requested_live": decision.requested_live,
        "effective_shadow": decision.effective_shadow,
        "allowed": decision.allowed,
        "denial_reason": decision.denial_reason,
        "runtime_state_available": decision.runtime_state_available,
        "timestamp": _now_iso(),
        "tool_permissions": tool_permissions or [],
        "budget_lease_id": budget_lease_id or decision.lease_id,
        "evaluator_sha": evaluator_sha,
        "archive_path": str(archive_path or ""),
    }

    if runtime_state is not None:
        recorder = getattr(runtime_state, "record_self_mod_receipt_sync", None)
        if callable(recorder):
            try:
                ident = getattr(runtime_state, "_last_identity", None)
                if ident is not None:
                    recorder(
                        ident,
                        stage="guard",
                        status=("allowed" if decision.allowed else "denied"),
                        payload=receipt,
                    )
            except Exception as exc:  # noqa: BLE001 - receipt mirror cannot weaken guard.
                receipt["runtime_state_receipt_error"] = (
                    f"{type(exc).__name__}: {exc}"
                )

    targets: list[Path] = []
    if archive_path:
        targets.append(_resolve(archive_path) / "mutation_receipts.jsonl")
    targets.append(_DEFAULT_MUTATION_RECEIPT_LOG)
    for target in targets:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(receipt, sort_keys=True) + "\n")
            break
        except OSError:
            continue
    return receipt


def patch_hash(diff_text: str) -> str:
    return hashlib.sha256((diff_text or "").encode("utf-8")).hexdigest()[:32]


def model_spend_allowed() -> tuple[bool, str]:
    """Model spend is disabled unless an explicit budget/lease gate exists."""
    raw = os.environ.get("DHARMA_MODEL_BUDGET_USD", "").strip()
    if raw:
        try:
            if float(raw) > 0:
                return (True, f"budget_env:{raw}")
        except ValueError:
            return (False, f"invalid_budget_env:{raw}")
    lease = load_live_mutation_lease()
    if lease is not None:
        return (True, f"lease:{lease.lease_id}")
    return (False, "no_budget_gate")


def safety_summary(
    repo_path: Path | str | None = None,
    *,
    evaluator_mount: Path | None = None,
) -> dict[str, Any]:
    ident = RuntimeCodeIdentity.capture(repo_path, evaluator_mount=evaluator_mount)
    ev = evaluator_status(evaluator_mount)
    budget_ok, budget_reason = model_spend_allowed()
    lease = load_live_mutation_lease()
    live_allowed = bool(allow_live_mutation_env() and lease is not None)
    if not live_allowed:
        why_no_live = []
        if not allow_live_mutation_env():
            why_no_live.append("DHARMA_ALLOW_LIVE_MUTATION!=1")
        if lease is None:
            why_no_live.append("no_valid_live_mutation_lease")
        live_denied_reason = ",".join(why_no_live)
    else:
        live_denied_reason = ""
    src = source_mount_status(ident.repo_path)
    return {
        "code_identity": ident.to_dict(),
        "source_writable": src["exists"] and not src["read_only"],
        "evolution_shadow": shadow_enabled(),
        "autonomy_level": autonomy_level(),
        "self_improve_enabled": self_improve_enabled(),
        "live_mutation_allowed": live_allowed,
        "live_mutation_denied_reason": live_denied_reason,
        "budget_gate_ok": budget_ok,
        "budget_gate_reason": budget_reason,
        "archive_path": str(Path.home() / ".dharma" / "evolution"),
        "evaluator": ev,
    }
