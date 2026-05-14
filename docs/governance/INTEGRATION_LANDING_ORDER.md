# Integration Landing Order

Snapshot date: 2026-05-14.

This note is for final merge coordination only. It records the order and PR
handling needed to keep the MemoryKernel, KnowledgeOps, and older Chetana work
mergeable without broadening any feature scope.

## Proposed Order

1. Land `cleanup/memory-kernel-shadow-context-main-2026-05-13` at `b3c45e7`
   after the final coordinator gates pass. Treat `Makefile`,
   `docs/governance/INTEGRATION_LANDING_ORDER.md`, and DocOps count refreshes
   as the only Agent F edits on top of the existing MemoryKernel branch.
2. Rebase PR #191 (`feat(knowledge-ops): seed semantic metabolism organ`) on
   the new `main`, resolve DocOps count surfaces, then merge it if the focused
   KnowledgeOps tests and governance gates stay green.
3. Run an integration pass after #191: `make memory-kernel-readiness`,
   `make module-budget`, `make docops-integrity`, `make test-hygiene`, and
   `git diff --check`. Add `make operator-prod-smoke` once the operator
   control-surface worker has stabilized the fast smoke script.
4. Defer any MemoryKernel-to-KnowledgeOps promotion or write-path integration
   to a follow-up branch. The current landing sequence should stay read-only
   and shadow-mode only.

## PR #191 Handling

PR #191 is still open and draft as of this snapshot. GitHub reports it as not
currently mergeable, but the latest review comment says the branch was clean
after its earlier conflict resolution and CI pass. Its risk is mostly DocOps
count drift and stale base state, not a known feature conflict.

Required before merge:

- rebase or recreate on the post-MemoryKernel `main`
- refresh `docs/docops/AUTO_INVENTORY.md` and
  `docs/governance/SOVEREIGN_MANIFEST.md`
- rerun focused KnowledgeOps tests plus the coordinator gates above

## PR #59 Handling

PR #59 should not be merged as-is. It is open, draft, and not mergeable. A
2026-05-07 comment marked it superseded by PR #159; PR #159 was later closed as
superseded by merged PR #172. PR #59 also still carries security-bot comments
on `~/.dharma` ownership and clear-text sensitive logging.

Recommended disposition:

- leave #59 out of the landing order
- close it as superseded once the current stack lands, or keep it only as
  historical reference
- if Chetana work is still needed, cut a fresh successor from current `main`
  after MemoryKernel and KnowledgeOps land, with the security comments resolved
  before review
