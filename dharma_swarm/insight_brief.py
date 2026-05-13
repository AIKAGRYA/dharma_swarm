"""Ontology-native Daily Insight Brief for Dhyana."""

from __future__ import annotations

import logging
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
from dharma_swarm.runtime_state import (
    DEFAULT_RUNTIME_DB,
    OperatorAction,
    RuntimeStateStore,
    operator_action_id_for_payload,
)

WITA = ZoneInfo("Asia/Makassar")
DEFAULT_ONTOLOGY_DB = Path.home() / ".dharma" / "ontology.db"
DEFAULT_DAILY_CAPTURE_DIR = Path.home() / ".dharma" / "sessions" / "captures" / "daily"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BriefClaim:
    """A claim that must cite one concrete Outcome row."""

    text: str
    outcome_id: str
    citation: str
    section: str


@dataclass(frozen=True)
class BriefOpenClaim:
    """A proposed Claim surfaced for follow-up."""

    obj_id: str
    text: str
    confidence: float
    evidence_count: int


@dataclass(frozen=True)
class BriefOpenQuestion:
    """An open Question surfaced for follow-up."""

    obj_id: str
    text: str
    priority: str
    domain: str


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
        open_claims = self._open_claim_summaries()
        open_questions = self._open_question_summaries()
        content = self._render_markdown(
            today,
            artifact.id,
            witness.id,
            claims,
            open_claims=open_claims,
            open_questions=open_questions,
        )
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

    def _open_claim_summaries(self) -> list[BriefOpenClaim]:
        claims = [
            claim for claim in self.gateway.registry.get_objects_by_type("Claim")
            if claim.properties.get("lifecycle_state") == "proposed"
            and float(claim.properties.get("confidence") or 0.0) < 1.0
        ]
        claims.sort(key=lambda obj: obj.created_at, reverse=True)

        summaries: list[BriefOpenClaim] = []
        for claim in claims[:5]:
            props = claim.properties
            evidence_links = self.gateway.registry.get_links(
                source_id=claim.id,
                link_name="claim_has_evidence",
            )
            evidence_refs = props.get("evidence_refs")
            fallback_count = len(evidence_refs) if isinstance(evidence_refs, list) else 0
            summaries.append(
                BriefOpenClaim(
                    obj_id=claim.id,
                    text=InsightBriefBuilder._clean_summary(str(props.get("statement") or "")),
                    confidence=float(props.get("confidence") or 0.0),
                    evidence_count=len(evidence_links) or fallback_count,
                )
            )
        return summaries

    def _open_question_summaries(self) -> list[BriefOpenQuestion]:
        questions = [
            question for question in self.gateway.registry.get_objects_by_type("Question")
            if question.properties.get("lifecycle_state") == "open"
        ]
        questions.sort(key=lambda obj: obj.created_at, reverse=True)

        summaries: list[BriefOpenQuestion] = []
        for question in questions[:5]:
            props = question.properties
            summaries.append(
                BriefOpenQuestion(
                    obj_id=question.id,
                    text=InsightBriefBuilder._clean_summary(str(props.get("text") or "")),
                    priority=str(props.get("priority") or "normal"),
                    domain=str(props.get("domain") or ""),
                )
            )
        return summaries

    @staticmethod
    def _render_markdown(
        today: str,
        artifact_id: str,
        witness_id: str,
        claims: list[BriefClaim],
        *,
        open_claims: list[BriefOpenClaim] | None = None,
        open_questions: list[BriefOpenQuestion] | None = None,
    ) -> str:
        open_claims = open_claims or []
        open_questions = open_questions or []
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
        if open_claims:
            lines.extend([f"## Open Claims (n={len(open_claims)})", ""])
            for claim in open_claims:
                lines.append(
                    "- "
                    f"`Claim/{claim.obj_id}` "
                    f"conf={claim.confidence:.2f} "
                    f"evidence={claim.evidence_count}: "
                    f"{claim.text}"
                )
            lines.append("")
        if open_questions:
            lines.extend([f"## Outstanding Questions (n={len(open_questions)})", ""])
            for question in open_questions:
                domain = f" domain={question.domain}" if question.domain else ""
                lines.append(
                    "- "
                    f"`Question/{question.obj_id}` "
                    f"priority={question.priority}"
                    f"{domain}: "
                    f"{question.text}"
                )
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
    capture_dir: str | Path | None = None,
    runtime_db: str | Path | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> Path:
    gw = gateway or OntologyActionGateway(path=ontology_path or DEFAULT_ONTOLOGY_DB)
    builder = InsightBriefBuilder(gw, output_dir=output_dir, now_fn=now_fn)
    brief = builder.compose(builder.propose())
    path = builder.publish(brief)
    if capture_dir is not None:
        capture_path = capture_daily_operator_brief(
            path,
            capture_dir=capture_dir,
            date_str=builder.now_fn().date().isoformat(),
        )
        _record_operator_brief_capture(
            brief,
            primary_path=path,
            capture_path=capture_path,
            runtime_db=Path(runtime_db) if runtime_db is not None else DEFAULT_RUNTIME_DB,
        )
    return path


def capture_daily_operator_brief(
    brief_path: str | Path,
    *,
    capture_dir: str | Path = DEFAULT_DAILY_CAPTURE_DIR,
    date_str: str | None = None,
) -> Path:
    """Copy the gated ontology brief into the daily operator capture sink."""
    source = Path(brief_path)
    if not source.exists():
        raise FileNotFoundError(f"brief path does not exist: {source}")
    if date_str is None:
        date_str = datetime.now(WITA).date().isoformat()
    target_dir = Path(capture_dir) / date_str
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "operator_brief.md"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def _record_operator_brief_capture(
    brief_obj: OntologyObj,
    *,
    primary_path: Path,
    capture_path: Path,
    runtime_db: Path,
) -> None:
    payload = {
        "artifact_id": brief_obj.id,
        "title": str(brief_obj.properties.get("title") or ""),
        "primary_path": str(primary_path),
        "capture_path": str(capture_path),
        "publish_channel": "daily_operator_capture",
    }
    action_name = "operator_brief_captured"
    actor = "insight_brief"
    reason = "Ontology-native daily brief copied to operator capture sink"
    action = OperatorAction(
        action_id=operator_action_id_for_payload(
            action_name=action_name,
            actor=actor,
            reason=reason,
            payload=payload,
        ),
        action_name=action_name,
        actor=actor,
        reason=reason,
        payload=payload,
    )
    try:
        RuntimeStateStore(runtime_db).record_operator_action_sync(action)
    except Exception:
        logger.debug("Failed to record operator brief capture action", exc_info=True)


def main() -> None:
    path = build_and_publish_daily_brief()
    print(path)


if __name__ == "__main__":
    main()
