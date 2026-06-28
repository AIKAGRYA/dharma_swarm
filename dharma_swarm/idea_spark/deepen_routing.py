"""Single-source, Kimi-floored routing for the deepen pipeline.

Every deepen LLM call goes through the ONE canonical router
(model_hierarchy -> runtime_provider.complete_via_preferred_runtime_providers).
This module adds the operator's HARD CAPABILITY FLOOR: never route a deepen
call below the Kimi-2.6 tier. It restricts the provider chain to >=floor
providers (cheap/free-strong first, escalating to powerful) and NEVER falls
back to the weak free lane (NVIDIA NIM llama / small ollama). If no >=floor
provider is reachable it RAISES rather than silently degrading — an honest
floor, not a soft preference.

Floor reality (verified live 2026-06-28):
  - OpenRouter moonshotai/kimi-k2.6 is the literal floor model but the account
    is currently unfunded (402); kimi-k2.7 is not a valid OpenRouter id.
  - GOOGLE_AI gemini-2.5-flash is the working >=floor provider here.
  - OLLAMA glm-5:cloud is >=floor but currently rate-limited (429).
The PROPER long-term fix is to lift this floor into model_hierarchy itself so
ALL routing (not just deepen) respects it; this module is the scoped first cut.
"""

from __future__ import annotations

from dataclasses import dataclass

from dharma_swarm.models import ProviderType
from dharma_swarm.runtime_provider import complete_via_preferred_runtime_providers

# >= Kimi-2.6 capability tier, ordered cheap/free-strong -> powerful.
# Deliberately EXCLUDES NVIDIA_NIM / small-ollama (below floor).
FLOOR_PROVIDER_ORDER: tuple[ProviderType, ...] = (
    ProviderType.OPENROUTER,  # moonshotai/kimi-k2.6 — the literal floor (needs credits)
    ProviderType.GOOGLE_AI,   # gemini-2.5-flash — working, cheap, strong
    ProviderType.OLLAMA,      # glm-5:cloud — strong; may rate-limit
)
FLOOR_OPENROUTER_MODEL = "moonshotai/kimi-k2.6"


@dataclass(frozen=True)
class DeepenLLMResult:
    text: str
    provider: str
    model: str


async def deepen_llm(
    messages: list[dict[str, str]],
    system: str = "",
    *,
    max_tokens: int = 2048,
    temperature: float = 0.4,
) -> DeepenLLMResult:
    """One LLM completion at or above the Kimi floor, via the single router.

    Raises RuntimeError (from the router) if no >=floor provider is reachable —
    deepen never runs on a sub-floor model.
    """
    resp, cfg = await complete_via_preferred_runtime_providers(
        messages=messages,
        system=system,
        openrouter_model=FLOOR_OPENROUTER_MODEL,
        provider_order=FLOOR_PROVIDER_ORDER,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    text = getattr(resp, "content", None) or getattr(resp, "text", "") or ""
    return DeepenLLMResult(
        text=str(text),
        provider=str(getattr(cfg, "provider", "")),
        model=str(getattr(cfg, "default_model", "")),
    )
