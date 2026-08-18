"""Read-only evidence collection for session status.

Collection only — no policy, no rendering, no writes, no network.  Every
function here observes the repository, toolchain, portfolio, and generated
projections and returns typed dicts shaped for the v2 receipt's
``stable_core`` and ``live_delta`` partitions. Deciding what the evidence
means is ``readiness.py``'s job.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .repository_identity import (
    RepositoryIdentityObservation,
    observe_repository_identity,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

# The canonical max-five first-read list. "onboard output" is the command
# itself; the remaining paths come from CANONICAL_DOC_STACK.md.
REQUIRED_READING = (
    "onboard output",
    "CLAUDE.md",
    "docs/governance/SWARM_GENOME.md",
    "docs/governance/ACTIVE_TRACK.yaml",
    "docs/governance/ANTI_SLOP_RULES.md",
)

# Instruction-custody surfaces hashed into the contract block.  These are the
# inputs whose silent change must invalidate any cached static section
# (cache input-manifest instruction-custody category).
CONTRACT_SOURCES = (
    "CLAUDE.md",
    "docs/governance/ACTIVE_TRACK.yaml",
    "docs/governance/ANTI_SLOP_RULES.md",
    "docs/governance/BUILD_SESSION_ENTRYPOINT.md",
    "docs/governance/CANONICAL_DOC_STACK.md",
    "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md",
    "docs/governance/REPOSITORY_IDENTITY.json",
    "docs/state/BROKEN_REGISTER.md",
    "pyproject.toml",
    "uv.lock",
)

_PROJECTION_STALE_MINUTES = 24 * 60


def _git_probe(*args: str, cwd: Path = REPO_ROOT) -> tuple[str, str]:
    """One read-only Git observation: ``(stdout, typed_error)``.

    ``typed_error`` is ``""`` on success; a nonzero exit, timeout, or OSError
    yields a non-empty typed string so callers can distinguish "empty output"
    from "probe failed" (O3R-B1)."""
    command = "git " + " ".join(args)
    try:
        proc = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "", f"timeout after 30s: {command}"
    except OSError as exc:
        return "", f"{type(exc).__name__}: {command}"
    if proc.returncode != 0:
        return "", f"exit {proc.returncode}: {command}"
    return proc.stdout.strip(), ""


def _git(*args: str, cwd: Path = REPO_ROOT) -> str:
    output, _error = _git_probe(*args, cwd=cwd)
    return output


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def repo_identity(
    observation: RepositoryIdentityObservation | None = None,
) -> dict[str, str]:
    """Stable repository identity: owner/repo, HEAD, branch."""
    observed = observation or observe_repository_identity(REPO_ROOT)
    return {
        "identity": observed.identity,
        "head": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
    }


def observe_repo_live_state(
    base_ref: str = "origin/main",
) -> tuple[dict[str, Any], dict[str, str]]:
    """Volatile repository state plus typed probe errors (O3R-B1).

    Returns ``(state, errors)`` where ``state`` keeps the exact five-key
    ``live_delta.repo_state`` shape the v2 receipt validates, and ``errors``
    maps probe name (``status``, ``ahead_behind``) to a typed error string.
    A failed status probe reports ``dirty=True`` fail-closed — the state is
    not provably clean.  Ahead/behind is contextual rather than admission
    truth, so its typed error can remain a non-blocking diagnostic when status
    itself was observed; the caller owns turning errors into conditions."""
    errors: dict[str, str] = {}
    status, error = _git_probe("status", "--porcelain")
    if error:
        errors["status"] = error
    conflicted = any(
        line[:2] in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
        for line in status.splitlines()
    )
    ahead = behind = 0
    counts, error = _git_probe(
        "rev-list", "--left-right", "--count", f"{base_ref}...HEAD"
    )
    if error:
        errors["ahead_behind"] = error
    else:
        left, _, right = counts.partition("\t")
        try:
            behind, ahead = int(left), int(right)
        except ValueError:
            ahead = behind = 0
            errors["ahead_behind"] = (
                f"malformed output: git rev-list --left-right --count {base_ref}...HEAD"
            )
    return {
        "base": base_ref,
        "dirty": bool(status) or "status" in errors,
        "conflicted": conflicted,
        "ahead": ahead,
        "behind": behind,
    }, errors


def repo_live_state(base_ref: str = "origin/main") -> dict[str, Any]:
    """Volatile repository state for the live partition."""
    state, _errors = observe_repo_live_state(base_ref)
    return state


def toolchain_versions() -> dict[str, str]:
    """Normalized versions of the universally required hermetic tools."""
    versions: dict[str, str] = {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }
    for tool in ("git", "make"):
        if shutil.which(tool) is None:
            versions[tool] = ""
            continue
        try:
            proc = subprocess.run(
                [tool, "--version"], capture_output=True, text=True, timeout=10,
            )
            first = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
            versions[tool] = first.strip()
        except (OSError, subprocess.TimeoutExpired, IndexError):
            versions[tool] = ""
    return versions


def contract_sources() -> dict[str, Any]:
    """Hash the instruction-custody surfaces the contract stands on."""
    hashes: dict[str, str] = {}
    for rel in CONTRACT_SOURCES:
        digest = _sha256_file(REPO_ROOT / rel)
        if digest:
            hashes[rel] = digest
    joined = "\n".join(f"{k}={v}" for k, v in sorted(hashes.items()))
    return {
        "required_files": sorted(hashes),
        "source_hashes": hashes,
        "contract_digest": hashlib.sha256(joined.encode("utf-8")).hexdigest(),
    }


def _load_yaml_tracks(path: Path) -> list[dict[str, Any]]:
    try:
        import yaml
    except ImportError:
        return _scrape_tracks(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return []
    rows = data.get("active_tracks") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _scrape_tracks(path: Path) -> list[dict[str, Any]]:
    """Dependency-light fallback: TOP-LEVEL track ids only, no nested detail.

    Only ``- id:`` items at the indent of the first list item directly under
    ``active_tracks:`` are tracks; deeper ``- id:`` rows (next_items,
    prerequisites, completion_criteria) are not."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    in_active = False
    item_indent: int | None = None
    for line in text.splitlines():
        if line.startswith("active_tracks:"):
            in_active = True
            continue
        if in_active and line and not line[0].isspace():
            break
        stripped = line.strip()
        if not in_active or not stripped.startswith("- id:"):
            continue
        indent = len(line) - len(line.lstrip())
        if item_indent is None:
            item_indent = indent
        if indent == item_indent:
            rows.append({"id": stripped.split(":", 1)[1].strip().strip("'\"")})
    return rows


