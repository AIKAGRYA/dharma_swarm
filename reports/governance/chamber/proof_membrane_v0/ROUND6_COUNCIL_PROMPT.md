# Final bounded-schema council: Hyperbolic Chamber V0

Review the compact fact check and cited primary evidence. No prior vote carries
forward. Round 5 produced five substantive 100 approvals, but the runner held
because MiniMax wrote `"None."` instead of an empty disagreement string and
Nemotron's approving JSON ended inside its evidence list.

Return exactly one JSON object and nothing else. Use at most five short
`evidence_checked` entries. Keep `summary` under 120 words. On approval, copy
this shape exactly, replacing only the summary and evidence strings:

```json
{
  "verdict": "approve",
  "score": 100,
  "summary": "Concise evidence-based result.",
  "blockers": [],
  "required_changes": [],
  "evidence_checked": ["path:line or exact JSON field"],
  "explicit_disagreement": ""
}
```

Do not write `None`, `none`, commentary, Markdown, or a second object outside
that JSON. If you dissent, cite a contradicting attached path/line or exact JSON
field and use a non-empty `explicit_disagreement`.

Approve only if all remain true:

1. attempt 1 is present and typed failed;
2. final closeout is typed passed with scope, six gates, and control green;
3. governed dependency-light and full plugin-aware tests remain distinct;
4. proof semantics reject fabrication, semantic mismatch, and unissued power;
5. council/model output cannot mint evaluator permission;
6. MiroFish/external simulators are untrusted candidate sources;
7. the exact seven-source replay manifest pins `df435af863e651287de3f637509a45d59b133ad3`;
8. the claim ceiling is exact-scope `HARNESS_PROVEN`.

Model consensus is review evidence only, never runtime authority.
