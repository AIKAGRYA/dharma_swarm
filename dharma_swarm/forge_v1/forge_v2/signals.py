"""Typed learning signals from a closed Forge campaign (Learning Spine v0).

This module is PURE: it converts a closed scheduler ``campaign_meta_report.json``
(plus optional enrichment the caller already read) into ``ForgeLearningSignal``
objects. It writes nothing, touches no router/Darwin state, and is deterministic
so the same report always yields the same ``signal_key`` (the idempotency key).

Two fields are kept deliberately SEPARATE (contract trap: a precise-looking score
can still be policy-disqualified):
  * ``evidence_strength`` — a continuous read of how strong the POSITIVE evidence
    is (CONFIRM-weighted). Says nothing about whether promotion is allowed.
  * ``promotion_blockers`` — the list of hard reasons promotion is NOT allowed.

Negative/null results are first-class: every arm in a closed report yields a
signal, including ``measured_negative`` ones, encoded as shadow advice.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

SIGNAL_SCHEMA = "forge_v2.learning_signal.v1"
SIGNAL_TYPE_ARM_CONTRAST = "arm_contrast"

# Shadow advice vocabulary (contract-locked set).
SHADOW_ACTIONS = (
    "downrank_or_ablate",
    "avoid_default_use_on_this_taskbed",
    "hold_for_confirm",
    "quarantine",
    "retry_with_budget_fix",
)

# Contamination states that would NOT block on contamination grounds.
_CLEAN_CONTAMINATION = ("fresh_heldout", "self_mod_clean", "clean")


@dataclass(frozen=True)
class ForgeLearningSignal:
    """One signal per (report, arm). Pure data; no I/O."""

    schema: str
    signal_type: str
    source_report_sha256: str
    run_id: str
    taskbed: str
    mission_class: str
    arm: str
    class_null: str
    inference_scope: str
    epoch_id: str
    # Evidence (carried verbatim from the report so downstream never re-derives).
    overall_ci: dict
    explore_ci: dict
    confirm_ci: dict
    fdr_positive_significant: bool
    reliability: dict
    contamination_state: str
    sealed_provenance: dict
    closeout_counts: dict
    null_survived: bool
    # Echoed report flag — NOT a decision. Present so the trap is visible, not trusted.
    report_positive_promotion_allowed: bool
    # Computed, kept separate on purpose.
    evidence_strength: float
    promotion_blockers: list
    action: str
    next_action_hint: str
    model_set: list = field(default_factory=list)

    @property
    def signal_key(self) -> str:
        """Idempotency key (contract-locked order). ``epoch_id`` is intentionally
        excluded so the key format is stable across epoch tagging."""
        return ":".join(
            [
                self.source_report_sha256,
                self.run_id,
                self.signal_type,
                self.taskbed,
                self.mission_class,
                self.arm,
                self.class_null,
                self.inference_scope,
            ]
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signal_key"] = self.signal_key
        return d


def canonical_sha256(obj) -> str:
    """SHA-256 over canonical JSON bytes — for hashing a report dict deterministically."""
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _ci(d: dict | None) -> dict:
    """Normalise a CI block to the five canonical keys (missing -> conservative)."""
    d = d or {}
    return {
        "n": int(d.get("n", 0)),
        "mean": float(d.get("mean", 0.0)),
        "lower": float(d.get("lower", 0.0)),
        "upper": float(d.get("upper", 0.0)),
        "p_le_0": float(d.get("p_le_0", 1.0)),
    }


def compute_evidence_strength(overall_ci: dict, confirm_ci: dict) -> float:
    """CONFIRM-weighted positive-evidence read in [0, 1].

    Only the POSITIVE part of each lower bound counts — a negative lower bound
    contributes nothing. CONFIRM (frozen held-out) dominates because that is the
    bound a real claim must clear. Seed run -> 0.0 for every arm (all confirm
    lowers are 0.0 and overall lowers are negative)."""
    confirm_part = max(0.0, float(confirm_ci.get("lower", 0.0)))
    overall_part = max(0.0, float(overall_ci.get("lower", 0.0)))
    return round(min(1.0, confirm_part * 0.6 + overall_part * 0.4), 4)


def compute_promotion_blockers(
    *,
    overall_ci: dict,
    confirm_ci: dict,
    fdr_positive_significant: bool,
    contamination_state: str,
    null_survived: bool,
    closeout_counts: dict,
) -> list:
    """Hard reasons promotion is NOT allowed. Independent of evidence_strength."""
    blockers: list = []
    if float(confirm_ci.get("lower", 0.0)) <= 0.0:
        blockers.append("confirm_ci_lower<=0")
    if float(overall_ci.get("lower", 0.0)) <= 0.0:
        blockers.append("overall_ci_lower<=0")
    if not fdr_positive_significant:
        blockers.append("fdr_not_significant")
    if contamination_state not in _CLEAN_CONTAMINATION:
        blockers.append(f"contamination_{contamination_state}")
    if null_survived:
        blockers.append("null_survived")
    # A run with zero positive-lift campaigns cannot source a positive claim.
    if not closeout_counts.get("positive_lift_candidate"):
        blockers.append("no_positive_lift_campaign_in_run")
    return blockers


def choose_action(
    *,
    promotion_blockers: list,
    null_survived: bool,
    explore_ci: dict,
    confirm_ci: dict,
    contamination_state: str,
) -> str:
    """Map evidence to one shadow action from the locked vocabulary."""
    if not promotion_blockers:
        # Clean and promotable on its own terms — still shadow-only downstream.
        return "hold_for_confirm"
    if null_survived:
        return "downrank_or_ablate"
    explore_positive = float(explore_ci.get("mean", 0.0)) > 0.0 and float(
        explore_ci.get("lower", 0.0)
    ) <= 0.0 <= float(explore_ci.get("upper", 0.0))
    confirm_flat = float(confirm_ci.get("upper", 0.0)) <= 0.0
    if explore_positive and confirm_flat:
        # Promising in EXPLORE but unconfirmed -> earn a frozen CONFIRM run.
        return "hold_for_confirm"
    if contamination_state not in _CLEAN_CONTAMINATION:
        return "hold_for_confirm"
    return "avoid_default_use_on_this_taskbed"


def report_to_signals(
    meta_report: dict,
    *,
    source_report_sha256: str,
    run_id: str,
    taskbed: str | None = None,
    mission_class: str | None = None,
    contamination_state: str | None = None,
    class_null: str | None = None,
    epoch_id: str = "epoch_0",
) -> list[ForgeLearningSignal]:
    """Convert a closed campaign_meta_report into one signal per tested arm.

    The meta report is the primary input. ``taskbed``/``mission_class``/
    ``class_null`` may be enriched by the caller. ``contamination_state`` is kept
    as a backward-compatible conservative hint only: clean states are ignored
    unless sealed provenance in the report says the same thing.  A caller kwarg
    can no longer launder public SWE-bench into ``clean``.
    """
    contrasts = meta_report.get("contrasts", {}) or {}
    closeout_counts = dict(meta_report.get("closeout_counts", {}) or {})
    inference_scope = str(meta_report.get("inference_scope", "unknown"))
    learning_state = meta_report.get("learning_state", {}) or {}
    null_survived_arms = set(learning_state.get("null_survived_arms", []) or [])
    reliability_all = meta_report.get("reliability", {}) or {}
    next_policy = meta_report.get("next_policy", {}) or {}
    recommended_arms = next_policy.get("recommended_arms", []) or []
    promo_flag = bool(
        (meta_report.get("promotion_policy", {}) or {}).get("positive_promotion_allowed", False)
    )

    # Conservative derivations (documented; overridable by caller enrichment).
    label = str((meta_report.get("scheduler", {}) or {}).get("label", "") or "")
    derived_mission = mission_class or (label.split("overnight_", 1)[-1] if label else "unknown")
    derived_taskbed = taskbed or _derive_taskbed(meta_report)
    # Absent sealed contamination on a public benchmark -> possible_pretrain
    # (a blocker), never caller-supplied "clean".
    sealed_contam = _sealed_contamination(meta_report)
    derived_contam = _derive_contamination(meta_report, external_hint=contamination_state)
    sealed_provenance = (
        {
            "contamination_state": sealed_contam,
            "source": "closed_report",
            "source_report_sha256": source_report_sha256,
        }
        if sealed_contam
        else {}
    )
    derived_class_null = class_null or _derive_class_null(meta_report)

    signals: list[ForgeLearningSignal] = []
    for arm in meta_report.get("arms_tested", []) or []:
        block = contrasts.get(arm, {}) or {}
        overall = _ci(block.get("overall"))
        by_split = block.get("by_split", {}) or {}
        explore = _ci(by_split.get("explore"))
        confirm = _ci(by_split.get("confirm"))
        fdr_sig = bool(block.get("fdr_positive_significant", False))
        null_survived = arm in null_survived_arms

        blockers = compute_promotion_blockers(
            overall_ci=overall,
            confirm_ci=confirm,
            fdr_positive_significant=fdr_sig,
            contamination_state=derived_contam,
            null_survived=null_survived,
            closeout_counts=closeout_counts,
        )
        strength = compute_evidence_strength(overall, confirm)
        action = choose_action(
            promotion_blockers=blockers,
            null_survived=null_survived,
            explore_ci=explore,
            confirm_ci=confirm,
            contamination_state=derived_contam,
        )
        signals.append(
            ForgeLearningSignal(
                schema=SIGNAL_SCHEMA,
                signal_type=SIGNAL_TYPE_ARM_CONTRAST,
                source_report_sha256=source_report_sha256,
                run_id=run_id,
                taskbed=derived_taskbed,
                mission_class=derived_mission,
                arm=arm,
                class_null=derived_class_null,
                inference_scope=inference_scope,
                epoch_id=epoch_id,
                overall_ci=overall,
                explore_ci=explore,
                confirm_ci=confirm,
                fdr_positive_significant=fdr_sig,
                reliability=dict(reliability_all.get(arm, {}) or {}),
                contamination_state=derived_contam,
                sealed_provenance=sealed_provenance,
                closeout_counts=closeout_counts,
                null_survived=null_survived,
                report_positive_promotion_allowed=promo_flag,
                evidence_strength=strength,
                promotion_blockers=blockers,
                action=action,
                next_action_hint=", ".join(str(a) for a in recommended_arms),
                model_set=[],
            )
        )
    return signals


def _derive_taskbed(meta_report: dict) -> str:
    """Best-effort taskbed label without inventing facts. SWE-bench task ids look
    like ``django__django-12209`` / ``sympy__sympy-22914``."""
    task_stats = meta_report.get("task_stats", {}) or {}
    if any("__" in str(k) for k in task_stats):
        return "public_swebench"
    label = str((meta_report.get("scheduler", {}) or {}).get("label", "") or "")
    return label or "unknown_taskbed"


def _sealed_contamination(meta_report: dict) -> str | None:
    """Extract contamination only from report/provenance fields that are part of
    the closed receipt.  This is the promotion-relevant source of truth."""
    candidates = [
        meta_report.get("contamination_state"),
        (meta_report.get("provenance") or {}).get("contamination_state"),
        (meta_report.get("sealed_provenance") or {}).get("contamination_state"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            state = candidate.get("state")
        else:
            state = candidate
        if state:
            return str(state)
    return None


def _derive_contamination(meta_report: dict, *, external_hint: str | None = None) -> str:
    """Derive contamination fail-closed from sealed provenance and taskbed.

    ``external_hint`` is accepted only when it is conservative.  Clean hints are
    ignored unless the closed report itself carries sealed clean provenance.
    """
    sealed = _sealed_contamination(meta_report)
    if sealed:
        return sealed
    if external_hint and external_hint not in _CLEAN_CONTAMINATION:
        return str(external_hint)
    if _derive_taskbed(meta_report) == "public_swebench":
        return "possible_pretrain"
    return "unknown"


def _derive_class_null(meta_report: dict) -> str:
    task_stats = meta_report.get("task_stats", {}) or {}
    for v in task_stats.values():
        cn = (v or {}).get("class_null")
        if cn:
            return str(cn)
    return "self_moa"
