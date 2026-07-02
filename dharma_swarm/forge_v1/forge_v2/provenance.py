"""Task provenance, EXPLORE/CONFIRM split, contamination state (F1 + invariant 2).

A positive claim requires a contamination_state and an EXPLORE/CONFIRM split.
EXPLORE = where pockets are found; CONFIRM = frozen held-out; a pocket only
counts if it replicates on CONFIRM. Contamination is reported HONESTLY: public
benchmarks predate model cutoffs, so SWE-bench is marked 'possible_pretrain' and
the paraphrase canary is flagged WEAK for code (the model sees the real fixed
file, not just the issue text) — we do not pretend the canary clears it.
"""
from __future__ import annotations


def split_explore_confirm(instance_ids: list[str], n_explore: int) -> tuple[list[str], list[str]]:
    """Deterministic split (order-stable). CONFIRM stays frozen across the campaign."""
    ids = list(instance_ids)
    return ids[:n_explore], ids[n_explore:]


def contamination_state(instance: dict) -> dict:
    """Honest contamination assessment for a SWE-bench instance."""
    created = instance.get("created_at", "") or instance.get("base_commit", "")[:0]
    return {
        "state": "possible_pretrain",
        "basis": "SWE-bench Verified is public and predates most model cutoffs; "
                 "the buggy file is shown verbatim, so a paraphrase canary on the "
                 "issue text does NOT rule out memorized fixes. Treat lift here as "
                 "an upper bound until rerun on post-cutoff/fresh instances.",
        "created_at": str(created),
        "canary": "problem_statement_paraphrase_only_WEAK_for_code",
        "strong_control_todo": "post-cutoff or SWE-bench-Pro (contamination-resistant) instances",
    }


def aggregate_contamination_states(task_states: dict[str, dict]) -> dict:
    """Run-level contamination summary without losing per-task provenance."""
    if not task_states:
        return {"state": "unknown", "task_count": 0, "task_states": {}}
    states = {str(v.get("state", "unknown")) for v in task_states.values()}
    if "contaminated_quarantine" in states:
        state = "contaminated_quarantine"
    elif "possible_pretrain" in states:
        state = "possible_pretrain"
    elif len(states) == 1:
        state = next(iter(states))
    else:
        state = "mixed"
    return {
        "state": state,
        "task_count": len(task_states),
        "task_states": task_states,
        "strong_control_todo": "rerun promoted claims on post-cutoff or fresh held-out tasks",
    }


def paraphrase_problem(problem: str) -> str:
    """Weak canary: lightly reword the issue framing (NOT the code). If a swarm's
    lift vanishes under this, it was leaning on memorized issue phrasing. Kept
    deliberately conservative; the honest control is fresh instances."""
    prefix = ("[Reworded statement of the same defect — same repository, same code, "
              "different phrasing.]\n")
    return prefix + problem
