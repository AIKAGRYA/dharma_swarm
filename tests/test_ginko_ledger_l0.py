"""Tests for scripts/ginko_ledger_l0.py — the L0 forecast-ledger runner.

Covers the real-edition contract (yes-sheet 2026-08-18 line 7):
  - question universe >= 20 with mechanical resolution metadata,
  - probabilities only from a model call (failure -> nonzero exit, nothing
    recorded, grant untouched),
  - the resolver replays recorded rules and calls resolve_prediction,
  - rehydration round-trip through the public ledger snapshot,
  - field names against the real BrierDashboard (resolved_predictions).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import dharma_swarm.ginko_brier as gb  # noqa: E402
import dharma_swarm.ginko_data as gd  # noqa: E402
from scripts import ginko_ledger_l0 as l0  # noqa: E402

SNAPS = {
    "fred.cpi": 320.0,
    "fred.dgs10": 4.25,
    "fred.icsa": 220000.0,
    "crypto.btc_usd": 65000.0,
    "crypto.eth_usd": 3200.0,
}


def _utc() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture()
def ginko_store(tmp_path, monkeypatch):
    """Point the ginko_brier persistence at an isolated temp store."""
    gdir = tmp_path / "ginko"
    monkeypatch.setattr(gb, "GINKO_DIR", gdir)
    monkeypatch.setattr(gb, "PREDICTIONS_FILE", gdir / "predictions.jsonl")
    monkeypatch.setattr(gb, "DASHBOARD_FILE", gdir / "brier_dashboard.json")
    monkeypatch.setattr(
        gb, "NOTIFICATIONS_FILE", gdir / "resolved_notifications.jsonl"
    )
    return gdir


@pytest.fixture()
def fake_repo(tmp_path):
    """A minimal repo root for repo_root()/publish() without touching the
    real checkout. Cleans the sys.path entry main_async inserts."""
    repo = tmp_path / "repo"
    (repo / "dharma_swarm").mkdir(parents=True)
    (repo / "dharma_swarm" / "ginko_brier.py").write_text(
        "# repo-root marker for tests\n", encoding="utf-8"
    )
    yield repo
    while str(repo) in sys.path:
        sys.path.remove(str(repo))


class _FakePrice:
    def __init__(self, coin_id: str, price: float) -> None:
        self.coin_id = coin_id
        self.current_price_usd = price


def _patch_fetchers(
    monkeypatch, fred: dict[str, float], crypto: dict[str, float]
) -> None:
    async def fake_fred(series_id, api_key=None, client=None):
        return fred.get(series_id)

    async def fake_crypto(coin_ids=None, client=None):
        return [
            _FakePrice(coin, crypto[coin])
            for coin in (coin_ids or [])
            if coin in crypto
        ]

    monkeypatch.setattr(gd, "fetch_fred_series", fake_fred)
    monkeypatch.setattr(gd, "fetch_crypto_prices", fake_crypto)


def _write_grant(path: Path, **overrides) -> Path:
    grant = {
        "grant_id": "ginko-l0-test",
        "kind": "PUBLISH",
        "granted_by": "test-operator",
        "expires_at": (_utc() + timedelta(days=30)).isoformat(),
        "kill_after_days": 30,
        "allowed_universes": sorted(l0.ALLOWED_UNIVERSES),
    }
    grant.update(overrides)
    path.write_text(json.dumps(grant, indent=2), encoding="utf-8")
    return path


def _args(grant: Path, repo: Path, receipt: Path, **kw) -> argparse.Namespace:
    defaults = dict(
        grant=str(grant),
        repo_root=str(repo),
        model="claude-test-model",
        source=None,
        rehydrate_from=None,
        resolve_only=False,
        receipt=str(receipt),
    )
    defaults.update(kw)
    return argparse.Namespace(**defaults)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UNIVERSE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_universe_meets_ratified_floor_with_resolution_rules():
    questions = l0.build_universe(SNAPS)
    assert len(questions) >= 20, "ratified floor is 20+ questions per run"
    qids = [q.qid for q in questions]
    assert len(set(qids)) == len(qids), "qids must be unique"
    for q in questions:
        assert q.universe in l0.ALLOWED_UNIVERSES
        assert q.horizon_days > 0
        assert q.category in {"macro", "crypto"}
        rule = q.resolution
        assert rule["source"] in {"fred", "coingecko"}
        assert rule["series"]
        assert rule["comparator"] in {"gt", "lt"}
        assert isinstance(rule["threshold"], float)


def test_universe_refuses_below_floor(monkeypatch):
    monkeypatch.setattr(l0, "MIN_QUESTIONS_PER_RUN", 999)
    with pytest.raises(SystemExit):
        l0.build_universe(SNAPS)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NO-DEFAULT PROBABILITIES (fail loud)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_parse_probabilities_rejects_gaps_and_bounds():
    questions = l0.build_universe(SNAPS)
    full = {q.qid: 0.42 for q in questions}
    assert l0._parse_probabilities(json.dumps(full), questions) == full

    missing = dict(full)
    missing.pop(questions[0].qid)
    with pytest.raises(l0.GinkoModelError):
        l0._parse_probabilities(json.dumps(missing), questions)

    for bad in (0.0, 1.0, "0.4", None, True):
        broken = dict(full)
        broken[questions[0].qid] = bad
        with pytest.raises(l0.GinkoModelError):
            l0._parse_probabilities(json.dumps(broken), questions)

    with pytest.raises(l0.GinkoModelError):
        l0._parse_probabilities("no json here", questions)


async def test_model_failure_exits_nonzero_and_records_nothing(
    ginko_store, fake_repo, tmp_path, monkeypatch
):
    _patch_fetchers(
        monkeypatch,
        {"CPIAUCSL": 320.0, "DGS10": 4.25, "ICSA": 220000.0},
        {"bitcoin": 65000.0, "ethereum": 3200.0},
    )

    async def failing_model(questions, model, now):
        raise l0.GinkoModelError("simulated model outage")

    monkeypatch.setattr(l0, "model_probabilities", failing_model)
    grant = _write_grant(tmp_path / "GRANT.json")
    args = _args(grant, fake_repo, tmp_path / "receipt.json")

    with pytest.raises(SystemExit) as excinfo:
        await l0.main_async(args)
    assert excinfo.value.code == 1, "model failure must exit nonzero"
    assert not gb.PREDICTIONS_FILE.exists(), "nothing may be recorded"
    assert not (fake_repo / l0.PUBLISH_REL).exists(), "nothing may be published"
    assert "consumed_at" not in json.loads(grant.read_text()), (
        "a failed run must not consume the grant"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MECHANICAL RESOLVER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def test_resolver_calls_resolve_prediction_on_matured(
    ginko_store, monkeypatch
):
    past = (_utc() - timedelta(days=1)).isoformat()
    future = (_utc() + timedelta(days=7)).isoformat()
    yes = gb.record_prediction(
        question="DGS10 above 4.0?",
        probability=0.7,
        resolve_by=past,
        category="macro",
        source="test",
        metadata={
            "resolution": {
                "source": "fred",
                "series": "DGS10",
                "comparator": "gt",
                "threshold": 4.0,
            }
        },
    )
    no = gb.record_prediction(
        question="BTC above 70000?",
        probability=0.6,
        resolve_by=past,
        category="crypto",
        source="test",
        metadata={
            "resolution": {
                "source": "coingecko",
                "series": "bitcoin",
                "comparator": "gt",
                "threshold": 70000.0,
            }
        },
    )
    legacy = gb.record_prediction(
        question="No rule recorded",
        probability=0.5,
        resolve_by=past,
        category="general",
        source="test",
        metadata=None,
    )
    pending = gb.record_prediction(
        question="Not matured yet",
        probability=0.8,
        resolve_by=future,
        category="macro",
        source="test",
        metadata={
            "resolution": {
                "source": "fred",
                "series": "DGS10",
                "comparator": "gt",
                "threshold": 4.0,
            }
        },
    )

    _patch_fetchers(monkeypatch, {"DGS10": 4.5}, {"bitcoin": 65000.0})
    calls: list[tuple[str, float]] = []
    real_resolve = gb.resolve_prediction

    def spying_resolve(prediction_id, outcome):
        calls.append((prediction_id, outcome))
        return real_resolve(prediction_id, outcome)

    monkeypatch.setattr(gb, "resolve_prediction", spying_resolve)

    resolved_rows, failures = await l0.resolve_matured()

    assert {c[0] for c in calls} == {yes.id, no.id}, (
        "resolve_prediction must be called for exactly the matured rows "
        "with mechanical rules"
    )
    outcomes = {row["prediction_id"]: row["outcome"] for row in resolved_rows}
    assert outcomes == {yes.id: 1.0, no.id: 0.0}
    assert len(failures) == 1 and legacy.id in failures[0]

    by_id = {p.id: p for p in gb._load_all_predictions()}
    assert by_id[yes.id].outcome == 1.0
    assert by_id[yes.id].brier_score == pytest.approx((0.7 - 1.0) ** 2)
    assert by_id[no.id].outcome == 0.0
    assert by_id[legacy.id].outcome is None, "no rule -> never guessed"
    assert by_id[pending.id].outcome is None, "unmatured stays open"


async def test_resolver_skips_when_actual_unavailable(ginko_store, monkeypatch):
    past = (_utc() - timedelta(days=1)).isoformat()
    pred = gb.record_prediction(
        question="DGS10 above 4.0?",
        probability=0.7,
        resolve_by=past,
        category="macro",
        source="test",
        metadata={
            "resolution": {
                "source": "fred",
                "series": "DGS10",
                "comparator": "gt",
                "threshold": 4.0,
            }
        },
    )
    _patch_fetchers(monkeypatch, {}, {})
    resolved_rows, failures = await l0.resolve_matured()
    assert resolved_rows == []
    assert len(failures) == 1
    assert gb._load_all_predictions()[0].outcome is None
    assert pred.id in failures[0]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REHYDRATION ROUND-TRIP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def test_rehydration_round_trip(ginko_store, fake_repo, monkeypatch):
    future = (_utc() + timedelta(days=7)).isoformat()
    preds = [
        gb.record_prediction(
            question=f"q{i}",
            probability=0.4,
            resolve_by=future,
            category="macro",
            source="test",
            metadata={
                "resolution": {
                    "source": "fred",
                    "series": "DGS10",
                    "comparator": "gt",
                    "threshold": 4.0,
                }
            },
        )
        for i in range(3)
    ]
    gb.resolve_prediction(preds[0].id, 1.0)

    monkeypatch.setattr(l0, "which", lambda name: None)
    dash = asdict(gb.build_dashboard())
    _, grade = l0.publish(fake_repo, dash, [], [], "ginko-l0-test")
    assert grade == l0.GRADE_AMBER, "no ots client -> AMBER, never GREEN"
    public = fake_repo / l0.PUBLISH_REL / l0.PUBLIC_LEDGER_NAME
    assert public.is_file()
    published_rows = l0._read_jsonl(public)
    assert len(published_rows) == 3, "public ledger is the FULL snapshot"

    # Blow away the local store (ephemeral CI) and rehydrate from the
    # public ledger: every row, including the resolution, must survive.
    gb.PREDICTIONS_FILE.unlink()
    n = l0.rehydrate_store(public)
    assert n == 3
    by_id = {p.id: p for p in gb._load_all_predictions()}
    assert set(by_id) == {p.id for p in preds}
    assert by_id[preds[0].id].outcome == 1.0
    assert by_id[preds[0].id].brier_score == pytest.approx((0.4 - 1.0) ** 2)
    assert by_id[preds[1].id].outcome is None

    # Union semantics: a resolved public row wins over a stale local copy.
    gb.resolve_prediction(preds[1].id, 0.0)
    dash = asdict(gb.build_dashboard())
    l0.publish(fake_repo, dash, [], [], "ginko-l0-test")
    gb.PREDICTIONS_FILE.unlink()
    gb.record_prediction(
        question="q1",
        probability=0.4,
        resolve_by=future,
        category="macro",
        source="test",
        metadata=None,
    )
    n = l0.rehydrate_store(public)
    assert n == 4, "union by id: 3 public rows + 1 local-only row"
    resolved = [p for p in gb._load_all_predictions() if p.outcome is not None]
    assert len(resolved) == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DASHBOARD FIELD NAMES + KILL DATE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _seed_resolved(n: int, probability: float = 0.9, outcome: float = 1.0):
    past = (_utc() - timedelta(days=2)).isoformat()
    for i in range(n):
        pred = gb.record_prediction(
            question=f"seed{i}",
            probability=probability,
            resolve_by=past,
            category="macro",
            source="test",
            metadata=None,
        )
        gb.resolve_prediction(pred.id, outcome)


def test_kill_hit_reads_real_dashboard_field_names(ginko_store):
    _seed_resolved(20)
    dash = asdict(gb.build_dashboard())
    # The real BrierDashboard field is resolved_predictions (ginko_brier.py);
    # the old runner read resolved_count/n_resolved, which do not exist and
    # silently coerced to 0.
    assert dash["resolved_predictions"] == 20
    assert "resolved_count" not in dash
    assert "n_resolved" not in dash

    armed = {
        "consumed_at": (_utc() - timedelta(days=40)).isoformat(),
        "kill_after_days": 30,
    }
    # 20 resolved at Brier 0.01: healthy ledger, kill must NOT fire. If the
    # code still read the wrong key it would see 0 resolved and kill.
    assert dash["overall_brier"] == pytest.approx(0.01)
    assert l0.kill_hit(armed, dash) is False

    starved = dict(dash)
    starved["resolved_predictions"] = 5
    assert l0.kill_hit(armed, starved) is True

    dead_edge = dict(dash)
    dead_edge["overall_brier"] = 0.3
    assert l0.kill_hit(armed, dead_edge) is True

    unconsumed = {"kill_after_days": 30}
    assert l0.kill_hit(unconsumed, dash) is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FULL RUN + GRANT GATING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def test_full_run_records_model_probabilities(
    ginko_store, fake_repo, tmp_path, monkeypatch
):
    _patch_fetchers(
        monkeypatch,
        {"CPIAUCSL": 320.0, "DGS10": 4.25, "ICSA": 220000.0},
        {"bitcoin": 65000.0, "ethereum": 3200.0},
    )

    async def fake_model(questions, model, now):
        return {q.qid: 0.61 for q in questions}

    monkeypatch.setattr(l0, "model_probabilities", fake_model)
    monkeypatch.setattr(l0, "which", lambda name: None)
    grant = _write_grant(tmp_path / "GRANT.json")
    receipt_path = tmp_path / "receipt.json"
    args = _args(grant, fake_repo, receipt_path)

    assert await l0.main_async(args) == 0

    rows = gb._load_all_predictions()
    assert len(rows) >= 20
    assert all(row.probability == pytest.approx(0.61) for row in rows), (
        "recorded probabilities must be exactly the model output — no 0.5 "
        "default may exist anywhere"
    )
    for row in rows:
        meta = row.metadata or {}
        assert meta["model"] == "claude-test-model"
        assert meta["timestamp_grade"] == l0.GRADE_AMBER
        assert {"source", "series", "comparator", "threshold"} <= set(
            meta["resolution"]
        )
    assert rows[0].source == "claude-test-model"

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["schema"] == "dharma.ginko.l0.v2"
    assert receipt["valid"] is True
    assert receipt["n_new"] == len(rows)
    assert receipt["timestamp_grade"] == l0.GRADE_AMBER
    assert receipt["store_sync_invoked"] is False

    public = fake_repo / l0.PUBLISH_REL / l0.PUBLIC_LEDGER_NAME
    assert len(l0._read_jsonl(public)) == len(rows)
    day_files = sorted((fake_repo / l0.PUBLISH_REL).glob("*.json"))
    assert day_files, "day receipt must be published"
    day = json.loads(day_files[0].read_text(encoding="utf-8"))
    assert day["timestamp_grade"] == l0.GRADE_AMBER
    assert day["dashboard"]["resolved_predictions"] == 0
    assert json.loads(grant.read_text())["consumed_at"], (
        "first published row consumes the grant start"
    )


async def test_grant_universe_mismatch_refused(tmp_path, fake_repo):
    grant = _write_grant(
        tmp_path / "GRANT.json",
        allowed_universes=[
            "fred.cpi_mom_positive",
            "fred.dgs10_up",
            "crypto.btc_usd_up",
        ],
    )
    args = _args(grant, fake_repo, tmp_path / "receipt.json")
    with pytest.raises(SystemExit) as excinfo:
        await l0.main_async(args)
    assert excinfo.value.code == 2
