#!/usr/bin/env python3
"""Refresh the local AGNI watcher receipt with read-only remote evidence."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import shlex
import subprocess
from typing import Any, Mapping, Sequence


DEFAULT_STATE_ROOT = Path("~/.dharma").expanduser()
DEFAULT_TRADING_ROOT = "/root/trading_lab"
SCHEMA_VERSION = "dharma_remote_kaizen_agni_result.v1"
PACKET_SCHEMA_VERSION = "agni.kaizen_watcher.v1"
RECEIPT_KIND = "kaizen_agni"

CRITICAL_FEEDS: dict[str, int] = {
    "alpaca_1m": 1800,
    "congressional_trades": 3600,
    "crypto_history": 3600,
    "defi_overview": 3600,
    "defi_tvl": 3600,
    "etf_prices": 86400,
    "insider_trades": 3600,
    "oanda_forex": 1800,
    "sentiment": 3600,
    "yield_curve": 86400,
}

REMOTE_SNAPSHOT_CODE = r"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("/root/trading_lab")
now = time.time()

def iso(ts):
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()

def file_status(rel, max_age_s):
    path = BASE / rel
    if not path.exists():
        return {
            "path": rel,
            "exists": False,
            "fresh": False,
            "age_s": None,
            "max_age_s": max_age_s,
            "mtime_utc": "",
        }
    mtime = path.stat().st_mtime
    age = max(0, int(now - mtime))
    return {
        "path": rel,
        "exists": True,
        "fresh": age <= max_age_s,
        "age_s": age,
        "max_age_s": max_age_s,
        "mtime_utc": iso(mtime),
    }

def feed_status(name, threshold):
    rel = f"data/cache/{name}.json"
    path = BASE / rel
    out = file_status(rel, threshold)
    cached_at = None
    if path.exists():
        try:
            payload = json.loads(path.read_text())
            cached_at = payload.get("_cached_at")
        except Exception:
            cached_at = None
    if isinstance(cached_at, (int, float)):
        age = max(0, int(now - cached_at))
        out.update({
            "age_s": age,
            "fresh": age <= threshold,
            "cached_at": cached_at,
            "cached_at_utc": iso(cached_at),
        })
    out["status"] = "fresh" if out["fresh"] else "stale" if out["exists"] else "missing"
    out["threshold_s"] = threshold
    return out

critical = {
    "alpaca_1m": 1800,
    "congressional_trades": 3600,
    "crypto_history": 3600,
    "defi_overview": 3600,
    "defi_tvl": 3600,
    "etf_prices": 86400,
    "insider_trades": 3600,
    "oanda_forex": 1800,
    "sentiment": 3600,
    "yield_curve": 86400,
}

payload = {
    "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "files": {
        "data/dashboard_snapshot.json": file_status("data/dashboard_snapshot.json", 1800),
        "data/market_snapshot.json": file_status("data/market_snapshot.json", 600),
        "data/heartbeat": file_status("data/heartbeat", 300),
        "data/net_exposure.json": file_status("data/net_exposure.json", 300),
        "data/system/dharma_paper_sweep_latest.json": file_status(
            "data/system/dharma_paper_sweep_latest.json",
            86400,
        ),
    },
    "feed_freshness": {name: feed_status(name, threshold) for name, threshold in critical.items()},
}
print(json.dumps(payload, sort_keys=True))
"""


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: str
    exit_code: int
    stdout: str
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def receipt_timestamp(value: str) -> str:
    return (
        value.replace("-", "")
        .replace(":", "")
        .replace("+00:00", "Z")
        .replace(".000000", "")
        .replace("Z", "Z")
    )


