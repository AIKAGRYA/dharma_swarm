---
id: narrative-comment-scan
version: 0.1.0
theme: 17-code-health-metrics
status: tested
reproduce: "python docs/stop-the-slop/probe/probe.py narrative_comments <pkg>"
invariant: >
  A comment that restates the line below it carries zero information (Shannon) and is
  a measurable tell of machine-generated code: LLMs narrate their own output
  ("# Create a future for the response" above `future = ...`). A good comment explains
  WHY; a narrative comment explains WHAT the code already says. This is a LOW-confidence
  PROXY by nature — regex cannot read intent — so it must be graded LOW and confirmed
  by a human, never asserted as fact.
lineage:
  - "Shannon 1948 — information as surprise; a comment that predicts its own next line is zero-entropy"
  - "Knuth — literate programming: prose should add what code cannot, not echo it"
  - "arXiv 2508.14727 — AI code introduces measurable smells; comment inflation is among the tells"
ground_truth_tools: ["comment extraction (tokenize/AST)", "comment-vs-next-line token overlap (PROXY)", "human read (the actual ground truth)"]
returns_clean: true
---

## Prompt

> Scan for **narrative comments** — comments that restate the code instead of
> explaining why. The invariant (Shannon, Knuth): a comment that paraphrases its own
> next line is zero-entropy and a tell of machine narration. **This is a proxy
> signal**; grade it honestly.
>
> **Hard rules:**
> 1. **Measure overlap, but own the proxy.** Flag a comment when its content largely
>    restates the immediately following statement (high token overlap with the
>    identifiers/keywords on the next line). State plainly that this is a heuristic
>    PROXY at **LOW confidence** — a regex cannot read intent.
> 2. **Never auto-delete, never assert.** The output is a *candidate list for human
>    read*, not a verdict. A "narrative-looking" comment may legitimately flag a
>    subtle line. The human is the ground truth.
> 3. **Report density, not just count.** Give the count AND the fraction of all
>    comments, so a large codebase isn't condemned for an absolute number that's a
>    small ratio.
> 4. **Return clean.** Low density → `Comment quality healthy: ~X% restate-the-code
>    of N comments.` Do not inflate a small ratio into a finding.
>
> **Output:** the count, the density (% of comments), and a sample of flagged
> `file:line: # comment` for a human to confirm — explicitly labeled LOW-confidence.

## Why it's built this way

This is the deliberately humble prompt in the set, and that humility is the point. The
signal is real — comment inflation is a documented AI tell — but the instrument is a
regex, which cannot distinguish "# increment i" (noise) from "# off-by-one guard: API
is 1-indexed" (gold) without reading intent. A library that condemns vibe-grading must
grade *its own weak proxy* as weak: LOW confidence, density not count, human-confirms,
`pressure=0` so it can never drive a composite. That is the difference between a tell
and an accusation.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-27:

```
| Signal             | Measured                                     | Grade | Confidence | Confirm with                    |
|--------------------|----------------------------------------------|-------|------------|---------------------------------|
| Narrative comments | ~86 restate-the-code comments (0.9% of 9700) | AMBER | LOW        | human read of the flagged lines |

Detail (comment-restatement regex (PROXY)):
  semantic_digester.py:378  # Get surrounding text (up to 500 chars after the
  startup_crew.py:541       # Create all tasks in single batch (single transaction)
  orchestrator.py:321       # Return agent to available pool before skipping
  checkpoint.py:129         # Create a future for the response
  kaizen_stats.py:298       # Get ease score (default to 0.5 if category not in map)
```

- **~86 candidates, but density is 0.9% of 9,700 comments** — low. Reporting the
  *ratio* (rule 3) is what keeps this honest: 86 sounds alarming; 0.9% says comment
  quality is broadly healthy with a thin seam of narration to review.
- Confidence is **LOW** and the grade does not drive the composite (`pressure=0`). The
  output is a sample for a human to read, not a delete-list. Some flagged lines (e.g.
  `# Create a future for the response` above `future = ...`) are textbook narration;
  others may be load-bearing — only a human read settles it, which is exactly what the
  "confirm with" column says.

## Changelog

- **v0.1.0** (2026-06-27) — new dimension. Comment-vs-next-line overlap proxy, graded
  LOW with density (not count) and human-confirm; `pressure=0` so it never drives the
  index. Tested on `dharma_swarm`: ~86 candidates at 0.9% density → AMBER/LOW, a
  review list rather than a verdict.
