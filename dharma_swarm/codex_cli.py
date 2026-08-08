"""Shared Codex CLI launch defaults for DGC-owned execution paths."""

from __future__ import annotations

import os

DGC_CODEX_PROFILE_ENV = "DGC_CODEX_PROFILE"
DGC_CODEX_REASONING_EFFORT_ENV = "DGC_CODEX_REASONING_EFFORT"
_SUPPORTED_REASONING_EFFORTS = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh"}
)


def dgc_codex_exec_prefix(
    *,
    cli_path: str = "codex",
    dangerous_bypass: bool = True,
) -> list[str]:
    """Return the Codex exec prefix for DGC-owned launches.

    DGC runs Codex with the most permissive execution surface available.
    An optional profile can still be layered on via ``DGC_CODEX_PROFILE``.
    """

    cmd = [cli_path, "exec"]
    profile = os.environ.get(DGC_CODEX_PROFILE_ENV, "").strip()
    if profile:
        cmd.extend(["-p", profile])
    # DGC owns the execution contract for every subprocess it launches. Do not
    # inherit a workstation-wide experimental value (for example ``ultra``,
    # which current GPT-5.5 requests translate to the rejected value ``max``).
    # Keep an explicit, CLI-supported value at this boundary while retaining a
    # narrow operator override for lower-effort lanes.
    effort = os.environ.get(DGC_CODEX_REASONING_EFFORT_ENV, "xhigh").strip().lower()
    if effort not in _SUPPORTED_REASONING_EFFORTS:
        effort = "xhigh"
    cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])
    if dangerous_bypass:
        cmd.append("--dangerously-bypass-approvals-and-sandbox")
    return cmd
