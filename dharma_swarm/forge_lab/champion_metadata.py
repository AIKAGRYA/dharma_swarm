"""Strict research-only champion metadata construction and validation."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Mapping

from dharma_swarm.forge_lab.campaign_budget import CampaignBudgetError, CampaignBudgetLedger
from dharma_swarm.forge_lab.ids import (
    candidate_id as raw_candidate_id,
    content_digest,
    genome_digest,
    phenotype_id as executed_phenotype_id,
)
from dharma_swarm.forge_lab.paired_evaluation import AGGREGATE_SCHEMA, SEED_SUPPORT_MODES

CHAMPION_SCHEMA = "forge_lab.shadow_champion.v1"


class ChampionStoreError(RuntimeError):
    """Champion metadata or persisted state is invalid."""


class ChampionConflict(ChampionStoreError):
    """The incumbent changed after this campaign froze its baseline."""


def json_copy(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        copied = json.loads(json.dumps(value, sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ChampionStoreError(f"metadata is not canonical JSON: {exc}") from exc
    if not isinstance(copied, dict):
        raise ChampionStoreError("metadata must be an object")
    return copied


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_shadow_champion(
    *, category: str, candidate_id: str, phenotype_id: str,
    genome: Mapping[str, Any], genome_sha256: str, experiment_id: str,
    source_base_sha: str, evaluation_plan_sha256: str, baseline_candidate_id: str,
    paired_stats: Mapping[str, Any], repeat_seeds: tuple[int, ...] | list[int],
    seed_support: str, campaign_budget: Mapping[str, Any], selection_score: float,
    selection_rule: str, tie_break: Mapping[str, Any], created_at: str | None = None,
) -> dict[str, Any]:
    """Construct metadata that can only describe a shadow/research champion."""
    value: dict[str, Any] = {
        "schema": CHAMPION_SCHEMA,
        "category": category,
        "candidate_id": candidate_id,
        "phenotype_id": phenotype_id,
        "genome": json_copy(genome),
        "genome_sha256": genome_sha256,
        "experiment_id": experiment_id,
        "source_base_sha": source_base_sha,
        "evaluation_plan_sha256": evaluation_plan_sha256,
        "baseline_candidate_id": baseline_candidate_id,
        "paired_stats": json_copy(paired_stats),
        "repeat_seeds": list(repeat_seeds),
        "seed_support": seed_support,
        "campaign_budget": json_copy(campaign_budget),
        "selection": {
            "score": float(selection_score), "rule": selection_rule,
            "tie_break": json_copy(tie_break), "selection_eligible": True,
        },
        "evidence_tier": "shadow_research",
        "created_at": created_at or utc_now(),
        "claims": {
            "positive_lift_claimed": False, "production_eligible": False,
            "holdout_used_for_selection": False, "scope": "research_only",
        },
    }
    value["metadata_sha256"] = content_digest(value)
    validate_shadow_champion(value)
    return value


def validate_shadow_champion(value: Mapping[str, Any]) -> None:
    if value.get("schema") != CHAMPION_SCHEMA:
        raise ChampionStoreError(f"unsupported champion schema: {value.get('schema')!r}")
    for field in (
        "category", "candidate_id", "phenotype_id", "experiment_id",
        "source_base_sha", "baseline_candidate_id", "created_at",
    ):
        if not str(value.get(field) or "").strip():
            raise ChampionStoreError(f"champion field is required: {field}")
    if not str(value.get("candidate_id")).startswith("cand_"):
        raise ChampionStoreError("candidate_id must be a raw cand_ identity")
    if not str(value.get("phenotype_id")).startswith("pheno_"):
        raise ChampionStoreError("phenotype_id must be an executed pheno_ identity")
    if value.get("candidate_id") == value.get("baseline_candidate_id"):
        raise ChampionStoreError("champion candidate must differ from its paired baseline")
    genome = value.get("genome")
    if not isinstance(genome, Mapping):
        raise ChampionStoreError("champion executable genome is required")
    if genome_digest(dict(genome)) != value.get("genome_sha256"):
        raise ChampionStoreError("champion genome digest does not match genome")
    if raw_candidate_id(dict(genome)) != value.get("candidate_id"):
        raise ChampionStoreError("champion candidate_id does not match genome")
    try:
        expected_phenotype = executed_phenotype_id(dict(genome))
    except (TypeError, ValueError) as exc:
        raise ChampionStoreError(f"champion genome is not executable: {exc}") from exc
    if expected_phenotype != value.get("phenotype_id"):
        raise ChampionStoreError("champion phenotype_id does not match genome")
    for field in ("genome_sha256", "evaluation_plan_sha256"):
        digest = str(value.get(field) or "")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ChampionStoreError(f"{field} must be a full SHA-256 digest")

    repeats = value.get("repeat_seeds")
    if (not isinstance(repeats, list) or not repeats
            or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in repeats)
            or len(set(repeats)) != len(repeats)):
        raise ChampionStoreError("repeat_seeds must be non-empty unique integers")
    if value.get("seed_support") not in SEED_SUPPORT_MODES:
        raise ChampionStoreError("invalid seed_support mode")
    budget = value.get("campaign_budget")
    if not isinstance(budget, Mapping):
        raise ChampionStoreError("a budget-valid campaign ledger is required")
    try:
        parsed_budget = CampaignBudgetLedger.from_dict(budget)
        parsed_budget.assert_closeout_ready()
    except CampaignBudgetError as exc:
        raise ChampionStoreError(f"a budget-valid settled campaign ledger is required: {exc}") from exc
    selection = value.get("selection")
    if not isinstance(selection, Mapping) or selection.get("selection_eligible") is not True:
        raise ChampionStoreError("champion must be selection eligible")
    if not str(selection.get("rule") or "").strip() or not isinstance(selection.get("tie_break"), Mapping):
        raise ChampionStoreError("selection rule and tie_break metadata are required")
    try:
        score = float(selection.get("score"))
    except (TypeError, ValueError) as exc:
        raise ChampionStoreError("selection score must be finite") from exc
    if not math.isfinite(score):
        raise ChampionStoreError("selection score must be finite")

    paired_stats = value.get("paired_stats")
    if not isinstance(paired_stats, Mapping) or set(paired_stats) != {
        "train", "explore", "confirm", "holdout",
    }:
        raise ChampionStoreError("paired_stats must contain exactly four frozen splits")
    explore = paired_stats.get("explore")
    if (not isinstance(explore, Mapping) or explore.get("complete") is not True
            or explore.get("budget_valid") is not True
            or explore.get("selection_eligible") is not True):
        raise ChampionStoreError("complete budget-valid EXPLORE paired evidence is required")
    for split, stats in paired_stats.items():
        if not isinstance(stats, Mapping):
            raise ChampionStoreError(f"paired_stats[{split!r}] must be an object")
        if stats.get("schema") != AGGREGATE_SCHEMA or stats.get("plan_bound") is not True:
            raise ChampionStoreError(f"paired_stats[{split!r}] is not bound to a frozen plan")
        if stats.get("complete") is not True or stats.get("budget_valid") is not True:
            raise ChampionStoreError(f"paired_stats[{split!r}] is incomplete or budget-invalid")
        if stats.get("protocol_sha256") != value.get("evaluation_plan_sha256"):
            raise ChampionStoreError(f"paired_stats[{split!r}] protocol does not match plan")
        if stats.get("baseline_candidate_id") != value.get("baseline_candidate_id"):
            raise ChampionStoreError(f"paired_stats[{split!r}] baseline does not match metadata")
        if stats.get("candidate_id") != value.get("candidate_id"):
            raise ChampionStoreError(f"paired_stats[{split!r}] candidate does not match metadata")
        if stats.get("split") != split:
            raise ChampionStoreError(f"paired_stats[{split!r}] split identity is invalid")
        if stats.get("repeat_seeds") != sorted(repeats):
            raise ChampionStoreError(f"paired_stats[{split!r}] repeat seeds do not match metadata")
        if stats.get("seed_support") != value.get("seed_support"):
            raise ChampionStoreError(f"paired_stats[{split!r}] seed support does not match metadata")
        if stats.get("positive_lift_claimed") is not False:
            raise ChampionStoreError(f"paired_stats[{split!r}] makes a positive-lift claim")
    if paired_stats["confirm"].get("decision_eligible") is not True:
        raise ChampionStoreError("CONFIRM evidence is not decision eligible")
    if paired_stats["holdout"].get("decision_eligible") is not True:
        raise ChampionStoreError("HOLDOUT evidence is not decision eligible")
    _validate_budget_dispatches(budget, paired_stats)

    claims = value.get("claims")
    if claims != {"positive_lift_claimed": False, "production_eligible": False,
                  "holdout_used_for_selection": False, "scope": "research_only"}:
        raise ChampionStoreError("shadow champion claims must remain research-only")
    if value.get("evidence_tier") != "shadow_research":
        raise ChampionStoreError("only shadow_research champions may be stored")
    claimed_digest = str(value.get("metadata_sha256") or "")
    unsigned = dict(value)
    unsigned.pop("metadata_sha256", None)
    if claimed_digest != content_digest(unsigned):
        raise ChampionStoreError("champion metadata digest mismatch")


def _validate_budget_dispatches(
    budget: Mapping[str, Any], paired_stats: Mapping[str, Any],
) -> None:
    rows = budget.get("reservations")
    if not isinstance(rows, list):
        raise ChampionStoreError("campaign budget reservations are missing")
    by_id = {str(row.get("reservation_id")): row for row in rows if isinstance(row, Mapping)}
    expected: set[str] = set()
    for split, stats in paired_stats.items():
        baseline = {str(item) for item in stats.get("expected_baseline_eval_ids", [])}
        candidate = {str(item) for item in stats.get("expected_candidate_eval_ids", [])}
        combined = baseline | candidate
        if (not baseline or not candidate or baseline & candidate
                or combined != {str(item) for item in stats.get("expected_eval_ids", [])}):
            raise ChampionStoreError(f"paired_stats[{split!r}] evaluation arm IDs are invalid")
        expected.update(combined)
        components = {
            **{item: "baseline_eval" if split in {"train", "explore"} else f"{split}_eval" for item in baseline},
            **{item: "candidate_eval" if split in {"train", "explore"} else f"{split}_eval" for item in candidate},
        }
        for eval_id, component in components.items():
            reservation = by_id.get(eval_id)
            if (reservation is None or reservation.get("status") != "settled"
                    or reservation.get("component") != component):
                raise ChampionStoreError(
                    "paired evaluation IDs are not fully bound to settled budget dispatches"
                )
    if not expected:
        raise ChampionStoreError("paired evaluation IDs are missing")
    if not any(isinstance(row, Mapping) and row.get("component") == "mutation"
               and row.get("status") == "settled" for row in rows):
        raise ChampionStoreError("campaign budget has no settled metered mutation operation")


__all__ = ["CHAMPION_SCHEMA", "ChampionConflict", "ChampionStoreError",
           "build_shadow_champion", "json_copy", "utc_now", "validate_shadow_champion"]
