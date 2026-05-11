"""UI surface commands (TUI, chat, dashboard)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys


from dharma_swarm.terminal_commands._helpers import (
    DHARMA_STATE,
    DHARMA_SWARM,
    HOME,
)

def cmd_tui() -> None:
    """Launch the interactive TUI dashboard."""
    use_legacy = os.getenv("DGC_USE_LEGACY_TUI", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not use_legacy:
        terminal_dir = DHARMA_SWARM / "terminal"
        if terminal_dir.exists() and (terminal_dir / "package.json").exists():
            bun_path = shutil.which("bun")
            if bun_path:
                try:
                    env = dict(os.environ)
                    native_auth = subprocess.run(
                        ["/bin/zsh", "-lc", "env -u ANTHROPIC_API_KEY claude auth status"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if native_auth.returncode == 0:
                        try:
                            payload = json.loads(native_auth.stdout or "{}")
                        except json.JSONDecodeError:
                            payload = {}
                        if isinstance(payload, dict) and str(payload.get("subscriptionType", "")).strip().lower() == "max":
                            env["DHARMA_CLAUDE_AUTH_MODE"] = "subscription"
                    subprocess.run(
                        [bun_path, "run", "start"],
                        cwd=str(terminal_dir),
                        env=env,
                        check=True,
                    )
                    return
                except subprocess.CalledProcessError:
                    pass
    try:
        from dharma_swarm.tui import run
        run()
    except Exception:
        # Fallback to legacy TUI
        from dharma_swarm.tui_legacy import run_tui
        run_tui()


def _build_chat_context_snapshot() -> str:
    """Build a compact DGC context snapshot for Claude chat sessions."""
    from dharma_swarm.prompt_builder import build_state_context_snapshot

    return build_state_context_snapshot(
        state_dir=DHARMA_STATE,
        home=HOME,
        max_chars=6000,
    )


def cmd_chat(
    continue_last: bool = False,
    offline: bool = False,
    model: str | None = None,
    effort: str | None = None,
    include_context: bool = True,
) -> None:
    """Launch native Claude Code interactive UI (full experience)."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", None)
    if offline:
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

    cmd = ["claude"]
    if continue_last:
        cmd.append("--continue")
    if model:
        cmd.extend(["--model", model])
    if effort:
        cmd.extend(["--effort", effort])

    if include_context:
        snapshot = _build_chat_context_snapshot()
        if snapshot:
            cmd.extend(
                [
                    "--append-system-prompt",
                    "DGC mission-control context snapshot. Treat as hints and verify.\n\n"
                    + snapshot,
                ]
            )

    try:
        os.execvpe("claude", cmd, env)
    except FileNotFoundError:
        print("claude CLI not found. Install Claude Code first.")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to launch Claude Code: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Sprint generator
# ---------------------------------------------------------------------------
