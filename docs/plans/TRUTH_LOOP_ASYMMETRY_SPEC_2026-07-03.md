# Truth-Loop Asymmetry — diagnosis, fixes, and standing rules (2026-07-03)

**Role:** engineered spec from the 2026-07-03 audit-rewire session (follow-on to
`FABLE5_CAMPAIGN_ROADMAP_2026-07-03.md`). Names the four systemic blind spots the
fresh-eyes pass found, records which fixes SHIPPED (with their owners), and
states the standing design rules so the same diseases cannot be reintroduced.
**Rule:** if this file disagrees with `make onboard`, a receipt, or the code,
trust those. Findings here are dated observations, not permanent truths.

---

## 1. Diagnosis — four asymmetries in the truth machinery

The repo's defenses are ferociously good against **overclaiming** (trust gates,
receipt quorums, adversarial verification, false-shippable ERROR) and almost
undefended against the inverse failures:

**A1 — The immune system did not audit itself.** The governance corpus had no
idempotence discipline: `SOVEREIGN_MANIFEST.md`'s count table was quadruplicated
by append-style refreshes; the strict DocOps gate was red on main for weeks with
nobody noticing.

**A2 — No underclaim detection.** Every defense catches claims AHEAD of reality;
nothing caught the ledger falling BEHIND it. Observed live: the arena controls
blocker and Mike Slice 1 were both shipped-with-tests yet still listed as open
blockers in `ACTIVE_TRACK.yaml`.

**A3 — Green that means nothing.** `docops-reconcile-main.yml` ran 102
consecutive times with `conclusion: success` while **every single delivery push
was rejected** (`GH006` protected-branch, no bypass token) and downgraded to a
`::warning` nobody read. A repair organ that failed 102/102 times at its one
job, reporting green throughout. This is A2 at the CI layer.

**A4 — Incommensurable numbers with no stated relation.** The hermetic arena's
+0.625 lift (fixture pool CONSTRUCTED so routing wins) and the live −0.1 lift
(2026-06-10 anatomy audit) are objects of different kinds; no artifact stated
this, leaving C2 open to slow self-deception by harness improvement.

(A fifth observation — no persistence-in-time substrate; every "live" loop
criterion silently assumes an always-on host that does not exist — is REAL but
operator-gated; see §4.)

---

## 2. What shipped (this branch, 2026-07-03)

| Fix | Asymmetry | Owner surface | Proof |
|-----|-----------|---------------|-------|
| Duplicate-assertion tripwire: an asserted count token appearing >1x in its doc is a FAIL (WARN on advisory PR runs) | A1 | `scripts/docops/check_docops_integrity.py` (`assertion-duplicate`) | `tests/test_docops_integrity.py::test_duplicate_asserted_token_is_flagged` |
| Deduped + regenerated `SOVEREIGN_MANIFEST.md` VERIFIED NUMBERS (one row per metric, replace-never-append note) | A1 | `docs/governance/SOVEREIGN_MANIFEST.md` | `make docops-integrity` green |
| Underclaim detector: a `next_items` entry may declare `evidence_criterion: <criterion id>`; if that criterion PASSES while the item is still open (not prose-DONE), `check_track_status` emits `WARN track-underclaim` and the evidence JSON carries `underclaims` | A2 | `scripts/governance/check_track_status.py`, `docs/governance/ACTIVE_TRACK.yaml` | `tests/test_active_track_governance.py::test_underclaim_detector_flags_shipped_but_open_items`; live probe on Mike Slice 1 fires today |
| Reconcile delivery made honest: Tier 1 direct push only when `DOCOPS_RECONCILE_TOKEN` exists (rejected push with token = red); Tier 2 fallback = rolling bot PR on the already-registered `chore/docops-autorefresh` lane; neither delivered = job FAILS red. Weekly scheduled `docops.yml` run is now STRICT on counts (the floor that catches a rotted loop) | A3, A1 | `.github/workflows/docops-reconcile-main.yml`, `.github/workflows/docops.yml` | first post-merge run on main is the live proof; YAML+shell validated |
| Commensurability rule encoded at the evidence owner: C2 scorer documents and renders that hermetic arena lift is inadmissible; admissible = live seats, >=2 model families, same control arms. Arena surface states its win is fixture-constructed | A4 | `scripts/governance/trust_gate_status.py::score_c2`, `scripts/governance/arena_truth_report.py` | C2 evidence line renders in `trust_gate_status`; `arena_truth_report --check` replays |

Companion (previous commit, same branch): the Arena Truth read-only governance
surface + cold-start corpus + rigorous track criteria (`reports/governance/arena/`).

---

## 3. Standing design rules (the antibodies, stated once)

1. **Deliver-or-red.** A job whose purpose is to produce an effect (push,
   PR, receipt) must exit non-zero when the effect did not happen. A
   `::warning` is not delivery. Green must mean "did the job", never "ran".
2. **Replace, never append.** Generated/counted content in docs is rewritten
   in place to a fixed point. Any asserted token appearing more than once is a
   defect even when the copies agree (`assertion-duplicate` enforces).
