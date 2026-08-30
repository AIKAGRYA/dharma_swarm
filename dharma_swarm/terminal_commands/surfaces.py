"""UI surface commands (TUI, chat, dashboard)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from dharma_swarm.models import ProviderType
from dharma_swarm.provider_policy import (
    ProviderPolicyRouter,
    ProviderRouteRequest,
    ProviderRoutingConfig,
)
from dharma_swarm.runtime_provider import (
    RuntimeProviderConfig,
    resolve_runtime_provider_config,
)
from dharma_swarm.terminal_commands._helpers import (
    DHARMA_STATE,
    DHARMA_SWARM,
    HOME,
)


_CHAT_CHILD_ENV_DENYLIST = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDECODE",
        "CLAUDE_CODE_ENTRYPOINT",
        "CLAUDE_CODE_INCLUDE_PARTIAL_MESSAGES",
    }
)


def cmd_tui() -> None:
    """Launch the interactive TUI dashboard."""
    try:
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
    except KeyboardInterrupt:
        print("\nDGC dashboard stopped.")


def _build_chat_context_snapshot() -> str:
    """Build a compact DGC context snapshot for Claude chat sessions."""
    from dharma_swarm.prompt_builder import build_state_context_snapshot

    return build_state_context_snapshot(
        state_dir=DHARMA_STATE,
        home=HOME,
        max_chars=6000,
    )


def _resolve_chat_runtime(
    *,
    env: dict[str, str],
    model: str | None,
) -> RuntimeProviderConfig:
    """Resolve and policy-authorize the native interactive Claude runtime."""
    runtime = resolve_runtime_provider_config(
        ProviderType.CLAUDE_CODE,
        model=model,
        working_dir=os.getcwd(),
        env=env,
    )
    if runtime.provider != ProviderType.CLAUDE_CODE:
        raise RuntimeError(
            "dgc chat runtime provider mismatch: "
            f"expected {ProviderType.CLAUDE_CODE.value}, got {runtime.provider.value}"
        )
    if not runtime.available or not runtime.binary_path:
        raise FileNotFoundError("claude")

    route_context: dict[str, object] = {
        "preferred_provider": ProviderType.CLAUDE_CODE.value,
        "requires_tooling": True,
        "operator_invoked": True,
    }
    if model:
        route_context["preferred_model"] = model

    decision = ProviderPolicyRouter(
        config=ProviderRoutingConfig(default_model_hints={})
    ).route(
        ProviderRouteRequest(
            action_name="dgc.chat.interactive",
            risk_score=0.10,
            uncertainty=0.05,
            novelty=0.05,
            urgency=0.50,
            expected_impact=0.30,
            context=route_context,
        ),
        available_providers=[ProviderType.CLAUDE_CODE],
    )
    if decision.selected_provider != ProviderType.CLAUDE_CODE:
        raise RuntimeError(
            "dgc chat policy provider mismatch: "
            f"expected {ProviderType.CLAUDE_CODE.value}, "
            f"got {decision.selected_provider.value}"
        )
    if decision.selected_model_hint != model:
        raise RuntimeError(
            "dgc chat policy model mismatch: "
            f"requested {model or 'native_cli_default'}, "
            f"selected {decision.selected_model_hint or 'native_cli_default'}"
        )
    return runtime


def _normalize_chat_executable(binary_path: str) -> str:
    """Return a canonical absolute path for the native ``execve`` handoff.

    Runtime discovery is allowed to follow the operator's configured PATH, but
    the process-replacement boundary must not perform a second PATH lookup.
    Requiring an absolute provider result and resolving aliases here gives
    ``execve`` one concrete executable identity.
    """
    expanded = os.path.expanduser(binary_path)
    if not os.path.isabs(expanded):
        raise ValueError(
            "dgc chat runtime executable must be an absolute provider-resolved path"
        )
    if "\x00" in expanded:
        raise ValueError("dgc chat runtime executable contains a null byte")

    executable = os.path.realpath(expanded)
    if not os.path.isabs(executable):  # defensive invariant across platforms
        raise ValueError("dgc chat runtime executable did not normalize absolutely")
    return executable


def cmd_chat(
    continue_last: bool = False,
    offline: bool = False,
    model: str | None = None,
    effort: str | None = None,
    include_context: bool = True,
) -> None:
    """Launch native Claude Code interactive UI (full experience)."""
    env = os.environ.copy()
    for key in _CHAT_CHILD_ENV_DENYLIST:
        env.pop(key, None)
    env.pop("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", None)
    if offline:
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

    try:
        runtime = _resolve_chat_runtime(env=env, model=model)
        assert runtime.binary_path is not None  # narrowed by _resolve_chat_runtime
        executable = _normalize_chat_executable(runtime.binary_path)
    except FileNotFoundError:
        print("claude CLI not found. Install Claude Code first.")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to launch Claude Code: {e}")
        sys.exit(1)

    command = [executable]
    if continue_last:
        command.append("--continue")
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["--effort", effort])

    if include_context:
        snapshot = _build_chat_context_snapshot()
        if snapshot:
            command.extend(
                [
                    "--append-system-prompt",
                    "DGC mission-control context snapshot. Treat as hints and verify.\n\n"
                    + snapshot,
                ]
            )

    try:
        # The executable is absolute/realpath-normalized above; argv is an
        # array and execve never invokes a shell or performs a PATH lookup.
        os.execve(executable, command, env)  # nosemgrep: python.lang.security.audit.dangerous-os-exec-tainted-env-args.dangerous-os-exec-tainted-env-args
    except FileNotFoundError:
        print("claude CLI not found. Install Claude Code first.")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to launch Claude Code: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Sprint generator
# ---------------------------------------------------------------------------
