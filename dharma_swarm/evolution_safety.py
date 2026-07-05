"""Fail-closed safety substrate for all self-modification / evolution paths (PR-001).

Polarity inversion (PR-001): live mutation of the running organism is
IMPOSSIBLE by default. It becomes possible only when ALL of the following
hold simultaneously — and while lease infrastructure is incomplete, the lease
check can never pass, so live mutation stays impossible:

  1. the write target is a *marked scratch evolution worktree* (never the live
     checkout / main repo root),
  2. ``DHARMA_ALLOW_LIVE_MUTATION=1`` is explicitly set,
  3. a valid, unexpired live-mutation lease (referencing a human promotion
     receipt) exists,
  4. a durable RuntimeStateStore is available to receipt the mutation.

Everything else is shadow-only, and every attempt — allowed, downgraded, or
denied — produces a receipt.

This module is intentionally dependency-light (stdlib + lazy imports only) so
every producer (DiffApplier, SelfImprovementCycle, DarwinEngine, free-grind,
custodians) can import it without circular-ownership problems.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# ---------------------------------------------------------------------------
# Fail-closed defaults — the SAFE state requires no configuration.
# ---------------------------------------------------------------------------

SAFE_DEFAULTS: dict[str, str] = {
    "DHARMA_EVOLUTION_SHADOW": "1",   # 1 = dry-run / shadow (never mutate source)
    "DHARMA_SELF_IMPROVE": "0",       # 0 = self-improvement disabled
    "DHARMA_ALLOW_LIVE_MUTATION": "0",  # 0 = live mutation forbidden
    "DGC_AUTONOMY_LEVEL": "1",        # never default to 2
}

EVOLUTION_MARKER = ".dharma_evolution_worktree.json"
REQUIRED_MARKER_FIELDS = ("experiment_id", "git_base_sha", "created_at", "archive_path")

# Live checkouts that must never be a mutation target.
_PROTECTED_LITERAL_ROOTS = (
    Path.home() / "dharma_swarm",
    Path("/root/dharma_swarm"),
    Path("/home/openclaw/dharma_swarm"),
    Path("/Users/dhyana/dharma_swarm"),
    Path("/app/dharma_swarm"),  # container source mount
)

_DEFAULT_MUTATION_RECEIPT_LOG = (
    Path.home() / ".dharma" / "evolution" / "mutation_receipts.jsonl"
)
_LIVE_MUTATION_LEASE_DIR = Path.home() / ".dharma" / "leases" / "live_mutation"
_DEFAULT_EVALUATOR_MOUNT = Path("/mnt/dharma_eval")


class LiveMutationDenied(RuntimeError):
    """Raised when a mutation targets the live organism or lacks authority."""


# ---------------------------------------------------------------------------
# Env accessors (fail-closed)
# ---------------------------------------------------------------------------

def env_default(name: str, hard_default: str = "") -> str:
    return os.environ.get(name, SAFE_DEFAULTS.get(name, hard_default))


def shadow_enabled() -> bool:
    """True unless DHARMA_EVOLUTION_SHADOW is explicitly '0'. Default: shadow ON."""
    return env_default("DHARMA_EVOLUTION_SHADOW", "1") != "0"


def self_improve_enabled() -> bool:
    """True only if DHARMA_SELF_IMPROVE == '1'. Default: OFF."""
    return env_default("DHARMA_SELF_IMPROVE", "0") == "1"


def autonomy_level() -> int:
    try:
        return int(env_default("DGC_AUTONOMY_LEVEL", "1"))
    except (TypeError, ValueError):
        return 0


def allow_live_mutation_env() -> bool:
    """The explicit opt-in flag. Necessary but NEVER sufficient on its own."""
    return env_default("DHARMA_ALLOW_LIVE_MUTATION", "0") == "1"


# ---------------------------------------------------------------------------
# Scratch worktree recognition
# ---------------------------------------------------------------------------

def evolution_worktree_roots() -> tuple[Path, ...]:
    roots = [
        Path.home() / ".dharma" / "evolution_worktrees",
        Path("/evolution_worktrees"),
    ]
    env_root = os.environ.get("DHARMA_EVOLUTION_WORKTREE_ROOT")
    if env_root:
        roots.insert(0, Path(env_root))
    return tuple(r.resolve() for r in roots if str(r))


@dataclass(frozen=True)
class WorktreeMarker:
    experiment_id: str
    git_base_sha: str
    created_at: str
    archive_path: str
    parent_id: str = ""
    candidate_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def _resolve(path: Path | str) -> Path:
    try:
        return Path(path).expanduser().resolve()
    except (OSError, RuntimeError):
        return Path(path).expanduser()


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def load_worktree_marker(workspace: Path | str) -> WorktreeMarker | None:
    marker_path = _resolve(workspace) / EVOLUTION_MARKER
    if not marker_path.is_file():
        return None
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if any(not str(data.get(f, "")).strip() for f in REQUIRED_MARKER_FIELDS):
        return None
    return WorktreeMarker(
        experiment_id=str(data["experiment_id"]),
        git_base_sha=str(data["git_base_sha"]),
        created_at=str(data["created_at"]),
        archive_path=str(data["archive_path"]),
        parent_id=str(data.get("parent_id", "")),
        candidate_id=str(data.get("candidate_id", "")),
        raw=data,
    )


def is_scratch_worktree(workspace: Path | str) -> tuple[bool, WorktreeMarker | None, str]:
    """A workspace is a valid scratch worktree iff it lives under an approved
    evolution-worktree root AND contains a well-formed evolution marker."""
    resolved = _resolve(workspace)
    under_root = any(
        resolved == root or _is_within(resolved, root)
        for root in evolution_worktree_roots()
    )
    if not under_root:
        return (False, None, "not under an evolution_worktrees root")
    marker = load_worktree_marker(resolved)
    if marker is None:
        return (False, None, f"missing/invalid {EVOLUTION_MARKER} marker")
    return (True, marker, "ok")


def is_protected_live_root(workspace: Path | str) -> bool:
    """True if the workspace is (or is inside) a known live checkout / main repo
    root — unless it is an approved scratch worktree."""
    resolved = _resolve(workspace)
    scratch, _, _ = is_scratch_worktree(resolved)
    if scratch:
        return False
    for root in _PROTECTED_LITERAL_ROOTS:
        r = _resolve(root)
        if resolved == r or _is_within(resolved, r):
            return True
    detected = _detect_main_repo_root(resolved)
    if detected is not None:
        return True
    return False


def _detect_main_repo_root(workspace: Path) -> Path | None:
    """Return the enclosing dharma_swarm main-repo root if `workspace` is inside
    one (a dir containing both `.git` and a `dharma_swarm/` package), else None."""
    cur = workspace
    for _ in range(40):
        try:
            if (cur / ".git").exists() and (cur / "dharma_swarm" / "__init__.py").is_file():
                return cur
        except OSError:
            return None
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


# ---------------------------------------------------------------------------
# Live-mutation lease (infra incomplete → always denies)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LiveMutationLease:
    lease_id: str
    target_sha: str
    promotion_receipt: str
    granted_by_human: str
    expires_at: str


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_live_mutation_lease(
    *, lease_dir: Path | None = None
) -> LiveMutationLease | None:
    """Load and strictly validate a live-mutation lease. Returns None unless a
    complete, unexpired, human-granted, promotion-backed lease exists. While
    lease infrastructure is incomplete this returns None in every real
    deployment — keeping live mutation impossible."""
    d = (lease_dir or _LIVE_MUTATION_LEASE_DIR)
    try:
        if not d.is_dir():
            return None
        candidates = sorted(d.glob("*.json"))
    except OSError:
        return None
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        required = ("lease_id", "target_sha", "promotion_receipt",
                    "granted_by_human", "expires_at")
        if any(not str(data.get(f, "")).strip() for f in required):
            continue
        try:
            expires = datetime.fromisoformat(str(data["expires_at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= _now_utc():
            continue
        return LiveMutationLease(
            lease_id=str(data["lease_id"]),
            target_sha=str(data["target_sha"]),
            promotion_receipt=str(data["promotion_receipt"]),
            granted_by_human=str(data["granted_by_human"]),
            expires_at=str(data["expires_at"]),
        )
    return None


# ---------------------------------------------------------------------------
# The single mutation decision
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MutationDecision:
    allowed: bool
    effective_shadow: bool
    requested_live: bool
    target_workspace: str
    is_scratch: bool
    is_protected: bool
    runtime_state_available: bool
    lease_id: str
    denial_reason: str


def evaluate_mutation(
    *,
    target_workspace: Path | str,
    requested_live: bool,
    runtime_state_available: bool,
    lease_dir: Path | None = None,
) -> MutationDecision:
    """The ONE decision function every mutation path consults.

    Rules (fail-closed):
      * A protected live root is never writable -> denied outright.
      * Live (real) apply requires: scratch worktree + explicit opt-in env +
        valid lease + durable runtime_state. Missing any -> downgrade to shadow
        (if in a scratch worktree) or deny.
      * Shadow apply is allowed in a scratch worktree, and (for backward-compat
        with sandbox/test tmp dirs) in any non-protected dir.
    """
    resolved = _resolve(target_workspace)
    scratch, _marker, _why = is_scratch_worktree(resolved)
    protected = is_protected_live_root(resolved)

    if protected:
        return MutationDecision(
            allowed=False, effective_shadow=True, requested_live=requested_live,
            target_workspace=str(resolved), is_scratch=False, is_protected=True,
            runtime_state_available=runtime_state_available, lease_id="",
            denial_reason=f"protected_live_root:{resolved}",
        )

    lease = load_live_mutation_lease(lease_dir=lease_dir) if requested_live else None
    live_ok = bool(
        requested_live
        and scratch
        and allow_live_mutation_env()
        and lease is not None
        and runtime_state_available
    )
    if requested_live and not live_ok:
        # Downgrade rather than mutate live: allowed as shadow inside scratch.
        reasons = []
        if not scratch:
            reasons.append("not_scratch_worktree")
        if not allow_live_mutation_env():
            reasons.append("DHARMA_ALLOW_LIVE_MUTATION!=1")
        if lease is None:
            reasons.append("no_valid_live_mutation_lease")
        if not runtime_state_available:
            reasons.append("no_runtime_state")
        return MutationDecision(
            allowed=True, effective_shadow=True, requested_live=True,
            target_workspace=str(resolved), is_scratch=scratch, is_protected=False,
            runtime_state_available=runtime_state_available, lease_id="",
            denial_reason="live_downgraded_to_shadow:" + ",".join(reasons),
        )
    if live_ok:
        return MutationDecision(
            allowed=True, effective_shadow=False, requested_live=True,
            target_workspace=str(resolved), is_scratch=True, is_protected=False,
            runtime_state_available=runtime_state_available,
            lease_id=lease.lease_id if lease else "",
            denial_reason="",
        )
    # Shadow request (requested_live=False): allowed in any non-protected dir.
    return MutationDecision(
        allowed=True, effective_shadow=True, requested_live=False,
        target_workspace=str(resolved), is_scratch=scratch, is_protected=False,
        runtime_state_available=runtime_state_available, lease_id="",
        denial_reason="",
    )


def guard_writable_target(workspace: Path | str) -> None:
    """Low-level backstop used by DiffApplier before any write. Refuses protected
    live roots unconditionally (raises). Non-protected dirs pass through."""
    if is_protected_live_root(workspace):
        raise LiveMutationDenied(
            f"refusing to mutate protected live checkout: {_resolve(workspace)} "
            f"(evolution writes must target a marked scratch worktree)"
        )


# ---------------------------------------------------------------------------
# Runtime code identity
# ---------------------------------------------------------------------------

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
    mode: str  # dev | lab | production | non_promotable
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
        """Never raises — unknown metadata becomes 'unknown' and forces
        mode=non_promotable."""
        rp = _resolve(repo_path or Path.cwd())
        sha = _git(["rev-parse", "HEAD"], rp) or "unknown"
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], rp) or "unknown"
        status = _git(["status", "--porcelain"], rp)
        dirty: bool | None
        untracked: bool | None
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

        if reasons:
            mode = "non_promotable"
        else:
            mode = os.environ.get("DHARMA_RUNTIME_MODE", "lab")
        return cls(
            repo_path=str(rp), git_sha=sha, branch=branch, dirty=dirty,
            untracked=untracked, ahead=ahead, behind=behind,
            docker_image_digest=digest, evaluator_sha=ev.get("sha", ""),
            config_hash=config_hash, started_at=started_at or _now_iso(),
            mode=mode, reason="; ".join(reasons),
        )


def _now_iso() -> str:
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
        k for k in os.environ
        if k.startswith(("DHARMA_", "DGC_")) and "KEY" not in k and "SECRET" not in k
    )
    blob = "\n".join(f"{k}={os.environ[k]}" for k in keys)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Protected evaluator / source-mount contracts
# ---------------------------------------------------------------------------

def evaluator_status(mount: Path | None = None) -> dict[str, Any]:
    """Recognize a protected evaluator mount. promotion_grade_available is True
    ONLY when the evaluator is mounted, read-only, and carries a SHA."""
    m = _resolve(mount or _DEFAULT_EVALUATOR_MOUNT)
    mounted = m.is_dir()
    if not mounted:
        return {"mounted": False, "read_only": False, "sha": "",
                "promotion_grade_available": False, "path": str(m)}
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
        "mounted": True, "read_only": read_only, "sha": sha,
        "promotion_grade_available": bool(read_only and sha),
        "path": str(m),
    }


def source_mount_status(path: Path | str) -> dict[str, Any]:
    """A read-only source mount is *safer* but never *sufficient* on its own."""
    p = _resolve(path)
    exists = p.exists()
    read_only = exists and not os.access(str(p), os.W_OK)
    return {
        "path": str(p), "exists": exists, "read_only": read_only,
        "sufficient_alone": False,
    }


# ---------------------------------------------------------------------------
# Mutation receipts (allowed, downgraded, and denied)
# ---------------------------------------------------------------------------

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
    """Write a receipt for a mutation attempt. Uses RuntimeStateStore when
    available AND always appends to a local JSONL fail-closed ledger. Denied and
    downgraded attempts are receipted just like allowed ones."""
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
                    recorder(ident, stage="guard", status=(
                        "allowed" if decision.allowed else "denied"),
                        payload=receipt)
            except Exception:
                pass  # receipting must never break the guard

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


# ---------------------------------------------------------------------------
# Budget / lease gate for model spend
# ---------------------------------------------------------------------------

def model_spend_allowed() -> tuple[bool, str]:
    """Model spend is disabled unless an explicit budget/lease gate is present.
    A budget gate is present when DHARMA_MODEL_BUDGET_USD is set > 0 OR a live
    budget lease file exists. Absent gate -> denied (fail-closed)."""
    raw = os.environ.get("DHARMA_MODEL_BUDGET_USD", "").strip()
    if raw:
        try:
            if float(raw) > 0:
                return (True, f"budget_env:{raw}")
        except ValueError:
            pass
    lease = load_live_mutation_lease()
    if lease is not None:
        return (True, f"lease:{lease.lease_id}")
    return (False, "no_budget_gate")


# ---------------------------------------------------------------------------
# Startup safety summary
# ---------------------------------------------------------------------------

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
