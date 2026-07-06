"""External notary anchoring for the Merkle root (\u00a7U5) \u2014 core (pure).

The core exports:
  * `AnchorReceipt` \u2014 frozen dataclass carrying (root_hash, anchor_ref,
    anchored_at, scheme).
  * `NotaryAnchor` \u2014 abstract base with a single `anchor(root_hash)` method.
  * `LocalFileAnchor` \u2014 base class with pure `_build_receipt` logic and an
    abstract `_git_head_result()` seam. The actual filesystem-append plus
    the subprocess git-HEAD binding live in
    `telos_kernel._io.notary_fs.GitBoundLocalFileAnchor`.

Phase 1+ can drop in:
  * `Rfc3161TimestampAnchor` \u2014 RFC 3161 timestamping via a public TSA.
  * `OpenTimestampsAnchor` \u2014 Bitcoin-anchored via OpenTimestamps.

References:
  * RFC 3161: https://datatracker.ietf.org/doc/html/rfc3161
  * OpenTimestamps: https://opentimestamps.org/
  * Certificate Transparency (design precedent): RFC 9162.
"""
from __future__ import annotations

import abc
import datetime as _dt
from dataclasses import dataclass

from telos_kernel.effects import Effect, effect
from telos_kernel.result import ERR_GIT_UNAVAILABLE, Err, KernelError, Ok, Result


@dataclass(frozen=True)
class AnchorReceipt:
    root_hash: str
    anchor_ref: str      # e.g. "git:4c4f5aa4" or "rfc3161:<tsr-hex>"
    anchored_at: str     # ISO 8601 UTC
    scheme: str          # "local-file+git" | "rfc3161" | "opentimestamps"


class NotaryAnchor(abc.ABC):
    @abc.abstractmethod
    def anchor(self, root_hash: str) -> AnchorReceipt:
        raise NotImplementedError


@effect(Effect.NONDETERMINISTIC)
def _now_iso_utc() -> str:
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class LocalFileAnchor(NotaryAnchor):
    """Append-only anchor bound to a git HEAD.

    The core class is pure by default: `_git_head_result()` returns
    `Err(ERR_GIT_UNAVAILABLE)` unconditionally. The rim subclass
    `telos_kernel._io.notary_fs.GitBoundLocalFileAnchor` overrides it
    to actually invoke `git rev-parse HEAD`.

    Similarly, `anchor()` here builds an in-memory receipt only. The rim
    subclass extends it to append to the on-disk log.
    """

    def __init__(self, path=None, git_repo=None):
        # `path` and `git_repo` are stored but not touched from core.
        # The rim subclass uses them.
        self.path = path
        self.git_repo = git_repo

    def _git_head_result(self) -> Result:
        return Err(KernelError(
            ERR_GIT_UNAVAILABLE,
            "core LocalFileAnchor cannot invoke git; use GitBoundLocalFileAnchor "
            "from telos_kernel._io.notary_fs instead",
        ))

    @effect(Effect.NONDETERMINISTIC)
    def _build_receipt(self, root_hash: str) -> AnchorReceipt:
        head_r = self._git_head_result()
        head = head_r.unwrap() if head_r.is_ok else "no-git"
        return AnchorReceipt(
            root_hash=root_hash,
            anchor_ref=f"git:{head}",
            anchored_at=_now_iso_utc(),
            scheme="local-file+git",
        )

    @effect(Effect.NONDETERMINISTIC)
    def anchor(self, root_hash: str) -> AnchorReceipt:
        """Pure receipt-construction. Persistence lives in the rim subclass."""
        return self._build_receipt(root_hash)
