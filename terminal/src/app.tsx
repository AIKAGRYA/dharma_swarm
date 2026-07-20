import React, {useEffect, useMemo, useReducer, useRef, useState} from "react";
import {Box, Text, useApp, useInput, useStdin} from "ink";

import {DharmaBridge, type BridgeEvent} from "./bridge.ts";
import {ActivityPane, activityRowCount} from "./components/ActivityPane.tsx";
import {canonicalEventsFromBridgeEvent, latestChatTurnRoute, localCommandResultExecutionEvent, localStatusExecutionEvent, queuedPromptExecutionEvent, userPromptExecutionEvent} from "./executionLog.ts";
import {
  loadSupervisorRepoPreview,
  loadStoredState,
  normalizeRepoPreview,
  loadSupervisorControlPreview,
  loadSupervisorControlState,
  saveSupervisorRepoPreview,
  saveStoredState,
  saveSupervisorControlSummary,
} from "./persistence.ts";
import {Composer} from "./components/Composer.tsx";
import {ApprovalsPane} from "./components/ApprovalsPane.tsx";
import {AgentsPane} from "./components/AgentsPane.tsx";
import {ControlPane, buildControlPaneSections, buildRuntimePaneSections} from "./components/ControlPane.tsx";
import {ModelPicker} from "./components/ModelPicker.tsx";
import {OperatorSummaryBand} from "./components/OperatorSummaryBand.tsx";
import {PaneSwitcher} from "./components/PaneSwitcher.tsx";
import {RepoPane, buildRepoPaneSections} from "./components/RepoPane.tsx";
import {NavigatorRail} from "./components/NavigatorRail.tsx";
import {ScenicStrip} from "./components/ScenicStrip.tsx";
import {SessionsPane} from "./components/SessionsPane.tsx";
import {TourOverlay} from "./components/TourOverlay.tsx";
import {ShellHeader} from "./components/ShellHeader.tsx";
import {Sidebar} from "./components/Sidebar.tsx";
import {StatusFooter} from "./components/StatusFooter.tsx";
import {TabBar} from "./components/TabBar.tsx";
import {TranscriptPane} from "./components/TranscriptPane.tsx";
import {closestCommand, helmDirectiveToIntent, matchUiIntent, parseHelmDirectives, tourLines, type HelmDirective, type UiIntent} from "./uiIntents.ts";
import {REGISTERED_SLASH_COMMANDS} from "./commandRegistry.ts";
import {parseControlPulsePreview, parseRuntimeFreshness} from "./freshness.ts";
import {routeLabel, routePolicyFromValue, routePolicyWithSuccessfulReceipt, routeSummary, selectableRouteTargets} from "./routePolicy.ts";
import {THEME} from "./theme.ts";
import {manuscriptLines, scrollStatusLine} from "./scrollFace.ts";
import {isPlainReturn, normalizeComposerInput} from "./inputPolicy.ts";
import {
  continuityStateFromSession,
  messagesForNextTurn,
  sessionResumeEligibility,
} from "./sessionContinuity.ts";
import {focusModeFor, paneActionsFor, type PaneAction} from "./shellControls.ts";
import {
  SESSION_CATALOG_LIMIT,
  authoritativeResyncComplete,
  authoritativeResyncStatus,
  markAuthoritativeSurface,
  requestAuthoritativeResync,
  requestLiveSnapshots,
  requestMissingAuthoritativeSurfaces,
  requestPermissionHistory,
  requestSessionCatalog,
  sendBackgroundRequest,
} from "./surfaceAuthority.ts";
import {
  buildVerificationSummaryRows,
  isGenericVerificationLabel,
  parseVerificationBundle,
  resolveVerificationEntries,
} from "./verification.ts";
import {
  approvalPaneToLines,
  approvalPaneToPreview,
  agentRoutesPayloadFromEvent,
  agentRoutesToLines,
  agentRoutesToPreview,
  buildBridgeTabs,
  normalizeCommandName,
  commandTargetTab,
  commandGraphToLines,
  commandGraphToPreview,
  evolutionSurfaceToLines,
  evolutionSurfaceToPreview,
  eventToTabPatch,
  isSlashCommandPrompt,
  isWorkspaceSnapshotContent,
  modelPolicyToLines,
  modelPolicyToPreview,
  handshakeRouteConfigFromEvent,
  providerRouteReceiptFromEvent,
  permissionDecisionFromEvent,
  permissionHistoryFromEvent,
  permissionOutcomeFromEvent,
  permissionResolutionFromEvent,
  resolveCommandTargetPane,
  resolveEventActionType,
  resolveEventCommand,
  resolveEventOutput,
  routingDecisionPayloadFromEvent,
  outlineFromTabs,
  runtimePreviewToLines,
  runtimePayloadHasAuthoritativeControlSignal,
  runtimePayloadToPreview,
  runtimeSnapshotPayloadFromEvent,
  runtimeSnapshotToLines,
  runtimeSnapshotToPreview,
  sessionCatalogFromEvent,
  sessionDetailResultFromEvent,
  sessionPaneToLines,
  sessionPaneToPreview,
  sessionBootstrapToLines,
  sessionBootstrapToPreview,
  workspacePreviewToLines,
  workspacePayloadToPreview,
  workspaceSnapshotPayloadFromEvent,
  workspaceSnapshotToPreview,
} from "./protocol.ts";
import {
  nextSessionPaneAfterCatalog,
  nextSessionPaneAfterDetailResult,
} from "./sessionPaneState.ts";
import {initialState, reduceApp} from "./state.ts";
import type {ActiveTurnState, AppAction, AppState, ApprovalQueueEntry, ApprovalQueueState, CanonicalPermissionDecision, CanonicalPermissionOutcome, CanonicalPermissionResolution, RouteTarget, RuntimeSnapshotPayload, SessionPaneState, SurfaceAuthorityState, TabPreview, TabSpec, TranscriptLine, WorkspaceSnapshotPayload} from "./types.ts";

export {continuityStateFromSession} from "./sessionContinuity.ts";
export {
  authoritativeResyncComplete,
  authoritativeResyncStatus,
  markAuthoritativeSurface,
  missingAuthoritativeSurfaces,
  requestMissingAuthoritativeSurfaces,
} from "./surfaceAuthority.ts";

const SNAPSHOT_REFRESH_INTERVAL_MS = 15000;
const SESSION_TRANSCRIPT_LIMIT = 40;
// F-021: floor lowered 8 -> 5 so the 80x24 budget (24 - 17 chrome rows = 7)
// is not forced past the terminal height by the old floor.
const MIN_SCROLL_WINDOW_SIZE = 5;

type ModelChoice = RouteTarget;

type PendingCommandStream = {
  command: string;
  tabId: string;
  lastCompletedText?: string;
};

export type TurnCancellationDecision =
  | {kind: "idle"}
  | {kind: "request"; requestId: string}
  | {kind: "already_requested"; requestId: string; cancelRequestId: string};

export function decideTurnCancellation(activeTurn: ActiveTurnState): TurnCancellationDecision {
  if (activeTurn.phase === "idle") {
    return {kind: "idle"};
  }
  if (activeTurn.phase === "cancelling") {
    return {
      kind: "already_requested",
      requestId: activeTurn.requestId,
      cancelRequestId: activeTurn.cancelRequestId,
    };
  }
  return {kind: "request", requestId: activeTurn.requestId};
}

const shellControlOptions = {
  sessionCatalogLimit: SESSION_CATALOG_LIMIT,
  approvalResolveAction,
};

function bridgeRouteState(state: AppState): {provider: string; model: string; strategy: string} {
  return {
    provider: state.routePolicy.provider,
    model: state.routePolicy.model,
    strategy: state.routePolicy.strategy,
  };
}

function ensureRuntimeTabs(stateTabs: TabSpec[]): TabSpec[] {
  const existingIds = new Set(stateTabs.map((tab) => tab.id));
  const missing = buildBridgeTabs().filter((tab) => !existingIds.has(tab.id));
  return [...stateTabs, ...missing];
}

function queueAppActions(dispatch: React.Dispatch<AppAction>, actions: AppAction[]): void {
  if (actions.length === 0) {
    return;
  }
  if (actions.length === 1) {
    dispatch(actions[0]);
    return;
  }
  dispatch({type: "batch", actions});
}

function markPendingCommandStream(
  pendingCommandStream: React.MutableRefObject<PendingCommandStream | null> | undefined,
  event: Record<string, unknown>,
): void {
  if (!pendingCommandStream) {
    return;
  }
  const command = resolveEventCommand(event);
  if (!command) {
    return;
  }
  pendingCommandStream.current = {
    command,
    tabId: resolveCommandTargetPane(event, commandTargetTab(command)),
    lastCompletedText: undefined,
  };
}

function clearPendingCommandStream(
  pendingCommandStream: React.MutableRefObject<PendingCommandStream | null> | undefined,
): void {
  if (pendingCommandStream) {
    pendingCommandStream.current = null;
  }
}

function reconcilePendingCommandStream(
  pendingCommand: PendingCommandStream | null,
  event: Record<string, unknown>,
): PendingCommandStream | null {
  if (!pendingCommand) {
    return null;
  }

  const command = resolveEventCommand(event) || pendingCommand.command;
  const tabId = resolveSlashCommandResultTabId(event, command, pendingCommand.tabId);
  if (command === pendingCommand.command && tabId === pendingCommand.tabId) {
    return pendingCommand;
  }

  return {
    ...pendingCommand,
    command,
    tabId,
  };
}

function normalizeCommandStreamText(content: unknown): string {
  return typeof content === "string" ? content.trim() : "";
}

function shouldSuppressPendingCommandStreamOutput(pendingCommand: PendingCommandStream | null): boolean {
  if (!pendingCommand) {
    return false;
  }
  return pendingCommand.tabId === "chat";
}

function shouldSuppressDuplicatePendingCommandPatch(
  event: Record<string, unknown>,
  pendingCommand: PendingCommandStream | null,
): boolean {
  if (!pendingCommand?.lastCompletedText) {
    return false;
  }
  const eventType = String(event.type ?? "");
  const isSlashCommandResult =
    eventType === "command.result" || (eventType === "action.result" && resolveEventActionType(event) === "command.run");
  if (!isSlashCommandResult) {
    return false;
  }
  if (normalizeCommandStreamText(resolveEventOutput(event)) !== pendingCommand.lastCompletedText) {
    return false;
  }
  return resolveCommandTargetPane(event, "control") === pendingCommand.tabId;
}

function snapshotActionsForPendingCommandStream(
  pendingCommand: PendingCommandStream | null,
  output: string,
  liveRepoPreview?: TabPreview,
  liveControlPreview?: TabPreview,
  supervisor = loadSupervisorControlState(),
): AppAction[] {
  if (!pendingCommand || !output) {
    return [];
  }

  return commandRunSnapshotActionsForBridgeEvent(
    {
      type: "command.result",
      command: pendingCommand.command,
      target_pane: pendingCommand.tabId,
      output,
    },
    liveRepoPreview,
    liveControlPreview,
    supervisor,
  );
}

export function commandRunEventFromPaneAction(
  action: {summary: string; payload: Record<string, unknown>} | undefined,
): Record<string, unknown> | undefined {
  if (!action || String(action.payload.action_type ?? "") !== "command.run") {
    return undefined;
  }

  return {
    ...action.payload,
    summary: action.summary,
  };
}

function transcriptMetaForTab(tab: TabSpec | undefined): {subtitle: string; emptyState: string; accentColor: string} {
  switch (tab?.kind) {
    case "chat":
      return {
        subtitle: "Live operator exchange, assistant output, and command spillover that still belongs in chat.",
        emptyState: "No operator exchange yet.",
        accentColor: "cyan",
      };
    case "mission":
      return {
        subtitle: "Bootstrap framing, intent routing, and session launch context.",
        emptyState: "Mission bootstrap is waiting on the next session start.",
        accentColor: "magenta",
      };
    case "ontology":
      return {
        subtitle: "Shared world model, foundations, and semantic frame updates.",
        emptyState: "Ontology surface has not been refreshed yet.",
        accentColor: "green",
      };
    case "commands":
      return {
        subtitle: "Registered command graph and operational affordances.",
        emptyState: "Command registry is waiting on refresh.",
        accentColor: "yellow",
      };
    case "evolution":
      return {
        subtitle: "Forward-loop, swarm evolution, and shell continuation surface.",
        emptyState: "Evolution surface has not been materialized yet.",
        accentColor: "blue",
      };
    default:
      return {
        subtitle: "Structured operator transcript.",
        emptyState: "No content yet.",
        accentColor: "gray",
      };
  }
}

function previewField(preview: TabPreview | undefined, label: string): string {
  const value = preview?.[label];
  return typeof value === "string" ? value.trim() : "";
}

function hasPreviewSignal(value: string): boolean {
  return value.length > 0 && value !== "unknown" && value !== "none" && value !== "n/a";
}

const DEFERRED_CONTROL_PREVIEW_FIELDS = [
  "Loop state",
  "Task progress",
  "Active task",
  "Result status",
  "Acceptance",
  "Last result",
  "Loop decision",
  "Next task",
  "Updated",
  "Durable state",
  "Verification summary",
  "Verification bundle",
  "Verification checks",
  "Verification status",
  "Verification passing",
  "Verification failing",
  "Verification updated",
  "Control pulse preview",
  "Control truth preview",
  "Runtime freshness",
] as const;

const DEFERRED_REPO_TOPOLOGY_PREVIEW_FIELDS = [
  "Topology status",
  "Topology peer count",
  "Topology warnings",
  "Topology warning members",
  "Topology warning severity",
  "Topology risk",
  "Risk preview",
  "Topology preview",
  "Topology pressure preview",
  "Primary warning",
  "Primary peer drift",
  "Branch divergence",
  "Detached peers",
  "Primary topology peer",
  "Peer drift markers",
  "Topology peers",
  "Topology pressure",
] as const;

const DEFERRED_REPO_HOTSPOT_PREVIEW_FIELDS = [
  "Hotspot summary",
  "Lead hotspot preview",
  "Hotspot pressure preview",
  "Primary file hotspot",
  "Primary dependency hotspot",
  "Hotspots",
  "Inbound hotspots",
] as const;

function preserveDeferredControlPreview(nextPreview: TabPreview, livePreview?: TabPreview): TabPreview {
  if (!livePreview) {
    return nextPreview;
  }
  const mergedPreview: TabPreview = {...nextPreview};
  for (const field of DEFERRED_CONTROL_PREVIEW_FIELDS) {
    const liveValue = previewField(livePreview, field);
    if (hasPreviewSignal(liveValue)) {
      mergedPreview[field] = liveValue;
    }
  }
  return mergedPreview;
}

function previewSignalPresent(value: string): boolean {
  return value.length > 0 && value !== "unknown" && value !== "none" && value !== "n/a";
}

function preservePreviewFields(
  nextPreview: TabPreview,
  livePreview: TabPreview | undefined,
  fields: readonly string[],
): TabPreview {
  if (!livePreview) {
    return nextPreview;
  }
  const mergedPreview: TabPreview = {...nextPreview};
  for (const field of fields) {
    const liveValue = previewField(livePreview, field);
    if (!previewSignalPresent(liveValue)) {
      continue;
    }
    mergedPreview[field] = liveValue;
  }
  return mergedPreview;
}

function rawWorkspacePayloadRecord(event: Record<string, unknown>): Record<string, unknown> | undefined {
  const pending: unknown[] = [event, event.workspace_payload];
  const visited = new Set<object>();
  while (pending.length > 0) {
    const candidate = pending.shift();
    if (typeof candidate !== "object" || candidate === null || visited.has(candidate)) {
      continue;
    }
    visited.add(candidate);
    const record = candidate as Record<string, unknown>;
    if (record.version === "v1" && record.domain === "workspace_snapshot") {
      return record;
    }
    pending.push(record.payload, record.result, record.workspace_payload);
  }
  return undefined;
}

function workspaceEventHasAuthoritativeTopology(event: Record<string, unknown>): boolean {
  const rawPayload = rawWorkspacePayloadRecord(event);
  return Boolean(workspaceSnapshotPayloadFromEvent(event) && rawPayload && Object.hasOwn(rawPayload, "topology"));
}

function workspaceEventHasAuthoritativeHotspotDetail(event: Record<string, unknown>): boolean {
  const rawPayload = rawWorkspacePayloadRecord(event);
  return Boolean(
    workspaceSnapshotPayloadFromEvent(event) &&
      rawPayload &&
      (Object.hasOwn(rawPayload, "largest_python_files") || Object.hasOwn(rawPayload, "most_imported_modules")),
  );
}

function workspaceEventHasAuthoritativeRepoSignal(event: Record<string, unknown>): boolean {
  return workspaceEventHasAuthoritativeTopology(event) && workspaceEventHasAuthoritativeHotspotDetail(event);
}

function workspaceEventHasTopologyDisplaySignal(event: Record<string, unknown>): boolean {
  if (workspaceEventHasAuthoritativeTopology(event)) {
    return true;
  }
  return /^##\s+Topology\b/m.test(String(event.content ?? ""));
}

function workspaceEventHasHotspotDisplaySignal(event: Record<string, unknown>): boolean {
  if (workspaceEventHasAuthoritativeHotspotDetail(event)) {
    return true;
  }
  const content = String(event.content ?? "");
  const hasHotspotSummary = /^Git hotspots:\s*(?!none\b).+/im.test(content);
  const hasChangedPathDetail = /^Git changed paths:\s*(?!none\b).+/im.test(content);
  const hasHotspotDetailSection =
    /^##\s+(?:Largest Python files|Most imported local modules)\b/im.test(content) ||
    /^(?:Primary file hotspot|Dependency hotspots|Inbound hotspots):\s*(?!none\b).+/im.test(content);
  return hasHotspotSummary && hasChangedPathDetail && hasHotspotDetailSection;
}

function preserveDeferredRepoPreview(nextPreview: TabPreview, livePreview: TabPreview | undefined, event: Record<string, unknown>): TabPreview {
  let mergedPreview = nextPreview;
  if (!workspaceEventHasTopologyDisplaySignal(event)) {
    mergedPreview = preservePreviewFields(mergedPreview, livePreview, DEFERRED_REPO_TOPOLOGY_PREVIEW_FIELDS);
  }
  if (!workspaceEventHasHotspotDisplaySignal(event)) {
    mergedPreview = preservePreviewFields(mergedPreview, livePreview, DEFERRED_REPO_HOTSPOT_PREVIEW_FIELDS);
  }
  return mergedPreview;
}

function derivedOperatorRuntimeFreshness(preview: TabPreview | undefined): string {
  const explicit = previewField(preview, "Runtime freshness");
  if (hasPreviewSignal(explicit)) {
    return explicit;
  }
  return parseControlPulsePreview(previewField(preview, "Control pulse preview")).runtimeFreshness ?? "";
}

function normalizeOperatorLoopLabel(loopState: string): string {
  return loopState.replace(/\brunning_cycle\b/gi, "running").replace(/\s+/g, " ").trim();
}

