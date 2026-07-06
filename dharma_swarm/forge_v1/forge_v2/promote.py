"""Promotion packet writer/refuser (Learning Spine v0).

Fails closed. A signal is promotable ONLY if every conjunct of the hard
promotion predicate is true; any missing field is treated as False (not absent =
not assumed-ok). Promotion additionally requires a battery of falsification
receipts (preregistration, sequential-alpha, scaffold parity, judge, run-level
critic, mutation sandbox). Those receipt predicates are false unless the sole
promotion verifier supplies trusted signed-receipt status.

Even a hypothetically-clean signal yields a SHADOW-ONLY packet in v0
(``live_apply_allowed=false``). The report's ``positive_promotion_allowed`` flag
is echoed but never trusted — the predicate decides.
"""
from __future__ import annotations

from .signals import canonical_sha256
from .stats import positive_claim_gate

# Receipts a real promotion requires but the v0 signal cannot yet supply.
# Listed explicitly so the refusal names exactly what is missing.
REQUIRED_RECEIPTS_V0_ABSENT = (
    "preregistration",
    "sequential_alpha_spending",
    "scaffold_parity_proof",
    "independent_judge",
    "run_level_critic_refutation",
    "mutation_sandbox_proof",
    "budget_matched_proof",
)

_CLEAN_CONTAMINATION = ("fresh_heldout", "self_mod_clean", "clean")
MIN_CONFIRM_N_FOR_PROMOTION = 500
MIN_PROMOTION_EFFECT = 0.05
DEFAULT_PREREGISTERED_MDE = 0.056
PASSING_PACKET_GUARD_VERDICT = "pass_for_next_scale"


def _float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ci_half_width(ci: dict) -> float:
    return max(0.0, (_float(ci.get("upper")) - _float(ci.get("lower"))) / 2.0)


def _preregistered_mde(signal: dict) -> float:
    power = dict(signal.get("power") or signal.get("power_receipt") or {})
    return _float(
        signal.get("pre_registered_mde")
        or signal.get("preregistered_mde")
        or power.get("pre_registered_mde")
        or power.get("mde")
        or DEFAULT_PREREGISTERED_MDE,
        DEFAULT_PREREGISTERED_MDE,
    )


def _sealed_contamination(signal: dict) -> str | None:
    candidates = [
        signal.get("sealed_provenance"),
        signal.get("provenance_receipt"),
        signal.get("contamination_provenance"),
    ]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        state = candidate.get("contamination_state")
        if isinstance(state, dict):
            state = state.get("state")
        if state:
            return str(state)
    return None


def _packet_guard_review(signal: dict) -> dict:
    """Extract the deterministic packet guard review from a signal.

    Promotion treats the deterministic packet guard as part of the fail-closed
    receipt battery.  The optional NVIDIA/NIM review is advisory; it is not used
    as a promotion oracle.
    """
    # The advisory NVIDIA/NIM review must never satisfy this hard conjunct;
    # only the deterministic packet guard keys are accepted.
    candidate = (
        signal.get("packet_guard_review")
        or signal.get("forge_packet_guard")
        or {}
    )
    if not isinstance(candidate, dict):
        return {}
    deterministic = candidate.get("deterministic_review")
    if isinstance(deterministic, dict):
        return deterministic
    return candidate


def _e4_discrimination_receipt(signal: dict) -> dict:
    candidate = (
        signal.get("e4_discrimination_receipt")
        or signal.get("e4_discrimination")
        or {}
    )
    return dict(candidate) if isinstance(candidate, dict) else {}


def _e4_discrimination_passed(receipt: dict) -> bool:
    return bool(receipt.get("promotion_gate_satisfied")) or receipt.get("decision") == "pass"


def _receipt_present(receipt_status: dict | None, name: str) -> bool:
    status = receipt_status or {}
    return bool(status.get(name) or status.get(f"receipt_{name}_present"))


def _receipt_predicates(receipt_status: dict | None = None) -> dict:
    return {
        f"receipt_{name}_present": _receipt_present(receipt_status, name)
        for name in REQUIRED_RECEIPTS_V0_ABSENT
    }


