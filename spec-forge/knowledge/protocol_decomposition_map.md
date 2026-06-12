# protocol.ts Decomposition Map (S2 pre-work)

Scout 2 deliverable, 2026-06-12. Source read: `terminal/src/protocol.ts` @ 4,064 lines, 175 top-level declarations, 53 exported functions. Dependency graph computed mechanically (symbol-reference scan over exact declaration ranges), not eyeballed. Every line number below is verified against the file as of this scan — re-verify with `grep -n` if the build loop has touched protocol.ts since.

**Verifier for every extraction step**: `cd terminal && bun run typecheck && bun test tests/protocol.test.ts tests/app.test.ts tests/repoPane.test.ts tests/sidebar.test.ts tests/persistence.test.ts` (the `verify:repo-pane` script is this minus persistence; run the union). Green after each wave or roll back the wave.

---

## 1. The zero-break strategy in one paragraph

`protocol.ts` becomes a pure re-export barrel. Consumers (`app.tsx`, `persistence.ts`, `executionLog.ts`, 4 test files) never change an import path during S2. Each extraction step: (1) create the new module file, (2) move the symbol bodies verbatim, (3) add `export * from "./protocol/<module>.ts"` (or named re-exports) to protocol.ts, (4) run the verifier. Because the current file relies on function hoisting (e.g. `workspaceSnapshotPayloadFromEvent` at L862 calls `stringField` defined at L2611), the shared-helpers module MUST be extracted first — after that, every move is import-resolved and order-independent within its wave. All `const` declarations (`VALID_TARGET_PANES` L2485, `TARGET_PANE_ALIASES` L2503, `RUNTIME_SUPERVISOR_AUTHORITATIVE_FIELDS` L32, `RUNTIME_AUTHORITATIVE_SNAPSHOT_FIELDS` L55) are referenced only from inside function bodies, so no TDZ hazard exists after splitting.

NOTE: `app.tsx` imports with an explicit extension: `from "./protocol.ts"` (app.tsx L85). All other consumers use `"./protocol"` / `"../src/protocol"`. The barrel keeps both working; do not rename or move `src/protocol.ts` itself.

---

## 2. Module plan (16 modules + barrel), with exact symbol rosters

Proposed layout: `terminal/src/protocol/` directory; `terminal/src/protocol.ts` stays as the barrel. Body-line counts are exact sums of current declaration ranges; budgets add headroom for imports + named-type declarations.

### M1 `protocol/shared.ts` — core text/record helpers
- **Body 154L, budget 200L. Depends on: `./types` only. LEAF.**
- Symbols (current lines): `makeLine` 88-95, `makeActivityEntry` 96-113, `toLines` 114-121, `findLine` 122-126, `collectSectionLines` 127-145, `trimBullet` 146-149, `firstSemicolonSegment` 150-159, `basename` 160-164, `asRecord` 173-176, `asStringArray` 177-180, `asNumberRecord` 181-189, `prettyRaw` 1909-1912, `compactText` 1913-1920, `previewField` 632-636, `previewValue` 2602-2606, `asRecordList` 2607-2610, `stringField` 2611-2615, `numberField` 2616-2627, `boolField` 2628-2632, `formatUsd` 2633-2636, `formatPercent` 2637-2640, `hasPreviewSignal` 1520-1523.
- Everything else imports this. None of these are currently exported; export them all from the module (the barrel does NOT re-export them — keep them internal to the protocol package).

### M2 `protocol/events.ts` — envelope unwrapping + command identity
- **Body 139L, budget 180L. Depends on: shared.**
- Symbols: `isSlashCommandPrompt` 2118-2121 (EXP), `normalizeCommandName` 2122-2127 (EXP), `inferSlashCommand` 2128-2136 (EXP), `nestedCommandString` 2137-2156, `nestedEnvelopeRecords` 2157-2214, `resolveEventOutput` 2381-2393 (EXP), `resolveEventCommand` 2394-2409 (EXP), `resolveEventActionType` 2410-2422 (EXP).
- `nestedEnvelopeRecords` is the load-bearing shared unwrapper: also called by workspacePayload, runtimeParse, and commands. It must live here, not in commands.

