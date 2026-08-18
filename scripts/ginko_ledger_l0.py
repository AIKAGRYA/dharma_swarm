#!/usr/bin/env python3
"""L-0 forecast ledger — record, resolve, publish. No trading. No store_sync.

Real edition (operator ratification 2026-08-18, yes-sheet line 7):
20+ model-generated forecasts per run, mechanical resolution, durable public
ledger. Named path: ginko_brier.record_prediction / resolve_prediction /
build_dashboard.

Invariants:
  - Probabilities come from an actual model call. There is no default, no
    hardcoded prior, and no probability file. If the model call fails, the
    run records NOTHING and exits nonzero (fail loud, never fake).
  - Resolution is mechanical: every question carries its resolution rule
    (source + series + comparator + threshold) in metadata at record time;
    the resolver replays that rule against a fresh fetch. Never judgment.
  - The public ledger (predictions.public.jsonl on generated/forecast-ledger)
    is the durable store of record. Each run rehydrates the local store from
    it, then republishes the full snapshot. Rows are never deleted (SATYA);
    resolution only fills in outcome fields.
  - Timestamp grade is AMBER (git self-asserted) unless an OpenTimestamps
    stamp actually succeeded, in which case the day file is GREEN. Never
    claim anchored when not.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from shutil import which
from typing import Any

FORBIDDEN_HOSTS = {"meghadharma-cloud"}

# Universe FAMILIES (grant surface). Individual questions live inside a
# family; the grant enumerates families, not per-question ids.
FRED_FAMILIES: dict[str, str] = {
    "fred.cpi": "CPIAUCSL",
    "fred.dgs10": "DGS10",
    "fred.icsa": "ICSA",
}
CRYPTO_FAMILIES: dict[str, str] = {
    "crypto.btc_usd": "bitcoin",
    "crypto.eth_usd": "ethereum",
}
ALLOWED_UNIVERSES = frozenset(FRED_FAMILIES) | frozenset(CRYPTO_FAMILIES)

MIN_QUESTIONS_PER_RUN = 20
DEFAULT_MODEL = os.environ.get("GINKO_L0_MODEL", "claude-opus-5")
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"

PUBLISH_REL = Path("reports/darshan/forecast_ledger")
PUBLIC_LEDGER_NAME = "predictions.public.jsonl"

GRADE_AMBER = "AMBER_git_self_asserted"
GRADE_GREEN = "GREEN_ots_stamped"

_BANNED_MODULES = frozenset(
    {
        "dharma_swarm.revenue.wedge_pipeline",
        "dharma_swarm.engine.store_sync",
    }
)


class GinkoModelError(RuntimeError):
    """The model call failed or returned unusable probabilities."""


@dataclass(frozen=True)
class Question:
    """One mechanically-resolvable yes/no question with a frozen strike."""

    qid: str
    universe: str
    text: str
    category: str
    horizon_days: int
    strike: float
    resolution: dict[str, Any] = field(hash=False)

    def resolve_by(self, now: datetime) -> str:
        return (now + timedelta(days=self.horizon_days)).isoformat()


def _utc() -> datetime:
    return datetime.now(timezone.utc)


def _die(msg: str, code: int = 2) -> None:
    print(f"GINKO_L0_REFUSED: {msg}", file=sys.stderr)
    raise SystemExit(code)


def refuse_host() -> None:
    if socket.gethostname() in FORBIDDEN_HOSTS:
        _die("forbidden host meghadharma-cloud")


def assert_no_forbidden_imports() -> None:
    """Belt: refuse if the process ever imported a BR-007 path."""
    hit = _BANNED_MODULES.intersection(sys.modules)
    if hit:
        _die(f"forbidden modules already imported: {sorted(hit)}")


def load_grant(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
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
    universes = set(data.get("allowed_universes") or [])
    if universes != set(ALLOWED_UNIVERSES):
        _die(
            f"grant universes {sorted(universes)} != {sorted(ALLOWED_UNIVERSES)}"
        )
    return data


def consume_start(path: Path, grant: dict[str, Any]) -> None:
    """One-shot: the first published row consumes the grant's start."""
    if grant.get("consumed_at"):
        return
    stamped = dict(grant)
    stamped["consumed_at"] = _utc().isoformat().replace("+00:00", "Z")
    path.write_text(json.dumps(stamped, indent=2) + "\n", encoding="utf-8")


