"""Policy compiler for DHARMA SWARM.

Compiles kernel principles and accepted claims into a unified Policy
that can evaluate actions against dharmic constraints. Immutable rules
(from the kernel) always override mutable rules (from the corpus).

v2: Three-tier evaluation replaces naive keyword matching:
  Tier 1 -- Structured predicates (deterministic field evaluation)
  Tier 2 -- Semantic similarity via hash-embed cosine (paraphrase-aware)
  Tier 3 -- Graduated enforcement (block / warn / no-match by similarity)
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from dharma_swarm.fourfold_action_warrant import (
    FourfoldActionWarrant,
    trigger_reasons_for_action,
)
from dharma_swarm.models import GateDecision
from dharma_swarm.models import _utc_now
from dharma_swarm.structured_predicate import (
    CompoundPredicate,
    StructuredPredicate,
    evaluate_compound,
    evaluate_predicate,
    semantic_similarity,
)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

EnforcementLevel = Literal["block", "warn", "log", "gate_human"]

_SEVERITY_TO_ENFORCEMENT: dict[str, EnforcementLevel] = {
    "critical": "block",
    "high": "warn",
    "medium": "log",
}

# Tier 3 graduated thresholds -- calibrated to _hash_embed cosine distribution.
# The hash-embed method yields ~0.77 for near-identical strings with
# added stopwords (e.g. "delete production database" vs "delete the production
# database now"), so 0.7 is the correct block boundary for this embedding.
_SIMILARITY_BLOCK_THRESHOLD = 0.7
_SIMILARITY_WARN_THRESHOLD = 0.45
FOURFOLD_ACTION_WARRANT_GATE_ENV = "DHARMA_FOURFOLD_ACTION_WARRANT_GATE"
FOURFOLD_ACTION_WARRANT_METADATA_KEY = "fourfold_action_warrant"
FOURFOLD_ACTION_WARRANT_LEGACY_METADATA_KEY = "fourfold_warrant"
FOURFOLD_ACTION_WARRANT_RULE_SOURCE = "kernel:fourfold_action_warrant"


class PolicyRule(BaseModel):
    """A single rule inside a compiled policy."""

    source: str
    rule_text: str
    weight: float = Field(ge=0.0, le=1.0)
    is_immutable: bool
    enforcement_level: EnforcementLevel
    structured_predicate: Optional[StructuredPredicate] = None
    compound_predicate: Optional[CompoundPredicate] = None


class PolicyDecision(BaseModel):
    """Result of checking an action against a policy."""

    allowed: bool
    violated_rules: list[PolicyRule] = Field(default_factory=list)
    warnings: list[PolicyRule] = Field(default_factory=list)
    reason: str = ""


class Policy(BaseModel):
    """A compiled set of rules ready for action evaluation."""

    rules: list[PolicyRule] = Field(default_factory=list)
    context: str = ""
    compiled_at: str = Field(default_factory=lambda: _utc_now().isoformat())

    def get_immutable_rules(self) -> list[PolicyRule]:
        """Return all immutable (kernel-derived) rules."""
        return [r for r in self.rules if r.is_immutable]

    def get_mutable_rules(self) -> list[PolicyRule]:
        """Return all mutable (corpus-derived) rules."""
        return [r for r in self.rules if not r.is_immutable]

    def check_action(
        self,
        action: str,
        context: str = "",
        action_metadata: dict[str, Any] | None = None,
        *,
        enforce_fourfold_warrant: bool | None = None,
    ) -> PolicyDecision:
        """Evaluate an action against all policy rules using three-tier matching.

        Tier 1 -- Structured predicate: If the rule has a structured_predicate
            (or compound_predicate), evaluate it against action_metadata.
            This is deterministic and precise. A match here is authoritative.

        Tier 2 -- Semantic similarity: For rules without structured predicates,
            compute hash-based cosine similarity between rule_text and the
            combined action+context string.

        Tier 3 -- Graduated enforcement:
            - similarity >= 0.8 + enforcement="block" -> block
            - similarity >= 0.6 + enforcement in ("block","warn") -> warn
            - similarity < 0.6 -> no match

        Blocking logic (unchanged from v1):
        - Immutable rule with enforcement_level="block" -> not allowed.
        - Mutable rule with enforcement_level="block" and weight > 0.7 -> not allowed.

        Args:
            action: The action string to evaluate.
            context: Optional free-text context for the action.
            action_metadata: Optional dict of structured metadata for Tier 1
                evaluation (e.g. {"evaluator_count": 1, "action_type": "destructive"}).
            enforce_fourfold_warrant: Optional explicit override for the
                Fourfold Action Warrant runtime gate. If omitted, the
                ``DHARMA_FOURFOLD_ACTION_WARRANT_GATE`` environment flag
                controls enforcement.

        Returns:
            PolicyDecision with allowed flag, violated rules, warnings, and reason.
        """
        metadata = action_metadata or {}
        warrant_decision = _check_fourfold_action_warrant_gate(
            action,
            context,
            metadata,
            enforce=enforce_fourfold_warrant,
        )
        if warrant_decision is not None:
            return warrant_decision

        combined = (action + " " + context).lower()
        violated: list[PolicyRule] = []
        warned: list[PolicyRule] = []

        for rule in self.rules:
            matched = False

            # --- Tier 1: Structured predicate evaluation ---
            if rule.compound_predicate is not None:
                matched = evaluate_compound(rule.compound_predicate, metadata)
            elif rule.structured_predicate is not None:
                matched = evaluate_predicate(rule.structured_predicate, metadata)

            if matched:
                violated.append(rule)
                continue

            # If structured predicate exists but didn't match, skip Tier 2/3.
            # The predicate is authoritative when present.
            if rule.structured_predicate is not None or rule.compound_predicate is not None:
                continue

            # --- Tier 2/3: Semantic similarity for prose rules ---
            if not rule.rule_text.strip():
                continue

            sim = semantic_similarity(rule.rule_text, combined)

            if sim >= _SIMILARITY_BLOCK_THRESHOLD:
                # Strong match -> treat as violation
                violated.append(rule)
            elif sim >= _SIMILARITY_WARN_THRESHOLD:
                # Moderate match -> treat as warning
                warned.append(rule)

        # --- Blocking logic (same as v1) ---
        blocked = False
        reasons: list[str] = []

        for rule in violated:
            if rule.enforcement_level == "block":
                if rule.is_immutable:
                    blocked = True
                    reasons.append(
                        f"immutable block: {rule.source}"
                    )
                elif rule.weight > 0.7:
                    blocked = True
                    reasons.append(
                        f"mutable block (weight={rule.weight}): {rule.source}"
                    )

        return PolicyDecision(
            allowed=not blocked,
            violated_rules=violated,
            warnings=warned,
            reason="; ".join(reasons) if reasons else "",
        )


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------


class PolicyCompiler:
    """Stateless compiler that fuses kernel principles and corpus claims."""

    def compile(
        self,
        kernel_principles: dict[str, Any],
        accepted_claims: list[Any],
        context: str = "",
    ) -> Policy:
        """Compile kernel principles and accepted claims into a Policy.

        Args:
            kernel_principles: Mapping of name -> principle object. Each
                principle must expose ``name``, ``description``,
                ``formal_constraint``, and ``severity`` attributes.
                Optionally exposes ``structured_predicate`` (dict or
                StructuredPredicate) for Tier 1 evaluation.
            accepted_claims: List of claim objects. Each must expose
                ``id``, ``statement``, ``confidence``, and ``enforcement``
                attributes.
            context: Free-text description of what this policy is for.

        Returns:
            A Policy with immutable rules (from kernel) sorted before
            mutable rules (from claims), ordered by weight descending
            within each group.
        """
        immutable_rules: list[PolicyRule] = []
        mutable_rules: list[PolicyRule] = []

        for name, principle in kernel_principles.items():
            severity: str = getattr(principle, "severity", "medium")
            enforcement = _SEVERITY_TO_ENFORCEMENT.get(severity, "log")

            # Extract structured predicate if present
            sp = _extract_structured_predicate(principle)
            cp = _extract_compound_predicate(principle)

            rule = PolicyRule(
                source=f"kernel:{name}",
                rule_text=getattr(principle, "formal_constraint", ""),
                weight=1.0,
                is_immutable=True,
                enforcement_level=enforcement,
                structured_predicate=sp,
                compound_predicate=cp,
            )
            immutable_rules.append(rule)

        for claim in accepted_claims:
            sp = _extract_structured_predicate(claim)
            cp = _extract_compound_predicate(claim)

            rule = PolicyRule(
                source=f"corpus:{getattr(claim, 'id', 'unknown')}",
                rule_text=getattr(claim, "statement", ""),
                weight=float(getattr(claim, "confidence", 0.5)),
                is_immutable=False,
                enforcement_level=getattr(claim, "enforcement", "log"),
                structured_predicate=sp,
                compound_predicate=cp,
            )
            mutable_rules.append(rule)

        # Sort: immutable first, then mutable -- each group by weight desc.
        immutable_rules.sort(key=lambda r: r.weight, reverse=True)
        mutable_rules.sort(key=lambda r: r.weight, reverse=True)

        return Policy(
            rules=immutable_rules + mutable_rules,
            context=context,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_structured_predicate(obj: Any) -> StructuredPredicate | None:
    """Extract a StructuredPredicate from an object, if present."""
    raw = getattr(obj, "structured_predicate", None)
    if raw is None:
        return None
    if isinstance(raw, StructuredPredicate):
        return raw
    if isinstance(raw, dict):
        try:
            return StructuredPredicate(**raw)
        except Exception:
            return None
    return None


def _extract_compound_predicate(obj: Any) -> CompoundPredicate | None:
    """Extract a CompoundPredicate from an object, if present."""
    raw = getattr(obj, "compound_predicate", None)
    if raw is None:
        return None
    if isinstance(raw, CompoundPredicate):
        return raw
    if isinstance(raw, dict):
        try:
            return CompoundPredicate(**raw)
        except Exception:
            return None
    return None


def fourfold_action_warrant_gate_enabled() -> bool:
    """Whether the opt-in Fourfold Action Warrant runtime gate is active."""

    value = os.getenv(FOURFOLD_ACTION_WARRANT_GATE_ENV, "")
    return value.strip().lower() in {"1", "true", "yes", "on", "enforce", "block"}


def _check_fourfold_action_warrant_gate(
    action: str,
    context: str,
    metadata: dict[str, Any],
    *,
    enforce: bool | None,
) -> PolicyDecision | None:
    if enforce is None:
        enforce = fourfold_action_warrant_gate_enabled()
    if not enforce:
        return None

    trigger_reasons = trigger_reasons_for_action(action, context, metadata)
    if not trigger_reasons:
        return None

    warrant, load_error = _load_fourfold_action_warrant(metadata)
    if warrant is None:
        return _fourfold_action_warrant_block(
            trigger_reasons,
            load_error or "missing_fourfold_action_warrant",
        )

    if not warrant.required:
        return _fourfold_action_warrant_block(
            trigger_reasons,
            "stale_or_irrelevant_fourfold_action_warrant",
        )

    missing_reasons = sorted(set(trigger_reasons) - set(warrant.trigger_reasons))
    if missing_reasons:
        return _fourfold_action_warrant_block(
            trigger_reasons,
            "warrant_missing_trigger_reasons:" + ",".join(missing_reasons),
        )

    if warrant.decision is GateDecision.ALLOW:
        return None

    reason = f"fourfold_action_warrant_{warrant.decision.value}"
    if warrant.blockers:
        reason += ": " + ",".join(warrant.blockers)
    return _fourfold_action_warrant_block(trigger_reasons, reason)


def _load_fourfold_action_warrant(
    metadata: dict[str, Any],
) -> tuple[FourfoldActionWarrant | None, str | None]:
    for key in (
        FOURFOLD_ACTION_WARRANT_METADATA_KEY,
        FOURFOLD_ACTION_WARRANT_LEGACY_METADATA_KEY,
    ):
        if key not in metadata:
            continue
        raw = metadata[key]
        if isinstance(raw, FourfoldActionWarrant):
            return raw, None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                return None, "invalid_fourfold_action_warrant_json"
        try:
            return FourfoldActionWarrant.model_validate(raw), None
        except (TypeError, ValidationError, ValueError):
            return None, "invalid_fourfold_action_warrant"
    return None, "missing_fourfold_action_warrant"


def _fourfold_action_warrant_block(
    trigger_reasons: list[str],
    detail: str,
) -> PolicyDecision:
    rule = PolicyRule(
        source=FOURFOLD_ACTION_WARRANT_RULE_SOURCE,
        rule_text="high-authority actions require an allowing Fourfold Action Warrant",
        weight=1.0,
        is_immutable=True,
        enforcement_level="block",
    )
    return PolicyDecision(
        allowed=False,
        violated_rules=[rule],
        reason=(
            "fourfold action warrant gate: "
            f"{detail}; triggers={','.join(trigger_reasons)}"
        ),
    )
