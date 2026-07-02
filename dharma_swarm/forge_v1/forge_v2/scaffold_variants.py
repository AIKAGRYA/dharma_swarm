"""Phase 4 Track A scaffold/genome variant generator with static sanity checks.

The RSI Lab v2.2 Track A candidate lifecycle is:

    sample parent genome
    -> mutate one or two fields
    -> static sanity check
    -> run on tiny EXPLORE slice
    -> compare against baseline under same budget
    -> archive if non-broken
    -> promote only via confirm gate

This module owns the deterministic, budget-free front half of that lifecycle:
it enumerates one- or two-field mutations of a parent genome and statically
validates them, so a caller can archive 10-30 candidates via
``phase4_alpha.archive_scaffold_candidate`` before spending any grade budget.

It never calls a model, never grades, never applies patches, and never opens a
promotion gate.  Static rejection is a first-class, receipt-backed outcome, not
an exception.  Model self-report is irrelevant here: a genome is judged only by
its own field values against the known scaffold surface.
"""
from __future__ import annotations

import itertools
from typing import Any, Iterable

from .signals import canonical_sha256

SCHEMA_VERSION = "forge_v2.scaffold_variants.v1"

# Valid tested-arm surface.  ``self_moa`` is the class-null arm that every
# campaign runs for paired control; it is a valid selection strategy but not a
# standalone tested candidate arm in the current Forge runner.  Marking it
# broken here prevents Track A from spending grade budget on a no-op
# self_moa-vs-self_moa scaffold.
VALID_ARMS = frozenset({"verify_chain", "mixed_moa"})
VALID_SELECTION_STRATEGIES = frozenset({"self_moa", "mixed_moa", "verify_chain"})

# Bounds for numeric context policy.  The first-slice arms window every model to
# DEFAULT_WINDOW_CHARS=11000; a candidate window outside a sane band is either a
# no-op or a budget hazard, so it is statically rejected.
MIN_WINDOW_CHARS = 2_000
MAX_WINDOW_CHARS = 24_000

# Mutation menu: each entry is (field, value).  These are pure scaffold/genome
# fields (Workstream 3), never source code.  Values are deliberately conservative
# so the generated set is enumerable and reviewable.
_MUTATION_MENU: dict[str, tuple[Any, ...]] = {
    "arm": ("self_moa", "verify_chain", "mixed_moa"),
    "selection_strategy": ("self_moa", "verify_chain", "mixed_moa"),
    "window_chars": (7_000, 9_000, 11_000, 14_000),
    "verifier": (
        "kimi-k2.7-code:cloud",
        "deepseek-v4-pro:cloud",
        "qwen3-coder:480b-cloud",
    ),
    "retry_policy": ("none", "single_repair"),
    "patch_format_policy": ("search_replace", "unified_diff"),
}


def _genome_key(genome: dict[str, Any]) -> str:
    return canonical_sha256({k: genome[k] for k in sorted(genome)})


def static_sanity_check(genome: dict[str, Any]) -> dict[str, Any]:
    """Return a fail-closed static sanity receipt for a scaffold genome.

    A genome is ``ok`` only when every populated field it carries is within the
    known scaffold surface.  Unknown-but-harmless free-text fields (generator id,
    label, prompt-variant text) are allowed; structurally meaningful fields are
    range/enum checked.
    """
    blockers: list[str] = []

    arm = str(genome.get("arm", "")).strip()
    if not arm:
        blockers.append("missing_arm")
    elif arm not in VALID_ARMS:
        blockers.append(f"invalid_arm:{arm}")

    selection = genome.get("selection_strategy")
    if selection is not None and str(selection) not in VALID_SELECTION_STRATEGIES:
        blockers.append(f"invalid_selection_strategy:{selection}")

    window = genome.get("window_chars")
    if window is not None:
        try:
            window_int = int(window)
        except (TypeError, ValueError):
            blockers.append(f"non_integer_window_chars:{window!r}")
        else:
            if not (MIN_WINDOW_CHARS <= window_int <= MAX_WINDOW_CHARS):
                blockers.append(
                    f"window_chars_out_of_band:{window_int}(allowed {MIN_WINDOW_CHARS}-{MAX_WINDOW_CHARS})"
                )

    generator = str(genome.get("generator", "")).strip()
    if not generator:
        blockers.append("missing_generator")

    # A verify_chain genome must name a verifier; a mixed_moa genome must name
    # mix models.  Otherwise the arm cannot express its intended contrast.
    if arm == "verify_chain" and not str(genome.get("verifier", "")).strip():
        blockers.append("verify_chain_requires_verifier")
    if arm == "mixed_moa" and not (genome.get("mix_models") or []):
        blockers.append("mixed_moa_requires_mix_models")

    return {
        "schema": f"{SCHEMA_VERSION}.static_check",
        "ok": not blockers,
        "blockers": blockers,
        "genome_sha256": _genome_key(genome),
    }


