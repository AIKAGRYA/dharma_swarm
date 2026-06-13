# Bug Corral Arbiter Packet

For Codex 5.5 (the third arbiter). Start with `CODEX_ARBITER_PROMPT.md`.

## Files
- `CODEX_ARBITER_PROMPT.md` — your instructions. Read first.
- `00_ORIGINAL_PROMPT.md` — the prompt both Devin and Perplexity worked from.
- `A_devin_09_PROVENANCE.md` — Agent A (Devin) manifest, v2.
- `A_devin_01_TRUTH_VERIFIERS.md` — Agent A file 01 (10 distilled findings, ~12 KB).
- `B_perplexity_09_PROVENANCE.md` — Agent B (Perplexity Computer) manifest, v1.
- `B_perplexity_01_TRUTH_VERIFIERS.md` — Agent B file 01 (19 verbatim sources, ~222 KB).

## Output location
Write your three deliverables here, on this same branch:
- `01_COMPARISON.md`
- `02_CODEX_SCAN.md`
- `03_VERDICT_FOR_OPERATOR.md`

Then push back to `perplexity/bug-corral-arbiter-packet`. Do not merge to main; the operator gates that.

## Repo state
- Main HEAD: `9c76b210` (clean working tree at packet-staging time).
- Devin's work: PR #592, branch `devin/1781340172-bug-corral`, head `d2192036`.
- Operator: on mobile, cannot run terminal. All hand-off goes through this branch + PR comments.