def portfolio_snapshot() -> dict[str, Any]:
    """Static portfolio projection: declared track ids, never live status."""
    rows = _load_yaml_tracks(REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml")
    tracks = sorted(
        {str(row.get("id", "")) for row in rows if row.get("id")}
    )
    return {
        "tracks": tracks,
        "selected_track": "",
        "ownership_conflicts": [],
    }


def orientation_static() -> dict[str, Any]:
    """Static orientation over owner files, via the canonical parser only."""
    broken: dict[str, Any]
    try:
        from .broken_register import parse_broken_register

        parsed = parse_broken_register(REPO_ROOT / "docs/state/BROKEN_REGISTER.md")
        broken = {
            "total": parsed.total,
            "open_like": parsed.open_count,
            "closed_like": parsed.closed_count,
            "unknown": parsed.unknown_count,
        }
    except Exception as exc:  # canonical parser owns semantics; type the gap
        broken = {"error": f"{type(exc).__name__}"}
    surfaces = {
        rel: bool((REPO_ROOT / rel).exists())
        for rel in (
            "foundations/THE_ORGANISM.md",
            "docs/vision_maps/NORTH_STAR.md",
            "docs/MEGAFILE_INDEX.md",
            "INTERFACE_MISMATCH_MAP.md",
        )
    }
    return {
        "identity": {"repo_root": REPO_ROOT.name},
        "broken_register": broken,
        "static_surfaces": surfaces,
    }


def projection_freshness() -> dict[str, Any]:
    """Typed diagnostic freshness.  Never regenerates or gates a session."""
    rel = "reports/governance/active_track_evidence.json"
    path = REPO_ROOT / rel
    if not path.exists():
        return {rel: {"present": False, "age_minutes": None}}
    import time

    try:
        age_minutes = max(0.0, (time.time() - path.stat().st_mtime) / 60.0)
    except OSError:
        return {rel: {"present": False, "age_minutes": None}}
    return {
        rel: {
            "present": True,
            "age_minutes": round(age_minutes, 1),
            "stale": age_minutes > _PROJECTION_STALE_MINUTES,
        }
    }


def collect_stable_core(
    repository_observation: RepositoryIdentityObservation | None = None,
) -> dict[str, Any]:
    """Assemble the full v2 ``stable_core`` partition."""
    # The v2 receipt retains an empty packet object for backwards-compatible
    # validation. Packet binding belongs exclusively to the AgentOps runner.
    packet_block = {
        "id": "", "digest": "", "track": "", "owner": "",
        "allowed_files": [], "forbidden_files": [],
    }
    return {
        "repository": repo_identity(repository_observation),
        "contract": contract_sources(),
        "packet": packet_block,
        "portfolio": portfolio_snapshot(),
        "orientation": orientation_static(),
        "required_reading": list(REQUIRED_READING),
    }


__all__ = [
    "CONTRACT_SOURCES",
    "REPO_ROOT",
    "REQUIRED_READING",
    "collect_stable_core",
    "contract_sources",
    "observe_repo_live_state",
    "orientation_static",
    "portfolio_snapshot",
    "projection_freshness",
    "repo_identity",
    "repo_live_state",
    "toolchain_versions",
]
