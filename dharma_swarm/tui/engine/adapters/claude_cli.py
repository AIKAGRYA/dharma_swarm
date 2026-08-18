"""Pure Claude CLI request serialization for the canonical adapter."""

from __future__ import annotations

import json
import os

from dharma_swarm.api_keys import ALL_API_KEY_ENV_KEYS, PROVIDER_BASE_URL_ENV_KEYS

from .base import CompletionRequest

_UNRELATED_PROVIDER_TOKEN_KEYS = frozenset(
    {
        "CLAUDE_CODE_OAUTH_TOKEN",
        "KIMI_ACCESS_TOKEN",
        "MOONSHOT_AUTH_TOKEN",
        "OPENROUTER_AUTH_TOKEN",
        "XAI_API_KEY",
    }
)
_SUBSCRIPTION_CHILD_ENV_ALLOWLIST = frozenset(
    {
        "CLAUDE_CONFIG_DIR",
        "COLORTERM",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LOGNAME",
        "NO_COLOR",
        "PATH",
        "SHELL",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "TERM",
        "TMPDIR",
        "USER",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    }
)


def _without_nul(value: str) -> str:
    """Remove bytes that cannot cross the subprocess argv boundary."""

    return value.replace("\x00", "")


def build_claude_env(request: CompletionRequest) -> dict[str, str]:
    """Build a child environment without leaking nested or metered auth."""

    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    env.pop("CLAUDE_CODE_INCLUDE_PARTIAL_MESSAGES", None)
    if request.provider_options.get("subscription_auth_only"):
        scrubbed = (
            set(ALL_API_KEY_ENV_KEYS)
            | set(PROVIDER_BASE_URL_ENV_KEYS.values())
            | set(_UNRELATED_PROVIDER_TOKEN_KEYS)
            | {"ANTHROPIC_AUTH_TOKEN", "DHARMA_FORCE_ANTHROPIC_API"}
        )
        for key in scrubbed:
            env.pop(key, None)
        env = {
            key: value
            for key, value in env.items()
            if key in _SUBSCRIPTION_CHILD_ENV_ALLOWLIST
        }
    elif (
        request.provider_options.get("scrub_metered_keys")
        and env.get("DHARMA_FORCE_ANTHROPIC_API") != "1"
    ):
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
    internet_enabled = bool(request.provider_options.get("internet_enabled", True))
    if internet_enabled:
        env.pop("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", None)
    else:
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    return env


def build_claude_command(
    cli_path: str,
    request: CompletionRequest,
    *,
    default_model: str | None,
    prompt: str,
) -> list[str]:
    """Serialize one request into a permission-safe Claude CLI command."""

    cmd = [
        cli_path,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
    ]

    if request.resume_session_id:
        cmd.extend(["--resume", request.resume_session_id])
    elif request.provider_options.get("continue_last"):
        cmd.append("--continue")

    model = request.model or default_model
    if model:
        cmd.extend(["--model", model])

    # A missing authority grant must preserve Claude's permission checks.
    permission_mode = str(request.provider_options.get("permission_mode", "default"))
    if permission_mode:
        cmd.extend(["--permission-mode", permission_mode])
        if permission_mode == "bypassPermissions":
            cmd.extend(["--allowedTools", "*", "--dangerously-skip-permissions"])

    max_turns = request.provider_options.get("max_turns")
    if isinstance(max_turns, int) and max_turns > 0:
        cmd.extend(["--max-turns", str(max_turns)])

    tools_value = request.provider_options.get("tools")
    if tools_value is not None:
        cmd.extend(["--tools", str(tools_value)])
    budget = request.provider_options.get("max_budget_usd")
    if budget is not None:
        cmd.extend(["--max-budget-usd", str(budget)])
    if request.provider_options.get("strict_mcp_config"):
        cmd.extend(["--strict-mcp-config", "--mcp-config", json.dumps({"mcpServers": {}})])
    setting_sources = request.provider_options.get("setting_sources")
    if setting_sources is not None:
        cmd.extend(["--setting-sources", str(setting_sources)])

    if request.system_prompt:
        cmd.extend(["--append-system-prompt", request.system_prompt])
    if request.enable_thinking:
        cmd.append("--include-partial-messages")

    return [_without_nul(argument) for argument in cmd]


def build_claude_prompt(request: CompletionRequest) -> str:
    """Render messages deterministically for the headless Claude CLI."""

    if request.provider_options.get("raw_single_user_prompt") is True:
        if (
            len(request.messages) == 1
            and isinstance(request.messages[0], dict)
            and request.messages[0].get("role") == "user"
            and isinstance(request.messages[0].get("content"), str)
        ):
            content = request.messages[0]["content"]
            if "\x00" in content:
                raise ValueError("raw Claude prompt contains a NUL byte")
            return content

    if not request.messages:
        return "Hello."

    rendered: list[str] = []
    for message in request.messages:
        role = str(message.get("role", "user")).title()
        content = message.get("content", "")
        if isinstance(content, list):
            chunks: list[str] = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
                elif isinstance(part, str):
                    chunks.append(part)
            content_text = "\n".join(chunks)
        else:
            content_text = str(content)
        rendered.append(f"{role}: {content_text}")
    return _without_nul("\n\n".join(rendered))
