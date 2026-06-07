#!/usr/bin/env python3
"""Write local CashClaw v3 presence-learning metrics and dossiers.

This is a report helper, not a control plane. It reads existing local receipts
from the v3 Hydra run root and writes summary artifacts. It performs no network
reads and no external mutations.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AGENT_PRESENCE_CONFIG_HINTS = (
    "cashclaw",
    "moltlaunch",
    "moltbotmarket",
    "workprotocol",
)

DOSSIER_NEEDLES = {
    "service_catalog": ("service", "skill", "catalog", "agent", "employee", "automation"),
    "pricing": ("price", "pricing", "$", "usd", "bounty", "paid"),
    "payment": ("payment", "stripe", "escrow", "usdc", "payout", "gets paid"),
    "identity": ("identity", "profile", "agent card", "leaderboard", "reputation"),
    "delivery": ("deliver", "artifact", "submission", "pull request", "receipt"),
    "guardrails": ("guard", "approval", "safe", "policy", "permission", "human"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args(argv)

    run_root = Path(args.run_root).expanduser().resolve()
    output_root = run_root / "v3_presence_digest"
    output_root.mkdir(parents=True, exist_ok=True)

    source_items = _load_presence_source_items(run_root)
    pattern_cards = _load_presence_pattern_cards(run_root)
    summaries = _read_json(run_root / "summaries.json", default=[])
    cash_memory = _read_json(run_root / "cash_memory.json", default={})
    lease_requests = _read_json(run_root / "operator_revenue_lease_requests.json", default={})

    metrics = build_metrics(
        source_items=source_items,
        pattern_cards=pattern_cards,
        summaries=summaries,
        cash_memory=cash_memory,
        lease_requests=lease_requests,
        run_root=run_root,
    )
    dossiers = build_dossiers(source_items)
    training_notes = build_training_notes(metrics=metrics, cash_memory=cash_memory)

    (output_root / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_root / "agent_presence_dossiers.md").write_text(dossiers_markdown(dossiers), encoding="utf-8")
    (output_root / "skill_mutation_training_notes.md").write_text(training_notes, encoding="utf-8")
    print(json.dumps({"status": "pass", "output_root": str(output_root), "metrics": metrics}, indent=2, sort_keys=True))
    return 0


def build_metrics(
    *,
    source_items: list[dict[str, Any]],
    pattern_cards: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    cash_memory: dict[str, Any],
    lease_requests: dict[str, Any],
    run_root: Path,
) -> dict[str, Any]:
    local_episodes = list(run_root.glob("local_executor/**/training/local_execution_episode.json"))
    sidecar_work_orders = list(run_root.glob("local_executor/**/sidecar_work_order.json"))
    external_side_effects = bool(lease_requests.get("external_side_effects_performed"))
    if any(summary.get("external_side_effects_performed") for summary in summaries if isinstance(summary, dict)):
        external_side_effects = True
    return {
        "schema_version": "cashclaw_v3_presence_digest.v1",
        "generated_at": utc_now_iso(),
        "run_root": str(run_root),
        "primary_cycles": len(summaries) if isinstance(summaries, list) else 0,
        "latest_primary_cycle_source_items": int((summaries[-1] or {}).get("source_items") or 0) if summaries else 0,
        "latest_primary_cycle_pattern_cards": int((summaries[-1] or {}).get("pattern_cards") or 0) if summaries else 0,
        "latest_primary_cycle_top_packets": int((summaries[-1] or {}).get("top10_packets") or 0) if summaries else 0,
        "latest_primary_cycle_ready_packets": len((summaries[-1] or {}).get("ready_packets") or []) if summaries else 0,
        "presence_source_items": len(source_items),
        "presence_pattern_cards": len(pattern_cards),
        "presence_source_types": dict(Counter(str(item.get("source_type") or "unknown") for item in source_items).most_common()),
        "presence_source_configs": dict(Counter(str(item.get("source_config_id") or "unknown") for item in source_items).most_common()),
        "unique_ready_opportunities": int(cash_memory.get("unique_ready_opportunities") or 0) if isinstance(cash_memory, dict) else 0,
        "total_ready_appearances": int(cash_memory.get("total_ready_appearances") or 0) if isinstance(cash_memory, dict) else 0,
        "lease_request_count": len(lease_requests.get("requests") or []) if isinstance(lease_requests, dict) else 0,
        "local_sidecar_work_orders": len(sidecar_work_orders),
        "local_execution_episodes": len(local_episodes),
        "external_side_effects_performed": external_side_effects,
    }


def build_dossiers(source_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dossiers: list[dict[str, Any]] = []
    for item in source_items:
        config_id = str(item.get("source_config_id") or "")
        if not any(hint in config_id.lower() for hint in AGENT_PRESENCE_CONFIG_HINTS):
            continue
        text = " ".join(
            str(item.get(key) or "")
            for key in ("title", "summary", "raw_excerpt", "author_or_org", "url")
        )
        lower = text.lower()
        signals = {
            category: [needle for needle in needles if needle in lower]
            for category, needles in DOSSIER_NEEDLES.items()
        }
        signals = {key: value for key, value in signals.items() if value}
        dossiers.append(
            {
                "title": item.get("title", ""),
                "source_config_id": config_id,
                "source_type": item.get("source_type", ""),
                "url": item.get("url", ""),
                "signals": signals,
                "excerpt": str(item.get("raw_excerpt") or item.get("summary") or "")[:700],
            }
        )
    return dossiers


def build_training_notes(*, metrics: dict[str, Any], cash_memory: dict[str, Any]) -> str:
    best_ready = cash_memory.get("best_ready") if isinstance(cash_memory, dict) else []
    rows: list[str] = []
    if isinstance(best_ready, list):
        for item in best_ready[:10]:
            gate = item.get("killshot_quality_gate") or {}
            reasons = ", ".join(gate.get("blocking_reasons") or []) or "none"
            rows.append(
                f"- {item.get('title', '')}: price=${float(item.get('price_usd') or 0):,.0f}; "
                f"appearances={item.get('appearances', 0)}; killshot={gate.get('status', 'not_run')}; "
                f"blocks={reasons}"
            )
    if not rows:
        rows.append("- No best-ready packets yet; keep scouting and avoid forcing local execution.")

    return (
        "# CashClaw v3 Skill Mutation Training Notes\n\n"
        f"- Generated: {metrics.get('generated_at', '')}\n"
        f"- Primary cycles: {metrics.get('primary_cycles', 0)}\n"
        f"- Presence source items: {metrics.get('presence_source_items', 0)}\n"
        f"- Unique ready opportunities: {metrics.get('unique_ready_opportunities', 0)}\n"
        f"- Lease requests: {metrics.get('lease_request_count', 0)}\n"
        f"- Local sidecar work orders: {metrics.get('local_sidecar_work_orders', 0)}\n"
        f"- Local execution episodes: {metrics.get('local_execution_episodes', 0)}\n"
        f"- External side effects performed: {metrics.get('external_side_effects_performed') is True}\n\n"
        "## Current Learning Rules\n\n"
        "- Keep public agent-presence pages as market-learning signals, not direct execution targets.\n"
        "- Prefer executable paid tasks from the opportunity feed for sidecars.\n"
        "- Expand `top_n` enough that high-price crowded tasks do not hide smaller clean tasks.\n"
        "- Pivot immediately when commercial readiness is blocked by claim pressure or open PR pileups.\n"
        "- Treat every local patch/test episode as training unless external submit is separately approved.\n\n"
        "## Best-Ready / Killshot Notes\n\n"
        + "\n".join(rows)
        + "\n"
    )


def dossiers_markdown(dossiers: list[dict[str, Any]]) -> str:
    if not dossiers:
        body = "- No public agent-presence dossiers found yet.\n"
    else:
        blocks = []
        for dossier in dossiers:
            signal_lines = []
            for category, needles in (dossier.get("signals") or {}).items():
                signal_lines.append(f"- {category}: {', '.join(needles)}")
            blocks.append(
                f"## {dossier.get('title') or dossier.get('source_config_id')}\n\n"
                f"- Source: {dossier.get('url', '')}\n"
                f"- Source config: `{dossier.get('source_config_id', '')}`\n"
                f"- Source type: `{dossier.get('source_type', '')}`\n\n"
                "### Signals\n\n"
                f"{chr(10).join(signal_lines) if signal_lines else '- none detected'}\n\n"
                "### Excerpt\n\n"
                f"{dossier.get('excerpt', '').strip() or 'n/a'}\n"
            )
        body = "\n\n".join(blocks) + "\n"
    return "# Public Agent-Presence Dossiers\n\n" + body


def _load_presence_source_items(run_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(run_root.glob("presence_scout/*/source_items.json")):
        payload = _read_json(path, default=[])
        if isinstance(payload, list):
            items.extend(item for item in payload if isinstance(item, dict))
    return items


def _load_presence_pattern_cards(run_root: Path) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for path in sorted(run_root.glob("presence_scout/*/pattern_cards.json")):
        payload = _read_json(path, default=[])
        if isinstance(payload, list):
            cards.extend(item for item in payload if isinstance(item, dict))
    return cards


def _read_json(path: Path, *, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