def _evidence_predicate(signal: dict) -> dict:
    """The substantive checks computable from the signal itself."""
    overall = signal.get("overall_ci", {}) or {}
    explore = signal.get("explore_ci", {}) or {}
    confirm = signal.get("confirm_ci", {}) or {}
    contamination = str(signal.get("contamination_state", "unknown"))
    sealed_contamination = _sealed_contamination(signal)
    confirm_n = _int(confirm.get("n"))
    explore_n = _int(explore.get("n"))
    overall_n = _int(overall.get("n"))
    preregistered_mde = _preregistered_mde(signal)
    guard = _packet_guard_review(signal)
    e4_discrimination = _e4_discrimination_receipt(signal)
    return {
        "receipt_core_present": bool(overall) and bool(confirm),
        "stats_confirm_gate": positive_claim_gate(
            overall, {"explore": explore, "confirm": confirm}
        ),
        "e4_confirm_full_500": confirm_n >= MIN_CONFIRM_N_FOR_PROMOTION,
        "e4_no_split_confirm": explore_n == 0 and overall_n == confirm_n and confirm_n > 0,
        "e4_target_effect_ge_5pp": _float(confirm.get("mean")) >= MIN_PROMOTION_EFFECT,
        "e4_confirm_power_sufficient": _ci_half_width(confirm) <= preregistered_mde,
        "fdr_significant": bool(signal.get("fdr_positive_significant", False)),
        "contamination_self_mod_clean": contamination in _CLEAN_CONTAMINATION,
        "contamination_sealed_provenance": (
            sealed_contamination == contamination
            and sealed_contamination in _CLEAN_CONTAMINATION
        ),
        "class_null_valid": bool(signal.get("class_null")),
        "null_did_not_survive": not bool(signal.get("null_survived", False)),
        "evidence_strength_positive": float(signal.get("evidence_strength", 0.0)) > 0.0,
        "packet_guard_review_present": bool(guard),
        "packet_guard_passed": guard.get("verdict") == PASSING_PACKET_GUARD_VERDICT,
        "e4_discrimination_receipt_present": bool(e4_discrimination),
        "e4_discrimination_passed": _e4_discrimination_passed(e4_discrimination),
    }


def evaluate_promotion(signal: dict, *, receipt_status: dict | None = None) -> dict:
    """Return a promotion packet (decision + predicate + blockers + safety)."""
    evidence = _evidence_predicate(signal)
    receipts = _receipt_predicates(receipt_status)

    predicate = {**evidence, **receipts}
    failed = sorted(k for k, v in predicate.items() if not v)

    # Surface the signal's own blockers plus the missing receipts, deduped.
    blockers = sorted(
        set(signal.get("promotion_blockers", []) or [])
        | {
            f"missing:{name}"
            for name in REQUIRED_RECEIPTS_V0_ABSENT
            if not _receipt_present(receipt_status, name)
        }
    )
    guard = _packet_guard_review(signal)
    if not guard:
        blockers.append("missing:packet_guard_review")
    elif guard.get("verdict") != PASSING_PACKET_GUARD_VERDICT:
        findings = guard.get("findings") or []
        guard_codes = [
            str(finding.get("code"))
            for finding in findings
            if isinstance(finding, dict) and finding.get("code")
        ]
        blockers.extend(f"packet_guard:{code}" for code in guard_codes)
        if not guard_codes:
            blockers.append(f"packet_guard:verdict_{guard.get('verdict', 'missing')}")
    e4_discrimination = _e4_discrimination_receipt(signal)
    if not e4_discrimination:
        blockers.append("missing:e4_discrimination_receipt")
    elif not _e4_discrimination_passed(e4_discrimination):
        e4_blockers = [str(item) for item in e4_discrimination.get("blockers", []) or [] if item]
        blockers.extend(f"e4_discrimination:{blocker}" for blocker in e4_blockers)
        if not e4_blockers:
            blockers.append(f"e4_discrimination:decision_{e4_discrimination.get('decision', 'missing')}")
    blockers = sorted(set(blockers))

    promotion_allowed = len(failed) == 0
    decision = "promotable_candidate" if promotion_allowed else "refused"

    payload = {
        "schema": "forge_v2.promotion_packet.v1",
        "decision": decision,
        "arm": signal.get("arm"),
        "taskbed": signal.get("taskbed"),
        "mission_class": signal.get("mission_class"),
        "run_id": signal.get("run_id"),
        "signal_key": signal.get("signal_key"),
        "epoch_id": signal.get("epoch_id"),
        "evidence_strength": signal.get("evidence_strength"),
        "predicate": predicate,
        "failed_conjuncts": failed,
        "blockers": blockers,
        # The trap, echoed but not obeyed.
        "report_positive_promotion_allowed": bool(
            signal.get("report_positive_promotion_allowed", False)
        ),
        "safety": {
            "shadow_only": True,
            "live_apply_allowed": False,
            "code_diff_allowed": False,
        },
    }
    payload["payload_sha256"] = canonical_sha256(payload)
    return payload


def evaluate_signals(signals) -> list[dict]:
    return [evaluate_promotion(s if isinstance(s, dict) else s.to_dict()) for s in signals]


def is_refusal(packet: dict) -> bool:
    return packet.get("decision") == "refused"
