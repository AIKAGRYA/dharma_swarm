"""External notary anchoring for the Merkle root (§U5).

Phase 0 ships:
  * `LocalFileAnchor` — append-only file bound to `git rev-parse HEAD`.

Phase 1+ can drop in:
  * `Rfc3161TimestampAnchor` — RFC 3161 timestamping via a public TSA.
  * `OpenTimestampsAnchor` — Bitcoin-anchored via OpenTimestamps.

References:
  * RFC 3161: https://datatracker.ietf.org/doc/html/rfc3161
  * OpenTimestamps: https://opentimestamps.org/
  * Certificate Transparency (design precedent): RFC 9162.
"""
from __future__ import annotations

import abc
import datetime as _dt
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


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


class LocalFileAnchor(NotaryAnchor):
    """Append-only file anchor that binds each root to the current git HEAD.

    This is intentionally weak — it defends against replay against an
    honest observer, not against an attacker who controls the local disk.
    Phase 1+ swaps in a real timestamping authority.
    """

    def __init__(self, path: str | Path = "~/.dharma/merkle_anchors.jsonl",
                 git_repo: str | Path | None = None):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.git_repo = Path(git_repo).expanduser() if git_repo else None

    def _git_head(self) -> str:
        try:
            cmd = ["git", "rev-parse", "HEAD"]
            cwd = str(self.git_repo) if self.git_repo else None
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5, check=False, cwd=cwd
            )
            if out.returncode == 0:
                return out.stdout.strip()
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
        return "no-git"

    def anchor(self, root_hash: str) -> AnchorReceipt:
        now = (
            _dt.datetime.now(_dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        head = self._git_head()
        receipt = AnchorReceipt(
            root_hash=root_hash,
            anchor_ref=f"git:{head}",
            anchored_at=now,
            scheme="local-file+git",
        )
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(receipt.__dict__, sort_keys=True) + "\n")
        return receipt