function operatorLoopSummary(preview: TabPreview | undefined): {value: string; tone: "live" | "warn" | "critical" | "neutral"} {
  const explicitLoopState = previewField(preview, "Loop state");
  const loopState = hasPreviewSignal(explicitLoopState)
    ? explicitLoopState
    : parseRuntimeFreshness(derivedOperatorRuntimeFreshness(preview)).loopState || "";
  if (!hasPreviewSignal(loopState)) {
    return {value: "unknown", tone: "neutral"};
  }
  const normalizedLabel = normalizeOperatorLoopLabel(loopState);
  const normalized = normalizedLabel.toLowerCase();
  if (/(fail|error|blocked|stalled)/.test(normalized)) {
    return {value: normalizedLabel, tone: "critical"};
  }
  if (/(wait|pending|verify|review)/.test(normalized)) {
    return {value: normalizedLabel, tone: "warn"};
  }
  return {value: normalizedLabel, tone: "live"};
}

function operatorVerificationSummary(preview: TabPreview | undefined): {value: string; tone: "live" | "warn" | "critical" | "neutral"} {
  const checks = previewField(preview, "Verification checks");
  const summary = previewField(preview, "Verification summary");
  const bundle = resolveVerificationEntries({
    checksText: checks,
    summaryText: summary,
    bundleText: previewField(preview, "Verification bundle"),
    passingText: previewField(preview, "Verification passing"),
    failingText: previewField(preview, "Verification failing"),
  });
  if (bundle.length > 0) {
    const rows = buildVerificationSummaryRows(bundle);
    return {
      value: rows.status,
      tone: rows.failing === "none" ? "live" : "critical",
    };
  }

  const compactBundle = parseRuntimeFreshness(derivedOperatorRuntimeFreshness(preview)).verificationBundle ?? "";
  const parsedCompactBundle = parseVerificationBundle("none", compactBundle);
  if (parsedCompactBundle.length > 0) {
    const rows = buildVerificationSummaryRows(parsedCompactBundle);
    return {
      value: rows.status,
      tone: rows.failing === "none" ? "live" : "critical",
    };
  }

  const status = previewField(preview, "Verification status");
  if (hasPreviewSignal(status)) {
    if (!isGenericVerificationLabel(status)) {
      return {value: status, tone: "warn"};
    }
    const normalized = status.toLowerCase();
    return {
      value: status,
      tone: /(fail|error)/.test(normalized) ? "critical" : /(ok|pass)/.test(normalized) ? "live" : "warn",
    };
  }
  if (hasPreviewSignal(summary) && isGenericVerificationLabel(summary)) {
    const normalized = summary.toLowerCase();
    return {
      value: summary,
      tone: /(fail|error)/.test(normalized) ? "critical" : /(ok|pass)/.test(normalized) ? "live" : "warn",
    };
  }
  return {value: "unknown", tone: "neutral"};
}

function parseRuntimeActivityMetrics(value: string): Record<string, string> {
  if (!hasPreviewSignal(value)) {
    return {};
  }
  return Object.fromEntries(
    Array.from(value.matchAll(/([A-Za-z][A-Za-z0-9]*)=([^\s]+)/g), (match) => [match[1], match[2]]),
  );
}

function operatorRuntimeSummary(
  preview: TabPreview | undefined,
  fallbackSessionCount: number,
): {value: string; tone: "live" | "warn" | "critical" | "neutral"} {
  const runtimeSummary = previewField(preview, "Runtime summary");
  if (hasPreviewSignal(runtimeSummary)) {
    return {value: runtimeSummary, tone: "live"};
  }

  const metrics = parseRuntimeActivityMetrics(previewField(preview, "Runtime activity"));
  const fragments = [
    metrics.Sessions ? `${metrics.Sessions} sessions` : "",
    metrics.Runs ? `${metrics.Runs} runs` : "",
    metrics.ActiveRuns && metrics.ActiveRuns !== "0" ? `${metrics.ActiveRuns} active` : "",
  ].filter((value) => value.length > 0);
  if (fragments.length > 0) {
    return {value: fragments.join(" | "), tone: "live"};
  }

  if (fallbackSessionCount > 0) {
    return {value: `${fallbackSessionCount} sessions`, tone: "live"};
  }

  return {value: "idle", tone: "neutral"};
}

function mergeOperatorSummaryPreviewSources(...previews: Array<TabPreview | undefined>): TabPreview | undefined {
  const merged: TabPreview = {};
  for (const preview of previews) {
    if (!preview) {
      continue;
    }
    for (const [key, rawValue] of Object.entries(preview)) {
      const candidate = rawValue.trim();
      if (!candidate) {
        continue;
      }
      const existing = previewField(merged, key);
      if (!existing || !hasPreviewSignal(existing) || hasPreviewSignal(candidate)) {
        merged[key] = candidate;
      }
    }
  }
  return Object.keys(merged).length > 0 ? merged : undefined;
}

function operatorSummaryPreview(state: AppState): TabPreview | undefined {
  const controlTabPreview = state.tabs.find((tab) => tab.id === "control")?.preview;
  const runtimeTabPreview = state.tabs.find((tab) => tab.id === "runtime")?.preview;
  const repoPreview = mergeOperatorSummaryPreviewSources(
    state.tabs.find((tab) => tab.id === "repo")?.preview,
    state.liveRepoPreview,
  );
  return controlPanePreview(
    mergeOperatorSummaryPreviewSources(controlTabPreview, runtimeTabPreview, state.liveControlPreview),
    repoPreview,
  );
}

export function buildOperatorSummaryItems(state: AppState): Array<{label: string; value: string; tone?: "live" | "warn" | "critical" | "neutral"}> {
  const pendingApprovals = state.approvalPane.order.filter((actionId) => state.approvalPane.entriesByActionId[actionId]?.pending).length;
  const sessionCount = state.sessionPane.catalog?.count ?? state.sessionPane.catalog?.sessions.length ?? 0;
  const preview = operatorSummaryPreview(state);
  const loop = operatorLoopSummary(preview);
  const verification = operatorVerificationSummary(preview);
  const runtime = operatorRuntimeSummary(preview, sessionCount);
  const approvalsTone = pendingApprovals > 0 ? "warn" : "live";
  // F-164 status single-source: bridge/route/strategy live EXCLUSIVELY in the
  // bottom status row — the summary band carries operational data only.
  return [
    {label: "loop", value: loop.value, tone: loop.tone},
    {label: "verify", value: verification.value, tone: verification.tone},
    {label: "runtime", value: runtime.value, tone: runtime.tone},
    {label: "approvals", value: pendingApprovals === 0 ? "clear" : `${pendingApprovals} pending`, tone: approvalsTone},
    {label: "sessions", value: `${sessionCount}`, tone: sessionCount > 0 ? "live" : "neutral"},
  ];
}

function isDuplicateCompletedAssistantPatch(state: AppState, event: Record<string, unknown>): boolean {
  if (String(event.type ?? "") !== "text_complete") {
    return false;
  }
  const content = String(event.content ?? "").trim();
  if (!content) {
    return false;
  }
  const chatLines = state.tabs.find((tab) => tab.id === "chat")?.lines ?? [];
  for (let index = chatLines.length - 1; index >= 0; index -= 1) {
    const line = chatLines[index];
    if (!line) {
      continue;
    }
    if (line.kind !== "assistant") {
      continue;
    }
    return line.text.trim() === content;
  }
  return false;
}

function displayedTranscriptLinesForTab(activeTab: TabSpec | undefined, state: AppState): TranscriptLine[] {
  if (activeTab?.kind !== "chat") {
    return activeTab?.lines ?? [];
  }
  const firstUserIndex = activeTab.lines.findIndex((line) => line.kind === "user");
  const chatPreludeLines = firstUserIndex >= 0 ? activeTab.lines.slice(0, firstUserIndex) : activeTab.lines;
  return [...chatPreludeLines, ...state.chatTraceLines];
}

function requestSessionDetail(
  bridge: DharmaBridge,
  dispatch: React.Dispatch<AppAction>,
  sessionId: string | undefined,
  background = false,
): string | undefined {
  if (!sessionId) {
    return undefined;
  }
  const payload = {session_id: sessionId, transcript_limit: SESSION_TRANSCRIPT_LIMIT};
  const requestId = background
    ? sendBackgroundRequest(bridge, "session.detail", payload)
    : bridge.send("session.detail", payload);
  dispatch({type: "session.detail.requested", requestId, sessionId});
  return requestId;
}

function nextApprovalPaneAfterDecision(
  current: ApprovalQueueState,
  decision: CanonicalPermissionDecision,
  seenAt = new Date().toISOString(),
): ApprovalQueueState {
  const existing = current.entriesByActionId[decision.action_id];
  const pending = decision.decision === "require_approval" && decision.requires_confirmation;
  return {
    selectedActionId: pending ? decision.action_id : current.selectedActionId ?? decision.action_id,
    entriesByActionId: {
      ...current.entriesByActionId,
      [decision.action_id]: {
        decision,
        status: existing?.resolution ? existing.status : pending ? "pending" : "observed",
        firstSeenAt: existing?.firstSeenAt ?? seenAt,
        lastSeenAt: seenAt,
        lastSourceEventType: "permission.decision",
        seenCount: (existing?.seenCount ?? 0) + 1,
        pending,
        resolution: existing?.resolution,
      },
    },
    order: [decision.action_id, ...current.order.filter((actionId) => actionId !== decision.action_id)],
    historyBacked: false,
    lastHistorySyncAt: current.lastHistorySyncAt,
  };
}

function nextApprovalPaneAfterResolution(
  current: ApprovalQueueState,
  resolution: CanonicalPermissionResolution,
): ApprovalQueueState {
  const existing = current.entriesByActionId[resolution.action_id];
  if (!existing) {
    return current;
  }
  const entriesByActionId = {
    ...current.entriesByActionId,
    [resolution.action_id]: {
      ...existing,
      status: resolution.resolution,
      pending: false,
      resolution,
      lastSeenAt: resolution.resolved_at,
      lastSourceEventType: "permission.resolution",
    },
  };
  const order = [resolution.action_id, ...current.order.filter((actionId) => actionId !== resolution.action_id)];
  const pendingSelection = order.find((actionId) => entriesByActionId[actionId]?.pending);
  return {
    selectedActionId:
      current.selectedActionId === resolution.action_id
        ? pendingSelection ?? order.find((actionId) => Boolean(entriesByActionId[actionId]))
        : current.selectedActionId,
    entriesByActionId,
    order,
    historyBacked: false,
    lastHistorySyncAt: current.lastHistorySyncAt,
  };
}

function nextApprovalPaneAfterOutcome(
  current: ApprovalQueueState,
  outcome: CanonicalPermissionOutcome,
): ApprovalQueueState {
  const existing = current.entriesByActionId[outcome.action_id];
  if (!existing) {
    return current;
  }
  const entriesByActionId = {
    ...current.entriesByActionId,
    [outcome.action_id]: {
      ...existing,
      status: outcome.outcome,
      outcome,
      pending: false,
      lastSeenAt: outcome.outcome_at,
      lastSourceEventType: "permission.outcome",
    },
  };
  const order = [outcome.action_id, ...current.order.filter((actionId) => actionId !== outcome.action_id)];
  return {
    selectedActionId: current.selectedActionId ?? outcome.action_id,
    entriesByActionId,
    order,
    historyBacked: false,
    lastHistorySyncAt: current.lastHistorySyncAt,
  };
}

function approvalPaneFromHistory(history: NonNullable<ReturnType<typeof permissionHistoryFromEvent>>): ApprovalQueueState {
  const order = history.entries.map((entry) => entry.action_id);
  const entriesByActionId = Object.fromEntries(
    history.entries.map((entry) => [
      entry.action_id,
      {
        decision: entry.decision,
        status: entry.status,
        firstSeenAt: entry.first_seen_at,
        lastSeenAt: entry.last_seen_at,
        lastSourceEventType: entry.resolution ? "permission.resolution" : "permission.decision",
        seenCount: entry.seen_count,
        pending: entry.pending,
        resolution: entry.resolution ?? undefined,
        outcome: entry.outcome ?? undefined,
      },
    ]),
  );
  return {
    selectedActionId: order.find((actionId) => entriesByActionId[actionId]?.pending) ?? order[0],
    entriesByActionId,
    order,
    historyBacked: true,
  };
}

function approvalResolveAction(entry: ApprovalQueueEntry, resolution: CanonicalPermissionResolution["resolution"], label: string): PaneAction {
  return {
    label,
    summary: `${resolution} ${entry.decision.action_id}`,
    payload: {
      action_type: "approval.resolve",
      action_id: entry.decision.action_id,
      resolution,
      metadata: entry.decision.metadata,
    },
  };
}

type PendingBootstrap = {
  prompt: string;
  provider: string;
  model: string;
  messages: Array<{role: "user" | "assistant" | "system"; content: string}>;
  resumeSessionId?: string;
  cancelled?: boolean;
};

type BridgeHandlerDeps = {
  dispatch: React.Dispatch<AppAction>;
  getState: () => AppState;
  bridge: DharmaBridge;
  pendingBootstraps: React.MutableRefObject<Record<string, PendingBootstrap>>;
  pendingCommandStream?: React.MutableRefObject<PendingCommandStream | null>;
  requestHandshake?: (reason: "initial" | "reconnect" | "probe") => void;
  resetHandshakeBackoff?: () => void;
};

export function handshakeBackoffDelayMs(attempt: number): number {
  if (attempt <= 1) {
    return 5_000;
  }
  if (attempt === 2) {
    return 15_000;
  }
  if (attempt === 3) {
    return 30_000;
  }
  return 60_000;
}

function scrollMaxOffsetForTab(activeTab: TabSpec | undefined, state: AppState, windowSize: number): number {
  if (!activeTab) {
    return 0;
  }
  if (activeTab.kind === "chat") {
    return Math.max(displayedTranscriptLinesForTab(activeTab, state).length - windowSize, 0);
  }
  if (activeTab.kind === "thinking" || activeTab.kind === "tools" || activeTab.kind === "timeline") {
    return Math.max(activityRowCount(activeTab.kind, state.activityFeed) - windowSize, 0);
  }
  if (activeTab.kind === "repo") {
    const sections = buildRepoPaneSections(
      state.liveRepoPreview ?? activeTab.preview,
      activeTab.lines,
      state.liveControlPreview ?? state.tabs.find((tab) => tab.id === "control")?.preview,
      state.tabs.find((tab) => tab.id === "control")?.lines ?? [],
    );
    const selected = sections[state.paneFocusIndices[activeTab.id] ?? 0];
    return Math.max((selected?.rows.length ?? 0) - Math.max(windowSize - 4, MIN_SCROLL_WINDOW_SIZE), 0);
  }
  if (activeTab.kind === "control") {
    const preview = state.liveControlPreview ?? activeTab.preview ?? state.tabs.find((tab) => tab.id === "control")?.preview;
    const sections = buildControlPaneSections(preview, activeTab.lines);
    const selected = sections[state.paneFocusIndices[activeTab.id] ?? 0];
    return Math.max((selected?.rows.length ?? 0) - Math.max(windowSize - 4, MIN_SCROLL_WINDOW_SIZE), 0);
  }
  if (activeTab.kind === "runtime") {
    const runtimeLines =
      activeTab.lines.length === 0 ? (state.tabs.find((tab) => tab.id === "control")?.lines ?? []) : activeTab.lines;
    const preview = state.liveControlPreview ?? activeTab.preview ?? state.tabs.find((tab) => tab.id === "control")?.preview;
    const sections = buildRuntimePaneSections(preview, runtimeLines);
    const selected = sections[state.paneFocusIndices[activeTab.id] ?? 0];
    return Math.max((selected?.rows.length ?? 0) - Math.max(windowSize - 4, MIN_SCROLL_WINDOW_SIZE), 0);
  }
  return Math.max((activeTab.lines.length || 0) - windowSize, 0);
}

function isBareModelCommand(prompt: string): boolean {
  const trimmed = prompt.trim();
  return trimmed === "/model" || trimmed === "/models" || trimmed === "/model list";
}

function stepApprovalSelection(state: AppState, direction: 1 | -1): string | undefined {
  const order = state.approvalPane.order;
  if (order.length === 0) {
    return undefined;
  }
  const currentIndex = state.approvalPane.selectedActionId ? order.indexOf(state.approvalPane.selectedActionId) : -1;
  const nextIndex = currentIndex === -1 ? 0 : Math.min(Math.max(currentIndex + direction, 0), order.length - 1);
  return order[nextIndex];
}

function stepSessionSelection(state: AppState, direction: 1 | -1): string | undefined {
  const sessions = state.sessionPane.catalog?.sessions ?? [];
  if (sessions.length === 0) {
    return undefined;
  }
  const currentIndex = state.sessionPane.selectedSessionId
    ? sessions.findIndex((entry) => entry.session.session_id === state.sessionPane.selectedSessionId)
    : -1;
  const nextIndex = currentIndex === -1 ? 0 : Math.min(Math.max(currentIndex + direction, 0), sessions.length - 1);
  return sessions[nextIndex]?.session.session_id;
}

function stepPaneSectionFocus(
  currentIndex: number | undefined,
  sectionCount: number,
  direction: 1 | -1,
): number | undefined {
  if (sectionCount <= 0) {
    return undefined;
  }
  const baseIndex = currentIndex ?? 0;
  return Math.min(Math.max(baseIndex + direction, 0), sectionCount - 1);
}

function agentRouteCount(lines: TranscriptLine[]): number {
  return lines.filter((line) => /^\s*-\s+.+? -> .+?:.+? \| effort .+ \| role .+$/.test(line.text)).length;
}

function paneSectionCount(activeTab: TabSpec | undefined, state: AppState): number {
  if (!activeTab) {
    return 0;
  }
  if (activeTab.kind === "repo") {
    return buildRepoPaneSections(
      state.liveRepoPreview ?? activeTab.preview,
      activeTab.lines,
      state.liveControlPreview ?? state.tabs.find((tab) => tab.id === "control")?.preview,
      state.tabs.find((tab) => tab.id === "control")?.lines ?? [],
    ).length;
  }
  if (activeTab.kind === "control") {
    const preview = state.liveControlPreview ?? activeTab.preview ?? state.tabs.find((tab) => tab.id === "control")?.preview;
    return buildControlPaneSections(preview, activeTab.lines).length;
  }
  if (activeTab.kind === "runtime") {
    const runtimeLines =
      activeTab.lines.length === 0 ? (state.tabs.find((tab) => tab.id === "control")?.lines ?? []) : activeTab.lines;
    const preview = state.liveControlPreview ?? activeTab.preview ?? state.tabs.find((tab) => tab.id === "control")?.preview;
    return buildRuntimePaneSections(preview, runtimeLines).length;
  }
  return 0;
}

function mergePreview(current: Record<string, string> | undefined, incoming: Record<string, string> | undefined): Record<string, string> | undefined {
  if (!incoming) {
    return current;
  }
  return {...(current ?? {}), ...incoming};
}

function asPreviewRecord(value: unknown): TabPreview | undefined {
  if (typeof value !== "object" || value === null) {
    return undefined;
  }
  const entries = Object.entries(value as Record<string, unknown>).filter((entry): entry is [string, string] => typeof entry[1] === "string");
  if (entries.length === 0) {
    return undefined;
  }
  return Object.fromEntries(entries);
}

