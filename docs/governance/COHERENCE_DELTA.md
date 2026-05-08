# Coherence Delta — Why The Gate Exists And What Each Field Means

**Subordinate to:** [`CLAUDE.md`](../../CLAUDE.md) (behavior) and [`SOVEREIGN_MANIFEST.md`](SOVEREIGN_MANIFEST.md) (architectural truth). When this file disagrees with either, they win.

**Companion to:** [`BUILD_SESSION_ENTRYPOINT.md`](BUILD_SESSION_ENTRYPOINT.md) (the read order) and [`CANONICAL_DOC_STACK.md`](CANONICAL_DOC_STACK.md) (the doc-stack registry).

---

## Why this gate exists

Three independent audit waves on 2026-05-07 (megafile survey, convergence audit, codex validation pass) converged on the same finding: **work scatters without a persistent merge-time discipline.** The repo has many maps, but PRs were landing without each PR re-reading them, without each PR registering its own drift, and without each PR linking its change back to the architectural surface it touches.

The Coherence Delta gate is the four-field discipline applied at the merge boundary. It does not introduce new substrates. It closes the loop between:

- The **map of organs** (what exists, where, how it connects) — see [`docs/architecture/NAVIGATION.md`](../architecture/NAVIGATION.md)
- The **declared-vs-actual gap log** (what's broken, stale, or degraded) — see the broken-register surface (`docs/state/BROKEN_REGISTER.md` once landed; until then, `INTERFACE_MISMATCH_MAP.md` is the closest substrate)
- The **architectural truth** (the one-sentence answer to "what does this organ do?") — see [`SOVEREIGN_MANIFEST.md`](SOVEREIGN_MANIFEST.md)
- The **immune system** (interface mismatches that cause runtime failures) — see [`INTERFACE_MISMATCH_MAP.md`](../../INTERFACE_MISMATCH_MAP.md)

A PR that fills the four fields cannot bypass these. A PR that doesn't fill them flags itself for review.

---

## The four fields, defined

Every PR must answer all four. If any answer is genuinely UNKNOWN, the PR must say *why* it is unknown (e.g., "this is a docs-only change with no organ scope" — that is a valid answer; "I don't know" is not).

### 1. Organ touched

**What it asks:** name the module(s), package(s), or file(s) the PR modifies, and the architectural layer they live in. One PR should touch one organ; if the PR touches several, name the primary one and list the rest.

**Anchor:** [`docs/architecture/NAVIGATION.md`](../architecture/NAVIGATION.md) (the module map) and [`SOVEREIGN_MANIFEST.md`](SOVEREIGN_MANIFEST.md) (the architectural truth at the package level).

**Why it matters:** without this, blast-radius analysis is impossible at review time. A reviewer reading "organ touched: `dharma_swarm/shakti_executive/inputs.py` (executive layer)" can immediately consult NAVIGATION.md to see what depends on that organ.

**Examples:**
- ✓ `dharma_swarm/shakti_executive/inputs.py` (executive feedback intake; layer 4 of NAVIGATION.md)
- ✓ `~/Library/LaunchAgents/com.dharma.cron-daemon.plist` (cron / metabolic-clock organ; out-of-repo but in-system)
- ✓ governance / docs (`docs/governance/COHERENCE_DELTA.md`, `.github/PULL_REQUEST_TEMPLATE.md`) — for self-applying meta-PRs
- ✗ "various files" — too vague; if the PR is genuinely cross-organ, name the primary one and list the rest
- ✗ "see diff" — the reviewer needs the layer label, not the line count

### 2. Declared-vs-actual gap closed

**What it asks:** which previously-registered gap does this PR close, demote, or add? Cite the entry id and the file:line evidence that closes it.

**Anchor:** [`INTERFACE_MISMATCH_MAP.md`](../../INTERFACE_MISMATCH_MAP.md) (interface mismatches by id), and once landed, the broken-register surface at `docs/state/BROKEN_REGISTER.md` (BR-NNN ids).

**Why it matters:** registers without write-paths grow stale; PRs without register-paths fix things silently. Both fail. This field is the bidirectional bridge — the PR updates the register, and the register grants the PR provenance.

**Required action:** if this PR closes / demotes / adds an entry, the PR must include the register update in the same diff. No silent closure.

**Examples:**
- ✓ `MM-05 (DEGRADED → RESOLVED); evidence at orchestrator.py:1234, fixed by extracting public coupling.`
- ✓ `BR-002 (BLOCKER → WORKAROUND); evidence at shakti_executive/inputs.py:30, :162, :293; partial closure pending VentureCell polymorphism design.`
- ✓ `none — this is a pure docstring backfill; no gap closed, no new gap added.`
- ✗ "fixes a bug" — which one? in which register?
- ✗ "addresses tech debt" — name the entry id, or admit no entry exists and add one

### 3. Proof that re-reads the map

**What it asks:** which map / spec / register did you read *before* writing the change, and what verification step did you run *against the current state*?

**Anchor:** [`BUILD_SESSION_ENTRYPOINT.md`](BUILD_SESSION_ENTRYPOINT.md) lists the canonical read order. This field asks the PR author to point at which step of that order they actually performed.

**Why it matters:** the failure mode this gate guards against is "I rebuilt a substrate that already exists" or "I edited code without re-reading the spec it implements." Re-reading is the safety mechanism. Asserting that you re-read is the merge-time evidence.

**What counts:** any concrete verification step — a `make xray` output, a `gitnexus_impact` blast-radius, a grep that confirmed the symbol's usage, a re-read of a numbered file from the build-session read order.

**Examples:**
- ✓ "Read `BUILD_SESSION_ENTRYPOINT.md` step 0 + 1 + 2; ran `make xray` at HEAD; spot-checked `dharma_swarm/shakti_executive/inputs.py` against `SOVEREIGN_MANIFEST.md` package definition."
- ✓ "Read `INTERFACE_MISMATCH_MAP.md` for MM-NN; verified the mismatch still exists via grep at `path/to/file:line`; the fix in this PR closes it."
- ✓ "Read the [Phase 3 plan](file:line); ran the test subset locally; confirmed pass."
- ✗ "I know this codebase" — re-reading is not optional; the gate exists because confidence about codebases is the failure mode
- ✗ "(skipped)" — if the PR genuinely needs no map re-read, name why; "this is a typo fix in a single comment" is a valid answer

### 4. New drift introduced

**What it asks:** does this PR create any new drift that future agents will trip on? If yes, append it to the broken-register (or interface-mismatch map) in the same PR. If no, declare "none" explicitly.

**Anchor:** the broken-register surface (`docs/state/BROKEN_REGISTER.md` once landed; until then, [`INTERFACE_MISMATCH_MAP.md`](../../INTERFACE_MISMATCH_MAP.md)).

**Why it matters:** the worst category of drift is the kind nobody registered. Every PR is a candidate drift-source — small ones (a TODO that would land), medium ones (a behavior change the docs don't yet describe), large ones (a new dependency the architecture doesn't yet model). The discipline is to name them at merge time, not wait for the next audit wave to find them.

**What counts as drift:**
- A new TODO / FIXME / HACK comment in the touched code
- A new dependency on a schema field, env var, or external service that the docs don't describe
- A behavior change that contradicts a current spec (e.g., a "this never happens" guard that now fires)
- An intentional architectural separation that future readers might mistake for a bug
- A test that passes but whose preconditions are not yet stable

**Examples:**
- ✓ "BR-019 added: this gate is enforced honor-system only — no pre-commit / CI / GitHub Action validates the four fields. First sloppy PR breaks the discipline. Future hardening tracked as separate work."
- ✓ "BR-022 added: the live-apply path at `evolution.py:2443-2457` is unreachable from the CLI — intentional architectural separation; future readers may mistake it for unreachable dead code."
- ✓ "none — this is a docstring change; no behavior change, no new dependency, no new schema field."
- ✗ "minor cleanup" — if it's truly clean, declare none; if it isn't, name the drift
- ✗ "TBD" — drift declared at merge time becomes register-tracked; drift left as TBD becomes future re-discovery cost

---

## Machine Enforcement

The Coherence Delta gate is machine-checked by
`.github/workflows/coherence-delta.yml`. The workflow runs
`scripts/governance/check_pr_coherence_delta.py` against the pull request body
and fails if any of the four field markers is missing, empty, or left as a
placeholder.

This is still not semantic proof. CI can verify that a PR body names an organ,
gap, map reread, and drift statement; it cannot prove those answers are true.
That residual limitation is tracked in `docs/state/BROKEN_REGISTER.md` as the
next hardening target.

---

## Self-application

This rationale doc and the gate itself ship in one PR. That PR's body fills the four fields. It is the first dogfood. Anyone reading this doc can read that PR's template body to see the gate applied to itself.

---

*The map is not the territory. The map is what makes the territory recognizable. The Coherence Delta gate is what makes every PR keep the map and the territory in agreement.*
