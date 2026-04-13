"""Two-tier LLM synthesis engine for the Research RTN.

Tier B (free/cheap): GLM-5, Nemotron, Qwen3 — source summarization, fact extraction.
Tier A (Anthropic): Claude Sonnet — editorial synthesis with citations.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from dharma_swarm.auto_research.models import ClaimRecord, SourceDocument
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType

logger = logging.getLogger(__name__)

TIER_B_CHAIN: list[ProviderType] = [
    ProviderType.OLLAMA,
    ProviderType.NVIDIA_NIM,
    ProviderType.GROQ,
    ProviderType.CEREBRAS,
]

TIER_A_PROVIDER = ProviderType.ANTHROPIC
TIER_A_MODEL = "claude-sonnet-4-20250514"


@dataclass
class SourceSummary:
    source_id: str
    title: str
    url: str
    summary: str
    key_facts: list[str] = field(default_factory=list)


@dataclass
class SynthesizedSection:
    title: str
    text: str
    claims: list[ClaimRecord] = field(default_factory=list)
    source_ids_used: list[str] = field(default_factory=list)
    model_used: str = ""
    provider_used: str = ""


class SynthesisEngine:
    def __init__(self, router: Any = None) -> None:
        self._router = router

    def _get_router(self) -> Any:
        if self._router is None:
            from dharma_swarm.providers import create_default_router
            self._router = create_default_router()
        return self._router

    async def _call_llm(
        self,
        provider: ProviderType,
        system: str,
        user_msg: str,
        max_tokens: int = 2048,
        temperature: float = 0.3,
        model: str = "",
    ) -> LLMResponse | None:
        router = self._get_router()
        request = LLMRequest(
            model=model or "",
            messages=[{"role": "user", "content": user_msg}],
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            return await router.complete(provider, request)
        except Exception as exc:
            logger.debug("LLM call failed (%s): %s", provider.value, exc)
            return None

    async def _call_tier_b(
        self,
        system: str,
        user_msg: str,
        max_tokens: int = 512,
    ) -> LLMResponse | None:
        for provider in TIER_B_CHAIN:
            resp = await self._call_llm(provider, system, user_msg, max_tokens=max_tokens)
            if resp and resp.content.strip():
                return resp
        return None

    async def summarize_source(self, source: SourceDocument) -> SourceSummary:
        content_preview = (source.content or source.title or "")[:3000]
        if not content_preview.strip():
            return SourceSummary(
                source_id=source.source_id,
                title=source.title,
                url=source.url,
                summary="No content available.",
            )

        system = "Extract key facts from this source. Output a 2-3 sentence summary followed by a bullet list of key facts. Be precise and factual."
        user_msg = f"Source: {source.title}\nURL: {source.url}\n\nContent:\n{content_preview}"

        resp = await self._call_tier_b(system, user_msg, max_tokens=400)
        if resp and resp.content.strip():
            lines = resp.content.strip().split("\n")
            summary_lines = []
            facts = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith(("-", "•", "*")):
                    facts.append(stripped.lstrip("-•* "))
                elif stripped:
                    summary_lines.append(stripped)
            return SourceSummary(
                source_id=source.source_id,
                title=source.title,
                url=source.url,
                summary=" ".join(summary_lines[:3]),
                key_facts=facts[:8],
            )

        return SourceSummary(
            source_id=source.source_id,
            title=source.title,
            url=source.url,
            summary=content_preview[:200],
        )

    async def summarize_sources(
        self,
        sources: list[SourceDocument],
        max_concurrent: int = 3,
    ) -> list[SourceSummary]:
        summaries: list[SourceSummary] = []
        for i in range(0, len(sources), max_concurrent):
            batch = sources[i:i + max_concurrent]
            results = await asyncio.gather(
                *[self.summarize_source(s) for s in batch],
                return_exceptions=True,
            )
            for j, r in enumerate(results):
                if isinstance(r, Exception):
                    logger.debug("Summarization error: %s", r)
                    summaries.append(SourceSummary(
                        source_id=batch[j].source_id,
                        title=batch[j].title,
                        url=batch[j].url,
                        summary="Summarization failed.",
                    ))
                else:
                    summaries.append(r)
            if i + max_concurrent < len(sources):
                await asyncio.sleep(0.3)
        return summaries

    async def synthesize_section(
        self,
        section_title: str,
        section_description: str,
        summaries: list[SourceSummary],
        claims: list[ClaimRecord],
        target_words: int = 600,
    ) -> SynthesizedSection:
        # Build source inventory
        inventory_lines = ["SOURCE INVENTORY:"]
        source_ids = []
        for s in summaries:
            source_ids.append(s.source_id)
            facts_str = "; ".join(s.key_facts[:4]) if s.key_facts else "no extracted facts"
            inventory_lines.append(f"[{s.source_id}] {s.title} — {s.summary[:150]} | Facts: {facts_str}")

        claim_lines = ["VERIFIED CLAIMS:"]
        for c in claims[:20]:
            cites = ", ".join(c.citations) if c.citations else f"[{c.supporting_source_ids[0]}]" if c.supporting_source_ids else ""
            claim_lines.append(f"- {c.text} {cites}")

        system = (
            f"You are writing section '{section_title}' of a research brief on autonomous coding agents.\n"
            f"Write exactly {target_words} words of analytical prose.\n"
            f"CRITICAL: Cite sources using their IDs in brackets like [src-abc12345]. "
            f"Every factual claim MUST have a citation. Use only source IDs from the inventory below.\n"
            f"Be analytical, not descriptive. Compare, contrast, identify patterns, draw conclusions.\n"
            f"Do NOT use markdown headers — the section title is already set."
        )
        user_msg = (
            f"Section: {section_title}\n"
            f"Focus: {section_description}\n\n"
            f"{chr(10).join(inventory_lines)}\n\n"
            f"{chr(10).join(claim_lines)}\n\n"
            f"Write the section now ({target_words} words, with [src-X] citations):"
        )

        resp = await self._call_llm(
            TIER_A_PROVIDER,
            system,
            user_msg,
            max_tokens=target_words * 3,
            temperature=0.4,
            model=TIER_A_MODEL,
        )

        if not resp or not resp.content.strip():
            # Fallback: try Tier B
            resp = await self._call_tier_b(system, user_msg, max_tokens=target_words * 3)

        text = resp.content.strip() if resp else self._fallback_section(section_title, summaries, claims)
        model_used = resp.model if resp else "fallback"
        provider_used = resp.provider if resp else "none"

        # Extract claims from synthesized text
        synth_claims = self._extract_cited_claims(text, source_ids, section_title)

        return SynthesizedSection(
            title=section_title,
            text=text,
            claims=synth_claims,
            source_ids_used=source_ids,
            model_used=model_used,
            provider_used=provider_used,
        )

    def _extract_cited_claims(
        self,
        text: str,
        valid_source_ids: list[str],
        section_title: str,
    ) -> list[ClaimRecord]:
        import re
        claims: list[ClaimRecord] = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        valid_set = set(valid_source_ids)
        for sent in sentences:
            cited_ids = re.findall(r'\[(src-[a-f0-9]+)\]', sent)
            valid_cited = [sid for sid in cited_ids if sid in valid_set]
            if valid_cited:
                clean_text = re.sub(r'\[src-[a-f0-9]+\]', '', sent).strip()
                if len(clean_text) > 20:
                    claims.append(ClaimRecord(
                        claim_id=f"synth-{section_title[:10]}-{len(claims)+1}",
                        text=clean_text,
                        support_level="supported",
                        supporting_source_ids=valid_cited,
                        citations=[f"[{sid}]" for sid in valid_cited],
                        confidence=0.85,
                    ))
        return claims

    def _fallback_section(
        self,
        title: str,
        summaries: list[SourceSummary],
        claims: list[ClaimRecord],
    ) -> str:
        lines = [f"Based on {len(summaries)} sources analyzed:\n"]
        for s in summaries[:5]:
            lines.append(f"- {s.summary} [{s.source_id}]")
        if claims:
            lines.append("\nKey findings:")
            for c in claims[:5]:
                cites = " ".join(c.citations) if c.citations else ""
                lines.append(f"- {c.text} {cites}")
        return "\n".join(lines)