### M3 `protocol/git.ts` — git content parsing
- **Body 181L, budget 220L. Depends on: shared; type-only on topology (see §4 cycle note).**
- Symbols: `normalizeGitHeadLabel` 165-172, `parseGitLine` 206-245, `parseGitSyncLine` 246-250, `parseGitSyncSummary` 251-293, `summarizeBranchStatus` 294-311, `summarizeBranchSyncPreview` 312-321, `totalDirtyCount` 322-329, `summarizeDirtyPressure` 330-346, `summarizeRepoRisk` 347-368, `parseGitHotspotsLine` 369-373, `parseGitChangedPathsLine` 374-378.
- Zero exported symbols today — all consumed by workspacePreview. Export the ones workspacePreview needs.

### M4 `protocol/topology.ts` — worktree-peer topology summaries
- **Body 247L, budget 290L. Depends on: shared; type-only on git (cycle note §4).**
- Symbols: `TopologyPeer` 379-387, `classifyTopologyWarningSeverity` 388-401, `summarizePeerDriftMarker` 402-416, `summarizePeerPressure` 417-441, `selectPrimaryTopologyPeerIndex` 442-472, `summarizeTopologyFromPeers` 473-510, `summarizeTopology` 511-550, `summarizeTopologyStatus` 551-561, `summarizeTopologyWarningMembers` 562-565, `summarizeTopologyPreview` 680-699, `summarizeTopologyPressurePreview` 700-709, `summarizeBranchDivergence` 710-723, `summarizeDetachedPeers` 724-739.

### M5 `protocol/workspacePayload.ts` — workspace payload extraction + workspace summaries
- **Body 277L, budget 330L. Depends on: shared, events (`nestedEnvelopeRecords`), topology (real calls: `summarizeTopologyFromPeers`, `summarizeTopology`).**
- Symbols: `isWorkspaceSnapshotContent` 805-808 (EXP), `workspaceSnapshotPayloadFromEvent` 862-972 (EXP), `extractRepoRoot` 809-812, `extractWorkspaceMetric` 813-816, `summarizeLanguageMix` 817-824, `summarizeImportedModules` 825-832, `summarizeImportedModulesFromPayload` 833-839, `summarizeHotspotsFromPayload` 840-843, `workspaceTopologySummaryFromPayload` 844-857, `inventoryFieldLabel` 858-861, `summarizeHotspots` 566-576, `summarizeHotspotPreview` 577-599, `summarizeLeadHotspotPreview` 600-617, `summarizeHotspotPressurePreview` 618-631, `leadHotspotPreviewFromPreview` 637-644, `summarizeRiskPreview` 645-656, `summarizeRepoRiskPreview` 657-665, `summarizeRepoTruthPreview` 666-679.

### M6 `protocol/workspacePreview.ts` — workspace TabPreview/TranscriptLine builders
- **Body 333L, budget 380L. Depends on: shared, git, topology, workspacePayload.**
- Symbols: `buildWorkspaceSnapshotPreludeFromPreview` 740-800, `buildWorkspaceSnapshotPrelude` 801-804, `workspaceSnapshotToPreview` 973-1086 (EXP), `workspacePayloadToPreview` 1087-1232 (EXP), `workspaceSnapshotToLines` 3995-3998 (EXP), `workspacePreviewToLines` 3999-4002 (EXP).

### M7 `protocol/runtimeParse.ts` — runtime content/payload extraction
- **Body ~356L after the two moves below, budget 400L. Depends on: shared, events; external `./freshness` (`freshnessToken` used at L1351), `./verification` (used at L83-84, L1525-1530).**
- Symbols: `RUNTIME_AUTHORITATIVE_SNAPSHOT_FIELDS` 55-77, `verificationBundleFromPreview` 78-87, `extractRuntimeDb` 1233-1241, `extractToolchain` 1242-1265, `extractRuntimeMetricLine` 1266-1274, `parseRuntimeMetrics` 1275-1280, `runtimeMetricValue` 1281-1284, `runtimeMetricFragment` 1285-1289, `joinRuntimeMetricFragments` 1290-1294, `summarizeSessionState` 1295-1310, `summarizeRunState` 1311-1324, `summarizeContextState` 1325-1340, `summarizeRuntimeFreshness` 1341-1348, `summarizeControlPulsePreview` 1349-1356, `summarizeControlTruthPreview` 1357-1364, `previewControlPulse` 1365-1383, `summarizeRuntimeSummary` 1384-1397, `normalizeCanonicalRuntimeSnapshot` 1398-1445, `runtimeSnapshotPayloadFromEvent` 1446-1473 (EXP), `extractRuntimeAlerts` 1735-1743, `normalizeVerificationPreview` 1524-1537, **plus `runtimeSnapshotToPreview` 1772-1830 (EXP) moved IN** (it calls only runtimeParse symbols — this move is what keeps both runtime modules ≤400 and the dependency one-directional).
- **Moved OUT to M8**: `runtimePayloadHasAuthoritativeControlSignal` (it calls `runtimeSupervisorPreviewFromPayload` + `RUNTIME_SUPERVISOR_AUTHORITATIVE_FIELDS`, both M8 — leaving it here creates a parse→preview cycle).

