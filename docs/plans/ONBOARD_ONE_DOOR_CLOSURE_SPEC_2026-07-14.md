# One-Door Onboarding Closure — Hill-Climb Specification (2026-07-14)

**Role:** `working_plan` — the closure sequencing document for
`onboard-one-door-2026-07`. It specifies the remaining work from the current
12/15-criteria state to a fully closed track (`status: SHIPPED`,
`closure_kind: VERIFIED_SLICE`, zero ship blocks, Titanium unblocked). This
document implements nothing.

**Parent authority:**
`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md` remains the detail
authority for packet internals — WP-O5 (`:1752-1808`), WP-O6 (`:1809-1894`),
decisions D2/C1/M6-1 (`:2051-2113`), and the terminal clean-room proof §13
(`:2186` onward). This spec does not restate those envelopes; it sequences
them, adjudicates current truth, and closes gaps the parent does not cover
(criterion verifiability in the published projection, the evidence-grade
ratchet, the closure flip itself). Where the two disagree on a packet's
internals, the parent wins; on closure sequencing, this document wins.

**Evidence baseline:** all repository claims in this revision were checked at
`971923a71c18b0effb5bbf2db279e85e8a7db413` (equal to `origin/main` at write
time). Claims observed only in the authoring sandbox are labeled
*environment-scoped witness* and bind no other host. Live portfolio state is
never read from this file — it comes only from
`python3 scripts/governance/check_track_status.py` and `make onboard`.

**Hard boundary (inherited and extended):** extend the existing doorway,
AgentOps packet machinery, receipt path, digest primitive, owner files, and
`needs_host` vocabulary. No gate weakening, no second truth store, no
author-minted operator records, no production or `CLOSED_LIVE` claim, no
`min_evidence_grade` lowering, and no performance target met by removing a
required validation.

---

## §1 Measured current state and claim adjudication

### 1.1 Criteria (15 declared, `docs/governance/ACTIVE_TRACK.yaml:1921-1983`)

Session witness 2026-07-14 (fresh clone, deps installed, evidence rendered by
`check_track_status.py` into `reports/governance/active_track_evidence.md:208-231`,
untracked): **12/15 pass.** The three recorded failures adjudicate as:

| Criterion | Recorded result | Adjudication |
|---|---|---|
| `wp_o2_single_parser_six_consumers` | exit 2 — `ImportError` collecting `tests/test_control_surface.py:17` (`fastapi` absent) | **Environment-scoped, not a regression.** After installing the missing dev deps (`fastapi`, `httpx`, `idna`) the full seven-file batch passed: `176 passed`, exit 0, witnessed this session at the evidence baseline. |
| `wp_o4_make_agentops_ci_parity` | timed out at the checker's 120 s limit | **Unadjudicated → CL-1 must adjudicate.** A full 600 s run this session completed in 152 s with `2 failed, 181 passed, 2 skipped`; both failures are `tests/test_make_onboarding_contract.py::test_make_agentops_bootstrap_never_executes_repo_venv_sitecustomize` and `::test_make_agentops_bootstrap_preserves_external_venv_dependencies`. Both exercise Make bootstrap venv identity and plausibly reflect this container's interpreter layout (root `pip` installs into `/usr/local`, no project venv) — and `main` merges only through the merge-blocking `pytest (3.11)`/`pytest (3.12)` contexts (`scripts/governance/ci_parity_manifest.json:8-19`) — but *plausible* is not adjudicated. CL-1 settles it on a reference environment. |
| `wp_o6_readiness_property_battery` | `tests/properties/test_onboarding_readiness_properties.py` not found, exit 4 | **Real missing work.** The file does not exist in the repo (`tests/properties/` contains five other batteries). Owned by WP-O6 (CL-6). |

### 1.2 The published projection cannot verify any of this (finding V1)

