"""Revenue Intelligence Ingestor — ingests, parses, and routes intel.

Wraps the parser functions from ``intel_parser`` and provides the
``RevenueIntelligenceIngestor`` class for the revenue daemon.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from dharma_swarm.revenue.intel_parser import (
    ClaimType,
    CompetitorProfile,
    IngestResult,
    IntelClaim,
    IntelDocument,
    IntelSource,
    RevenuePattern,
    build_competitor_profiles,
    identify_revenue_patterns,
    parse_claims,
)

logger = logging.getLogger(__name__)

_INTEL_DIR = Path.home() / ".dharma" / "revenue_intel"


class RevenueIntelligenceIngestor:
    """Ingests, parses, and routes competitive intelligence.

    Usage::

        ingestor = RevenueIntelligenceIngestor()

        # Ingest raw text
        result = ingestor.ingest_text(
            "ServiceNow says its L1 service desk handles 90%+ requests...",
            title="ServiceNow Autonomous Workforce"
        )

        # Ingest from file
        result = ingestor.ingest_file(Path("research/competitor_analysis.md"))

        # Get actionable insights
        patterns = ingestor.get_revenue_patterns()
        competitors = ingestor.get_competitor_profiles()

        # Route high-value claims to the economic spine
        ingestor.route_to_spine(spine)
    """

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        self._dir = storage_dir or _INTEL_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._documents: dict[str, IntelDocument] = {}
        self._claims: list[IntelClaim] = []
        self._competitors: list[CompetitorProfile] = []
        self._patterns: list[RevenuePattern] = []
        self._load()

    def ingest_text(
        self,
        content: str,
        title: str = "Untitled Intelligence",
        source: IntelSource = IntelSource.MANUAL,
        source_url: str = "",
    ) -> IngestResult:
        """Ingest raw text and extract structured claims."""
        start = time.time()

        doc = IntelDocument(
            title=title,
            content=content,
            source=source,
            source_url=source_url,
        )

        claims = parse_claims(doc)
        doc.claims_extracted = len(claims)

        self._documents[doc.id] = doc
        self._claims.extend(claims)
        self._persist_doc(doc)
        for claim in claims:
            self._persist_claim(claim)

        self._competitors = build_competitor_profiles(self._claims)
        self._patterns = identify_revenue_patterns(self._claims)

        elapsed_ms = (time.time() - start) * 1000

        result = IngestResult(
            document_id=doc.id,
            claims_extracted=len(claims),
            competitors_identified=len(self._competitors),
            patterns_identified=len(self._patterns),
            top_claims=sorted(claims, key=lambda c: c.revenue_relevance, reverse=True)[:5],
            duration_ms=elapsed_ms,
        )

        logger.info(
            "Ingested '%s': %d claims, %d competitors, %d patterns (%.0fms)",
            title, len(claims), len(self._competitors),
            len(self._patterns), elapsed_ms,
        )
        return result

    def ingest_file(self, path: Path) -> IngestResult:
        """Ingest a file (Markdown, text, or JSON)."""
        if not path.exists():
            return IngestResult(
                document_id="",
                errors=[f"File not found: {path}"],
            )

        content = path.read_text(encoding="utf-8", errors="replace")
        source = IntelSource.MANUAL

        if path.suffix == ".json":
            try:
                data = json.loads(content)
                content = json.dumps(data, indent=2)
            except json.JSONDecodeError:
                pass

        return self.ingest_text(
            content,
            title=path.stem.replace("_", " ").replace("-", " ").title(),
            source=source,
        )

    def ingest_batch(self, texts: list[tuple[str, str]]) -> list[IngestResult]:
        """Ingest multiple (title, content) pairs."""
        results: list[IngestResult] = []
        for title, content in texts:
            results.append(self.ingest_text(content, title=title))
        return results

    def get_claims(
        self,
        claim_type: ClaimType | None = None,
        min_relevance: float = 0.0,
        limit: int = 50,
    ) -> list[IntelClaim]:
        """Get claims filtered and sorted by relevance."""
        claims = self._claims
        if claim_type is not None:
            claims = [c for c in claims if c.claim_type == claim_type]
        if min_relevance > 0:
            claims = [c for c in claims if c.revenue_relevance >= min_relevance]
        claims = sorted(claims, key=lambda c: c.revenue_relevance, reverse=True)
        return claims[:limit]

    def get_competitor_profiles(self) -> list[CompetitorProfile]:
        return self._competitors

    def get_revenue_patterns(self) -> list[RevenuePattern]:
        return self._patterns

    def route_to_spine(self, spine: Any) -> int:
        """Route high-value intelligence to the revenue spine as targets.

        Returns the number of targets created.
        """
        from dharma_swarm.revenue.spine import RevenueTarget, TargetStatus

        created = 0
        for pattern in self._patterns:
            if pattern.dharma_swarm_fit < 0.4:
                continue

            target = RevenueTarget(
                name=f"[pattern] {pattern.name}",
                domain="revenue_pattern",
                pain_signals=[f"pattern:{pattern.name.lower().replace(' ', '_')}"],
                estimated_value_usd=pattern.estimated_tam_usd,
                status=TargetStatus.SCOUTED,
                qualification_score=pattern.dharma_swarm_fit,
                intelligence={
                    "pattern_id": pattern.id,
                    "description": pattern.description,
                    "examples": pattern.examples,
                    "complexity": pattern.implementation_complexity,
                    "time_to_revenue_days": pattern.time_to_revenue_days,
                },
            )
            spine.add_target(target)
            created += 1

        logger.info("Routed %d revenue patterns to spine", created)
        return created

    def summary(self) -> dict[str, Any]:
        """Get a summary of all ingested intelligence."""
        return {
            "documents_ingested": len(self._documents),
            "total_claims": len(self._claims),
            "claims_by_type": {
                ct.value: sum(1 for c in self._claims if c.claim_type == ct)
                for ct in ClaimType
                if any(c.claim_type == ct for c in self._claims)
            },
            "competitors_profiled": len(self._competitors),
            "top_competitors": [
                {"name": p.name, "relevance": round(p.relevance_score, 2)}
                for p in self._competitors[:10]
            ],
            "revenue_patterns": [
                {
                    "name": p.name,
                    "fit": round(p.dharma_swarm_fit, 2),
                    "time_to_revenue_days": p.time_to_revenue_days,
                    "complexity": p.implementation_complexity,
                }
                for p in self._patterns
            ],
            "high_relevance_claims": sum(
                1 for c in self._claims if c.revenue_relevance >= 0.6
            ),
        }

    # -- Persistence -------------------------------------------------------

    def _persist_doc(self, doc: IntelDocument) -> None:
        path = self._dir / "documents.jsonl"
        try:
            with open(path, "a") as f:
                f.write(doc.model_dump_json() + "\n")
        except OSError:
            logger.warning("Failed to persist document", exc_info=True)

    def _persist_claim(self, claim: IntelClaim) -> None:
        path = self._dir / "claims.jsonl"
        try:
            with open(path, "a") as f:
                f.write(claim.model_dump_json() + "\n")
        except OSError:
            logger.warning("Failed to persist claim", exc_info=True)

    def _load(self) -> None:
        docs_path = self._dir / "documents.jsonl"
        if docs_path.exists():
            try:
                for line in docs_path.read_text().splitlines():
                    line = line.strip()
                    if line:
                        try:
                            doc = IntelDocument.model_validate_json(line)
                            self._documents[doc.id] = doc
                        except Exception:
                            continue
            except OSError:
                pass

        claims_path = self._dir / "claims.jsonl"
        if claims_path.exists():
            try:
                for line in claims_path.read_text().splitlines():
                    line = line.strip()
                    if line:
                        try:
                            self._claims.append(IntelClaim.model_validate_json(line))
                        except Exception:
                            continue
            except OSError:
                pass

        if self._claims:
            self._competitors = build_competitor_profiles(self._claims)
            self._patterns = identify_revenue_patterns(self._claims)