### M8 `protocol/runtimePreview.ts` — runtime TabPreview/lines builders
- **Body ~376L after moves, budget 400L. Depends on: shared, runtimeParse; external `./freshness` (`parseControlPulsePreview`, `parseRuntimeFreshness` at L1539-1541), `./verification` (L1542-1543, L1844).**
- Symbols: `RUNTIME_SUPERVISOR_AUTHORITATIVE_FIELDS` 32-53, `runtimeSnapshotStateFromPayload` 1493-1519, `compactSupervisorPreview` 1538-1561, `runtimeSupervisorPreviewFromPayload` 1562-1567, `runtimePayloadHasAuthoritativeControlSignal` 1474-1492 (EXP, moved in from the parse range), `runtimePayloadToPreview` 1568-1734 (EXP, 167L — largest single function in the file), `buildRuntimeSnapshotPrelude` 1744-1748, `buildRuntimeSnapshotPreludeFromPreview` 1749-1771, `buildSupervisorPrelude` 1831-1866, `buildSupervisorPreludeFromPreview` 1867-1892, `runtimeSnapshotToLines` 4003-4013 (EXP), `runtimePreviewToLines` 4014-4022 (EXP).

### M9 `protocol/activity.ts` — execution-event → ActivityEntry
- **Body 213L, budget 250L. Depends on: shared, events, approvals.**
- Symbols: `summarizeTool` 1893-1908, `detailLinesFromUnknown` 1921-1939, `activityEntriesFromEvent` 1940-2117 (EXP, 178L).
- `summarizeTool` is also called by `eventToTabPatch` (M16) — export it from this module.

### M10 `protocol/commands.ts` — pane targeting / command routing
- **Body 326L, budget 370L. Depends on: shared, events.**
- Symbols: `commandTargetTab` 2423-2484 (EXP), `VALID_TARGET_PANES` 2485-2502, `TARGET_PANE_ALIASES` 2503-2516, `normalizeTargetPaneId` 2517-2525, `isLauncherPaneTarget` 2526-2529, `deepestOperationalTargetPane` 2530-2539, `nestedTargetPaneCandidates` 2215-2380 (166L — second-largest function), `resolveCommandTargetPane` 2540-2582 (EXP).

### M11 `protocol/approvals.ts` — permission events + approval pane
- **Body 300L, budget 340L. Depends on: shared only. LEAF after M1.**
- Symbols: `permissionDecisionFromEvent` 2944-2968 (EXP), `permissionResolutionFromEvent` 2969-2995 (EXP), `permissionOutcomeFromEvent` 2996-3022 (EXP), `permissionHistoryFromEvent` 3023-3085 (EXP), `approvalLabel` 3086-3098 (**DEAD CODE** — unexported, zero callers; recommend deleting during extraction, with a one-line note in the commit), `approvalEntries` 3100-3105, `selectedApprovalEntry` 3106-3111, `approvalStatusLabel` 3112-3115, `approvalPaneToLines` 3116-3218 (EXP), `approvalPaneToPreview` 3219-3243 (EXP).

### M12 `protocol/sessionsModel.ts` — canonical session normalizers
- **Body 181L, budget 220L. Depends on: shared, approvals (`sessionDetailFromEvent` → `permissionHistoryFromEvent`).**
- Symbols: `normalizeCanonicalSession` 2720-2743, `normalizeCanonicalEventEnvelope` 2744-2768, `normalizeSessionCatalogEntry` 2769-2784, `normalizeSessionCompactionPreview` 2785-2795, `sessionCatalogPayloadRecord` 2796-2802, `sessionDetailPayloadRecord` 2803-2809, `sessionRouteLabel` 2651-2656, `sessionSummaryLine` 2657-2660, `sessionBranchLabel` 2661-2664, `compactableRatioLabel` 2665-2668, `summarizeReplayState` 2641-2650, `sessionCatalogFromEvent` 2852-2863 (EXP), `sessionDetailFromEvent` 3244-3261 (EXP), `summarizeEventEnvelope` 3275-3294, `sessionStatePayload` 3262-3274.