def repo_root(start: Path) -> Path:
    cur = start.resolve()
    for _ in range(40):
        if (cur / "dharma_swarm" / "ginko_brier.py").is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    _die("repo root with ginko_brier.py not found")
    raise AssertionError("unreachable")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# QUESTION UNIVERSE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def fetch_snapshots() -> dict[str, float]:
    """Fetch one strike snapshot per family. Any miss refuses the run."""
    from dharma_swarm import ginko_data as gd

    snaps: dict[str, float] = {}
    for family, series in FRED_FAMILIES.items():
        obs = await gd.fetch_fred_series(series)
        if obs is None:
            _die(f"FRED snapshot failed for {series} (key missing?)")
        snaps[family] = float(obs)
    prices = await gd.fetch_crypto_prices(sorted(CRYPTO_FAMILIES.values()))
    by_id = {p.coin_id: float(p.current_price_usd) for p in prices}
    for family, coin in CRYPTO_FAMILIES.items():
        if coin not in by_id:
            _die(f"CoinGecko snapshot failed for {coin}")
        snaps[family] = by_id[coin]
    return snaps


def _fred_question(
    family: str,
    strike: float,
    threshold: float,
    comparator: str,
    horizon_days: int,
    label: str,
) -> Question:
    series = FRED_FAMILIES[family]
    direction = "strictly above" if comparator == "gt" else "strictly below"
    text = (
        f"Will the latest FRED {series} observation, read at the first ledger "
        f"run at or after the resolve-by time, print {direction} "
        f"{threshold:.4f}? (strike now: {strike:.4f})"
    )
    return Question(
        qid=f"{family}.{comparator}.{label}.h{horizon_days}",
        universe=family,
        text=text,
        category="macro",
        horizon_days=horizon_days,
        strike=strike,
        resolution={
            "source": "fred",
            "series": series,
            "comparator": comparator,
            "threshold": round(threshold, 6),
        },
    )


def _crypto_question(
    family: str, strike: float, multiplier: float, horizon_days: int
) -> Question:
    coin = CRYPTO_FAMILIES[family]
    threshold = round(strike * multiplier, 2)
    text = (
        f"Will {coin.upper()}-USD (CoinGecko spot), read at the first ledger "
        f"run at or after the resolve-by time, be strictly above "
        f"${threshold:,.2f}? (spot now: ${strike:,.2f})"
    )
    label = f"x{multiplier:.2f}".replace(".", "p")
    return Question(
        qid=f"{family}.gt.{label}.h{horizon_days}",
        universe=family,
        text=text,
        category="crypto",
        horizon_days=horizon_days,
        strike=strike,
        resolution={
            "source": "coingecko",
            "series": coin,
            "comparator": "gt",
            "threshold": threshold,
        },
    )