3. **Symmetric epistemics.** For every mechanism that blocks a claim running
   ahead of evidence, name the mechanism that flags evidence running ahead of
   the ledger. `evidence_criterion` on next_items is the current instrument;
   attach it whenever a blocker's completion is machine-checkable. The detector
   only WARNs — reconciliation stays a human/owner act.
4. **Commensurability is declared at the evidence owner.** When two numbers
   look comparable but are not (fixture vs live lift), the scorer that consumes
   one of them states the admissibility rule in its rendered evidence — not in
   a doc nobody re-reads.
5. **No new governance machinery to fix governance** (BR-022, upheld): all of
   the above extend existing owners — zero new stores, gates, or schemas.

---

## 4. Operator decision queue (not code; do not silently block)

1. **Reconcile Tier 1 or Tier 2 enablement:** either provision
   `DOCOPS_RECONCILE_TOKEN` (bypass-listed fine-grained PAT / App token) for
   direct-push reconciles, or confirm "Allow GitHub Actions to create and
   approve pull requests" is enabled so Tier 2 bot PRs can open. If neither,
   the job now goes RED — by design.
2. **Reconcile the flagged underclaims:** Mike Slice 1 (`track-underclaim`
   WARN fires now); annotate DONE or narrow to the remaining live edge.
3. **Metabolism (A5):** the VPS host remains the single point of failure for
   every CLOSED_LIVE ambition (RUNBOOK §3e when reachable). No coding session
   can substitute for it.
4. **C2 becomes measurable:** the live arena lane (2+ model families through
   `DHARMA_ARENA_LIVE`, inheriting the hermetic control arms) needs provider
   keys and a ratified budget; until then C2 stays honestly RED.

## 5. Fine-tooth-comb addendum (2026-07-03, second pass)

A four-lane adversarial sweep (truth docs / workflow silent failures /
declared-rule violations / ledger-vs-reality) plus a full-suite + lint pass.
Fixed in this branch: the fabricated-clean surface-manifest health line in
onboarding (double schema mismatch masked 47 entities); the dead COLM clock
still broadcasting "crunch" months after the venue died despite handoffs
claiming it fixed (deadlines now live in operator-owned
`~/.dharma/research_deadlines.json` via `dharma_swarm/research_deadlines.py`);
CLAUDE.md's four phantom make targets; the loop map's superseded second verdict
table + stale hand-copied runtime numbers; LIVE_OPS_DASHBOARD claiming CURRENT
at 18 days stale; BR-014's drifted line citation; pre-announced "CLOSED" counts
in stale-pr/pr-dedupe (closes now counted only when they happen); the reconcile
writer's residual `|| true` swallow; 4 git-tracked runtime receipts removed;
~330 dead imports removed (re-export facades restored and marked); the
algedonic-event memory-write swallow now logs.

**Verified, deliberately NOT fixed here (owners in brackets):**

- `codex-mention-router.yml` single-PR path: gate/merge failures produce a
  green run (outcome is comment-visible; run status lies). Changing router
  exit semantics belongs to the Mike track's owned surface and needs care to
  not spam red on legitimately-unmergeable PRs. [merge-master-mike-d4]
- `merge_group` skip-evasion: `fourfold-warrant.yml` and `structure.yml`
  never re-check the batched tree at merge time (skipped required check =
  satisfied). Documented-by-design, but worth an operator second look.
- Credential reads bypassing `api_keys.py` (X_BEARER_TOKEN, TELEGRAM_BOT_TOKEN,
  LANGFUSE keys, GITHUB_TOKEN and HF tokens in ~20 modules/scripts) and
  hardcoded model pins at call-sites (worst: `subconscious_hum.py:178`,
  `master_prompt_engineer.py:566`, `router_v1.py:460-504`). Each needs the
  registry/resolver wiring done deliberately, not in a sweep. [routing/keys
  doctrine owner]
- 7 files added since 2026-06-25 already exceed the 500-line law (worst:
  `scripts/governance/runtime_receipt_coverage_report.py` at 3,285).
- Deep COLM references in the telos goal graph (`telos_substrate.py`,
  `telos_graph.py`, `ontology.py`, `workflow.py` `colm_paper`,
  `skills/researcher.skill.md`) — goal-graph semantics belong to the future
  research-depth track, not a text sweep.
- `manifest_health` reports two of its own checks as `unknown check_id`
  (`go_world_receipts_present`, `recursive_discovery_module_exists`) — the
  health checker itself has registry drift; now at least visible in onboard.

## 6. Anti-goals

- Do not soften deliver-or-red back to warnings to "reduce CI noise" — route
  noise into fixing the delivery path instead.
- Do not let the underclaim detector auto-close items; it demands
  reconciliation, it never performs it.
- Do not feed the hermetic arena lift into C2 or any capability narrative,
  regardless of how many controls it carries.
- Do not add a parallel counts pipeline; `check_docops_integrity.py` writers +
  the reconcile workflow remain the only owners.
