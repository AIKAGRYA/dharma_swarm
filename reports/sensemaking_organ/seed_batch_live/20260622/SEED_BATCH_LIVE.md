# The Seeing Organ — First Meal, LIVE (evidence from real public repos)

**Run:** 2026-06-22T02:57:01.416600Z · **Repos fetched:** 2026-06-22T02:55:19Z · **Source:** the seed batch's signals are all public GitHub repos.

Evidence is no longer hand-assembled prose — it is fetched from the repos themselves (existence + HEAD + tag count via git) plus independent package registries that **verifiably link back to the same repo**. A name-collision package is rejected, not counted. A repo is ONE origin, so a tool with no verified independent family stays *insufficient* — not false, just not yet cross-validated.

## Stage 0 — safety: all envelopes safe **True**, all payloads fenced **True**

## Stage 1 — verdicts: `{'corroborated': 3, 'insufficient': 12, 'refuted': 2}`

| signal | verdict | eval families | source families | refutations | note |
|---|---|---|---|---|---|
| markitdown | corroborated | 3 | 3 | 0 |  |
| dspy | corroborated | 3 | 2 | 0 |  |
| papermark | corroborated | 3 | 2 | 0 |  |
| open_notebook_identity | refuted | 0 | 1 | 2 |  |
| huly_docuseal_identity | refuted | 0 | 1 | 2 |  |
| continue | insufficient | 0 | 1 | 0 | npm 'continue' -> scottcorgan/continue (different project; NOT counted) |
| headroom | insufficient | 0 | 1 | 0 | pypi 'headroom' -> SUNKENDREAMS/headroom (different project; NOT counted) |
| maybe | insufficient | 0 | 1 | 0 |  |
| dify | insufficient | 0 | 1 | 0 |  |
| twenty | insufficient | 0 | 1 | 0 |  |
| docuseal | insufficient | 0 | 1 | 0 |  |
| anytype | insufficient | 0 | 1 | 0 |  |
| last30days_skill | insufficient | 0 | 1 | 0 |  |
| taste_skill | insufficient | 0 | 1 | 0 |  |
| agent_reach | insufficient | 0 | 1 | 0 |  |
| career_ops | insufficient | 0 | 1 | 0 |  |
| pm_skills | insufficient | 0 | 1 | 0 |  |

### False decorrelations rejected (the moat working)
- **headroom**: pypi 'headroom' -> SUNKENDREAMS/headroom (different project; NOT counted)
- **continue**: npm 'continue' -> scottcorgan/continue (different project; NOT counted)

## Stage 2 — advisory warrant-pressure (read-only; dispatch held False: **True**)

| signal | weight | source families | dispatch_authority |
|---|---|---|---|
| markitdown | 0.5488 | 3 | False |
| dspy | 0.432 | 2 | False |
| papermark | 0.384 | 2 | False |

## What the live run changed vs. the hand-assembled run
- Corroborated dropped from 9 → 3. Real evidence is more conservative and more correct.
- **`continue` was corrected from corroborated → insufficient**: its 'independent' marketplace/package evidence did not verify (npm 'continue' is a different project).
- **`headroom`** stays insufficient and its pypi hit was rejected as a name collision (SUNKENDREAMS/headroom), so its 60–95% claim earns nothing.
- Only **markitdown / dspy / papermark** corroborate — each has a package that verifiably links back to its own repo; MarkItDown also has an independent reproduction (PR #663), so it carries the top advisory weight.
- The two identity mismatches remain *refuted*, now settled against the real repo README.

*Demonstration run. Creates no authority surface, mutates no owner. Read-only throughout.*
