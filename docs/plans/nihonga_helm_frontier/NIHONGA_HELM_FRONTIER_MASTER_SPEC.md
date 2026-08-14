# Nihonga Helm Frontier — Master Active-Spec Candidate

```yaml
document_role: active_spec
status: CANDIDATE_NOT_ADMITTED
prepared_at: 2026-08-15
canonical_repository: AIKAGRYA/dharma_swarm
canonical_runtime_baseline: origin/main@a5a61b73c8848b86664f9d5bbcf21986df43c02c
delivery_stack_base: agent/helm-four-model-preview-20260813@708923bb2a7a9616d523da8cf7f55bfe58e3113a
implementation_candidate: agent/nihonga-helm-frontier-stack-20260815@15fb6cd85e9ec7534196c53ce3d1bbe71fdaf242
tested_integration_preview: agent/nihonga-helm-frontier-20260814@74b2370a16d370abd4f3a96c8498c1ed44294005
product: one Dharma Helm TUI
```

## 0. Role, authority, and replacement

This file has exactly one role: it is an **`active_spec` candidate** for the
next bounded Helm build. It is not canon, a runtime receipt, a release claim,
or evidence that a provider/model is live. Repository governance says that an
`active_spec` may drive current implementation, but only canon files may make
repo-level authority claims (`docs/AGENTS.md:13-43`). Therefore this candidate
is subordinate, in order, to:

1. live owner state and machine receipts;
2. current admitted code and executable tests;
3. `docs/governance/ACTIVE_TRACK.yaml` and the canonical document stack;
4. accepted ADRs and owner contracts;
5. this document.

If admitted, this file replaces the external August `master_forge_spec` package
as the implementation-driving Helm spec, and subordinates the April surface
direction, July Operator Seat proposals, June visual corpus, World Deck, and
playgrounds to the reference roles stated in the census below. Until admission,
**no replacement has occurred**. It does not replace the Bun/Python architecture
owner, RuntimeState, TaskBoard, Mission Control, Swarm, A2A, evolution, provider,
permission, Forge, or merge authorities. This explicit role and replacement
statement follows `docs/AGENTS.md:45-52`.

Admission requires all of the following before code from this branch is called
current: land or rebase the parent preview stack; reconcile current main;
resolve the stale Helm track/terminal-owner contradiction; approve the owned
paths and slices; record an admission decision; and rerun the gates in Section
12. A separate integration preview at `74b2370a1` contains
`origin/main@a5a61b73c`; that tested integration fact does not make this stacked
delivery branch current or admit the product.

## 1. Executive decision

Build **one persistent, model-agnostic Bun/Ink Dharma Helm** on the current-main
terminal chassis and Python truth core. At rest it is the Quiet Field: one
reading surface, composer, one-line compass, exact-selection Inspector, and a
hidden palette. When summoned, the same state expands into the Full Helm: five
places, three simultaneous planes at panorama size, recursive evidence-bound
depth, and a truthful projection of the whole organism.

The remembered design is not a choice between quiet and rich. Its exact
composition is:

> **V's cockpit richness + W's quiet/ma + X's recursive depth**

That operator synthesis is recorded in
`/Users/dhyana/Desktop/Projects/DharmaSwarm FrontEnd/04_Fal Generations/Wave_06_hokusai_muted/WAVE06_CRITIQUE.md:9-19`.
W alone was too muted and dead. Richness is progressive disclosure, not a
permanent dashboard. The mandala is real-data-bound information architecture,
not scenery: the rejected v14 painted hero had zero live data and optimized a
picture rather than an instrument
(`/Users/dhyana/Desktop/Projects/DharmaSwarm FrontEnd/03_Claude Prototypes/POSTMORTEM_proto_v14_waste.md:12-35`).

The Helm is the organism's **epistemic instrument**, never a new organism brain.
It lets the operator locate, question, inspect, propose, authorize, observe, and
verify work through existing owners. It does not invent liveness, health,
permission, completion, or truth.

### 1.1 Non-claims

- This proposal is not shipped or merged.
- The current local UI slice is implemented, committed, and tested on the
  candidate branch; it is not current-main product truth.
- A successful model response is not an OnCall verdict.
- Four preview adapters are not “any model,” and adapter compatibility is not
  verified model support.
- Mission Control is admitted on current main and present in the tested
  integration preview, but not yet in this stacked delivery branch; the
  terminal is not thereby wired to it.
- No public evidence proves that any benchmark TUI was “built by GPT-5.6-sol
  Ultra.” Public repositories generally do not expose meaningful model/effort
  provenance, and this spec makes no chain-of-thought attribution.

## 2. Baseline and latest-state ledger

This is the observation boundary as of 2026-08-15 JST. Recheck every hash at
admission.