### M13 `protocol/sessionsView.ts` — session pane/bootstrap renderers
- **Body 295L, budget 340L. Depends on: shared, sessionsModel, approvals (`sessionDetailToLines` → `permissionHistoryFromEvent`), workspacePayload + workspacePreview (`sessionBootstrap*` → `workspaceSnapshotPayloadFromEvent`, `workspacePayloadToPreview`).**
- Symbols: `sessionCatalogToLines` 2810-2835 (EXP), `sessionCatalogToPreview` 2836-2851 (EXP), `sessionDetailToLines` 2864-2925 (EXP), `sessionDetailToPreview` 2926-2943 (EXP), `sessionPaneToLines` 3295-3351 (EXP), `sessionPaneToPreview` 3352-3372 (EXP), `sessionBootstrapToLines` 3373-3418 (EXP), `sessionBootstrapToPreview` 3419-3448 (EXP), `summarizeIntent` 2583-2601.

### M14 `protocol/models.ts` — routing decisions / model policy / agent routes
- **Body 243L, budget 290L. Depends on: shared; external `./routePolicy` (only module that uses it: L3627-3756).**
- Symbols: `displayModelRouteLabel` 190-205, `normalizeCanonicalRoutingDecision` 2669-2686, `routingDecisionPayloadFromEvent` 2687-2705 (EXP), `agentRoutesPayloadFromEvent` 2706-2719 (EXP), `modelPolicyToLines` 3626-3718 (EXP), `modelPolicyToPreview` 3719-3759 (EXP), `agentRoutesToLines` 3760-3785 (EXP), `agentRoutesToPreview` 3786-3801 (EXP).

### M15 `protocol/surfaces.ts` — commandGraph / operatorSnapshot / evolutionSurface
- **Body 213L, budget 250L. Depends on: shared, runtimeParse (`operatorSnapshotToPreview` → `summarizeRuntimeSummary`).**
- Symbols: `commandGraphToLines` 3449-3470 (EXP), `commandGraphToPreview` 3471-3485 (EXP), `operatorSnapshotToLines` 3486-3536 (EXP), `operatorSnapshotToPreview` 3537-3625 (EXP), `evolutionSurfaceToLines` 3802-3825 (EXP), `evolutionSurfaceToPreview` 3826-3837 (EXP).

### M16 `protocol/tabs.ts` — static tab/outline builders + the patch dispatcher
- Split into two files because of dependency direction:
  - **M16a `protocol/tabsStatic.ts`** — `buildBridgeTabs` 4023-4039 (EXP), `buildBridgeOutline` 4040-4056 (EXP), `outlineFromTabs` 4057-4065 (EXP). **Body 43L. ZERO dependencies (pure literals). Extract in Wave 0.**
  - **M16b `protocol/tabPatch.ts`** — `eventToTabPatch` 3838-3994 (EXP, 157L). **Depends on: shared, events, commands, approvals, runtimeParse, workspacePayload, sessionsModel, activity (`summarizeTool`). The apex dispatcher — extract LAST.**

**Barrel** `protocol.ts` after S2: ~70 lines of re-exports covering exactly the 53 currently-exported functions (roster in §6). Internal helpers are NOT re-exported.

---

## 3. Cross-module dependency matrix (mechanically derived)

```
shared           -> (types only)
tabsStatic       -> (types only)
events           -> shared
git              -> shared, [type-only: topology]
topology         -> shared, [type-only: git]
approvals        -> shared
models           -> shared, ./routePolicy
sessionsModel    -> shared, approvals
commands         -> shared, events
workspacePayload -> shared, events, topology
runtimeParse     -> shared, events, ./freshness, ./verification
activity         -> shared, events, approvals
workspacePreview -> shared, git, topology, workspacePayload
runtimePreview   -> shared, runtimeParse, ./freshness, ./verification
surfaces         -> shared, runtimeParse
sessionsView     -> shared, sessionsModel, approvals, workspacePayload, workspacePreview
tabPatch         -> shared, events, commands, approvals, runtimeParse, workspacePayload, sessionsModel, activity
```

