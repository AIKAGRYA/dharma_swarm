"""Target registry — where the Foundry aims, and where it must never.

Sequencing (market scouting report, 2026-08-18): AI-native venues first
(OpenEvolve, FlashInfer-Bench, AlgoTune, GPU MODE) where AI-authored, benchmark-
verified code is the welcome native format and policy risk is zero; graduate to
policy-gated engines (vLLM, SGLang) only with a track record and a human
reviewer. The do-not-touch list is absolute: projects that ban AI authorship, or
whose oracle is too weak to prove an improvement, or where a listing would
poison every other target.
"""

from __future__ import annotations

from dharma_swarm.foundry.target_ingest import TargetSpec

# --- AI-native first targets (contribution is the native format) -------------

T1_OPENEVOLVE = TargetSpec(
    id="openevolve-mlx",
    name="OpenEvolve — MLX Metal kernel example + evolved records",
    url="https://github.com/algorithmicsuperintelligence/openevolve",
    sha="",  # pinned at ingest time
    evolve_paths=["examples/mlx_metal_kernel_opt/"],
    oracle_cmd=["python", "-m", "unittest", "discover", "tests"],
    subdir="",
    license="Apache-2.0",
    ai_policy="native",
    notes=(
        "The reference implementation of the Foundry's own method. The MLX "
        "example is an honest open problem (README: best evolved kernel is 3.2% "
        "SLOWER than baseline after eval-validity fixes). Contributing evolved "
        "records / evaluator hardening is the welcome native contribution."
    ),
)

T2_FLASHINFER_BENCH = TargetSpec(
    id="flashinfer-bench",
    name="FlashInfer / FlashInfer-Bench kernel records",
    url="https://github.com/flashinfer-ai/flashinfer",
    sha="",
    evolve_paths=["benchmarks/"],
    oracle_cmd=["python", "-m", "flashinfer_bench", "run"],
    subdir="",
    license="Apache-2.0",
    ai_policy="native",
    notes=(
        "FlashInfer-Bench is a third-party harness built to score AI-generated "
        "kernels against FlashInfer baselines (a scored record is scored by "
        "infrastructure we do not control -> a strong domain-3(b) One Wire "
        "candidate). Kernel-class work routes through GPU MODE / KernelBot free "
        "GPUs; FlashInfer sits under vLLM/SGLang/TensorRT-LLM."
    ),
)

TARGET_REGISTRY: dict[str, TargetSpec] = {
    T1_OPENEVOLVE.id: T1_OPENEVOLVE,
    T2_FLASHINFER_BENCH.id: T2_FLASHINFER_BENCH,
}

# --- do-not-touch: absolute (AI-authorship bans, weak oracles, channel poison) ---

DO_NOT_TOUCH: dict[str, str] = {
    "ggml-org/llama.cpp": "predominantly-AI-generated PRs banned; edited AI code still counts; permanent-ban enforcement",
    "qemu/qemu": "AI-derived contributions declined (relaxation only proposed as of Aug 2026)",
    "gentoo": "AI contributions banned (council policy, Apr 2024)",
    "NetBSD": "LLM output treated as tainted code",
    "huggingface/transformers": "first-time contributors must not use code agents; agent-looking PRs closed without review",
    "llvm/llvm-project": "autonomous-PR bots banned; AI banned on good-first-issues",
    "torvalds/linux": "human-accountability model incompatible with a non-coding submitter",
    "ghostty-org/ghostty": "vouch system + public denouncement list; a listing poisons every other target",
    "tldraw/tldraw": "external PRs auto-closed",
    "curl/curl": "bug bounty closed over AI slop; AI security reports are brand-terminal",
    "*security-report*": "NEVER submit AI-generated security reports anywhere (one fabricated CVE brands the account permanently)",
}


class ForbiddenTarget(RuntimeError):
    """Raised when a target is on the do-not-touch list or bans AI authorship."""


def is_forbidden(repo_or_id: str) -> str | None:
    """Return the reason a target is off-limits, or None if it is allowed."""
    if repo_or_id in DO_NOT_TOUCH:
        return DO_NOT_TOUCH[repo_or_id]
    lowered = repo_or_id.lower()
    for key, reason in DO_NOT_TOUCH.items():
        stripped = key.strip("*")
        if stripped and stripped.lower() in lowered:
            return reason
    return None


def assert_contributable(spec: TargetSpec) -> None:
    """Raise :class:`ForbiddenTarget` if the target may not receive AI work."""
    reason = is_forbidden(spec.url) or is_forbidden(spec.id)
    if reason:
        raise ForbiddenTarget(f"{spec.id}: {reason}")
    if spec.ai_policy == "banned":
        raise ForbiddenTarget(f"{spec.id}: target ai_policy is 'banned'")
