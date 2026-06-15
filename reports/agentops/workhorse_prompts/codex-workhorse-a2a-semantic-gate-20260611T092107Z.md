# Codex Workhorse Prompt - A2A Semantic Gate Review

You are `codex_workhorse_semantic_reviewer`, a bounded Codex workhorse invoked by Codex Composer.

## Scope

Repository:

```text
/Users/dhyana/dharma_swarm_main
```

You may write only:

```text
reports/agentops/semantic_reviews/codex-workhorse-a2a-semantic-gate-20260611T092107Z.json
reports/agentops/semantic_reviews/codex-workhorse-a2a-semantic-gate-20260611T092107Z.md
```

Do not modify code, docs, dashboard files, scripts, tests, receipts, or git state.

## Task

Independently review the current A2A semantic-peer gate and write a semantic review artifact. You are not Hermes, Fable, Devin, or Claude. You may set `semantic_reply_claim=true` only for your own Codex workhorse review.

Read enough of these files to make a grounded judgment:

- `/Users/dhyana/.dharma/a2a_bus/collab/convergence/MEGA_PROMPT_CODEX_COMPOSER_SEMANTIC_PEER_KANBAN_V5_20260611T091643Z.md`
- `/Users/dhyana/.dharma/a2a_bus/collab/convergence/RUN_RECEIPT_a2a_domain_receipt_nonsemantic_proof_20260611T091643Z.md`
- `reports/a2a/reply_receipts/20260611T091604Z-hermes-3a0e3081da8a.json`
- `reports/a2a/domain_reply_receipts/20260611T091559Z-hermes-m5-3a0e3081da8a.json`
- `scripts/runtime/a2a_domain_reply_artifact.py`
- `scripts/runtime/a2a_domain_reply_worker.py`
- `scripts/runtime/a2a_reply_capture.py`
- `reports/agentops/work_packets/codex-workhorse-semantic-review-a2a-gate.json`

## Required JSON Shape

Write this JSON object:

```json
{
  "schema_version": "dharma.agentops.semantic_review.v1",
  "created_at": "<UTC timestamp>",
  "agent_uid": "codex_workhorse_semantic_reviewer",
  "reviewed_by_model": true,
  "semantic_reply_claim": true,
  "peer_model_processed_claim": true,
  "not_claimed_agents": ["hermes-m5", "fable_5_cursor", "fable_composer", "devin"],
  "review_target": "a2a_semantic_peer_gate",
  "verdict": "reviewed",
  "summary": "...",
  "sharpest_disagreement": "...",
  "missing_evidence": ["..."],
  "highest_leverage_next_build": "...",
  "recommended_verifier_commands": ["..."],
  "evidence_refs": ["..."],
  "semantic_boundary": "This is a Codex workhorse semantic review only; it is not a Hermes/Fable/Devin semantic reply."
}
```

Also write a short Markdown companion with the same conclusion.

Be concrete. Cite file paths. Preserve the distinction between mechanical `DOMAIN_RECEIPTED` and true peer/model semantic processing.
