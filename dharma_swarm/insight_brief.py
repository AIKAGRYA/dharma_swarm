"""Ontology-native Daily Insight Brief for Dhyana."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from textwrap import shorten
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

from dharma_swarm.ontology import OntologyObj
from dharma_swarm.ontology_action_gateway import (
    OntologyActionGateway,
    OntologyGatewayError,
)

WITA = ZoneInfo("Asia/Makassar")
DEFAULT_ONTOLOGY_DB = Path.home() / ".dharma" / "ontology.db"


@dataclass(frozen=True)
class BriefClaim:
    """A claim that must cite one concrete Outcome row."""

    text: str
    outcome_id: str
    citation: str
    section: str


class InsightBriefBuilder:
    """Build and publish one fail-closed ontology-cited brief."""

    def __init__(
        self,
        gateway: OntologyActionGateway | None = None,
        *,
        output_dir: str | Path | None = None,
        now_fn: Callable[[], datetime] | None = None,
        max_outcomes: int = 5,
    ) -> None:
        if gateway is None:
            raise OntologyGatewayError("InsightBriefBuilder requires an OntologyActionGateway")
        self.gateway = gateway
        self.output_dir = Path(output_dir or Path.home() / "dharma_briefs")
        self.now_fn = now_fn or (lambda: datetime.now(WITA))
        self.max_outcomes = max_outcomes
        self._composed_ids: set[str] = set()

    def propose(self) -> list[OntologyObj]:
        """Select high-signal Outcome objects as the only admissible source material."""
        outcomes = self.gateway.registry.get_objects_by_type("Outcome")
        outcomes.sort(
            key=lambda obj: (self._outcome_score(obj), str(obj.created_at)),
            reverse=True,
        )
        return outcomes[: self.max_outcomes]

    def compose(self, thread_objs: Iterable[OntologyObj]) -> OntologyObj:
        """Create WitnessLog + KnowledgeArtifact and link each cited Outcome."""
        outcomes = list(thread_objs)
        if not outcomes:
            raise OntologyGatewayError("Insight brief requires at least one Outcome row")

        today = self.now_fn().date().isoformat()
        witness = self.gateway.create_object_or_fail(
            "WitnessLog",
            {
                "observation": f"Daily Insight Brief source review for {today}",
                "observer": "insight_brief",
                "context": "ontology_native_flow_001",
                "witness_quality": 1.0,
                "contraction_level": "L3",
            },
            created_by="insight_brief",
        )
        artifact = self.gateway.create_object_or_fail(
            "KnowledgeArtifact",
            {
                "title": f"Daily Insight Brief {today}",
                "artifact_type": "note",
                "domain": "dharma_swarm",
                "content": "",
                "provenance": "ontology_native_flow_001",
                "confidence": 1.0,
                "verified": True,
                "audience": "dhyana",
            },
            created_by="insight_brief",
        )

        claims = self._claims_for(artifact.id, outcomes)
        content = self._render_markdown(today, artifact.id, witness.id, claims)
        artifact = self.gateway.update_object_or_fail(
            artifact.id,
            {"content": content},
            updated_by="insight_brief",
        )

        for outcome in outcomes:
            self.gateway.link_or_fail(
                "derived_from",
                artifact.id,
                outcome.id,
                created_by="insight_brief",
            )
        self.gateway.link_or_fail(
            "cites_witness",
            artifact.id,
            witness.id,
            created_by="insight_brief",
        )

        self._composed_ids.add(artifact.id)
        return artifact

    def publish(self, brief_obj: OntologyObj) -> Path:
        """Gate and write the brief markdown file."""
        if brief_obj.id not in self._composed_ids:
            raise OntologyGatewayError(
                "publish requires a brief composed by InsightBriefBuilder"
            )
        content = str(brief_obj.properties.get("content") or "").strip()
        if not content:
            raise OntologyGatewayError("brief content is empty")

        today = self.now_fn().date().isoformat()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{today}-brief.md"
        self.gateway.execute_action_or_fail(
            "KnowledgeArtifact",
            "Publish",
            brief_obj.id,
            {"channel": "filesystem", "path": str(path)},
            executed_by="insight_brief",
        )
        path.write_text(content + "\n", encoding="utf-8")
        self.gateway.update_object_or_fail(
            brief_obj.id,
            {
                "published_path": str(path),
                "published_at": self.now_fn().isoformat(),
                "published_channel": "filesystem",
            },
            updated_by="insight_brief",
        )
        return path

    @staticmethod
    def _claims_for(artifact_id: str, outcomes: list[OntologyObj]) -> list[BriefClaim]:
        claims: list[BriefClaim] = []
        for index, outcome in enumerate(outcomes, start=1):
            props = outcome.properties
            task_id = str(props.get("task_id") or "unknown-task")
            agent_id = str(props.get("agent_id") or "unknown-agent")
            success = bool(props.get("success"))
            summary = str(
                props.get("result_summary")
                or props.get("error")
                or "No result summary recorded"
            ).strip()
            status = "completed" if success else "failed"
            citation = f"ontology://KnowledgeArtifact/{artifact_id}#cites/Outcome/{outcome.id}"
            section = "Signals" if success else "Breakages"
            claims.append(
                BriefClaim(
                    text=(
                        f"{index}. `{task_id}` {status} under `{agent_id}`: "
                        f"{InsightBriefBuilder._clean_summary(summary)}"
                    ),
                    outcome_id=outcome.id,
                    citation=citation,
                    section=section,
                )
            )
        return claims

    @staticmethod
    def _render_markdown(
        today: str,
        artifact_id: str,
        witness_id: str,
        claims: list[BriefClaim],
    ) -> str:
        lines = [
            f"# Daily Insight Brief - {today}",
            "",
            f"Artifact: `KnowledgeArtifact/{artifact_id}`",
            f"Witness: `WitnessLog/{witness_id}`",
            "",
        ]
        for section in ("Signals", "Breakages"):
            section_claims = [claim for claim in claims if claim.section == section]
            if not section_claims:
                continue
            lines.extend([f"## {section}", ""])
            for claim in section_claims:
                lines.append(f"- {claim.text} [{claim.citation}]")
            lines.append("")
        lines.extend([
            "## Decision Surface",
            "",
            "- Read only claims with resolvable Outcome citations.",
            "- Treat missing citations as a build failure, not editorial drift.",
        ])
        return "\n".join(lines)

    @staticmethod
    def _outcome_score(outcome: OntologyObj) -> int:
        props = outcome.properties
        success = bool(props.get("success"))
        text = str(
            props.get("result_summary")
            or props.get("error")
            or ""
        ).strip()
        lower = text.lower()

        score = 100 if success else 25
        if len(text) >= 80:
            score += 10
        if text.startswith("##"):
            score -= 5
        if any(marker in lower for marker in ("verified", "passed", "completed", "synthesis", "report")):
            score += 10
        if lower.startswith(("i'll ", "i will ", "let me ")):
            score -= 30
        if not text:
            score -= 60
        if InsightBriefBuilder._is_provider_plumbing_failure(text):
            score -= 200
        return score

    @staticmethod
    def _clean_summary(text: str) -> str:
        ascii_text = text.encode("ascii", "ignore").decode("ascii")
        stripped = re.sub(r"(^|\s)#{1,6}\s*", " ", ascii_text)
        stripped = stripped.replace("**", "").replace("__", "").replace("`", "")
        one_line = " ".join(stripped.split())
        if not one_line:
            return "No result summary recorded"
        return shorten(one_line, width=180, placeholder="...")

    @staticmethod
    def _is_provider_plumbing_failure(text: str) -> bool:
        lower = text.lower()
        return any(
            marker in lower
            for marker in (
                "all providers failed",
                "provider_error",
                "credit balance is too low",
                "selected model",
                "may not exist or you may not have access",
                "not logged in",
            )
        )


def build_and_publish_daily_brief(
    *,
    gateway: OntologyActionGateway | None = None,
    output_dir: str | Path | None = None,
    ontology_path: str | Path | None = None,
) -> Path:
    gw = gateway or OntologyActionGateway(path=ontology_path or DEFAULT_ONTOLOGY_DB)
    builder = InsightBriefBuilder(gw, output_dir=output_dir)
    brief = builder.compose(builder.propose())
    return builder.publish(brief)


def main() -> None:
    path = build_and_publish_daily_brief()
    print(path)


if __name__ == "__main__":
    main()
