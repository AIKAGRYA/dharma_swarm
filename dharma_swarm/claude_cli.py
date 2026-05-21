"""Shared Claude CLI helpers for unattended/background execution."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import shutil
import subprocess
from typing import Mapping

_MODEL_ALIASES: dict[str, str] = {
    "flash": "haiku",
    "gemini": "haiku",
    "gpt4": "sonnet",
    "gpt-4": "sonnet",
}

_ANTHROPIC_MODELS = frozenset({
    "sonnet", "opus", "haiku",
    "claude-sonnet-4-20250514", "claude-opus-4-6",
    "claude-3-5-sonnet", "claude-3-haiku",
})

_default_router = None


def _get_default_router():
    """Lazy singleton for the canonical ModelRouter."""
    global _default_router
    if _default_router is None:
        from dharma_swarm.providers import create_default_router
        _default_router = create_default_router()
    return _default_router


def _canonical_fallback(prompt: str, *, model: str | None = None) -> str:
    """Route through the canonical ModelRouter when Claude CLI is unavailable.

    Uses create_default_router() which wires provider_policy, smart_router,
    resilience (circuit breaker + retry), session affinity, routing memory,
    and reward ranking — the full chain.
    """
    from dharma_swarm.models import LLMRequest, ProviderType
    from dharma_swarm.provider_policy import ProviderRouteRequest

    router = _get_default_router()
    available = list(router._providers.keys())
    fallback_model = (
        model if model and model not in _ANTHROPIC_MODELS
        and model not in _MODEL_ALIASES else None
    )
    route_req = ProviderRouteRequest(
        action_name="claude_cli_fallback",
        risk_score=0.3,
        uncertainty=0.3,
        novelty=0.2,
        urgency=0.5,
        expected_impact=0.5,
    )
    llm_req = LLMRequest(
        model=fallback_model or "gemini-2.5-flash",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )

    async def _dispatch():
        _decision, response = await router.complete_for_task(
            route_req, llm_req,
            available_provider_types=available,
        )
        return response.content

    try:
        return asyncio.run(_dispatch())
    except RuntimeError:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, _dispatch()).result(timeout=60)


def resolve_claude_binary() -> str:
    """Find the Claude CLI binary, checking known install locations."""
    found = shutil.which("claude")
    if found:
        return found
    for candidate in (
        Path.home() / ".npm-global" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
        Path("/opt/homebrew/bin/claude"),
    ):
        if candidate.exists():
            return str(candidate)
    return "claude"


def build_claude_headless_command(
    prompt: str,
    *,
    model: str | None = None,
    output_format: str = "text",
    permission_mode: str | None = None,
    bare: bool = False,
    tools: str | None = "default",
) -> list[str]:
    """Build a `claude -p` command for unattended/background runs."""
    command = [
        resolve_claude_binary(),
        "-p",
        prompt,
        "--output-format",
        output_format,
    ]
    if model:
        resolved = _MODEL_ALIASES.get(model.lower(), model)
        command.extend(["--model", resolved])
    if permission_mode:
        command.extend(["--permission-mode", permission_mode])
    if bare:
        command.append("--bare")
    if tools:
        command.extend(["--tools", tools])
    return command


def build_claude_headless_env(
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Prepare a stable environment for nested/background Claude runs."""
    merged = dict(os.environ if env is None else env)
    merged["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    merged.pop("CLAUDECODE", None)
    merged.pop("CLAUDE_CODE_ENTRYPOINT", None)
    return merged


def unattended_claude_auth_error(
    *,
    bare: bool,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Return a fast-fail error when unattended Claude auth is unavailable.

    In `--bare` mode Claude Code skips OAuth/keychain auth entirely and requires
    an Anthropic API credential path. The unattended DGC lanes currently do not
    pass a settings-based apiKeyHelper, so a non-empty `ANTHROPIC_API_KEY` is
    the only supported auth source here.
    """
    if not bare:
        return None
    merged = build_claude_headless_env(env)
    if merged.get("ANTHROPIC_API_KEY", "").strip():
        return None
    return (
        "ERROR: unattended Claude bare mode requires ANTHROPIC_API_KEY; "
        "OAuth/login is ignored in --bare mode"
    )


def run_claude_headless(
    prompt: str,
    *,
    timeout: int = 600,
    model: str | None = None,
    permission_mode: str | None = "bypassPermissions",
    bare: bool = True,
    tools: str | None = "default",
) -> str:
    """Run Claude Code in headless mode for unattended/background work.

    When Claude CLI auth is unavailable (no ANTHROPIC_API_KEY), falls back
    to the canonical ModelRouter (provider_policy + smart_router + resilience)
    which routes through Gemini/OpenRouter/etc directly.
    """
    env = build_claude_headless_env()
    auth_error = unattended_claude_auth_error(bare=bare, env=env)

    if auth_error:
        try:
            return _canonical_fallback(prompt, model=model)
        except Exception as exc:
            return f"ERROR: Claude CLI auth failed and canonical fallback failed: {exc}"

    try:
        result = subprocess.run(
            build_claude_headless_command(
                prompt,
                model=model,
                permission_mode=permission_mode,
                bare=bare,
                tools=tools,
            ),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return result.stdout[:5000]
        detail = result.stderr or result.stdout or ""
        if "Credit balance is too low" in detail:
            try:
                return _canonical_fallback(prompt, model=model)
            except Exception:
                pass
        return f"Error (rc={result.returncode}): {detail[:500]}"
    except subprocess.TimeoutExpired:
        return "TIMEOUT: Claude Code exceeded limit"
    except FileNotFoundError:
        return "ERROR: claude CLI not found in PATH"
    except Exception as exc:
        return f"ERROR: {exc}"