def build_universe(snaps: dict[str, float]) -> list[Question]:
    """26 mechanically-resolvable questions from frozen strikes.

    Families overlap Kalshi market categories (CPI prints, Treasury yield
    levels, weekly jobless claims, BTC/ETH thresholds at several horizons
    and strikes); no Kalshi contract IDs — overlap is incidental.
    """
    questions: list[Question] = []

    # CPI level: next monthly print vs current level (new print exists well
    # inside 45 days).
    cpi = snaps["fred.cpi"]
    questions.append(_fred_question("fred.cpi", cpi, cpi, "gt", 45, "strike"))

    # 10y Treasury yield: five strikes bracketing the current print, 7 days.
    dgs10 = snaps["fred.dgs10"]
    for offset in (-0.10, -0.05, 0.0, 0.05, 0.10):
        questions.append(
            _fred_question(
                "fred.dgs10",
                dgs10,
                dgs10 + offset,
                "gt",
                7,
                f"{offset:+.2f}".replace(".", "p"),
            )
        )

    # Weekly initial jobless claims: above strike, and below +5% band, 14 days.
    icsa = snaps["fred.icsa"]
    questions.append(_fred_question("fred.icsa", icsa, icsa, "gt", 14, "strike"))
    questions.append(
        _fred_question("fred.icsa", icsa, icsa * 1.05, "lt", 14, "band105")
    )

    # BTC/ETH: three horizons x three strikes each.
    for family in sorted(CRYPTO_FAMILIES):
        strike = snaps[family]
        for horizon in (1, 3, 7):
            for multiplier in (0.98, 1.00, 1.02):
                questions.append(
                    _crypto_question(family, strike, multiplier, horizon)
                )

    qids = [q.qid for q in questions]
    if len(set(qids)) != len(qids):
        _die("duplicate qids in universe")
    if len(questions) < MIN_QUESTIONS_PER_RUN:
        _die(
            f"universe has {len(questions)} questions; "
            f"ratified floor is {MIN_QUESTIONS_PER_RUN}"
        )
    return questions


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODEL PROBABILITIES (fail loud — no defaults, no priors, no overrides)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

_FORECASTER_SYSTEM = (
    "You are a calibrated probabilistic forecaster. You are given yes/no "
    "questions about macro data prints and crypto prices, each with its "
    "frozen strike and resolve-by time. Reply with ONLY a JSON object "
    "mapping every question id to your probability that the answer is YES, "
    "as a number strictly between 0 and 1. No prose, no code fences, no "
    "omitted ids. Your Brier score is tracked publicly, misses included; "
    "answer with your honest calibrated probability, not a hedge."
)


def _parse_probabilities(
    raw_text: str, questions: list[Question]
) -> dict[str, float]:
    match = _JSON_BLOCK_RE.search(raw_text)
    if not match:
        raise GinkoModelError("model reply contained no JSON object")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise GinkoModelError(f"model reply is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise GinkoModelError("model reply JSON is not an object")
    probs: dict[str, float] = {}
    for q in questions:
        value = data.get(q.qid)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise GinkoModelError(f"model omitted or mistyped {q.qid}")
        p = float(value)
        if not 0.0 < p < 1.0:
            raise GinkoModelError(
                f"probability for {q.qid} out of (0, 1): {p}"
            )
        probs[q.qid] = p
    return probs


async def model_probabilities(
    questions: list[Question], model: str, now: datetime
) -> dict[str, float]:
    """One real model call for the whole universe. Raises GinkoModelError.

    There is deliberately no fallback path: a failed or unparseable call
    aborts the run before anything is recorded.
    """
    api_key = os.environ.get(ANTHROPIC_API_KEY_ENV)
    if not api_key:
        raise GinkoModelError(f"{ANTHROPIC_API_KEY_ENV} not set")
    try:
        from anthropic import AsyncAnthropic
    except ImportError as exc:
        raise GinkoModelError("anthropic SDK not installed") from exc

    payload = [
        {
            "qid": q.qid,
            "question": q.text,
            "category": q.category,
            "resolve_by": q.resolve_by(now),
        }
        for q in questions
    ]
    user_text = (
        f"Current UTC time: {now.isoformat()}\n"
        f"Questions ({len(payload)}):\n"
        f"{json.dumps(payload, indent=2)}\n\n"
        "Return the JSON object of qid -> probability now."
    )
    client = AsyncAnthropic(api_key=api_key)
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=16000,
            system=_FORECASTER_SYSTEM,
            messages=[{"role": "user", "content": user_text}],
        )
    except Exception as exc:  # fail loud: any API failure aborts the run
        raise GinkoModelError(f"model call failed: {exc}") from exc
    if response.stop_reason == "refusal":
        raise GinkoModelError("model refused the forecasting request")
    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    )
    return _parse_probabilities(raw_text, questions)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MECHANICAL RESOLVER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _compare(actual: float, comparator: str, threshold: float) -> float | None:
    if comparator == "gt":
        return 1.0 if actual > threshold else 0.0
    if comparator == "lt":
        return 1.0 if actual < threshold else 0.0
    return None