def _apply_mutation(parent: dict[str, Any], field: str, value: Any) -> dict[str, Any]:
    child = dict(parent)
    child[field] = value
    return child


def generate_variants(
    parent: dict[str, Any],
    *,
    max_variants: int = 30,
    max_fields_per_mutation: int = 2,
    include_broken: bool = True,
) -> dict[str, Any]:
    """Enumerate one- or two-field mutations of ``parent`` with static receipts.

    Returns a summary dict containing every distinct candidate genome, each with
    its static sanity receipt and mutation description.  Deterministic ordering
    (single-field mutations first, then two-field) keeps the set reviewable and
    reproducible.  ``include_broken=True`` keeps statically-rejected variants in
    the output so their rejection is receipted (objective: archive all
    candidates; every run writes receipts).
    """
    if max_variants <= 0:
        raise ValueError("max_variants must be positive")
    if max_fields_per_mutation not in (1, 2):
        raise ValueError("max_fields_per_mutation must be 1 or 2")

    parent = dict(parent)
    parent_key = _genome_key(parent)
    seen: set[str] = {parent_key}
    variants: list[dict[str, Any]] = []

    single_mutations: list[tuple[tuple[str, Any], ...]] = []
    for field, values in _MUTATION_MENU.items():
        for value in values:
            if parent.get(field) == value:
                continue
            single_mutations.append(((field, value),))

    combos: list[tuple[tuple[str, Any], ...]] = list(single_mutations)
    if max_fields_per_mutation == 2:
        for left, right in itertools.combinations(single_mutations, 2):
            (lf, _), (rf, _) = left[0], right[0]
            if lf == rf:
                continue
            combos.append((left[0], right[0]))

    for mutation in combos:
        if len(variants) >= max_variants:
            break
        child = dict(parent)
        described: list[str] = []
        for field, value in mutation:
            child = _apply_mutation(child, field, value)
            described.append(f"{field}={value}")
        key = _genome_key(child)
        if key in seen:
            continue
        seen.add(key)
        check = static_sanity_check(child)
        if not check["ok"] and not include_broken:
            continue
        variants.append(
            {
                "genome": child,
                "mutation_description": "; ".join(described),
                "mutated_fields": [field for field, _ in mutation],
                "static_check": check,
                "candidate_key": key,
            }
        )

    ok = [v for v in variants if v["static_check"]["ok"]]
    broken = [v for v in variants if not v["static_check"]["ok"]]
    return {
        "schema": f"{SCHEMA_VERSION}.generation",
        "parent_genome": parent,
        "parent_sha256": parent_key,
        "requested_max_variants": max_variants,
        "max_fields_per_mutation": max_fields_per_mutation,
        "variant_count": len(variants),
        "static_ok_count": len(ok),
        "static_broken_count": len(broken),
        "variants": variants,
    }


def archive_generated_variants(
    generation: dict[str, Any],
    *,
    archive_root: Any,
    parent_id: str | None = None,
    receipt_links: Iterable[str] = (),
) -> dict[str, Any]:
    """Archive every generated variant through the Phase 4 scaffold archive.

    A statically-ok variant is archived as an unevaluated scaffold candidate
    (closeout ``static_ok_unevaluated``); a statically-broken variant is archived
    with closeout ``blocked_with_evidence`` so its rejection is receipted.  No
    grading or promotion happens here.
    """
    from . import phase4_alpha

    results: list[dict[str, Any]] = []
    for variant in generation.get("variants", []):
        check = variant["static_check"]
        closeout = "static_ok_unevaluated" if check["ok"] else "blocked_with_evidence"
        result = phase4_alpha.archive_scaffold_candidate(
            archive_root=archive_root,
            parent_id=parent_id,
            genome=variant["genome"],
            mutation_description=variant["mutation_description"],
            evaluation={
                "closeout": closeout,
                "static_check": check,
                "evaluated": False,
                "note": "static-only Track A variant; not yet EXPLORE-graded",
            },
            receipt_links=list(receipt_links),
            reason=(
                "static sanity ok; queued for EXPLORE"
                if check["ok"]
                else "; ".join(check["blockers"])
            ),
        )
        results.append({**result, "candidate_key": variant["candidate_key"], "static_ok": check["ok"]})
    return {
        "schema": f"{SCHEMA_VERSION}.archive",
        "archived": len(results),
        "static_ok": sum(1 for r in results if r["static_ok"]),
        "static_broken": sum(1 for r in results if not r["static_ok"]),
        "results": results,
    }


__all__ = [
    "MAX_WINDOW_CHARS",
    "MIN_WINDOW_CHARS",
    "SCHEMA_VERSION",
    "VALID_ARMS",
    "VALID_SELECTION_STRATEGIES",
    "archive_generated_variants",
    "generate_variants",
    "static_sanity_check",
]
