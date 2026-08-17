"""Typed repository-authority observation from raw local Git config.

The configured origin is read with ``git config --local``.  In particular,
this module does not use ``git remote get-url``: that command applies ambient
``url.*.insteadOf`` rewrites and can make a legacy local configuration appear
canonical.  Classification is read-only and carries the source observation as
typed provenance; readiness policy remains in :mod:`cli`.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from urllib.parse import unquote, urlsplit


CANONICAL_IDENTITY = "AIKAGRYA/dharma_swarm"
CANONICAL_ORIGIN_URL = "https://github.com/AIKAGRYA/dharma_swarm.git"
LEGACY_IDENTITY = "AmitabhainArunachala/dharma_swarm"
LEGACY_CUTOFF_UTC = "2026-08-15T15:00:00Z"
LEGACY_CUTOFF = datetime(2026, 8, 15, 15, 0, 0, tzinfo=timezone.utc)
EXPLICITLY_BLOCKED_IDENTITIES = frozenset({"shakti-saraswati/dharma_swarm"})
LOCAL_ORIGIN_KEY = "remote.origin.url"
LOCAL_CONFIG_COMMAND = (
    "git", "config", "--local", "--null", "--get-all", LOCAL_ORIGIN_KEY,
)

_SCP_REMOTE_RE = re.compile(
    r"^(?:(?P<user>[^/@:]+)@)?(?P<host>[^/:]+):(?P<path>.+)$"
)
_WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


class RepositoryIdentityStatus(str, Enum):
    """Exhaustive classification of the configured repository target."""

    CANONICAL = "canonical"
    LEGACY_COMPATIBLE = "legacy_compatible"
    LEGACY_EXPIRED = "legacy_expired"
    STERILE = "sterile"
    WRONG_TARGET = "wrong_target"
    AMBIGUOUS = "ambiguous"
    NOT_OBSERVED = "not_observed"


class RepositoryIdentitySource(str, Enum):
    """Where the target claim came from (or why it was unavailable)."""

    RAW_LOCAL_GIT_CONFIG = "raw_local_git_config"
    RAW_LOCAL_GIT_CONFIG_ABSENT = "raw_local_git_config_absent"
    RAW_LOCAL_GIT_CONFIG_ERROR = "raw_local_git_config_error"


@dataclass(frozen=True)
class RepositoryIdentityProvenance:
    """Lossless provenance for one local-config observation."""

    source: RepositoryIdentitySource
    key: str = LOCAL_ORIGIN_KEY
    command: tuple[str, ...] = LOCAL_CONFIG_COMMAND
    raw_values: tuple[str, ...] = field(default=(), repr=False)
    error: str = ""


@dataclass(frozen=True)
class RepositoryIdentityObservation:
    """One cutoff-aware, typed repository identity observation."""

    status: RepositoryIdentityStatus
    identity: str
    origin_url: str
    provenance: RepositoryIdentityProvenance
    reason: str

    @property
    def blocks(self) -> bool:
        return self.status in {
            RepositoryIdentityStatus.LEGACY_EXPIRED,
            RepositoryIdentityStatus.WRONG_TARGET,
            RepositoryIdentityStatus.AMBIGUOUS,
            RepositoryIdentityStatus.NOT_OBSERVED,
        }


def _utc_time(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
        except ValueError as exc:
            raise ValueError("now must be a valid ISO-8601 timestamp") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return value.astimezone(timezone.utc)


def _read_raw_local_origin(
    repo_root: Path,
) -> tuple[tuple[str, ...], RepositoryIdentityProvenance]:
    """Read literal local values without applying global URL rewrites."""
    try:
        proc = subprocess.run(
            list(LOCAL_CONFIG_COMMAND),
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        provenance = RepositoryIdentityProvenance(
            source=RepositoryIdentitySource.RAW_LOCAL_GIT_CONFIG_ERROR,
            error="timeout after 30s while reading raw local Git config",
        )
        return (), provenance
    except OSError as exc:
        provenance = RepositoryIdentityProvenance(
            source=RepositoryIdentitySource.RAW_LOCAL_GIT_CONFIG_ERROR,
            error=f"{type(exc).__name__} while reading raw local Git config",
        )
        return (), provenance

    # ``git config --get-all`` uses exit 1 for an absent key.  That is a
    # sterile clone, distinct from a command/config failure.
    if proc.returncode == 1:
        provenance = RepositoryIdentityProvenance(
            source=RepositoryIdentitySource.RAW_LOCAL_GIT_CONFIG_ABSENT,
        )
        return (), provenance
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        suffix = f": {detail[0][:120]}" if detail else ""
        provenance = RepositoryIdentityProvenance(
            source=RepositoryIdentitySource.RAW_LOCAL_GIT_CONFIG_ERROR,
            error=f"git config exited {proc.returncode}{suffix}",
        )
        return (), provenance

    values = tuple(value for value in proc.stdout.split("\0") if value)
    provenance = RepositoryIdentityProvenance(
        source=(
            RepositoryIdentitySource.RAW_LOCAL_GIT_CONFIG
            if values
            else RepositoryIdentitySource.RAW_LOCAL_GIT_CONFIG_ABSENT
        ),
        raw_values=values,
    )
    return values, provenance


def _looks_like_local_path(value: str) -> bool:
    if value.casefold().startswith("file://"):
        return True
    if value.startswith(("/", "./", "../", "~/", "\\\\")):
        return True
    if _WINDOWS_PATH_RE.match(value):
        return True
    # A remote without a URI scheme or scp-style host separator is a path as
    # far as Git is concerned (for example ``../source.git`` or ``source``).
    return "://" not in value and _SCP_REMOTE_RE.match(value) is None


def _github_identity(value: str) -> str:
    """Return owner/repository for a literal github.com remote, else empty."""
    host = ""
    path = ""
    if "://" in value:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").casefold().rstrip(".")
        path = unquote(parsed.path)
    else:
        match = _SCP_REMOTE_RE.match(value)
        if match is not None:
            host = match.group("host").casefold().rstrip(".")
            path = match.group("path")
    if host != "github.com":
        return ""
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) != 2:
        return ""
    repository = parts[1].removesuffix(".git")
    if not parts[0] or not repository:
        return ""
    return f"{parts[0]}/{repository}"


def _same_identity(left: str, right: str) -> bool:
    # GitHub owner/repository identity is case-insensitive, while the emitted
    # authority value is always the canonical spelling from governance.
    return left.casefold() == right.casefold()


def observe_repository_identity(
    repo_root: Path,
    *,
    now: datetime | str | None = None,
) -> RepositoryIdentityObservation:
    """Classify the literal local origin under the repository cutover rule."""
    observed_at = _utc_time(now)
    values, provenance = _read_raw_local_origin(Path(repo_root))
    if provenance.source is RepositoryIdentitySource.RAW_LOCAL_GIT_CONFIG_ERROR:
        return RepositoryIdentityObservation(
            status=RepositoryIdentityStatus.NOT_OBSERVED,
            identity="",
            origin_url="",
            provenance=provenance,
            reason=provenance.error or "raw local Git config was not observed",
        )
    if not values:
        return RepositoryIdentityObservation(
            status=RepositoryIdentityStatus.STERILE,
            identity="",
            origin_url="",
            provenance=provenance,
            reason=(
                "remote.origin.url is absent from raw local Git config; "
                "sterile clone remains nonblocking"
            ),
        )
    if len(values) != 1:
        return RepositoryIdentityObservation(
            status=RepositoryIdentityStatus.AMBIGUOUS,
            identity="",
            origin_url="",
            provenance=provenance,
            reason=(
                f"raw local Git config has {len(values)} origin URLs; "
                "repository authority is ambiguous"
            ),
        )

    origin_url = values[0].strip()
    if not origin_url or _looks_like_local_path(origin_url):
        return RepositoryIdentityObservation(
            status=RepositoryIdentityStatus.STERILE,
            identity="",
            origin_url=origin_url,
            provenance=provenance,
            reason="local-path origin is sterile and nonblocking",
        )

    identity = _github_identity(origin_url)
    if _same_identity(identity, CANONICAL_IDENTITY):
        return RepositoryIdentityObservation(
            status=RepositoryIdentityStatus.CANONICAL,
            identity=CANONICAL_IDENTITY,
            origin_url=origin_url,
            provenance=provenance,
            reason=(
                f"canonical {CANONICAL_IDENTITY} observed in raw local Git config"
            ),
        )
    if _same_identity(identity, LEGACY_IDENTITY):
        if observed_at < LEGACY_CUTOFF:
            return RepositoryIdentityObservation(
                status=RepositoryIdentityStatus.LEGACY_COMPATIBLE,
                identity=LEGACY_IDENTITY,
                origin_url=origin_url,
                provenance=provenance,
                reason=(
                    f"legacy {LEGACY_IDENTITY} is nonblocking only before "
                    f"{LEGACY_CUTOFF_UTC}; update origin to {CANONICAL_ORIGIN_URL}"
                ),
            )
        return RepositoryIdentityObservation(
            status=RepositoryIdentityStatus.LEGACY_EXPIRED,
            identity=LEGACY_IDENTITY,
            origin_url=origin_url,
            provenance=provenance,
            reason=(
                f"legacy {LEGACY_IDENTITY} expired at {LEGACY_CUTOFF_UTC}; "
                f"update origin to {CANONICAL_ORIGIN_URL}"
            ),
        )

    display_identity = identity or "non-canonical remote"
    return RepositoryIdentityObservation(
        status=RepositoryIdentityStatus.WRONG_TARGET,
        identity=identity,
        origin_url=origin_url,
        provenance=provenance,
        reason=(
            f"origin targets {display_identity}; expected {CANONICAL_IDENTITY}"
        ),
    )


__all__ = [
    "CANONICAL_IDENTITY",
    "CANONICAL_ORIGIN_URL",
    "EXPLICITLY_BLOCKED_IDENTITIES",
    "LEGACY_CUTOFF",
    "LEGACY_CUTOFF_UTC",
    "LEGACY_IDENTITY",
    "LOCAL_CONFIG_COMMAND",
    "LOCAL_ORIGIN_KEY",
    "RepositoryIdentityObservation",
    "RepositoryIdentityProvenance",
    "RepositoryIdentitySource",
    "RepositoryIdentityStatus",
    "observe_repository_identity",
]
