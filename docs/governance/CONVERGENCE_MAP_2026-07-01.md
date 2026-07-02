# The Convergence Map — dharma_swarm — 2026-07-01

**Method:** read-only investigation (Claude Code, Sonnet 5, ultracode). Built on three completed 2026-07-01
investigations (cited throughout, not re-derived): the ecosystem audit (`docs/governance/AUDIT_2026-07-01.md`),
the holon/sakshi_auditor design memory, and the Metabolization Sweep (`origin/codex/metabolization-ledger-20260701`).
Executed via the Workflow tool: 1 discovery agent → 8 gravity-center verification agents → 20 subsystem-maturity
agents → 2 fusion investigations → 1 claim-selection agent → 10 adversarial triple-check agents (42 agents total,
1,518 live tool calls, ~56 minutes of real investigation, all timestamps 2026-07-01 ~03:40–04:30 UTC). No edits,
commits, or destructive operations were performed.

---

## 0. Ground truth this map stands on — and one thing the required reading didn't know yet

The three cited investigations are correct as far as they go, but this repo moved under them within hours:

- **Branch drift is worse than every prior citation.** `agent/magpie-seed` @ `b6e6ae8ca` is **28 ahead / 308
  behind** `origin/main` (live `git rev-list`, checked twice 40 minutes apart during this investigation — it was
  406 uncommitted paths at 03:12 UTC, 428 by 03:42, 444 by 03:51). The morning audit measured 27/307. Treat every
  drift number anywhere in this document as a snapshot, not a fact.
- **`docs/governance/AUDIT_2026-07-01.md` itself is an untracked, uncommitted file** (`git log --oneline -- <path>`
  returns nothing) that exists in exactly one place: this one dirty worktree. If it were reset, the "required
  reading" would be destroyed. This is itself a live instance of this map's own subject matter — governance
  artifacts living outside the substrate they audit.
