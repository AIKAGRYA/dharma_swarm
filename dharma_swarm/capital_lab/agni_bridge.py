"""Read-only Agni evidence bridge for Dharma Capital.

V0 contract:
- Agni publishes evidence packets from stable local snapshots.
- Dharma Capital ingests packets into capital_lab evidence and Insight objects.
- The bridge never creates PortfolioTarget, RiskAdjustedTarget, Order, broker
  payloads, route mutations, or capital approvals.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from dharma_swarm.capital_lab.contracts import Direction, Insight, Universe


PACKET_SCHEMA_VERSION = "dharma.capital_lab.agni_bridge.v0.packet"
SIGNATURE_METHOD = "sha256_canonical_payload_v0"
EXPORTER_ID = "agni_snapshot_exporter_v0"
IMPORTER_ID = "dharma_capital_packet_importer_v0"
TREE = {
    "organ": "SHAKTI_GINKO",
    "allocator": "DHARMA_CAPITAL",
    "cell": "trading-lab",
    "lab": "agni",
    "route_layer": "routes",
}
STABLE_AGNI_FILES = (
    "agni_daily_reports.json",
    "agni_trading_timeline.json",
    "agni_alpha_full_summary.json",
)
AUTHORITY_BOUNDARY = {
    "read_only": True,
    "live_authority": False,
    "broker_write_authority": False,
    "capital_approval": False,
    "operator_approval_granted": False,
    "mutates_live_lab_state": False,
    "route_mutation_authority": False,
    "order_generation_authority": False,
}
SISTER_LAB_MISSING = "sister_labs_missing"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def sha256_json(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _packet_signature_basis(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in packet.items() if key != "signature"}


def sign_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    signed = dict(packet)
    signed["signature_method"] = SIGNATURE_METHOD
    signed["signature"] = sha256_json(_packet_signature_basis(signed))
    return signed


def validate_packet_signature(packet: Mapping[str, Any]) -> bool:
    if packet.get("signature_method") != SIGNATURE_METHOD:
        return False
    expected = sha256_json(_packet_signature_basis(packet))
    return packet.get("signature") == expected


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _data_dir(snapshot_root: Path) -> Path:
    root = Path(snapshot_root)
    if (root / "data").is_dir():
        return root / "data"
    return root


def _stable_file_paths(snapshot_root: Path) -> dict[str, Path]:
    data_dir = _data_dir(snapshot_root)
    paths = {name: data_dir / name for name in STABLE_AGNI_FILES}
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing stable Agni snapshot file(s): {', '.join(missing)}")
    return paths


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _sum(rows: Iterable[Mapping[str, Any]], key: str) -> float:
    return round(sum(_float(row.get(key)) for row in rows), 6)


def _sum_int(rows: Iterable[Mapping[str, Any]], key: str) -> int:
    return sum(_int(row.get(key)) for row in rows)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{value}T00:00:00+00:00")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _latest_datetime(values: Iterable[str | None]) -> str:
    parsed = [item for item in (_parse_dt(value) for value in values) if item is not None]
    if not parsed:
        return ""
    return max(parsed).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _age_days(latest: str, candidate: str) -> int | None:
    latest_dt = _parse_dt(latest)
    candidate_dt = _parse_dt(candidate)
    if latest_dt is None or candidate_dt is None:
        return None
    return max(0, (latest_dt.date() - candidate_dt.date()).days)


def _window(rows: Sequence[Mapping[str, Any]], days: int) -> Sequence[Mapping[str, Any]]:
    return rows[-days:] if len(rows) > days else rows


def _performance_summary(daily_reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    sorted_rows = sorted(daily_reports, key=lambda row: str(row.get("date", "")))
    latest = sorted_rows[-1] if sorted_rows else {}
    last_7 = _window(sorted_rows, 7)
    last_30 = _window(sorted_rows, 30)
    return {
        "first_date": str(sorted_rows[0].get("date", "")) if sorted_rows else "",
        "last_date": str(latest.get("date", "")),
        "days": len(sorted_rows),
        "latest_nav": _float(latest.get("nav")),
        "latest_routes": _int(latest.get("routes")),
        "total_pnl": _sum(sorted_rows, "day_pnl"),
        "pnl_7d": _sum(last_7, "day_pnl"),
        "pnl_30d": _sum(last_30, "day_pnl"),
        "trades": _sum_int(sorted_rows, "trades"),
        "wins": _sum_int(sorted_rows, "wins"),
        "losses": _sum_int(sorted_rows, "losses"),
        "vraj_applied": _sum_int(sorted_rows, "vraj_applied"),
        "vraj_proposed": _sum_int(sorted_rows, "vraj_proposed"),
    }


def _route_status(pnl: float, trades: int, rows: int, age_days: int | None) -> str:
    if trades <= 0 and rows <= 0:
        return "no_evidence"
    if age_days is not None and age_days > 14:
        return "stale"
    if pnl > 0:
        return "positive_pnl"
    if pnl < 0:
        return "negative_pnl"
    return "flat"


def _route_evidence(timeline: Mapping[str, Any]) -> list[dict[str, Any]]:
    route_summary = timeline.get("route_summary", {})
    if not isinstance(route_summary, Mapping):
        route_summary = {}
    route_rows = {
        str(row.get("route")): row
        for row in timeline.get("routes", [])
        if isinstance(row, Mapping) and row.get("route")
    }
    latest_activity = _latest_datetime(
        [row.get("timestamp") for row in timeline.get("system_equity", []) if isinstance(row, Mapping)]
        + [row.get("last_ts") for row in route_rows.values()]
    )
    route_ids = sorted(set(route_summary) | set(route_rows))
    evidence: list[dict[str, Any]] = []
    for route_id in route_ids:
        summary = route_summary.get(route_id, {})
        if not isinstance(summary, Mapping):
            summary = {}
        row = route_rows.get(route_id, {})
        pnl = _float(summary.get("pnl"), _float(row.get("last_value")) - _float(row.get("first_value")))
        trades = _int(summary.get("trades"))
        rows = _int(row.get("rows"))
        first_ts = str(row.get("first_ts") or summary.get("first_trade") or "")
        last_ts = str(row.get("last_ts") or summary.get("last_trade") or "")
        age = _age_days(latest_activity, last_ts)
        basis = {"route": route_id, "summary": summary, "timeline": row}
        evidence.append(
            {
                "route_id": route_id,
                "symbol": symbol_from_route(route_id),
                "first_ts": first_ts,
                "last_ts": last_ts,
                "age_days": age,
                "trades": trades,
                "rows": rows,
                "pnl": round(pnl, 6),
                "first_value": _float(row.get("first_value")),
                "last_value": _float(row.get("last_value")),
                "status": _route_status(pnl, trades, rows, age),
                "evidence_hash": sha256_json(basis),
            }
        )
    return evidence


def _status_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counters: dict[str, int] = {}
    for row in rows:
        for key, value in row.items():
            if ":" in str(key) or key in {
                "llm_failed",
                "no_regime_data",
                "no_sizeup_candidates",
                "placeholder",
                "observed",
                "proposed",
            }:
                counters[str(key)] = counters.get(str(key), 0) + _int(value)
    return dict(sorted(counters.items()))


def _stale_or_broken(timeline: Mapping[str, Any], alpha_summary: Mapping[str, Any]) -> dict[str, Any]:
    alerts = [row for row in timeline.get("alerts_daily", []) if isinstance(row, Mapping)]
    alpha_by_day = [row for row in alpha_summary.get("by_day", []) if isinstance(row, Mapping)]
    alpha_tail = alpha_by_day[-7:]
    stale_feeds: dict[str, int] = {}
    for alert in alerts:
        feeds = alert.get("feeds", {})
        if isinstance(feeds, Mapping):
            for feed, count in feeds.items():
                stale_feeds[str(feed)] = stale_feeds.get(str(feed), 0) + _int(count)
    alpha_counts = _status_counts(alpha_tail)
    broken = {
        "llm_failed": alpha_counts.get("llm_failed", 0),
        "no_regime_data": alpha_counts.get("no_regime_data", 0),
        "no_sizeup_candidates": alpha_counts.get("no_sizeup_candidates", 0),
        "placeholder": alpha_counts.get("placeholder", 0),
        "stale_feed_alerts": sum(stale_feeds.values()),
    }
    return {
        "alpha_rows": _int(alpha_summary.get("rows")),
        "latest_alpha_day": str(alpha_tail[-1].get("date", "")) if alpha_tail else "",
        "alpha_status_counts_7d": alpha_counts,
        "stale_feed_counts_7d": dict(sorted(stale_feeds.items())),
        "broken_counts_7d": broken,
        "is_clean": not any(value > 0 for value in broken.values()),
    }


def _source_snapshot(paths: Mapping[str, Path]) -> dict[str, Any]:
    return {
        "stable_files_only": True,
        "files": {
            name: {
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for name, path in sorted(paths.items())
        },
    }


def build_agni_packet(
    snapshot_root: str | Path,
    *,
    generated_at: str | None = None,
    lab_id: str = "agni",
    parent_lab_id: str = "trading-lab/agni",
    strategy_scope: str = "crypto_multi_route_vps_trading",
) -> dict[str, Any]:
    """Read stable Agni snapshot JSON files and build one signed packet."""
    generated_at = generated_at or utc_now()
    paths = _stable_file_paths(Path(snapshot_root))
    daily_reports = _load_json(paths["agni_daily_reports.json"])
    timeline = _load_json(paths["agni_trading_timeline.json"])
    alpha_summary = _load_json(paths["agni_alpha_full_summary.json"])
    if not isinstance(daily_reports, list):
        raise ValueError("agni_daily_reports.json must contain a list")
    if not isinstance(timeline, Mapping):
        raise ValueError("agni_trading_timeline.json must contain an object")
    if not isinstance(alpha_summary, Mapping):
        raise ValueError("agni_alpha_full_summary.json must contain an object")

    performance = _performance_summary([row for row in daily_reports if isinstance(row, Mapping)])
    route_evidence = _route_evidence(timeline)
    stale_or_broken = _stale_or_broken(timeline, alpha_summary)
    packet_id = "agni_pkt_" + sha256_json(
        {
            "generated_at": generated_at,
            "lab_id": lab_id,
            "source_snapshot": _source_snapshot(paths),
            "performance": performance,
            "route_count": len(route_evidence),
        }
    )[:24]
    packet = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "packet_id": packet_id,
        "generated_at": generated_at,
        "exporter_id": EXPORTER_ID,
        "lab_id": lab_id,
        "parent_lab_id": parent_lab_id,
        "strategy_scope": strategy_scope,
        "tree": {**TREE, "lab": lab_id},
        "custody": {
            "packet": "RECEIPT",
            "source_snapshot": "RECEIPT",
            "capital_mapping": "PROJECTION",
            "capital_authority": "EXTERNAL-GATED",
        },
        "authority": dict(AUTHORITY_BOUNDARY),
        "source_snapshot": _source_snapshot(paths),
        "performance": performance,
        "stale_or_broken": stale_or_broken,
        "route_evidence": route_evidence,
        "evidence_summary": {
            "routes_observed": len(route_evidence),
            "positive_routes": sum(1 for row in route_evidence if row["status"] == "positive_pnl"),
            "negative_routes": sum(1 for row in route_evidence if row["status"] == "negative_pnl"),
            "stale_routes": sum(1 for row in route_evidence if row["status"] == "stale"),
            "latest_activity_ts": _latest_datetime(
                [row.get("timestamp") for row in timeline.get("system_equity", []) if isinstance(row, Mapping)]
                + [row.get("last_ts") for row in timeline.get("routes", []) if isinstance(row, Mapping)]
            ),
        },
    }
    return sign_packet(packet)


def append_packet_jsonl(packet: Mapping[str, Any], jsonl_path: str | Path) -> Path:
    path = Path(jsonl_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(packet) + "\n")
    return path


def export_agni_packet(
    snapshot_root: str | Path,
    jsonl_path: str | Path,
    *,
    generated_at: str | None = None,
    lab_id: str = "agni",
    parent_lab_id: str = "trading-lab/agni",
    strategy_scope: str = "crypto_multi_route_vps_trading",
) -> dict[str, Any]:
    packet = build_agni_packet(
        snapshot_root,
        generated_at=generated_at,
        lab_id=lab_id,
        parent_lab_id=parent_lab_id,
        strategy_scope=strategy_scope,
    )
    append_packet_jsonl(packet, jsonl_path)
    return packet


def read_packet_jsonl(jsonl_path: str | Path) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    with Path(jsonl_path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL packet at line {line_number}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"packet at line {line_number} must be an object")
            packets.append(payload)
    return packets


def validate_agni_packet(packet: Mapping[str, Any]) -> None:
    if packet.get("schema_version") != PACKET_SCHEMA_VERSION:
        raise ValueError(f"unsupported packet schema: {packet.get('schema_version')}")
    if not validate_packet_signature(packet):
        raise ValueError(f"invalid packet signature: {packet.get('packet_id')}")
    authority = packet.get("authority")
    if authority != AUTHORITY_BOUNDARY:
        raise ValueError("authority boundary violation")
    if not isinstance(packet.get("route_evidence"), list):
        raise ValueError("packet route_evidence must be a list")
    if packet.get("tree", {}).get("organ") != "SHAKTI_GINKO":
        raise ValueError("packet is not under SHAKTI_GINKO")


@dataclass(frozen=True)
class CapitalLabEvidence:
    evidence_id: str
    lab_id: str
    packet_id: str
    generated_at: str
    custody_label: str
    source_signature: str
    performance: Mapping[str, Any]
    stale_or_broken: Mapping[str, Any]
    route_evidence_refs: tuple[Mapping[str, Any], ...]
    insights: tuple[Insight, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["insights"] = [insight.to_dict() for insight in self.insights]
        payload["route_evidence_refs"] = list(self.route_evidence_refs)
        return payload


@dataclass(frozen=True)
class LabComparison:
    status: str
    ranked_labs: tuple[str, ...]
    metrics_by_lab: Mapping[str, Mapping[str, Any]]
    orthogonality_status: str
    conclusion: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HumanReviewProposal:
    proposal_id: str
    title: str
    body: str
    reason: str
    arjuna_weight: float
    approval_state: str = "requires_human_review"
    auto_approved: bool = False
    capital_authority_change: bool = False
    route_mutation: bool = False
    order_generation: bool = False
    suggested_actions: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DharmaCapitalImportResult:
    universe: Universe
    evidence: tuple[CapitalLabEvidence, ...]
    comparison: LabComparison
    proposals: tuple[HumanReviewProposal, ...]
    authority: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "universe": self.universe.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
            "comparison": self.comparison.to_dict(),
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "authority": dict(self.authority),
        }


_SYMBOL_RE = re.compile(r"(?:^|_)(btc|eth|sol|avax|aapl|msft|nvda|tsla|eur|jpy|gbp|xau)(?:_|$)", re.I)


def symbol_from_route(route_id: str) -> str:
    match = _SYMBOL_RE.search(route_id)
    if match:
        return match.group(1).upper()
    return "AGNI_LAB"


def _direction_for_route(route: Mapping[str, Any]) -> Direction:
    status = str(route.get("status", ""))
    pnl = _float(route.get("pnl"))
    if status in {"stale", "no_evidence"}:
        return Direction.FLAT
    if pnl > 0:
        return Direction.UP
    if pnl < 0:
        return Direction.DOWN
    return Direction.FLAT


def _confidence_for_route(route: Mapping[str, Any], packet: Mapping[str, Any]) -> float:
    trades = _int(route.get("trades"))
    rows = _int(route.get("rows"))
    age = route.get("age_days")
    base = min(0.92, 0.2 + math.log10(max(1, trades + rows)) / 6.0)
    if isinstance(age, int) and age > 14:
        base *= 0.3
    stale_or_broken = packet.get("stale_or_broken", {})
    if isinstance(stale_or_broken, Mapping) and not stale_or_broken.get("is_clean", False):
        base *= 0.75
    return round(max(0.01, min(base, 0.99)), 4)


def _magnitude_for_route(route: Mapping[str, Any]) -> float:
    pnl = abs(_float(route.get("pnl")))
    trades = max(1, _int(route.get("trades")))
    return round(min(1.0, pnl / max(10.0, trades)), 4)


def _insights_from_packet(packet: Mapping[str, Any]) -> tuple[Insight, ...]:
    insights: list[Insight] = []
    for route in packet.get("route_evidence", []):
        if not isinstance(route, Mapping):
            continue
        insights.append(
            Insight(
                symbol=str(route.get("symbol") or symbol_from_route(str(route.get("route_id", "")))),
                direction=_direction_for_route(route),
                magnitude=_magnitude_for_route(route),
                confidence=_confidence_for_route(route, packet),
                horizon_days=7,
                source_agent=f"{IMPORTER_ID}:{packet.get('lab_id', 'unknown')}:{route.get('route_id', 'route')}",
                generated_at=str(packet.get("generated_at", utc_now())),
                knowledge_ts=str(packet.get("generated_at", "")),
            )
        )
    return tuple(insights)


def evidence_from_packet(packet: Mapping[str, Any]) -> CapitalLabEvidence:
    validate_agni_packet(packet)
    insights = _insights_from_packet(packet)
    refs = tuple(
        {
            "route_id": route.get("route_id"),
            "symbol": route.get("symbol"),
            "status": route.get("status"),
            "evidence_hash": route.get("evidence_hash"),
        }
        for route in packet.get("route_evidence", [])
        if isinstance(route, Mapping)
    )
    evidence_id = "cap_evd_" + sha256_json(
        {
            "packet_id": packet.get("packet_id"),
            "signature": packet.get("signature"),
            "importer": IMPORTER_ID,
        }
    )[:24]
    return CapitalLabEvidence(
        evidence_id=evidence_id,
        lab_id=str(packet["lab_id"]),
        packet_id=str(packet["packet_id"]),
        generated_at=str(packet["generated_at"]),
        custody_label="RECEIPT_BACKED_PROJECTION",
        source_signature=str(packet["signature"]),
        performance=dict(packet.get("performance", {})),
        stale_or_broken=dict(packet.get("stale_or_broken", {})),
        route_evidence_refs=refs,
        insights=insights,
    )


def compare_labs(packets: Sequence[Mapping[str, Any]]) -> LabComparison:
    metrics: dict[str, dict[str, Any]] = {}
    scopes: dict[str, str] = {}
    for packet in packets:
        validate_agni_packet(packet)
        lab_id = str(packet["lab_id"])
        performance = packet.get("performance", {})
        stale = packet.get("stale_or_broken", {})
        metrics[lab_id] = {
            "total_pnl": _float(performance.get("total_pnl") if isinstance(performance, Mapping) else 0),
            "pnl_30d": _float(performance.get("pnl_30d") if isinstance(performance, Mapping) else 0),
            "trades": _int(performance.get("trades") if isinstance(performance, Mapping) else 0),
            "routes_observed": _int(packet.get("evidence_summary", {}).get("routes_observed")),
            "stale_feed_alerts": _int(
                stale.get("broken_counts_7d", {}).get("stale_feed_alerts")
                if isinstance(stale, Mapping)
                else 0
            ),
        }
        scopes[lab_id] = str(packet.get("strategy_scope", "unknown"))
    ranked = tuple(
        lab_id
        for lab_id, _metric in sorted(
            metrics.items(), key=lambda item: (item[1]["pnl_30d"], item[1]["total_pnl"]), reverse=True
        )
    )
    if len(packets) < 2:
        status = SISTER_LAB_MISSING
        orthogonality = "unproven_without_sister_labs"
        conclusion = "Agni is ingested, but Dharma Capital cannot compare it until at least one sister-lab packet exists."
    elif len(set(scopes.values())) < len(scopes):
        status = "compared_with_clone_risk"
        orthogonality = "clone_risk"
        conclusion = "At least one sister lab shares Agni's strategy scope; require orthogonal evidence before portfolio judgment."
    else:
        status = "compared"
        orthogonality = "orthogonal_scope_claimed"
        conclusion = f"Ranked labs by evidence PnL. Current leader: {ranked[0] if ranked else 'none'}."
    return LabComparison(
        status=status,
        ranked_labs=ranked,
        metrics_by_lab=metrics,
        orthogonality_status=orthogonality,
        conclusion=conclusion,
    )


def _proposal_id(seed: Mapping[str, Any]) -> str:
    return "cap_prop_" + sha256_json(seed)[:20]


def proposals_for_import(
    packets: Sequence[Mapping[str, Any]],
    evidence: Sequence[CapitalLabEvidence],
    comparison: LabComparison,
) -> tuple[HumanReviewProposal, ...]:
    proposals: list[HumanReviewProposal] = []
    packets_by_lab = {str(packet.get("lab_id")): packet for packet in packets}
    agni_packet = packets_by_lab.get("agni", packets[0] if packets else {})
    stale = agni_packet.get("stale_or_broken", {}) if isinstance(agni_packet, Mapping) else {}
    broken_counts = stale.get("broken_counts_7d", {}) if isinstance(stale, Mapping) else {}

    proposals.append(
        HumanReviewProposal(
            proposal_id=_proposal_id({"kind": "boundary", "packets": [item.packet_id for item in evidence]}),
            title="Review Agni evidence under Dharma Capital without granting authority",
            body=(
                "Agni packets have been normalized into capital_lab evidence and Insight objects. "
                "This proposal is for human review only and carries no capital, route, or order authority."
            ),
            reason="receipt_backed_projection_ready",
            arjuna_weight=0.85,
            suggested_actions=(
                "Review packet signatures and route evidence hashes.",
                "Decide whether the evidence warrants a separate human-approved capital review.",
            ),
        )
    )
    if comparison.status == SISTER_LAB_MISSING:
        proposals.append(
            HumanReviewProposal(
                proposal_id=_proposal_id({"kind": "sister_lab", "status": comparison.status}),
                title="Request orthogonal sister-lab evidence before allocation comparison",
                body=(
                    "Dharma Capital needs at least one sister VPS/lab packet with a distinct strategy scope "
                    "before comparing Agni at portfolio level."
                ),
                reason="missing_sister_lab_packet",
                arjuna_weight=0.72,
                suggested_actions=(
                    "Export a read-only packet from rushabdev or another non-clone lab.",
                    "Reject Agni clone packets as comparison evidence unless strategy_scope differs.",
                ),
            )
        )
    if comparison.orthogonality_status == "clone_risk":
        proposals.append(
            HumanReviewProposal(
                proposal_id=_proposal_id({"kind": "clone_risk", "scopes": comparison.metrics_by_lab}),
                title="Hold portfolio comparison because sister lab looks cloned",
                body="A sister packet shares Agni's strategy scope. Treat comparison as AMBER until orthogonal evidence arrives.",
                reason="sister_lab_clone_risk",
                arjuna_weight=0.65,
                suggested_actions=("Require complementary route universe, exchange, data source, or strategy family.",),
            )
        )
    if any(_int(value) > 0 for value in broken_counts.values()):
        proposals.append(
            HumanReviewProposal(
                proposal_id=_proposal_id({"kind": "repair", "broken": broken_counts}),
                title="Repair stale or broken Agni evidence before capital escalation",
                body=(
                    "Agni evidence contains stale feed or broken alpha-cycle signals. This blocks any clean "
                    "capital escalation claim until fixed and re-exported."
                ),
                reason="stale_or_broken_evidence",
                arjuna_weight=0.8,
                suggested_actions=(
                    "Fix stale feeds and LLM failure lanes.",
                    "Re-run the exporter after repair and compare packet signatures.",
                ),
            )
        )
    return tuple(proposals)


def import_packets_to_dharma_capital(
    packets: Sequence[Mapping[str, Any]],
) -> DharmaCapitalImportResult:
    if not packets:
        raise ValueError("at least one Agni or sister-lab packet is required")
    evidence = tuple(evidence_from_packet(packet) for packet in packets)
    symbols = sorted({insight.symbol for item in evidence for insight in item.insights}) or ["AGNI_LAB"]
    universe = Universe(
        as_of=max(str(packet.get("generated_at", "")) for packet in packets),
        security_ids=tuple(symbols),
        source="dharma_capital_agni_bridge_v0",
    )
    comparison = compare_labs(packets)
    proposals = proposals_for_import(packets, evidence, comparison)
    return DharmaCapitalImportResult(
        universe=universe,
        evidence=evidence,
        comparison=comparison,
        proposals=proposals,
        authority=dict(AUTHORITY_BOUNDARY),
    )


def import_packet_jsonl_to_dharma_capital(jsonl_path: str | Path) -> DharmaCapitalImportResult:
    return import_packets_to_dharma_capital(read_packet_jsonl(jsonl_path))


def _export_cmd(args: argparse.Namespace) -> int:
    packet = export_agni_packet(
        args.snapshot_root,
        args.jsonl,
        generated_at=args.generated_at,
        lab_id=args.lab_id,
        parent_lab_id=args.parent_lab_id,
        strategy_scope=args.strategy_scope,
    )
    print(
        json.dumps(
            {
                "packet_id": packet["packet_id"],
                "jsonl": str(args.jsonl),
                "signature": packet["signature"],
                "routes_observed": packet["evidence_summary"]["routes_observed"],
                "authority": packet["authority"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _ingest_cmd(args: argparse.Namespace) -> int:
    result = import_packet_jsonl_to_dharma_capital(args.jsonl)
    payload = result.to_dict()
    if args.receipt_json:
        path = Path(args.receipt_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Agni to Dharma Capital bridge V0")
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="append one signed Agni packet to JSONL")
    export.add_argument("--snapshot-root", required=True)
    export.add_argument("--jsonl", required=True)
    export.add_argument("--generated-at", default=None)
    export.add_argument("--lab-id", default="agni")
    export.add_argument("--parent-lab-id", default="trading-lab/agni")
    export.add_argument("--strategy-scope", default="crypto_multi_route_vps_trading")
    export.set_defaults(func=_export_cmd)

    ingest = sub.add_parser("ingest", help="validate and import packet JSONL as Dharma Capital projections")
    ingest.add_argument("--jsonl", required=True)
    ingest.add_argument("--receipt-json", default="")
    ingest.set_defaults(func=_ingest_cmd)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
