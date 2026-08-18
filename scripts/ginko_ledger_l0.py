#!/usr/bin/env python3
"""L-0 forecast ledger — record, resolve, publish. No trading. No store_sync.

Named path: ginko_brier.record_prediction / resolve_prediction / build_dashboard.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

FORBIDDEN_HOSTS = {"meghadharma-cloud"}
ALLOWED_UNIVERSES = {
    "fred.cpi_mom_positive",
    "fred.dgs10_up",
    "crypto.btc_usd_up",
}
PUBLISH_REL = Path("reports/darshan/forecast_ledger")


def _utc() -> datetime:
    return datetime.now(timezone.utc)


def _die(msg: str, code: int = 2) -> None:
    print(f"GINKO_L0_REFUSED: {msg}", file=sys.stderr)
    raise SystemExit(code)


def refuse_host() -> None:
    if socket.gethostname() in FORBIDDEN_HOSTS:
        _die("forbidden host meghadharma-cloud")


def load_grant(path: Path) -> dict:
    data = json.loads(path.read_text())
    for k in ("grant_id", "granted_by", "expires_at", "kind"):
        if not str(data.get(k, "")).strip():
            _die(f"grant missing {k}")
    if data["kind"] != "PUBLISH":
        _die("L0 accepts PUBLISH grants only")
    exp = datetime.fromisoformat(str(data["expires_at"]).replace("Z", "+00:00"))
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp <= _utc():
        _die("grant expired")
    if data.get("consumed_at") and not data.get("allow_daily_after_consume"):
        # first row consumes start; later days may pass --resume
        pass
    universes = set(data.get("allowed_universes") or [])
    if universes != ALLOWED_UNIVERSES:
        _die(f"grant universes {sorted(universes)} != {sorted(ALLOWED_UNIVERSES)}")
    return data


def consume_start(path: Path, grant: dict) -> None:
    if grant.get("consumed_at"):
        return
    grant = dict(grant)
    grant["consumed_at"] = _utc().isoformat().replace("+00:00", "Z")
    path.write_text(json.dumps(grant, indent=2) + "\n")


def repo_root(start: Path) -> Path:
    cur = start.resolve()
    for _ in range(40):
        if (cur / "dharma_swarm" / "ginko_brier.py").is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    _die("repo root with ginko_brier.py not found")


def assert_no_forbidden_imports() -> None:
    # Belt: refuse if the process already imported the BR-007 path.
    banned = {
        "dharma_swarm.revenue.wedge_pipeline",
        "dharma_swarm.engine.store_sync",
    }
    hit = banned.intersection(sys.modules)
    if hit:
        _die(f"forbidden modules already imported: {sorted(hit)}")


async def snapshot(universe: str) -> dict:
    from dharma_swarm import ginko_data as gd

    if universe.startswith("fred."):
        series = "CPIAUCSL" if universe == "fred.cpi_mom_positive" else "DGS10"
        obs = await gd.fetch_fred_series(series)
        if obs is None:
            _die(f"FRED snapshot failed for {series} (key missing?)")
        return {"resolver": "fred", "series": series, "obs": obs}
    if universe == "crypto.btc_usd_up":
        prices = await gd.fetch_crypto_prices(["bitcoin"])
        if not prices:
            _die("CoinGecko snapshot failed")
        px = prices[0].current_price_usd
        return {"resolver": "coingecko", "symbol": "bitcoin", "obs": px}
    _die(f"unknown universe {universe}")


def make_question(universe: str, snap: dict, horizon_days: int) -> tuple[str, dict]:
    resolve_by = (_utc() + timedelta(days=horizon_days)).isoformat()
    meta = {"universe": universe, "resolver": snap["resolver"], "strike_snap": snap}
    if universe == "fred.cpi_mom_positive":
        q = "Will the next published CPIAUCSL monthly change be strictly greater than 0?"
    elif universe == "fred.dgs10_up":
        q = (
            f"Will FRED DGS10 next print strictly above the strike "
            f"recorded now ({snap['obs']!s})?"
        )
    else:
        q = (
            f"Will BTC-USD (CoinGecko) next 00:00 UTC close print strictly above "
            f"the strike recorded now ({snap['obs']!s})?"
        )
    return q, {**meta, "resolve_by": resolve_by}


def publish(repo: Path, dashboard: dict, rows: list[dict], grant_id: str) -> Path:
    day = _utc().strftime("%Y-%m-%d")
    dest = repo / PUBLISH_REL
    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "dharma.ginko.l0.v1",
        "date": day,
        "grant_id": grant_id,
        "host": socket.gethostname(),
        "dashboard": dashboard,
        "rows": rows,
        "note": "ledger receipt, not an edge receipt. misses included.",
    }
    path = dest / f"{day}.json"
    text = json.dumps(payload, indent=2, default=str) + "\n"
    path.write_text(text)
    public = dest / "predictions.public.jsonl"
    with public.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
    index = dest / "index.md"
    brier = dashboard.get("overall_brier")
    n = dashboard.get("resolved_count") or dashboard.get("n_resolved")
    index.write_text(
        f"# Forecast ledger (L0)\n\n"
        f"Last publish: {day}\n\n"
        f"Brier: {brier} · resolved: {n} · edge_validated: "
        f"{dashboard.get('edge_validated')}\n\n"
        f"Misses are included. This page is not a trading signal.\n"
    )
    # Optional OpenTimestamps; absence is AMBER, not a refusal.
    ots = shutil_which("ots")
    if ots:
        subprocess.run([ots, "stamp", str(path)], check=False)
    else:
        payload["timestamp_grade"] = "AMBER_git_self_asserted"
        path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return path


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def kill_hit(grant: dict, dashboard: dict) -> bool:
    consumed = grant.get("consumed_at")
    if not consumed:
        return False
    start = datetime.fromisoformat(str(consumed).replace("Z", "+00:00"))
    days = int(grant.get("kill_after_days") or 30)
    if _utc() < start + timedelta(days=days):
        return False
    brier = dashboard.get("overall_brier")
    n = int(dashboard.get("resolved_count") or dashboard.get("n_resolved") or 0)
    if n < 15:
        return True
    if brier is None or float(brier) >= 0.25:
        return True
    return False


async def main_async(args: argparse.Namespace) -> int:
    refuse_host()
    assert_no_forbidden_imports()
    grant_path = Path(args.grant).expanduser().resolve()
    grant = load_grant(grant_path)
    repo = repo_root(Path(args.repo_root) if args.repo_root else Path.cwd())
    sys.path.insert(0, str(repo))

    from dharma_swarm.ginko_brier import (
        build_dashboard,
        record_prediction,
    )

    dash_obj = build_dashboard()
    dash = dash_obj.__dict__ if hasattr(dash_obj, "__dict__") else dict(dash_obj)
    if kill_hit(grant, dash) and not args.resolve_only:
        _die("kill date hit — no new forecasts (resolve-only is still allowed)")

    consume_start(grant_path, grant)
    grant = json.loads(grant_path.read_text())

    rows: list[dict] = []
    if not args.resolve_only:
        import asyncio

        horizon = int(args.horizon_days)
        # Default probability 0.5 is honest ignorance — models plug in via --probability-json
        probs = {u: 0.5 for u in ALLOWED_UNIVERSES}
        if args.probability_json:
            probs.update(json.loads(Path(args.probability_json).read_text()))
        for universe in sorted(ALLOWED_UNIVERSES):
            p = float(probs[universe])
            if not 0.0 <= p <= 1.0:
                _die(f"bad probability for {universe}")
            snap = await snapshot(universe)
            question, meta = make_question(universe, snap, horizon)
            pred = record_prediction(
                question=question,
                probability=p,
                resolve_by=meta["resolve_by"],
                category=universe.split(".")[0],
                source=args.source,
                metadata=meta,
            )
            rows.append(asdict_pred(pred))

    dash_obj = build_dashboard()
    dash = dash_obj.__dict__ if hasattr(dash_obj, "__dict__") else dict(dash_obj)
    published = publish(repo, dash, rows, grant["grant_id"])
    receipt = {
        "schema": "dharma.ginko.l0.v1",
        "ts": _utc().isoformat().replace("+00:00", "Z"),
        "grant_id": grant["grant_id"],
        "host": socket.gethostname(),
        "published_path": str(published.relative_to(repo)),
        "n_new": len(rows),
        "store_sync_invoked": False,
        "valid": bool(published.exists() and (rows or args.resolve_only)),
        "note": "ledger receipt, not an edge receipt",
    }
    Path(args.receipt).expanduser().parent.mkdir(parents=True, exist_ok=True)
    Path(args.receipt).expanduser().write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    if not receipt["valid"]:
        _die("invalid receipt", 1)
    return 0


def asdict_pred(pred: object) -> dict:
    if hasattr(pred, "__dict__"):
        return dict(pred.__dict__)
    return json.loads(json.dumps(pred, default=str))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--grant", required=True)
    p.add_argument("--repo-root", default=None)
    p.add_argument("--source", default="uninformed-prior")
    p.add_argument("--horizon-days", default=7)
    p.add_argument("--probability-json", default=None)
    p.add_argument("--resolve-only", action="store_true")
    p.add_argument(
        "--receipt",
        default=str(Path.home() / ".dharma" / "ginko_l0" / "last_receipt.json"),
    )
    args = p.parse_args()
    import asyncio

    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
