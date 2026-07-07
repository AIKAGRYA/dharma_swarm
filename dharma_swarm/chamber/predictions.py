"""E3 — the micro-prediction lane: ingest emits forecasts; reality grades them.

Elevation spec E3: every ingest batch can emit resolvable micro-predictions
through the EXISTING ginko store (dharma_swarm/ginko_brier.py — no new truth
store), and resolution obeys the ORACLE RULE (chamber doctrine discipline
10): resolution evidence comes ONLY from fetcher-organ bronze receipts with
corroboration k>=2. A self-authored resolution is an incident, written to an
incident log and refused — never silently accepted.

The promotion back-pointer: every prediction's metadata carries the bronze
receipt hash that prompted it, so the forecast-driven memory-promotion feed
(facts whose presence improved Brier) can trace provenance end-to-end.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.ginko_brier import Prediction, record_prediction, resolve_prediction

EMITTER_SOURCE = "chamber.zeitgeist"
TRUSTED_FETCHER_PREFIXES = (
    "dharma_swarm.world_radar",   # bronze.py FETCHER_AGENT_ID lives here
    "tools.world_scout_go",
    "tools.world_signal_ingestor_go",
    "tools.github_ingestor_go",
    "tools.evidence_ingestor_go",
)
DEFAULT_INCIDENT_PATH = dharma_state_dir("DHARMA_HOME") / "chamber" / "incidents.jsonl"
REQUIRED_K = 2


class OracleRuleViolation(RuntimeError):
    """Resolution evidence failed the oracle rule (discipline 10)."""


def emit_micro_prediction(*, question: str, probability: float, resolve_by: str,
                          bronze_receipt_sha: str, category: str = "general",
                          resolution_criterion: str,
                          extra_metadata: dict[str, Any] | None = None) -> Prediction:
    """Record one resolvable micro-prediction against a bronze observation.

    The resolution criterion must be stated machine-checkably AT PREDICTION
    TIME (the G2 adversary rule: vague criteria auto-resolving true is the
    gaming vector); the bronze back-pointer makes the promotion feed
    traceable."""
    if not resolution_criterion.strip():
        raise ValueError("resolution_criterion is required at prediction time")
    if not bronze_receipt_sha.strip():
        raise ValueError("bronze_receipt_sha back-pointer is required")
    metadata = dict(extra_metadata or {})
    metadata.update({
        "emitter": EMITTER_SOURCE,
        "bronze_receipt_sha": bronze_receipt_sha,
        "resolution_criterion": resolution_criterion,
    })
    return record_prediction(
        question=question, probability=probability, resolve_by=resolve_by,
        category=category, source=EMITTER_SOURCE, metadata=metadata,
    )


def _agent_id(receipt: dict[str, Any]) -> str:
    """Defensive against present-but-null / non-dict nesting: a malformed
    bronze dict must produce a finding, never an AttributeError (which would
    bypass the incident log and fail OPEN — review R1-1/R3-N1)."""
    prov = receipt.get("prov") or {}
    agent = prov.get("agent") if isinstance(prov, dict) else None
    agent = agent or {}
    return str(agent.get("id", "")) if isinstance(agent, dict) else ""


def _evidence_findings(evidence: list[dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    if len(evidence) < REQUIRED_K:
        findings.append(f"corroboration k={len(evidence)} < required {REQUIRED_K}")
    urls: set[str] = set()
    for i, receipt in enumerate(evidence):
        if not isinstance(receipt, dict):
            findings.append(f"evidence {i}: not a receipt object (untrusted shape)")
            continue
        agent = _agent_id(receipt)
        if not agent:
            findings.append(f"evidence {i}: no prov.agent.id (untraceable)")
        elif not agent.startswith(TRUSTED_FETCHER_PREFIXES):
            findings.append(
                f"evidence {i}: prov.agent.id {agent!r} is not a fetcher "
                "organ — self-authored resolution is the mirror")
        corr = receipt.get("corroboration") or {}
        src = corr.get("independent_source_urls") if isinstance(corr, dict) else None
        if isinstance(src, str):  # a bare string would be iterated char-by-char
            findings.append(f"evidence {i}: independent_source_urls must be a list")
        elif isinstance(src, list):
            urls.update(str(u) for u in src)
    if len(evidence) >= REQUIRED_K and len(urls) < REQUIRED_K:
        findings.append(
            f"only {len(urls)} independent source url(s) across evidence — "
            f"corroboration requires {REQUIRED_K} independent sources")
    return findings


def _write_incident(prediction_id: str, findings: list[str],
                    incident_path: Path) -> None:
    incident_path.parent.mkdir(parents=True, exist_ok=True)
    with incident_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "schema": "chamber_oracle_incident.v1",
            "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "prediction_id": prediction_id,
            "findings": findings,
        }, sort_keys=True) + "\n")


def resolve_with_bronze(prediction_id: str, outcome: float,
                        evidence: list[dict[str, Any]], *,
                        incident_path: Path | None = None) -> Prediction | None:
    """Resolve a prediction ONLY on fetcher-organ bronze evidence (k>=2).

    Any violation: an incident line is appended and OracleRuleViolation is
    raised — the prediction stays unresolved rather than self-graded."""
    findings = _evidence_findings(evidence)
    if findings:
        _write_incident(prediction_id, findings,
                        incident_path or DEFAULT_INCIDENT_PATH)
        raise OracleRuleViolation(
            f"prediction {prediction_id}: {'; '.join(findings)}")
    return resolve_prediction(prediction_id, outcome)


__all__ = [
    "EMITTER_SOURCE",
    "OracleRuleViolation",
    "REQUIRED_K",
    "TRUSTED_FETCHER_PREFIXES",
    "emit_micro_prediction",
    "resolve_with_bronze",
]
