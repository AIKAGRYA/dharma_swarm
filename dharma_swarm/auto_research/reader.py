"""Source normalization and enrichment utilities for AutoResearch."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .models import SourceDocument
from .search import RawSourceDocument

logger = logging.getLogger(__name__)

_MAX_CONTENT_CHARS = 8000
_ENRICH_DELAY = 0.5  # seconds between Jina calls to avoid rate limits


class SourceReader:
    def normalize(self, source: RawSourceDocument) -> SourceDocument:
        if isinstance(source, SourceDocument):
            return source
        return SourceDocument.model_validate(source)

    def normalize_all(self, sources: list[RawSourceDocument]) -> list[SourceDocument]:
        return [self.normalize(source) for source in sources]

    async def enrich_source(self, source: SourceDocument) -> SourceDocument:
        if source.content and len(source.content) > 500:
            return source  # already has substantial content
        try:
            from dharma_swarm.web_search import fetch_url
            full_text = await fetch_url(source.url)
            if full_text and not full_text.startswith("Error"):
                return source.model_copy(
                    update={"content": full_text[:_MAX_CONTENT_CHARS]}
                )
        except Exception as exc:
            logger.debug("Failed to enrich %s: %s", source.url, exc)
        return source

    async def enrich_sources(
        self,
        sources: list[SourceDocument],
        max_concurrent: int = 3,
    ) -> list[SourceDocument]:
        enriched: list[SourceDocument] = []
        for i in range(0, len(sources), max_concurrent):
            batch = sources[i:i + max_concurrent]
            results = await asyncio.gather(
                *[self.enrich_source(s) for s in batch],
                return_exceptions=True,
            )
            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.debug("Enrichment error: %s", result)
                    enriched.append(batch[j])
                else:
                    enriched.append(result)
            if i + max_concurrent < len(sources):
                await asyncio.sleep(_ENRICH_DELAY)
        return enriched