| Layer | Observed state | Disposition |
|---|---|---|
| Canonical repository | `https://github.com/AIKAGRYA/dharma_swarm.git` | Sole GitHub authority. |
| Current `origin/main` | `a5a61b73c884`, bounded fleet truth topology ([PR #1344](https://github.com/AIKAGRYA/dharma_swarm/pull/1344)) atop Mission Control admission ([PR #1346](https://github.com/AIKAGRYA/dharma_swarm/pull/1346)) | Runtime/governance baseline; contained by the tested integration preview, not yet by the stacked delivery branch. |
| Helm chassis landing | `88458e06f750`, Bun/Ink Helm merged by [PR #1078](https://github.com/AIKAGRYA/dharma_swarm/pull/1078); golden closeout by [PR #1073](https://github.com/AIKAGRYA/dharma_swarm/pull/1073) | Preserve as chassis, not final IA. |
| Stacked delivery branch | `agent/nihonga-helm-frontier-stack-20260815@15fb6cd85e9e` | Nihonga S1 implementation on exact parent preview `708923bb2`; deliberately small and reviewable. |
| Tested integration preview | `agent/nihonga-helm-frontier-20260814@74b2370a1` | Same Nihonga slice plus the model-preview stack and current main; live operator test source, not the merge shape. |
| Locked terminal appearance | `680b013c027194eb50416840d63055f025ca4bb7`, later included in the Helm landing | Exact warm Nihonga token authority. |
| Wayfinder live slice | Issue [#1277](https://github.com/AIKAGRYA/dharma_swarm/issues/1277), lock [comment](https://github.com/AIKAGRYA/dharma_swarm/issues/1277#issuecomment-5226785831), draft [PR #1324](https://github.com/AIKAGRYA/dharma_swarm/pull/1324) | Truth-law source; live proof remained blocked/degraded, not closure. |
| Mission Control | Core merged by [PR #1325](https://github.com/AIKAGRYA/dharma_swarm/pull/1325); integration paths admitted by current-main [PR #1346](https://github.com/AIKAGRYA/dharma_swarm/pull/1346) | Canonical coordination membrane/projection source, never a second scheduler/store. |
| Four-model preview | `708923bb2`, draft [PR #1341](https://github.com/AIKAGRYA/dharma_swarm/pull/1341) | Unmerged, no-tools, singleton, preview-only, OnCall-ineligible. |
| Local Nihonga slice | Seven files under `terminal/src/nihonga/` plus focused tests and 42 governed frames | Committed on the candidate branch; not merged and not live-provider proof. |
| Governance status | Current Helm entry remains `ACTIVE`; an unmerged closure branch claims `SHIPPED/CLOSED_NOT_PROD` | Canonical state is the stale `ACTIVE` value until reconciled; do not borrow the closure claim. |

Current main admits Mission Control as a typed membrane without transferring
TaskBoard, RuntimeStateStore, Orchestrator, A2A, Forge, or merge ownership
(`origin/main@bd779ddc:docs/governance/ACTIVE_TRACK.yaml:838-875`). It also makes
the non-coercion ladder explicit: proposal, governance admission, authorized
dispatch, acknowledgements, verified outcome, promotion, and merge remain
distinct (`origin/main@bd779ddc:docs/governance/ACTIVE_TRACK.yaml:969-992`).

## 3. Product constitution

### 3.1 Quiet Field is the default; Full Helm is earned depth

The Quiet Lever is both the default disclosure level and the control condition.
It retains one reading surface, composer, compass, exact Inspector, and hidden
action palette; reach comes from typed owners, not permanent panes
(`/Users/dhyana/dharma_tui_reverse_spec_20260804/agents/23_ruthless_minimalist.md:5-18`).
The wider Quiet Field synthesis keeps the current Helm's circulation, the
Operator Seat's semantic constitution, and owner-backed organism reach
(`/Users/dhyana/dharma_tui_reverse_spec_20260804/synthesis/00_EXECUTIVE_SYNTHESIS.md:8-26`).

The Full Helm may disclose more only when it improves orientation or a user
explicitly asks for depth. It is the same product, state, focus, draft, and
causal chain. No separate “quiet app,” “cockpit app,” or dashboard truth store
may emerge.

At rest:

```text
Room band / one-line compass
────────────────────────────────────────────
One reading surface (conversation or place)
Exact Inspector only when selected/summoned
────────────────────────────────────────────
Boundary line
Composer
Status / route receipt
```

### 3.2 Five places, three planes, one recursive Inspector

The stable places are keyboard coordinates, not five dashboards:

| Place | Question | Owner-backed content |
|---|---|---|
| Home | What requires me now? | changed, held, stale, conflicting, or consequential items only |
| Conversation | What am I asking and what answered? | byte-faithful transcript, drafts, route receipts, session handhold |
| Activity | What is changing? | task/attempt/run/event/cancel stream with explicit causal states |
| Evidence | Why may I believe it? | claim → evidence → source → checker, freshness, conflict, expiry |
| System | What substrate and route am I on? | workspace, bridge, provider/model, costs, permissions, diagnostics |

The three planes are views of those places, not new destinations:

| Plane | Panorama share | Meaning |
|---|---:|---|
| Conversation / Intent | 45% | operator intent, transcript, draft, selected response |
| Ecosystem / Organism | 35% | selected owner/capability region and exact projections |
| Causal / Proof | 20% | proposal → authority → execution → evidence → verification |

The Inspector is recursive contextual depth. It is not a tab, place, sidebar
destination, or model-controlled pane. Only exact selection, an exact entity
query, a typed action result, or explicit Follow may push a frame. `Esc` pops
exactly one frame; each place retains scroll and focus; Home is one gesture
away. Raw model prose mentioning an entity cannot retarget it. These semantics
derive from the Quiet Lever's stack law
(`/Users/dhyana/dharma_tui_reverse_spec_20260804/agents/23_ruthless_minimalist.md:56-60`).

### 3.3 Responsive profiles

| Profile | Geometry | Contract |
|---|---|---|
| Panorama | `>=120×30` | exact 45/35/20 planes; quiet start still allowed |
| Standard | `>=100×28` and not Panorama | focus-weighted 58/42: Conversation receives 58% on chat; selected Context receives 58% otherwise; causal depth stays in Inspector |
| Compact | `>=80×24` and not Standard | one focused plane; five places remain reachable |
| Survival | `44–79` columns or `18–23` rows | one terse surface, composer/cancel/status, no fake fit |
| Resize-safe | below `44×18` | identity, actual geometry, route, quit/resize help; no clipped cockpit claim |
| Linear | explicit user/a11y/terminal fallback | ordered semantic stream with feature parity, never a degraded truth model |

Resize never changes semantic selection, draft, authority, or execution state.
Overlay is temporary and cannot become a sixth place. The local branch encodes
the exact breakpoints in `terminal/src/nihonga/shellModel.ts:41-55` and the
panorama/focus-weighted-standard/compact composition in
`terminal/src/nihonga/NihongaCockpit.tsx:77-124`; this is local branch evidence,
not merged authority.

## 4. Nihonga design constitution

### 4.1 Exact terminal tokens

The warm operator-picked palette wins over older cool dashboard palettes.
Values and usage laws are already expressed in `terminal/src/theme.ts:1-39`.

| Token | Hex | Semantic use |
|---|---|---|
| `night` / canvas | `#14110E` | warm sumi-black app canvas |
| `indigo` / raised | `#201913` | raised background or border only |
| `harbor` / selected | `#2C2218` | selected/overlay background |
| `river` / quiet line | `#3A2C20` | decorative border only; never meaning |
| `ridge` / focus | `#9A7C5A` | focused border |
| `foam` / primary | `#E8DCC0` | primary text |
| `mist` / secondary | `#D6C7A2` | secondary text |
| `stone` / meta | `#A89A7E` | labels and metadata |
| `ink` / decoration | `#80735F` | decoration only; never information |
| `wave` / observed | `#6FA890` | chrome, active item, observed/witness |
| `crest` / executing | `#6E90D0` | running/streaming |
| `parchment` / identity | `#D2A05A` | model identity and cost |
| `sunlit` | `#E4C07E` | high-emphasis warm highlight |
| `bengara` | `#8F2D12` | fill only, never raw text |
| `moss` / verified | `#9AB46A` | verified/success where independently warranted |
| `pine` / quiet terminal | `#86A492` | done/quiet-OK |
| `persimmon` / held | `#E0A24E` | held, warning, stale, expected-offline |
| `vermilion` / danger | `#E85A4E` | danger/refuted only; never expected-offline |
| `iris` / specialist | `#B488A6` | spawning/specialist identity |

Hard laws:

- `indigo` and `river` appear only as backgrounds/borders.
- `ink` is decorative and cannot carry state.
- `vermilion` means danger/refutation only.
- `wave` is chrome/active; `ridge` is focus; `parchment` is model identity/cost.
- Every state uses glyph + word + color; color is never sole meaning. Existing
  agent pairs are defined in `terminal/src/theme.ts:41-50`.
- No unconstrained ANSI literals in feature components; semantic tokens only.
- CJK width, grapheme clusters, bidi isolation, no-color, ASCII, screen reader,
  and native scrollback are first-class renderer contracts.

### 4.2 Anti-cliche and art laws

Nihonga here means ma, asymmetry, warm mineral restraint, atmospheric recession,
legible thresholds, and repair traces. It does **not** mean fake kanji, faux
seals, shrine language, anime avatars, samurai metaphors, seasonal ornament,
Great Wave wallpaper, or a painting with telemetry pasted over it. The external
design contract makes the same anti-cliche boundary
(`/Users/dhyana/dharma_tui_reverse_spec_20260804/master_forge_spec/DESIGN_SYSTEM.md:23-61`).

The “rug → instrument” law preserves warmth and aliveness while increasing
operability; darkness and emptiness are not serenity
(`/Users/dhyana/Desktop/Projects/DharmaSwarm FrontEnd/ART_DIRECTION_v2_2026-06-15_RUG_TO_INSTRUMENT.md:4-30`).
The Current Field may be a sparse procedural trace of actual state change. It
must stop after finite motion, disappear in no-motion mode, and never imply
activity from an idle timer. There is no generated hero art, ambient particle
weather, token waterfall, agent theater, completion confetti, XP, or universal
health score.

## 5. Typed epistemic and authority contract

### 5.1 Independent axes, not a confidence soup

Every displayed operational fact remains structured across at least four
independent axes:

```text
Claim<State, Modality, Authority, EvidenceRef, ObservedAt>
```

The small language-design contribution is a construction boundary: only the
owner/evaluator for a modality may construct its promoted form. A provider
response can construct `Observed<Response>`; it cannot construct
`OnCall<Route>`, `Permitted<Action>`, `Verified<Outcome>`, or `Live<Executor>`.
The type/evaluator boundary must reject those coercions before rendering, not
merely attach a warning after the fact.

Visible marks are redundant labels over structured fields, not one linear state
machine:

| Mark | Word | Meaning |
|---|---|---|
| `·[C]` | Claimed | asserted without qualifying observation |
| `◉[O]` | Observed | owner/evidence observation exists |
| `◇[P]` | Proposed | effect shape exists; no authority implied |
| `▣[H]` | Held | intentionally unable to execute |
| `◆[A]` | Permitted | exact authority owner permitted this effect |
| `▶[>]` | Executing | correlated execution is in progress |
| `■[S]` | Succeeded | executor reported terminal success |
| `✓[V]` | Verified | qualifying independent verifier promoted outcome |
| `×[R]` | Refuted | evidence refutes claim |
| `?[?]` | Unknown | owner truth absent or undecodable |
| `⇄[D]` | Divergent | owners disagree; show both |
| `~[~]` | Stale | observation exceeded freshness contract |
| `░[SIM]` | Simulation | fixture/synthetic projection only |

Required non-coercions:

- response ≠ OnCall;
- route selected ≠ route served ≠ exact identity verified;
- configured ≠ available ≠ live;
- task claim, lease, heartbeat, publish ACK, or “running” row ≠ executor liveness;
- proposed ≠ held ≠ permitted ≠ dispatched;
- accepted ≠ completed;
- cancel requested ≠ stopped;
- execution success ≠ verified semantic outcome;
- evidence identifier ≠ evidence fact;
- council/model consensus ≠ proof, promotion, or authority;
- projection freshness ≠ owner health;
- no global completion/health score may average independent owners.

### 5.2 Wayfinder #1277 truth laws

The candidate incorporates these laws from the locked live-slice contract
(`docs/plans/HELM_LIVE_SLICE_1_SPEC_2026-08-09.md:12-27`):

1. Raw conversation bytes are preserved. A compound prompt cannot silently
   collapse into `/swarm`, dispatch, evolution, or another effectful intent.
2. The primary turn is physically no-tools. Provider tool/task/command events
   are rejected, not painted as harmless.
3. Provider text has `authority=NONE`, `narration_verified=false`, and
   `state_promotion_allowed=false`.
4. Python is the sole Helm OnCall evaluator. The terminal decodes and renders
   its projection; it never evaluates a shadow truth.
5. The roster is fixed and ordered at seven seats; missing stays missing. There
   is no duplicate, substitute, or model-name fuzzy match.
6. OnCall requires strict requested/served identity, non-synthetic current
   receipt and hash, runtime epoch, verifier, timezone-aware timestamps, and a
   TTL no longer than 24 hours. Projection renders exact `N/7` or `?/7`.
7. R1C may restore transcript/view/draft, but reconnect or runtime-epoch change
   synchronously resets organism/OnCall truth to UNKNOWN before later events.
8. Completion rendering requires explicit `completed`; `accepted`,
   `unsupported`, `failed`, missing, or malformed outcomes cannot get a check.
9. The Helm adds no task store, scheduler, model registry, permission engine,
   bridge brain, truth database, or liveness oracle.

The seven-seat schema and admissible served identities are explicit in
`terminal/src/onCallTruth.ts:1-73`; the projection retains evidence identity,
timestamps, receipt hashes, verifier, and runtime epoch at
`terminal/src/onCallTruth.ts:75-150`.

### 5.3 Focus and action boundary

Plain language is conversation and has zero effects. Exact inspect/find/compare
resolves a read projection or selection. `propose` produces a normalized held
action containing scope, owner, effects, network, credentials, cost,
reversibility, cancellation, and verification plan. Ambiguity performs nothing.
The action palette generates typed shapes; it is not another slash-command
inventory. Action History must not be called Approvals until a real pre-effect
hold/deny/resume-once gate exists.

Drafts never auto-send, including after resize, route change, reconnect, session
restore, place/plane change, palette close, or model completion. Current bridge
model-output directives such as `⟦helm:...⟧` must be retired as focus/action
authority; model prose may suggest an exact selectable reference but cannot
retarget or dispatch.

## 6. Architecture and owner seams

The chosen chassis is the current Bun + React + Ink shell over the typed Python
operator core, with NDJSON stdio as transport. The architecture owner explicitly
keeps presentation in Bun, runtime/provider semantics in Python, and requires
the bridge to shrink rather than become a new brain
(`docs/plans/2026-04-02-bun-tui-shared-operator-core-spec.md:13-25` and
`:50-113`; `terminal/README.md:81-105`).

```text
Ink renderer + input + local view state
              │ typed projection/event/action envelopes
NDJSON bridge ├── adaptation, correlation, backpressure, no new truth
              │
Python operator_core ── contracts / routing / permissions / evaluator
              │
Canonical owners ────── TaskBoard / RuntimeState / MissionControl / Swarm
                         A2A / evolution / memory / repo / sessions
```

| Concern | Canonical owner | Helm may do | Helm must not do |
|---|---|---|---|
| Render/layout/theme | `terminal/src/**` | render semantic projection; retain local focus/draft/scroll | infer backend truth from pixels or copy |
| Input/navigation | terminal input reducer/registry | resolve keys, places, planes, Inspector stack, cancel intent | turn ambiguous prose into effects |
| Cross-language contracts | `dharma_swarm/operator_core/**` plus typed terminal decoders | extend versioned envelopes and fail closed | duplicate contract/state ownership |
| Transport | `dharma_swarm/terminal_bridge.py` | correlate, sanitize, stream, resync, expose bounded projections | schedule, evaluate truth, store parallel facts |
| Work lifecycle | `TaskBoard` | query exact tasks/dependencies/claims | create a second task ledger |
| Live runtime | `RuntimeStateStore` | project sessions, runs, leases, events, receipts with freshness | infer liveness from heartbeat or recorded running |
| Coordination membrane | Mission Control | join Mission/Task/Attempt/Lease/Receipt/Snapshot; expose divergence | become scheduler, worker pool, store, evaluator, or authority |
| Swarm internals | `SwarmManager`, AgentPool, MessageBus, orchestrator | show bounded coordination/topology projections | equate route catalog with agents or spawn from chat |
| External agent boundary | A2A | show native task/context/run and publish/consume/outcome receipts | wrap A2A lifecycle or treat ACK as outcome |
| Evolution/research | evolution owners/archives/Forge | inspect proposals, trials, fitness evidence, promotions | apply mutation, promote, or claim improvement from UI prose |
| Providers/models | provider adapters/catalog/evaluator | select exact route, show requested/served/receipt/cost | claim arbitrary support or fallback silently |
| Permission/merge | permission owner, governance, Merge Master | display exact authority and held action | synthesize admission, permission, promotion, or merge |

Mission Control is an additive projection/join membrane. Its original contract
explicitly says it is not a scheduler or replacement store and must expose torn
projections (`dharma_swarm/mission_control.py:1-15` and `:79-99`). Its snapshot
joins owner facts and reconciliation at `dharma_swarm/mission_control.py:278-335`.
The terminal integration must use those bounded projections rather than add a
Mission Control database or infer liveness from a recorded heartbeat.

### 6.1 Whole-organism terrain

Home's rich lens uses six stable capability regions, not “ten tracks = ten
organs” and not one score:

1. purpose / governance;
2. core organism;
3. intelligence mesh;
4. evolution / research;
5. outward organs;
6. delivery substrate.

Each region is a navigational grouping over owner projections. Active tracks
are overlays; they are not anatomy. Region marks must be `observed`,
`configured`, `unverified`, `held`, `unknown`, `divergent`, or `stale` with
source and observed-at. The local branch models this without liveness promotion
in `terminal/src/nihonga/organismView.ts:4-20` and `:30-83`; its negative test
keeps a configured outward route distinct from contact and a connected bridge
distinct from core liveness (`terminal/tests/nihongaShell.test.ts:40-67`).

The World Deck may later supply an optional spatial lens over this terrain, but
graph/list views must be semantically equivalent and the lens must never become
authorization. Its source itself is CANDIDATE/INCUBATING and targets a dashboard,
not this TUI (`spec/dharma-world-deck-20260809@eefef177:spec-forge/mandala-world-deck/MASTER_SPEC.md:24-35`).

## 7. Model/provider contract

### 7.1 Exact current preview routes

These four routes are an **unmerged, no-tools preview boundary**. Each is
singleton, has no fallback, grants bounded attempt authority only, defaults to
`exact_model_proven=false`, `preview_only=true`, and
`helm_on_call_eligible=false` (`dharma_swarm/terminal_bridge_external_preview.py:33-45`).

| Picker alias | Exact requested route | Account lane | Current honest label |
|---|---|---|---|
| GPT-5.6 Sol | `codex_text:gpt-5.6-sol` | ChatGPT subscription | text-only preview; exact served model unproven |
| Claude Fable 5 | `claude:claude-fable-5` | Claude/Anthropic subscription | no-tools preview |
| Kimi K3 | `kimi_code:k3` | first-party Kimi Code API | no-tools preview |
| Grok 4.6 | `grok_oauth:grok-4.6` | Grok OAuth account | no-tools preview; response may expose a build identity |

The literal routes and labels live at
`dharma_swarm/terminal_bridge_external_preview.py:52-81`. Picker projection
must remain `unverified`/`unavailable`, never `available=true`, until qualifying
evidence exists (`dharma_swarm/terminal_bridge_external_preview.py:144-184`).
Catalog constants grant no global availability, tier, default, or proof
(`dharma_swarm/model_catalog.py:25-31`). The current GPT preview exposes no
“Ultra” effort control, so the UI must not add that word.

### 7.2 Preview, served identity, and OnCall are different types

```text
configured adapter
  -> selectable attempt route
  -> requested provider/model
  -> observed served provider/model
  -> qualifying RouteVerification
  -> evaluator-owned OnCall seat verdict
```

No arrow is implicit. Route receipts retain requested and served identities,
tool-disable evidence, costs, timestamps, and provider-owned response identity.
A preview completion remains preview-only and OnCall-ineligible. Failure may not
fall back to a different account/provider/model unless a separately displayed
operator policy permits an exact fallback; these preview routes have none.

The OnCall bench is a separate fixed roster: Fable 5, GPT 5.6, Grok 4.5/4.6
lineage, Fugu Ultra, Kimi K3, Opus 5.0, and Opus 4.8
(`terminal/src/onCallTruth.ts:5-69`). A preview picker item need not correspond
to a currently verified seat, and a verified seat need not be selectable in the
preview picker.

“Any model” means the Helm can host a provider-neutral adapter interface with
capability negotiation. It never means an arbitrary model is silently treated
as compatible, tool-safe, exact, paid-for, or OnCall. A new adapter earns a
picker entry only after contract tests; it earns a live label only after a
fresh route receipt; it earns OnCall only through the Python evaluator.

## 8. Frontier TUI benchmark

This is a primary-source snapshot checked 2026-08-14, not an endorsement or a
claim about which model authored a repository.

| System | Pinned source/license | Adopt or adapt | Reject/limit |
|---|---|---|---|
| OpenAI Codex | [repo](https://github.com/openai/codex), [8630bb3](https://github.com/openai/codex/commit/8630bb3), [Apache-2.0](https://github.com/openai/codex/blob/main/LICENSE) | quiet transcript, source-attributed approval, subagents, native terminal flow | do not infer hosted/model internals or authorship provenance |
| Claude Code | [repo](https://github.com/anthropics/claude-code), [1f6015b](https://github.com/anthropics/claude-code/commit/1f6015b), [terms](https://github.com/anthropics/claude-code/blob/main/LICENSE.md) | explicit steering, team/task UX, permission modes | behavior reference only; implementation is proprietary |
| Gemini CLI | [repo](https://github.com/google-gemini/gemini-cli), [c0d1924](https://github.com/google-gemini/gemini-cli/commit/c0d1924), [Apache-2.0](https://github.com/google-gemini/gemini-cli/blob/main/LICENSE) | plan/execute distinction, extensions, configurable command discovery | no hidden authority from plan prose |
| OpenCode | [repo](https://github.com/anomalyco/opencode), [e23586a](https://github.com/anomalyco/opencode/commit/e23586a), [MIT](https://github.com/anomalyco/opencode/blob/dev/LICENSE) | core/renderer/provider separation, provider neutrality, themes/commands | no permanent dashboard or route ambiguity |
| goose | [repo](https://github.com/aaif-goose/goose), [705f30d](https://github.com/aaif-goose/goose/commit/705f30d), [Apache-2.0](https://github.com/aaif-goose/goose/blob/main/LICENSE) | ACP/MCP interoperability, runtime controls, output budgets | protocol support never implies authority |
| OpenTUI | [repo](https://github.com/anomalyco/opentui), [ae27200](https://github.com/anomalyco/opentui/commit/ae27200), [MIT](https://github.com/anomalyco/opentui/blob/main/LICENSE) | renderer architecture, Markdown/cell discipline; evaluate after Ink parity proof | no renderer rewrite during product-IA convergence |
| Crush | [repo](https://github.com/charmbracelet/crush), [051955a](https://github.com/charmbracelet/crush/commit/051955a), [FSL](https://github.com/charmbracelet/crush/blob/main/LICENSE) | multi-model terminal interaction and explicit architecture as comparison input | license-aware behavior reference; do not import fashion or provenance claims |
| Bubble Tea | [repo](https://github.com/charmbracelet/bubbletea), [351d215](https://github.com/charmbracelet/bubbletea/commit/351d215), [MIT](https://github.com/charmbracelet/bubbletea/blob/main/LICENSE) | explicit model/update/view separation | do not port framework for fashion |
| Ratatui | [repo](https://github.com/ratatui/ratatui), [60c8af4](https://github.com/ratatui/ratatui/commit/60c8af4), [MIT](https://github.com/ratatui/ratatui/blob/main/LICENSE) | layout/cell/accessibility test ideas | no Rust rewrite without measured need |
| lazygit | [repo](https://github.com/jesseduffield/lazygit), [af04698](https://github.com/jesseduffield/lazygit/commit/af04698), [MIT](https://github.com/jesseduffield/lazygit/blob/master/LICENSE) | discoverable context keys, reversibility, focused density | full density belongs only in summoned Helm |
| K9s | [repo](https://github.com/derailed/k9s), [e46b172](https://github.com/derailed/k9s/commit/e46b172), [Apache-2.0](https://github.com/derailed/k9s/blob/master/LICENSE) | fast ops navigation, filters, resource orientation | no always-on wall of status |
| Gas Town | [repo](https://github.com/gastownhall/gastown), [649b832](https://github.com/gastownhall/gastown/commit/649b832), [MIT](https://github.com/gastownhall/gastown/blob/main/LICENSE) | adapt agent tree/task DAG/event/problems to typed owner evidence | no agent self-report as proof or gamified town theater |
| Claude Squad | [repo](https://github.com/smtg-ai/claude-squad), [2dd388e](https://github.com/smtg-ai/claude-squad/commit/2dd388e), [AGPL](https://github.com/smtg-ai/claude-squad/blob/main/LICENSE.md) | worktree/process isolation as reference | tmux/process presence is not organism liveness |

Interoperability should prefer open, typed boundaries such as
[ACP](https://github.com/agentclientprotocol/agent-client-protocol) and the
[MCP authorization specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization),
but neither protocol is a permission grant by itself.

The frontier opportunity is the combination the public field does not yet show
in one product: K9s-grade operational orientation, lazygit-grade reversibility,
Codex-grade source attribution, Claude-grade steering, OpenCode-grade
provider/renderer separation, goose ACP/MCP controls, OpenTUI-grade cell
discipline, and Dharma's typed evidence and authority semantics. The last term
is the differentiator; visual density without it is merely another dashboard.

## 9. Architecture constraints and file ownership

Terminal Guardian is binding for each change slice. No slice may span more than
two of these categories: **UI rendering, UI state, input handling, protocol,
bridge, session persistence, provider boundary**. If a proposal needs three, it
must split at a typed seam. Overlays are not tabs; structured state remains
structured; god files do not grow; compact behavior is verified in the same
slice.

Additional constraints:

- `terminal/src/app.tsx`, `terminal/src/protocol.ts`, the Python bridge, and
  large panes are extraction targets, not destinations for new feature logic.
- UI modules receive typed view models and emit typed intents; they do not read
  owner databases or provider credentials.
- Protocol decoders reject unknown/malformed promotions; they do not coerce
  them into defaults.
- Bridge handlers adapt one owner seam at a time and preserve correlation,
  cancellation, epoch, and provenance.
- New state fields need an owner, freshness rule, unknown representation,
  reconnect behavior, negative control, and compact rendering.
- Synthetic fixtures are always marked `SIM`; their receipts cannot enter live
  evaluators.

## 10. Progressive implementation slices

Slices are serially admissible. Each row lists its complete Terminal Guardian
category budget.

| Slice | Categories (max 2) | Deliverable | Gate/status |
|---|---|---|---|
| S0 — admit/rebase | documentation/governance only | land/rebase the parent stack; reconcile with current main; settle Helm track and terminal owner; admit this spec | **Partly complete:** a separate tested integration preview contains current main at `74b2370a1`; this delivery branch remains stacked on `708923bb2` until its parent lands. Track/owner reconciliation and admission remain. |
| S1 — Nihonga shell | UI state + UI rendering | five places, three planes, responsive profiles (including focus-weighted Standard), Room/Boundary bands, six-region honest projection, bounded compact PaneSwitcher row; preserve zen/scroll | **Implemented and committed on the delivery candidate; unmerged.** The tested integration preview produced 693 passed/0 failed and 42 deterministic golden frames at 80×24, 100×30, and 120×40; the stacked delivery head independently reproduces 693/0 and Terminal Guardian. In both shapes, `git diff --numstat -- terminal/src/app.tsx` is 119/119, net-zero growth in the legacy app entrypoint while the new shell lives in bounded modules. Rerun all proof after the eventual current-main rebase. |
| S2 — owner projection envelopes | protocol + bridge | versioned bounded snapshots for MissionControl/TaskBoard/RuntimeState/Swarm/A2A/evolution; explicit freshness/divergence/unknown | No terminal rendering changes. |
| S3 — organism views | UI state + UI rendering | bind S2 projections to six regions, Home query, Activity, Evidence; remove mocks/zeros | No new backend state. |
| S4 — recursive Inspector | input handling + UI state | exact entity resolver, bounded focus stack, one-Esc pop, per-place anchors, mention-attack resistance | Model prose cannot retarget. |
| S5 — Inspector presentation | UI rendering + protocol | linear/recursive parity, claim/evidence/source/checker, CJK/bidi/no-color/a11y | No action execution. |
| S6 — model route truth | provider boundary + bridge | exact preview adapters, no-tools enforcement, requested/served receipts, singleton/no fallback | Live label remains evaluator-owned. |
| S7 — route UI | UI state + UI rendering | picker/receipt/OnCall distinction, costs/capabilities, explicit unavailable/unknown | Never “any model” without evidence. |
| S8 — durable handhold | session persistence + UI state | restore transcript, draft, selection/Inspector depth; reset runtime truth and never resume work | Kill/relaunch proves zero implicit effects. |
| S9 — action membrane | protocol + bridge | typed proposal/consequence/held/permit/dispatch/cancel/outcome envelopes for one harmless action | No UI until deny-zero-effect/resume-once proof passes. |
| S10 — action UI | input handling + UI rendering | hidden palette, consequence line, exact confirmation, Action History, causal receipt | “Approvals” remains forbidden until gate is real. |
| S11 — optional world lens | UI state + UI rendering | stable region terrain + overlays with list/graph parity | Must pass Quiet Lever improvement kill gate or delete. |
| S12 — renderer decision | UI rendering + protocol | measure Ink against OpenTUI/cell/a11y needs behind the same view model | No rewrite unless evidence beats retained Ink. |
| S13 — live proof | provider boundary + session persistence | bounded two-route no-tools journey, reconnect reset, exact receipts | External credentials/quota may honestly yield `LIVE_PROOF_BLOCKED`. |

No slice may be bundled to “save time.” The fastest path is a narrow seam with
a falsifiable negative control, not a cross-stack rewrite.

## 11. Required journeys

1. **Quiet launch:** at 80×24, identify exact workspace, bridge epoch, route
   state, and “nothing running” versus unknown without a dashboard.
2. **Ask:** send one byte-faithful no-tools prompt; see requested and served
   route separately; no model text changes place, focus, truth, or authority.
3. **Inspect:** select a mission/task/attempt, follow claim → evidence → source →
   checker, then pop exactly one level and return Home.
4. **Conflict:** show TaskBoard/Runtime/MissionControl disagreement side by side;
   never average it into health.
5. **Cancel:** issue correlated cancel; render `cancellation requested` until an
   owner terminal event proves stopped.
6. **Recover:** kill/relaunch; restore transcript/draft/last selection but reset
   live/OnCall state to UNKNOWN and perform zero implicit work.
7. **Model switch:** select a second exact no-tools route; preserve the first
   receipt; show unavailable instead of silent fallback when blocked.
8. **Organism:** from one Home item, reach TaskBoard, RuntimeState, Mission
   Control, Swarm, A2A, and evolution evidence without creating another owner.
9. **Effect boundary:** propose one harmless action, inspect consequence and
   authority, deny with zero effect, permit once, and correlate the receipt.
10. **Linear parity:** complete journeys 1–7 in Linear/no-color mode with the
    same facts and authority distinctions.

## 12. Acceptance and kill gates

### 12.1 Admission and truth

- [x] A separate tested integration preview contains `origin/main@a5a61b73c`
  at the 2026-08-15 observation boundary.
- [ ] Stacked delivery branch is rebased onto current main after its parent
  preview stack lands.
- [ ] Branch is clean, published as a draft PR, and hashes/PR states are
  refreshed at handoff.
- [ ] `make onboard`, docs integrity, ownership checks, and governed closeout
  pass.
- [ ] One admitted owner names the spec and every touched path.
- [ ] All projections carry owner, schema, observed-at, freshness/expiry,
  runtime epoch where relevant, and explicit unknown/divergent states.
- [ ] Adversarial fixtures prove every non-coercion in Section 5.
- [ ] There is no terminal truth database, scheduler, permission engine,
  liveness oracle, or model registry.

### 12.2 Layout, interaction, and accessibility

- [ ] Panorama is exactly 45/35/20 at `120×30` and larger; Standard, Compact,
  Survival, Resize-safe, and Linear select at the stated boundaries.
- [ ] Quiet mode uses no more than four persistent chrome lines and keeps one
  reading surface, composer, compass, and summoned Inspector.
- [ ] All five places remain reachable in at most two gestures at 80×24.
- [ ] Resize, overlay, route switch, reconnect, and completion produce zero
  draft auto-sends and preserve semantic focus where valid.
- [ ] Exact selection and one-Esc-one-level pass mention attacks, resize, and
  session restore.
- [ ] PTY/goldens cover 80×24, 100×30, and 120×40; Unicode, CJK/wcwidth,
  combining glyphs, emoji, bidi, no-color, ASCII, and screen-reader order pass.
- [ ] Idle motion is zero; state motion is finite and disabled by no-motion.
- [ ] No new monolith growth; extracted app/protocol/bridge budgets are ratchets.

### 12.3 Models and effects

- [ ] Every picker row exposes requested route, account lane, capability/tool
  posture, route state, exact-model evidence, fallback policy, and cost source.
- [ ] Four preview routes stay no-tools, singleton, preview-only, and
  OnCall-ineligible until separately verified.
- [ ] Forged, stale, replayed, synthetic, duplicate, wrong-order, wrong-epoch,
  timezone-naive, TTL-over-24h, or identity-mismatched OnCall evidence fails.
- [ ] Disconnect/reconnect resets `N/7` to `?/7` before later events.
- [ ] Ambiguous prose, provider events, and denied actions cause zero effects.
- [ ] Cancel request and terminal stop, success and verification, ACK and
  outcome remain visually and structurally separate.

### 12.4 Quiet Lever and deletion gates

At 80×24 over SSH, founder, on-call, auditor, screen-reader, and newcomer tasks
must achieve at least **90% task success, zero false execution/verification
claims, median two gestures per lookup, and at most four persistent chrome
lines**, matching the Quiet Lever challenge
(`/Users/dhyana/dharma_tui_reverse_spec_20260804/agents/23_ruthless_minimalist.md:120-124`).

Any rich panorama, Current Field, organism terrain, recursive/world lens, or
decorative component survives only if it improves orientation/task success by
at least **20% over the Quiet Lever control** without increasing false belief,
time-to-cancel, input loss, or 80×24 failure. Otherwise delete it. Specifically:

- delete the world lens if list parity fails or selection context is lost;
- delete animation if it is not owner-state-bound, finite, and useful;
- delete any region/status aggregate that hides divergence or missing data;
- delete any pane that cannot become a place query or exact Inspector view;
- delete any model badge that outruns a route receipt/evaluator verdict;
- reject OpenTUI migration if it does not measurably improve cell correctness,
  performance, or accessibility while preserving all contracts;
- if provider availability blocks S13, record `LIVE_PROOF_BLOCKED` and block
  the **final live-completion claim**, rather than weakening evidence. Honest,
  independently gated non-provider slices such as S1 may merge without S13.

## 13. Complete surviving-artifact and provenance census

This is the disposition ledger for every surviving artifact family found in the
Helm investigation. “Reference” means useful input, not edit/runtime authority.

| ID | Artifact / provenance | Status | Binding disposition |
|---|---|---|---|
| A1 | Current `origin/main@a5a61b73c884`; Bun/Ink `terminal/**`, Python `operator_core/**`; Helm landing `88458e06`; April Bun shared-core/surface/convergence specs; PTY/goldens | **Canonical runtime chassis** | Keep and reconcile; current code/tests beat all proposals. |
| A2 | Operator-picked Nihonga commit `680b013c027194eb50416840d63055f025ca4bb7`; current `terminal/src/theme.ts:1-50` | **Locked terminal visual authority** | Exact warm palette and semantic laws; supersedes cool terminal/dashboard palettes. |
| A3 | `/Users/dhyana/dharma_tui_reverse_spec_20260804/`: 25 lens reports, synthesis, and `master_forge_spec/{README,MASTER_FORGE_SPEC,UX_AND_INFORMATION_ARCHITECTURE,DESIGN_SYSTEM,TECHNICAL_ARCHITECTURE,AGENT_AND_CAPABILITY_MODEL,BUILD_ROADMAP,ACCEPTANCE_AND_KILL_GATES,EVIDENCE_BOUNDARY,tasks/prd.json}` | **External active-spec candidate/reference** | Richest target IA; this file replaces it only if admitted. The corpus count/completion is recorded at `/Users/dhyana/dharma_tui_reverse_spec_20260804/STATUS.md:3-12`; the package explicitly owns no repo authority (`.../master_forge_spec/README.md:1-18`). |
| A4 | `/Users/dhyana/Desktop/Projects/DharmaSwarm FrontEnd/` visual/design corpus: `MANDALA_MISSION_CONTROL_CANON.md`, `ART_DIRECTION_v2_2026-06-15_RUG_TO_INSTRUMENT.md`, `LIVING_ONTOLOGY_v1_DESIGN_2026-06-15.md`, `MANDALA_COCKPIT_MASTER_SPEC_PROMPT_2026-06-23.md`, `FRONTEND_DESIGN_PACKET_INDEX.md`, Wave06 V/W/X images and critique, v14 postmortem | **Operator-locked composition reference; no git authority** | Preserve meditation hall + command bridge, rug→instrument, ma/asymmetry/depth, V+W+X formula. Reject old cool palette, single health, fixed ten organs, and painting hero. |
| A5 | `/Users/dhyana/dharma_swarm_tui_audit_20260725/` at baseline `bb3eb9f4`; Operator Seat docs and audit | **Semantic reference** | Select five places, independent axes, typed catalog, pre-effect membrane, projections; governance G0 was blocked. |
| A6 | `/Users/dhyana/ds_operator_seat_p07_preflight_final_20260727@3f4aa245`; packet08 sibling; overnight recovery `1e499cb9` | **Stranded implementation** | Salvage tested contracts/reducers selectively; provider disabled and broker synthetic; never wholesale merge. |
| A7 | Branch `spec/dharma-world-deck-20260809@eefef177`, `spec-forge/mandala-world-deck/{MASTER_SPEC.md,prototype/**}` | **CANDIDATE/INCUBATING dashboard experiment** | Optional spatial/full visual reference only; prototype is synthetic/cool/Inter and targets `/dashboard/cockpit`, not TUI. |
| A8 | `/Users/dhyana/dharma_helm_playground_20260806/` | **Synthetic False Close fixture** | Retain as visual/regression rehearsal; no live repo/model/agent/A2A/network/effect proof (`README.md:1-47`). |
| A9 | Wayfinder method `/Users/dhyana/.codex/skills/wayfinder/SKILL.md`; native-integration goal/evidence; research branch `72718ea`; issue #1278; live slice branch `69102a0`; issue #1277 reports | **Planning/research/live-proof artifacts** | Wayfinder is planning, not product or design chooser. #1277 laws bind this candidate; its `LIVE_DEGRADED 0/7`/blocked proof must remain honest. |
| A10 | Four-model preview worktree/branch `708923bb2`, work packet `reports/agentops/work_packets/helm-worldclass-terminal-WP-HELMFOURMODEL1.json`, draft PR #1341 | **Unmerged preview** | Preserve adapter registry, capability negotiation, requested/served identity, proof state; no “any model,” no OnCall. |
| A11 | Mission Control core `1366d819`/PR #1325; current-main admission `bd779ddc`/PR #1346; `mission_control*.py`, exact tests/API/dashboard/operator-brief paths | **Canonical admitted backend membrane** | Project bounded typed state; no scheduler/store/liveness/promotion/merge ownership. Terminal wiring remains a separate slice. |
| A12 | `/Users/dhyana/dharma_whole_field_failure_audit_20260807/`: verdict, first principles, roadmap, code/OSS audits, manifest, JSONL evidence, adversarial/baseline/code-path/source/vision evidence | **Failure/recovery research** | Preserve UNKNOWN verdict and sequence: truthful read-only → one hand → dry-run compiler → durable worker → multi-agent/external → evolution. |
| A13 | `dharma_swarm/tui/**`, cool `dharma_dark` themes, splash, `docs/reports/TUI_WORLD_CLASS_SPLASH_REPROMPT_2026-03-12.md`; early Bun branch `dgc-splash-art@36d55d9` | **Legacy archaeology** | Mood/history only; not runtime or current terminal appearance. |
| A14 | `origin/governance/close-helm-track-v2-20260803@26c19f9` versus canonical `origin/main:docs/governance/ACTIVE_TRACK.yaml` | **Unresolved governance contradiction** | Main's `ACTIVE` is authoritative though stale; reconcile before admitting this spec. |
| A15 | Tested integration worktree `agent/nihonga-helm-frontier-20260814@74b2370a1`; stacked delivery implementation `agent/nihonga-helm-frontier-stack-20260815@15fb6cd85e9e`; `terminal/src/nihonga/**`, tests, app/goldens | **Committed implementation evidence; unmerged** | Use the integration worktree for operator proof and the stacked branch for review. Rebase the latter after parent landing; neither is runtime authority or current-main product truth. |
| A16 | Primary-source frontier repositories and behavior docs pinned in Section 8 | **External benchmark research** | Adopt patterns, respect licenses, and retain the no-model-provenance boundary. |

### 13.1 Precedence when artifacts disagree

1. Current live owners/receipts and admitted `origin/main` code/tests.
2. Bun/Ink + Python shared-core architecture and Mission Control owner contracts.
3. Locked warm terminal palette at `680b013c` and terminal accessibility laws.
4. Admitted subset of this target IA, with Quiet Lever as default/control.
5. Selected Operator Seat safety contracts and clean tests.
6. June visual corpus as composition/art law, never literal scenery.
7. World Deck as optional lens after its kill gate.
8. Synthetic fixtures for tests only.
9. Legacy cool Textual/splash archaeology.

Concrete resolutions: warm terminal palette beats cool dashboard palettes; five
places beat fifteen peer panes; stable capability regions beat tracks-as-organs;
owner divergence beats one health score; procedural Current Field beats literal
Great Wave art; exact selection beats model-prose retargeting; Action History
beats false Approvals; requested/served/OnCall remain distinct; Mission Control
is a membrane, not a brain.

## 14. Definition of done

The frontier Helm is done only when one admitted, current-main-derived product
passes every gate above and a human operator can use the quiet default to run
the required journeys, summon rich recursive depth without losing context, use
multiple exact model routes without false identity or fallback claims, observe
the whole organism through its real owners, and cause one bounded effect through
a genuine authority membrane with a correlated outcome and independent
verification.

“Looks like the Helm,” “a model answered,” “tests passed on an unmerged branch,”
“seven names are visible,” “Mission Control exists,” and “the dashboard feels
alive” are each insufficient. The product is complete only when the instrument
is beautiful **because its truth, causal structure, and operating boundaries are
legible**.