function authorityLabel(surface: "repo" | "control", bridgeStatus: AppState["bridgeStatus"], authoritative: boolean): string {
  if (bridgeStatus === "connected") {
    return authoritative ? "live | authoritative" : `resyncing | awaiting authoritative ${surface} refresh`;
  }
  if (authoritative) {
    return `stale | bridge ${bridgeStatus} | last authoritative ${surface} snapshot`;
  }
  return `placeholder | bridge ${bridgeStatus} | awaiting authoritative ${surface} refresh`;
}

function decorateSurfacePreview(
  preview: TabPreview | undefined,
  surface: "repo" | "control",
  bridgeStatus: AppState["bridgeStatus"],
  authoritativeSurfaces: SurfaceAuthorityState,
): TabPreview | undefined {
  if (!preview) {
    return undefined;
  }
  return {
    ...preview,
    Authority: authorityLabel(surface, bridgeStatus, authoritativeSurfaces[surface]),
  };
}

export function controlPanePreview(
  controlPreview: TabPreview | undefined,
  repoPreview: TabPreview | undefined,
): TabPreview | undefined {
  if (!controlPreview && !repoPreview) {
    return undefined;
  }
  const repoControlPreview = repoPreview?.["Repo/control preview"];
  if (typeof repoControlPreview !== "string" || repoControlPreview.length === 0) {
    return controlPreview;
  }
  return {
    ...(controlPreview ?? {}),
    ...(typeof controlPreview?.["Repo/control preview"] === "string" && controlPreview["Repo/control preview"].length > 0
      ? {}
      : {"Repo/control preview": repoControlPreview}),
  };
}

function synchronizeRepoControlPreviews(
  repoPreview: TabPreview | undefined,
  controlPreview: TabPreview | undefined,
  now: Date = new Date(),
) {
  return normalizeRepoPreview(repoPreview, controlPreview, now);
}

function isStructuredControlSnapshotContent(output: string): boolean {
  return output.includes("# Runtime") || /^(Runtime DB|Durable state):\s+/m.test(output);
}

export function commandRunSnapshotActionsForBridgeEvent(
  event: BridgeEvent,
  liveRepoPreview?: TabPreview,
  liveControlPreview?: TabPreview,
  supervisor = loadSupervisorControlState(),
): AppAction[] {
  const typed = event as Record<string, unknown>;
  const eventType = String(typed.type ?? "");
  const isCommandRunAction = eventType === "action.result" && resolveEventActionType(typed) === "command.run";
  if (eventType !== "command.result" && !isCommandRunAction) {
    return [];
  }

  const targetPane = resolveCommandTargetPane(typed, "control");
  const workspacePayload = workspaceSnapshotPayloadFromEvent(typed);
  const runtimePayload = runtimeSnapshotPayloadFromEvent(typed);
  if (targetPane === "repo") {
    if (workspacePayload) {
      const preview = workspacePayloadToPreview(workspacePayload);
      const synchronizedPreview = synchronizeRepoControlPreviews(preview, liveControlPreview);
      return [
        {
          type: "tab.replace",
          tabId: "repo",
          lines: workspacePreviewToLines(synchronizedPreview ?? preview),
          preview: synchronizedPreview ?? preview,
        },
        {type: "live.repo.set", preview: synchronizedPreview ?? preview},
      ];
    }

    const output = resolveEventOutput(typed);
    if (!isWorkspaceSnapshotContent(output)) {
      return [];
    }

    const preview = workspaceSnapshotToPreview(output);
    const synchronizedPreview = synchronizeRepoControlPreviews(preview, liveControlPreview);
    return [
      {
        type: "tab.replace",
        tabId: "repo",
        lines: workspacePreviewToLines(synchronizedPreview ?? preview),
        preview: synchronizedPreview ?? preview,
      },
      {type: "live.repo.set", preview: synchronizedPreview ?? preview},
    ];
  }

  if (targetPane === "control" || targetPane === "runtime") {
    if (runtimePayload) {
      const preview = runtimePayloadToPreview(runtimePayload, supervisor);
      const synchronizedRepoPreview = synchronizeRepoControlPreviews(liveRepoPreview, preview);
      return [
        {
          type: "tab.replace",
          tabId: "control",
          lines: runtimePreviewToLines(preview),
          preview,
        },
        {
          type: "tab.replace",
          tabId: "runtime",
          lines: runtimePreviewToLines(preview),
          preview,
        },
        {type: "live.control.set", preview},
        ...(synchronizedRepoPreview ? [{type: "live.repo.set", preview: synchronizedRepoPreview} as const] : []),
      ];
    }

    const output = resolveEventOutput(typed);
    if (!isStructuredControlSnapshotContent(output)) {
      return [];
    }

    const preview = runtimeSnapshotToPreview(output, supervisor);
    const synchronizedRepoPreview = synchronizeRepoControlPreviews(liveRepoPreview, preview);
    return [
      {
        type: "tab.replace",
        tabId: "control",
        lines: runtimePreviewToLines(preview),
        preview,
      },
      {
        type: "tab.replace",
        tabId: "runtime",
        lines: runtimePreviewToLines(preview),
        preview,
      },
      {type: "live.control.set", preview},
      ...(synchronizedRepoPreview ? [{type: "live.repo.set", preview: synchronizedRepoPreview} as const] : []),
    ];
  }

  return [];
}

export function persistControlPreview(preview?: TabPreview, runtimePayload?: RuntimeSnapshotPayload): void {
  if (!preview) {
    return;
  }
  const supervisor = loadSupervisorControlState();
  if (supervisor) {
    saveSupervisorControlSummary(supervisor, preview, {runtimePayload});
  }
}

export function persistRepoPreview(preview?: TabPreview, workspacePayload?: WorkspaceSnapshotPayload): void {
  if (!preview) {
    return;
  }
  const supervisor = loadSupervisorControlState();
  if (supervisor) {
    saveSupervisorRepoPreview(supervisor, preview, {workspacePayload});
  }
}

export function snapshotActionsForBridgeEvent(
  event: BridgeEvent,
  liveRepoPreview?: TabPreview,
  liveControlPreview?: TabPreview,
): AppAction[] {
  const typed = event as Record<string, unknown>;
  const eventType = String(typed.type ?? "");

  if (eventType === "workspace.snapshot.result") {
    const typedPayload = workspaceSnapshotPayloadFromEvent(typed);
    const preview = typedPayload
      ? workspacePayloadToPreview(typedPayload)
      : workspaceSnapshotToPreview(String(typed.content ?? ""));
    const effectivePreview = preserveDeferredRepoPreview(preview, liveRepoPreview, typed);
    const synchronizedPreview = synchronizeRepoControlPreviews(effectivePreview, liveControlPreview);
    return [
      {
        type: "tab.replace",
        tabId: "repo",
        lines: workspacePreviewToLines(synchronizedPreview ?? effectivePreview),
        preview: synchronizedPreview ?? effectivePreview,
      },
      {type: "live.repo.set", preview: synchronizedPreview ?? effectivePreview},
    ];
  }

  if (eventType === "session.bootstrap.result") {
    const actions: AppAction[] = [];
    const workspacePayload = workspaceSnapshotPayloadFromEvent(typed);
    const runtimePayload = runtimeSnapshotPayloadFromEvent(typed);
    const rawWorkspacePreview = workspacePayload
      ? workspacePayloadToPreview(workspacePayload)
      : asPreviewRecord(typed.workspace_preview) ?? liveRepoPreview;
    const runtimePreview = runtimePayload
      ? runtimePayloadToPreview(runtimePayload)
      : asPreviewRecord(typed.runtime_preview) ?? liveControlPreview;
    const workspacePreview = synchronizeRepoControlPreviews(
      rawWorkspacePreview,
      runtimePreview,
    );

    if (workspacePreview) {
      actions.push({
        type: "tab.replace",
        tabId: "repo",
        lines: workspacePreviewToLines(workspacePreview),
        preview: workspacePreview,
      });
      actions.push({
        type: "live.repo.set",
        preview: workspacePreview,
      });
    }

    if (runtimePreview) {
      actions.push({
        type: "tab.replace",
        tabId: "control",
        lines: runtimePreviewToLines(runtimePreview),
        preview: runtimePreview,
      });
      actions.push({
        type: "tab.replace",
        tabId: "runtime",
        lines: runtimePreviewToLines(runtimePreview),
        preview: runtimePreview,
      });
      actions.push({
        type: "live.control.set",
        preview: runtimePreview,
      });
    }

    return actions;
  }

  return [];
}

export function commandResultActionsForBridgeEvent(
  event: BridgeEvent,
  fallbackCommand?: string,
  fallbackTabId?: string,
): AppAction[] {
  const typed = event as Record<string, unknown>;
  if (String(typed.type ?? "") !== "command.result") {
    return [];
  }

  return slashCommandResultActions(
    typed,
    String(typed.summary ?? "action applied"),
    fallbackCommand,
    fallbackTabId,
  );
}

export function slashCommandStartActions(event: Record<string, unknown>, statusPrefix = "command"): AppAction[] {
  const command = resolveEventCommand(event);
  if (!command) {
    return [];
  }

  const tabId = resolveCommandTargetPane(event, commandTargetTab(command));
  return [
    {type: "tab.activate", tabId},
    {type: "status.set", value: `${statusPrefix} ${command} -> ${tabId}`},
  ];
}

function commandIntentFromBootstrapIntent(intent: Record<string, unknown>, command: string): Record<string, unknown> {
  const commandIntent: Record<string, unknown> = {command};
  for (const key of [
    "target_surface",
    "targetSurface",
    "target_surface_id",
    "targetSurfaceId",
    "target_pane",
    "targetPane",
    "surface",
    "surface_id",
    "surfaceId",
    "target_pane_id",
    "targetPaneId",
    "target_tab",
    "targetTab",
    "target_tab_id",
    "targetTabId",
    "pane",
    "pane_id",
    "paneId",
    "tab",
    "tab_id",
    "tabId",
  ]) {
    const value = intent[key];
    if (typeof value === "string" && value.trim()) {
      commandIntent[key] = value;
    }
  }
  return commandIntent;
}

export function actionResultActionsForBridgeEvent(
  event: BridgeEvent,
  fallbackCommand?: string,
  fallbackTabId?: string,
): AppAction[] {
  const typed = event as Record<string, unknown>;
  if (String(typed.type ?? "") !== "action.result") {
    return [];
  }

  if (resolveEventActionType(typed) !== "command.run") {
    return [];
  }

  return slashCommandResultActions(
    typed,
    String(typed.summary ?? "action applied"),
    fallbackCommand,
    fallbackTabId,
  );
}

function isOperationalResultTab(tabId: string): boolean {
  return tabId.length > 0 && tabId !== "chat" && tabId !== "commands";
}

function sanitizeSlashCommandFallbackTabId(tabId: string | undefined): string {
  return tabId === "commands" ? "" : tabId ?? "";
}

function resolveSlashCommandResultTabId(
  event: Record<string, unknown>,
  fallbackCommand?: string,
  fallbackTabId?: string,
): string {
  const eventCommand = resolveEventCommand(event);
  const command = eventCommand || fallbackCommand || "";
  const resolvedTabId = resolveCommandTargetPane(event, "");
  const fallbackCommandTabId = fallbackCommand ? commandTargetTab(fallbackCommand) : "";
  const preferredFallbackTabId =
    [fallbackTabId ?? "", fallbackCommandTabId].find((tabId) => isOperationalResultTab(tabId)) ?? fallbackTabId ?? "";
  const sanitizedFallbackTabId = sanitizeSlashCommandFallbackTabId(fallbackTabId);
  if (!eventCommand && isOperationalResultTab(sanitizedFallbackTabId) && resolvedTabId !== sanitizedFallbackTabId) {
    return sanitizedFallbackTabId;
  }
  return (
    isOperationalResultTab(preferredFallbackTabId) && !isOperationalResultTab(resolvedTabId)
      ? preferredFallbackTabId
      : resolvedTabId || sanitizedFallbackTabId || "control"
  );
}

function slashCommandResultActions(
  event: Record<string, unknown>,
  fallbackStatus = String(event.summary ?? "action applied"),
  fallbackCommand?: string,
  fallbackTabId?: string,
): AppAction[] {
  const command = resolveEventCommand(event) || fallbackCommand || "";
  const normalized = normalizeCommandName(command);
  const tabId = resolveSlashCommandResultTabId(event, fallbackCommand, fallbackTabId);
  const statusValue = normalized ? `/${normalized} -> ${tabId}` : fallbackStatus;
  return [
    {type: "tab.activate", tabId},
    {type: "status.set", value: statusValue},
  ];
}

function enrichSparseCommandResultEvent(
  event: Record<string, unknown>,
  pendingCommand: PendingCommandStream | null,
): Record<string, unknown> {
  if (!pendingCommand) {
    return event;
  }

  const eventType = String(event.type ?? "");
  const isCommandResult = eventType === "command.result";
  const isCommandRunAction = eventType === "action.result" && resolveEventActionType(event) === "command.run";
  if (!isCommandResult && !isCommandRunAction) {
    return event;
  }

  const command = resolveEventCommand(event);
  const targetPane = resolveCommandTargetPane(event, "");
  const shouldOverrideTargetPane =
    isOperationalResultTab(pendingCommand.tabId) &&
    (!isOperationalResultTab(targetPane) || (!command && targetPane !== pendingCommand.tabId));
  if (command && targetPane && !shouldOverrideTargetPane) {
    return event;
  }

  return {
    ...event,
    ...(command ? {} : {command: pendingCommand.command}),
    ...((targetPane && !shouldOverrideTargetPane) ? {} : {target_pane: pendingCommand.tabId}),
  };
}

// Execute an agent-emitted ⟦helm:…⟧ directive: the same reducer dispatches as
// the operator's own plain language, but narration goes to the rail head-band
// (the agent already narrated in its reply text) — never a duplicate respond.
// The agent REQUESTS; this is the single point where the TS reducer EXECUTES.
// Only VIEW/toggle verbs resolve; operator-gated actions never reach here.
function executeAgentDirective(
  directive: HelmDirective,
  state: AppState,
  dispatch: React.Dispatch<AppAction>,
  bridge: DharmaBridge,
): void {
  const panes = state.tabs.map((tab) => ({id: tab.id, title: tab.title}));
  const intent = helmDirectiveToIntent(directive, panes, selectableRouteTargets(state.routePolicy));
  if (!intent) {
    dispatch({type: "navigator.narrate", line: `couldn't act on "${directive.verb} ${directive.arg}".`});
    return;
  }
  if (intent.kind === "layout") {
    dispatch({type: "layout.mode.set", mode: intent.mode});
    dispatch({type: "navigator.narrate", line: `switched to the ${intent.mode} view`});
    dispatch({type: "status.set", value: `navigator -> ${intent.mode}`});
    return;
  }
  if (intent.kind === "pane") {
    dispatch({type: "tab.activate", tabId: intent.tabId});
    dispatch({type: "navigator.narrate", line: `opened ${intent.title}`});
    dispatch({type: "status.set", value: `navigator -> ${intent.title}`});
    return;
  }
  if (intent.kind === "rail") {
    const on = intent.on === "toggle" ? !state.uiMode.railVisible : intent.on;
    if (on && state.uiMode.layoutMode !== "cockpit") {
      dispatch({type: "layout.mode.set", mode: "cockpit"});
    }
    dispatch({type: "rail.set", visible: on});
    dispatch({type: "navigator.narrate", line: on ? "docked the chat rail" : "undocked the rail"});
    return;
  }
  if (intent.kind === "model") {
    if (state.bridgeStatus === "connected") {
      bridge.send("action.run", {
        action_type: "model.set",
        provider: intent.target.provider,
        model: intent.target.model,
        strategy: state.routePolicy.strategy,
      });
    }
    dispatch({type: "navigator.narrate", line: `switching route to ${intent.target.provider}:${intent.target.model}`});
    return;
  }
}