Acyclic given the two fixes in §4. Key load-bearing edges (symbol level):
- `workspaceSnapshotToPreview` → 27 callees across git(8)/topology(7)/workspacePayload(11)/shared(1) — the widest fan-out in the file.
- `workspacePayloadToPreview` → 23 callees, same families.
- `eventToTabPatch` → 14 callees across 8 modules.
- `activityEntriesFromEvent` → 10 callees (shared 5, events 3, approvals 3).
- `sessionBootstrapTo*` → workspace family (the only sessions→workspace edge).
- `operatorSnapshotToPreview` → `summarizeRuntimeSummary` (the only surfaces→runtime edge).

## 4. Two cycles found, both pre-resolved

1. **git ↔ topology** — purely TYPE-LEVEL. `summarizeRepoRisk` (L347-350) and `summarizeRiskPreview` (L645) take `ReturnType<typeof summarizeTopology>`; `summarizeBranchDivergence` (L710-711) takes `ReturnType<typeof parseGitSyncSummary>`. **Fix**: declare named exported types once — `export type GitLineSummary = ReturnType<typeof parseGitLine>`, `GitSyncSummary`, `TopologySummary` — in their owning modules and use `import type` across. Type-only circular imports are erased at runtime and safe under bun + `tsc --noEmit`. (Extract git + topology in the same coder session to do this in one pass.)
2. **runtimeParse ↔ runtimePreview** — REAL. `runtimePayloadHasAuthoritativeControlSignal` (L1474-1491) calls `runtimeSupervisorPreviewFromPayload` + `RUNTIME_SUPERVISOR_AUTHORITATIVE_FIELDS` (preview-side). **Fix already baked into the rosters above**: that function moves to runtimePreview; `runtimeSnapshotToPreview` moves to runtimeParse (all 12 of its callees are parse-side). Result: preview → parse only.

## 5. Extraction order (waves; build green after every wave)

| Wave | Modules | Why safe |
|---|---|---|
| 0 | M1 shared, M16a tabsStatic | Zero in-file deps. Unblocks hoisting hazard for everything else. |
| 1 | M2 events, M11 approvals, M14 models, M3 git + M4 topology (one session, shared named types) | Depend only on Wave 0 (+ external routePolicy for models). |
| 2 | M10 commands, M12 sessionsModel, M7 runtimeParse, M5 workspacePayload, M9 activity | Depend only on Waves 0-1. All five are mutually independent — fan out to parallel coders if lanes don't share protocol.ts edits (they do share barrel edits; serialize the barrel append or assign one integrator). |
| 3 | M6 workspacePreview, M8 runtimePreview, M15 surfaces | Depend on Wave 2. Mutually independent. |
| 4 | M13 sessionsView | Needs workspacePreview (Wave 3). |
| 5 | M16b tabPatch | Needs everything. After this, protocol.ts is barrel-only. |

Per-step recipe (repeat per module): create file → move bodies verbatim (no logic edits in S2 except the two §4 moves and optional `approvalLabel` deletion) → add module-internal `export` keywords to formerly-private helpers that other protocol modules consume → add barrel re-export for public symbols → `bun run typecheck` → targeted test file → full verifier at wave end. **Never edit consumer files. Never reorder function bodies within a move.**

## 6. Danger list — symbols with external consumers (stable barrel paths REQUIRED)

The barrel must re-export all 53 exported functions. The externally-consumed subset, by consumer:

- **`src/app.tsx`** (imports from `"./protocol.ts"`, L41-85 — 43 symbols): approvalPaneToLines, approvalPaneToPreview, agentRoutesPayloadFromEvent, agentRoutesToLines, agentRoutesToPreview, buildBridgeTabs, normalizeCommandName, commandTargetTab, commandGraphToLines, commandGraphToPreview, evolutionSurfaceToLines, evolutionSurfaceToPreview, eventToTabPatch, isSlashCommandPrompt, isWorkspaceSnapshotContent, modelPolicyToLines, modelPolicyToPreview, permissionDecisionFromEvent, permissionHistoryFromEvent, permissionOutcomeFromEvent, permissionResolutionFromEvent, resolveCommandTargetPane, resolveEventActionType, resolveEventCommand, resolveEventOutput, routingDecisionPayloadFromEvent, outlineFromTabs, runtimePreviewToLines, runtimePayloadHasAuthoritativeControlSignal, runtimePayloadToPreview, runtimeSnapshotPayloadFromEvent, runtimeSnapshotToLines, runtimeSnapshotToPreview, sessionCatalogFromEvent, sessionDetailFromEvent, sessionPaneToLines, sessionPaneToPreview, sessionBootstrapToLines, sessionBootstrapToPreview, workspacePreviewToLines, workspacePayloadToPreview, workspaceSnapshotPayloadFromEvent, workspaceSnapshotToPreview.
- **`src/persistence.ts`** (L7-12, 4 symbols): runtimePayloadToPreview, runtimeSnapshotPayloadFromEvent, workspacePayloadToPreview, workspaceSnapshotPayloadFromEvent.
- **`src/executionLog.ts`** (L2-9, 6 symbols): permissionDecisionFromEvent, permissionOutcomeFromEvent, permissionResolutionFromEvent, resolveEventActionType, resolveEventCommand, resolveEventOutput.
- **`tests/protocol.test.ts`** (L3-49): 45 symbols (near-total surface).
- **`tests/app.test.ts`** (L38-50, 12): commandTargetTab, eventToTabPatch, normalizeCommandName, resolveCommandTargetPane, resolveEventActionType, resolveEventCommand, runtimeSnapshotToPreview, runtimePayloadToPreview, runtimePreviewToLines, workspacePayloadToPreview, workspacePreviewToLines, workspaceSnapshotToPreview.
- **`tests/repoPane.test.ts` / `tests/sidebar.test.ts`** (3 each): workspacePayloadToPreview, workspacePreviewToLines, workspaceSnapshotToPreview.
- Exported but consumed ONLY by tests/barrel (safe to move freely, must stay exported): inferSlashCommand, activityEntriesFromEvent, sessionCatalogToLines/ToPreview, sessionDetailToLines/ToPreview, permissionHistoryFromEvent (also app.tsx), operatorSnapshotToLines/ToPreview, modelPolicyToLines/ToPreview, workspaceSnapshotToLines, buildBridgeOutline.

## 7. Test-block → module mapping (`tests/protocol.test.ts`, 3,252 lines)

