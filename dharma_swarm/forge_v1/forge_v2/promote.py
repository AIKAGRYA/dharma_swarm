"""Promotion packet writer/refuser (Learning Spine v0).

Fails closed. A signal is promotable ONLY if every conjunct of the hard
promotion predicate is true; any missing field is treated as False (not absent =
not assumed-ok). v0 additionally requires a battery of falsification receipts
(preregistration, sequential-alpha, scaffold parity, judge, run-level critic,
mutation sandbox) that the campaign-meta-report-level signal does not yet carry —
so v0 can never promote, by construction. That is correct: the gradient earns
write access by passing the gate, not by self-report.

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


def _evidence_predicate(signal: dict) -> dict:
    """The substantive checks computable from the signal itself."""
    overall = signal.get("overall_ci", {}) or {}
    explore = signal.get("explore_ci", {}) or {}
    confirm = signal.get("confirm_ci", {}) or {}
    contamination = str(signal.get("contamination_state", "unknown"))
    return {
        "receipt_core_present": bool(overall) and bool(confirm),
        "stats_confirm_gate": positive_claim_gate(
            overall, {"explore": explore, "confirm": confirm}
        ),
        "fdr_significant": bool(signal.get("fdr_positive_significant", False)),
        "contamination_self_mod_clean": contamination in _CLEAN_CONTAMINATION,
        "class_null_valid": bool(signal.get("class_null")),
        "null_did_not_survive": not bool(signal.get("null_survived", False)),
        "evidence_strength_positive": float(signal.get("evidence_strength", 0.0)) > 0.0,
    }


def evaluate_promotion(signal: dict) -> dict:
    """Return a promotion packet (decision + predicate + blockers + safety)."""
    evidence = _evidence_predicate(signal)
    # Falsification receipts absent in v0 -> all False (fail closed).
    receipts = {f"receipt_{name}_present": False for name in REQUIRED_RECEIPTS_V0_ABSENT}

    predicate = {**evidence, **receipts}
    failed = sorted(k for k, v in predicate.items() if not v)

    # Surface the signal's own blockers plus the missing receipts, deduped.
    blockers = sorted(
        set(signal.get("promotion_blockers", []) or [])
        | {f"missing:{name}" for name in REQUIRED_RECEIPTS_V0_ABSENT}
    )

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