- **A previously-unknown artifact surfaced mid-investigation and changes the picture:
  `docs/governance/AUDIT_2026-07-01_REMEDIATION.md`** (also untracked, dated 2026-07-01 07:55 JST, ~31 minutes
  after the audit it responds to). It shows someone/some session already executed 4 of the morning audit's 5
  ranked recommendations within the hour: BR-007 reopened in `BROKEN_REGISTER.md`, algedonic triage manually
  revived (481+2 backlogged signals drained, cron re-enabled), the runtime-spine track's `SHIPPABLE`-at-70/100
  gaming closed (`hardening_score_at_least_75` added as a real completion criterion), stale doc claims fixed
  (`CLAUDE.md`/`INTERFACE_MISMATCH_MAP.md` now agree NEW-14 is an open BLOCKER), and — load-bearing for this
  map — **"AgentRunner self-editing memory is wired through the production `SwarmManager.spawn_agent` path."**
  This directly **stales one of this task's own named "known contrast pairs"**: the brief's premise that
  `AgentRunner`'s `AgentMemoryBank` is "built-but-dormant" was true this morning and is false now. Section 2
  corrects this with independent live re-verification (not just trust in the remediation doc's own claim).
- **`sakshi_auditor`** (the verification holon this map is also asked to instantiate): a real Claude Code Remote
  trigger (`trig_01Kzd5tAAcNzLpGwwGFLR9dy`, cron `0 */2 * * *`) exists and fired once
  (`last_fired_at: 2026-07-01T02:02:22Z`) — but persisted **zero** artifacts anywhere on this filesystem. This
  session backfilled `~/.dharma/agents/sakshi_auditor/{cadence_state.json, reports/20260701T032201Z.md}` (outside
  the dharma_swarm repo, per the design's own guardrails) so the next scheduled fire has real state instead of
  nothing. See §5 item 5 and the maturity entry in §2.

---

## Section 1 — Semantic Gravity Map

A gravity center is a word that pulled ≥3 non-unified implementations toward itself without them ever converging.
Three seeds were given (Receipt, Holon, Coherence); discovery found five more (Ledger, Bridge, Witness/Witness
Auditor, Verification/Verifier, Memory). All eight were independently deep-verified with live tool calls.

| # | Center | Implementations found | Classification | Should converge? | Confidence |
|---|---|---|---|---|---|
| 1 | **Receipt** | 5: `spine.EvidenceReceipt`, `ClosureEvidenceReceipt` (renamed from `closure_v0.EvidenceReceipt` 2026-06-05, one day after the ADR), `RuntimeReceipt`, `CostEntry`, `GoEvidenceReceipt` | genuine_necessity | **No** | High |
| 2 | **Holon / PersistentAgentIdentity** | 4+: ontology `PersistentAgentIdentity` (orphan, unregistered), `holon_bridge.load_holon()`, `living_agent_kernel.py` wake ledger, `roaming_onboarding.onboard_roaming_agent()` — plus 3 more found live (`ontology_agents.py`, `autonomous_agent.py`'s own `AgentIdentity`, `persistent_agent.py`'s wake loop) | mixed | **Yes** (contested — see §4 C1) | High |
| 3 | **Coherence** | 3: `OrganState.coherence_state`, the Coherence Delta PR-body gate, and a genuinely new find — `operator_coherence_cockpit.py`'s dashboard-rebuild readiness scorer | mixed (effectively false_pattern at the macro level) | **No** | High |
| 4 | **Ledger** | 8 named + 2 more found live (`human_yds_ledger.py`, `compounding_ledger.py`) = 10, plus a mischaracterization corrected (2 of the original 8 aren't ledgers at all) | mixed | **No** (one narrow exception) | High |
| 5 | **Bridge** | 30+ (discovery undercounted at ~12) across 3 unrelated problem classes: statistics correlator, SQLite graph-edge store, 28+ point-to-point adapters | mixed | **No** at code level; naming/governance fix only | High |
| 6 | **Witness / Witness Auditor** | 6, of which 2 genuinely collide (`witness.py`'s `WitnessAuditor` vs `sakshi/__init__.py`'s self-declared "Witness Auditor") and 3 are false-pattern inclusions | mixed | **Yes** (narrow) | High |
| 7 | **Verification / Verifier** | 6 named, 2 of which (`VerificationOracle`/`VerificationUnit`) turned out to be one coupled subsystem, not independent | false_pattern | **No** | High |
| 8 | **Memory** (Store/Router/Registry/Substrate/Plane/Lattice/Palace/Kernel) | 7 named + 1 more found live (`contracts.intelligence.MemoryPlane` Protocol + `SovereignMemoryPlaneAdapter`, a 3rd independently-built "canonical interface") | mixed | **Yes** | High |

### 1.1 Receipt — genuine, ADR-governed layering (No)

All 5 verified live at exact file:line (`spine/receipt.py:37`, `operator_core/closure_v0.py:69`, `runtime_state.py:650`,
`cost_tracker.py:59`, `operator_core/go_evidence_bridge.py:26`). Each owns a non-overlapping layer — in-flight
dispatch proof, test/acceptance closure, persisted runtime events, cross-provider cost accounting, cross-language
(Go→Python) sidecar parsing — and the split is a **binding ADR**
(`docs/research/RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md`, PR #471, 2026-06-04) with an explicit anti-double-write
rule. Two real, narrower execution gaps exist inside the reconciliation glue itself (not between the receipt
types): `spine/adapters.py:303`'s `runtime_receipt_kwargs()` — the association seam the ADR prescribes — has
**zero production callers**, and `a2a_server.py:399`'s `submit()` hand-rolls the identical field mapping inline
instead. Adversarial re-verification (§4, C4) found this is not A2A-specific: the same unadopted pattern recurs
at 5 more sites, including inside the spine package's own `warrant.py`. **Also found live and separately worth
noting: the CostEntry→EvidenceReceipt.cost_usd bridge the ADR prescribes was never built at all** (zero connecting
code) — a second undelivered ADR follow-through, not a reason to converge the types themselves.

### 1.2 Holon / PersistentAgentIdentity — mixed, and the recommended fix has a bug (Yes, contested)

The real population is bigger than the 4 seeds: 3 more overlapping identity representations exist live
(`ontology_agents.py`, `autonomous_agent.py`'s own `AgentIdentity`, `persistent_agent.py`'s independent wake
loop). Per-mechanism: (1) ontology `PersistentAgentIdentity` is a **dead, orphaned unification attempt** — zero
schema registration, one hand-inserted DB row (`merge-master-mike`), `git log -S` finds it was never written by
any commit, and `OntologyRegistry.create_object()` rejects the type name today, so it cannot proliferate further.
(2) `holon_bridge.load_holon()` is production-proven (20 real importers, not the cited 9+; 6 live agents satisfy
it). (3) `living_agent_kernel.py`'s wake ledger is a deliberately separate governance/audit layer, already an
open, tracked reconciliation item (`composer-holon-spine-longrun-2026-06` blocker #3). (4)
`onboard_roaming_agent()` is the operator-ratified canonical onboarding path (24 of ~28 agent dirs) — 4x
`holon_bridge`'s reach. **The decisive, previously undocumented finding:** 3 agents (`codex_composer`,
`devin-roaming-2987d222`, `opus_composer`) carry **both** `identity.json` and `living_agent.json`, mtimes ~12
days apart (range 7.7–16.3 days), with no shared write path — hand-patched drift invisible to the one document
(`AGENT_HOME_RECONCILIATION.md`) that should track it.

**§4 adversarial result (C1) matters here: this is a disputed verdict, not a settled one.** The `re_derive` lens
confirmed the underlying facts. The `refute` lens found the prescribed fix is technically broken: `onboard_roaming_agent()`'s
`living_agent.json` has no top-level `model`/`provider`/`system_prompt` keys (they're nested or absent), while
`holon_bridge.py:139-141` does `model = identity.get("model"); if not model: raise ValueError(...)` — repointing
`holon_bridge`'s read path there **as literally stated would crash every currently-registered holon**, and
`autonomous_agent.py`'s caller only catches `FileNotFoundError`, not `ValueError`. The refute lens also found the
convergence direction may be backwards: `identity.json` is the actively-mutated file (task counters, prompt
generation) and is the owned surface of the currently-ACTIVE `composer-holon-spine-longrun-2026-06` track, while
`living_agent.json` for those 3 agents has sat untouched 20+ days. **Net: the `should_converge:true` direction is
probably right in spirit (stop the identity.json/living_agent.json split), but the specific target — onboarding's
schema becomes canonical — is wrong as stated and would need a real schema-reconciliation step first, not a
direct read-path swap.**

### 1.3 Coherence — a naming collision, not a split (No)

Confirmed: `OrganState.coherence_state` (`operator_core/operating_facts.py:37`, born 2026-05-07, PR #155) and the
Coherence Delta PR-body gate (`.github/workflows/coherence-delta.yml`, born the *same afternoon*, PR #154, ~3
hours apart) are structurally unrelated — zero shared imports, different data models, independently authored.
Investigation surfaced a **third, previously-unknown "coherence" system the framing didn't know about**:
`operator_coherence_cockpit.py` (2,012 lines, born 2026-06-23, feeds the live `/dashboard/cockpit` route named in
this repo's own CLAUDE.md as the active Mandala Mission Control priority) — zero code overlap with either of the
other two. All three are production-proven today (116/117 relevant tests green, live-verified). The one real,
if harmless, defect: `COHERENCE_STATES` is copy-pasted with divergent member ordering between
`operating_facts.py:37` and `control_surface_models.py:113` (6 days apart) — should import from one source, but
currently inert since both are used only for membership checks. **Adjacent, unrelated-to-classification finding:**
a live-reproducible test failure, `tests/test_control_surface.py::test_cockpit_aliases_control_surface_page`,
caused by a 2026-06-28 rescue commit reintroducing a pre-2026-06-24 assumption `origin/main` already fixed —
branch-hygiene drift specific to this checkout.

### 1.4 Ledger — a generic English word, one narrow real duplication (No)

All 8 cited implementations verified at exact file:line; two are mischaracterized (`MemoryPromotionDecisionLedger`
is a computed validation report with no load/save of its own; `KernelLedgerIntegrityRef` is a cross-ledger health
check, not a ledger). Discovery undercounted by 2 (`human_yds_ledger.py`, `scripts/compounding_ledger.py`, both
missed because they're function-based, not classes). The discovery claim "none import from one another" is
**false** — `AIReciprocityLedger` explicitly imports `GaiaLedger`'s types, then re-implements (rather than
reuses) its hash-chain mechanics — the one real, narrow convergence opportunity in this cluster (extract a
shared hash-chain mixin, source = `GaiaLedger`, the most production-proven). **A positive counter-example was
found that undercuts the whole "sprawl" framing**: `KernelRunStore` already internally unifies 4 hash-chained
JSONL streams through shared helpers — proof that convergence happens naturally within one file when engineers
are co-located in it. **The single highest-value adjacent finding, outside the named 8**: the
`_verify_hash_ledger()` hash-chain-verification algorithm is copy-pasted near-verbatim **6 times** across the
LivingAgentKernel/holon family, including one **confirmed worktree-drift clone**
(`holon_l4_activation.py`, cloned from `living_agent_kernel_activation.py` 13–18 days later — see §4 C5). This
is the exact `_complete_deferred_startup`-style failure CLAUDE.md's Cross-Worktree Awareness section already
names — a real, zero-domain-cost convergence target.

### 1.5 Bridge — governance/naming gap, not a code problem (No, but flag it)

30+ modules use the `Bridge` suffix across 3 architecturally unrelated domains (statistics correlator, SQLite
graph-edge store, 28+ point-to-point integration adapters) — every `class XBridge:` is base-less, zero shared
interface exists or would be worth building (method signatures share nothing). This is a genuinely-known,
**already-flagged-and-partially-metabolized** issue: `docs/governance/REPO_GOVERNANCE_AUDIT.md:112-121` (dated
2026-05-20) independently named this "C6: Bridge Proliferation Without Registry" over a month ago, and 4 modules
it called zombies have since been deleted. What's still missing: `Bridge` is **not registered anywhere** in the
naming SSOT (`docs/ontology/semantic_objects.yaml`/`semantic_aliases.yaml` — zero hits), despite CLAUDE.md
mandating exactly that check before inventing a name. Fix is documentation/governance, not code.

### 1.6 Witness / Witness Auditor — a real collision with a clean fix (Yes)

The doctrinal core of the whole system (Sakshi/Drishti) is genuinely double-claimed: `witness.py`'s `WitnessAuditor`
(live, production-wired into `swarm.py:2456-2459`'s tick loop and `orchestrate_live.py`'s background loop; both
independently confirmed firing **today** via live log + a real StigmergyStore mark matching its exact code
strings) and `sakshi/__init__.py`'s docstring, which reuses the identical name "Witness Auditor (Provenance Chain
Guardian)" for `ProvenanceLog` — a structurally different, **zero-production-call-site** mechanism (test-only).
`cybernetics_codex.py`'s Loop-6 registry slot never actually binds to either — its `build_loop_statuses` check
reads an unrelated generic `runtime_receipts` table. §4 (C2) independently re-confirmed all of this with even
stronger live evidence than the original citation, and caught that the "1,013 real witness-log entries"
corroboration in `CYBERNETIC_LOOP_MAP.md` is itself a misattribution — those entries come from `telos_gates.py`'s
unrelated think-point logger, not `WitnessAuditor`. **Recommendation, narrow and editorial (no code merge):**
(1) re-word `sakshi/__init__.py`'s docstring to drop the "Witness Auditor" self-declaration; (2) rewire
`cybernetics_codex.py:609`'s Loop-6 check to read `witness.py`'s real evidence substrate instead of the unrelated
table. `WitnessGateEnhancement`, `WitnessVerdict`, `WitnessReception` are correctly separate and should not be
touched.

### 1.7 Verification / Verifier — false pattern (No)

6 named classes across 5 domains that share nothing but the English word: ecological-offset attestation
(genuinely one coupled subsystem with `VerificationUnit`, not two independent ones as discovery framed it),
operator-cockpit drift-repair timeline events, an autonomous overnight loop's ad hoc check bundle, the standalone
`holon/` package's import-firewall linter (**architecturally forbidden** from sharing any dharma_swarm base
class), and a GitHub PR-review-bot webhook handler. No shared protocol exists or would make sense; unification
would be actively harmful in the `holon/` case. **A larger, genuinely real "Finding/Report" reporting-shape
duplication was found adjacent to this** (`holon/verifier.py`'s `VerificationFinding`/`VerificationReport` vs.
`living_dock_verifier.py`'s near-identical `LivingDockFinding`/`LivingDockReport`, plus 25+ other `*Finding`
modules repo-wide) — a different, larger candidate this task didn't scope in.

### 1.8 Memory — the sharpest, most self-aware sprawl in the repo (Yes)

The repo's **own governance tooling already treats this as a known problem**:
`scripts/governance/check_memory_kernel_canonical.py` polices new "memory-authority" class names via a denylist
with a hand-maintained allowlist of 6 grandfathered exceptions — containment, not resolution. Live-running the
check itself (`--base-ref origin/main --head-ref HEAD --no-worktree`) surfaces a **currently-failing, unenforced
violation**: `holon/memory_kernel/__init__.py`'s second `MemoryKernel` class — a genuine architectural necessity
(verified zero parent-package imports, standalone-installable) but an avoidable identical-name collision, and the
check that would catch it is wired into **zero** CI workflows or Makefile targets. A **3rd, previously-unknown
"canonical memory interface" was found**: `contracts.intelligence.MemoryPlane` (Protocol) +
`SovereignMemoryPlaneAdapter`, wrapping a 3rd physical database (`runtime.db`) — not the 2-way split the seed
implied. **The load-bearing correction to CLAUDE.md's own doctrine**: `MemoryKernel` is claimed canonical with
`MemoryLattice`/`MemoryPalace` "subordinate" — verified **false in the executing system**: the actual production
hot path (`orchestrator.py`, `organism.py`) calls `MemoryLattice`/`MemoryPalace` directly and bypasses
`MemoryKernel`'s facade (which has ~1 real, mostly-optional caller family). **Recommendation, explicitly
overriding the "default to production-proven" instruction:** `dharma_swarm/memory_kernel/facade.py`'s
`MemoryKernel` should still be the convergence target for the context/agent-memory front door, not
`MemoryLattice`/`MemoryPalace` — naming the currently-live incumbent canonical would just relabel the system that
*produced* today's fragmentation; `MemoryKernel` is purpose-built for consolidation (read-only by construction,
real census/promotion-gate machinery already built to absorb other surfaces) and is what the repo's own doctrine
already declares the target. This is a finish-the-migration problem, not a pick-the-other-one problem.
`RoutingMemoryStore` (router telemetry, different domain) and `KnowledgeStore` (backend plumbing, not an
authority) should **not** converge — a naive name-pattern grep conflates "has Memory in the name" with "is a
competing authority."

---

## Section 2 — Evolution-Maturity Map

20 subsystems, each independently live-verified (traffic evidence, test runs, real call-site greps, commit
recency — never claimed status alone).

| # | Subsystem | Maturity | Key live evidence | Last real commit |
|---|---|---|---|---|
| 1 | DarwinEngine (`evolution.py:226`) | MIXED | 12,228-entry archive, last write 8 min before check; local "rescue" fix (260a11539) unreconciled with a materially better fix already merged to `origin/main` (dbdd24167/#562) that this branch never received | 260a11539 (local) vs dbdd24167 (main, unmerged here) |
| 2 | `AgentRunner`'s `AgentMemoryBank` | **PRODUCTION_PROVEN** (corrected from "dormant") | Live-wired through the one real spawn call site (`swarm.py:895-900`); 40+ agent dirs with fresh JSON writes ~25 min before check; independently confirmed by `AUDIT_2026-07-01_REMEDIATION.md`'s own claim | n/a (runtime-usage fact) |
| 2b | Letta-style `AgentMemoryManager` | MIXED | Also live in parallel (384 real SQLite rows), but its self-directed `get_memory_tools()` API has **zero callers anywhere** — the actually-dead piece, not `AgentMemoryBank` | n/a |
| 3 | `gaia_ledger.py` `ConservationLawChecker` | MIXED | 3/5 laws wired into `check_all()`; `check_temporal_coherence` is self-contained and should be wired now (2-line fix); `check_additionality` is genuinely blocked (no `baseline_co2e` field exists anywhere in GAIA) | d69519c45 (2026-03-11, only commit ever) |
| 4 | SAB flywheel (HTTPS) | MIXED | Transport/agora production-proven (live 200, hash-chain valid, real ~24h posting cadence); **today's new tool** (`sab_flywheel_tick.py`) is built-but-dormant (2 dry runs, zero live submissions); underlying content-quality gate broken (depth_score=0.0 on all 38 posts) | f1f3e140e (2026-07-01) |
| 4b | WSS-NATS bridge (qwen_code) | **ABANDONED_EXPERIMENT** | 13 days stale, 1 cycle, zero messages ever, no live process | 2026-06-19, untouched since |
| 5 | Ontology-native template (revenue lifecycle) | MIXED | Base `TelicSeam`/`OntologyRegistry` pattern production-proven at scale (5,900+ live objects); `RevenueTelicBridge` extension fully built/tested, **zero production rows ever** — wired only to the dead legacy `Organism` class, bypassed by the live `OrganismRuntime` and the live revenue API router | 60171d4969 (2026-05-10) |
| 5b | Spine/ontology divergence doctrine | MIXED | The cited ADR (equivalence matrix) never actually discusses ontology — the real, precise decision lives in `RUNTIME_TRUTH_SPINE_COMPLETION_PLAN.md` ("Hold the line"); that decision has drifted toward unexamined — never entered `ACTIVE_TRACK.yaml`, and the track's TTL expires **today** | 2026-06-04 doctrine, unrevisited since |
| 6 | **sakshi_auditor** | **ABANDONED_EXPERIMENT** | Trigger fired once, zero persisted artifacts before this session's backfill; doesn't meet its own design doc's minimal "is a holon" bar | none (zero git footprint) |
| 7 | Algedonic emergency channel | MIXED | Writer live/healthy 3+ months unchanged; consumer died silently 10.5 days, **deliberately revived** via the `AUDIT_2026-07-01_REMEDIATION.md` pass (not an accidental side-effect as first hypothesized) — but no watchdog on the watchdog | 8a44f5f8d (2026-05-09) |
| 8 | `witness.py` `anomaly_signals.jsonl` | BUILT_BUT_DORMANT | 27,530 lines, actively growing, but its one nominal reader (`WitnessJsonlAdapter`) hard-caps at the first 100 lines of a monotonically-growing file — structurally blind to 99.6% of its own lifetime by construction | 974de272c3 (2026-05-10) |
| 9 | `vector_store.py` ANN search | MIXED | Audit's "every recent row shows the dependency-missing pattern" is **falsified** by full data (7/8,562 rows, 0.08%, clustered in one 24h window); mechanism independently **reproduced live** on `/opt/homebrew`'s Python 3.14 (fleet-wide interpreter drift is the real root cause); 56GB/24.8M-row unpruned store forces near-permanent fallback mode | 260a11539 (guard, local only) |
| 10 | `handoff.py` | MIXED | Producer production-proven (231 real council-turn records); consumer (`acknowledge`/`reject`/`get_pending`) fully built, tested, **zero production callers ever** — same one-way-telemetry pattern as #7/#8 | 3ffe5b7c7 (2026-03-09, logic frozen since) |
| 11 | BR-007 ontology/runtime split-brain | BUILT_BUT_DORMANT | `store_sync` still disabled; split confirmed byte-identical to this morning; root cause traced to code (`ontology_runtime.py`'s cwd-aware path vs `daemon_config.py`'s lack of one) — re-enabling as-is would sync stale data and orphan the live copy | 0c3fe4ae3 (2026-05-11) |
| 12 | SWE-bench "Forge" harness | MIXED | Measurement engineering mature (real Docker grading, rigorous statistics); the actual research question (does coordination beat one strong model) is **fully null** — independently re-derived >1,000 non-positive real closeouts, 0 genuine positive; only "positive" result found is a self-disclosed synthetic/offline simulation; fragmented across 6 worktrees, one lane (`feat/rsi-lab`) genuinely active + pushed today | ad3183434 (2026-07-01) |
| 13 | `StigmergyStore` | MIXED | Genuinely live, 30+ real call sites, actively written seconds before check; but its 2026-06-16 concurrency fix is stuck unmerged (origin/main still racier); 401-auth-spam now 14.5% of recent traffic (was 5% overall); **a shadow `.dharma/` state tree at repo root was found actively fooling mtime checks today** — the exact "decoy" pattern reproduced live, not theoretical | 5deeb970b9 (unmerged to main) |
| 14 | TELOS Morning Refinery | MIXED | Governed track = doctrine-only (dashboard is a hardcoded static array); the "DEEPEN heart absent everywhere" claim is now **stale** — `deepen.py` exists and works for 3/4 tiers on an ungoverned, PR-less branch; "debate"/"harden"/"implement-as-cell" remain genuinely zero-code everywhere | 7383eb81d (2026-07-01) |
| 15 | Operator Idea Spark ingest | BUILT_BUT_DORMANT | 229 tests green (verified live), actively developed **today**, pushed to origin but **no PR ever opened**; root cause traced to the 11/11 WIP-saturated portfolio having no admission valve; actively at risk of silent loss — a real, small, uncommitted bugfix exists only in the shared, background-branch-switching-prone worktree | 7383eb81d (2026-07-01) |
| 16 | Metabolization Sweep Ledger | BUILT_BUT_DORMANT | Reusable core is genuinely good (877 unique rows, zero corruption, real `--verify-only` CI-gateable check); PR #737 open, 30/30 CI green, 0 reviews; date/branch-name literals hardcoded, would misdate a second run | 8110909bf (2026-07-01) |
| 17 | DharmaVerifier-Ranker v0 | **ABANDONED_EXPERIMENT** (leaning mixed) | Real, tested (4/4 passing), explicitly killed same-day for 60-75% overlap; the redaction/inventory utility slice is genuinely novel and worth preserving as reference | 8db43bde0 (orphan branch, never pushed) |
| 18 | Pudgala Forge (PR #693) | **PRODUCTION_PROVEN** — but **absent from this investigation's own base branch** | Fully verified live on `origin/main`; **AI-M1 enforcement is NOT safe to flip** — 4/4 real active tracks on `origin/main` are undergraded, `--enforce` fails closed on the whole portfolio right now | dd02c1e03 (2026-07-01, main) |
| 19 | Mike's merge-trust organ (PR #707) | MIXED | GH Actions CI check genuinely live (real successful runs today, correctly non-blocking); convergence-advisory is shipped-and-tested but **dead in the only daemon that runs it** — the live `launchd` daemon points at a worktree 36 commits behind `origin/main` that predates PR #707 entirely (confirmed: 0/30 real cycle receipts contain the `advisory` key) | 141809675 (merged, not running) |
| 20 | cybernetics-codex-stewardship track | MIXED | Genuinely working code — ran live, produced real diagnostics on the first try; but its "SHIPPABLE" gate is satisfied only by two files uncommitted since 2026-06-29 that would vanish on a worktree reset; a more capable v2 fork sits 8-days-stale on `origin/main`, never reconciled with this branch's v1 | cc9c05f21 (this branch) / f4814580a (main, stale) |
| 21 | runtime-truth-nats vs -reconciliation | MIXED | Reconciliation lane: durably stable, 11/11 criteria, zero churn risk. NATS lane: real hard-won live-broker evidence (genuine cross-process HANDLER_ACKED receipt, 6-model council 100/100) but its freshness gate is **mtime-keyed on an uncommitted artifact pile** — watched flip from 3/3 SHIPPABLE to 1/3 within 3 hours with byte-identical code | cc9c05f21 (committed) / uncommitted campaign work |

**Correction flagged loudly:** the task brief's own contrast pair — "AgentRunner's headline AgentMemoryBank
(built-but-dormant)... a quieter Letta-style store actually carries production traffic instead" — is now **wrong
in both halves**. `AgentMemoryBank` is live and wired through the real production spawn path (independently
re-confirmed here, not just trusted from `AUDIT_2026-07-01_REMEDIATION.md`'s own claim). The Letta-style store
also carries real traffic, in parallel — but its self-directed tool-calling API (`get_memory_tools()`) is the
piece that's actually dead. Both stores fire on every task completion today; the real finding is redundant
parallel writes, not one-live-one-dead.

---

## Section 3 — Fusion / Consolidation Candidates

### 3.1 The verification trio: Pudgala Forge + Mike's organ + sakshi_auditor

**Verdict: do not unify the evaluators. The split is real and load-bearing — but one formal integration hook
already exists and should be used, later, not now.**

Reading every evaluator function in both shipped systems (`check_track_status.py:261-651`,
`pr_convergence_policy.py`, `reviewer_quorum_repair.py`) and grepping for
`llm|judge|frontier|semantic|holistic` across all of it: **zero hits.** Pudgala and Mike are 100%
structural/mechanical — file existence, git ancestry, PR metadata, pytest exit codes, mutation scores. Neither
has any notion of "read this claim and check it against the world." `sakshi_auditor`, even in its single
orchestrator-backfilled demo run, did exactly that (caught branch drift worsening within hours; caught its own
trigger's claimed-live-vs-measured-dead gap) — a category of catch neither Pudgala nor Mike can structurally
represent. This mirrors, precisely, why the same-day adversarial review killed DharmaVerifier-Ranker v0: trying
to build **one thing** that spans both territories produces 60-75% duplication. Forcing them into one spine now
would either slow Pudgala's per-PR gate to LLM latency (breaking Mike's whole "fast, authentic CI check" model)
or dumb the semantic layer down to a sub-minute budget (defeating the reason it exists).

**The integration hook that already exists, unused:** `evidence_grades.yaml:131-137` reserves grade **S7
(`S7_VERIFIED`, kind `verifier_approved`, "an independent verifier — signer != committer — approved a machine
receipt")**, empty since Phase 1 shipped. This is precisely sakshi_auditor's future output shape. Recommended
integration, once real: a genuine sakshi_auditor run emits a `verifier_approved` criterion result through the
*same* `VerifiedMachineReceipt` hash chain Pudgala already writes to — no new receipt class (per the ADR in §1.1
that already exists specifically to prevent that), no logic change needed in `check_track_status.py` (it already
reads whatever kind a criterion declares). It must **never** become a blocking precondition on Mike's CI-green
gate (LLM latency/cost/nondeterminism on the merge-critical path is exactly what Mike's organ exists to avoid)
and must **never** let sakshi_auditor request/dismiss a GitHub review itself (the same integrity≠authenticity
correction that already forced Mike's own PR #707 redesign).

**Precondition before any of this is real:** don't build the S7 wiring yet. sakshi_auditor is 0-for-1 on real
persisted runs. Sequence: fix the trigger-fires-but-nothing-persists gap (this session's backfill is a stopgap,
not a fix — root cause unestablished), get 2-3 real consecutive runs, only then land the small `verifier_approved`
criterion PR.

**Precise ownership boundary, so it doesn't silently re-converge:** Pudgala owns the closed-world declared
claim/evidence ladder — grows only by activating its own reserved grades (S4/S5/S8), never by adding prose
reasoning. Mike owns PR-level traffic control — should never grow a "read the diff and judge it" branch. Sakshi
owns holistic claim-vs-reality drift detection — should never re-derive Pudgala's structural checks (pure
duplication of already-fast, already-correct machinery) and must stay shadow/advisory until a real track record
exists.

### 3.2 SystemMap format — genuinely worth extending, but not a drop-in replacement for these audits

`scripts/system_map_populator.py` was read in full, then **run live** against `docs/governance/` as a real,
un-modified proof-of-concept (a script run, not a source edit — this investigation stayed read-only on code):

```
.venv/bin/python3 scripts/system_map_populator.py --audit-dir docs/governance --output <artifact> --json
```

Result: it picked up **28 real `.md` files** in `docs/governance/` — more usefully than expected from reading the
source alone — including the previously-unknown `AUDIT_2026-07-01_REMEDIATION.md`, and produced 15 real organs
with genuine `coherence_state` classification and real `evidence_refs` (e.g. `algedonic_stream` → `partial`, 11
refs citing exact lines in `AUDIT_2026-07-01.md` and the remediation doc). This is a stronger, more honest
partial-credit signal than a source-only read suggested.

**But it is not, today, a substitute for this map or the ecosystem audit**, for three concrete reasons found by
running it: (1) its `AUDIT_ORGANS` list is a hardcoded 7-item tuple (`metabolic_clock`, `algedonic_stream`,
`onboarding_spine`, `truth_spine`, `central_loop`, `self_evolution`, `recognition_seed`) — none of today's 8
gravity centers or 20 maturity subsystems (Ledger, Bridge, sakshi_auditor, Pudgala, Mike, Forge fragmentation,
etc.) have a matching organ, so they produce zero signal in this artifact regardless of how real they are; (2)
its coherence-state logic for the audit-half is a **trivial grep-count heuristic** (0 refs=unknown, 1=declared_only,
≥2=partial) — it can never say "bound" or "drifted" from prose alone, only the separate `operating_facts`-fed
half can; (3) it has no notion of adversarial verification, maturity classification (production-proven vs.
abandoned), or fusion recommendations — the three things Sections 2-4 of this map exist to do.

**Verdict: yes, genuinely worth extending — this is a real "yes," not a bolt-on.** It's the system's own native,
typed format for exactly the declared-vs-observed comparison every ad hoc markdown audit re-invents by hand.
Concrete extension (proposed, **not made** — a source-code change is outside this investigation's read-only
scope): add new `AUDIT_ORGANS` entries per gravity center / hot subsystem (e.g. `receipt_taxonomy`,
`holon_identity`, `witness_auditor`, `memory_kernel_sprawl`, `sakshi_auditor`, `pudgala_forge`,
`mike_merge_organ`, `forge_swe_bench`), and point future audits/sweeps at emitting entries into this format
alongside their markdown report, not instead of it. A real artifact from today's run is saved alongside this
document (see §Deliverables below) as the demonstration.

### 3.3 Forge worktree fragmentation — the structural cause, not just "pick one"

Beyond the already-flagged "pick a canonical worktree," the **root cause is a discoverability + governance gap**,
confirmed by direct evidence:

1. `reports/forge/FORGE_CANONICAL_INDEX.md` is a genuinely good canonical map — but it exists on git **only via
   one emergency rescue commit** (`260a11539`), is absent from `origin/main`, and is present in only 1 of the 6
   live forge worktrees (not even the one it names canonical). Anyone forking off `origin/main` — the normal
   path — has no route to the document that would stop them.
2. **No `ACTIVE_TRACK.yaml` track owns any Forge surface** — the one governance gate every other feature hits
   ("which track are you serving? we're at WIP cap") never fires for Forge work.
3. The dedup telemetry to catch this **already exists and already runs every session** —
   `agent_onboard.py::render_parallel_work_lanes()` correctly counts 16 forge/measurement branches+worktrees
   live — but only prints a neutral count, no threshold, no pointer to the canonical doc. Observability exists;
   the interpretation step is missing.
4. **A provable literal duplicate exists**: `codex/dharma-forge-proving-ground-10-10-20260626` and
   `droid/dharma-forge-proving-ground-10-10-20260626` are the *identical commit* — two different agent-tool
   runners (Codex CLI, Factory's Droid CLI) independently forked the same task string. Tool-identity-first branch
   naming (`codex/…`, `droid/…`, `forge/…` all naming the same task) actively defeats a pre-fork
   `git branch -a | grep <keyword>` check.
5. **Even the fix has fragmented, live, today**: 3 separate, uncoordinated reconciliation efforts exist right
   now (PR #723 "canonicalize Forge lanes," open since 2026-06-30; PR #734 "offline production contract
   harness," open since 2026-07-01; `feat/rsi-lab`'s same-day reconciliation commit) — none references the
   other two.

**Recommendation (fixes the cause):** land `FORGE_CANONICAL_INDEX.md` on `origin/main` for real (fold into PR
#723, which already touches Forge routing); open one `forge-proving-ground` track in `ACTIVE_TRACK.yaml` with a
`canonical_worktree:` pointer field; wire the already-live `family_counts` into an actual nudge ("N forge lanes
open — read the canonical doc before creating another") — zero new infrastructure; add a one-line pre-fork
collision check to `docs/ops/AGENT_ONBOARDING.md`. **Caveat against over-fusing**: not all 6 worktrees are pure
duplicates — 3 (`ds_forge_v1_scoreboard`, `ds_forge_prod_contracts_20260701`, `ds_forge_nvidia_foundry_mvp_20260701`)
plausibly represent genuinely different scopes per the index's own "Five Evolutionary Levels" table. The proving-ground
pair and the 3-way reconciliation are the genuine, provable redundancy.

### 3.4 Cross-reference: every should_converge:true verdict from Sections 1-2, in one place

| Item | Converge onto | Type of fix | Risk if done wrong |
|---|---|---|---|
| Holon identity.json / living_agent.json split | Contested — see §1.2/§4 C1 | Schema reconciliation, then read-path change | HIGH — literal crash on all 6 registered holons if done as first-drafted |
| Witness/Witness Auditor naming | `witness.py`'s `WitnessAuditor` | Docstring edit + one `cybernetics_codex.py` rewire | Low |
| Memory front-door sprawl | `dharma_swarm/memory_kernel/facade.py`'s `MemoryKernel` | Finish-the-migration (build read adapters, repoint `orchestrator.py`) | Medium — real, multi-week effort, not a quick fix |
| Ledger hash-chain algorithm (6x duplicated) | Shared utility (extract from `GaiaLedger`) | Pure refactor, zero domain-schema change | Low |
| Bridge naming | Semantic Commons registration (docs only) | Governance doc, not code | None |

---

## Section 4 — Adversarial Triple-Check

Five highest-stakes claims selected from the full digest above; each independently re-derived from raw evidence
(one lens) and independently attacked for refutation (a second lens).

| Claim | Re-derive lens | Refute lens | Net verdict |
|---|---|---|---|
| **C1** — Holon convergence: retire ontology `PersistentAgentIdentity`, make `onboard_roaming_agent()` the sole writer, repoint `holon_bridge` to read `living_agent.json` | CONFIRMED (facts hold; "PersistentAgentIdentity" isn't a real registered type, just doctrine) | **REFUTED** (the literal fix crashes production; wrong convergence direction — see §1.2) | **DISPUTED — medium confidence.** Direction is plausible, the specific prescription is broken. Do not execute as stated. |
| **C2** — `witness.py`'s `WitnessAuditor` is the live one; `sakshi`'s `ProvenanceLog` is dead in production | CONFIRMED (found even stronger live proof than cited) | CONFIRMED (tried to refute via corroborating-evidence attack; found a real misattribution in the *citation* but not in the core fact) | **CONFIRMED — high confidence.** Both lenses independently caught the same "1,013 entries" misattribution — solid cross-corroboration. |
| **C3** — All 5 Receipt types are uniformly "genuine_necessity, should_converge:false, per the binding ADR" | **REFUTED** | **REFUTED** | **REFUTED AS STATED — but this is a claim-selection compression artifact, not a flaw in §1.1.** The ADR treats `CostEntry` (ordered to be field-bridged) and `GoEvidenceReceipt` (never discussed) very differently from the 3 heavily-reasoned types (`spine`/`closure_v0`/`RuntimeReceipt`) — a nuance §1.1's own original verdict already flagged, which the claim-selection step flattened away. The narrower, correct claim — "3 of the 5 are ADR-bound distinct layers that must not collapse" — stands. |
| **C4** — `a2a_server.py` bypasses the ADR-prescribed single association seam (`runtime_receipt_kwargs()`) | CONFIRMED | UNCERTAIN (letter true; "singular seam, A2A-specific" framing overstated — found in 5 more sites, including inside `spine/warrant.py` itself) | **CONFIRMED WITH CAVEATS — medium-high confidence.** This is systemic unadopted scaffolding across the whole receipt-construction layer, not an A2A-specific oversight — §1.1 updated accordingly. |
| **C5** — `holon_l4_activation.py` is a near-total clone of `living_agent_kernel_activation.py`, one of 6 copy-pasted hash-chain-verification instances | CONFIRMED | CONFIRMED (with mitigating context: only ~55% file-level similarity once renames are normalized; the security-critical hash primitive itself is centralized — only a thin validation wrapper is duplicated; the fork is already a known, dated, governance-tracked migration, not a fresh discovery) | **CONFIRMED WITH CAVEATS — high confidence.** Real finding, but "near-total clone" overstates whole-file similarity, and it's expected mid-migration state, not a surprise. |

**What this triple-check demonstrates about the investigation as a whole:** 2 of 5 claims survived clean, 2
survived with caveats that meaningfully sharpen but don't overturn them, and 1 was refuted-as-stated — in every
case because a downstream summarization step (claim selection, in C3's case) lost nuance the underlying
per-center investigation had already captured correctly. The base investigation (Sections 1-2) held up better
under adversarial pressure than its own compressed claim-selection layer did.

---

## Section 5 — Ranked Highest-Leverage Moves

Ranked by leverage-per-effort and honesty about what's a quick fix vs. a real project vs. an operator-only
judgment call. The operator works under a personal cap on concurrent active commitments — items marked
**[NEW COMMITMENT]** would start something, not just close something.

1. **Ship the `vector_store.py` fallback-guard fix as a clean PR to `origin/main`.** Quick fix (extract ~35 lines
   from WIP, per the morning audit's own scoping). Highest leverage: real, reproducible risk on a hot retrieval
   path, root-caused further this session (fleet-wide Python-interpreter/dependency drift — confirmed at least
   one other live-reachable interpreter, `/opt/homebrew/bin/python3`, reproduces the exact failure). Not new
   work — closing an already-identified gap.

2. **Repoint (or fix) the Merge-Master-Mike `launchd` daemon.** It runs `~/ds_mike_nonstop_20260626`, 36 commits
   behind `origin/main`, predating the merged PR #707 entirely — the production merge daemon is silently missing
   a shipped safety feature (convergence-advisory), confirmed via 0/30 real cycle receipts containing the
   `advisory` key. Touches a live daemon — flag to operator before restarting, but the fix itself (point the
   plist at a current checkout) is mechanical. Not new work.

3. **Fix the Witness/Witness Auditor naming collision** (§1.6/§3.4): re-word `sakshi/__init__.py`'s docstring,
   rewire `cybernetics_codex.py`'s Loop-6 check to the real evidence substrate. Quick, safe, pure clarity —
   closes a real doctrine/machine-audit divergence for near-zero risk.

4. **Do NOT flip AI-M1/Pudgala Forge to `--enforce` yet.** This is a *hold*, not an action — flagging because it
   might otherwise look tempting given Pudgala's overall production-proven status. Running the actual gate live
   shows 4/4 real active tracks on `origin/main` fail closed today. The honest path to Stage 1 is raising each
   track's evidence grade first, not flipping the switch.

5. **sakshi_auditor: get 2-3 real persisted runs before building anything further on it.** This session's
   backfill (`~/.dharma/agents/sakshi_auditor/`) is a stopgap so the next scheduled fire (cron `0 */2 * * *`) has
   real state — it is not a fix for *why* the one real fire produced nothing. **[JUDGMENT CALL]** — root-causing
   whether this is a CCR per-session-environment isolation issue or a crash is worth a short, scoped
   investigation before the §3.1 S7-wiring recommendation becomes real.

6. **Forge worktree fragmentation root cause** (§3.3): land `FORGE_CANONICAL_INDEX.md` on `origin/main`, open one
   `forge-proving-ground` `ACTIVE_TRACK.yaml` entry, wire the existing `family_counts` nudge. **[NEW COMMITMENT]**
   — opens a new track slot (though `origin/main`'s *real* live portfolio is only 4 tracks right now per the
   Pudgala investigation, not the 11 this branch's `CLAUDE.md` shows — there may be more room than the branch
   framing suggests; confirm the real `origin/main` count before treating this as WIP-blocked). Real, multi-hour
   project, not a one-liner.

7. **BR-007 split-brain: fix path-resolution symmetry, do NOT touch data yet.** `ontology_runtime.py`'s cwd-aware
   fallback vs. `daemon_config.py`'s lack of one is the confirmed root cause of two diverged `ontology.db`
   copies. Unifying path resolution is a real, moderate-risk code change (changes what every daemon/script reads
   from). **The data-merge direction itself is explicitly an [OPERATOR JUDGMENT CALL]** — picking wrong risks
   silent data loss (confirmed: each copy holds object types absent from the other); requires backup + typed
   merge first, per this repo's own prior corruption precedent.

8. **Operator Idea Spark / TELOS Morning Refinery: decide the WIP-cap question.** 229 real, passing, actively-worked
   tests (last commit ~50 minutes before this investigation) sit outside the governed portfolio with no open PR,
   at genuine risk of silent loss via uncommitted drift in the shared, background-branch-switching worktree.
   **[OPERATOR JUDGMENT CALL, EXPLICITLY NOT MINE]** — either bump the WIP cap, close an existing track, or
   explicitly decide this stays shelved. Flagging because real, tested work is quietly at risk, not because a
   specific answer is being pushed.

---

## Deliverables

- This document: `docs/governance/CONVERGENCE_MAP_2026-07-01.md` (uncommitted, per this session's read-only-on-source
  discipline — the operator can commit at will).
- Real `system_map_populator.py` proof-of-concept artifact (§3.2), generated live against `docs/governance/`:
  `reports/system_map/convergence_map_poc_2026-07-01.json` (untracked; not committed).
- `sakshi_auditor` backfill (outside this repo): `~/.dharma/agents/sakshi_auditor/cadence_state.json` +
  `reports/20260701T032201Z.md`.
