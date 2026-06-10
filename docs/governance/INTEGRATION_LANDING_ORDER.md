# Integration Landing Order

Snapshot date: 2026-05-14.

This note is for final merge coordination only. It records the order and PR
handling needed to keep the MemoryKernel, KnowledgeOps, and older Chetana work
mergeable without broadening any feature scope.

## Proposed Order

1. Land `cleanup/memory-kernel-shadow-context-main-2026-05-13` at `fde1443`
   after the final coordinator gates pass and the MemoryKernel 100% landing
   gate below is satisfied. Keep Agent F follow-up edits scoped to governance,
   architecture, and DocOps surfaces.
2. Rebase PR #191 (`feat(knowledge-ops): seed semantic metabolism organ`) on
   the new `main`, resolve DocOps count surfaces, then merge it if the focused
   KnowledgeOps tests and governance gates stay green.
3. Run an integration pass after #191 with `make prod-preflight`. This wraps
   `make memory-kernel-readiness`, `make operator-prod-smoke`,
   `make docops-integrity`, `make test-hygiene`, `make module-budget`,
   `git diff --check`, and focused recursive/operator/control-surface tests.
4. Defer any MemoryKernel-to-KnowledgeOps promotion or write-path integration
   to a follow-up branch. The current landing sequence should stay read-only
   and shadow-mode only.

## MemoryKernel 100% Landing Gate

For this landing, 100% means accounted safe readiness. It does not mean every
home-state directory has a live adapter, and it does not permit MemoryKernel
atoms to mutate prompts, canon, Chetana, vectors, or runtime state.

Required before the branch is called operationally ready:

- `make memory-kernel-readiness` exits 0. This target runs adapter readiness,
  writer sentinel CI mode, context eval default cases, and the shadow context
  sweep.
- The adapter readiness report keeps `schema_version=memory_kernel_readiness.v1`
  and `required_surface_count=7`.
- The seven required adapter surfaces are all registered and none is
  `unavailable` or `missing_adapter`.
- A required `degraded` row remains a blocker unless the landing code and tests
  explicitly classify that warning as reviewed safe degradation.
- Non-required `missing_adapter` rows may remain only as accounted census
  backlog with `required=false`; they are not a request to read all live memory
  surfaces.
- Writer sentinel output has `unregistered_surface_count=0`,
  `unreviewed_discovery_count=0`, and `action_required_count=0`.
- Context eval and shadow sweep have `hard_failure_count=0`. Warnings are
  acceptable only when they preserve shadow mode, no write-through, and no
  prompt injection.

The latest local run passes the make target with adapter readiness
`status=ready`: 81 registered adapters, 7 ready required surfaces, 74 accounted
optional surfaces, 0 missing adapters, and 0 warnings. This is the target shape
for the final coordinator: complete required coverage plus accounted optional
surface metadata, not unconstrained live memory.

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
