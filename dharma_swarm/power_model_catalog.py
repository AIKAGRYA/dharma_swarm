"""Canonical high-power model lanes exposed to operator surfaces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PowerModelRoute:
    provider_id: str
    model_id: str
    display_name: str
    lane_role: str
    aliases: tuple[str, ...] = ()


POWER_MODEL_ROUTES: tuple[PowerModelRoute, ...] = (
    PowerModelRoute(
        provider_id="claude",
        model_id="claude-opus-4-6",
        display_name="Claude Opus 4.6",
        lane_role="primary_driver",
        aliases=("opus", "opus-4.6", "claude opus"),
    ),
    PowerModelRoute(
        provider_id="codex",
        model_id="gpt-5.4",
        display_name="Codex 5.4",
        lane_role="primary_driver",
        aliases=("codex", "codex-5.4", "gpt-5.4"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="anthropic/claude-opus-4.6",
        display_name="Claude Opus 4.6 API",
        lane_role="primary_driver",
        aliases=("opus-api", "claude-opus-api"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="anthropic/claude-opus-4.6-fast",
        display_name="Claude Opus 4.6 Fast API",
        lane_role="primary_driver",
        aliases=("opus-fast", "claude-opus-fast"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="openai/gpt-5.4",
        display_name="GPT-5.4 API",
        lane_role="primary_driver",
        aliases=("gpt-5.4-api", "openai-gpt-5.4"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="openai/gpt-5.4-pro",
        display_name="GPT-5.4 Pro API",
        lane_role="primary_driver",
        aliases=("gpt-5.4-pro", "openai-gpt-5.4-pro"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="z-ai/glm-5.1",
        display_name="GLM-5.1",
        lane_role="research_delegate",
        aliases=("glm-5.1", "glm51"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="z-ai/glm-5-turbo",
        display_name="GLM-5 Turbo",
        lane_role="research_delegate",
        aliases=("glm-5-turbo", "glm-turbo"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="z-ai/glm-5",
        display_name="GLM-5",
        lane_role="research_delegate",
        aliases=("glm-5", "glm5"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="moonshotai/kimi-k2.5",
        display_name="Kimi K2.5",
        lane_role="research_delegate",
        aliases=("kimi", "kimi-k2.5"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="qwen/qwen3-coder",
        display_name="Qwen3 Coder 480B",
        lane_role="bulk_builder",
        aliases=("qwen-coder", "qwen3-coder"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="qwen/qwen3-coder-plus",
        display_name="Qwen3 Coder Plus",
        lane_role="bulk_builder",
        aliases=("qwen-coder-plus", "qwen3-coder-plus"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="qwen/qwen3.5-397b-a17b",
        display_name="Qwen3.5 397B A17B",
        lane_role="bulk_builder",
        aliases=("qwen-3.5", "qwen35"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="qwen/qwen3.6-plus",
        display_name="Qwen3.6 Plus",
        lane_role="bulk_builder",
        aliases=("qwen-3.6", "qwen36"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="deepseek/deepseek-v3.2",
        display_name="DeepSeek V3.2",
        lane_role="challenger",
        aliases=("deepseek-v3.2", "deepseek"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="deepseek/deepseek-v3.2-speciale",
        display_name="DeepSeek V3.2 Speciale",
        lane_role="challenger",
        aliases=("deepseek-speciale", "deepseek-v3.2-speciale"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="deepseek/deepseek-r1-0528",
        display_name="DeepSeek R1 0528",
        lane_role="challenger",
        aliases=("deepseek-r1", "r1-0528"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="minimax/minimax-m2.7",
        display_name="MiniMax M2.7",
        lane_role="challenger",
        aliases=("minimax-openrouter", "minimax-m2.7-openrouter"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="minimax/minimax-m2.5",
        display_name="MiniMax M2.5",
        lane_role="challenger",
        aliases=("minimax-m2.5",),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="nvidia/nemotron-3-super-120b-a12b",
        display_name="Nemotron 3 Super 120B",
        lane_role="validator",
        aliases=("nemotron-super", "nemotron-120b"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="nvidia/llama-3.1-nemotron-ultra-253b-v1",
        display_name="Nemotron Ultra 253B",
        lane_role="validator",
        aliases=("nemotron-ultra", "nemotron-253b"),
    ),
    PowerModelRoute(
        provider_id="openrouter",
        model_id="nvidia/llama-3.3-nemotron-super-49b-v1.5",
        display_name="Nemotron Super 49B V1.5",
        lane_role="validator",
        aliases=("nemotron-49b", "nemotron-super-49b"),
    ),
)


OPENROUTER_POWER_MODELS: dict[str, str] = {
    route.model_id: route.display_name
    for route in POWER_MODEL_ROUTES
    if route.provider_id == "openrouter"
}


OLLAMA_CLOUD_POWER_MODELS: dict[str, str] = {
    "glm-5:cloud": "GLM-5 (Ollama Cloud)",
    "deepseek-v3.2:cloud": "DeepSeek v3.2 (Ollama Cloud)",
    "kimi-k2.5:cloud": "Kimi K2.5 (Ollama Cloud)",
    "qwen3-coder:480b-cloud": "Qwen3 Coder 480B (Ollama Cloud)",
    "minimax-m2.7:cloud": "MiniMax M2.7 (Ollama Cloud)",
}


__all__ = [
    "OLLAMA_CLOUD_POWER_MODELS",
    "OPENROUTER_POWER_MODELS",
    "POWER_MODEL_ROUTES",
    "PowerModelRoute",
]
