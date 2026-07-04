"""Revenue Scout Daemon — autonomous scouting, ingestion, and routing loop.

Runs on cron or triggered by stigmergy signals. The full loop:

    1. SCOUT  — search GitHub for repos with AI governance gaps
    2. INGEST — pull competitive intelligence from configured sources
    3. PARSE  — extract structured claims, competitor profiles, revenue patterns
    4. ROUTE  — feed qualified targets + patterns into the RevenueSpine
    5. DRAFT  — generate outreach drafts for qualified targets (human-approved only)
    6. REPORT — log results to stigmergy + witness for the operator brief

Rule: NO AUTONOMOUS SPAM. Outreach drafts require human approval.
The daemon scouts, ingests, parses, and routes — it does NOT send messages.

Cron integration:
    Register as handler "revenue_scout" in cron_runner.py.
    Scheduled to run every 6 hours by default.

Signal bus integration:
    Emits SIGNAL_REVENUE_INTEL_INGESTED after each successful ingestion cycle.
    Listens for SIGNAL_REVENUE_SCOUT_TRIGGER to run ad-hoc cycles.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.revenue.spine import (
    RevenueSpine,
    OutreachChannel,
    RevenueTarget,
    TargetStatus,
)
from dharma_swarm.revenue.intelligence import RevenueIntelligenceIngestor

logger = logging.getLogger(__name__)

SIGNAL_REVENUE_INTEL_INGESTED = "REVENUE_INTEL_INGESTED"
SIGNAL_REVENUE_SCOUT_TRIGGER = "REVENUE_SCOUT_TRIGGER"

_SCOUT_DIR = Path.home() / ".dharma" / "revenue_scout"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Scout configuration
# ---------------------------------------------------------------------------

DEFAULT_GITHUB_QUERIES: list[str] = [
    "copilot agent language:python stars:>50",
    "ai-generated code review language:typescript stars:>100",
    "llm agent framework language:python stars:>200",
    "autonomous coding agent stars:>50",
]

DEFAULT_INTEL_SOURCES: list[dict[str, str]] = [
    {
        "title": "Agent Governance Market",
        "path": "docs/offers/agentic-code-governance-sprint.md",
    },
]


# ---------------------------------------------------------------------------
# Scout result model
# ---------------------------------------------------------------------------


class ScoutCycleResult(BaseModel):
    """Result of a single scout cycle."""

    timestamp: str = Field(default_factory=_utc_now_iso)
    targets_scouted: int = 0
    targets_qualified: int = 0
    claims_extracted: int = 0
    patterns_identified: int = 0
    outreach_drafted: int = 0
    targets_routed_from_intel: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------


class RevenueScoutDaemon:
    """Autonomous revenue scouting daemon.

    Usage::

        daemon = RevenueScoutDaemon()
        result = daemon.run_cycle()

        # Or run just specific phases:
        daemon.scout_github()
        daemon.ingest_intelligence()
        daemon.draft_outreach_for_qualified()
    """

    def __init__(
        self,
        spine: RevenueSpine | None = None,
        ingestor: RevenueIntelligenceIngestor | None = None,
        github_queries: list[str] | None = None,
        min_qualification_score: float = 0.3,
        max_targets_per_cycle: int = 10,
    ) -> None:
        self._spine = spine or RevenueSpine()
        self._ingestor = ingestor or RevenueIntelligenceIngestor()
        self._queries = github_queries or DEFAULT_GITHUB_QUERIES
        self._min_score = min_qualification_score
        self._max_targets = max_targets_per_cycle
        _SCOUT_DIR.mkdir(parents=True, exist_ok=True)

    def run_cycle(self) -> ScoutCycleResult:
        """Run a full scout → ingest → parse → route → draft cycle."""
        start = time.time()
        result = ScoutCycleResult()

        scout_result = self.scout_github()
        result.targets_scouted = scout_result.get("scouted", 0)
        result.targets_qualified = scout_result.get("qualified", 0)
        result.errors.extend(scout_result.get("errors", []))

        intel_result = self.ingest_intelligence()
        result.claims_extracted = intel_result.get("claims", 0)
        result.patterns_identified = intel_result.get("patterns", 0)
        result.targets_routed_from_intel = intel_result.get("routed", 0)
        result.errors.extend(intel_result.get("errors", []))

        draft_result = self.draft_outreach_for_qualified()
        result.outreach_drafted = draft_result.get("drafted", 0)
        result.errors.extend(draft_result.get("errors", []))

        result.duration_seconds = round(time.time() - start, 2)

        self._persist_result(result)
        self._emit_stigmergy(result)
        self._emit_signal(result)

        logger.info(
            "Revenue scout cycle complete: %d scouted, %d qualified, "
            "%d claims, %d patterns, %d drafts (%.1fs)",
            result.targets_scouted, result.targets_qualified,
            result.claims_extracted, result.patterns_identified,
            result.outreach_drafted, result.duration_seconds,
        )
        return result

    def scout_github(self) -> dict[str, Any]:
        """Scout GitHub for targets with governance gaps."""
        scouted = 0
        qualified = 0
        errors: list[str] = []

        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            logger.info("GITHUB_TOKEN not set — skipping GitHub scouting")
            return {"scouted": 0, "qualified": 0, "errors": ["GITHUB_TOKEN not set"]}

        try:
            from scripts.revenue.find_targets import scout_targets
            for query in self._queries:
                try:
                    targets = scout_targets(
                        query=query,
                        max_results=self._max_targets,
                        min_score=self._min_score,
                    )
                    for target in targets:
                        existing = self._spine.get_target(target.id)
                        if existing:
                            continue
                        self._spine.add_target(target)
                        scouted += 1
                        if target.qualification_score >= 0.5:
                            qualified += 1
                    time.sleep(1.0)
                except Exception as exc:
                    errors.append(f"Query '{query}': {exc}")
                    logger.warning("Scout query failed: %s — %s", query, exc)
        except ImportError:
            try:
                self._scout_github_inline()
            except Exception as exc:
                errors.append(f"Inline scout failed: {exc}")

        return {"scouted": scouted, "qualified": qualified, "errors": errors}

    def _scout_github_inline(self) -> dict[str, Any]:
        """Lightweight inline scouting when scripts.revenue is not importable."""
        from urllib.parse import quote_plus
        from urllib.request import Request, urlopen

        headers = {"Accept": "application/vnd.github.v3+json"}
        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            headers["Authorization"] = f"token {token}"

        scouted = 0
        for query in self._queries[:2]:
            try:
                url = f"https://api.github.com/search/repositories?q={quote_plus(query)}&sort=stars&per_page=5"
                req = Request(url, headers=headers)
                with urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())

                for repo in data.get("items", [])[:5]:
                    full_name = repo.get("full_name", "")
                    target = RevenueTarget(
                        name=full_name,
                        org=full_name.split("/")[0] if "/" in full_name else "",
                        domain=repo.get("language", "").lower() or "general",
                        pain_signals=["needs_governance_audit"],
                        repo_urls=[f"https://github.com/{full_name}"],
                        estimated_value_usd=5000.0,
                        status=TargetStatus.SCOUTED,
                        qualification_score=0.3,
                        intelligence={
                            "stars": repo.get("stargazers_count", 0),
                            "description": repo.get("description", ""),
                        },
                    )
                    self._spine.add_target(target)
                    scouted += 1
            except Exception as exc:
                logger.debug("Inline scout failed for query %s: %s", query, exc)

        return {"scouted": scouted, "qualified": 0, "errors": []}

    def ingest_intelligence(self) -> dict[str, Any]:
        """Ingest competitive intelligence from configured sources."""
        total_claims = 0
        total_patterns = 0
        routed = 0
        errors: list[str] = []

        repo_root = Path(__file__).resolve().parent.parent
        for source_cfg in DEFAULT_INTEL_SOURCES:
            path = repo_root / source_cfg["path"]
            if path.exists():
                try:
                    result = self._ingestor.ingest_file(path)
                    total_claims += result.claims_extracted
                    total_patterns += result.patterns_identified
                except Exception as exc:
                    errors.append(f"Ingest {source_cfg['title']}: {exc}")

        intel_dir = Path.home() / ".dharma" / "revenue_intel" / "inbox"
        if intel_dir.exists():
            for fpath in sorted(intel_dir.glob("*.md")) + sorted(intel_dir.glob("*.txt")):
                try:
                    result = self._ingestor.ingest_file(fpath)
                    total_claims += result.claims_extracted
                    total_patterns += result.patterns_identified
                    processed_dir = intel_dir / "processed"
                    processed_dir.mkdir(exist_ok=True)
                    fpath.rename(processed_dir / fpath.name)
                except Exception as exc:
                    errors.append(f"Ingest {fpath.name}: {exc}")

        try:
            routed = self._ingestor.route_to_spine(self._spine)
        except Exception as exc:
            errors.append(f"Route to spine: {exc}")

        return {
            "claims": total_claims,
            "patterns": total_patterns,
            "routed": routed,
            "errors": errors,
        }

    def draft_outreach_for_qualified(self) -> dict[str, Any]:
        """Draft outreach for qualified targets that don't have drafts yet."""
        drafted = 0
        errors: list[str] = []

        qualified = self._spine.list_targets(status=TargetStatus.QUALIFIED)
        existing_target_ids = {d.target_id for d in self._spine.pending_outreach()}

        offer = self._spine.default_offer()

        for target in qualified:
            if target.id in existing_target_ids:
                continue

            try:
                pain_hooks = self._build_pain_summary(target)
                subject = f"Code governance for {target.org or target.name}"
                body = (
                    f"Noticed governance gaps in {target.name}'s public repos. "
                    f"Signals: {', '.join(target.pain_signals[:3])}.\n\n"
                    f"{pain_hooks}\n\n"
                    f"We offer the {offer.title} — "
                    f"${offer.price_range_low_usd:,.0f}-${offer.price_range_high_usd:,.0f}, "
                    f"{offer.duration_days} days. Everything installed in your repo."
                )
                draft = self._spine.draft_outreach(
                    target.id, offer.id,
                    channel=OutreachChannel.EMAIL,
                    subject=subject,
                    body=body,
                )
                if draft:
                    drafted += 1
            except Exception as exc:
                errors.append(f"Draft for {target.name}: {exc}")

        return {"drafted": drafted, "errors": errors}

    def _build_pain_summary(self, target: RevenueTarget) -> str:
        """Build a one-sentence pain summary from target signals."""
        signal_descriptions = {
            "no_ci_gates": "no required status checks on the default branch",
            "bot_prs": "high ratio of bot/AI-authored PRs without review",
            "no_provenance": "no commit signing or provenance tracking",
            "high_churn": "high file churn suggesting AI slop accumulation",
            "needs_governance_audit": "AI tooling active but no governance framework",
        }
        descriptions = [
            signal_descriptions.get(s, s) for s in target.pain_signals[:3]
        ]
        if not descriptions:
            return ""
        return "Key findings: " + "; ".join(descriptions) + "."

    def _persist_result(self, result: ScoutCycleResult) -> None:
        """Persist cycle result for operator brief consumption."""
        log_path = _SCOUT_DIR / "cycle_log.jsonl"
        try:
            with open(log_path, "a") as f:
                f.write(result.model_dump_json() + "\n")
        except OSError:
            logger.warning("Failed to persist scout cycle result", exc_info=True)

    def _emit_stigmergy(self, result: ScoutCycleResult) -> None:
        """Leave a stigmergic mark for other agents to pick up."""
        try:
            from dharma_swarm.stigmergy import StigmergicMark
            mark_path = Path.home() / ".dharma" / "stigmergy" / "marks.jsonl"
            mark_path.parent.mkdir(parents=True, exist_ok=True)
            mark = StigmergicMark(
                agent="revenue_scout_daemon",
                file_path=str(_SCOUT_DIR / "cycle_log.jsonl"),
                action="scan",
                observation=(
                    f"Revenue scout: {result.targets_scouted} scouted, "
                    f"{result.claims_extracted} claims, "
                    f"{result.patterns_identified} patterns"
                ),
                salience=0.7 if result.targets_qualified > 0 else 0.4,
                channel="strategy",
            )
            with open(mark_path, "a") as f:
                f.write(mark.model_dump_json() + "\n")
        except Exception:
            logger.debug("Stigmergy emit failed", exc_info=True)

    def _emit_signal(self, result: ScoutCycleResult) -> None:
        """Emit a signal bus event for other loops to respond to."""
        try:
            from dharma_swarm.signal_bus import SignalBus
            bus = SignalBus.get()
            bus.emit({
                "type": SIGNAL_REVENUE_INTEL_INGESTED,
                "targets_scouted": result.targets_scouted,
                "claims_extracted": result.claims_extracted,
                "patterns_identified": result.patterns_identified,
                "timestamp": result.timestamp,
            })
        except Exception:
            logger.debug("Signal bus emit failed", exc_info=True)

    def summary(self) -> dict[str, Any]:
        """Get summary of all scout activity."""
        spine_snap = self._spine.snapshot()
        intel_summary = self._ingestor.summary()
        return {
            "pipeline": spine_snap.model_dump(),
            "intelligence": intel_summary,
            "scout_dir": str(_SCOUT_DIR),
        }


