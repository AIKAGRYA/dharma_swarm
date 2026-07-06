"""The two first-slice arms: self_moa (class_null) vs verify_chain.

INVARIANTS baked in:
- Generator-identity pin: verify_chain's generator is the SAME slot as self_moa's
  model. The ONLY delta is the added cross-family verifier.
- No-oracle-selection: neither arm uses the Docker grade to select. self_moa
  selects via a synthesis pass (a model, not the hidden tests). Each arm yields ONE
  final patch, graded once by the runner.
- Total-system budget: every model call charges the Budget by component; the
  verifier's tokens count against verify_chain. Over cap -> Budget.invalid.
"""
from __future__ import annotations

from dharma_swarm.forge_v1.canonical import _propose_slot

from .budget import Budget

# Shared per-step scaffold templates (parity: both arms generate with the SAME
# base repair prompt; the only difference is the verifier step). Used for the
# scaffold_parity_hash.
GEN_TEMPLATE = "<forge_v1.build_repair_prompt base>"
SYNTH_TEMPLATE = ("You produced these candidate fixes (unified diffs). Synthesize the SINGLE best, "
                  "correct, minimal fix and output it as SEARCH/REPLACE edit block(s) only.")
VERIFY_TEMPLATE = ("Another engineer proposed this patch. Review it. If correct, reproduce it exactly. "
                   "If wrong, output the corrected SEARCH/REPLACE block(s). Output only the block(s).")
DEFAULT_WINDOW_CHARS = 11000


def _is_free_route(slot) -> bool:
    provider = getattr(slot, "provider", "")
    prov = getattr(provider, "value", str(provider))
    return prov in ("ollama", "openrouter_free") or str(slot.model_id).endswith((":cloud", ":free"))


def _win(slot, window_chars: int | None = None):
    # First-slice runs must fit the matched budget on large SWE-bench contexts.
    # Use the same bounded window for all providers in a campaign.  Track A
    # scaffold/genome evolution may mutate this context policy, but the override
    # must be applied symmetrically to the class-null and tested arm so budget
    # parity remains meaningful.
    return int(DEFAULT_WINDOW_CHARS if window_chars is None else window_chars)


def self_moa_arm(generator, inst, ctx, budget: Budget, *, k: int, per_call_tokens: int,
                 timeout_s: int, window_chars: int | None = None) -> dict:
    """Same model, k independent samples, then a SYNTHESIS pass selects/merges the
    best (NOT the Docker oracle). The headline null baseline."""
    candidates = []
    for i in range(k):
        rec = _propose_slot(generator, inst, ctx, max_tokens=per_call_tokens, timeout_s=timeout_s,
                            window_chars=_win(generator, window_chars))
        budget.charge("generation", rec["tokens"], is_free_route=_is_free_route(generator))
        if rec["patch"].strip():
            candidates.append(rec["patch"])
        if budget.invalid:
            break
    final_patch = candidates[0] if candidates else ""
    if candidates and not budget.invalid:
        synth_instr = (SYNTH_TEMPLATE + "\n\n" + "\n\n--- candidate ---\n".join(c[:1500] for c in candidates[:4]))
        srec = _propose_slot(generator, inst, ctx, max_tokens=per_call_tokens, timeout_s=timeout_s,
                            window_chars=_win(generator, window_chars), extra_instruction=synth_instr)
        budget.charge("selection", srec["tokens"], is_free_route=_is_free_route(generator))
        if srec["patch"].strip():
            final_patch = srec["patch"]
    return {"arm": "self_moa", "final_patch": final_patch, "n_candidates": len(candidates)}


def verify_chain_arm(generator, verifier, inst, ctx, budget: Budget, *, per_call_tokens: int,
                     timeout_s: int, window_chars: int | None = None) -> dict:
    """Generator (SAME model as self_moa) produces a patch; an independent
    CROSS-FAMILY verifier reviews/repairs it. One final patch, graded once."""
    grec = _propose_slot(generator, inst, ctx, max_tokens=per_call_tokens, timeout_s=timeout_s,
                        window_chars=_win(generator, window_chars))
    budget.charge("generation", grec["tokens"], is_free_route=_is_free_route(generator))
    final_patch = grec["patch"]
    if final_patch.strip() and not budget.invalid:
        vrec = _propose_slot(verifier, inst, ctx, max_tokens=per_call_tokens, timeout_s=timeout_s,
                            window_chars=_win(verifier, window_chars),
                            extra_instruction=VERIFY_TEMPLATE + "\n\nProposed patch:\n" + final_patch[:2000])
        budget.charge("verification", vrec["tokens"], is_free_route=_is_free_route(verifier))
        if vrec["patch"].strip():
            final_patch = vrec["patch"]
    return {"arm": "verify_chain", "final_patch": final_patch, "generator": generator.model_id,
            "verifier": verifier.model_id}


def mixed_moa_arm(generators, selector, inst, ctx, budget: Budget, *, per_call_tokens: int,
                  timeout_s: int, window_chars: int | None = None) -> dict:
    """Cross-model mixture-of-agents control.

    Each callable generator gets one independent sample under the same total
    budget broker; the selector then synthesizes one final patch. This is the
    diversity hypothesis arm and is intentionally contrasted against self_moa,
    not used as an oracle over Docker grades.
    """
    candidates = []
    model_ids = []
    for slot in generators:
        rec = _propose_slot(slot, inst, ctx, max_tokens=per_call_tokens, timeout_s=timeout_s,
                            window_chars=_win(slot, window_chars))
        budget.charge("generation", rec["tokens"], is_free_route=_is_free_route(slot))
        model_ids.append(slot.model_id)
        if rec["patch"].strip():
            candidates.append((slot.model_id, rec["patch"]))
        if budget.invalid:
            break

    final_patch = candidates[0][1] if candidates else ""
    if candidates and not budget.invalid:
        synth_instr = (
            SYNTH_TEMPLATE
            + "\n\nCandidate patches from different model families follow. "
              "Synthesize the SINGLE best minimal fix. Do not mention the candidates.\n\n"
            + "\n\n--- candidate ---\n".join(
                f"model: {model_id}\n{patch[:1500]}" for model_id, patch in candidates[:6]
            )
        )
        srec = _propose_slot(selector, inst, ctx, max_tokens=per_call_tokens, timeout_s=timeout_s,
                             window_chars=_win(selector, window_chars), extra_instruction=synth_instr)
        budget.charge("selection", srec["tokens"], is_free_route=_is_free_route(selector))
        if srec["patch"].strip():
            final_patch = srec["patch"]
    return {"arm": "mixed_moa", "final_patch": final_patch, "models": model_ids,
            "selector": selector.model_id, "n_candidates": len(candidates)}