export function createBridgeEventHandler({
  dispatch,
  getState,
  bridge,
  pendingBootstraps,
  pendingCommandStream,
  requestHandshake,
  resetHandshakeBackoff,
}: BridgeHandlerDeps): (event: BridgeEvent) => void {
  let awaitingAuthoritativeResync = true;
  let resyncPending = false;
  let reconnectRequested = false;
  const reconnectingCodes = new Set(["bridge_exit", "bridge_spawn_error", "bridge_send_failed", "bridge_stdin_unavailable"]);
  let malformedBridgeEvents = 0;
  const apply = (actions: AppAction[]): void => queueAppActions(dispatch, actions);
  const startSession = (payload: Record<string, unknown>): string => {
    const requestId = bridge.send("session.start", payload);
    apply([{type: "turn.start", requestId}]);
    return requestId;
  };

  function requestReconnect(status: string, offline = false): void {
    awaitingAuthoritativeResync = true;
    resyncPending = false;
    apply([
      {type: "surface.truth.reset"},
      {type: "turn.reset"},
      {type: "bridge.status", status: offline ? "offline" : "degraded"},
      {type: "status.set", value: status},
    ]);
    if (reconnectRequested) {
      return;
    }
    reconnectRequested = true;
    if (requestHandshake) {
      requestHandshake("reconnect");
    } else {
      bridge.send("handshake");
    }
  }

  return (event: BridgeEvent) => {
    const state = getState();
    const originalPendingCommand = pendingCommandStream?.current ?? null;
    const streamedPendingCommand =
      String((event as Record<string, unknown>).type ?? "") === "text_delta" ||
      String((event as Record<string, unknown>).type ?? "") === "text_complete"
        ? reconcilePendingCommandStream(originalPendingCommand, event as Record<string, unknown>)
        : originalPendingCommand;
    if (pendingCommandStream && streamedPendingCommand !== originalPendingCommand) {
      pendingCommandStream.current = streamedPendingCommand;
    }
    const pendingCommand = streamedPendingCommand;
    const typed = enrichSparseCommandResultEvent(event as Record<string, unknown>, pendingCommand);
    const eventType = String(typed.type ?? "");
    const canonicalEvents = canonicalEventsFromBridgeEvent(typed);
    if (canonicalEvents.length > 0) {
      apply([{type: "execution.events.ingest", events: canonicalEvents}]);
    }
    if (eventType === "session.ack") {
      const requestId = String(typed.request_id ?? "");
      if (requestId) {
        apply([{
          type: "turn.ack",
          requestId,
          sessionId: String(typed.session_id ?? "") || undefined,
        }]);
      }
    }
    if (eventType === "session.cancelled") {
      const cancelRequestId = String(typed.request_id ?? "");
      const targetRequestId = String(typed.target_request_id ?? "");
      const cancelled = typed.cancelled === true;
      const reason = String(typed.reason ?? (cancelled ? "cancel_requested" : "rejected"));
      const actions: AppAction[] = [{
        type: "status.set",
        value: cancelled ? "cancellation accepted" : `cancellation rejected: ${reason}`,
      }];
      if (!cancelled && cancelRequestId && targetRequestId) {
        actions.unshift({
          type: "turn.cancel.rejected",
          requestId: targetRequestId,
          cancelRequestId,
        });
      }
      apply(actions);
    }
    if (eventType === "session_end") {
      const requestId = String(typed.request_id ?? "");
      if (requestId) apply([{type: "turn.finish", requestId}]);
    }
    if (eventType === "route.receipt") {
      const receipt = providerRouteReceiptFromEvent(typed), routePolicy = getState().routePolicy;
      if (receipt) apply([{type: "route.policy.set", policy: routePolicyWithSuccessfulReceipt(routePolicy, receipt)}]);
    }
    // Agent-action channel: the chat agent drives the Helm by emitting
    // ⟦helm:…⟧ directives in its reply. Parse them off the completed assistant
    // text and execute each (the sentinel itself is stripped from the display).
    const assistantText =
      eventType === "text_complete"
        ? String(typed.content ?? "")
        : eventType === "assistant"
          ? String(typed.message ?? "")
          : "";
    if (assistantText.includes("⟦")) {
      for (const directive of parseHelmDirectives(assistantText)) {
        executeAgentDirective(directive, state, dispatch, bridge);
      }
    }
    if (eventType !== "bridge.error" && eventType !== "error") {
      malformedBridgeEvents = 0;
    }
    if (eventType === "bridge.ready") {
      apply([
        {type: "bridge.status", status: "connected"},
        {type: "status.set", value: "bridge ready"},
      ]);
    }
    if (eventType === "bridge.error") {
      const code = String(typed.code ?? "");
      const message = String(typed.message ?? typed.code ?? "bridge error");
      if (code === "session_detail_failed") {
        const requestId = String(typed.request_id ?? "").trim();
        if (requestId) {
          apply([{type: "session.detail.failed", requestId}]);
        }
      }
      if (reconnectingCodes.has(code)) {
        malformedBridgeEvents = 0;
        requestReconnect(code === "bridge_exit" ? "bridge exited, reconnecting" : "backend offline, retrying", code !== "bridge_exit");
      } else if (code === "invalid_bridge_json") {
        malformedBridgeEvents += 1;
        if (malformedBridgeEvents >= 3) {
          malformedBridgeEvents = 0;
          requestReconnect("bridge unhealthy, reconnecting");
        } else {
          apply([
            {type: "bridge.status", status: "degraded"},
            {type: "status.set", value: `bridge output invalid (${malformedBridgeEvents}/3)`},
          ]);
        }
      } else {
        apply([
          {type: "bridge.status", status: "degraded"},
          {type: "status.set", value: message},
        ]);
      }
    }
    if (eventType === "error") {
      const code = String(typed.code ?? "provider_error");
      const message = String(typed.message ?? typed.code ?? "provider error");
      apply([{type: "status.set", value: `${code}: ${message}`}]);
    }
    if (eventType === "handshake.result") {
      const {provider, model, policy} = handshakeRouteConfigFromEvent(typed, state.routePolicy);
      apply([{
        type: "bridge.config",
        provider,
        model,
        strategy: state.routePolicy.strategy,
      }, ...(policy
        ? [{type: "route.policy.set", policy} as const]
        : [])]);
      malformedBridgeEvents = 0;
      reconnectRequested = false;
      resetHandshakeBackoff?.();
      apply([
        {type: "bridge.status", status: "connected"},
        {type: "status.set", value: "backend connected"},
      ]);
      if (awaitingAuthoritativeResync) {
        awaitingAuthoritativeResync = false;
        resyncPending = true;
        requestAuthoritativeResync(bridge, provider, model, getState().routePolicy.strategy);
        apply([{type: "status.set", value: authoritativeResyncStatus(state.authoritativeSurfaces)}]);
      }
    }
    if (eventType === "command.result") {
      const command = resolveEventCommand(typed);
      const commandName = normalizeCommandName(command);
      apply(commandResultActionsForBridgeEvent(
        typed,
        pendingCommand?.command,
        pendingCommand?.tabId,
      ));
      const commandSnapshotActions = commandRunSnapshotActionsForBridgeEvent(
        typed,
        state.liveRepoPreview,
        state.liveControlPreview,
      );
      apply(commandSnapshotActions);
      const persistedRepoPreview = commandSnapshotActions.find((action) => action.type === "live.repo.set");
      if (persistedRepoPreview?.type === "live.repo.set") {
        persistRepoPreview(persistedRepoPreview.preview, workspaceSnapshotPayloadFromEvent(typed));
      }
      const persistedControlPreview = commandSnapshotActions.find((action) => action.type === "live.control.set");
      if (persistedControlPreview?.type === "live.control.set") {
        persistControlPreview(persistedControlPreview.preview, runtimeSnapshotPayloadFromEvent(typed));
      }
      if (isBareModelCommand(command)) {
        apply([{type: "modelPicker.open", returnTabId: state.uiMode.activeTabId}]);
      }
      const currentRoute = bridgeRouteState(getState());
      requestLiveSnapshots(bridge, currentRoute.provider, currentRoute.model, currentRoute.strategy);
    }
    if (eventType === "workspace.snapshot.result") {
      const actions = snapshotActionsForBridgeEvent(typed, state.liveRepoPreview, state.liveControlPreview);
      const repoIsAuthoritative = workspaceEventHasAuthoritativeRepoSignal(typed);
      apply(repoIsAuthoritative ? [...actions, {type: "surface.truth.mark", surface: "repo"}] : actions);
      if (repoIsAuthoritative && resyncPending && state.bridgeStatus === "connected") {
        const nextAuthority = markAuthoritativeSurface(state.authoritativeSurfaces, "repo");
        apply([{type: "status.set", value: authoritativeResyncStatus(nextAuthority)}]);
        resyncPending = !authoritativeResyncComplete(nextAuthority);
      }
      const persistedRepoPreview = actions.find((action) => action.type === "live.repo.set");
      if (persistedRepoPreview?.type === "live.repo.set") {
        persistRepoPreview(persistedRepoPreview.preview, workspaceSnapshotPayloadFromEvent(typed));
      }
    }
    if (eventType === "permission.decision") {
      const decision = permissionDecisionFromEvent(typed);
      if (decision) {
        const nextApprovalPane = nextApprovalPaneAfterDecision(state.approvalPane, decision);
        apply([
          {type: "approval.decision.set", decision, sourceEventType: eventType},
          {
          type: "tab.replace",
          tabId: "approvals",
          lines: approvalPaneToLines(nextApprovalPane),
          preview: approvalPaneToPreview(nextApprovalPane),
          },
        ]);
        if (decision.decision === "require_approval" && decision.requires_confirmation) {
          apply([
            {type: "status.set", value: `approval required ${decision.tool_name} (${decision.risk})`},
          ]);
        }
        requestPermissionHistory(bridge);
      }
    }
    if (eventType === "permission.history.result") {
      const history = permissionHistoryFromEvent(typed);
      if (history) {
        apply([{type: "surface.truth.mark", surface: "approvals"}]);
        if (resyncPending && state.bridgeStatus === "connected") {
          const nextAuthority = markAuthoritativeSurface(state.authoritativeSurfaces, "approvals");
          apply([{type: "status.set", value: authoritativeResyncStatus(nextAuthority)}]);
          resyncPending = !authoritativeResyncComplete(nextAuthority);
        }
        const approvalPane = approvalPaneFromHistory(history);
        apply([
          {type: "approval.history.set", approvalPane},
          {
          type: "tab.replace",
          tabId: "approvals",
          lines: approvalPaneToLines(approvalPane),
          preview: approvalPaneToPreview(approvalPane),
          },
        ]);
      }
    }
    if (eventType === "permission.resolution") {
      const resolution = permissionResolutionFromEvent(typed);
      if (resolution) {
        const nextApprovalPane = nextApprovalPaneAfterResolution(state.approvalPane, resolution);
        apply([
          {type: "approval.resolution.set", resolution, sourceEventType: eventType},
          {
          type: "tab.replace",
          tabId: "approvals",
          lines: approvalPaneToLines(nextApprovalPane),
          preview: approvalPaneToPreview(nextApprovalPane),
          },
          {type: "status.set", value: `${resolution.resolution} ${resolution.action_id} (${resolution.enforcement_state})`},
        ]);
        requestPermissionHistory(bridge);
      }
    }
    if (eventType === "permission.outcome") {
      const outcome = permissionOutcomeFromEvent(typed);
      if (outcome) {
        const nextApprovalPane = nextApprovalPaneAfterOutcome(state.approvalPane, outcome);
        apply([
          {type: "approval.outcome.set", outcome, sourceEventType: eventType},
          {
          type: "tab.replace",
          tabId: "approvals",
          lines: approvalPaneToLines(nextApprovalPane),
          preview: approvalPaneToPreview(nextApprovalPane),
          },
          {type: "status.set", value: `${outcome.outcome} ${outcome.action_id}`},
        ]);
        requestPermissionHistory(bridge);
      }
    }
    if (eventType === "session.catalog.result") {
      const catalog = sessionCatalogFromEvent(typed);
      if (catalog) {
        apply([{type: "surface.truth.mark", surface: "sessions"}]);
        if (resyncPending && state.bridgeStatus === "connected") {
          const nextAuthority = markAuthoritativeSurface(state.authoritativeSurfaces, "sessions");
          apply([{type: "status.set", value: authoritativeResyncStatus(nextAuthority)}]);
          resyncPending = !authoritativeResyncComplete(nextAuthority);
        }
        const nextSessionPane = nextSessionPaneAfterCatalog(state.sessionPane, catalog);
        const catalogActions: AppAction[] = [
          {type: "session.catalog.set", catalog},
          {
          type: "tab.replace",
          tabId: "sessions",
          lines: sessionPaneToLines(nextSessionPane),
          preview: sessionPaneToPreview(nextSessionPane),
          },
        ];
        const previousSelectedDetail = state.sessionPane.selectedSessionId
          ? state.sessionPane.detailsBySessionId[state.sessionPane.selectedSessionId]
          : undefined;
        const nextSelectedDetail = nextSessionPane.selectedSessionId
          ? nextSessionPane.detailsBySessionId[nextSessionPane.selectedSessionId]
          : undefined;
        if (
          nextSessionPane.selectedSessionId !== state.sessionPane.selectedSessionId ||
          (previousSelectedDetail !== undefined && nextSelectedDetail === undefined)
        ) {
          catalogActions.push({
            type: "session.continuity.set",
            continuity: continuityStateFromSession(state, nextSelectedDetail),
          });
        }
        apply(catalogActions);
        if (
          nextSessionPane.selectedSessionId &&
          !nextSessionPane.detailsBySessionId[nextSessionPane.selectedSessionId]
        ) {
          requestSessionDetail(bridge, dispatch, nextSessionPane.selectedSessionId, true);
        }
      }
    }
    if (eventType === "session.detail.result") {
      const result = sessionDetailResultFromEvent(typed);
      if (result) {
        const nextSessionPane = nextSessionPaneAfterDetailResult(
          state.sessionPane,
          result.requestId,
          result.sessionId,
          result.detail,
        );
        if (!nextSessionPane) {
          return;
        }
        const detail = result.detail;
        const detailActions: AppAction[] = [
          {
            type: "session.detail.received",
            requestId: result.requestId,
            sessionId: result.sessionId,
            detail,
          },
          {
          type: "tab.replace",
          tabId: "sessions",
          lines: sessionPaneToLines(nextSessionPane),
          preview: sessionPaneToPreview(nextSessionPane),
          },
        ];
        if (nextSessionPane.selectedSessionId === detail.session.session_id) {
          const preserveExplicitResume =
            state.sessionContinuity.continuityMode === "resume" &&
            state.sessionContinuity.activeSessionId === detail.session.session_id;
          detailActions.splice(1, 0, {
            type: "session.continuity.set",
            continuity: continuityStateFromSession(state, detail, preserveExplicitResume ? "resume" : "view"),
          });
        }
        apply(detailActions);
      }
    }
    if (eventType === "command.graph.result") {
      dispatch({
        type: "tab.replace",
        tabId: "commands",
        lines: commandGraphToLines(typed),
        preview: commandGraphToPreview(typed),
      });
    }
    if (eventType === "command.registry.result") {
      const existingTab = state.tabs.find((tab) => tab.id === "commands");
      const registry = typeof typed.registry === "object" && typed.registry !== null ? (typed.registry as Record<string, unknown>) : {};
      dispatch({
        type: "tab.replace",
        tabId: "commands",
        lines: (existingTab?.lines.slice(0, 3) ??
          commandGraphToLines({
            graph: {
              count: registry.count ?? 0,
              async_count: 0,
              categories: {},
            },
          })).concat(
          String(typed.content ?? "")
            .split("\n")
            .filter((line) => line.trim().length > 0)
            .slice(3)
            .map((line, index) => ({
              id: `command-registry-${index}-${Date.now()}`,
              kind: "system" as const,
              text: line,
            })),
        ),
        preview: {
          ...(existingTab?.preview ?? {}),
          Commands: String(registry.count ?? 0),
        },
      });
    }
    if (eventType === "ontology.snapshot.result") {
      const content = String(typed.content ?? "");
      dispatch({
        type: "tab.replace",
        tabId: "ontology",
        lines: content
          .split("\n")
          .filter((line) => line.trim().length > 0)
          .map((line, index) => ({
            id: `ontology-${index}-${Date.now()}`,
            kind: "system",
            text: line,
          })),
      });
    }
    if (eventType === "runtime.snapshot.result") {
      const typedPayload = runtimeSnapshotPayloadFromEvent(typed);
      const runtimeIsAuthoritative = typedPayload ? runtimePayloadHasAuthoritativeControlSignal(typedPayload) : false;
      if (runtimeIsAuthoritative) {
        apply([{type: "surface.truth.mark", surface: "control"}]);
      }
      if (runtimeIsAuthoritative && resyncPending && state.bridgeStatus === "connected") {
        const nextAuthority = markAuthoritativeSurface(state.authoritativeSurfaces, "control");
        apply([{type: "status.set", value: authoritativeResyncStatus(nextAuthority)}]);
        resyncPending = !authoritativeResyncComplete(nextAuthority);
      }
      const supervisor = loadSupervisorControlState();
      const content = String(typed.content ?? "");
      const preview = typedPayload ? runtimePayloadToPreview(typedPayload, supervisor) : runtimeSnapshotToPreview(content, supervisor);
      const effectivePreview =
        typedPayload && !runtimeIsAuthoritative
          ? preserveDeferredControlPreview(preview, state.liveControlPreview)
          : preview;
      const synchronizedRepoPreview = synchronizeRepoControlPreviews(state.liveRepoPreview, effectivePreview);
      if (synchronizedRepoPreview) {
        persistRepoPreview(synchronizedRepoPreview);
      }
      persistControlPreview(effectivePreview, typedPayload ?? undefined);
      apply([{
        type: "tab.replace",
        tabId: "control",
        lines: runtimePreviewToLines(effectivePreview),
        preview: effectivePreview,
      }, {
        type: "tab.replace",
        tabId: "runtime",
        lines: runtimePreviewToLines(effectivePreview),
        preview: effectivePreview,
      }, {type: "live.control.set", preview: effectivePreview},
      ...(synchronizedRepoPreview ? [{type: "live.repo.set", preview: synchronizedRepoPreview} as const] : [])]);
    }
    if (eventType === "model.policy.result") {
      const suppressRouteStatus = resyncPending && state.bridgeStatus === "connected";
      apply([{type: "surface.truth.mark", surface: "models"}]);
      if (resyncPending && state.bridgeStatus === "connected") {
        const nextAuthority = markAuthoritativeSurface(state.authoritativeSurfaces, "models");
        apply([{type: "status.set", value: authoritativeResyncStatus(nextAuthority)}]);
        resyncPending = !authoritativeResyncComplete(nextAuthority);
      }
      const routingPayload = routingDecisionPayloadFromEvent(typed);
      const policyRecord =
        typeof typed.policy === "object" && typed.policy !== null ? (typed.policy as Record<string, unknown>) : undefined;
      const nextRoutePolicy = routePolicyFromValue(routingPayload ?? policyRecord ?? typed, state.routePolicy);
      const activeChoice = nextRoutePolicy.targets.find(
        (choice) => choice.provider === nextRoutePolicy.provider && choice.model === nextRoutePolicy.model,
      );
      apply([{
        type: "route.policy.set",
        policy: nextRoutePolicy,
      }, {
        type: "tab.replace",
        tabId: "models",
        lines: modelPolicyToLines(routingPayload ? {payload: routingPayload} : typed),
        preview: modelPolicyToPreview(routingPayload ? {payload: routingPayload} : typed),
      }]);
      if (activeChoice) {
        const actions: AppAction[] = [{
          type: "bridge.config",
          provider: activeChoice.provider,
          model: activeChoice.model,
          strategy: nextRoutePolicy.strategy,
        }];
        if (!suppressRouteStatus) {
          actions.push({
            type: "status.set",
            value: activeChoice.selectable ? `route confirmed -> ${routeLabel(nextRoutePolicy)}` : `route constrained -> ${routeSummary(nextRoutePolicy)}`,
          });
        }
        apply(actions);
      }
    }
    if (eventType === "agent.routes.result") {
      apply([{type: "surface.truth.mark", surface: "agents"}]);
      if (resyncPending && state.bridgeStatus === "connected") {
        const nextAuthority = markAuthoritativeSurface(state.authoritativeSurfaces, "agents");
        apply([{type: "status.set", value: authoritativeResyncStatus(nextAuthority)}]);
        resyncPending = !authoritativeResyncComplete(nextAuthority);
      }
      const routesPayload = agentRoutesPayloadFromEvent(typed);
      apply([{
        type: "tab.replace",
        tabId: "agents",
        lines: agentRoutesToLines(routesPayload ? {payload: routesPayload} : typed),
        preview: agentRoutesToPreview(routesPayload ? {payload: routesPayload} : typed),
      }]);
    }
    if (eventType === "evolution.surface.result") {
      dispatch({
        type: "tab.replace",
        tabId: "evolution",
        lines: evolutionSurfaceToLines(typed),
        preview: evolutionSurfaceToPreview(typed),
      });
    }
    if (eventType === "session.bootstrap.result") {
      const requestId = String(typed.request_id ?? "");
      const pending = pendingBootstraps.current[requestId];
      dispatch({
        type: "tab.replace",
        tabId: "mission",
        lines: sessionBootstrapToLines(typed),
        preview: sessionBootstrapToPreview(typed),
      });
      const actions = snapshotActionsForBridgeEvent(typed, state.liveRepoPreview, state.liveControlPreview);
      actions.forEach((action) => dispatch(action));
      const persistedRepoPreview = actions.find((action) => action.type === "live.repo.set");
      if (persistedRepoPreview?.type === "live.repo.set") {
        persistRepoPreview(persistedRepoPreview.preview, workspaceSnapshotPayloadFromEvent(typed));
      }
      const persistedControlPreview = actions.find((action) => action.type === "live.control.set");
      if (persistedControlPreview?.type === "live.control.set") {
        persistControlPreview(persistedControlPreview.preview, runtimeSnapshotPayloadFromEvent(typed));
      }

      const selectedProvider = String(typed.selected_provider ?? pending?.provider ?? state.routePolicy.provider);
      const selectedModel = String(typed.selected_model ?? pending?.model ?? state.routePolicy.model);
      const selectedStrategy = String(typed.routing_strategy ?? state.routePolicy.strategy ?? "responsive");
      dispatch({type: "bridge.config", provider: selectedProvider, model: selectedModel, strategy: selectedStrategy});

      // Ctrl-C can arrive before bootstrap returns. That is a real cancelled
      // turn boundary: consume the informational bootstrap result, but never
      // launch the provider or auto-execute an inferred intent afterward.
      if (pending?.cancelled) {
        delete pendingBootstraps.current[requestId];
        dispatch({type: "status.set", value: "cancelled before provider start"});
        return;
      }

      const intent = typed.intent as Record<string, unknown> | undefined;
      if (intent && String(intent.kind ?? "") === "command" && Boolean(intent.auto_execute)) {
        const command = `/${String(intent.command ?? "")}`;
        const commandIntent = commandIntentFromBootstrapIntent(intent, command);
        const tabId = resolveCommandTargetPane(commandIntent, commandTargetTab(command));
        dispatch({type: "tab.activate", tabId});
        markPendingCommandStream(pendingCommandStream, commandIntent);
        bridge.send("command.run", commandIntent);
        dispatch({type: "status.set", value: `intent ${command} -> ${tabId}`});
      } else if (intent && String(intent.kind ?? "") === "model_switch") {
        bridge.send("action.run", {
          action_type: "model.set",
          provider: selectedProvider,
          model: selectedModel,
          strategy: String(intent.strategy ?? selectedStrategy),
        });
        dispatch({
          type: "bridge.config",
          provider: selectedProvider,
          model: selectedModel,
          strategy: String(intent.strategy ?? selectedStrategy),
        });
        dispatch({
          type: "status.set",
          value: `model route -> ${selectedProvider}:${selectedModel} (${String(intent.strategy ?? selectedStrategy)})`,
        });
        dispatch({
          type: "tab.append",
          tabId: "chat",
          lines: [
            {
              id: `model-switch-${Date.now()}`,
              kind: "assistant",
              text: `Switched route to ${selectedProvider}:${selectedModel} (${String(intent.strategy ?? selectedStrategy)}).`,
            },
          ],
        });
      } else if (intent && String(intent.kind ?? "") === "agent") {
        dispatch({type: "tab.activate", tabId: "agents"});
        bridge.send("agent.routes");
        dispatch({type: "status.set", value: "agent routing surface ready"});
        if (pending) {
          startSession({
            provider: selectedProvider,
            model: selectedModel,
            prompt: pending.prompt,
            messages: pending.messages,
            resume_session_id: pending.resumeSessionId,
            bootstrap: typed,
            system_prompt: String(typed.system_prompt ?? ""),
          });
        }
      } else if (intent && String(intent.kind ?? "") === "evolution") {
        dispatch({type: "tab.activate", tabId: "evolution"});
        bridge.send("evolution.surface");
        dispatch({type: "status.set", value: "evolution surface ready"});
        if (pending) {
          startSession({
            provider: selectedProvider,
            model: selectedModel,
            prompt: pending.prompt,
            messages: pending.messages,
            resume_session_id: pending.resumeSessionId,
            bootstrap: typed,
            system_prompt: String(typed.system_prompt ?? ""),
          });
        }
      } else if (pending) {
        startSession({
          provider: selectedProvider,
          model: selectedModel,
          prompt: pending.prompt,
          messages: pending.messages,
          resume_session_id: pending.resumeSessionId,
          bootstrap: typed,
          system_prompt: String(typed.system_prompt ?? ""),
        });
        dispatch({type: "status.set", value: `running ${selectedProvider}:${selectedModel}`});
      }
      delete pendingBootstraps.current[requestId];
    }
    if (eventType === "session_end") {
      const currentRoute = bridgeRouteState(getState());
      requestLiveSnapshots(bridge, currentRoute.provider, currentRoute.model, currentRoute.strategy);
      requestSessionCatalog(bridge);
    }
    if (eventType === "action.result") {
      const actionType = resolveEventActionType(typed);
      const command = resolveEventCommand(typed);
      if (actionType === "command.run") {
        clearPendingCommandStream(pendingCommandStream);
        actionResultActionsForBridgeEvent(
          typed,
          pendingCommand?.command,
          pendingCommand?.tabId,
        ).forEach((action) => dispatch(action));
        if (isBareModelCommand(command)) {
          dispatch({type: "modelPicker.open", returnTabId: state.uiMode.activeTabId});
        }
      } else {
        actionResultActionsForBridgeEvent(typed).forEach((action) => dispatch(action));
      }
      const pane =
        actionType === "command.run"
          ? resolveSlashCommandResultTabId(typed, pendingCommand?.command, pendingCommand?.tabId)
          : String(typed.target_pane ?? "control");
      const commandRunSnapshotActions = commandRunSnapshotActionsForBridgeEvent(
        typed,
        state.liveRepoPreview,
        state.liveControlPreview,
      );
      commandRunSnapshotActions.forEach((action) => dispatch(action));
      const surfaceRefreshActions = surfaceRefreshActionsForBridgeEvent(
        typed,
        state.liveRepoPreview,
        state.liveControlPreview,
        state.sessionPane,
      );
      surfaceRefreshActions.forEach((action) => dispatch(action));
      if (actionType === "surface.refresh") {
        const surface = String(typed.surface ?? "").trim().toLowerCase();
        const workspaceIsAuthoritative = workspaceEventHasAuthoritativeRepoSignal(typed);
        const runtimePayload = runtimeSnapshotPayloadFromEvent(typed);
        const runtimeIsAuthoritative = Boolean(
          runtimePayload && runtimePayloadHasAuthoritativeControlSignal(runtimePayload),
        );
        if ((surface === "repo" || surface === "workspace") && workspaceIsAuthoritative) {
          dispatch({type: "surface.truth.mark", surface: "repo"});
          if (resyncPending && state.bridgeStatus === "connected") {
            const nextAuthority = markAuthoritativeSurface(state.authoritativeSurfaces, "repo");
            dispatch({type: "status.set", value: authoritativeResyncStatus(nextAuthority)});
            resyncPending = !authoritativeResyncComplete(nextAuthority);
          }
        }
        if ((surface === "control" || surface === "runtime") && runtimeIsAuthoritative) {
          dispatch({type: "surface.truth.mark", surface: "control"});
          if (resyncPending && state.bridgeStatus === "connected") {
            const nextAuthority = markAuthoritativeSurface(state.authoritativeSurfaces, "control");
            dispatch({type: "status.set", value: authoritativeResyncStatus(nextAuthority)});
            resyncPending = !authoritativeResyncComplete(nextAuthority);
          }
        }
        if (surface === "sessions" || surface === "session") {
          dispatch({type: "surface.truth.mark", surface: "sessions"});
          if (resyncPending && state.bridgeStatus === "connected") {
            const nextAuthority = markAuthoritativeSurface(state.authoritativeSurfaces, "sessions");
            dispatch({type: "status.set", value: authoritativeResyncStatus(nextAuthority)});
            resyncPending = !authoritativeResyncComplete(nextAuthority);
          }
        }
        if (surface === "models" || surface === "model") {
          dispatch({type: "surface.truth.mark", surface: "models"});
          if (resyncPending && state.bridgeStatus === "connected") {
            const nextAuthority = markAuthoritativeSurface(state.authoritativeSurfaces, "models");
            dispatch({type: "status.set", value: authoritativeResyncStatus(nextAuthority)});
            resyncPending = !authoritativeResyncComplete(nextAuthority);
          }
        }
        if (surface === "agents" || surface === "agent") {
          dispatch({type: "surface.truth.mark", surface: "agents"});
          if (resyncPending && state.bridgeStatus === "connected") {
            const nextAuthority = markAuthoritativeSurface(state.authoritativeSurfaces, "agents");
            dispatch({type: "status.set", value: authoritativeResyncStatus(nextAuthority)});
            resyncPending = !authoritativeResyncComplete(nextAuthority);
          }
        }
      }
      const persistedRepoPreview = [...commandRunSnapshotActions, ...surfaceRefreshActions].find(
        (action) => action.type === "live.repo.set",
      );
      if (persistedRepoPreview?.type === "live.repo.set") {
        persistRepoPreview(persistedRepoPreview.preview, workspaceSnapshotPayloadFromEvent(typed));
      }
      const persistedControlPreview = [...commandRunSnapshotActions, ...surfaceRefreshActions].find(
        (action) => action.type === "live.control.set",
      );
      if (persistedControlPreview?.type === "live.control.set") {
        persistControlPreview(persistedControlPreview.preview, runtimeSnapshotPayloadFromEvent(typed));
      }
      const output = resolveEventOutput(typed).trim();
      const policy =
        typeof typed.policy === "object" && typed.policy !== null ? (typed.policy as Record<string, unknown>) : null;
      const routingPayload = routingDecisionPayloadFromEvent(typed);
      let refreshProvider = getState().routePolicy.provider;
      let refreshModel = getState().routePolicy.model;
      let refreshStrategy = getState().routePolicy.strategy;
      if (policy || routingPayload) {
        const nextRoutePolicy = routePolicyFromValue(routingPayload ?? policy, getState().routePolicy);
        refreshProvider = nextRoutePolicy.provider;
        refreshModel = nextRoutePolicy.model;
        refreshStrategy = nextRoutePolicy.strategy;
        dispatch({
          type: "bridge.config",
          provider: refreshProvider,
          model: refreshModel,
          strategy: refreshStrategy,
        });
        dispatch({type: "route.policy.set", policy: nextRoutePolicy});
        dispatch({
          type: "tab.replace",
          tabId: "models",
          lines: modelPolicyToLines(routingPayload ? {payload: routingPayload} : {policy}),
          preview: modelPolicyToPreview(routingPayload ? {payload: routingPayload} : {policy}),
        });
      }
      if (
        output &&
        commandRunSnapshotActions.length === 0 &&
        surfaceRefreshActions.length === 0 &&
        !(pane === "models" && (policy || routingPayload)) &&
        !(actionType === "command.run" && shouldSuppressDuplicatePendingCommandPatch(typed, pendingCommand))
      ) {
        dispatch({
          type: "tab.append",
          tabId: pane,
          lines: [{id: `action-${Date.now()}`, kind: "system", text: output}],
        });
      }
      if (actionType !== "command.run" && !(actionType === "surface.refresh" && resyncPending)) {
        dispatch({type: "status.set", value: String(typed.summary ?? "action applied")});
      }
      requestLiveSnapshots(bridge, refreshProvider, refreshModel, refreshStrategy);
    }

    if (eventType === "command.result") {
      clearPendingCommandStream(pendingCommandStream);
    }

    if (eventType === "text_delta" && pendingCommand && !shouldSuppressPendingCommandStreamOutput(pendingCommand)) {
      dispatch({type: "tab.activate", tabId: pendingCommand.tabId});
    }

    if (eventType === "text_complete" && pendingCommand) {
      const output = normalizeCommandStreamText(typed.content);
      if (output) {
        pendingCommand.lastCompletedText = output;
        const streamSnapshotActions = snapshotActionsForPendingCommandStream(
          pendingCommand,
          output,
          state.liveRepoPreview,
          state.liveControlPreview,
        );
        if (!shouldSuppressPendingCommandStreamOutput(pendingCommand)) {
          dispatch({type: "tab.activate", tabId: pendingCommand.tabId});
          if (streamSnapshotActions.length > 0) {
            queueAppActions(dispatch, streamSnapshotActions);
            const persistedRepoPreview = streamSnapshotActions.find((action) => action.type === "live.repo.set");
            if (persistedRepoPreview?.type === "live.repo.set") {
              persistRepoPreview(persistedRepoPreview.preview);
            }
            const persistedControlPreview = streamSnapshotActions.find((action) => action.type === "live.control.set");
            if (persistedControlPreview?.type === "live.control.set") {
              persistControlPreview(persistedControlPreview.preview);
            }
          } else {
            dispatch({
              type: "tab.append",
              tabId: pendingCommand.tabId,
              lines: [{id: `command-stream-${Date.now()}`, kind: "system", text: output}],
            });
          }
        }
      }
    }

    const suppressChatPatch =
      (eventType === "text_delta" || eventType === "text_complete") && Boolean(pendingCommand);
    const suppressDuplicateCommandPatch = shouldSuppressDuplicatePendingCommandPatch(typed, pendingCommand);
    const suppressDuplicateCompletedAssistantPatch = isDuplicateCompletedAssistantPatch(getState(), typed);
    const canonicalLogOwnsTranscriptPatch =
      canonicalEvents.length > 0 &&
      eventType !== "text_delta" &&
      eventType !== "text_complete" &&
      eventType !== "command.result";
    const patches =
      suppressChatPatch || suppressDuplicateCommandPatch || suppressDuplicateCompletedAssistantPatch || canonicalLogOwnsTranscriptPatch
        ? []
        : eventToTabPatch(typed);
    for (const patch of patches) {
      dispatch({type: "tab.append", tabId: patch.tabId, lines: patch.lines});
    }
  };
}