def parse_json_stdout(result: CommandResult) -> Mapping[str, Any]:
    if not result.ok:
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _stale_files(snapshot: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    files = snapshot.get("files")
    if not isinstance(files, Mapping):
        return []
    stale: list[Mapping[str, Any]] = []
    for rel, raw in files.items():
        row = raw if isinstance(raw, Mapping) else {}
        if not row.get("fresh"):
            stale.append({"path": str(rel), **dict(row)})
    return stale


def _stale_feeds(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    feeds = snapshot.get("feed_freshness")
    if not isinstance(feeds, Mapping):
        return {}
    return {
        str(name): dict(row)
        for name, row in feeds.items()
        if isinstance(row, Mapping) and not row.get("fresh")
    }


def _cron_summary(cron: Mapping[str, Any]) -> dict[str, Any]:
    counts = cron.get("counts") if isinstance(cron.get("counts"), Mapping) else {}
    return {
        "timestamp": str(cron.get("timestamp") or ""),
        "window_days": int(cron.get("window_days") or 0),
        "total_crons": int(cron.get("total_crons") or 0),
        "counts": dict(counts),
        "red_stale_log": int(counts.get("RED_STALE_LOG") or 0),
        "unknown_no_log": int(counts.get("UNKNOWN_NO_LOG") or 0),
    }


def _killed_summary(killed: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": str(killed.get("timestamp") or ""),
        "killed_route_count": int(killed.get("killed_route_count") or 0),
        "routes_with_capital": int(killed.get("routes_with_capital") or 0),
        "routes_with_positions": int(killed.get("routes_with_positions") or 0),
        "total_open_positions": int(killed.get("total_open_positions") or 0),
        "total_positions_value_usd": float(killed.get("total_positions_value_usd") or 0.0),
        "total_cash_trapped_usd": float(killed.get("total_cash_trapped_usd") or 0.0),
    }


def build_watcher_payload(
    *,
    checked_at: str,
    ssh_alias: str,
    trading_root: str,
    snapshot: Mapping[str, Any],
    cron_audit: Mapping[str, Any],
    killed_routes: Mapping[str, Any],
    command_results: Sequence[CommandResult],
) -> dict[str, Any]:
    stale_files = _stale_files(snapshot)
    stale_feeds = _stale_feeds(snapshot)
    cron = _cron_summary(cron_audit)
    killed = _killed_summary(killed_routes)
    command_failures = [result for result in command_results if not result.ok]

    blockers: list[str] = []
    stale_file_paths = {str(row.get("path") or "") for row in stale_files}
    if "data/dashboard_snapshot.json" in stale_file_paths:
        blockers.append("Dashboard snapshot must be <=30 minutes old.")
    if "data/market_snapshot.json" in stale_file_paths:
        blockers.append("Market snapshot must be <=10 minutes old for route promotion.")
    if stale_feeds:
        blockers.append(
            f"{len(stale_feeds)} critical feed(s) are stale or missing: "
            + ", ".join(sorted(stale_feeds))
        )
    if cron["red_stale_log"] or cron["unknown_no_log"]:
        blockers.append(
            "Cron audit is not clean: "
            f"RED_STALE_LOG={cron['red_stale_log']}, UNKNOWN_NO_LOG={cron['unknown_no_log']}."
        )
    if killed["total_open_positions"] or killed["total_positions_value_usd"]:
        blockers.append("Killed-route audit reports open positions; capital review stays blocked.")
    if command_failures:
        blockers.append(
            "One or more read-only AGNI audit commands failed: "
            + ", ".join(result.name for result in command_failures)
        )
    blockers.append("Real-money permission remains blocked without explicit operator approval.")

    penalty = (
        18 * len(stale_files)
        + 4 * len(stale_feeds)
        + 5 * cron["red_stale_log"]
        + 5 * cron["unknown_no_log"]
        + 30 * int(bool(killed["total_open_positions"]))
        + 15 * len(command_failures)
    )
    health_score = max(0, min(100, 100 - penalty))
    readiness_score = 0 if blockers else 100
    ok = not command_failures

    packet = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "watcher": "KaizenOpsForShaktiGinko_AGNITradingLab",
        "generated_at": checked_at,
        "capital_status": "paper_only",
        "real_money_permission": "blocked",
        "live_order_authority": False,
        "exchange_key_mutation": False,
        "freshness": {
            "files": dict(snapshot.get("files") or {}),
            "feed_freshness": dict(snapshot.get("feed_freshness") or {}),
            "current_stale_feeds": stale_feeds,
            "stale_evidence": stale_files,
        },
        "cron_audit": cron,
        "killed_routes": killed,
        "blockers": blockers,
        "route_screen": {
            "candidate_use": "paper_review_only_not_capital_permission",
            "capital_eligible": False,
            "screen_rules": [
                "positive paper PnL",
                ">=30 trades for shadow candidate; >=100 trades preferred for micro-live review",
                "Sharpe >=1.0 before deeper validation",
                "no capital without OOS, fee/slippage stress, kill-switch proof, and model council review",
            ],
        },
        "remote_validation_generated_at": checked_at,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "checked_at": checked_at,
        "updated_at": checked_at,
        "node_id": "agni",
        "ssh_alias": ssh_alias,
        "trading_root": trading_root,
        "watcher": "KaizenOpsForShaktiGinko_AGNITradingLab",
        "status": "watching" if ok else "error",
        "ok": ok,
        "mode": "paper",
        "live_order_authority": False,
        "exchange_key_mutation": False,
        "real_money_permission": "blocked",
        "health_score": health_score,
        "readiness_score": readiness_score,
        "remote_writes": [],
        "packet": packet,
        "metadata": {
            "paper_only": True,
            "read_only_remote_commands": [
                {
                    "name": result.name,
                    "command": result.command,
                    "exit_code": result.exit_code,
                    "stderr": result.stderr[-1000:],
                }
                for result in command_results
            ],
        },
        "error": "; ".join(
            f"{result.name}: {result.stderr.strip() or 'exit ' + str(result.exit_code)}"
            for result in command_failures
        ),
    }


def remote_command_results(
    *,
    ssh_alias: str,
    trading_root: str,
    timeout: int,
) -> list[CommandResult]:
    commands = [
        (
            "snapshot_probe",
            f"python3 -c {shlex.quote(REMOTE_SNAPSHOT_CODE)}",
        ),
        (
            "cron_audit",
            "python3 scripts/cron_audit.py --json --days 2",
        ),
        (
            "killed_routes_audit",
            "python3 scripts/killed_routes_audit.py --json --positions",
        ),
    ]
    results: list[CommandResult] = []
    for name, remote_cmd in commands:
        command = f"cd {shlex.quote(trading_root)} && {remote_cmd}"
        completed = subprocess.run(
            ["ssh", ssh_alias, command],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        results.append(
            CommandResult(
                name=name,
                command=f"ssh {ssh_alias} {command}",
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        )
    return results


def write_watcher_outputs(
    payload: Mapping[str, Any],
    *,
    state_root: Path,
) -> tuple[Path, Path, Path]:
    root = state_root.expanduser() / "remote_nodes" / "agni"
    receipts = root / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    result_path = root / "kaizen_agni_latest.json"
    markdown_path = root / "kaizen_agni_latest.md"
    stamp = receipt_timestamp(str(payload.get("checked_at") or utc_now_iso()))
    receipt_path = receipts / f"agni-trading_{RECEIPT_KIND}-{stamp}.json"

    materialized = dict(payload)
    materialized["result_path"] = str(result_path)
    materialized["receipt_path"] = str(receipt_path)
    result_path.write_text(json.dumps(materialized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_path.write_text(json.dumps(materialized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(materialized), encoding="utf-8")
    return result_path, markdown_path, receipt_path


def render_markdown(payload: Mapping[str, Any]) -> str:
    packet = payload.get("packet") if isinstance(payload.get("packet"), Mapping) else {}
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    lines = [
        "# AGNI watcher refresh",
        "",
        f"- checked_at: {payload.get('checked_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- health_score: {payload.get('health_score', '')}",
        f"- readiness_score: {payload.get('readiness_score', '')}",
        f"- mode: {payload.get('mode', '')}",
        f"- real_money_permission: {payload.get('real_money_permission', '')}",
        f"- live_order_authority: {payload.get('live_order_authority', False)}",
        f"- remote_writes: {payload.get('remote_writes', [])}",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-alias", default="agni")
    parser.add_argument("--trading-root", default=DEFAULT_TRADING_ROOT)
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--no-write", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checked_at = utc_now_iso()
    results = remote_command_results(
        ssh_alias=args.ssh_alias,
        trading_root=args.trading_root,
        timeout=args.timeout,
    )
    snapshot = parse_json_stdout(results[0])
    cron = parse_json_stdout(results[1])
    killed = parse_json_stdout(results[2])
    payload = build_watcher_payload(
        checked_at=checked_at,
        ssh_alias=args.ssh_alias,
        trading_root=args.trading_root,
        snapshot=snapshot,
        cron_audit=cron,
        killed_routes=killed,
        command_results=results,
    )
    if not args.no_write:
        write_watcher_outputs(payload, state_root=Path(args.state_root))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
