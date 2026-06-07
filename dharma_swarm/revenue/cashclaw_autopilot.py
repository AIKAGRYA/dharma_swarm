"""CashClaw Autopilot — governed cash-opportunity queue.

This is Dharma's CashClaw-shaped loop without CashClaw's external side
effects. It scans local/spine/synthetic opportunity surfaces, scores for
speed-to-cash, writes top-10 action packets, and runs each packet through the
Business Idea Gauntlet. It does not accept work, send outreach, submit bids, or
touch payments.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from ipaddress import ip_address
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from dharma_swarm.revenue.action_gateway import write_gateway_receipt
from dharma_swarm.revenue.cashclaw_employees import (
    CashClawEmployeeReceiptBundle,
    build_employee_receipt_bundle,
    write_employee_receipt_bundle,
)
from dharma_swarm.revenue.idea_gauntlet import (
    DECISION_HOLD,
    DECISION_KILL,
    DECISION_PASS,
    evaluate_candidate_dir,
    write_evaluation,
)
from dharma_swarm.revenue.live_intake import CashClawLiveIntake, pattern_card_to_opportunity
from dharma_swarm.revenue.live_intake_sources import load_source_configs
from dharma_swarm.revenue.spine import RevenueSpine, RevenueTarget

logger = logging.getLogger(__name__)

WEIGHTS: dict[str, int] = {
    "cash_speed": 20,
    "deliverability": 20,
    "distribution_access": 15,
    "payment_clarity": 15,
    "risk_cleanliness": 15,
    "agent_leverage": 10,
    "receipt_quality": 5,
}

HARD_RISK_FLAGS: tuple[str, ...] = (
    "regulated_advice",
    "tos_conflict",
    "secret_or_pii",
    "spam_or_bulk_outreach",
    "guaranteed_revenue",
    "requires_signup_or_credentials",
    "payment_or_wallet_action",
    "autonomous_send_requested",
    "auth_or_sensitive_security",
    "ai_disallowed_or_human_only",
    "security_or_bug_bounty",
    "non_cash_or_token_reward",
)

TRUTHY = {"1", "true", "yes", "y", "on"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str, *, limit: int = 52) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug or "opportunity")[:limit].strip("-") or "opportunity"


def _safe_path_segment(value: str, field_name: str) -> str:
    segment = str(value or "").strip()
    if (
        not segment
        or "/" in segment
        or "\\" in segment
        or ".." in Path(segment).parts
        or not re.fullmatch(r"[A-Za-z0-9_.:-]+", segment)
    ):
        raise ValueError(f"unsafe {field_name}: {value}")
    return segment


def _resolve_under(root: Path, child: str) -> Path:
    root_resolved = root.resolve()
    candidate = (root_resolved / child).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"path escapes root: {candidate}") from exc
    return candidate


def _validate_hyrve_fetch(url: str) -> None:
    if not _safe_bool(os.environ.get("DHARMA_CASHCLAW_ALLOW_HYRVE"), False):
        raise ValueError("HYRVE fetch requires DHARMA_CASHCLAW_ALLOW_HYRVE=1")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("HYRVE fetch requires https")
    host = (parsed.hostname or "").strip().lower()
    if host != "cashclawai.com":
        raise ValueError("HYRVE fetch host not allowed")
    if _host_is_private_or_local(host):
        raise ValueError("HYRVE fetch host cannot be local/private")


def _host_is_private_or_local(host: str) -> bool:
    if host in {"localhost", "0.0.0.0"} or host.endswith(".localhost"):
        return True
    try:
        parsed = ip_address(host)
    except ValueError:
        return False
    return parsed.is_private or parsed.is_loopback or parsed.is_link_local or parsed.is_reserved


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _safe_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in TRUTHY


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


class CashOpportunity(BaseModel):
    """One candidate task, lead, bounty, or paid service opening."""

    id: str = ""
    source: str = "synthetic"
    source_url: str = ""
    buyer_name: str = ""
    org: str = ""
    title: str
    description: str = ""
    pain_signals: list[str] = Field(default_factory=list)
    budget_usd: float = 0.0
    estimated_value_usd: float = 0.0
    payment_clarity: str = ""
    distribution_access: str = ""
    service_fit: str = ""
    deliverable: str = ""
    due_hours: int = 72
    evidence: list[str] = Field(default_factory=list)
    risk_signals: list[str] = Field(default_factory=list)
    agent_doable_steps: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class CashActionPacket(BaseModel):
    """Operator-reviewable next action for one ranked opportunity."""

    action_id: str
    rank: int
    opportunity_id: str
    created_at: str = Field(default_factory=_utc_now_iso)
    score: int
    score_breakdown: dict[str, int]
    verdict: str
    approval_packet_ready: bool = False
    approval_required: bool = True
    status: str = "UNSENT_UNSUBMITTED"
    no_external_side_effects: bool = True
    source: str = ""
    source_url: str = ""
    buyer_name: str = ""
    org: str = ""
    title: str = ""
    estimated_value_usd: float = 0.0
    service_fit: str = ""
    proposed_price_usd: float = 0.0
    proposed_deliverable: str = ""
    first_action: str = ""
    draft_message: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    gauntlet_decision: str = ""
    gauntlet_score: int = 0
    artifact_dir: str = ""
    gateway_decision: str = ""
    gateway_decision_id: str = ""
    gateway_decision_reasons: list[str] = Field(default_factory=list)
    gateway_required_receipts: list[str] = Field(default_factory=list)
    gateway_decision_path: str = ""
    employee_receipt_id: str = ""
    employee_receipt_bundle_id: str = ""
    execution_receipt_id: str = ""
    employee_receipt_path: str = ""
    employee_receipt_count: int = 0
    employee_roles_completed: list[str] = Field(default_factory=list)


class CashCycleResult(BaseModel):
    """Receipts for one CashClaw Autopilot cycle."""

    cycle_id: str
    timestamp: str = Field(default_factory=_utc_now_iso)
    mode: str = "dry_run"
    opportunities_scanned: int = 0
    top10: list[CashActionPacket] = Field(default_factory=list)
    top3_urgent: list[CashActionPacket] = Field(default_factory=list)
    state_dir: str = ""
    report_path: str = ""
    latest_queue_path: str = ""
    cycle_log_path: str = ""
    estimated_cost_usd: float = 0.0
    cost_cap_usd: float = 5.0
    employee_receipts_written: int = 0
    employee_receipts_path: str = ""
    gateway_allow_count: int = 0
    gateway_review_count: int = 0
    gateway_block_count: int = 0
    clean_cycle: bool = True
    side_effects_performed: bool = False
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    external_network_reads_performed: bool = False


class CashClawAutopilot:
    """Governed CashClaw loop adapted to Dharma's existing stack."""

    def __init__(
        self,
        *,
        spine: RevenueSpine | None = None,
        state_dir: str | Path | None = None,
        report_dir: str | Path | None = None,
        gauntlet_root: str | Path | None = None,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self._spine = spine
        self._state_dir = Path(state_dir) if state_dir is not None else Path.home() / ".dharma" / "cashclaw_autopilot"
        self._report_dir = (
            Path(report_dir)
            if report_dir is not None
            else repo_root / "reports" / "revenue_wedge" / "cashclaw_autopilot_001"
        )
        self._gauntlet_root = (
            Path(gauntlet_root)
            if gauntlet_root is not None
            else repo_root
            / "reports"
            / "revenue_wedge"
            / "gauntlet_runs"
            / "cashclaw_autopilot_001"
        )
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._report_dir.mkdir(parents=True, exist_ok=True)
        self._gauntlet_root.mkdir(parents=True, exist_ok=True)

    def run_cycle(self, job: dict[str, Any] | None = None) -> CashCycleResult:
        """Run one scan/score/packetize cycle with local receipts only."""
        job = job or {}
        started = time.time()
        timestamp = _utc_now_iso()
        cycle_id = "cashclaw-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        top_n = _safe_int(job.get("top_n"), 10)
        max_opportunities = _safe_int(job.get("max_opportunities"), 25)
        mode = str(job.get("mode") or "dry_run").strip() or "dry_run"
        cost_cap_usd = _safe_float(job.get("cost_cap_usd"), 5.0)
        errors: list[str] = []
        external_network_reads_performed = False

        opportunities: list[CashOpportunity] = []
        if _safe_bool(job.get("include_synthetic"), True):
            opportunities.extend(self._synthetic_opportunities())
        if _safe_bool(job.get("include_local"), True):
            inbox_dir = Path(str(job.get("inbox_dir") or self._state_dir / "inbox")).expanduser()
            try:
                opportunities.extend(self._scan_local_inbox(inbox_dir))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"local inbox scan failed: {exc}")
        if _safe_bool(job.get("include_spine"), True):
            try:
                opportunities.extend(self._scan_revenue_spine())
            except Exception as exc:  # noqa: BLE001
                errors.append(f"RevenueSpine scan failed: {exc}")
        if _safe_bool(job.get("include_hyrve"), False):
            try:
                opportunities.extend(self._scan_hyrve(job))
                external_network_reads_performed = True
            except Exception as exc:  # noqa: BLE001
                errors.append(f"HYRVE scan failed: {exc}")
        if _safe_bool(job.get("include_live_intake"), False):
            try:
                live_opportunities, live_network_reads = self._scan_live_intake(job)
                opportunities.extend(live_opportunities)
                external_network_reads_performed = external_network_reads_performed or live_network_reads
            except Exception as exc:  # noqa: BLE001
                errors.append(f"live intake scan failed: {exc}")

        deduped = sorted(
            self._dedupe_opportunities(opportunities),
            key=self._opportunity_preselect_score,
            reverse=True,
        )[:max_opportunities]
        planned_top_n = min(top_n, len(deduped))
        estimated_cost_usd = round(0.05 + len(deduped) * 0.01 + planned_top_n * 0.02, 2)
        if estimated_cost_usd > cost_cap_usd:
            result = CashCycleResult(
                cycle_id=cycle_id,
                timestamp=timestamp,
                mode=mode,
                opportunities_scanned=len(deduped),
                state_dir=str(self._state_dir),
                estimated_cost_usd=estimated_cost_usd,
                cost_cap_usd=cost_cap_usd,
                clean_cycle=False,
                side_effects_performed=False,
                errors=[
                    f"estimated cycle cost ${estimated_cost_usd:.2f} exceeds cap ${cost_cap_usd:.2f}; no artifacts written"
                ],
                duration_seconds=round(time.time() - started, 2),
                external_network_reads_performed=external_network_reads_performed,
            )
            self._persist_result(result)
            return result

        ranked = sorted(
            (self._build_packet(opp, idx + 1, cycle_id) for idx, opp in enumerate(deduped)),
            key=lambda packet: packet.score,
            reverse=True,
        )

        top_packets: list[CashActionPacket] = []
        gateway_counts = {"allow": 0, "review": 0, "block": 0}
        employee_receipts_written = 0
        for rank, packet in enumerate(ranked[:top_n], start=1):
            packet.rank = rank
            candidate_dir = self._write_gauntlet_candidate(packet)
            packet.artifact_dir = str(candidate_dir)
            evaluation = evaluate_candidate_dir(candidate_dir)
            write_evaluation(candidate_dir, evaluation)
            packet.gauntlet_decision = evaluation.decision
            packet.gauntlet_score = evaluation.score
            packet.approval_packet_ready = evaluation.can_create_human_packet
            if packet.gauntlet_decision == DECISION_KILL:
                packet.verdict = DECISION_KILL
            elif packet.gauntlet_decision == DECISION_HOLD:
                packet.verdict = DECISION_HOLD
            elif packet.gauntlet_decision == DECISION_PASS:
                packet.verdict = DECISION_PASS
            bundle = self._attach_employee_gateway_receipts(packet, candidate_dir, cycle_id, job)
            employee_receipts_written += len(bundle.employee_receipts)
            for decision, count in bundle.decision_counts.items():
                gateway_counts[decision] = gateway_counts.get(decision, 0) + count
            top_packets.append(packet)

        result = CashCycleResult(
            cycle_id=cycle_id,
            timestamp=timestamp,
            mode=mode,
            opportunities_scanned=len(deduped),
            top10=top_packets,
            top3_urgent=top_packets[:3],
            state_dir=str(self._state_dir),
            estimated_cost_usd=estimated_cost_usd,
            cost_cap_usd=cost_cap_usd,
            employee_receipts_written=employee_receipts_written,
            employee_receipts_path=str(self._gauntlet_root),
            gateway_allow_count=gateway_counts["allow"],
            gateway_review_count=gateway_counts["review"],
            gateway_block_count=gateway_counts["block"],
            clean_cycle=not errors and estimated_cost_usd <= cost_cap_usd,
            side_effects_performed=False,
            errors=errors,
            duration_seconds=round(time.time() - started, 2),
            external_network_reads_performed=external_network_reads_performed,
        )
        self._persist_result(result)
        return result

    def _scan_local_inbox(self, inbox_dir: Path) -> list[CashOpportunity]:
        if not inbox_dir.exists():
            return []
        opportunities: list[CashOpportunity] = []
        for path in sorted(inbox_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = payload if isinstance(payload, list) else [payload]
            for idx, record in enumerate(records):
                if not isinstance(record, dict):
                    continue
                opportunities.append(self._opportunity_from_mapping(record, fallback_id=f"{path.stem}-{idx}"))
        return opportunities

    def _scan_revenue_spine(self) -> list[CashOpportunity]:
        spine = self._spine or RevenueSpine()
        opportunities: list[CashOpportunity] = []
        for target in spine.list_targets():
            opportunities.append(self._opportunity_from_spine_target(target))
        return opportunities

    def _scan_hyrve(self, job: dict[str, Any]) -> list[CashOpportunity]:
        """Optional public marketplace fetch; off by default for dry governance."""
        url = str(job.get("hyrve_url") or "https://cashclawai.com/api/tasks").strip()
        _validate_hyrve_fetch(url)
        req = Request(url, headers={"Accept": "application/json", "User-Agent": "dharma-cashclaw-autopilot/0.1"})
        with urlopen(req, timeout=_safe_int(job.get("hyrve_timeout_sec"), 15)) as resp:
            max_bytes = _safe_int(job.get("hyrve_max_bytes"), 1_000_000)
            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise ValueError("HYRVE response exceeded max byte cap")
            payload = json.loads(raw.decode("utf-8"))
        records = payload.get("tasks", payload) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            return []
        return [
            self._opportunity_from_mapping(record, fallback_id=f"hyrve-{idx}")
            for idx, record in enumerate(records)
            if isinstance(record, dict)
        ]

    def _scan_live_intake(self, job: dict[str, Any]) -> tuple[list[CashOpportunity], bool]:
        """Optional read-only market intelligence intake; off by default."""
        configs = []
        for config_path in _as_list(job.get("live_source_config") or job.get("live_source_configs")):
            configs.extend(load_source_configs(config_path))
        fixtures = _as_list(job.get("live_fixture") or job.get("live_fixtures"))
        intake = CashClawLiveIntake(
            report_root=Path(str(job.get("live_report_root") or self._report_dir / "live_intake"))
        )
        result = intake.run(
            source_configs=configs,
            fixture_paths=fixtures,
            output_root=job.get("live_output_root"),
            top_n=_safe_int(job.get("live_top_n") or job.get("top_n"), 10),
            max_items=_safe_int(job.get("live_max_items"), 100),
            allow_network=_safe_bool(job.get("allow_live_network"), False),
        )
        opportunities = [
            self._opportunity_from_mapping(pattern_card_to_opportunity(card), fallback_id=card.pattern_card_id)
            for card in result.pattern_cards
        ]
        return opportunities, result.network_reads_performed

    def _opportunity_from_mapping(self, record: dict[str, Any], *, fallback_id: str) -> CashOpportunity:
        title = str(record.get("title") or record.get("name") or record.get("task") or fallback_id)
        budget = _safe_float(
            record.get("budget_usd")
            or record.get("budget")
            or record.get("estimated_value_usd")
            or record.get("value_usd")
        )
        estimated = _safe_float(record.get("estimated_value_usd") or record.get("value_usd"), budget)
        return CashOpportunity(
            id=str(record.get("id") or fallback_id),
            source=str(record.get("source") or record.get("platform") or "local_inbox"),
            source_url=str(record.get("source_url") or record.get("url") or ""),
            buyer_name=str(record.get("buyer_name") or record.get("buyer") or record.get("client") or ""),
            org=str(record.get("org") or record.get("company") or ""),
            title=title,
            description=str(record.get("description") or record.get("body") or record.get("summary") or ""),
            pain_signals=_as_list(record.get("pain_signals") or record.get("pain")),
            budget_usd=budget,
            estimated_value_usd=estimated or budget,
            payment_clarity=str(record.get("payment_clarity") or record.get("payment") or ""),
            distribution_access=str(record.get("distribution_access") or record.get("channel") or ""),
            service_fit=str(record.get("service_fit") or record.get("offer") or ""),
            deliverable=str(record.get("deliverable") or record.get("output") or ""),
            due_hours=_safe_int(record.get("due_hours") or record.get("deadline_hours"), 72),
            evidence=_as_list(record.get("evidence") or record.get("evidence_refs")),
            risk_signals=_as_list(record.get("risk_signals") or record.get("risks")),
            agent_doable_steps=_as_list(record.get("agent_doable_steps") or record.get("steps")),
            tags=_as_list(record.get("tags")),
            raw=record,
        )

    def _opportunity_from_spine_target(self, target: RevenueTarget) -> CashOpportunity:
        source_url = target.repo_urls[0] if target.repo_urls else ""
        description = " ".join(target.pain_signals) or str(target.intelligence.get("description", ""))
        return CashOpportunity(
            id=f"spine-{target.id}",
            source="revenue_spine",
            source_url=source_url,
            buyer_name=target.name,
            org=target.org,
            title=f"Paid governance sprint candidate: {target.name}",
            description=description,
            pain_signals=list(target.pain_signals),
            budget_usd=target.estimated_value_usd,
            estimated_value_usd=target.estimated_value_usd,
            payment_clarity="target value estimated in RevenueSpine; human scoping required",
            distribution_access="existing RevenueSpine target; no outreach drafted by CashClaw Autopilot",
            service_fit="Agentic Code Governance Sprint",
            deliverable="Ranked repo governance audit packet and scoped paid sprint proposal.",
            due_hours=72,
            evidence=[source_url] if source_url else ["RevenueSpine target ledger"],
            agent_doable_steps=[
                "inspect public repo signals",
                "draft human approval packet",
                "prepare scoped deliverable checklist",
            ],
            tags=["revenue_spine", "code_governance"],
            raw=target.model_dump(),
        )

    def _synthetic_opportunities(self) -> list[CashOpportunity]:
        """Seed queue with realistic, non-external fixtures for clean cycles."""
        rows = [
            {
                "id": "synthetic-paid-repo-xray",
                "source": "agent_service_inbound_fixture",
                "buyer_name": "Seed-stage AI SaaS",
                "org": "ExampleAI",
                "title": "48-hour AI repo governance x-ray",
                "description": "Buyer needs an AI-generated code risk audit before investor diligence.",
                "pain_signals": ["AI code churn", "investor diligence", "missing eval/provenance gates"],
                "budget_usd": 1500,
                "payment_clarity": "fixed-fee pilot paid after reviewed report",
                "distribution_access": "operator can approve direct warm outreach packet",
                "service_fit": "Agentic Code Governance Sprint",
                "deliverable": "10-page repo x-ray, top 20 risks, CI/eval gate proposal, and repair backlog.",
                "due_hours": 48,
                "evidence": ["fixture: common AI SaaS diligence pain"],
                "agent_doable_steps": ["repo scan", "risk ranking", "report drafting", "human packet"],
                "tags": ["code_governance", "fast_cash"],
            },
            {
                "id": "synthetic-lead-enrichment",
                "source": "local_business_ops_fixture",
                "buyer_name": "Boutique agency owner",
                "org": "Growth Ops Studio",
                "title": "Lead list cleanup and enrichment sprint",
                "description": "Agency has stale leads and needs clean company/contact research with source receipts.",
                "pain_signals": ["stale CRM", "manual research bottleneck", "needs source receipts"],
                "budget_usd": 600,
                "payment_clarity": "fixed-fee CSV deliverable",
                "distribution_access": "local operator approval packet only",
                "service_fit": "Lead Research / Enrichment",
                "deliverable": "Verified 100-row lead sheet with source links and confidence notes.",
                "due_hours": 36,
                "evidence": ["fixture: common agency operations pain"],
                "agent_doable_steps": ["research rows", "dedupe sheet", "add receipts"],
                "tags": ["lead_research", "agent_doable"],
            },
            {
                "id": "synthetic-creator-sponsor-inbox",
                "source": "creator_ops_fixture",
                "buyer_name": "Creator with inbound sponsors",
                "org": "Creator Desk",
                "title": "Sponsor inbox triage SOP and draft negotiation packet",
                "description": "Creator needs daily brand-deal triage, sponsor legitimacy checks, rate-card mapping, and drafts for human send.",
                "pain_signals": ["too many inbound emails", "brand-deal negotiation latency", "needs no-send drafts"],
                "budget_usd": 900,
                "payment_clarity": "setup fee plus monthly retainer possible",
                "distribution_access": "known transcript pattern; can package demo with dummy inbox",
                "service_fit": "AI employee installation",
                "deliverable": "Sandboxed brand-deal triage agent spec, dummy test inbox, and no-send draft SOP.",
                "due_hours": 72,
                "evidence": ["fixture: creator agent workflow transcript pattern"],
                "agent_doable_steps": ["write SOP", "build dummy inbox tests", "draft approval policy"],
                "tags": ["agent_install", "creator_ops"],
            },
            {
                "id": "synthetic-internal-tool",
                "source": "code_task_fixture",
                "buyer_name": "Ops manager",
                "org": "Field Services Co",
                "title": "Build a CSV-to-dashboard internal tool",
                "description": "Team manually merges CSVs each week and wants a small dashboard with import validation.",
                "pain_signals": ["manual reporting", "spreadsheet errors", "weekly recurring pain"],
                "budget_usd": 1200,
                "payment_clarity": "milestone paid on working local demo",
                "distribution_access": "operator can approve scoped proposal packet",
                "service_fit": "Internal Tool Delivery",
                "deliverable": "Single-user import dashboard, validation report, and README.",
                "due_hours": 72,
                "evidence": ["fixture: common local business reporting pain"],
                "agent_doable_steps": ["parse CSV", "build app", "write demo data", "test locally"],
                "tags": ["code_delivery", "local_business"],
            },
            {
                "id": "synthetic-grant-intel",
                "source": "funding_intel_fixture",
                "buyer_name": "Climate research nonprofit",
                "org": "Green Lab",
                "title": "Grant fit scan and application calendar",
                "description": "Nonprofit needs a ranked funding calendar with eligibility notes and source links.",
                "pain_signals": ["funding search overload", "eligibility uncertainty", "deadline tracking"],
                "budget_usd": 500,
                "payment_clarity": "fixed-fee research memo",
                "distribution_access": "research-only packet, no application submission",
                "service_fit": "Grant / Funding Intelligence",
                "deliverable": "Top 15 grant opportunities with eligibility, dates, and next-action checklist.",
                "due_hours": 72,
                "evidence": ["fixture: funding intelligence service pattern"],
                "agent_doable_steps": ["search sources", "rank fit", "write memo"],
                "tags": ["grant_intel", "research"],
            },
            {
                "id": "synthetic-agent-setup",
                "source": "ai_employee_fixture",
                "buyer_name": "Solo consultant",
                "org": "Advisory Solo",
                "title": "Install one AI employee for recurring inbox/report workflow",
                "description": "Consultant wants one cron-based AI employee to prepare a daily client briefing from local docs.",
                "pain_signals": ["daily repetitive briefing", "context scattered", "needs approval boundaries"],
                "budget_usd": 1000,
                "payment_clarity": "setup fee plus optional support",
                "distribution_access": "can be sold as sandboxed installation after human approval",
                "service_fit": "Agent setup / AI employee installation",
                "deliverable": "One sandboxed daily briefing agent, skill file, test fixture, and operator approval checklist.",
                "due_hours": 48,
                "evidence": ["fixture: OpenClaw employee-install trend"],
                "agent_doable_steps": ["define skill", "create cron", "run dummy cycles", "write SOP"],
                "tags": ["agent_install", "fast_cash"],
            },
            {
                "id": "synthetic-no-code-ops-agent",
                "source": "ai_employee_fixture",
                "buyer_name": "Operations lead",
                "org": "Micro SaaS Team",
                "title": "Daily KPI digest AI employee",
                "description": "Team wants a daily digest from CSV exports, support notes, and GitHub activity.",
                "pain_signals": ["manual daily reporting", "context switching", "needs source-linked summaries"],
                "budget_usd": 750,
                "payment_clarity": "fixed setup fee for working dry-run digest",
                "distribution_access": "can be sold from existing agent-loop proof",
                "service_fit": "AI employee installation",
                "deliverable": "One cron-based digest agent, sample input folder, markdown report, and rollback notes.",
                "due_hours": 48,
                "evidence": ["fixture: recurring ops digest pain"],
                "agent_doable_steps": ["define schema", "write skill", "run dummy digest", "document approval gates"],
                "tags": ["agent_install", "ops"],
            },
            {
                "id": "synthetic-support-macro-audit",
                "source": "customer_support_fixture",
                "buyer_name": "Support manager",
                "org": "B2B SaaS Helpdesk",
                "title": "Support macro cleanup and automation map",
                "description": "Helpdesk has outdated macros and wants duplicate cleanup plus automation candidates.",
                "pain_signals": ["outdated macros", "repeated tickets", "support team overload"],
                "budget_usd": 700,
                "payment_clarity": "fixed-fee audit memo",
                "distribution_access": "operator approval packet with no direct helpdesk changes",
                "service_fit": "AI automation / productized service",
                "deliverable": "Macro audit, duplicate map, top 10 automation candidates, and safe rollout plan.",
                "due_hours": 72,
                "evidence": ["fixture: support automation wedge"],
                "agent_doable_steps": ["cluster macros", "rank automation wins", "write SOP"],
                "tags": ["support_ops", "automation"],
            },
            {
                "id": "synthetic-marketplace-rfp-summary",
                "source": "paid_task_marketplace_fixture",
                "buyer_name": "Marketplace client",
                "org": "RFP Desk",
                "title": "Summarize 30 RFPs into qualification matrix",
                "description": "Client needs a source-linked matrix to decide which RFPs to pursue this week.",
                "pain_signals": ["too many RFPs", "qualification bottleneck", "needs decision matrix"],
                "budget_usd": 450,
                "payment_clarity": "marketplace fixed-price deliverable",
                "distribution_access": "marketplace response requires human approval",
                "service_fit": "Research support",
                "deliverable": "Spreadsheet with fit score, deadlines, requirements, and source links for 30 RFPs.",
                "due_hours": 36,
                "evidence": ["fixture: paid task marketplace research"],
                "agent_doable_steps": ["read docs", "extract requirements", "score fit", "write sheet"],
                "tags": ["marketplace", "research"],
            },
            {
                "id": "synthetic-bounty-docs",
                "source": "bounty_fixture",
                "buyer_name": "Open-source maintainer",
                "org": "Agent Framework Project",
                "title": "Documentation quickstart bounty",
                "description": "Project needs a working quickstart with verified install steps and screenshots.",
                "pain_signals": ["docs gaps", "onboarding friction", "open bounty"],
                "budget_usd": 300,
                "payment_clarity": "bounty paid after merged documentation PR",
                "distribution_access": "public issue/PR path; no submit without approval",
                "service_fit": "Code/internal-tool delivery",
                "deliverable": "Tested quickstart doc, reproduction notes, and PR-ready patch.",
                "due_hours": 48,
                "evidence": ["fixture: public bounty docs pattern"],
                "agent_doable_steps": ["install project", "verify quickstart", "write docs patch"],
                "tags": ["bounty", "docs", "code_delivery"],
            },
            {
                "id": "synthetic-data-cleanup",
                "source": "local_business_ops_fixture",
                "buyer_name": "Clinic admin",
                "org": "Wellness Clinic",
                "title": "De-identified appointment CSV cleanup",
                "description": "Admin needs de-identified operational CSVs cleaned and summarized for staffing decisions.",
                "pain_signals": ["messy exports", "staffing decision delay", "manual cleanup"],
                "budget_usd": 400,
                "payment_clarity": "fixed-fee local data cleanup after de-identification confirmed",
                "distribution_access": "requires human review of data handling before acceptance",
                "service_fit": "Local business operations automation",
                "deliverable": "Cleaned de-identified CSV, summary pivots, and repeatable cleanup script.",
                "due_hours": 72,
                "evidence": ["fixture: local operations data cleanup"],
                "agent_doable_steps": ["validate no PII", "clean CSV", "create summary", "write script"],
                "tags": ["local_business", "data_cleanup"],
            },
            {
                "id": "synthetic-content-repurposing",
                "source": "creator_ops_fixture",
                "buyer_name": "Podcast operator",
                "org": "Niche Podcast",
                "title": "Turn three transcripts into LinkedIn post pack",
                "description": "Creator needs transcript mining, hooks, post drafts, and source timestamps.",
                "pain_signals": ["unused transcripts", "content calendar gaps", "needs timestamp receipts"],
                "budget_usd": 350,
                "payment_clarity": "fixed-fee content pack",
                "distribution_access": "draft-only packet; no publishing",
                "service_fit": "Content / creator operations",
                "deliverable": "12 LinkedIn drafts, hook variants, and timestamp/source map.",
                "due_hours": 24,
                "evidence": ["fixture: transcript repurposing workflow"],
                "agent_doable_steps": ["parse transcript", "extract hooks", "draft posts", "map timestamps"],
                "tags": ["creator_ops", "content"],
            },
            {
                "id": "synthetic-competitive-intel",
                "source": "productized_service_fixture",
                "buyer_name": "Founder",
                "org": "Vertical SaaS",
                "title": "Competitor pricing and positioning tear-down",
                "description": "Founder wants a source-backed snapshot of competitor pricing, packaging, and feature gaps.",
                "pain_signals": ["pricing uncertainty", "competitor pressure", "sales enablement need"],
                "budget_usd": 650,
                "payment_clarity": "fixed-fee research report",
                "distribution_access": "operator can approve research-only proposal",
                "service_fit": "AI automation/productized services",
                "deliverable": "Competitor matrix, pricing evidence links, positioning notes, and opportunity summary.",
                "due_hours": 48,
                "evidence": ["fixture: productized competitive intelligence"],
                "agent_doable_steps": ["collect sources", "build matrix", "write report"],
                "tags": ["research", "productized_service"],
            },
            {
                "id": "synthetic-github-triage",
                "source": "code_task_fixture",
                "buyer_name": "Engineering lead",
                "org": "Small DevTools Startup",
                "title": "GitHub issue triage and duplicate clustering",
                "description": "Team has a noisy issue backlog and needs duplicates, priorities, and quick wins identified.",
                "pain_signals": ["noisy backlog", "duplicate issues", "triage debt"],
                "budget_usd": 800,
                "payment_clarity": "fixed-fee backlog report",
                "distribution_access": "public repo analysis; no issue edits without approval",
                "service_fit": "Code/internal-tool delivery",
                "deliverable": "Backlog triage report, duplicate clusters, labels recommendation, and top 10 fixes.",
                "due_hours": 48,
                "evidence": ["fixture: public GitHub triage service"],
                "agent_doable_steps": ["read issues", "cluster duplicates", "rank fixes", "write report"],
                "tags": ["code_delivery", "github"],
            },
            {
                "id": "synthetic-hyrve-no-demand",
                "source": "hyrve_fixture",
                "buyer_name": "Unclear task poster",
                "org": "Unknown",
                "title": "Vague AI automation help needed",
                "description": "Task asks for AI help but gives no concrete buyer pain, budget, or deliverable.",
                "pain_signals": [],
                "budget_usd": 0,
                "payment_clarity": "unclear",
                "distribution_access": "marketplace listing but proof burden high",
                "service_fit": "Unknown",
                "deliverable": "",
                "due_hours": 168,
                "evidence": ["fixture: no-demand marketplace noise"],
                "agent_doable_steps": ["needs clarification"],
                "tags": ["hyrve", "no_demand"],
            },
            {
                "id": "synthetic-legal-risk",
                "source": "blocked_fixture",
                "buyer_name": "Small landlord",
                "title": "Draft legal eviction advice letters",
                "description": "Client requests legal advice and letters without attorney review.",
                "pain_signals": ["legal dispute"],
                "budget_usd": 500,
                "payment_clarity": "fixed fee",
                "distribution_access": "requires regulated legal advice",
                "service_fit": "Legal advice",
                "deliverable": "Legal letters",
                "due_hours": 24,
                "risk_signals": ["legal advice"],
                "agent_doable_steps": ["blocked"],
                "tags": ["blocked"],
            },
            {
                "id": "synthetic-credentials-risk",
                "source": "blocked_fixture",
                "buyer_name": "Unknown ecommerce operator",
                "title": "Log into vendor portals and change pricing",
                "description": "Requires credentials and autonomous edits in vendor accounts.",
                "pain_signals": ["manual price updates"],
                "budget_usd": 900,
                "payment_clarity": "paid after account changes",
                "distribution_access": "requires credentials",
                "service_fit": "Operations automation",
                "deliverable": "Changed pricing in live portals",
                "due_hours": 24,
                "risk_signals": ["requires credentials", "live account changes"],
                "agent_doable_steps": ["blocked"],
                "tags": ["blocked"],
            },
            {
                "id": "synthetic-trading-risk",
                "source": "blocked_fixture",
                "buyer_name": "Anon trading group",
                "title": "Guaranteed crypto trading bot returns",
                "description": "Build a bot that guarantees trading returns and accepts wallet actions automatically.",
                "pain_signals": ["wants guaranteed returns"],
                "budget_usd": 3000,
                "payment_clarity": "crypto wallet after launch",
                "distribution_access": "requires credentials and autonomous wallet actions",
                "service_fit": "Trading / Research Support",
                "deliverable": "Live trading bot",
                "due_hours": 24,
                "risk_signals": ["regulated advice", "guaranteed revenue", "wallet transfer"],
                "agent_doable_steps": ["blocked"],
                "tags": ["blocked"],
            },
            {
                "id": "synthetic-bulk-outreach-risk",
                "source": "blocked_fixture",
                "buyer_name": "Growth hacker",
                "title": "Scrape emails and auto-send 5,000 cold pitches",
                "description": "Scrape private directories, bypass captcha, and send cold email without approval.",
                "pain_signals": ["wants bulk outreach"],
                "budget_usd": 800,
                "payment_clarity": "paid if replies arrive",
                "distribution_access": "spam path",
                "service_fit": "Lead generation",
                "deliverable": "Bulk campaign",
                "due_hours": 24,
                "risk_signals": ["bulk email", "bypass captcha", "send without approval"],
                "agent_doable_steps": ["blocked"],
                "tags": ["blocked"],
            },
        ]
        return [
            self._opportunity_from_mapping(row, fallback_id=str(row["id"]))
            for row in rows
        ]

    def _dedupe_opportunities(self, opportunities: list[CashOpportunity]) -> list[CashOpportunity]:
        seen: set[str] = set()
        deduped: list[CashOpportunity] = []
        for opp in opportunities:
            key = "|".join(
                [
                    opp.source.strip().lower(),
                    opp.source_url.strip().lower(),
                    opp.buyer_name.strip().lower(),
                    opp.title.strip().lower(),
                ]
            )
            if key in seen:
                continue
            seen.add(key)
            if not opp.id:
                opp.id = _slug(key)
            deduped.append(opp)
        return deduped

    def _opportunity_preselect_score(self, opp: CashOpportunity) -> int:
        risk_flags = self._risk_flags(opp)
        has_cash = (opp.budget_usd or opp.estimated_value_usd) > 0
        has_named_buyer = bool(opp.buyer_name or opp.org)
        has_source = bool(opp.source_url or opp.evidence)
        has_delivery = bool(opp.deliverable or opp.service_fit)
        value = min(5000.0, opp.budget_usd or opp.estimated_value_usd or 0.0)
        score = 0
        score += 1000 if not risk_flags else -200 * len(risk_flags)
        score += 200 if has_cash else 0
        score += 150 if has_source else 0
        score += 125 if has_named_buyer else 0
        score += 100 if has_delivery else 0
        score += 75 if not self._is_fixture_opportunity(opp) else -150
        score += 50 if "github_bounty_live_intake" in opp.source else 0
        score += 25 if opp.due_hours <= 72 else 0
        score += int(value // 25)
        return score

    def _build_packet(self, opp: CashOpportunity, rank: int, cycle_id: str) -> CashActionPacket:
        risk_flags = self._risk_flags(opp)
        breakdown = self._score_breakdown(opp, risk_flags)
        score = int(round(sum((breakdown[key] * weight) / 100 for key, weight in WEIGHTS.items())))
        if risk_flags:
            score = min(score, 45)
        action_id = f"{cycle_id}-{rank:02d}-{_slug(opp.title, limit=34)}"
        approval_ready = (
            not risk_flags
            and not self._is_fixture_opportunity(opp)
            and score >= 75
            and self._has_minimum_evidence(opp)
        )
        verdict = DECISION_KILL if risk_flags else (DECISION_PASS if approval_ready else DECISION_HOLD)
        proposed_price = opp.budget_usd or opp.estimated_value_usd or self._fallback_price(opp)
        deliverable = opp.deliverable or self._default_deliverable(opp)
        first_action = self._first_action(opp, approval_ready)
        return CashActionPacket(
            action_id=action_id,
            rank=rank,
            opportunity_id=opp.id,
            score=score,
            score_breakdown=breakdown,
            verdict=verdict,
            approval_packet_ready=approval_ready,
            source=opp.source,
            source_url=opp.source_url,
            buyer_name=opp.buyer_name,
            org=opp.org,
            title=opp.title,
            estimated_value_usd=opp.estimated_value_usd or opp.budget_usd,
            service_fit=opp.service_fit or "custom cash sprint",
            proposed_price_usd=proposed_price,
            proposed_deliverable=deliverable,
            first_action=first_action,
            draft_message=self._draft_message(opp, proposed_price, deliverable),
            acceptance_criteria=self._acceptance_criteria(opp, deliverable),
            risk_flags=risk_flags,
        )

    def _score_breakdown(self, opp: CashOpportunity, risk_flags: list[str]) -> dict[str, int]:
        has_budget = (opp.budget_usd or opp.estimated_value_usd) > 0
        has_receipt = bool(opp.source_url or opp.evidence)
        due = opp.due_hours
        cash_speed = 95 if has_budget and due <= 48 else 85 if has_budget and due <= 72 else 65 if has_budget else 35
        fit_text = " ".join([opp.service_fit, opp.title, opp.description, *opp.tags]).lower()
        deliverable_keywords = (
            "audit",
            "x-ray",
            "lead",
            "enrichment",
            "internal tool",
            "dashboard",
            "agent",
            "sop",
            "research",
            "grant",
        )
        deliverability = 90 if any(k in fit_text for k in deliverable_keywords) else 55
        if opp.deliverable and opp.agent_doable_steps:
            deliverability = min(100, deliverability + 10)
        distribution_access = 90 if "spine" in opp.source or "inbound" in opp.source else 80 if opp.distribution_access else 55
        payment_clarity = 95 if has_budget and "fixed" in opp.payment_clarity.lower() else 80 if has_budget else 40
        risk_cleanliness = 100 if not risk_flags else 0
        agent_leverage = min(100, 45 + len(opp.agent_doable_steps) * 12 + len(opp.pain_signals) * 5)
        receipt_quality = 90 if has_receipt else 45
        return {
            "cash_speed": cash_speed,
            "deliverability": deliverability,
            "distribution_access": distribution_access,
            "payment_clarity": payment_clarity,
            "risk_cleanliness": risk_cleanliness,
            "agent_leverage": agent_leverage,
            "receipt_quality": receipt_quality,
        }

    def _risk_flags(self, opp: CashOpportunity) -> list[str]:
        text = " ".join(
            [
                opp.title,
                opp.description,
                opp.payment_clarity,
                opp.distribution_access,
                *opp.risk_signals,
                *opp.tags,
            ]
        ).lower()
        checks: list[tuple[str, tuple[str, ...]]] = [
            ("regulated_advice", ("trading", "investment advice", "medical advice", "legal advice", "tax advice")),
            ("tos_conflict", ("bypass captcha", "fake review", "scrape private", "evade rate limit")),
            ("secret_or_pii", ("api key", "password", "ssn", "personal data", "credentials")),
            ("spam_or_bulk_outreach", ("bulk email", "cold email without", "5,000 cold", "scrape emails")),
            ("guaranteed_revenue", ("guaranteed revenue", "guaranteed returns", "guarantees trading")),
            ("requires_signup_or_credentials", ("sign up", "login required", "requires credentials", "give credentials")),
            ("payment_or_wallet_action", ("wallet transfer", "accept payment", "charge card", "send crypto", "crypto payment", "usdt", "payment gateway", "paypal sandbox", "payment flow")),
            ("autonomous_send_requested", ("send without approval", "auto-send", "submit bid automatically", "accept job automatically")),
            ("auth_or_sensitive_security", ("biometric", "biometrics", "pin", "password", "authentication")),
            ("ai_disallowed_or_human_only", ("100% human", "human contributions", "human-only", "no ai", "no llm")),
            (
                "security_or_bug_bounty",
                (
                    "bug bounty",
                    "bug-bounty",
                    "bug hunter",
                    "find a real bug",
                    "security bug",
                    "vulnerability",
                    "vulnerabilities",
                    "exploit",
                    "pentest",
                    "penetration test",
                    "sql injection",
                    "xss",
                    "cve",
                ),
            ),
            (
                "non_cash_or_token_reward",
                (
                    " rtc",
                    "token reward",
                    "reward token",
                    "non-cash",
                    "non cash",
                    "achievement",
                    "badge reward",
                    "points reward",
                ),
            ),
        ]
        flags = [flag for flag, needles in checks if any(needle in text for needle in needles)]
        upstream_flags = [flag for flag in opp.risk_signals if flag in HARD_RISK_FLAGS]
        return [flag for flag in HARD_RISK_FLAGS if flag in {*flags, *upstream_flags}]

    def _has_minimum_evidence(self, opp: CashOpportunity) -> bool:
        return bool(
            (opp.buyer_name or opp.org)
            and opp.pain_signals
            and (opp.budget_usd or opp.estimated_value_usd)
            and (opp.source_url or opp.evidence or opp.source)
            and (opp.deliverable or opp.service_fit)
        )

    def _is_fixture_opportunity(self, opp: CashOpportunity) -> bool:
        text = " ".join([opp.source, *opp.evidence, *opp.tags]).lower()
        generated_markers = (
            "fixture",
            "dogfood",
            "local generated",
            "generated proof signal",
            "artifact://cashclaw-dogfood",
            "live_intake_local_fixture",
            "market_pattern",
            "requires_named_buyer_proof",
        )
        return any(marker in text for marker in generated_markers)

    def _fallback_price(self, opp: CashOpportunity) -> float:
        text = f"{opp.title} {opp.service_fit}".lower()
        if "lead" in text or "grant" in text:
            return 500.0
        if "agent" in text:
            return 1000.0
        if "code" in text or "dashboard" in text or "governance" in text:
            return 1500.0
        return 750.0

    def _default_deliverable(self, opp: CashOpportunity) -> str:
        return f"Scoped {opp.service_fit or 'cash sprint'} deliverable with source receipts and handoff notes."

    def _first_action(self, opp: CashOpportunity, approval_ready: bool) -> str:
        if not approval_ready:
            return "Do not send. Refine evidence or reject before any external action."
        return "Human reviews packet, edits draft, then explicitly approves any outreach or marketplace response."

    def _draft_message(self, opp: CashOpportunity, price: float, deliverable: str) -> str:
        buyer = opp.buyer_name or opp.org or "there"
        pain = "; ".join(opp.pain_signals[:3]) or "the workflow you described"
        return (
            f"Hi {buyer},\n\n"
            f"I can help with {opp.title}. The main signals I see are: {pain}.\n\n"
            f"Proposed fixed-scope deliverable: {deliverable}\n\n"
            f"Proposed price: ${price:,.0f}, pending scope confirmation. "
            "I would send source-backed receipts and a concise delivery packet.\n\n"
            "This is a draft only and requires human approval before sending."
        )

    def _acceptance_criteria(self, opp: CashOpportunity, deliverable: str) -> list[str]:
        criteria = [
            "Human-approved scope and recipient/channel before any external action.",
            f"Deliverable produced: {deliverable}",
            "Source receipts included for every material claim.",
            "Operator can verify outcome from local artifacts before submission.",
        ]
        if opp.budget_usd or opp.estimated_value_usd:
            criteria.append(f"Payment target documented: ${opp.budget_usd or opp.estimated_value_usd:,.0f}.")
        return criteria

    def _write_gauntlet_candidate(self, packet: CashActionPacket) -> Path:
        candidate_dir = _resolve_under(self._gauntlet_root, _safe_path_segment(packet.action_id, "action_id"))
        candidate_dir.mkdir(parents=True, exist_ok=True)
        human_packet = self._human_packet_markdown(packet)
        (candidate_dir / "human_packet.md").write_text(human_packet, encoding="utf-8")
        delivery_plan = self._delivery_plan_markdown(packet)
        (candidate_dir / "delivery_plan.md").write_text(delivery_plan, encoding="utf-8")
        lease_request = self._operator_revenue_lease_request_markdown(packet)
        (candidate_dir / "operator_revenue_lease_request.md").write_text(lease_request, encoding="utf-8")
        evidence = self._gate_evidence(packet)
        (candidate_dir / "gate_evidence.json").write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return candidate_dir

    def _gate_evidence(self, packet: CashActionPacket) -> dict[str, Any]:
        has_budget = packet.proposed_price_usd > 0 or packet.estimated_value_usd > 0
        has_channel = bool(packet.source_url or (packet.source and "fixture" not in packet.source.lower()))
        has_delivery = bool(packet.service_fit and packet.proposed_deliverable)
        risk_clean = not packet.risk_flags

        def gate(passed: bool, message: str) -> dict[str, Any]:
            return {
                "status": "pass" if passed else "hold",
                "evidence_grade": "B" if passed else "C",
                "evidence_refs": ["human_packet.md", "delivery_plan.md", "operator_revenue_lease_request.md"],
                "notes": message,
            }

        scorecard = {
            "buyer_pain_specificity": 5 if packet.buyer_name and packet.title else 3,
            "budget_wtp_signal": 5 if has_budget else 2,
            "channel_access": 5 if has_channel else 2,
            "delivery_fit": 5 if has_delivery else 2,
            "differentiation": 4,
            "receipt_path_clarity": 5 if packet.source_url or packet.source else 3,
            "vision_telos_fit": 4,
            "risk_cleanliness": 5 if risk_clean else 0,
        }
        recommendation = "kill" if packet.risk_flags else "pass" if packet.verdict == DECISION_PASS else "hold"
        return {
            "candidate_id": packet.action_id,
            "title": packet.title,
            "human_packet_ref": "human_packet.md",
            "gates": {
                "buyer_pain": gate(bool(packet.buyer_name or packet.org), "Buyer or organization is identified."),
                "budget_wtp": gate(has_budget, "Budget or proposed fixed fee is present."),
                "channel": gate(has_channel, "Source/channel is documented."),
                "delivery_proof": gate(has_delivery, "Deliverable plan, deliverable, and service fit are explicit."),
                "risk_welfare": gate(risk_clean, "No hard risk flags detected."),
            },
            "scorecard": scorecard,
            "red_team": {
                "recommendation": recommendation,
                "notes": "Autopilot may draft only. Human approval is required before any send, bid, acceptance, or payment step.",
            },
        }

    def _human_packet_markdown(self, packet: CashActionPacket) -> str:
        risk = ", ".join(packet.risk_flags) if packet.risk_flags else "none"
        criteria = "\n".join(f"- {item}" for item in packet.acceptance_criteria)
        return (
            f"# {packet.title}\n\n"
            f"- Action ID: `{packet.action_id}`\n"
            f"- Source: {packet.source}\n"
            f"- Source URL: {packet.source_url or 'n/a'}\n"
            f"- Buyer: {packet.buyer_name or packet.org or 'unknown'}\n"
            f"- Score: {packet.score}\n"
            f"- Verdict: {packet.verdict}\n"
            f"- Approval required: {packet.approval_required}\n"
            f"- Status: {packet.status}\n"
            f"- No external side effects performed: {packet.no_external_side_effects}\n"
            f"- Risk flags: {risk}\n\n"
            "## Delivery Plan\n\n"
            "See `delivery_plan.md` for the local work-order scaffold. It is not permission to claim, comment, bid, submit, or collect payment.\n\n"
            "## Operator Revenue Lease\n\n"
            "See `operator_revenue_lease_request.md` for the exact bounded approval request. The file is draft-only and does not grant permission by existing.\n\n"
            "## Proposed Deliverable\n\n"
            f"{packet.proposed_deliverable}\n\n"
            "## First Action\n\n"
            f"{packet.first_action}\n\n"
            "## Acceptance Criteria\n\n"
            f"{criteria}\n\n"
            "## Draft Message\n\n"
            "```text\n"
            f"{packet.draft_message}\n"
            "```\n"
        )

    def _delivery_plan_markdown(self, packet: CashActionPacket) -> str:
        risk = ", ".join(packet.risk_flags) if packet.risk_flags else "none"
        criteria = "\n".join(f"- {item}" for item in packet.acceptance_criteria)
        return (
            f"# Delivery Plan: {packet.title}\n\n"
            "## Boundary\n\n"
            "- Status: draft-only local work order.\n"
            "- No external side effects performed.\n"
            "- Do not comment, claim, bid, submit a PR, send outreach, request payment, use credentials, or mutate an external system without an Operator Revenue Lease.\n\n"
            "## Source\n\n"
            f"- Source: {packet.source}\n"
            f"- Source URL: {packet.source_url or 'n/a'}\n"
            f"- Buyer/Org: {packet.buyer_name or packet.org or 'unknown'}\n"
            f"- Proposed price: ${packet.proposed_price_usd:,.0f}\n"
            f"- Risk flags: {risk}\n\n"
            "## Local Work Order\n\n"
            "1. Re-read the source issue/request and copy exact acceptance criteria into local notes.\n"
            "2. Inspect only public materials needed to estimate delivery; do not log in or claim the task.\n"
            "3. Build or outline the smallest verifiable local deliverable matching the request.\n"
            "4. Run local verification and record command outputs or screenshots in the artifact directory.\n"
            "5. Prepare a final submission draft for human review; leave it unsent and unsubmitted.\n\n"
            "## Deliverable\n\n"
            f"{packet.proposed_deliverable}\n\n"
            "## Acceptance Criteria\n\n"
            f"{criteria}\n\n"
            "## Handoff\n\n"
            "Human must approve scope, recipient/channel, repository action, and payment handling before any external action.\n"
        )

    def _operator_revenue_lease_request_markdown(self, packet: CashActionPacket) -> str:
        risk = ", ".join(packet.risk_flags) if packet.risk_flags else "none"
        lease_id = f"lease-{packet.action_id}"
        return (
            f"# Operator Revenue Lease Request: {packet.title}\n\n"
            "## Status\n\n"
            "- Status: draft_only_not_granted.\n"
            "- External side effects performed: none.\n"
            "- This file is not authority to contact, claim, bid, submit, mutate, request payment, or use credentials.\n\n"
            "## Requested Lease\n\n"
            f"- Lease ID: `{lease_id}`\n"
            f"- Action ID: `{packet.action_id}`\n"
            f"- Source: {packet.source}\n"
            f"- Source URL: {packet.source_url or 'n/a'}\n"
            f"- Buyer/Org: {packet.buyer_name or packet.org or 'unknown'}\n"
            f"- Proposed price: ${packet.proposed_price_usd:,.0f}\n"
            f"- Risk flags: {risk}\n\n"
            "## Requested External Actions\n\n"
            "1. Re-open the listed public source and verify the task is still open.\n"
            "2. Send or post one human-approved intent/scope message only on the listed source/channel.\n"
            "3. Build the local deliverable after scope confirmation.\n"
            "4. Submit the human-approved final deliverable only to the listed source/channel.\n"
            "5. Request payment only through the buyer's documented bounty or marketplace process after acceptance.\n\n"
            "## Hard Limits\n\n"
            "- No credentials, private accounts, private repositories, or non-public data.\n"
            "- No regulated, security-sensitive, financial, medical, legal, exploit, credential, biometric, or payment-rail work.\n"
            "- No spending money, creating accounts, signing agreements, changing payment details, or custodying funds.\n"
            "- No broader outreach, unrelated contacts, PR submissions, bids, claims, or payment requests outside this exact source/channel.\n\n"
            "## Approval Text\n\n"
            f"Operator must approve exactly: `APPROVE REVENUE LEASE {lease_id}`\n"
        )

    def _attach_employee_gateway_receipts(
        self,
        packet: CashActionPacket,
        candidate_dir: Path,
        cycle_id: str,
        job: dict[str, Any],
    ) -> CashClawEmployeeReceiptBundle:
        agent_uid = str(job.get("agent_uid") or "cashclaw_autopilot")
        bundle = build_employee_receipt_bundle(packet, cycle_id=cycle_id, agent_uid=agent_uid)
        gateway_path = candidate_dir / "gateway_decision.json"
        employee_path = candidate_dir / "employee_receipt.json"
        final_gateway = next(
            (
                decision
                for decision in bundle.gateway_decisions
                if decision.decision_id == bundle.final_gateway_decision_id
            ),
            bundle.gateway_decisions[-1],
        )
        write_gateway_receipt(gateway_path, final_gateway)
        write_employee_receipt_bundle(employee_path, bundle)
        packet.gateway_decision = bundle.final_gateway_decision
        packet.gateway_decision_id = bundle.final_gateway_decision_id
        packet.gateway_decision_reasons = list(bundle.final_gateway_reasons)
        packet.gateway_required_receipts = list(bundle.final_gateway_required_receipts)
        packet.gateway_decision_path = str(gateway_path)
        packet.employee_receipt_id = bundle.final_employee_receipt_id
        packet.employee_receipt_bundle_id = bundle.bundle_id
        packet.execution_receipt_id = bundle.final_execution_receipt_id
        packet.employee_receipt_path = str(employee_path)
        packet.employee_receipt_count = len(bundle.employee_receipts)
        packet.employee_roles_completed = list(bundle.roles_completed)
        return bundle

    def _persist_result(self, result: CashCycleResult) -> None:
        latest_json = self._state_dir / "latest_top10.json"
        latest_md = self._state_dir / "latest_top10.md"
        cycle_log = self._state_dir / "cycle_log.jsonl"
        approval_queue = self._report_dir / "approval_queue.md"
        result.latest_queue_path = str(latest_md)
        result.report_path = str(approval_queue)
        result.cycle_log_path = str(cycle_log)
        latest_json.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
        latest_md.write_text(self._queue_markdown(result), encoding="utf-8")
        approval_queue.write_text(self._queue_markdown(result), encoding="utf-8")
        with cycle_log.open("a", encoding="utf-8") as f:
            f.write(result.model_dump_json() + "\n")

    def _queue_markdown(self, result: CashCycleResult) -> str:
        rows = [
            "| Rank | Score | Source | Buyer | Value | Service Fit | Verdict | Gateway | Employees | Ready | Artifact |",
            "|---:|---:|---|---|---:|---|---|---|---:|---|---|",
        ]
        for packet in result.top10:
            buyer = packet.buyer_name or packet.org or "unknown"
            artifact = packet.artifact_dir or "pending"
            rows.append(
                "| "
                f"{packet.rank} | {packet.score} | {packet.source} | {buyer} | "
                f"${packet.proposed_price_usd:,.0f} | {packet.service_fit} | "
                f"{packet.verdict} | {packet.gateway_decision or 'pending'} | "
                f"{packet.employee_receipt_count} | {packet.approval_packet_ready} | `{artifact}` |"
            )
        urgent = "\n".join(
            f"- #{packet.rank} `{packet.action_id}` — {packet.title} (${packet.proposed_price_usd:,.0f})"
            for packet in result.top3_urgent
        ) or "- none"
        snippets = "\n\n".join(
            (
                f"## #{packet.rank} {packet.title}\n\n"
                f"- Action ID: `{packet.action_id}`\n"
                f"- First action: {packet.first_action}\n"
                f"- Risk flags: {', '.join(packet.risk_flags) if packet.risk_flags else 'none'}\n"
                f"- Gateway: {packet.gateway_decision or 'pending'} "
                f"({', '.join(packet.gateway_decision_reasons) if packet.gateway_decision_reasons else 'no reasons yet'})\n"
                f"- Employee receipt: `{packet.employee_receipt_path or 'pending'}`\n"
                f"- Draft status: `{packet.status}`\n"
            )
            for packet in result.top10
        )
        return (
            "# CashClaw Autopilot Approval Queue\n\n"
            f"- Cycle: `{result.cycle_id}`\n"
            f"- Timestamp: {result.timestamp}\n"
            f"- Mode: {result.mode}\n"
            f"- Opportunities scanned: {result.opportunities_scanned}\n"
            f"- Estimated cycle cost: ${result.estimated_cost_usd:.2f} / cap ${result.cost_cap_usd:.2f}\n"
            f"- Employee receipts: {result.employee_receipts_written} across {len(result.top10)} packets\n"
            f"- Gateway decisions: allow={result.gateway_allow_count}, review={result.gateway_review_count}, block={result.gateway_block_count}\n"
            f"- External network reads: {result.external_network_reads_performed}\n"
            f"- Clean cycle: {result.clean_cycle}\n"
            "- External side effects: none. No outreach, bid, job acceptance, submission, or payment action was performed.\n\n"
            "## Top 3 Urgent\n\n"
            f"{urgent}\n\n"
            "## Top 10\n\n"
            + "\n".join(rows)
            + "\n\n"
            "## Action Snippets\n\n"
            f"{snippets}\n"
        )


def cashclaw_autopilot_handler(job: dict[str, Any]) -> tuple[bool, str, str | None]:
    """Cron-compatible entry point for governed CashClaw cycles."""
    try:
        autopilot = CashClawAutopilot()
        result = autopilot.run_cycle(job)
        output = (
            f"CashClaw Autopilot Cycle — {result.timestamp}\n"
            f"  Cycle ID:              {result.cycle_id}\n"
            f"  Mode:                  {result.mode}\n"
            f"  Opportunities scanned: {result.opportunities_scanned}\n"
            f"  Top 10 packets:        {len(result.top10)}\n"
            f"  Approval-ready:        {sum(1 for packet in result.top10 if packet.approval_packet_ready)}\n"
            f"  Employee receipts:     {result.employee_receipts_written}\n"
            f"  Gateway decisions:     allow={result.gateway_allow_count} review={result.gateway_review_count} block={result.gateway_block_count}\n"
            f"  External side effects: none\n"
            f"  Queue:                 {result.latest_queue_path}\n"
            f"  Approval artifact:     {result.report_path}\n"
            f"  Cost estimate:         ${result.estimated_cost_usd:.2f}/${result.cost_cap_usd:.2f}\n"
        )
        if result.errors:
            output += f"  Errors:                {len(result.errors)}\n"
            for error in result.errors[:5]:
                output += f"    - {error}\n"
        return result.clean_cycle, output, "\n".join(result.errors) if result.errors else None
    except Exception as exc:  # noqa: BLE001
        error = f"CashClaw Autopilot failed: {exc}"
        logger.error(error, exc_info=True)
        return False, error, error
