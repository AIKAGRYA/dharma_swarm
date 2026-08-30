---
role: active_spec
date: 2026-08-30
status: ACTIVE — binding convention for receipts, reviews, audits, and measured claims
subordinates_to: docs/governance/CANONICAL_DOC_STACK.md
world:
  commit: eb79c0feacf6 (dirty) · host: Mac.lan · branch: feat/one-world-enforcement-2026-08-30
---

# CLAIM LOCUS CONVENTION

**Declaration (One World, Step 4):** every receipt, review, audit, and
measured claim must carry its locus — **commit + host + branch**. A claim
without a locus is demoted to rumor: it carries zero evidentiary weight
until reproduced with one, because a claim measured on one world says
nothing about another world.

This convention is the prose-layer half of the mechanical enforcement; the
runtime half is `make onboard`, which prints the session's world identity
(fetch-free: commit, host, branch, ahead/behind vs local `origin/main`) on
every run so the locus is always one glance away.

## The footer format

Frontmatter form (for dated docs: reports, plans, audits):

```yaml
world:
  commit: <short-hash>[( · dirty)] · host: <host> · branch: <branch>
```

Inline form (for log lines, table rows, verification entries, PR bodies):

```text
<ISO-8601 timestamp> · <host> · <short-hash>[+dirty] — <claim or measurement>
```

Closing-footer form (for the end of an audit or review):

```text
*<what was done>, against HEAD `<short-hash>`, branch `<branch>`, host `<host>`.*
```

Rules:

1. **Commit** is `git rev-parse HEAD` at the moment of the claim, shortened
   (≥9 chars). Mark `(dirty)` / `+dirty` when the working tree carried
   uncommitted changes that could affect the claim.
2. **Host** is the machine the measurement ran on (`hostname`), not the
   machine the author prefers to remember.
3. **Branch** is `git branch --show-current`; a detached HEAD says so.
4. **Fetch-free honesty:** comparisons against `origin/main` name the LOCAL
   ref and its staleness; never imply a fresh fetch that did not happen.
5. A claim about runtime state additionally needs its evidence class
   (receipt, file:line, runnable command) per the citation-or-silence rule
   in `CLAUDE.md`; locus does not replace evidence, it anchors it.

## Examples already in the corpus

`docs/plans/ONE_WORLD_2026-08-30.md` frontmatter:

```yaml
world:
  commit: ae9957c1d (dirty) · host: Mac · branch: chore/silvering-cleanup-2026-08-28
```

`docs/plans/ONE_WORLD_2026-08-30.md` verification log (inline form):

```text
2026-08-30 02:40 JST · Mac · ae9957c1d+dirty — census taken; S1 partially
verified (remote canonical); S2a/S2b adjudication launched.
```

`reports/2026-08-30_blueprint_adversarial_audit.md` method line and closing
footer:

```text
method: six parallel read-only audit prongs against the working tree
(HEAD ae9957c1d, branch chore/silvering-cleanup-2026-08-28), git history,
and live state under ~/.dharma

*Audit performed read-only by six parallel prongs against HEAD `ae9957c1d`,
git history, and live state under `~/.dharma`.*
```

## Demotion rule in practice

- A measured claim (counts, timings, pass/fail, P&L, fleet state) without
  locus is quoted only as "unlocated rumor" and may not close a scoreboard
  item, gate a merge, or promote a doc.
- When two claims disagree, the one with the newer, cleaner locus wins the
  benefit of the doubt; both lose to re-running the verification command.
- Generated artifacts carry their generator's locus (see
  `docs/state/BRANCH_TTL_REGISTER.md`, which records the world its
  generator ran in).
