#!/usr/bin/env python3
"""Stage or evaluate a CashClaw local executor sidecar."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--rank", type=int, default=1)
    parser.add_argument("--episode", default="")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    run_root = Path(args.run_root).expanduser().resolve()
    lease_requests = _read_json(run_root / "operator_revenue_lease_requests.json")
    requests = lease_requests.get("requests", [])
    if not isinstance(requests, list) or not requests:
        packet = build_idle_packet(run_root=run_root, rank=args.rank, lease_requests=lease_requests)
        if args.write:
            write_idle_packet(packet)
        else:
            print(json.dumps(packet, indent=2, sort_keys=True))
        return 0
    request = select_lease_request(lease_requests, rank=args.rank)
    episode = _read_json(Path(args.episode).expanduser().resolve()) if args.episode else None
    packet = build_sidecar_packet(run_root=run_root, request=request, episode=episode)
    if args.write:
        write_sidecar_packet(packet)
    else:
        print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


def select_lease_request(lease_requests: dict[str, Any], *, rank: int) -> dict[str, Any]:
    requests = lease_requests.get("requests", [])
    if not isinstance(requests, list) or not requests:
        raise ValueError("operator_revenue_lease_requests.json has no requests")
    for request in requests:
        if int(request.get("rank") or 0) == rank:
            return dict(request)
    raise ValueError(f"no lease request found for rank {rank}")


def build_sidecar_packet(
    *,
    run_root: Path,
    request: dict[str, Any],
    episode: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lease_stage = str(request.get("lease_stage") or "")
    if lease_stage != "local_delivery_only":
        raise ValueError(f"unsupported lease stage for local sidecar: {lease_stage}")
    if request.get("risk_flags"):
        raise ValueError("local sidecar refuses requests with risk_flags")

    action_id = str(request.get("action_id") or request.get("lease_id") or "unknown")
    sidecar_root = run_root / "local_executor" / _slug(action_id)
    training_root = sidecar_root / "training"
    gate = _build_killshot_quality_gate(episode) if episode else _build_killshot_quality_gate(None)
    return {
        "schema_version": "cashclaw_local_executor_sidecar.v1",
        "generated_at": utc_now_iso(),
        "run_root": str(run_root),
        "sidecar_root": str(sidecar_root),
        "training_root": str(training_root),
        "status": "staged",
        "lease_id": request.get("lease_id", ""),
        "action_id": action_id,
        "rank": request.get("rank"),
        "title": request.get("title", ""),
        "buyer": request.get("buyer", ""),
        "source_url": request.get("source_url", ""),
        "proposed_price_usd": request.get("proposed_price_usd", 0),
        "delivery_plan": request.get("delivery_plan", ""),
        "source_scope_snapshot": request.get("source_scope_snapshot", ""),
        "lease_preflight": request.get("lease_preflight", ""),
        "competition_probe": request.get("competition_probe", ""),
        "feasibility_probe": request.get("feasibility_probe", ""),
        "allowed_actions": [
            "Re-read public source and public repository contents.",
            "Clone or reuse a local public checkout under sidecar_root.",
            "Implement local patch, run local tests, and write local receipts.",
            "Write unsent PR/comment/submission packet for operator review.",
            "Write training/local_execution_episode.json and acceptance_matrix.json.",
            "Repeat locally until KillshotQualityGate passes or stop conditions block the target.",
        ],
        "forbidden_actions": [
            "Do not claim, comment, open PRs, submit bids, send outreach, or request payment.",
            "Do not use credentials, private accounts, private repositories, secrets, or non-public data.",
            "Do not perform live trading, live order placement, or payment-rail mutation.",
            "Do not treat this packet as approval for external_submit.",
        ],
        "required_outputs": [
            "local_executor_receipt.md",
            "unsent_pr_packet.md",
            "patch file",
            "training/local_execution_episode.json",
            "training/acceptance_matrix.json",
            "training/adversarial_review.md",
            "training/next_pass_recommendation.md",
        ],
        "killshot_quality_gate": gate,
        "next_node": gate.get("recommended_next_node", "LocalExecutorSidecar"),
        "external_side_effects_performed": False,
    }


def build_idle_packet(*, run_root: Path, rank: int, lease_requests: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "cashclaw_local_executor_sidecar_idle.v1",
        "generated_at": utc_now_iso(),
        "run_root": str(run_root),
        "status": "idle_no_ready_lease_requests",
        "rank_requested": rank,
        "lease_status": lease_requests.get("status", "missing"),
        "request_count": 0,
        "external_side_effects_performed": False,
        "next_node": "CashClawHydraScoutLoop",
        "message": "No draft local-delivery lease requests are ready; sidecar remains idle while Hydra continues scanning.",
    }


def write_idle_packet(packet: dict[str, Any]) -> None:
    idle_root = Path(str(packet["run_root"])) / "local_executor" / "_idle"
    idle_root.mkdir(parents=True, exist_ok=True)
    (idle_root / "sidecar_idle.json").write_text(
        json.dumps(packet, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (idle_root / "sidecar_idle.md").write_text(
        "# CashClaw Local Executor Sidecar Idle\n\n"
        f"- Generated: {packet.get('generated_at', '')}\n"
        f"- Status: `{packet.get('status', '')}`\n"
        f"- Requested rank: {packet.get('rank_requested')}\n"
        f"- Lease status: `{packet.get('lease_status', '')}`\n"
        f"- Request count: {packet.get('request_count')}\n"
        f"- Next node: `{packet.get('next_node', '')}`\n"
        f"- External side effects performed: false\n\n"
        f"{packet.get('message', '')}\n",
        encoding="utf-8",
    )


def write_sidecar_packet(packet: dict[str, Any]) -> None:
    sidecar_root = Path(str(packet["sidecar_root"]))
    training_root = Path(str(packet["training_root"]))
    training_root.mkdir(parents=True, exist_ok=True)
    (sidecar_root / "sidecar_work_order.json").write_text(
        json.dumps(packet, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (sidecar_root / "sidecar_work_order.md").write_text(sidecar_packet_markdown(packet), encoding="utf-8")
    (training_root / "killshot_quality_gate.json").write_text(
        json.dumps(packet.get("killshot_quality_gate", {}), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sidecar_packet_markdown(packet: dict[str, Any]) -> str:
    allowed = "\n".join(f"- {item}" for item in packet.get("allowed_actions", []))
    forbidden = "\n".join(f"- {item}" for item in packet.get("forbidden_actions", []))
    required = "\n".join(f"- {item}" for item in packet.get("required_outputs", []))
    gate = packet.get("killshot_quality_gate") or {}
    reasons = "\n".join(f"- {item}" for item in gate.get("blocking_reasons", [])) or "- none"
    return (
        "# CashClaw Local Executor Sidecar Work Order\n\n"
        f"- Generated: {packet.get('generated_at', '')}\n"
        f"- Status: `{packet.get('status', '')}`\n"
        f"- Lease ID: `{packet.get('lease_id', '')}`\n"
        f"- Action ID: `{packet.get('action_id', '')}`\n"
        f"- Title: {packet.get('title', '')}\n"
        f"- Buyer: {packet.get('buyer', '')}\n"
        f"- Source URL: {packet.get('source_url', '')}\n"
        f"- Sidecar root: `{packet.get('sidecar_root', '')}`\n"
        f"- Killshot gate: `{gate.get('status', 'not_run')}`\n"
        f"- Next node: `{packet.get('next_node', '')}`\n"
        f"- External side effects performed: false\n\n"
        "## Killshot Blocking Reasons\n\n"
        f"{reasons}\n\n"
        "## Allowed Actions\n\n"
        f"{allowed}\n\n"
        "## Forbidden Actions\n\n"
        f"{forbidden}\n\n"
        "## Required Outputs\n\n"
        f"{required}\n"
    )


def _build_killshot_quality_gate(episode: dict[str, Any] | None) -> dict[str, Any]:
    hydra_path = Path(__file__).resolve().with_name("cashclaw_revenue_hydra.py")
    spec = importlib.util.spec_from_file_location("cashclaw_revenue_hydra", hydra_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load cashclaw_revenue_hydra.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_killshot_quality_gate(episode)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:96] or "unknown"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