| describe block | test lines | follows module |
|---|---|---|
| normalizeCommandName | 54-60 | events |
| activityEntriesFromEvent | 61-126 | activity |
| typed session helpers | 127-310 | sessionsModel |
| typed runtime helpers | 311-535 | runtimeParse (+runtimePreview for preview assertions) |
| typed workspace helpers | 536-835 | workspacePayload |
| approval helpers | 836-1055 | approvals |
| session payload renderers | 1056-1188 | sessionsView |
| inferSlashCommand | 1189-1212 | events |
| isSlashCommandPrompt | 1213-1219 | events |
| commandTargetTab | 1220-1283 | commands |
| resolveCommandTargetPane | 1284-1492 | commands |
| eventToTabPatch | 1493-2116 | tabPatch (623 lines of tests — the regression net for Wave 5) |
| sessionBootstrap helpers | 2117-2190 | sessionsView |
| commandGraph helpers | 2191-2216 | surfaces |
| operatorSnapshot helpers | 2217-2258 | surfaces |
| modelPolicy helpers | 2259-2354 | models |
| agentRoutes helpers | 2355-2394 | models |
| evolutionSurface helpers | 2395-2413 | surfaces |
| workspaceSnapshotToLines | 2414-2492 | workspacePreview |
| workspacePreviewToLines | 2493-2600 | workspacePreview |
| workspaceSnapshotToPreview | 2601-3044 | workspacePreview (444 lines — Wave 3's net) |
| runtimeSnapshotToLines | 3045-3111 | runtimePreview |
| runtimePreviewToLines | 3112-3170 | runtimePreview |
| runtimeSnapshotToPreview | 3171-3252 | runtimeParse (post-move home of that function) |

S2 does NOT split the test file; it keeps testing through the barrel. Splitting tests per module is an optional follow-up (S3+), enabled by this table.

## 8. `type ===` string-sniff sites — exactly 37, in exactly 3 functions

When a discriminated-union event type later replaces string sniffing, only three surfaces change:

| Future module | Function | Count | Lines |
|---|---|---|---|
| activity | activityEntriesFromEvent | 13 | 1943, 1950, 1958, 1976, 1999, 2020, 2041, 2062, 2068, 2078, 2096, 2098, 2105 |
| sessionsModel | summarizeEventEnvelope | 5 | 3277, 3280, 3283, 3286, 3289 (these sniff `event.event_type`, typed `CanonicalEventEnvelope` — already half-canonical) |
| tabPatch | eventToTabPatch | 19 | 3841, 3844, 3849, 3872, 3875, 3878, 3881, 3894, 3897, 3900, 3908, 3925, 3942, 3955, 3965, 3967, 3969, 3978, 3987 |

The sniffed tag vocabulary (union candidates): bridge.ready, handshake.result, command.result, action.result, workspace.snapshot.result, session.catalog.result, session.detail.result, session.ack, text_delta, text_complete, thinking_delta, thinking_complete, tool_call_complete, tool_result, permission.decision, permission.resolution, permission.outcome, task_started, task_progress, task_complete, session_start, session_end, error, bridge.error.

## 9. `Record<string, unknown>` sites — 97 lines, grouped by future module

| Module | Count | Lines |
|---|---|---|
| shared | 10 | 173, 174, 1909, 1910, 2602, 2607, 2608, 2611, 2616, 2628 (these ARE the typed boundary — they stay) |
| events | 6 | 2157, 2163, 2187, 2381, 2394, 2410 |
| workspacePayload | 7 | 862, 863, 876, 882, 939, 945, 957 |
| runtimeParse | 2 | 1446, 1447 |
| activity | 2 | 1899, 1940 |
| commands | 2 | 2215, 2540 |
| approvals | 4 | 2944, 2969, 2996, 3023 |
| sessionsModel | 9 | 2651, 2657, 2661, 2762, 2796, 2803, 2852, 3244, 3262 |
| sessionsView | 14 | 2583, 2810, 2836, 2864, 2926, 3313, 3373, 3380, 3385, 3389, 3419, 3421, 3426, 3430 |
| models | 15 | 2687, 2706, 3626, 3675, 3695, 3719, 3741, 3760, 3763, 3767, 3770, 3786, 3789, 3793, 3798 |
| surfaces | 25 | 3449, 3451, 3453, 3454, 3471, 3473, 3475, 3476, 3486, 3488, 3491, 3517, 3528, 3537, 3539, 3542, 3564, 3572, 3603, 3802, 3804, 3810, 3826, 3828, 3834 |
| tabPatch | 1 | 3838 |

Typing-debt ranking for any post-S2 payload-typing pass: **surfaces (25) > models (15) > sessionsView (14)** — these three render raw payloads with no canonical type at all (no `CommandGraphPayload`, `OperatorSnapshotPayload`, `ModelPolicyPayload`, `EvolutionSurfacePayload` exist in types.ts). The workspace/runtime/session/permission families already normalize into canonical payload types early; their remaining Record sites are legitimately at the event boundary.

## 10. Other findings for the conductor

- **Dead code**: `approvalLabel` (L3086-3098) — unexported, zero callers. Delete during M11 extraction.
- **`summarizeTool` placement**: lives in activity but called by tabPatch; if a coder wants tabPatch to avoid importing activity, the alternative home is shared. Current plan: activity exports it.
- **External-import containment after split**: `./freshness` + `./verification` → runtime modules only; `./routePolicy` → models only; `./types` → everywhere. This containment is a correctness check: if any other module needs those imports, the coder mis-assigned a symbol.
- **Largest functions** (refactor candidates AFTER the split, not during): `activityEntriesFromEvent` 178L, `runtimePayloadToPreview` 167L, `nestedTargetPaneCandidates` 166L, `eventToTabPatch` 157L, `workspacePayloadToPreview` 146L, `workspaceSnapshotToPreview` 114L, `workspaceSnapshotPayloadFromEvent` 111L, `approvalPaneToLines` 103L.
- **Lint budget**: `eslint --max-warnings 19` is currently exactly at budget; moving code can shift warning locations but should not change the count. If a wave trips it, check for newly-unused imports in the barrel, not for logic drift.
- **Collision note**: the live build loop owns `src/` — this map is knowledge only; S2 coder sessions execute it under conductor scheduling, not this scout.