export function surfaceRefreshActionsForBridgeEvent(
  event: BridgeEvent,
  liveRepoPreview?: TabPreview,
  liveControlPreview?: TabPreview,
  sessionPane?: SessionPaneState,
  supervisor = loadSupervisorControlState(),
): AppAction[] {
  const typed = event as Record<string, unknown>;
  if (String(typed.type ?? "") !== "action.result" || String(typed.action_type ?? "") !== "surface.refresh") {
    return [];
  }

  const surface = String(typed.surface ?? typed.target_pane ?? "").trim().toLowerCase();
  if (surface === "sessions" || surface === "session") {
    const catalog = sessionCatalogFromEvent(typed);
    if (catalog) {
      const nextSessionPane = nextSessionPaneAfterCatalog(
        sessionPane ?? {
          selectionProvenance: "follow_latest",
          detailsBySessionId: {},
          pendingDetailRequestsBySessionId: {},
        },
        catalog,
      );
      return [
        {type: "session.catalog.set", catalog},
        {
          type: "tab.replace",
          tabId: "sessions",
          lines: sessionPaneToLines(nextSessionPane),
          preview: sessionPaneToPreview(nextSessionPane),
        },
      ];
    }
  }
  if (surface === "agents" || surface === "agent") {
    const routesPayload = agentRoutesPayloadFromEvent(typed);
    if (routesPayload) {
      return [
        {
          type: "tab.replace",
          tabId: "agents",
          lines: agentRoutesToLines({payload: routesPayload}),
          preview: agentRoutesToPreview({payload: routesPayload}),
        },
      ];
    }
  }

  if (surface === "repo" || surface === "workspace") {
    const workspacePayload = workspaceSnapshotPayloadFromEvent(typed);
    const output = resolveEventOutput(typed);
    if (!workspacePayload && !output.trim()) {
      return [];
    }
    const preview = workspacePayload ? workspacePayloadToPreview(workspacePayload) : workspaceSnapshotToPreview(output);
    const synchronizedPreview = synchronizeRepoControlPreviews(preview, liveControlPreview);
    return [
      {
        type: "tab.replace",
        tabId: "repo",
        lines: workspacePreviewToLines(synchronizedPreview ?? preview),
        preview: synchronizedPreview ?? preview,
      },
      {type: "live.repo.set", preview: synchronizedPreview ?? preview},
    ];
  }

  if (surface === "control" || surface === "runtime") {
    const typedPayload = runtimeSnapshotPayloadFromEvent(typed);
    const output = resolveEventOutput(typed);
    if (!typedPayload && !output.trim()) {
      return [];
    }
    const preview = typedPayload ? runtimePayloadToPreview(typedPayload, supervisor) : runtimeSnapshotToPreview(output, supervisor);
    const synchronizedRepoPreview = synchronizeRepoControlPreviews(liveRepoPreview, preview);
    return [
      {
        type: "tab.replace",
        tabId: "control",
        lines: runtimePreviewToLines(preview),
        preview,
      },
      {
        type: "tab.replace",
        tabId: "runtime",
        lines: runtimePreviewToLines(preview),
        preview,
      },
      {type: "live.control.set", preview},
      ...(synchronizedRepoPreview ? [{type: "live.repo.set", preview: synchronizedRepoPreview} as const] : []),
    ];
  }

  const output = resolveEventOutput(typed);
  if (!output.trim()) {
    return [];
  }

  return [];
}

export function paneActionStartActions(action: {summary: string; payload: Record<string, unknown>} | undefined): AppAction[] {
  const commandRunEvent = commandRunEventFromPaneAction(action);
  if (commandRunEvent) {
    return slashCommandStartActions(commandRunEvent, "command");
  }

  if (!action) {
    return [];
  }

  if (action.summary === "focus selected approval") {
    return [{type: "status.set", value: action.summary}];
  }

  return [{type: "status.set", value: action.summary}];
}

