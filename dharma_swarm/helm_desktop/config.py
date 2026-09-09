"""Validated local paths and the one private desktop seat."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

SOCKET = "CODEX_MANAGED_helm_desktop"
SESSION = "helm_desktop"
NAME_RE = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")


class DesktopError(ValueError):
    """A bounded operation cannot be performed safely or completely."""


def local_path(value: str | Path, *, directory: bool = False) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute() or ".." in path.parts or any(c in str(path) for c in "\0\r\n"):
        raise DesktopError("paths must be absolute and contain no traversal or control characters")
    if path.is_symlink():
        raise DesktopError(f"symlink paths are not accepted: {path}")
    path = path.resolve()
    if directory and not path.is_dir():
        raise DesktopError(f"directory does not exist: {path}")
    return path


@dataclass(frozen=True)
class DesktopConfig:
    repo_root: Path
    state_dir: Path
    profile: str = "research"
    socket: str = SOCKET
    session: str = SESSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "repo_root", local_path(self.repo_root, directory=True))
        object.__setattr__(self, "state_dir", local_path(self.state_dir))
        if self.state_dir in {Path("/"), Path.home().resolve()}:
            raise DesktopError("state-dir must be a dedicated directory, not the filesystem or home root")
        if not re.fullmatch(r"CODEX_MANAGED_[A-Za-z0-9][A-Za-z0-9_-]{0,48}", self.socket):
            raise DesktopError("socket must be a short CODEX_MANAGED_<name> label")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", self.session):
            raise DesktopError("session must be a simple exact name")
        if not (self.repo_root / "scripts/start_terminal_tui_tmux.sh").is_file():
            raise DesktopError("repo-root must contain the existing Helm terminal launcher")
        if self.state_dir == self.repo_root or self.repo_root in self.state_dir.parents:
            raise DesktopError("desktop state must live outside the source checkout")

    @property
    def status_path(self) -> Path:
        return self.state_dir / "status.json"

    def environment(self) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("TMUX", None)
        env.update({
            "TMUX_TMPDIR": "/tmp",
            "DHARMA_TERMINAL_ROOT": str(self.repo_root),
            "DHARMA_TERMINAL_TUI_STATE_DIR": str(self.state_dir / "terminal"),
            "DHARMA_TERMINAL_TMUX_SOCKET": self.socket,
            "DHARMA_TERMINAL_TMUX_SESSION": self.session,
            "DHARMA_TERMINAL_TMUX_TMPDIR": "/tmp",
            "DHARMA_HELM_DESKTOP_STATUS_FILE": str(self.status_path),
            "DHARMA_HELM_DESKTOP_TMUX_SOCKET": self.socket,
            "DHARMA_HELM_DESKTOP_TMUX_SESSION": self.session,
        })
        return env

    def seat(self) -> dict[str, str]:
        return {"tmux_socket": self.socket, "tmux_session": self.session}