The CI-published evidence (`git show origin/generated/status:reports/governance/active_track_evidence.md`)
renders **0/15** for this track: the publish job installs only `pyyaml`
(`.github/workflows/active-track.yml:252`) before running
`check_track_status.py --warn-only` (`:260`), so every `command_passes`
criterion reports *could not execute here: environment lacks 'pytest'*. The
projection is honest (unverified is never promoted to pass) but permanently
blind: the track's published status can never reach 15/15 from that job as
configured. CL-1 closes this.

### 1.3 The evidence-grade gap (finding G1)

All 15 completion criteria are `kind: command_passes`. That kind is absent
from `RIGOROUS_KINDS` (`scripts/governance/check_track_status.py:581-592`) and
unmapped in the grade ladder, so it scores S0
(`docs/governance/evidence_grades.yaml:17`, "an unmapped/unknown kind scores
S0"). The floor is S2 — landed on `origin/main`
(`docs/governance/evidence_grades.yaml:33`). Hence the standing ship blocks
even at 15/15: *no rigorous evidence* and *strongest evidence S0_EXISTS <
required S2_LANDED*. The graded rung is advisory today (AI-M1 stage
`advisory`, `docs/governance/hygiene/patterns/AI-M1.yaml:7`), but closure
means `shippable = criteria_pass and not ship_blocks`
(`scripts/governance/check_track_status.py:1934`) with an **empty**
`ship_blocks` — not a block list we hope stays advisory. CL-1 closes this.

### 1.4 Open blocker ledger (6 items, `docs/governance/ACTIVE_TRACK.yaml:2013-2036`)

- `C1` (`:2013`) — merge-authority evidence. Partially real already: the
  `Onboarding admission parity` context is in the parity manifest
  (`scripts/governance/ci_parity_manifest.json:38-43`, `regression_sensitive:
  true`) and automerge loads its required set from that manifest
  (`.github/workflows/automerge.yml:99-120`). Missing: captured live
  branch-protection, merge-queue, and fail-closed evidence. → CL-2.
- `D2` (`:2017`) — operator ratification of strict-by-default, exact record
  format in parent §9.2. → CL-3.
- `WP-O5` (`:2021`) — strict-by-default promotion. → CL-4.
- `M6-1` (`:2025`) — `pyproject.toml` mutmut coordination. `[tool.mutmut]`
  exists (`pyproject.toml:80-97`, landed via PR #873, commit `5f50ec3`) but is
  scoped to `dharma_swarm/spine/receipt.py` (`pyproject.toml:90`) — the
  onboarding widening has not happened, and the file is owned by
  `dharmagraph-engine-2026-07`. → CL-5.
- `WP-O6` (`:2029`) — terminal hardening battery. None of its four named test
  files exist yet (`tests/test_onboarding_performance.py`,
  `tests/test_onboarding_clean_room.py`, `tests/test_onboarding_mutation.py`,
  `tests/properties/test_onboarding_readiness_properties.py`). → CL-6.
- `TERMINAL-PROOF` (`:2033`) — decorrelated clean-room verifier per parent
  §13. → CL-8.

### 1.5 Adapter prerequisites A1/A2/A4 (parent §6.1: must join before terminal proof)

Observed repaired at the evidence baseline: `DEVIN.md:22` (sessions begin in
the assigned checkout/branch) and `:42` (never change branches or pull
`main`); `QWEN.md:3,21` (reference-only, owns no checkout or live-state
fact); `docs/AGENTS.md:14-26` (authority flows from
`CANONICAL_DOC_STACK.md`, no generated-projection precedence). These
observations still need a *recorded* verification inside the terminal-proof
preflight (CL-7) — a session grep is not a merged record.

---

## §2 Definition of done (mechanical, no prose escape hatch)

The campaign is finished when, in order:

1. `python3 scripts/governance/check_track_status.py` renders
   `onboard-one-door-2026-07` with **all completion criteria passing and
   `ship_blocks` empty** (`shippable: true`) — which mechanically requires:
   every criterion green (§1.1), zero open blocker next-items (§1.4), at
   least one passing `RIGOROUS_KINDS` criterion, and strongest passing grade
   ≥ S2 (§1.3);
2. the published projection on `generated/status` shows the same state, not
   an unverified 0/15 (§1.2);
3. the terminal clean-room proof artifact has merged together with the final
   WP-O6 candidate (parent §13);
4. the closure PR flips the track entry to `status: SHIPPED`,
   `closure_kind: VERIFIED_SLICE`, `closed_at: <date>` — the same shape as
   `runtime-truth-spine-adoption-2026-06`
   (`docs/governance/ACTIVE_TRACK.yaml:2178-2181`). `VERIFIED_SLICE` is a
   non-production closure kind, so no `final_boss_review` packet is required
   (`scripts/governance/check_track_status.py:48-50,1446-1456`); any future
   `SUBSTRATE_TRUSTED` claim is a new track;
5. `make onboard` renders the track under recently-closed, and Titanium
   vNext baseline capture / WP-00 unblocks per the track description.

Closing also drops active WIP from 11 toward the warn ceiling of 8 — the
portfolio's own standing WARN (`wip-high`).

---

## §3 Closure DAG

```
CL-1 (truth + verifiability + grade ratchet)   — independent; start now
CL-2 (C1 evidence capture)                     — independent; start now
CL-3 (D2 operator record)                      — after CL-2
CL-4 (WP-O5 strict-by-default)                 — after CL-2 + CL-3
CL-5 (M6-1 mutmut coordination)                — independent; start now
CL-6 (WP-O6 terminal battery)                  — after CL-4 + CL-5
CL-7 (A1/A2/A4 verification record)            — any time before CL-8
CL-8 (TERMINAL-PROOF, decorrelated verifier)   — after CL-6 + CL-7
CL-9 (closure flip)                            — last
```

Critical path: CL-2 → CL-3 → CL-4 → CL-6 → CL-8 → CL-9. CL-1, CL-5, and CL-7
are parallel-safe and should start immediately. CL-6 is the largest
implementation risk; CL-8 is the largest schedule risk (it needs a verifier
who authored none of WP-O1..O6).

---

## §4 Packets

### CL-1 — Truth, verifiability, and evidence-grade ratchet (S; governance + one workflow edit)

**Closes:** findings V1 (§1.2) and G1 (§1.3); adjudicates the `wp_o4`
ambiguity (§1.1); the two standing ship blocks that survive even at 15/15.

**Owner:** track owner. Precedent: the D3 record PR #941 and authority
bootstraps #924/#929/#936 — ledger edits to the track's own entry travel as
small governance PRs.

**Allowed files:** `docs/governance/ACTIVE_TRACK.yaml` (this track's entry
only), `.github/workflows/active-track.yml` (owned surface; publish-status
job only), regenerated managed include blocks (`python3
scripts/governance/render_active_track_includes.py`).

**Behavior map:**

| ID | Behavior | Check |
|---|---|---|
| CL1-B1 | Add `commit_on_main` criteria (S2) binding the landed WP waves to their merge commits — at minimum one for the WP-O2 parser wave (PRs #907/#911), one for the WP-O3 chain (#913/#916/#936/#937/#942), one for WP-O4 (#912/#918/#920). Resolve each 40-hex sha with `git log --merges` before writing; a wrong sha must fail, not be prettied. | `check_track_status.py` renders the new criteria ✓ with kind `commit_on_main`; *no rigorous evidence* ship block disappears; strongest grade ≥ S2 |
| CL1-B2 | Add `test_passes` twin criteria (S3, one pytest target each) for the load-bearing batteries — e.g. `tests/test_onboarding_broken_register.py`, `tests/test_make_onboarding_contract.py::test_door_delegates_to_compact_engine`. Declare `oracle_source` only if a genuinely independent verifier signs; otherwise accept the honest S3→S2 downgrade (`docs/governance/evidence_grades.yaml:40-44`). Do not delete the existing `command_passes` batches — they stay as breadth. | criteria render ✓ with kind `test_passes` |
| CL1-B3 | Publish-status job installs the dev environment (pytest + project deps, mirroring `tests.yml`) before `check_track_status.py --warn-only`, so `command_passes`/`test_passes` criteria actually execute in the published projection. Unverified must remain unverified on any install failure — never synthesize a pass. | `git show origin/generated/status:...` renders this track > 0/15 after the next scheduled publish |
| CL1-B4 | Adjudicate `wp_o4_make_agentops_ci_parity` on the reference environment (Linux CI or operator host with the project venv): if the two bootstrap venv-identity tests (§1.1) pass there, record the witness in the ledger item and the criterion stands; if they fail, that is a real WP-O4 regression — open a corrective item under this track *before* any CL-4 work, and CL-4 blocks on it. Also raise the checker timeout for this one batch (observed honest runtime 152 s > 120 s limit) via the criterion's declared timeout rather than trimming tests. | criterion renders ✓ executed (not timed out) in the session and published projections |
| CL1-B5 | Wire `evidence_criterion` links on the six blocker next-items where a criterion exists or is added, so the underclaim detector (`check_track_status.py:1873-1895`) can catch the ledger falling behind reality for the rest of the campaign. | `check_track_status.py` emits no `track-underclaim` WARN for this track afterwards |

**Verification / expected result:** `python3
scripts/governance/check_track_status.py` → this track's `ship_blocks`
reduces to exactly one entry: `N open blocker next-item(s)`. Gates:
`python3 -m pytest tests/test_active_track_governance.py
tests/test_track_portfolio.py -q` exits 0; `python3
scripts/governance/render_active_track_includes.py --check` exits 0;
DocOps integrity green.

**Rollback:** revert the one governance commit; the prior criteria set was
never weakened so nothing reopens silently.

**Forbidden:** marking any blocker DONE, lowering `min_evidence_grade`,
touching sibling-track entries, converting an existing criterion in place
(add, don't replace — counts only ratchet up).

### CL-2 — C1 merge-authority evidence capture (S; governance, external coordination)

**Closes:** blocker `C1` (`docs/governance/ACTIVE_TRACK.yaml:2013`).

**Owner boundary:** this is *evidence capture*, not a file grab (parent
§9.4). `.github/workflows/automerge.yml` belongs to
`merge-master-mike-d4-2026-06`; branch protection lives on the GitHub side
under operator authority. The authority-only WP-O16-B0 bootstrap and exact
WP-O16 implementation exception below are the sole shared-surface exceptions;
they transfer no ownership and admit no workflow, runtime, parity-manifest, or
branch-protection edit.

**Required evidence set** (each item captured with command + output, stored
in the C1 governance PR body and, where file-shaped, under
`reports/agentops/work_packets/` — an owned surface):

1. Live branch protection: `gh api
   repos/AmitabhainArunachala/dharma_swarm/branches/main/protection --jq
   .required_status_checks.contexts` includes `Onboarding admission parity`
   (the manifest's own regeneration command,
   `scripts/governance/ci_parity_manifest.json:5`).
2. Parity manifest entry (already present:
   `scripts/governance/ci_parity_manifest.json:38-43`) — cite, don't re-add.
3. Merge-authority consumer congruence: every repository path that can
   classify a PR as mergeable or authorize/refuse its merge must classify
   `Onboarding admission parity` as **required**, never absent or advisory.
   This includes both (a) an automerge run log showing the manifest-driven
   required set enforcing the context (`.github/workflows/automerge.yml:99-120`)
   and (b) the manual Merge Master Mike path, which consumes
   `docs/governance/CI_TRUTH_CONTRACT.json` through
   `scripts/runtime/pr_merge_control.py`. Capture the contract entry and tests
   proving that a missing, pending, or non-passing context blocks that manual
   path. A green hosted check is insufficient if any merge-authority consumer
   still classifies the same context more weakly.
4. Base-change sensitivity, using the strongest mechanism the hosting account
   can actually provide:
   - on an organization-owned repository with merge queue available, capture
     one live `merge_group` run where the context executed (it is declared
     `regression_sensitive: true` and must run there, manifest note `:5`);
   - on a personal-account repository, where GitHub does not offer merge
     queues, capture the repository owner type, the rejected merge-queue API
     request, and GitHub's published availability boundary; require live
     branch protection to report `required_status_checks.strict: true`, and
     prove every regression-sensitive workflow (including this context)
     already declares `merge_group`. This is the fail-closed equivalent
     available on the current host: every PR is retested against current
     `main`, while the workflow remains ready for a future organization
     transfer. A synthetic event or prose claim is not a merge-group run.
5. Fail-closed demonstration: one scratch PR carrying a deliberately BLOCKED
   onboarding truth (e.g. an undeclared forbidden file in the packet
   envelope) whose `Onboarding admission parity` check fails and whose merge
   is thereby refused. Record PR number, check-run URL, and the exact
   nonzero verdict. The PR is then closed unmerged.

**WP-O16 two-step authority boundary:** the current CI truth contract does not
yet classify `Onboarding admission parity` as required, so item 3 cannot be
claimed complete by evidence prose. First merge the authority-only
`onboard-one-door-WP-O16-B0` packet using Session Entry identity `WP-O16`.
That bootstrap may edit only this closure spec, this track's
`ACTIVE_TRACK.yaml` entry, the three mechanically rendered authority
projections (`CLAUDE.md`, `docs/governance/BUILD_SESSION_ENTRYPOINT.md`, and
`docs/governance/SOVEREIGN_MANIFEST.md`), the DocOps auto inventory, and its
own canonical packet. It changes no CI consumer.

After that bootstrap merges, a fresh exact-main
`onboard-one-door-WP-O16` packet receives a one-time packet-scoped exception
for **exactly** these implementation paths:

- `docs/governance/CI_TRUTH_CONTRACT.json`
- `tests/test_ci_truth.py`
- `tests/test_onboarding_ci_contract.py`
- `tests/test_pr_merge_control.py`
- `reports/agentops/work_packets/onboard-one-door-WP-O16.json`

WP-O16 may only align the existing CI-truth consumer and prove the required
classification. It may not edit `.github/workflows/**`,
`scripts/governance/ci_parity_manifest.json`, `scripts/runtime/**`, or any
other file, and it acquires no `owned_surfaces` claim. Merging either B0 or
WP-O16 closes no blocker by itself: `C1` remains `PENDING` and blocking until
all five required evidence captures above are merged into its operator-bound
record.

The epistemic boundary is explicit: tracked contract or manifest edits are
`Candidate[required-context-set]`, not
`Authority[live-branch-protection]`. Only a fresh live host capture can supply
the latter, and the candidate set cannot be promoted until every named
consumer is revalidated against it. B0 and WP-O16 therefore leave C1 pending
until both host authority and consumer parity are observed at the final base.

**Record:** flip `next_items[C1]` to `C1 DONE — operator=<handle>;
pr=<number>; merge_commit=<40-hex>; evidence=<the five captures>`,
`blocker: false`, following the D3 record precedent.

**Kill criterion:** if branch protection does *not* list the context, or any
merge-authority consumer classifies it as absent/advisory, C1 is not closable
by evidence prose. Escalate to the operator and the merge-authority owners;
use only the exact WP-O16 boundary above for the known CI-truth mismatch, and
do not edit automerge, runtime, the parity manifest, or protection yourself.

### CL-3 — D2 operator record (XS; operator-authored, cannot be delegated)

**Closes:** blocker `D2` (`docs/governance/ACTIVE_TRACK.yaml:2017`).

The exact, non-negotiable form is parent §9.2
(`docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md:2051-2065`). It is
materialized without a self-referential commit hash: first, a separately
merged, operator-authored governance PR changes only D2 to the intermediate
ratification-anchor form in the parent spec while keeping it blocking. Then a
separate ledger-finalization PR changes `next_items[D2]` to exactly
`D2 RATIFIED — operator=<handle>; pr=<anchor-number>;
merge_commit=<anchor-merge-commit-40-hex>;
scope=WP-O5-strict-default`, `blocker: false`, with the managed authority
blocks regenerated. The implementation author cannot mint either step;
WP-O5's preflight verifies the referenced anchor is a merged ancestor
predating the WP-O5 baseline.

**What this spec adds:** the ready-to-send operator checklist — (1) confirm
CL-2's C1 evidence merged; (2) author and merge the one-line blocking
ratification anchor in your own PR; (3) finalize the ledger with that merged
PR number and commit; (4) run
`python3 scripts/governance/render_active_track_includes.py` in both steps;
(5) merge both before any WP-O5 packet is created. Nothing else.

### CL-4 — WP-O5 strict-by-default promotion (S; code)

**Closes:** blocker `WP-O5` (`docs/governance/ACTIVE_TRACK.yaml:2021`).

Parent §6 WP-O5 (`:1752-1808`) is the complete envelope: allowed files,
behavior map O5-B1..O5-B5, verification command, rollback, kill criterion.
Execute it verbatim under a Session Entry Packet. Sequencing constraints this
spec adds:

- Blocks on CL-2 and CL-3 merged (O5-B4/O5-B5 verify both mechanically).
- Blocks on CL-1-B4's adjudication if it found a real WP-O4 regression.
- On merge, flip `next_items[WP-O5]` to DONE with PR + merge commit in the
  same governance style as the other DONE items.

### CL-5 — M6-1 mutmut coordination (S; cross-track governance)

**Closes:** blocker `M6-1` (`docs/governance/ACTIVE_TRACK.yaml:2025`).

Parent §9.6 admits exactly two paths; pick one, in writing, with the
`dharmagraph-engine-2026-07` owner:

- **Path (a) — preferred:** the DharmaGraph owner lands the widening under
  its own packet: `paths_to_mutate` gains
  `"dharma_swarm/operator_core/onboarding/readiness.py"` and the runner/test
  selection gains the onboarding readiness battery, observing the documented
  TOML-array shape hazard (`pyproject.toml:86-97` — a bare string is walked
  character-by-character). `pyproject.toml` stays forbidden to WP-O6.
- **Path (b):** a governance PR explicitly transfers the `[tool.mutmut]`
  scope to this track before WP-O6 admits the file.

A warning-only overlap is not coordination (parent §9.6). Record the outcome
in `next_items[M6-1]` with the coordinating PR number.

### CL-6 — WP-O6 terminal battery (L; code — the last implementation packet)

**Closes:** blocker `WP-O6` (`docs/governance/ACTIVE_TRACK.yaml:2029`) and
criterion `wp_o6_readiness_property_battery`.

Parent §6 WP-O6 (`:1809-1894`) is the complete envelope: allowed files after
M6-1, behavior map O6-B1..O6-B7, required-mutant list, external mutation-run
protocol, rollback, kill criterion (*correctness wins over latency*).
Sequencing and content constraints this spec adds:

- All four named test files are greenfield (§1.4); the property battery
  `tests/properties/test_onboarding_readiness_properties.py` must contain
  Hypothesis properties over the readiness verdict/exit mapping — lossless
  condition retention, precedence ordering, and no nonpass→pass promotion
  under any generated condition set (the O6-B7 obligations) — so that the
  existing criterion passes by construction, not by an empty file (the
  criterion already guards this: a missing file exits 4, and
  `check_test_passes` requires a genuine pass,
  `scripts/governance/check_track_status.py:730-756`).
- The mutation gate runs only after CL-5 resolved which track owns the
  `pyproject.toml` diff; `mutants/` and stats stay outside the admitted
  worktree (parent WP-O6 verification block).
- WP-O3's deferred verification (performance budgets, mutation strength,
  O3-B4/O3-B5 adversarial matrix — per `next_items[WP-O3]`) is discharged
  here, not silently dropped.

### CL-7 — A1/A2/A4 verification record (XS; governance)

**Closes:** the parent §6.1 requirement that the adapter repairs *join before
the independent proof* — as a merged record, not a session observation.

One governance PR (or a section of the CL-8 preflight) recording, with
current-HEAD citations, that `DEVIN.md`, `QWEN.md`, and `docs/AGENTS.md`
carry the repaired custody language observed in §1.5. If any regressed,
the repair belongs to that file's owner (parent §9.5) — this track records,
never edits.

### CL-8 — Terminal independent clean-room proof (M; decorrelated verifier)

**Closes:** blocker `TERMINAL-PROOF` (`docs/governance/ACTIVE_TRACK.yaml:2033`).

Parent §13 (`:2186` onward) is the complete protocol: sterile acquisition
with `run_sterile`, locked bootstrap, read-only successful path, byte-identical
deterministic core, §8 performance protocol, disposable negative controls
with the exact exit matrix, and the proof artifact outside the worktree.
Constraints this spec adds:

- **Verifier eligibility is checkable, not vibes:** the verifier's identity
  must appear as author/co-author on none of the WP-O1..WP-O6 implementation
  PRs (#907, #911, #912, #913, #916, #918, #920, #926, #937, #942, the CL-4
  and CL-6 PRs). An agent seat that only reviewed is eligible; the operator
  is eligible.
- The proof and the final WP-O6 candidate merge together without author
  changes (parent §13 preamble). If the proof fails, the failure goes back
  to CL-6 as a corrective packet; the verifier does not fix it.
- On merge, flip `next_items[TERMINAL-PROOF]` to DONE with the proof
  artifact digest and candidate integration sha.

### CL-9 — Closure flip (XS; governance — the last commit of the campaign)

**Closes:** the track.

One governance PR, only after `check_track_status.py` renders zero open
blockers and every criterion green in both the session and published
projections:

1. Track entry: `status: SHIPPED`, `closure_kind: VERIFIED_SLICE`,
   `closed_at: "<date>"` (shape of
   `docs/governance/ACTIVE_TRACK.yaml:2178-2181`).
2. Regenerate managed include blocks; the CLAUDE.md stamped digest moves the
   track to recently-closed.
3. Verify gates: `python3 -m pytest tests/test_active_track_governance.py
   tests/test_track_portfolio.py tests/test_agent_onboard.py -q` exits 0.
4. Record in the PR body: Titanium vNext baseline capture / WP-00 is now
   unblocked per the track description; WIP drops by one.

**Kill criterion:** if any ship block reappears between approval and merge
(regression drift), the flip PR closes unmerged and the regression gets its
own corrective item. A closure commit never carries a "small fix while we're
here".

---

## §5 Validation for this specification-only change

```bash
git diff --check
python3 scripts/docops/check_docops_integrity.py --changed-from 971923a71c18b0effb5bbf2db279e85e8a7db413
python3 scripts/governance/render_active_track_includes.py --check
python3 -m pytest tests/test_docops_integrity.py -q
```

If a tool is unavailable in the authoring environment, record the exact
command and exit instead of skipping silently. Confirm only this file
changed, every citation resolves at the evidence baseline, and no generated
report or receipt entered the diff.

## §6 Non-goals

- No implementation, ledger edit, criterion change, or workflow edit in the
  PR that lands this document — CL-1..CL-9 are each their own admitted change.
- No reuse of this document as live status: `make onboard` and
  `check_track_status.py` own that, always.
- No BR-id closure, demotion, or addition.
- No production, `PRODUCTION_READY`, or `SUBSTRATE_TRUSTED` claim — closure
  kind is `VERIFIED_SLICE`; a stronger claim is a new track with a Final
  Boss packet (`scripts/governance/check_track_status.py:1446-1456`).
- No Titanium work before CL-8's proof merges.