async def _fetch_actuals(
    rules: list[dict[str, Any]],
) -> dict[tuple[str, str], float]:
    """One fetch per distinct (source, series) across all matured rules."""
    from dharma_swarm import ginko_data as gd

    wanted = {(str(r["source"]), str(r["series"])) for r in rules}
    actuals: dict[tuple[str, str], float] = {}

    fred_series = sorted(s for src, s in wanted if src == "fred")
    for series in fred_series:
        obs = await gd.fetch_fred_series(series)
        if obs is not None:
            actuals[("fred", series)] = float(obs)

    coins = sorted(s for src, s in wanted if src == "coingecko")
    if coins:
        prices = await gd.fetch_crypto_prices(coins)
        for price in prices:
            actuals[("coingecko", price.coin_id)] = float(
                price.current_price_usd
            )
    return actuals


async def resolve_matured() -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve every prediction past resolve_by by replaying its recorded
    resolution rule. Returns (resolved rows, failure notes). A failed fetch
    or a legacy row without a rule stays pending — it is never guessed."""
    from dharma_swarm.ginko_brier import (
        get_overdue_predictions,
        resolve_prediction,
    )

    overdue = get_overdue_predictions()
    if not overdue:
        return [], []

    rules: list[dict[str, Any]] = []
    for pred in overdue:
        rule = (pred.metadata or {}).get("resolution")
        if isinstance(rule, dict) and {"source", "series"} <= rule.keys():
            rules.append(rule)
    actuals = await _fetch_actuals(rules)

    resolved_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for pred in overdue:
        rule = (pred.metadata or {}).get("resolution")
        if not (
            isinstance(rule, dict)
            and {"source", "series", "comparator", "threshold"} <= rule.keys()
        ):
            failures.append(f"{pred.id}: no mechanical resolution rule")
            continue
        key = (str(rule["source"]), str(rule["series"]))
        actual = actuals.get(key)
        if actual is None:
            failures.append(f"{pred.id}: no actual for {key}")
            continue
        outcome = _compare(actual, str(rule["comparator"]), float(rule["threshold"]))
        if outcome is None:
            failures.append(f"{pred.id}: unknown comparator {rule['comparator']}")
            continue
        updated = resolve_prediction(pred.id, outcome)
        if updated is None:
            failures.append(f"{pred.id}: resolve_prediction found no open row")
            continue
        resolved_rows.append(
            {
                "prediction_id": updated.id,
                "question": updated.question,
                "probability": updated.probability,
                "outcome": outcome,
                "brier_score": updated.brier_score,
                "actual": actual,
                "rule": rule,
            }
        )
    return resolved_rows, failures


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DURABLE LEDGER: REHYDRATE + PUBLISH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def rehydrate_store(public_ledger: Path) -> int:
    """Seed the local ~/.dharma store from the durable public ledger.

    The public ledger is the store of record; the CI store is ephemeral.
    Union by id: rows only ever gain resolution fields, so when both sides
    have a row, the resolved version wins. Returns rows in the store after.
    """
    from dharma_swarm import ginko_brier as gb

    if not public_ledger.is_file():
        if gb.PREDICTIONS_FILE.is_file():
            return len(_read_jsonl(gb.PREDICTIONS_FILE))
        return 0

    by_id: dict[str, dict[str, Any]] = {}
    if gb.PREDICTIONS_FILE.is_file():
        for row in _read_jsonl(gb.PREDICTIONS_FILE):
            by_id[str(row["id"])] = row
    for row in _read_jsonl(public_ledger):
        existing = by_id.get(str(row["id"]))
        if existing is None or (
            existing.get("outcome") is None and row.get("outcome") is not None
        ):
            by_id[str(row["id"])] = row

    gb.GINKO_DIR.mkdir(parents=True, exist_ok=True)
    with gb.PREDICTIONS_FILE.open("w", encoding="utf-8") as fh:
        for row in by_id.values():
            fh.write(json.dumps(row, default=str) + "\n")
    return len(by_id)


def publish(
    repo: Path,
    dashboard: dict[str, Any],
    new_rows: list[dict[str, Any]],
    resolved_rows: list[dict[str, Any]],
    grant_id: str,
) -> tuple[Path, str]:
    """Write the day receipt, the full public snapshot, and the index.

    Returns (day file path, timestamp grade). The public JSONL is the FULL
    store snapshot — rows are never removed, resolution fields fill in —
    so the generated/forecast-ledger branch stays the durable store of
    record that the next run rehydrates from.
    """
    from dharma_swarm import ginko_brier as gb

    day = _utc().strftime("%Y-%m-%d")
    dest = repo / PUBLISH_REL
    dest.mkdir(parents=True, exist_ok=True)

    grade = GRADE_GREEN if which("ots") else GRADE_AMBER
    payload: dict[str, Any] = {
        "schema": "dharma.ginko.l0.v2",
        "date": day,
        "grant_id": grant_id,
        "host": socket.gethostname(),
        "timestamp_grade": grade,
        "dashboard": dashboard,
        "new_rows": new_rows,
        "resolved_rows": resolved_rows,
        "note": "ledger receipt, not an edge receipt. misses included.",
    }
    path = dest / f"{day}.json"
    path.write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )

    if grade == GRADE_GREEN:
        stamp = subprocess.run(
            ["ots", "stamp", str(path)], check=False, capture_output=True
        )
        if stamp.returncode != 0 or not Path(str(path) + ".ots").is_file():
            grade = GRADE_AMBER
            payload["timestamp_grade"] = grade
            path.write_text(
                json.dumps(payload, indent=2, default=str) + "\n",
                encoding="utf-8",
            )

    # Full snapshot of the store — the durable public ledger.
    all_rows = (
        _read_jsonl(gb.PREDICTIONS_FILE) if gb.PREDICTIONS_FILE.is_file() else []
    )
    public = dest / PUBLIC_LEDGER_NAME
    with public.open("w", encoding="utf-8") as fh:
        for row in all_rows:
            fh.write(json.dumps(row, default=str) + "\n")

    index = dest / "index.md"
    index.write_text(
        f"# Forecast ledger (L0)\n\n"
        f"Last publish: {day}\n\n"
        f"Brier: {dashboard.get('overall_brier')} · "
        f"resolved: {dashboard.get('resolved_predictions')} · "
        f"pending: {dashboard.get('pending_predictions')} · "
        f"edge_validated: {dashboard.get('edge_validated')}\n\n"
        f"Timestamp grade: {grade}\n\n"
        f"Misses are included. This page is not a trading signal.\n",
        encoding="utf-8",
    )
    return path, grade


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# KILL DATE + MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def kill_hit(grant: dict[str, Any], dashboard: dict[str, Any]) -> bool:
    """After kill_after_days from first publish: stop NEW forecasts when the
    ledger is starved (<15 resolved) or the edge is dead (Brier >= 0.25).
    Resolve-only runs stay allowed either way."""
    consumed = grant.get("consumed_at")
    if not consumed:
        return False
    start = datetime.fromisoformat(str(consumed).replace("Z", "+00:00"))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    days = int(grant.get("kill_after_days") or 30)
    if _utc() < start + timedelta(days=days):
        return False
    brier = dashboard.get("overall_brier")
    resolved = int(dashboard.get("resolved_predictions") or 0)
    if resolved < 15:
        return True
    if brier is None or float(brier) >= 0.25:
        return True
    return False


def _dashboard_dict() -> dict[str, Any]:
    from dharma_swarm.ginko_brier import build_dashboard

    return asdict(build_dashboard())


async def main_async(args: argparse.Namespace) -> int:
    refuse_host()
    assert_no_forbidden_imports()
    grant_path = Path(args.grant).expanduser().resolve()
    grant = load_grant(grant_path)
    repo = repo_root(Path(args.repo_root) if args.repo_root else Path.cwd())
    sys.path.insert(0, str(repo))

    rehydrate_from = (
        Path(args.rehydrate_from).expanduser()
        if args.rehydrate_from
        else repo / PUBLISH_REL / PUBLIC_LEDGER_NAME
    )
    n_store = rehydrate_store(rehydrate_from)

    resolved_rows, resolve_failures = await resolve_matured()
    for note in resolve_failures:
        print(f"GINKO_L0_RESOLVE_SKIPPED: {note}", file=sys.stderr)

    dash = _dashboard_dict()
    if kill_hit(grant, dash) and not args.resolve_only:
        _die("kill date hit — no new forecasts (resolve-only is still allowed)")

    now = _utc()
    new_rows: list[dict[str, Any]] = []
    if not args.resolve_only:
        snaps = await fetch_snapshots()
        questions = build_universe(snaps)
        try:
            probs = await model_probabilities(questions, args.model, now)
        except GinkoModelError as exc:
            # Fail loud: nothing recorded, nothing published, exit nonzero.
            _die(f"model probabilities unavailable — recording nothing: {exc}", 1)

        from dharma_swarm.ginko_brier import record_prediction

        source = args.source or args.model
        for q in questions:
            pred = record_prediction(
                question=q.text,
                probability=probs[q.qid],
                resolve_by=q.resolve_by(now),
                category=q.category,
                source=source,
                metadata={
                    "qid": q.qid,
                    "universe": q.universe,
                    "strike": q.strike,
                    "resolution": q.resolution,
                    "model": args.model,
                    "timestamp_grade": GRADE_AMBER,
                },
            )
            new_rows.append(asdict(pred))

    assert_no_forbidden_imports()
    consume_start(grant_path, grant)
    grant = json.loads(grant_path.read_text(encoding="utf-8"))

    dash = _dashboard_dict()
    published, grade = publish(repo, dash, new_rows, resolved_rows, grant["grant_id"])
    receipt = {
        "schema": "dharma.ginko.l0.v2",
        "ts": _utc().isoformat().replace("+00:00", "Z"),
        "grant_id": grant["grant_id"],
        "host": socket.gethostname(),
        "model": None if args.resolve_only else args.model,
        "published_path": str(published.relative_to(repo)),
        "timestamp_grade": grade,
        "n_store": n_store,
        "n_new": len(new_rows),
        "n_resolved": len(resolved_rows),
        "n_resolve_skipped": len(resolve_failures),
        "store_sync_invoked": bool(_BANNED_MODULES.intersection(sys.modules)),
        "valid": bool(
            published.exists()
            and (new_rows or resolved_rows or args.resolve_only)
            and not _BANNED_MODULES.intersection(sys.modules)
        ),
        "note": "ledger receipt, not an edge receipt",
    }
    receipt_path = Path(args.receipt).expanduser()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    if not receipt["valid"]:
        _die("invalid receipt", 1)
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--grant", required=True)
    p.add_argument("--repo-root", default=None)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument(
        "--source",
        default=None,
        help="row source label; defaults to the model id",
    )
    p.add_argument(
        "--rehydrate-from",
        default=None,
        help="public ledger JSONL to seed the local store from "
        "(default: the repo publish dir copy)",
    )
    p.add_argument("--resolve-only", action="store_true")
    p.add_argument(
        "--receipt",
        default=str(Path.home() / ".dharma" / "ginko_l0" / "last_receipt.json"),
    )
    args = p.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
