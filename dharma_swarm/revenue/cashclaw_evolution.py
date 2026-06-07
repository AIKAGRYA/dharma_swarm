"""CashClaw Evolution Engine — variant management, fitness tracking, selection.

The evolution engine manages multiple CashClaw "variants" — each with its own
scoring weights, source configs, and filter thresholds. After each cycle,
results are recorded and variant fitness is updated. The fittest variants
survive; the weakest are replaced with mutations of the fittest.

This is the DarwinEngine for revenue generation: generate diversity, measure
fitness, select the best, mutate and repeat.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

DEFAULT_DB_PATH = Path.home() / ".dharma" / "cashclaw_evolution.db"

VARIANT_FIELDS = {
    "cash_speed_weight": (5, 40),
    "deliverability_weight": (5, 40),
    "distribution_access_weight": (0, 30),
    "payment_clarity_weight": (0, 30),
    "risk_cleanliness_weight": (0, 30),
    "agent_leverage_weight": (0, 20),
    "receipt_quality_weight": (0, 20),
    "min_score_threshold": (50, 95),
    "max_risk_flags": (0, 5),
    "top_n": (3, 25),
    "source_query_bias": (
        None,
        None,
    ),
}

SOURCE_QUERY_BIASES = (
    "broad",
    "ai_agent_focus",
    "crypto_focus",
    "docs_focus",
    "fastapi_focus",
    "infra_focus",
    "security_focus",
    "test_focus",
)


class Variant(BaseModel):
    """A CashClaw scoring/filtering variant."""

    variant_id: str
    generation: int = 0
    parent_id: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    cash_speed_weight: int = 20
    deliverability_weight: int = 20
    distribution_access_weight: int = 15
    payment_clarity_weight: int = 15
    risk_cleanliness_weight: int = 15
    agent_leverage_weight: int = 10
    receipt_quality_weight: int = 5
    min_score_threshold: int = 75
    max_risk_flags: int = 2
    top_n: int = 10
    source_query_bias: str = "broad"

    active: bool = True


class CycleResult(BaseModel):
    """Result of one evolutionary cycle run."""

    result_id: str
    variant_id: str
    cycle_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    opportunities_found: int = 0
    opportunities_above_threshold: int = 0
    opportunities_submitted: int = 0
    revenue_earned_cents: int = 0
    cost_cents: int = 0

    top_opportunity_value_cents: int = 0
    avg_score: float = 0.0
    sources_hit: int = 0
    errors: int = 0

    notes: str = ""


class FitnessScore(BaseModel):
    """Aggregate fitness of a variant across all its cycles."""

    variant_id: str
    total_cycles: int = 0
    total_revenue_cents: int = 0
    total_cost_cents: int = 0
    total_opportunities_found: int = 0
    total_opportunities_submitted: int = 0
    avg_score_per_cycle: float = 0.0
    roi: float = 0.0
    fitness: float = 0.0
    last_cycle: str = ""


class CashClawEvolutionDB:
    """SQLite-backed evolution state for CashClaw variants."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._create_tables()
        return self._conn

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS variants (
                variant_id TEXT PRIMARY KEY,
                generation INTEGER NOT NULL DEFAULT 0,
                parent_id TEXT,
                created_at TEXT NOT NULL,
                cash_speed_weight INTEGER NOT NULL DEFAULT 20,
                deliverability_weight INTEGER NOT NULL DEFAULT 20,
                distribution_access_weight INTEGER NOT NULL DEFAULT 15,
                payment_clarity_weight INTEGER NOT NULL DEFAULT 15,
                risk_cleanliness_weight INTEGER NOT NULL DEFAULT 15,
                agent_leverage_weight INTEGER NOT NULL DEFAULT 10,
                receipt_quality_weight INTEGER NOT NULL DEFAULT 5,
                min_score_threshold INTEGER NOT NULL DEFAULT 75,
                max_risk_flags INTEGER NOT NULL DEFAULT 2,
                top_n INTEGER NOT NULL DEFAULT 10,
                source_query_bias TEXT NOT NULL DEFAULT 'broad',
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS cycle_results (
                result_id TEXT PRIMARY KEY,
                variant_id TEXT NOT NULL,
                cycle_timestamp TEXT NOT NULL,
                opportunities_found INTEGER DEFAULT 0,
                opportunities_above_threshold INTEGER DEFAULT 0,
                opportunities_submitted INTEGER DEFAULT 0,
                revenue_earned_cents INTEGER DEFAULT 0,
                cost_cents INTEGER DEFAULT 0,
                top_opportunity_value_cents INTEGER DEFAULT 0,
                avg_score REAL DEFAULT 0.0,
                sources_hit INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                FOREIGN KEY (variant_id) REFERENCES variants(variant_id)
            );

            CREATE INDEX IF NOT EXISTS idx_cycle_variant ON cycle_results(variant_id);
            CREATE INDEX IF NOT EXISTS idx_cycle_ts ON cycle_results(cycle_timestamp);
            """
        )
        self._conn.commit()

    def upsert_variant(self, v: Variant) -> None:
        conn = self._connect()
        conn.execute(
            """INSERT OR REPLACE INTO variants
               (variant_id, generation, parent_id, created_at,
                cash_speed_weight, deliverability_weight, distribution_access_weight,
                payment_clarity_weight, risk_cleanliness_weight, agent_leverage_weight,
                receipt_quality_weight, min_score_threshold, max_risk_flags,
                top_n, source_query_bias, active)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                v.variant_id, v.generation, v.parent_id, v.created_at,
                v.cash_speed_weight, v.deliverability_weight, v.distribution_access_weight,
                v.payment_clarity_weight, v.risk_cleanliness_weight, v.agent_leverage_weight,
                v.receipt_quality_weight, v.min_score_threshold, v.max_risk_flags,
                v.top_n, v.source_query_bias, int(v.active),
            ),
        )
        conn.commit()

    def record_result(self, r: CycleResult) -> None:
        conn = self._connect()
        conn.execute(
            """INSERT OR REPLACE INTO cycle_results
               (result_id, variant_id, cycle_timestamp,
                opportunities_found, opportunities_above_threshold, opportunities_submitted,
                revenue_earned_cents, cost_cents, top_opportunity_value_cents,
                avg_score, sources_hit, errors, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r.result_id, r.variant_id, r.cycle_timestamp,
                r.opportunities_found, r.opportunities_above_threshold,
                r.opportunities_submitted, r.revenue_earned_cents, r.cost_cents,
                r.top_opportunity_value_cents, r.avg_score, r.sources_hit, r.errors, r.notes,
            ),
        )
        conn.commit()

    def get_fitness(self, variant_id: str) -> FitnessScore:
        conn = self._connect()
        row = conn.execute(
            """SELECT
                 COUNT(*) as total_cycles,
                 COALESCE(SUM(revenue_earned_cents), 0) as total_revenue_cents,
                 COALESCE(SUM(cost_cents), 0) as total_cost_cents,
                 COALESCE(SUM(opportunities_found), 0) as total_opportunities_found,
                 COALESCE(SUM(opportunities_submitted), 0) as total_opportunities_submitted,
                 COALESCE(AVG(avg_score), 0) as avg_score_per_cycle,
                 MAX(cycle_timestamp) as last_cycle
               FROM cycle_results WHERE variant_id = ?""",
            (variant_id,),
        ).fetchone()
        if row is None or row["total_cycles"] == 0:
            return FitnessScore(variant_id=variant_id)
        cost = max(row["total_cost_cents"], 1)
        roi = row["total_revenue_cents"] / cost
        submission_rate = row["total_opportunities_submitted"] / max(row["total_opportunities_found"], 1)
        fitness = (
            roi * 40
            + submission_rate * 30
            + row["avg_score_per_cycle"] * 0.3
        )
        return FitnessScore(
            variant_id=variant_id,
            total_cycles=row["total_cycles"],
            total_revenue_cents=row["total_revenue_cents"],
            total_cost_cents=row["total_cost_cents"],
            total_opportunities_found=row["total_opportunities_found"],
            total_opportunities_submitted=row["total_opportunities_submitted"],
            avg_score_per_cycle=round(row["avg_score_per_cycle"], 2),
            roi=round(roi, 4),
            fitness=round(fitness, 2),
            last_cycle=row["last_cycle"],
        )

    def get_active_variants(self) -> list[Variant]:
        conn = self._connect()
        rows = conn.execute("SELECT * FROM variants WHERE active = 1").fetchall()
        return [
            Variant(
                variant_id=r["variant_id"],
                generation=r["generation"],
                parent_id=r["parent_id"],
                created_at=r["created_at"],
                cash_speed_weight=r["cash_speed_weight"],
                deliverability_weight=r["deliverability_weight"],
                distribution_access_weight=r["distribution_access_weight"],
                payment_clarity_weight=r["payment_clarity_weight"],
                risk_cleanliness_weight=r["risk_cleanliness_weight"],
                agent_leverage_weight=r["agent_leverage_weight"],
                receipt_quality_weight=r["receipt_quality_weight"],
                min_score_threshold=r["min_score_threshold"],
                max_risk_flags=r["max_risk_flags"],
                top_n=r["top_n"],
                source_query_bias=r["source_query_bias"],
                active=bool(r["active"]),
            )
            for r in rows
        ]

    def get_leaderboard(self, limit: int = 10) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT variant_id FROM variants WHERE active = 1"
        ).fetchall()
        scored = []
        for r in rows:
            f = self.get_fitness(r["variant_id"])
            scored.append(f.model_dump())
        scored.sort(key=lambda x: x["fitness"], reverse=True)
        return scored[:limit]

    def seed_initial_variants(self) -> list[Variant]:
        """Create the founding population of variants."""
        existing = self.get_active_variants()
        if existing:
            return existing
        import random

        variants = []
        biases = list(SOURCE_QUERY_BIASES)
        for i, bias in enumerate(biases[:6]):
            v = Variant(
                variant_id=f"v0-{bias}-{_short_hash(bias + str(i))}",
                generation=0,
                parent_id=None,
                source_query_bias=bias,
                cash_speed_weight=20 + (i % 3) * 5,
                deliverability_weight=20 - (i % 2) * 5,
                min_score_threshold=70 + i * 3,
            )
            self.upsert_variant(v)
            variants.append(v)
        return variants


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:8]
