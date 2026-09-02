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
    root_override_ok: bool = True,
    bridge_live: bool = True,
    preexisting_session: bool = False,
) -> tuple[subprocess.CompletedProcess[str], list[list[str]], dict[str, object]]:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    tmux_log = tmp_path / "tmux.jsonl"
    bun_log = tmp_path / "bun.json"
    tmux_state = tmp_path / "tmux-live"
    _write_executable(
        fake_bin / "tmux",
        f"""#!{sys.executable}
import json
import os
import subprocess
import sys

args = sys.argv[1:]
expected_prefix = ["-L", "CODEX_MANAGED_helm_tui", "-f", "/dev/null"]
if args[:4] != expected_prefix:
    raise SystemExit(f"unexpected tmux server boundary: {{args[:4]!r}}")
if os.environ.get("TMUX_TMPDIR") != "/tmp":
    raise SystemExit(f"unexpected TMUX_TMPDIR: {{os.environ.get('TMUX_TMPDIR')!r}}")
command_args = args[4:]
with open(os.environ["FAKE_TMUX_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(command_args) + "\\n")
if command_args[:1] == ["has-session"]:
    raise SystemExit(0 if os.path.exists(os.environ["FAKE_TMUX_STATE"]) else 1)
if command_args[:1] == ["new-session"]:
    command = subprocess.run(["bash", "-c", command_args[-1]], env=os.environ.copy())
    if command.returncode == 0:
        open(os.environ["FAKE_TMUX_STATE"], "w", encoding="utf-8").close()
    raise SystemExit(command.returncode)
if command_args[:1] == ["display-message"]:
    print(f"0|{{os.environ['FAKE_PANE_PID']}}|bun")
    raise SystemExit(0)
if command_args[:1] == ["kill-session"]:
    try:
        os.unlink(os.environ["FAKE_TMUX_STATE"])
    except FileNotFoundError:
        pass
    raise SystemExit(0)
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
            "state_dir": os.environ.get("DHARMA_TERMINAL_TUI_STATE_DIR"),
        }},
        handle,
    )
""",
    )
    _write_executable(
        fake_bin / "pgrep",
        f"""#!{sys.executable}
import os
import sys

# BSD pgrep excludes ancestors of itself, so the real binary can never report
# the launcher shell as a child of the fake pane pid. Model the process tree
# instead: the fake pane has exactly one child (itself) while the bridge is
# live, and no children otherwise.
args = sys.argv[1:]
if args[:1] == ["-P"] and args[1:2] == [os.environ["FAKE_PANE_PID"]]:
    if os.environ.get("FAKE_BRIDGE_LIVE") == "1":
        print(os.environ["FAKE_PANE_PID"])
        raise SystemExit(0)
raise SystemExit(1)
""",
    )
    _write_executable(
        fake_bin / "ps",
        f"""#!{sys.executable}
import os

# Model a live bridge child beneath the launcher shell.  The shell is a real
# process, so the launcher's independent kill -0 probes remain meaningful.
pane_pid = os.environ["FAKE_PANE_PID"]
if os.environ.get("FAKE_BRIDGE_LIVE") == "1":
    print(f"{{pane_pid}} {{pane_pid}} {sys.executable} -m dharma_swarm.terminal_bridge stdio")
""",
    )

    if preexisting_session:
        tmux_state.touch()

    state_dir = tmp_path / "terminal state"
    env = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "SESSION_NAME": "portability-test",
        "DHARMA_TERMINAL_TUI_STATE_DIR": str(state_dir),
        "DHARMA_PYTHON": sys.executable,
        "FAKE_TMUX_LOG": str(tmux_log),
        "FAKE_TMUX_STATE": str(tmux_state),
        "FAKE_PANE_PID": str(os.getpid()),
        "FAKE_BUN_LOG": str(bun_log),
        "FAKE_BRIDGE_LIVE": "1" if bridge_live else "0",
        "TERMINAL_TUI_LIVENESS_TIMEOUT_SECONDS": "1",
    }
    env.pop("DHARMA_TERMINAL_TMUX_TMPDIR", None)
    env.pop("DHARMA_TERMINAL_ROOT_OVERRIDE_OK", None)
    if root_override is not None:
        env["DHARMA_TERMINAL_ROOT"] = str(root_override)
        if root_override_ok:
            env["DHARMA_TERMINAL_ROOT_OVERRIDE_OK"] = "1"
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
    tmux_calls = (
        [json.loads(line) for line in tmux_log.read_text().splitlines()]
        if tmux_log.exists()
        else []
    )
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
        "state_dir": str(tmp_path / "terminal state"),
    }
    assert [call[0] for call in tmux_calls] == [
        "has-session",
        "new-session",
        "pipe-pane",
        "has-session",
        "display-message",
    ]
    assert "bridge_process=live" in result.stdout
    assert f"Terminal dir: {REPO_ROOT / 'terminal'}" in result.stdout


def test_tmux_launcher_respects_root_override_with_spaces(tmp_path: Path) -> None:
    root_override = tmp_path / "alternate checkout with spaces"
    (root_override / "terminal").mkdir(parents=True)

    result, _, bun_call = _run_launcher(tmp_path, root_override=root_override)

    assert result.returncode == 0, result.stdout + result.stderr
    assert bun_call["cwd"] == str(root_override / "terminal")


def test_tmux_launcher_refuses_root_override_without_consent(tmp_path: Path) -> None:
    root_override = tmp_path / "alternate checkout"
    (root_override / "terminal").mkdir(parents=True)

    result, tmux_calls, bun_call = _run_launcher(tmp_path, root_override=root_override, root_override_ok=False)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "another tree's cockpit" in result.stderr
    assert tmux_calls == []
    assert bun_call == {}


def test_tmux_launcher_removes_only_a_new_unhealthy_session(tmp_path: Path) -> None:
    result, tmux_calls, _ = _run_launcher(tmp_path, bridge_live=False)

    assert result.returncode == 1
    assert not (tmp_path / "tmux-live").exists()
    assert tmux_calls[-1] == ["kill-session", "-t", "=portability-test"]
    assert "created by this launcher invocation" in result.stderr


def test_tmux_launcher_preserves_an_existing_unhealthy_session(tmp_path: Path) -> None:
    result, tmux_calls, _ = _run_launcher(
        tmp_path,
        bridge_live=False,
        preexisting_session=True,
    )

    assert result.returncode == 1
    assert (tmp_path / "tmux-live").exists()
    assert all(call[0] != "kill-session" for call in tmux_calls)
    assert "was left unchanged" in result.stderr