export function App(): React.ReactElement {
  const {exit} = useApp();
  const [state, dispatch] = useReducer(reduceApp, initialState, createInitialAppState);
  // FACE-1 regression fix: ink re-lays-out the EXISTING tree on stdout resize,
  // but width-derived React props (zen 100-col clamp, compactShell, window
  // sizes) stay stale until the next state event — offline that is the 15s
  // probe, so a live 120->80 resize garbled for seconds. This tick forces a
  // React re-render the moment the terminal resizes.
  const [, setViewportTick] = useState(0);
  // FACE-3 the scroll: the telemetry drawer is view-local — never persisted,
  // reset each boot, meaningless outside the scroll face.
  const [scrollDrawerOpen, setScrollDrawerOpen] = useState(false);
  useEffect(() => {
    const handleResize = (): void => {
      setViewportTick((tick) => tick + 1);
    };
    process.stdout.on("resize", handleResize);
    return () => {
      process.stdout.off("resize", handleResize);
    };
  }, []);

  const activeTab = state.tabs.find((tab) => tab.id === state.uiMode.activeTabId) ?? state.tabs[0];
  const terminalWidth = (process.stdout.columns ?? Number(process.env.COLUMNS ?? "0")) || 120;
  const terminalHeight = (process.stdout.rows ?? Number(process.env.LINES ?? "0")) || 30;
  const compactShell = terminalWidth <= 90;
  // F-021: offsets re-derived from measured boot chrome — compact: header 4 +
  // summary 1 + tab bar 1 + pane chrome 3 + composer 3 + footer 5 = 17; wide
  // chrome measures ~22-24 but the offset stays at 20 so the expanded-trace
  // anchor rows stay inside the end-anchored window at 100x30 (F-172 check).
  const paneWindowSize = Math.max(MIN_SCROLL_WINDOW_SIZE, terminalHeight - (compactShell ? 17 : 20));
  // Navigator rail (cockpit only): a fixed-width right column that mirrors the
  // sidebar's clip-don't-squeeze discipline so it can only partition WIDTH,
  // never inflate height (F-163 preserved by construction). It is the FIRST
  // thing to yield — suppressed under compactShell and auto-hidden whenever the
  // active pane would drop below 48 cols.
  const railWidth = Math.min(40, Math.max(28, Math.round(terminalWidth * 0.3)));
  const railSidebarOn = state.uiMode.sidebarVisible === "visible" && !compactShell;
  const railVisible =
    state.uiMode.railVisible &&
    !compactShell &&
    terminalWidth - railWidth - (railSidebarOn ? 34 : 0) >= 48;
  const railChatLines = displayedTranscriptLinesForTab(state.tabs.find((tab) => tab.id === "chat"), state);
  const railWindowSize = Math.max(MIN_SCROLL_WINDOW_SIZE, paneWindowSize - 3);
  const outline = useMemo(() => outlineFromTabs(state.tabs), [state.tabs]);
  const modelChoices = selectableRouteTargets(state.routePolicy);
  const displayedTranscriptLines = displayedTranscriptLinesForTab(activeTab, state);
  const transcriptMeta = transcriptMetaForTab(activeTab);
  // Display source of truth: name whichever model actually answered the latest
  // turn, falling back to the configured route before any turn has run.
  const liveRouteLabel = latestChatTurnRoute(state.executionEventLog) ?? routeLabel(state.routePolicy);
  const operatorSummaryItems = buildOperatorSummaryItems(state);
  const activeScrollOffset = Math.min(
    state.paneScrollOffsets[activeTab?.id ?? ""] ?? 0,
    scrollMaxOffsetForTab(activeTab, state, paneWindowSize),
  );
  const stateRef = useRef(state);
  const cancellationRequestRef = useRef<{requestId: string; cancelRequestId: string} | null>(null);
  const pendingBootstraps = useRef<Record<string, PendingBootstrap>>({});
  const bootstrapCancellationGuardRef = useRef(0);
  // F-157: prompts submitted while the bridge is offline wait here; the connect
  // effect below drains the queue — every entry is dispatched or marked failed.
  const queuedOfflinePrompts = useRef<Array<{
    queueId: string;
    prompt: string;
    provider: string;
    model: string;
    strategy: string;
    activeTabId: string;
    messages: Array<{role: "user" | "assistant" | "system"; content: string}>;
    resumeSessionId?: string;
  }>>([]);
  const queuedOfflineCounter = useRef(0);
  // F-158: slash commands submitted while the bridge is offline wait here; the connect
  // effect drains them — every queued command is dispatched (command.run) or marked failed.
  const queuedOfflineCommands = useRef<Array<{queueId: string; command: string}>>([]);
  const pendingCommandStream = useRef<PendingCommandStream | null>(null);
  const bridgeRef = useRef<DharmaBridge | null>(null);
  const handshakeBackoffRef = useRef({attempt: 0, nextAllowedAt: 0});
  const persistTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const liveSnapshotRequestRef = useRef(0);

  function requestLiveSnapshotsIfStale(provider: string, model: string, strategy: string, minIntervalMs = 900): void {
    const now = Date.now();
    if (now - liveSnapshotRequestRef.current < minIntervalMs) {
      return;
    }
    liveSnapshotRequestRef.current = now;
    requestLiveSnapshots(bridge, provider, model, strategy);
  }

  function requestHandshake(reason: "initial" | "reconnect" | "probe"): void {
    const bridgeInstance = bridgeRef.current;
    if (!bridgeInstance) {
      return;
    }
    const now = Date.now();
    const meta = handshakeBackoffRef.current;
    if (reason === "initial") {
      meta.attempt = 0;
      meta.nextAllowedAt = now + 1_000;
      bridgeInstance.send("handshake");
      return;
    }
    if (now < meta.nextAllowedAt) {
      return;
    }
    meta.attempt += 1;
    meta.nextAllowedAt = now + handshakeBackoffDelayMs(meta.attempt);
    bridgeInstance.send("handshake");
  }

  function resetHandshakeBackoff(): void {
    handshakeBackoffRef.current = {attempt: 0, nextAllowedAt: 0};
  }

  const bridge = useMemo(
    () => {
      let onEvent: (event: BridgeEvent) => void = () => undefined;
      const instance = new DharmaBridge((event: BridgeEvent) => onEvent(event));
      bridgeRef.current = instance;
      onEvent = createBridgeEventHandler({
        dispatch,
        getState: () => stateRef.current,
        bridge: instance,
        pendingBootstraps,
        pendingCommandStream,
        requestHandshake: (reason) => requestHandshake(reason),
        resetHandshakeBackoff,
      });
      return instance;
    },
    [],
  );

  useEffect(() => {
    requestHandshake("initial");
    const intervalId = setInterval(() => {
      if (stateRef.current.bridgeStatus === "connected") {
        requestAuthoritativeResync(
          bridge,
          stateRef.current.routePolicy.provider,
          stateRef.current.routePolicy.model,
          stateRef.current.routePolicy.strategy,
        );
      } else {
        requestHandshake("probe");
      }
    }, SNAPSHOT_REFRESH_INTERVAL_MS);
    return () => {
      clearInterval(intervalId);
      bridge.close();
    };
  }, [bridge]);

  useEffect(() => {
    if (state.bridgeStatus !== "connected" || authoritativeResyncComplete(state.authoritativeSurfaces)) {
      return;
    }
    const repairId = setTimeout(() => {
      requestMissingAuthoritativeSurfaces(
        bridge,
        stateRef.current.routePolicy.provider,
        stateRef.current.routePolicy.model,
        stateRef.current.routePolicy.strategy,
        stateRef.current.authoritativeSurfaces,
      );
    }, 3_000);
    return () => {
      clearTimeout(repairId);
    };
  }, [bridge, state.bridgeStatus, state.authoritativeSurfaces]);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    if (state.activeTurn.phase !== "cancelling") {
      cancellationRequestRef.current = null;
    }
  }, [state.activeTurn]);

  // F-157: bridge connect drains the offline prompt queue — each queued turn is
  // dispatched (session.bootstrap) or marked failed; no third silent state.
  // F-158: queued offline slash commands drain the same way via command.run.
  useEffect(() => {
    if (
      state.bridgeStatus !== "connected" ||
      (queuedOfflinePrompts.current.length === 0 && queuedOfflineCommands.current.length === 0)
    ) {
      return;
    }
    const commandEntries = queuedOfflineCommands.current.splice(0, queuedOfflineCommands.current.length);
    for (const entry of commandEntries) {
      try {
        markPendingCommandStream(pendingCommandStream, {command: entry.command});
        bridge.send("command.run", {command: entry.command});
        queueAppActions(dispatch, [
          {type: "execution.events.ingest", events: [queuedPromptExecutionEvent(entry.queueId, "dispatched")]},
        ]);
      } catch {
        queueAppActions(dispatch, [
          {type: "execution.events.ingest", events: [queuedPromptExecutionEvent(entry.queueId, "failed")]},
        ]);
      }
    }
    if (commandEntries.length > 0) {
      dispatch({
        type: "status.set",
        value: `dispatched ${commandEntries.length} queued command${commandEntries.length === 1 ? "" : "s"}`,
      });
    }
    if (queuedOfflinePrompts.current.length === 0) {
      return;
    }
    const entries = queuedOfflinePrompts.current.splice(0, queuedOfflinePrompts.current.length);
    for (const entry of entries) {
      try {
        const requestId = bridge.send("session.bootstrap", {
          provider: entry.provider,
          model: entry.model,
          strategy: entry.strategy,
          prompt: entry.prompt,
          active_tab: entry.activeTabId,
          resume_session_id: entry.resumeSessionId,
        });
        pendingBootstraps.current[requestId] = {
          prompt: entry.prompt,
          provider: entry.provider,
          model: entry.model,
          messages: entry.messages,
          resumeSessionId: entry.resumeSessionId,
        };
        queueAppActions(dispatch, [
          {type: "execution.events.ingest", events: [queuedPromptExecutionEvent(entry.queueId, "dispatched")]},
        ]);
      } catch {
        queueAppActions(dispatch, [
          {type: "execution.events.ingest", events: [queuedPromptExecutionEvent(entry.queueId, "failed")]},
        ]);
      }
    }
    dispatch({type: "status.set", value: `dispatched ${entries.length} queued prompt${entries.length === 1 ? "" : "s"}`});
  }, [bridge, state.bridgeStatus]);

  useEffect(() => {
    const current = state.sessionContinuity;
    if (current.continuityMode !== "resume") {
      return;
    }
    const selectedSessionId = state.sessionPane.selectedSessionId;
    const selectedDetail = selectedSessionId
      ? state.sessionPane.detailsBySessionId[selectedSessionId]
      : undefined;
    const preserveResume = Boolean(selectedSessionId && selectedSessionId === current.activeSessionId);
    const nextContinuity = continuityStateFromSession(
      state,
      selectedDetail,
      preserveResume ? "resume" : "view",
    );
    if (
      current.activeSessionId === nextContinuity.activeSessionId &&
      current.resumeSessionId === nextContinuity.resumeSessionId &&
      current.activeRouteId === nextContinuity.activeRouteId &&
      current.continuityMode === nextContinuity.continuityMode &&
      current.compactedSummary === nextContinuity.compactedSummary &&
      JSON.stringify(current.compactionPolicy) === JSON.stringify(nextContinuity.compactionPolicy) &&
      JSON.stringify(current.boundedHistory) === JSON.stringify(nextContinuity.boundedHistory)
    ) {
      return;
    }
    dispatch({type: "session.continuity.set", continuity: nextContinuity});
  }, [
    state.sessionContinuity.continuityMode,
    state.sessionContinuity.activeSessionId,
    state.sessionPane.selectedSessionId,
    state.sessionPane.detailsBySessionId,
    state.routePolicy.routeId,
  ]);

  useEffect(() => {
    if (persistTimeoutRef.current) {
      clearTimeout(persistTimeoutRef.current);
    }
    persistTimeoutRef.current = setTimeout(() => {
      saveStoredState(state);
      persistTimeoutRef.current = null;
    }, 120);
    return () => {
      if (persistTimeoutRef.current) {
        clearTimeout(persistTimeoutRef.current);
        persistTimeoutRef.current = null;
      }
    };
  }, [state.uiMode.sidebarVisible, state.uiMode.sidebarMode, outline]);

  useEffect(() => {
    dispatch({type: "ui.compact.set", compact: compactShell});
  }, [compactShell]);

  // F-065/F-066 + operator word 2026-06-12: layout, pane, model, and tour
  // intents resolve LOCALLY (offline-capable, instant) with a full transcript
  // turn — the composer steers the UI in plain language or via slash commands.
  function runLocalUiAction(submitted: string, intent: UiIntent): void {
    // The confirmation rides the SAME assistant-event canonicalization as real
    // backend answers (F-173), so steering the UI reads like a conversation:
    // you ask, the Helm answers, the turn closes ✓ — multi-line tour included.
    const respond = (message: string, activateTabId = "chat"): void => {
      queueAppActions(dispatch, [
        {
          type: "execution.events.ingest",
          events: [
            userPromptExecutionEvent(submitted),
            ...canonicalEventsFromBridgeEvent({
              type: "assistant",
              request_id: `local-ui-${Date.now()}`,
              message,
            }),
            localCommandResultExecutionEvent(submitted, message.split("\n")[0] ?? message),
          ],
        },
        {type: "tab.activate", tabId: activateTabId},
        {type: "status.set", value: message.split("\n")[0] ?? message},
      ]);
    };
    if (intent.kind === "layout") {
      dispatch({type: "layout.mode.set", mode: intent.mode});
      respond(
        intent.mode === "zen"
          ? "Zen — just the conversation. F2 or /cockpit brings the panel back."
          : intent.mode === "scroll"
            ? "The scroll — reading mode. ^D peeks telemetry · F2 or /zen returns."
            : "Cockpit — full panel. F2 or /zen returns to the quiet view.",
      );
      return;
    }
    if (intent.kind === "pane") {
      respond(
        `Opened ${intent.title}. Tab cycles panes · ^K opens the switcher · say "open the chat pane" to come back.`,
        intent.tabId,
      );
      return;
    }
    if (intent.kind === "model") {
      if (stateRef.current.bridgeStatus !== "connected") {
        respond(`Route switch needs the backend — it is ${stateRef.current.bridgeStatus}. Try again once connected.`);
        return;
      }
      bridge.send("action.run", {
        action_type: "model.set",
        provider: intent.target.provider,
        model: intent.target.model,
        strategy: stateRef.current.routePolicy.strategy,
      });
      respond(`Requesting route -> ${intent.target.provider}:${intent.target.model}`);
      return;
    }
    if (intent.kind === "model_unknown") {
      const menu = selectableRouteTargets(stateRef.current.routePolicy)
        .map((target) => `  ${target.provider}:${target.model}`)
        .join("\n");
      respond(
        `No route matches "${intent.query}". Available right now:\n${menu || "  (none — backend offline)"}\nSay "switch to <one of these>" or /model for the picker.`,
      );
      return;
    }
    if (intent.kind === "rail") {
      const next = intent.on === "toggle" ? !stateRef.current.uiMode.railVisible : intent.on;
      // The rail lives only in the cockpit face — turning it on brings the
      // operator there so they can see it beside the Helm's panes.
      if (next && stateRef.current.uiMode.layoutMode !== "cockpit") {
        dispatch({type: "layout.mode.set", mode: "cockpit"});
      }
      dispatch({type: "rail.set", visible: next});
      respond(
        next
          ? "Navigator docked — chat rides the right rail while the Helm's panes stay visible. Say \"undock\" or /rail to hide it."
          : "Navigator undocked. /rail or \"dock the chat\" brings it back.",
      );
      return;
    }
    // The tour opens in its own isolated overlay box — never inline transcript
    // text (operator word 2026-06-16).
    if (intent.kind === "tour") {
      dispatch({type: "tour.open"});
      return;
    }
  }

  function localUiSlashIntent(submitted: string): UiIntent | null {
    const text = submitted.trim().toLowerCase();
    if (text === "/zen") return {kind: "layout", mode: "zen"};
    // FACE-2: /post is the command-post alias for /cockpit.
    if (text === "/cockpit" || text === "/post") return {kind: "layout", mode: "cockpit"};
    // FACE-3: the reading-first manuscript face.
    if (text === "/scroll") return {kind: "layout", mode: "scroll"};
    if (text === "/tour") return {kind: "tour"};
    // Navigator rail: /navigator and /rail toggle the persistent chat rail.
    if (text === "/navigator" || text === "/rail") return {kind: "rail", on: "toggle"};
    return null;
  }

  function requestActiveTurnCancellation(source: "command" | "shortcut"): TurnCancellationDecision["kind"] {
    const decision = decideTurnCancellation(stateRef.current.activeTurn);
    if (decision.kind === "idle") {
      const pendingEntry = Object.entries(pendingBootstraps.current)
        .reverse()
        .find(([, pending]) => !pending.cancelled);
      if (pendingEntry) {
        const [requestId, pending] = pendingEntry;
        pending.cancelled = true;
        bootstrapCancellationGuardRef.current = Date.now();
        queueAppActions(dispatch, [
          {
            type: "execution.events.ingest",
            events: canonicalEventsFromBridgeEvent({
              type: "session_end",
              request_id: requestId,
              provider_id: pending.provider,
              success: false,
              cancelled: true,
              error_code: "cancelled",
              error_message: "cancelled before provider start",
            }),
          },
          {type: "tab.activate", tabId: "chat"},
          {type: "status.set", value: "cancelled before provider start"},
        ]);
        return "request";
      }
      if (
        Object.values(pendingBootstraps.current).some((pending) => pending.cancelled) ||
        Date.now() - bootstrapCancellationGuardRef.current < 2_000
      ) {
        dispatch({type: "status.set", value: "cancellation already requested"});
        return "already_requested";
      }
      if (source === "command") {
        queueAppActions(dispatch, [
          {
            type: "execution.events.ingest",
            events: [
              userPromptExecutionEvent("/cancel"),
              localCommandResultExecutionEvent("/cancel", "no active turn to cancel"),
            ],
          },
          {type: "tab.activate", tabId: "chat"},
        ]);
      }
      dispatch({type: "status.set", value: "no active turn to cancel"});
      return decision.kind;
    }
    if (decision.kind === "already_requested") {
      dispatch({type: "status.set", value: "cancellation already requested"});
      return decision.kind;
    }
    if (cancellationRequestRef.current?.requestId === decision.requestId) {
      dispatch({type: "status.set", value: "cancellation already requested"});
      return "already_requested";
    }
    try {
      const cancelRequestId = bridge.send("session.cancel", {target_request_id: decision.requestId});
      cancellationRequestRef.current = {requestId: decision.requestId, cancelRequestId};
      queueAppActions(dispatch, [
        {
          type: "turn.cancel.request",
          requestId: decision.requestId,
          cancelRequestId,
        },
        {
          type: "execution.events.ingest",
          events: [localStatusExecutionEvent("cancellation requested", "operator", "running")],
        },
        {type: "status.set", value: "cancellation requested"},
      ]);
      return decision.kind;
    } catch {
      dispatch({type: "status.set", value: "cancellation request could not reach the backend"});
      return "idle";
    }
  }

  function submitPrompt(prompt: string): void {
    const submitted = prompt.trim();
    if (!submitted) {
      return;
    }
    dispatch({type: "prompt.clear"});
    if (submitted.toLowerCase() === "/cancel") {
      requestActiveTurnCancellation("command");
      return;
    }
    const deckMatch = submitted.trim().toLowerCase().match(/^\/deck\s+([a-z0-9_-]+)$/);
    if (deckMatch) {
      // F-065: /deck <name> enters deck-focus; until decks ship (S6) it focuses
      // the matching pane inside the cockpit chrome.
      dispatch({type: "layout.mode.set", mode: `deck-focus:${deckMatch[1]}`});
      const target = stateRef.current.tabs.find((tab) => tab.id === deckMatch[1]);
      runLocalUiAction(submitted, target
        ? {kind: "pane", tabId: target.id, title: target.title}
        : {kind: "layout", mode: "cockpit"});
      return;
    }
    const slashIntent = localUiSlashIntent(submitted);
    if (slashIntent) {
      runLocalUiAction(submitted, slashIntent);
      return;
    }
    if (!isSlashCommandPrompt(submitted)) {
      const nlIntent = matchUiIntent(
        submitted,
        stateRef.current.tabs.map((tab) => ({id: tab.id, title: tab.title})),
        selectableRouteTargets(stateRef.current.routePolicy),
      );
      if (nlIntent) {
        runLocalUiAction(submitted, nlIntent);
        return;
      }
    } else {
      // Gauntlet finding 2026-06-12: a typo'd command (/hlep) must never yank
      // the user into the Control pane — unknown commands answer in-chat with
      // the nearest registered command.
      const commandName = submitted.slice(1).split(/\s+/)[0]?.toLowerCase() ?? "";
      if (commandName && !REGISTERED_SLASH_COMMANDS.includes(commandName) && !isBareModelCommand(submitted)) {
        const suggestion = closestCommand(commandName, REGISTERED_SLASH_COMMANDS);
        queueAppActions(dispatch, [
          {
            type: "execution.events.ingest",
            events: [
              userPromptExecutionEvent(submitted),
              ...canonicalEventsFromBridgeEvent({
                type: "assistant",
                request_id: `local-unknown-${Date.now()}`,
                message: suggestion
                  ? `Unknown command /${commandName} — did you mean /${suggestion}? (/help lists everything)`
                  : `Unknown command /${commandName}. /help lists everything; /tour gives the guided walkthrough.`,
              }),
              localCommandResultExecutionEvent(submitted, `unknown command /${commandName}`),
            ],
          },
          {type: "tab.activate", tabId: "chat"},
          {type: "status.set", value: `unknown command /${commandName}`},
        ]);
        return;
      }
    }
    if (isBareModelCommand(submitted)) {
      dispatch({
        type: "modelPicker.open",
        returnTabId: stateRef.current.uiMode.activeTabId,
      });
      // F-158: even the picker shortcut leaves a completed transcript turn — no
      // slash command may resolve without an entry in the chat transcript.
      queueAppActions(dispatch, [
        {
          type: "execution.events.ingest",
          events: [userPromptExecutionEvent(submitted), localCommandResultExecutionEvent(submitted, "route picker opened")],
        },
      ]);
      bridge.send("model.policy", {
        provider: stateRef.current.routePolicy.provider,
        model: stateRef.current.routePolicy.model,
        strategy: stateRef.current.routePolicy.strategy,
      });
      dispatch({type: "status.set", value: "route picker ready"});
      return;
    }
    if (!isSlashCommandPrompt(submitted) && stateRef.current.activeTurn.phase !== "idle") {
      dispatch({type: "status.set", value: "a turn is already running; cancel it before starting another"});
      return;
    }
    if (isSlashCommandPrompt(submitted)) {
      const commandEchoLine: TranscriptLine = {
        id: `user-${Date.now()}`,
        kind: "user",
        text: `> ${submitted}`,
      };
      // F-158: every slash command leaves a visible transcript turn — the echoed
      // command plus a result, or an explicit queued/failed status. The silent
      // zero-feedback branch (live tour finding 3) is banned.
      if (state.bridgeStatus === "offline") {
        queuedOfflineCounter.current += 1;
        const queueId = `q${queuedOfflineCounter.current}-${Date.now().toString(36)}`;
        queuedOfflineCommands.current.push({queueId, command: submitted});
        queueAppActions(dispatch, [
          {type: "tab.activate", tabId: "chat"},
          {type: "tab.append", tabId: "chat", lines: [commandEchoLine]},
          {
            type: "execution.events.ingest",
            events: [userPromptExecutionEvent(submitted), queuedPromptExecutionEvent(queueId)],
          },
          {type: "status.set", value: "command queued (backend offline)"},
        ]);
        return;
      }
      queueAppActions(dispatch, slashCommandStartActions({command: submitted}, "command"));
      queueAppActions(dispatch, [
        {type: "tab.append", tabId: "chat", lines: [commandEchoLine]},
        {type: "execution.events.ingest", events: [userPromptExecutionEvent(submitted)]},
      ]);
      markPendingCommandStream(pendingCommandStream, {command: submitted});
      bridge.send("command.run", {command: submitted});
    } else {
      const messages = messagesForNextTurn(state, submitted);
      const userLine: TranscriptLine = {
        id: `user-${Date.now()}`,
        kind: "user",
        text: `> ${submitted}`,
      };
      // F-157: while the bridge is offline the turn queues explicitly — no optimistic
      // trace steps, no session.bootstrap into the void, never a perpetual running state.
      if (state.bridgeStatus === "offline") {
        queuedOfflineCounter.current += 1;
        const queueId = `q${queuedOfflineCounter.current}-${Date.now().toString(36)}`;
        queuedOfflinePrompts.current.push({
          queueId,
          prompt: submitted,
          provider: state.routePolicy.provider,
          model: state.routePolicy.model,
          strategy: state.routePolicy.strategy,
          activeTabId: state.uiMode.activeTabId,
          messages,
          resumeSessionId: state.sessionContinuity.resumeSessionId,
        });
        queueAppActions(dispatch, [
          {type: "tab.activate", tabId: "chat"},
          {type: "tab.append", tabId: "chat", lines: [userLine]},
          {
            type: "execution.events.ingest",
            events: [userPromptExecutionEvent(submitted), queuedPromptExecutionEvent(queueId)],
          },
          {type: "status.set", value: "prompt queued (backend offline)"},
        ]);
        return;
      }
      const route = routeLabel(state.routePolicy);
      queueAppActions(dispatch, [
        {type: "tab.activate", tabId: "chat"},
        {type: "tab.append", tabId: "chat", lines: [userLine]},
        {
          type: "execution.events.ingest",
          events: [
            userPromptExecutionEvent(submitted),
            localStatusExecutionEvent("bootstrapping context", route, "queued"),
            localStatusExecutionEvent("selecting route", `${route} (${state.routePolicy.strategy})`, "queued"),
          ],
        },
      ]);
      const requestId = bridge.send("session.bootstrap", {
        provider: state.routePolicy.provider,
        model: state.routePolicy.model,
        strategy: state.routePolicy.strategy,
        prompt: submitted,
        active_tab: state.uiMode.activeTabId,
        resume_session_id: state.sessionContinuity.resumeSessionId,
      });
      pendingBootstraps.current[requestId] = {
        prompt: submitted,
        provider: state.routePolicy.provider,
        model: state.routePolicy.model,
        messages,
        resumeSessionId: state.sessionContinuity.resumeSessionId,
      };
      dispatch({
        type: "status.set",
        value:
          state.sessionContinuity.resumeSessionId
            ? `resuming ${state.sessionContinuity.resumeSessionId} via ${routeLabel(state.routePolicy)} (${state.routePolicy.strategy})`
            : `bootstrapping ${routeLabel(state.routePolicy)} (${state.routePolicy.strategy})`,
      });
    }
  }

  function runPaneAction(action: PaneAction | undefined): void {
    if (!action) {
      return;
    }
    queueAppActions(dispatch, paneActionStartActions(action));
    if (action.summary === "focus selected approval") {
      return;
    }
    if (action.requestType === "session.detail") {
      requestSessionDetail(bridge, dispatch, String(action.payload.session_id ?? "").trim() || undefined);
      return;
    }
    const commandRunEvent = commandRunEventFromPaneAction(action);
    if (commandRunEvent) {
      markPendingCommandStream(pendingCommandStream, commandRunEvent);
    }
    bridge.send(action.requestType ?? "action.run", action.payload);
  }

  function applyModelChoice(index: number): void {
    const currentState = stateRef.current;
    const choices = selectableRouteTargets(currentState.routePolicy);
    const returnTabId = currentState.uiMode.activeOverlay.kind === "modelPicker"
      ? currentState.uiMode.activeOverlay.returnTabId
      : currentState.uiMode.activeTabId;
    const clampedIndex = Math.min(Math.max(index, 0), Math.max(choices.length - 1, 0));
    const choice = choices[clampedIndex];
    if (!choice) {
      dispatch({type: "status.set", value: "no model targets available"});
      return;
    }
    queueAppActions(dispatch, [
      {type: "modelPicker.set", index: clampedIndex},
    ]);
    bridge.send("action.run", {
      action_type: "model.set",
      provider: choice.provider,
      model: choice.model,
      strategy: stateRef.current.routePolicy.strategy,
    });
    queueAppActions(dispatch, [
      {type: "modelPicker.close"},
      {type: "tab.activate", tabId: returnTabId},
      {type: "status.set", value: `requesting route -> ${choice.provider}:${choice.model}`},
    ]);
  }

  function selectSessionForInspection(sessionId: string): void {
    const currentState = stateRef.current;
    const detail = currentState.sessionPane.detailsBySessionId[sessionId];
    queueAppActions(dispatch, [
      {type: "session.select", sessionId},
      {type: "session.continuity.set", continuity: continuityStateFromSession(currentState, detail)},
      {type: "status.set", value: `viewing session ${sessionId} (next prompt remains fresh)`},
    ]);
  }

  function armSelectedSessionResume(): void {
    const currentState = stateRef.current;
    const sessionId = currentState.sessionPane.selectedSessionId;
    const detail = sessionId ? currentState.sessionPane.detailsBySessionId[sessionId] : undefined;
    const eligibility = sessionResumeEligibility(currentState, detail);
    if (!eligibility.canResume) {
      if (eligibility.reason === "detail_unavailable" && sessionId) {
        requestSessionDetail(bridge, dispatch, sessionId);
        dispatch({type: "status.set", value: `loading ${sessionId}; press r again to arm resume`});
        return;
      }
      const reason = {
        detail_unavailable: "select a session first",
        provider_unsupported: "runtime resume is currently Claude-only",
        provider_mismatch: "selected session does not match the active provider",
        replay_unverified: "selected transcript failed replay verification",
        provider_session_missing: "selected session has no provider-native resume id",
      }[eligibility.reason];
      dispatch({type: "status.set", value: `resume unavailable: ${reason}`});
      return;
    }
    if (!sessionId) {
      dispatch({type: "status.set", value: "resume unavailable: select a session first"});
      return;
    }
    queueAppActions(dispatch, [
      {type: "session.select", sessionId},
      {type: "session.continuity.set", continuity: continuityStateFromSession(currentState, detail, "resume")},
    ]);
    dispatch({type: "status.set", value: `resume armed for ${sessionId}; the next chat prompt continues it`});
  }

  function resetSessionResume(): void {
    const currentState = stateRef.current;
    const sessionId = currentState.sessionPane.selectedSessionId;
    const detail = sessionId ? currentState.sessionPane.detailsBySessionId[sessionId] : undefined;
    dispatch({type: "session.continuity.set", continuity: continuityStateFromSession(currentState, detail)});
    dispatch({type: "status.set", value: "resume cleared; the next chat prompt starts fresh"});
  }

  // F-064: F2 toggles zen <-> cockpit. ink 5 blanks F-key input inside
  // useInput (f2 is in nonAlphanumericKeys with no key flag), so the toggle
  // listens on the raw stdin bytes instead: ESC OQ / ESC [12~ / ESC [[B.
  const {stdin: rawStdin} = useStdin();
  useEffect(() => {
    if (!rawStdin) {
      return;
    }
    const onData = (data: Buffer | string): void => {
      const sequence = data.toString();
      if (sequence === "OQ" || sequence === "[12~" || sequence === "[[B") {
        if (stateRef.current.uiMode.activeOverlay.kind !== "none") {
          return;
        }
        const next = stateRef.current.uiMode.layoutMode === "zen" ? "cockpit" : "zen";
        dispatch({type: "layout.mode.set", mode: next});
        dispatch({type: "status.set", value: `${next} layout — F2 toggles`});
      }
    };
    rawStdin.on("data", onData);
    return () => {
      rawStdin.off("data", onData);
    };
  }, [rawStdin]);

  useInput((input, key) => {
    // The guided tour modal swallows the next keystroke to dismiss itself —
    // any key closes it (operator word 2026-06-16).
    if (state.uiMode.activeOverlay.kind === "tour") {
      dispatch({type: "tour.close"});
      dispatch({type: "status.set", value: "tour closed"});
      return;
    }
    if (state.uiMode.activeOverlay.kind === "paneSwitcher") {
      const maxIndex = Math.max(state.tabs.length - 1, 0);
      if (key.escape) {
        dispatch({type: "paneSwitcher.close"});
        dispatch({type: "status.set", value: "pane switcher closed"});
        return;
      }
      if (input === "j" || key.downArrow) {
        dispatch({type: "paneSwitcher.set", index: Math.min(state.uiMode.activeOverlay.selectedIndex + 1, maxIndex)});
        return;
      }
      if (input === "k" || key.upArrow) {
        dispatch({type: "paneSwitcher.set", index: Math.max(state.uiMode.activeOverlay.selectedIndex - 1, 0)});
        return;
      }
      if (key.return) {
        const target = state.tabs[state.uiMode.activeOverlay.selectedIndex];
        if (target) {
          queueAppActions(dispatch, [
            {type: "paneSwitcher.close"},
            {type: "tab.activate", tabId: target.id},
            {type: "status.set", value: `pane -> ${target.title}`},
          ]);
        }
        return;
      }
      return;
    }
    if (state.uiMode.activeOverlay.kind === "modelPicker") {
      const choices = modelChoices;
      const maxIndex = Math.max(choices.length - 1, 0);
      if (key.escape) {
        const returnTabId = state.uiMode.activeOverlay.returnTabId;
        queueAppActions(dispatch, [
          {type: "modelPicker.close"},
          {type: "tab.activate", tabId: returnTabId},
          {type: "status.set", value: "model picker closed"},
        ]);
        return;
      }
      if (input === "j" || key.downArrow) {
        dispatch({type: "modelPicker.set", index: Math.min(state.uiMode.activeOverlay.selectedIndex + 1, maxIndex)});
        return;
      }
      if (input === "k" || key.upArrow) {
        dispatch({type: "modelPicker.set", index: Math.max(state.uiMode.activeOverlay.selectedIndex - 1, 0)});
        return;
      }
      if (key.return) {
        applyModelChoice(state.uiMode.activeOverlay.selectedIndex);
        return;
      }
      if (/^[1-9]$/.test(input)) {
        const numericIndex = Number.parseInt(input, 10) - 1;
        if (numericIndex <= maxIndex) {
          applyModelChoice(numericIndex);
        }
        return;
      }
      return;
    }
    if (key.ctrl && input === "c") {
      const cancellation = decideTurnCancellation(stateRef.current.activeTurn);
      const bootstrapPending = Object.keys(pendingBootstraps.current).length > 0;
      const bootstrapCancellationGuarded = Date.now() - bootstrapCancellationGuardRef.current < 2_000;
      if (cancellation.kind !== "idle" || bootstrapPending || bootstrapCancellationGuarded) {
        requestActiveTurnCancellation("shortcut");
        return;
      }
      bridge.close();
      exit();
      return;
    }
    if (key.escape) {
      const nextFocus = state.uiMode.keyboardFocus === "composer" ? "navigation" : "composer";
      dispatch({type: "ui.focus.set", focus: nextFocus});
      dispatch({type: "status.set", value: `${nextFocus} focus`});
      return;
    }
    if (state.uiMode.keyboardFocus === "composer") {
      if (isPlainReturn(input, key.return)) {
        submitPrompt(state.prompt);
        return;
      }
      if (key.backspace || key.delete) {
        dispatch({type: "prompt.backspace"});
        return;
      }
      if (!key.ctrl && !key.meta) {
        const normalized = normalizeComposerInput(input);
        if (normalized) {
          dispatch({type: "prompt.append", value: normalized});
        }
      }
      return;
    }
    if (activeTab?.kind === "sessions") {
      if (!key.ctrl && !key.meta && input === "j") {
        const nextSessionId = stepSessionSelection(stateRef.current, 1);
        if (nextSessionId) {
          selectSessionForInspection(nextSessionId);
        }
        return;
      }
      if (!key.ctrl && !key.meta && input === "k") {
        const nextSessionId = stepSessionSelection(stateRef.current, -1);
        if (nextSessionId) {
          selectSessionForInspection(nextSessionId);
        }
        return;
      }
      if (!key.ctrl && !key.meta && input === "r") {
        armSelectedSessionResume();
        return;
      }
      if (!key.ctrl && !key.meta && input === "f") {
        resetSessionResume();
        return;
      }
      if (key.return) {
        if (state.sessionPane.selectedSessionId) {
          requestSessionDetail(bridge, dispatch, state.sessionPane.selectedSessionId);
          dispatch({type: "status.set", value: `refresh detail ${state.sessionPane.selectedSessionId}`});
        }
        return;
      }
    }
    if (activeTab?.kind === "approvals") {
      if (input === "j") {
        const nextActionId = stepApprovalSelection(stateRef.current, 1);
        if (nextActionId) {
          dispatch({type: "approval.select", actionId: nextActionId});
          dispatch({type: "status.set", value: `approval -> ${nextActionId}`});
        }
        return;
      }
      if (input === "k") {
        const nextActionId = stepApprovalSelection(stateRef.current, -1);
        if (nextActionId) {
          dispatch({type: "approval.select", actionId: nextActionId});
          dispatch({type: "status.set", value: `approval -> ${nextActionId}`});
        }
        return;
      }
    }
    if (activeTab?.kind === "agents") {
      if (input === "j" || input === "k" || key.upArrow || key.downArrow) {
        const direction: 1 | -1 = input === "k" || key.upArrow ? -1 : 1;
        const nextIndex = stepPaneSectionFocus(
          stateRef.current.paneFocusIndices[activeTab.id],
          agentRouteCount(activeTab.lines),
          direction,
        );
        if (typeof nextIndex === "number") {
          dispatch({type: "pane.focus.set", tabId: activeTab.id, index: nextIndex});
          dispatch({
            type: "status.set",
            value: `agent route ${nextIndex + 1}/${Math.max(agentRouteCount(activeTab.lines), 1)}`,
          });
        }
        return;
      }
    }
    if (activeTab?.kind === "repo" || activeTab?.kind === "control" || activeTab?.kind === "runtime") {
      if (input === "j" || input === "k" || key.upArrow || key.downArrow) {
        const direction: 1 | -1 = input === "k" || key.upArrow ? -1 : 1;
        const nextIndex = stepPaneSectionFocus(
          stateRef.current.paneFocusIndices[activeTab.id],
          paneSectionCount(activeTab, stateRef.current),
          direction,
        );
        if (typeof nextIndex === "number") {
          dispatch({type: "pane.focus.set", tabId: activeTab.id, index: nextIndex});
          dispatch({
            type: "status.set",
            value: `${activeTab.title.toLowerCase()} section ${nextIndex + 1}/${Math.max(paneSectionCount(activeTab, stateRef.current), 1)}`,
          });
        }
        return;
      }
    }
    if ((key.upArrow || key.downArrow) && activeTab?.kind === "sessions") {
      const nextSessionId = stepSessionSelection(stateRef.current, key.downArrow ? 1 : -1);
      if (nextSessionId) {
        selectSessionForInspection(nextSessionId);
      }
      return;
    }
    if ((key.upArrow || key.downArrow) && activeTab?.kind === "approvals") {
      const nextActionId = stepApprovalSelection(stateRef.current, key.downArrow ? 1 : -1);
      if (nextActionId) {
        dispatch({type: "approval.select", actionId: nextActionId});
        dispatch({type: "status.set", value: `approval -> ${nextActionId}`});
      }
      return;
    }
    if ((key.upArrow || key.downArrow) && activeTab) {
      dispatch({
        type: "pane.scroll",
        tabId: activeTab.id,
        delta: key.upArrow ? -1 : 1,
        maxOffset: scrollMaxOffsetForTab(activeTab, stateRef.current, paneWindowSize),
      });
      return;
    }
    if (key.ctrl && input === "b") {
      const current = stateRef.current.uiMode.sidebarVisible;
      const statusMap: Record<string, string> = {
        visible: "sidebar collapsed",
        collapsed: "sidebar hidden",
        hidden: `sidebar -> ${stateRef.current.uiMode.sidebarMode}`,
      };
      dispatch({type: "sidebar.toggle"});
      dispatch({
        type: "status.set",
        value: statusMap[current] ?? "sidebar",
      });
      return;
    }
    if (key.ctrl && input === "l") {
      runPaneAction(paneActionsFor(activeTab?.id ?? "chat", state, shellControlOptions).refresh);
      return;
    }
    if (key.ctrl && input === "w" && activeTab?.closable) {
      dispatch({type: "tab.close", tabId: activeTab.id});
      return;
    }
    if (key.ctrl && input === "x") {
      runPaneAction(paneActionsFor(activeTab?.id ?? "chat", state, shellControlOptions).primary);
      return;
    }
    if (key.ctrl && input === "f") {
      runPaneAction(paneActionsFor(activeTab?.id ?? "chat", state, shellControlOptions).secondary);
      return;
    }
    if (key.ctrl && input === "v") {
      runPaneAction(paneActionsFor(activeTab?.id ?? "chat", state, shellControlOptions).tertiary);
      return;
    }
    // F-159: the shift+tab branch must run BEFORE the plain-tab branch —
    // Shift-Tab also sets key.tab, so the old order consumed it as forward
    // (live tour finding 4: BTab navigated forward while the footer
    // advertised reverse).
    if (key.leftArrow || (key.shift && key.tab)) {
      dispatch({type: "tab.cycle", direction: -1});
      return;
    }
    if (key.tab || key.rightArrow) {
      dispatch({type: "tab.cycle", direction: 1});
      return;
    }
    // Design-truth law #6 (operator hit it live typing "5.1" — the "1" fired a
    // sidebar command mid-sentence): printable keys ALWAYS reach the composer;
    // navigation is chords only. Bare [ ] and 1/2/3 bindings are gone.
    if (key.ctrl && input === "g") {
      dispatch({type: "tab.activate", tabId: "chat"});
      return;
    }
    if (key.ctrl && input === "r") {
      dispatch({type: "tab.activate", tabId: "repo"});
      return;
    }
    if (key.ctrl && input === "o") {
      dispatch({type: "tab.activate", tabId: "ontology"});
      return;
    }
    if (key.ctrl && input === "m") {
      dispatch({type: "tab.activate", tabId: "commands"});
      return;
    }
    if (key.ctrl && input === "a") {
      dispatch({type: "tab.activate", tabId: "agents"});
      return;
    }
    if (key.ctrl && input === "p") {
      dispatch({
        type: "modelPicker.open",
        returnTabId: state.uiMode.activeTabId,
      });
      bridge.send("model.policy", {
        provider: stateRef.current.routePolicy.provider,
        model: stateRef.current.routePolicy.model,
        strategy: stateRef.current.routePolicy.strategy,
      });
      dispatch({type: "status.set", value: "route picker ready"});
      return;
    }
    if (key.ctrl && input === "k") {
      dispatch({type: "paneSwitcher.open"});
      dispatch({type: "status.set", value: "pane switcher ready"});
      return;
    }
    if (key.ctrl && input === "e") {
      dispatch({type: "tab.activate", tabId: "evolution"});
      return;
    }
    if (key.ctrl && input === "t") {
      if ((activeTab?.id ?? "chat") === "chat") {
        const nextExpanded = !stateRef.current.chatTraceExpanded;
        dispatch({type: "trace.toggle"});
        dispatch({type: "status.set", value: nextExpanded ? "trace expanded" : "trace collapsed"});
        return;
      }
      dispatch({type: "tab.activate", tabId: "control"});
      return;
    }
    if (key.ctrl && input === "y") {
      dispatch({type: "tab.activate", tabId: "runtime"});
      return;
    }
    if (key.ctrl && input === "h") {
      dispatch({type: "tab.activate", tabId: "thinking"});
      return;
    }
    if (key.ctrl && input === "j") {
      dispatch({type: "tab.activate", tabId: "tools"});
      return;
    }
    if (key.ctrl && input === "n") {
      dispatch({type: "tab.activate", tabId: "timeline"});
      return;
    }
    if (key.ctrl && input === "u") {
      dispatch({type: "activity.visibility.toggle"});
      return;
    }
    if (key.ctrl && input === "i") {
      dispatch({type: "activity.raw.toggle"});
      return;
    }
    if (key.ctrl && input === "d" && state.uiMode.layoutMode === "scroll") {
      // FACE-3: the scroll's telemetry drawer — scoped to the manuscript face
      // so ^D stays free for future faces everywhere else.
      setScrollDrawerOpen((open) => !open);
      return;
    }
  });

  // The guided tour is an isolated, full-screen modal box (operator word
  // 2026-06-16) — it pre-empts every face so it is never tangled with the
  // transcript. Any key dismisses it (handled in the input handler above).
  if (state.uiMode.activeOverlay.kind === "tour") {
    const tourPanes = state.tabs.map((tab) => ({id: tab.id, title: tab.title}));
    return (
      <TourOverlay lines={tourLines(tourPanes)} width={terminalWidth} height={terminalHeight} />
    );
  }

  // F-111: zen is the boot default and contains exactly the transcript, the
  // composer, and ONE thin status line (F-110) — the Claude Code-grade main
  // stage. Tab/^K still navigate: any non-chat pane or overlay falls through
  // to the full cockpit chrome below; returning to chat restores zen.
  if (
    state.uiMode.layoutMode === "zen" &&
    activeTab?.kind === "chat" &&
    state.uiMode.activeOverlay.kind === "none"
  ) {
    const zenWindow = Math.max(MIN_SCROLL_WINDOW_SIZE, terminalHeight - 7);
    // FACE-1 zen-pure: the status line carries only durable state (route +
    // bridge liveness) — transient statusLine spam ("route confirmed",
    // "sidebar ->") must never churn the zen frame.
    const zenStatus = [
      `zen/${state.uiMode.keyboardFocus}`,
      `${routeLabel(state.routePolicy)} [${state.routePolicy.routeState}]`,
      `bridge ${state.bridgeStatus}`,
      "F2 cockpit · /tour",
    ].join("  ·  ");
    // Claude-Code baseline (operator hard rule "full screen, just like claude
    // code" — the ~100-col clamp left a dead gulf on the right half of wide
    // terminals): the zen frame spans the full terminal width.
    const zenWidth = terminalWidth;
    // Content-hugging like Claude Code: the composer sits directly under the
    // last message (operator: "still too bulky" — the old bottom-pin left a
    // dead gulf mid-screen). The frame stays full-height with the spacer BELOW
    // the status line: mixed-height frames desync ink's in-place repaint
    // (zen->cockpit->zen left a stale cockpit frame on screen).
    return (
      <Box flexDirection="column" height={terminalHeight}>
        {/* Claude-Code baseline: conversation fills the top (newest hugs the
            composer), composer + one stable status row pinned at the bottom.
            Navigator is summonable (^N), off by default so the baseline stays pure. */}
        <Box flexGrow={1} flexShrink={1} flexDirection="column" width={zenWidth}>
          <TranscriptPane
            frameless
            bottomAnchor
            title="Chat"
            lines={displayedTranscriptLines}
            scrollOffset={activeScrollOffset}
            windowSize={zenWindow}
            emptyState={transcriptMeta.emptyState}
            accentColor={transcriptMeta.accentColor}
          />
        </Box>
        <Box flexShrink={0} flexDirection="column" width={zenWidth}>
          <Composer
            prompt={state.prompt}
            focused={state.uiMode.keyboardFocus === "composer"}
            compact={compactShell}
            width={zenWidth}
          />
          <Box paddingX={1}>
            <Text dimColor wrap="truncate-end">{zenStatus}</Text>
          </Box>
        </Box>
      </Box>
    );
  }

  // FACE-3 the scroll: a reading-first manuscript — the conversation as a
  // clean centered column (~80 cols), one thin wave rule between turns, all
  // telemetry folded behind a single toggleable drawer row (^D). The composer
  // carries the frame's only border; Tab/^K still fall through to the cockpit
  // chrome below, and returning to chat restores the manuscript.
  if (
    state.uiMode.layoutMode === "scroll" &&
    activeTab?.kind === "chat" &&
    state.uiMode.activeOverlay.kind === "none"
  ) {
    const scrollWindow = Math.max(MIN_SCROLL_WINDOW_SIZE, terminalHeight - 7);
    // Manuscript measure: a touch under the zen clamp — the column is the
    // identity of this face, so it earns gutters at wide terminals.
    const scrollMeasure = Math.min(terminalWidth, 84);
    const scrollStatus = `${state.uiMode.keyboardFocus} · ${scrollStatusLine({
      drawerOpen: scrollDrawerOpen,
      routeLabel: routeLabel(state.routePolicy),
      bridgeStatus: state.bridgeStatus,
      routeState: state.routePolicy.routeState,
      strategy: state.routePolicy.strategy,
    })}`;
    return (
      <Box flexDirection="column" height={terminalHeight} alignItems="center">
        <Box flexShrink={0} flexDirection="column" width={scrollMeasure}>
          <TranscriptPane
            frameless
            title="Chat"
            lines={manuscriptLines(displayedTranscriptLines, scrollMeasure)}
            scrollOffset={activeScrollOffset}
            windowSize={scrollWindow}
            emptyState={transcriptMeta.emptyState}
            accentColor={transcriptMeta.accentColor}
          />
          <Composer
            prompt={state.prompt}
            focused={state.uiMode.keyboardFocus === "composer"}
            compact={compactShell}
            width={scrollMeasure}
          />
          <Box paddingX={1}>
            <Text dimColor wrap="truncate-end">{scrollStatus}</Text>
          </Box>
        </Box>
        <Box flexGrow={1} />
      </Box>
    );
  }

  return (
    // F-163 fill law: the root owns exactly the terminal's rows — the pane row
    // flexGrows into the spare height and CLIPS overgrown content (live sidebar
    // telemetry previously inflated the layout past the terminal, scrolling the
    // header, tab bar, and the entire conversation off-screen — operator live
    // verdict 2026-06-12). Header/tab bar at top and composer/footer at bottom
    // are now unconditionally visible at every size.
    <Box flexDirection="column" height={terminalHeight}>
      {/* flexShrink 0 on all fixed chrome: only the pane row below may flex.
          Without it Yoga crushes the header/footer when pane content overflows. */}
      <Box flexDirection="column" flexShrink={0}>
        <ShellHeader
          activeTitle={activeTab?.title ?? "Workspace"}
          activeCount={state.tabs.length}
          compact={compactShell}
        />
        <OperatorSummaryBand items={operatorSummaryItems} compact={compactShell} />
        <TabBar tabs={state.tabs} activeTabId={state.uiMode.activeTabId} compact={compactShell} />
        {/* F-021: the 8-row wave renders only when the height budget affords it
            (>= 40 rows) and the chat is still quiet — once real turns arrive the
            transcript window owns those rows and the strip recedes. */}
        {activeTab?.kind === "chat" && !compactShell && terminalHeight >= 40 && displayedTranscriptLines.length <= 4 ? (
          <ScenicStrip />
        ) : null}
      </Box>
      <Box flexGrow={1} overflow="hidden">
        {/* FACE-2 command post: sidebar is OFF by default (data panes carry
            the info) and renders ONLY when explicitly visible — F-162: a
            collapsed sidebar renders zero-width, never a 3-col "T" sliver. */}
        {state.uiMode.sidebarVisible === "visible" && state.uiMode.activeOverlay.kind !== "modelPicker" && !compactShell ? (
          // clip-don't-squeeze: the row stretches children to its height, and
          // Yoga then crushes their inner columns into overlapping rows. The
          // wrapper clips at natural height instead.
          <Box flexDirection="column" overflow="hidden" flexShrink={0}>
            <Box flexShrink={0} flexDirection="column">
              <Sidebar
                mode={state.uiMode.sidebarMode}
                outline={outline}
                activeTabTitle={activeTab?.title ?? "Workspace"}
                provider={state.routePolicy.provider}
                model={state.routePolicy.model}
                bridgeStatus={state.bridgeStatus}
                tabs={state.tabs}
                repoPreview={decorateSurfacePreview(state.liveRepoPreview, "repo", state.bridgeStatus, state.authoritativeSurfaces)}
                controlPreview={decorateSurfacePreview(state.liveControlPreview, "control", state.bridgeStatus, state.authoritativeSurfaces)}
                compact={compactShell}
              />
            </Box>
          </Box>
        ) : null}
        <Box flexGrow={1} flexDirection="column" overflow="hidden">
        {/* FACE-2 fill law: flexGrow stretches a SHORT pane to claim the spare
            height (no dead gulf above the composer); flexShrink 0 keeps tall
            content at natural height so the outer overflow CLIPS instead of
            Yoga crushing columns into garble (F-022 clip-don't-squeeze). */}
        <Box flexShrink={0} flexGrow={1} flexDirection="column">
        {state.uiMode.activeOverlay.kind === "paneSwitcher" ? (
          <PaneSwitcher
            tabs={state.tabs}
            selectedIndex={Math.min(state.uiMode.activeOverlay.selectedIndex, Math.max(state.tabs.length - 1, 0))}
          />
        ) : state.uiMode.activeOverlay.kind === "modelPicker" ? (
          <ModelPicker
            choices={modelChoices}
            selectedIndex={Math.min(state.uiMode.activeOverlay.selectedIndex, Math.max(modelChoices.length - 1, 0))}
            title="Model Picker"
            compact={compactShell}
          />
        ) : activeTab?.kind === "repo" ? (
          <RepoPane
            title={activeTab.title}
            preview={decorateSurfacePreview(state.liveRepoPreview ?? activeTab.preview, "repo", state.bridgeStatus, state.authoritativeSurfaces)}
            controlPreview={decorateSurfacePreview(state.liveControlPreview ?? state.tabs.find((tab) => tab.id === "control")?.preview, "control", state.bridgeStatus, state.authoritativeSurfaces)}
            controlLines={state.tabs.find((tab) => tab.id === "control")?.lines ?? []}
            lines={activeTab.lines}
            scrollOffset={activeScrollOffset}
            windowSize={paneWindowSize}
            selectedSectionIndex={state.paneFocusIndices[activeTab.id] ?? 0}
          />
        ) : activeTab?.kind === "control" || activeTab?.kind === "runtime" ? (
          <ControlPane
            title={activeTab.title}
            mode={activeTab.kind}
            preview={
              decorateSurfacePreview(
                controlPanePreview(
                  state.liveControlPreview ??
                    activeTab.preview ??
                    state.tabs.find((tab) => tab.id === "control")?.preview,
                  state.liveRepoPreview ?? state.tabs.find((tab) => tab.id === "repo")?.preview,
                ),
                "control",
                state.bridgeStatus,
                state.authoritativeSurfaces,
              )
            }
            lines={
              activeTab.kind === "runtime" && activeTab.lines.length === 0
                ? (state.tabs.find((tab) => tab.id === "control")?.lines ?? [])
                : activeTab.lines
            }
            scrollOffset={activeScrollOffset}
            windowSize={paneWindowSize}
            selectedSectionIndex={state.paneFocusIndices[activeTab.id] ?? 0}
          />
        ) : activeTab?.kind === "approvals" ? (
          <ApprovalsPane title={activeTab.title} approvalPane={state.approvalPane} />
        ) : activeTab?.kind === "sessions" ? (
          <SessionsPane
            title={activeTab.title}
            sessionPane={state.sessionPane}
            sessionContinuity={state.sessionContinuity}
          />
        ) : activeTab?.kind === "agents" ? (
          <AgentsPane
            title={activeTab.title}
            lines={activeTab.lines}
            selectedRouteIndex={state.paneFocusIndices[activeTab.id] ?? 0}
          />
        ) : activeTab?.kind === "thinking" || activeTab?.kind === "tools" || activeTab?.kind === "timeline" ? (
          <ActivityPane
            title={activeTab.title}
            paneKind={activeTab.kind}
            feed={state.activityFeed}
            scrollOffset={activeScrollOffset}
            windowSize={paneWindowSize}
          />
        ) : (
          <TranscriptPane
            title={activeTab?.title ?? "Workspace"}
            lines={displayedTranscriptLines}
            scrollOffset={activeScrollOffset}
            windowSize={paneWindowSize}
            subtitle={transcriptMeta.subtitle}
            emptyState={transcriptMeta.emptyState}
            accentColor={transcriptMeta.accentColor}
          />
        )}
        </Box>
        </Box>
        {/* Navigator rail: the sidebar's mirror image on the right edge — a
            fixed-width, clip-don't-squeeze column so it can only partition the
            pane row's WIDTH, never inflate its height (F-163 by construction). */}
        {railVisible ? (
          <Box flexDirection="column" overflow="hidden" flexShrink={0} width={railWidth} borderStyle="single" borderColor={THEME.ridge} borderTop={false} borderRight={false} borderBottom={false}>
            <NavigatorRail
              lines={railChatLines}
              narration={state.navigatorNarration}
              routeLabel={liveRouteLabel}
              activeTitle={activeTab?.title ?? "Workspace"}
              windowSize={railWindowSize}
              width={railWidth}
            />
          </Box>
        ) : null}
      </Box>
      <Box flexDirection="column" flexShrink={0}>
        <Composer
          prompt={state.prompt}
          focused={state.uiMode.keyboardFocus === "composer"}
          compact={compactShell}
          width={terminalWidth}
        />
        {/* F-110: exactly ONE status row at every size — the single source
            (F-164) for mode, route, gate state, and provider summary. */}
        <StatusFooter
          mode={focusModeFor(activeTab, state)}
          routeLabel={routeLabel(state.routePolicy)}
          bridgeStatus={state.bridgeStatus}
          routeState={state.routePolicy.routeState}
          strategy={state.routePolicy.strategy}
          reason={state.routePolicy.availabilityReason}
          compact={compactShell}
        />
      </Box>
    </Box>
  );
}

