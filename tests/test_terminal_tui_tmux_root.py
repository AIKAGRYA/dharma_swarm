"""Worktree-portability contracts for the terminal bootstrap surfaces."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from dharma_swarm.terminal_bridge_text import render_system_prompt


REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "scripts" / "start_terminal_tui_tmux.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_launcher(
    tmp_path: Path,
    *,
    root_override: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[list[str]], dict[str, object]]:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    tmux_log = tmp_path / "tmux.jsonl"
    bun_log = tmp_path / "bun.json"
    _write_executable(
        fake_bin / "tmux",
        f"""#!{sys.executable}
import json
import os
import subprocess
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_TMUX_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")
if args[:1] == ["has-session"]:
    raise SystemExit(1)
if args[:1] == ["new-session"]:
    command = subprocess.run(["bash", "-c", args[-1]], env=os.environ.copy())
    raise SystemExit(command.returncode)
""",
    )
    _write_executable(
        fake_bin / "bun",
        f"""#!{sys.executable}
import json
import os
import sys

with open(os.environ["FAKE_BUN_LOG"], "w", encoding="utf-8") as handle:
    json.dump(
        {{
            "argv": sys.argv[1:],
            "cwd": os.getcwd(),
            "python": os.environ.get("DHARMA_PYTHON"),
        }},
        handle,
    )
""",
    )

    state_dir = tmp_path / "terminal state"
    env = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "SESSION_NAME": "portability-test",
        "DHARMA_TERMINAL_TUI_STATE_DIR": str(state_dir),
        "DHARMA_PYTHON": sys.executable,
        "FAKE_TMUX_LOG": str(tmux_log),
        "FAKE_BUN_LOG": str(bun_log),
    }
    if root_override is not None:
        env["DHARMA_TERMINAL_ROOT"] = str(root_override)
    else:
        env.pop("DHARMA_TERMINAL_ROOT", None)

    result = subprocess.run(
        ["bash", str(LAUNCHER)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    tmux_calls = [json.loads(line) for line in tmux_log.read_text().splitlines()]
    bun_call = json.loads(bun_log.read_text()) if bun_log.exists() else {}
    return result, tmux_calls, bun_call


def test_bridge_prompt_default_root_tracks_imported_checkout() -> None:
    rendered = render_system_prompt(prompt="verify checkout portability")

    assert f"- Repo root: {REPO_ROOT}" in rendered


def test_tmux_launcher_resolves_root_from_its_own_checkout(tmp_path: Path) -> None:
    result, tmux_calls, bun_call = _run_launcher(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert bun_call == {
        "argv": ["run", "src/index.tsx"],
        "cwd": str(REPO_ROOT / "terminal"),
        "python": sys.executable,
    }
    assert [call[0] for call in tmux_calls] == [
        "has-session",
        "new-session",
        "pipe-pane",
    ]
    assert f"Terminal dir: {REPO_ROOT / 'terminal'}" in result.stdout


def test_tmux_launcher_respects_root_override_with_spaces(tmp_path: Path) -> None:
    root_override = tmp_path / "alternate checkout with spaces"
    (root_override / "terminal").mkdir(parents=True)

    result, _, bun_call = _run_launcher(tmp_path, root_override=root_override)

    assert result.returncode == 0, result.stdout + result.stderr
    assert bun_call["cwd"] == str(root_override / "terminal")
