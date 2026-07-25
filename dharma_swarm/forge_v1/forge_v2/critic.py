"""Cross-family adversarial critics (contract invariant 2 + step 7).

For any POSITIVE interpretation (arm beat its class_null), N critics from
DIFFERENT model families are each prompted to REFUTE it. Majority-refute kills
promotion. Critics default to refuted=true when uncertain (burden of proof is on
the swarm). A negative result needs no critic pass — the null already survived.
"""
from __future__ import annotations

import json

from dharma_swarm.forge_v1.canonical import _call, _provider_for_slot, pool_slots, KIMI_TEMP1


def _family(model_id: str) -> str:
    m = model_id.lower()
    for fam in ("gemini", "glm", "kimi", "minimax", "deepseek", "qwen", "gpt", "claude", "llama", "mistral", "gemma"):
        if fam in m:
            return fam
    return m.split("/")[0]


def refute_pass(claim: str, evidence: dict, *, generator_family: str, n: int = 3,
                timeout_s: int = 90) -> dict:
    """Run up to n cross-family critics. Returns {refuted_majority, votes}."""
    # pick n callable slots whose family != generator's
    slots = pool_slots(n=16, strategy="explore")
    seen, critics = set(), []
    for s in slots:
        fam = _family(s.model_id)
        if fam == generator_family or fam in seen:
            continue
        seen.add(fam)
        critics.append(s)
        if len(critics) >= n:
            break

    votes = []
    prompt = (
        "You are an adversarial statistical reviewer. Your job is to REFUTE the following "
        "claim about a benchmark experiment. Default to refuted=true if the evidence is weak, "
        "under-powered, confounded, or contamination-suspect.\n\n"
        f"CLAIM: {claim}\n\nEVIDENCE (JSON):\n{json.dumps(evidence, indent=2, default=str)}\n\n"
        "Consider: sample size / statistical power, CI lower bound vs 0, contamination, budget "
        "matching, selection bias, replicate variance. Respond with ONLY a JSON object: "
        '{\"refuted\": true|false, \"reason\": \"<one sentence>\"}'
    )
    for s in critics:
        try:
            prov, wire = _provider_for_slot(s, timeout_s=timeout_s)
            temp = 1.0 if s.model_id in KIMI_TEMP1 else 0.2
            text, _, _ = _call(prov, wire, prompt, max_tokens=256, temperature=temp, timeout_s=timeout_s)
            refuted = True
            reason = "parse-failed-default-refute"
            try:
                start = text.find("{")
                obj = json.loads(text[start:text.rfind("}") + 1])
                refuted = bool(obj.get("refuted", True))
                reason = str(obj.get("reason", ""))[:160]
            except Exception:
                refuted = "false" not in text.lower()  # conservative
            votes.append({"critic": s.model_id, "family": _family(s.model_id), "refuted": refuted, "reason": reason})
        except Exception as e:
            votes.append({"critic": s.model_id, "family": _family(s.model_id), "refuted": True,
                          "reason": f"critic-unreachable-default-refute: {type(e).__name__}"})
    n_refute = sum(1 for v in votes if v["refuted"])
    return {"n_critics": len(votes), "n_refuted": n_refute,
            "refuted_majority": n_refute > len(votes) / 2 if votes else True, "votes": votes}