export function createInitialAppState(baseState: AppState): AppState {
  const restored = loadStoredState();
  const restoredTabs = ensureRuntimeTabs(baseState.tabs);
  const bootRepoPreview = loadSupervisorRepoPreview();
  const bootControlPreview = loadSupervisorControlPreview();
  const restoredControlSurfacePreview = mergePreview(
    restoredTabs.find((tab) => tab.id === "control")?.preview,
    restoredTabs.find((tab) => tab.id === "runtime")?.preview,
  );
  const restoredControlPreview = mergePreview(restoredControlSurfacePreview, bootControlPreview ?? undefined);
  const restoredRepoPreview = normalizeRepoPreview(
    mergePreview(restoredTabs.find((tab) => tab.id === "repo")?.preview, bootRepoPreview ?? undefined),
    restoredControlPreview,
  );
  const bootRepoLines = restoredRepoPreview ? workspacePreviewToLines(restoredRepoPreview) : undefined;
  const bootControlLines = restoredControlPreview ? runtimePreviewToLines(restoredControlPreview) : undefined;
  const hydratedTabs = restoredTabs.map((tab) => {
    if (tab.id === "repo" && restoredRepoPreview) {
      return {
        ...tab,
        lines: bootRepoLines ?? tab.lines,
        preview: restoredRepoPreview,
      };
    }
    if ((tab.id === "control" || tab.id === "runtime") && restoredControlPreview) {
      return {
        ...tab,
        lines: bootControlLines ?? tab.lines,
        preview: restoredControlPreview,
      };
    }
    return tab;
  });

  return {
    ...baseState,
    uiMode: {
      ...baseState.uiMode,
      sidebarVisible: restored?.sidebarVisible ?? baseState.uiMode.sidebarVisible,
      sidebarMode: restored?.sidebarMode ?? baseState.uiMode.sidebarMode,
      activeTabId: baseState.uiMode.activeTabId,
      focusedPaneId: baseState.uiMode.focusedPaneId,
    },
    paneScrollOffsets: baseState.paneScrollOffsets,
    tabs: hydratedTabs,
    liveRepoPreview: mergePreview(baseState.liveRepoPreview, restoredRepoPreview),
    liveControlPreview: mergePreview(baseState.liveControlPreview, restoredControlPreview),
    outline: outlineFromTabs(hydratedTabs),
  };
}
