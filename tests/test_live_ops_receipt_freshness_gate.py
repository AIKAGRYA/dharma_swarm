"""PR 8 verifier — receipt freshness gate for the ingest health receipt.

Deterministic, no-network. The idea-spark health receipt reuses the live-ops
census freshness contract; this gate proves missing/fresh/stale states with a
fixed clock.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dharma_swarm.idea_spark.health import (
    health_receipt_freshness,
    write_health_receipt,
)
from dharma_swarm.operator_core.live_ops_census_contract import census_payload_freshness

FIXED_NOW = "2026-06-26T00:00:00Z"
_NOW_DT = datetime(2026, 6, 26, 0, 0, 0, tzinfo=timezone.utc)


def test_missing_receipt_reports_missing(tmp_path) -> None:
    state = health_receipt_freshness(tmp_path, now=_NOW_DT)
    assert state["state"] == "missing"
    assert state["age_minutes"] is None


def test_fresh_receipt_is_fresh(tmp_path) -> None:
    write_health_receipt(tmp_path, now=FIXED_NOW, include_chetana_backlog=False)
    state = health_receipt_freshness(tmp_path, now=_NOW_DT)
    assert state["state"] == "fresh"
    assert state["age_minutes"] == 0.0


def test_stale_receipt_is_stale(tmp_path) -> None:
    write_health_receipt(tmp_path, now=FIXED_NOW, include_chetana_backlog=False)
    # Two days later, a 24h gate flags it stale.
    later = _NOW_DT + timedelta(days=2)
    state = health_receipt_freshness(tmp_path, now=later, max_age_hours=24.0)
    assert state["state"] == "stale"
    assert state["age_minutes"] is not None and state["age_minutes"] > 24 * 60


def test_census_freshness_contract_directly() -> None:
    fresh = census_payload_freshness({"generated_at": FIXED_NOW}, now=_NOW_DT, max_age_hours=24.0)
    assert fresh["state"] == "fresh"
    stale = census_payload_freshness(
        {"generated_at": "2026-06-01T00:00:00Z"}, now=_NOW_DT, max_age_hours=24.0
    )
    assert stale["state"] == "stale"