# ---------------------------------------------------------------------------
# Cron handler entry point
# ---------------------------------------------------------------------------


def revenue_scout_handler(job: dict[str, Any]) -> tuple[bool, str, None]:
    """Entry point for cron_runner.py handler dispatch.

    Returns (success, output, error) tuple matching the cron_runner contract.
    """
    try:
        min_score = float(job.get("min_qualification_score", 0.3))
        max_targets = int(job.get("max_targets_per_cycle", 10))
        queries = job.get("github_queries", DEFAULT_GITHUB_QUERIES)

        daemon = RevenueScoutDaemon(
            min_qualification_score=min_score,
            max_targets_per_cycle=max_targets,
            github_queries=queries,
        )
        result = daemon.run_cycle()

        output = (
            f"Revenue Scout Cycle — {result.timestamp}\n"
            f"  Targets scouted:  {result.targets_scouted}\n"
            f"  Targets qualified: {result.targets_qualified}\n"
            f"  Claims extracted:  {result.claims_extracted}\n"
            f"  Patterns found:    {result.patterns_identified}\n"
            f"  Outreach drafted:  {result.outreach_drafted}\n"
            f"  Intel routed:      {result.targets_routed_from_intel}\n"
            f"  Duration:          {result.duration_seconds:.1f}s\n"
        )
        if result.errors:
            output += f"  Errors: {len(result.errors)}\n"
            for err in result.errors[:5]:
                output += f"    - {err}\n"

        success = len(result.errors) < 3
        return success, output, None
    except Exception as exc:
        error_msg = f"Revenue scout failed: {exc}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg, None
