"""Safe local execution loop for the Livelihood Loom CEO."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.venture_cell import ExternalActionKind, ExternalActionRequest, VentureCellRuntime
from dharma_swarm.venture_cell.livelihood_loom import load_livelihood_loom_contract
from dharma_swarm.venture_cell.livelihood_loom.adapters.enabler_csv_import import load_enabler_csv
from dharma_swarm.venture_cell.livelihood_loom.ceo_agent import (
    AGENT_ID,
    DEFAULT_DHARMA_HOME,
    DEFAULT_RECEIPT_DIR,
    REPO_ROOT,
    register_livelihood_loom_ceo_sync,
)
from dharma_swarm.venture_cell.livelihood_loom.ontology import EnablerCompany
from dharma_swarm.venture_cell.livelihood_loom.scoring import LivelihoodFitScore, score_enabler


DEFAULT_ENABLER_CSV = (
    Path.home() / "informal_economy_enabler_map" / "informal_economy_enablers_1000.csv"
)
DEFAULT_LANE_ROLES = (
    "loom_conductor",
    "field_cartography",
    "worker_advocate",
    "offer_builder",
    "evidence_auditor",
    "safety_red_team",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _receipt_id(now: datetime) -> str:
    return "lloom_bootstrap_" + now.strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class ScoredEnabler:
    rank: int
    company: EnablerCompany
    fit: LivelihoodFitScore

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "company": self.company.to_dict(),
            "score": self.fit.score,
            "blocked": self.fit.blocked,
            "reasons": list(self.fit.reasons),
        }


def _score_candidates(candidates: list[EnablerCompany]) -> list[ScoredEnabler]:
    scored = [
        (candidate, score_enabler(candidate))
        for candidate in candidates
    ]
    scored.sort(key=lambda item: (item[1].blocked, -item[1].score, item[0].name.lower()))
    return [
        ScoredEnabler(rank=index + 1, company=candidate, fit=fit)
        for index, (candidate, fit) in enumerate(scored)
    ]


def _capital_signal_payload(
    *,
    receipt_id: str,
    candidate_count: int,
    source_refs: list[str],
    now: datetime,
) -> dict[str, object]:
    return {
        "claim_id": f"claim_{receipt_id}",
        "cell_id": "livelihood_loom",
        "claim_type": "public_enabler_map_ready",
        "aggregate_count": candidate_count,
        "sector": "informal_economy_enablers",
        "region_level": "country_or_public_market",
        "evidence_refs": source_refs[:20],
        "audit_status": "internal_bootstrap_only",
        "outcome_metric": "public_enabler_candidates_loaded",
        "outcome_value": str(candidate_count),
        "time_period": now.strftime("%Y-%m"),
    }


def run_safe_bootstrap(
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    repo_root: Path | str = REPO_ROOT,
    agents_dir: Path | str | None = None,
    candidate_csv: Path | str | None = DEFAULT_ENABLER_CSV,
    candidate_limit: int | None = 1000,
    top_n: int = 25,
    receipt_dir: Path | str | None = None,
    external_action_log: Path | str | None = None,
    write_canonical_onboarding: bool = True,
    register_ceo: bool = True,
) -> dict[str, Any]:
    """Run the first local CEO cycle without external-world side effects."""
    home = Path(dharma_home).expanduser()
    repo = Path(repo_root)
    now = _utc_now()
    receipt_id = _receipt_id(now)
    receipt_root = Path(receipt_dir) if receipt_dir is not None else repo / DEFAULT_RECEIPT_DIR
    action_log = (
        Path(external_action_log)
        if external_action_log is not None
        else home / "venture_cells" / "livelihood_loom" / "external_actions.jsonl"
    )

    registration = None
    if register_ceo:
        registration = register_livelihood_loom_ceo_sync(
            dharma_home=home,
            repo_root=repo,
            agents_dir=agents_dir,
            write_canonical_onboarding=write_canonical_onboarding,
        )

    contract = load_livelihood_loom_contract()
    runtime = VentureCellRuntime(contract, action_log)
    mission = runtime.start_mission(
        mission_id=contract.mission_id,
        title="Livelihood Loom safe bootstrap",
        success_contract=[
            "CEO identity registered",
            "bounded internal lanes spawned",
            "public enabler candidates loaded or absence receipted",
            "top candidates scored without private data",
            "external action remains drafted only unless human approved",
        ],
    )
    for role in DEFAULT_LANE_ROLES:
        runtime.spawn_lane(
            mission.mission_id,
            role=role,
            depth=1,
            lane_id=f"lane_{role}",
        )

    csv_path = Path(candidate_csv).expanduser() if candidate_csv is not None else None
    candidates: list[EnablerCompany] = []
    candidate_source_status = "not_configured"
    if csv_path is not None:
        if csv_path.exists():
            candidates = load_enabler_csv(csv_path, limit=candidate_limit)
            candidate_source_status = "loaded"
        else:
            candidate_source_status = "missing"

    scored = _score_candidates(candidates)
    top = scored[:top_n]
    source_refs = sorted({
        ref
        for item in top
        for ref in item.company.source_refs
        if ref
    })

    external_action = None
    if len(candidates) >= 2:
        external_action = runtime.draft_external_action(
            ExternalActionRequest(
                cell_id=contract.cell_id,
                kind=ExternalActionKind.CAPITAL_SIGNAL,
                title="Draft non-extractive sponsor signal for informal economy enabler pilot",
                requested_by=AGENT_ID,
                payload=_capital_signal_payload(
                    receipt_id=receipt_id,
                    candidate_count=len(candidates),
                    source_refs=source_refs,
                    now=now,
                ),
                risk_notes=[
                    "Draft only; no sponsor contacted.",
                    "Uses aggregate public-source candidate count only.",
                    "Requires human_governor risk review and approval before action.",
                ],
                evidence_refs=source_refs[:20],
                idempotency_key=f"{contract.mission_id}:{receipt_id}:capital_signal",
            )
        )

    receipt = {
        "schema_version": "livelihood_loom.safe_bootstrap.v1",
        "receipt_id": receipt_id,
        "created_at": now.isoformat(),
        "agent_uid": AGENT_ID,
        "cell_id": contract.cell_id,
        "mission": mission.to_dict(),
        "registration": registration,
        "candidate_source": {
            "path": str(csv_path) if csv_path is not None else "",
            "status": candidate_source_status,
            "limit": candidate_limit,
            "loaded_count": len(candidates),
        },
        "scored_candidates": [item.to_dict() for item in top],
        "external_action": external_action.to_dict() if external_action else None,
        "external_action_log": str(action_log),
        "safety_boundary": {
            "external_action_mode": contract.external_action_policy.external_action_mode,
            "capital_boundary": contract.capital_boundary,
            "provider_calls_made": False,
            "external_contacts_made": False,
            "payments_made": False,
            "on_chain_transactions_made": False,
            "private_data_used": False,
        },
        "next_actions": [
            "Human reviews top scored candidates and removes any harmful target classes.",
            "CEO drafts 5 enablement packets from public information only.",
            "Evidence auditor verifies source refs before any partner claim.",
            "Human_governor decides whether a sponsor/cultivation signal may leave draft state.",
        ],
    }

    receipt_path = receipt_root / f"{receipt_id}.json"
    latest_path = receipt_root / "latest.json"
    sandbox_receipt = home / "external_agents" / AGENT_ID / "receipts" / f"{receipt_id}.json"
    _write_json(receipt_path, receipt)
    _write_json(latest_path, receipt)
    _write_json(sandbox_receipt, receipt)
    receipt["receipt_path"] = str(receipt_path)
    receipt["latest_path"] = str(latest_path)
    receipt["sandbox_receipt_path"] = str(sandbox_receipt)
    _write_json(receipt_path, receipt)
    _write_json(latest_path, receipt)
    _write_json(sandbox_receipt, receipt)
    return receipt


def bootstrap_summary(receipt: dict[str, Any]) -> dict[str, Any]:
    """Small stable summary for CLI output."""
    return {
        "receipt_id": receipt["receipt_id"],
        "agent_uid": receipt["agent_uid"],
        "cell_id": receipt["cell_id"],
        "mission_id": receipt["mission"]["mission_id"],
        "lane_count": len(receipt["mission"]["lanes"]),
        "candidate_count": receipt["candidate_source"]["loaded_count"],
        "scored_count": len(receipt["scored_candidates"]),
        "external_action_status": (
            receipt["external_action"]["status"] if receipt["external_action"] else "not_drafted"
        ),
        "receipt_path": receipt.get("receipt_path", ""),
        "sandbox_receipt_path": receipt.get("sandbox_receipt_path", ""),
    }


__all__ = [
    "DEFAULT_ENABLER_CSV",
    "DEFAULT_LANE_ROLES",
    "ScoredEnabler",
    "bootstrap_summary",
    "run_safe_bootstrap",
]
