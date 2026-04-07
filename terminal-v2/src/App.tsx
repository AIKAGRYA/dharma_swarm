import React, { useCallback, useEffect, useMemo, useReducer, useRef } from "react";
import { Box, useApp, useInput, useStdout } from "ink";
import type { BridgeEvent } from "./core/bridge.js";
import { useBridge } from "./hooks/useBridge.js";
import type { LiveData } from "./hooks/useApi.js";
import { requestAuthoritativeResync, requestLiveSnapshots, requestPermissionHistory, requestSessionCatalog } from "./core/bridgeRequests.js";
import type { TranscriptLine, TabPreview, ApprovalQueueState, ApprovalQueueEntry, AppState } from "./core/types.js";
import { paneActionsFor } from "./core/shellControls.js";
import { workspaceSnapshotPayloadFromEvent, workspacePayloadToPreview, workspaceSnapshotToPreview, workspacePreviewToLines, runtimeSnapshotPayloadFromEvent, runtimePayloadToPreview, runtimeSnapshotToPreview, runtimePreviewToLines, modelPolicyToLines, modelPolicyToPreview, agentRoutesToLines, agentRoutesToPreview, evolutionSurfaceToLines, evolutionSurfaceToPreview, sessionCatalogToLines, sessionCatalogToPreview, sessionDetailToLines, sessionDetailToPreview, permissionDecisionFromEvent, permissionResolutionFromEvent, permissionOutcomeFromEvent, permissionHistoryFromEvent, approvalPaneToLines, approvalPaneToPreview, commandGraphToLines, commandGraphToPreview } from "./core/protocol.js";
import { routePolicyFromValue } from "./core/routePolicy.js";

type ApiOverview = NonNullable<LiveData["overview"]>;
type ApiAgent = LiveData["agents"][number];
type ApiProfile = LiveData["profiles"][number];
type ApiDharma = NonNullable<LiveData["dharma"]>;
import { colors } from "./theme.js";
import { ShellHeader, type BridgeStatus } from "./shell/ShellHeader.js";
import { OperatorSummaryBand } from "./shell/OperatorSummaryBand.js";
import { TabBar } from "./shell/TabBar.js";
import { Sidebar, type SidebarVisibility, type SidebarMode } from "./shell/Sidebar.js";
import { MainPane } from "./shell/MainPane.js";
import { Composer } from "./shell/Composer.js";
import { StatusFooter } from "./shell/StatusFooter.js";
import { ModelPicker } from "./overlays/ModelPicker.js";
import { PaneSwitcher } from "./overlays/PaneSwitcher.js";

// Strip Python Rich markup tags from text before rendering in terminal
// Handles: [bold], [/bold], [dim], [italic], [#hexcolor], [bold #color], [/] etc.
function stripRichMarkup(text: string): string {
  return text.replace(/\[\/?[^\]]*\]/g, "").replace(/  +/g, " ");
}

const TAB_DEFS = [
  { id: "chat", label: "Chat" },
  { id: "commands", label: "Commands" },
  { id: "agents", label: "Agents" },
  { id: "models", label: "Models" },
  { id: "evolution", label: "Evolution" },
  { id: "thinking", label: "Thinking" },
  { id: "tools", label: "Tools" },
  { id: "timeline", label: "Timeline" },
  { id: "sessions", label: "Sessions" },
  { id: "approvals", label: "Approvals" },
  { id: "mission", label: "Mission" },
  { id: "runtime", label: "Runtime" },
  { id: "repo", label: "Repo" },
  { id: "ontology", label: "Ontology" },
  { id: "control", label: "Control" },
] as const;

type TabId = (typeof TAB_DEFS)[number]["id"];

type OverlayState =
  | { kind: "none" }
  | { kind: "modelPicker"; selectedIndex: number }
  | { kind: "paneSwitcher"; selectedIndex: number };

type ChatLine = { id: string; kind: "system" | "user" | "assistant" | "thinking" | "tool" | "error"; text: string };

interface UIState {
  activeTabId: TabId;
  sidebarVisibility: SidebarVisibility;
  sidebarMode: SidebarMode;
  bridgeStatus: BridgeStatus;
  prompt: string;
  statusLine: string;
  overlay: OverlayState;
  chatLines: ChatLine[];
  nextChatId: number;
  live: LiveData;
  routeProvider: string;
  routeModel: string;
  bridgeRoutes: Array<{ id: string; label: string; provider: string; model: string; health: "ready" | "degraded" | "slow" | "unavailable" }>;
  tabData: Record<string, { lines: TranscriptLine[]; preview?: TabPreview }>;
  approvalQueue: ApprovalQueueState;
}

type UIAction =
  | { type: "tab.set"; id: TabId }
  | { type: "tab.next" }
  | { type: "tab.prev" }
  | { type: "sidebar.toggle" }
  | { type: "sidebar.mode.toggle" }
  | { type: "prompt.set"; value: string }
  | { type: "prompt.submit" }
  | { type: "prompt.backspace" }
  | { type: "prompt.append"; char: string }
  | { type: "overlay.open"; kind: "modelPicker" | "paneSwitcher" }
  | { type: "overlay.close" }
  | { type: "overlay.move"; delta: number }
  | { type: "overlay.select" }
  | { type: "bridge.status"; status: BridgeStatus }
  | { type: "bridge.event"; event: BridgeEvent }
  | { type: "live.update"; data: LiveData }
  | { type: "tab.replace"; tabId: string; lines: TranscriptLine[]; preview?: TabPreview }
  | { type: "bridge.model.set"; provider: string; model: string }
  | { type: "status.set"; value: string };

function reduceUI(state: UIState, action: UIAction): UIState {
  switch (action.type) {
    case "tab.set":
      return { ...state, activeTabId: action.id };
    case "tab.next": {
      const idx = TAB_DEFS.findIndex((t) => t.id === state.activeTabId);
      const next = (idx + 1) % TAB_DEFS.length;
      return { ...state, activeTabId: TAB_DEFS[next].id };
    }
    case "tab.prev": {
      const idx = TAB_DEFS.findIndex((t) => t.id === state.activeTabId);
      const prev = (idx - 1 + TAB_DEFS.length) % TAB_DEFS.length;
      return { ...state, activeTabId: TAB_DEFS[prev].id };
    }
    case "sidebar.toggle": {
      const cycle: SidebarVisibility[] = ["visible", "collapsed", "hidden"];
      const idx = cycle.indexOf(state.sidebarVisibility);
      return { ...state, sidebarVisibility: cycle[(idx + 1) % cycle.length] };
    }
    case "sidebar.mode.toggle":
      return { ...state, sidebarMode: state.sidebarMode === "dashboard" ? "detail" : "dashboard" };
    case "prompt.append":
      return { ...state, prompt: state.prompt + action.char };
    case "prompt.backspace":
      return { ...state, prompt: state.prompt.slice(0, -1) };
    case "prompt.submit": {
      const userLine: ChatLine = { id: `c${state.nextChatId}`, kind: "user", text: state.prompt };
      return {
        ...state,
        prompt: "",
        statusLine: `prompt sent → ${state.prompt.slice(0, 40)}`,
        chatLines: [...state.chatLines, userLine],
        nextChatId: state.nextChatId + 1,
      };
    }
    case "prompt.set":
      return { ...state, prompt: action.value };
    case "overlay.open":
      return { ...state, overlay: { kind: action.kind, selectedIndex: 0 } };
    case "overlay.close":
      return { ...state, overlay: { kind: "none" } };
    case "overlay.move": {
      if (state.overlay.kind === "none") return state;
      // Max is computed at render time; use a safe upper bound here
      const max = state.overlay.kind === "modelPicker" ? 20 : TAB_DEFS.length;
      const idx = state.overlay.selectedIndex + action.delta;
      return { ...state, overlay: { ...state.overlay, selectedIndex: Math.max(0, Math.min(max - 1, idx)) } };
    }
    case "overlay.select": {
      if (state.overlay.kind === "modelPicker") {
        // Model selection is handled via bridge.model.set (dispatched from useInput with bridgeSend)
        return { ...state, overlay: { kind: "none" } };
      }
      if (state.overlay.kind === "paneSwitcher") {
        const tab = TAB_DEFS[state.overlay.selectedIndex];
        return { ...state, overlay: { kind: "none" }, activeTabId: tab?.id ?? "chat" };
      }
      return state;
    }
    case "bridge.model.set":
      return {
        ...state,
        overlay: { kind: "none" },
        routeProvider: action.provider,
        routeModel: action.model,
        statusLine: `route → ${action.provider}:${action.model}`,
      };
    case "status.set":
      return { ...state, statusLine: action.value };
    case "bridge.status":
      return { ...state, bridgeStatus: action.status };
    case "bridge.event": {
      const evt = action.event;
      const t = String(evt.type ?? "");
      if (t === "bridge.ready") return { ...state, bridgeStatus: "connected", statusLine: "bridge connected" };
      if (t === "handshake.result") {
        const providers = Array.isArray(evt.providers) ? evt.providers : [];
        // Build route list from bridge's actual adapters
        const routes: UIState["bridgeRoutes"] = [];
        for (const p of providers) {
          if (typeof p !== "object" || p === null) continue;
          const pid = String((p as any).provider_id ?? "");
          const models = Array.isArray((p as any).models) ? (p as any).models : [];
          for (const m of models) {
            if (typeof m !== "object" || m === null) continue;
            const mid = String((m as any).id ?? (m as any).model_id ?? "");
            const label = String((m as any).display_name ?? mid);
            if (pid && mid) {
              routes.push({ id: `${pid}:${mid}`, label, provider: pid, model: mid, health: "ready" });
            }
          }
        }
        const claudeProv = providers.find((p: any) => typeof p === "object" && String(p.provider_id ?? "") === "claude") as any;
        const fallbackProv = providers.find((p: any) => typeof p === "object") as any;
        const prov = claudeProv ?? fallbackProv;
        const provider = String(prov?.provider_id ?? "claude");
        const model = String(prov?.default_model ?? "claude-sonnet-4-5");
        return { ...state, statusLine: `bridge ready | ${provider}:${model} | ${routes.length} models`, routeProvider: provider, routeModel: model, bridgeRoutes: routes };
      }
      if (t === "session.ack") {
        const sid = String(evt.session_id ?? "").slice(0, 12);
        return { ...state, statusLine: `session ${sid}… | ${String(evt.provider ?? "")}:${String(evt.model ?? "")}` };
      }
      if (t === "session.bootstrap.result") {
        return { ...state, statusLine: `bootstrap ready` };
      }
      if (t === "text_delta") {
        const content = stripRichMarkup(String(evt.content ?? evt.text ?? ""));
        if (!content) return state;
        const last = state.chatLines[state.chatLines.length - 1];
        if (last?.kind === "assistant") {
          const updated = [...state.chatLines];
          updated[updated.length - 1] = { ...last, text: last.text + content };
          return { ...state, chatLines: updated, statusLine: "streaming…" };
        }
        const newLine: ChatLine = { id: `c${state.nextChatId}`, kind: "assistant", text: content };
        return { ...state, chatLines: [...state.chatLines, newLine], nextChatId: state.nextChatId + 1, statusLine: "streaming…" };
      }
      if (t === "text_complete") {
        const content = stripRichMarkup(String(evt.content ?? ""));
        if (content) {
          const last = state.chatLines[state.chatLines.length - 1];
          if (last?.kind === "assistant") {
            const updated = [...state.chatLines];
            updated[updated.length - 1] = { ...last, text: last.text + content };
            return { ...state, chatLines: updated, statusLine: "response complete" };
          }
          const newLine: ChatLine = { id: `c${state.nextChatId}`, kind: "assistant", text: content };
          return { ...state, chatLines: [...state.chatLines, newLine], nextChatId: state.nextChatId + 1, statusLine: "response complete" };
        }
        return { ...state, statusLine: "response complete" };
      }
      if (t === "thinking_delta" || t === "thinking_complete") {
        const content = stripRichMarkup(String(evt.content ?? ""));
        if (!content) return state;
        const thinkLine: ChatLine = { id: `c${state.nextChatId}`, kind: "thinking", text: content };
        const thinkTabLine: TranscriptLine = { id: `t${state.nextChatId}`, kind: "thinking", text: content };
        const existingThinking = state.tabData.thinking?.lines ?? [];
        const newThinkingLines = [...existingThinking, thinkTabLine];
        const thinkStatus = t === "thinking_delta" ? "thinking..." : "thinking complete";
        return {
          ...state,
          chatLines: [...state.chatLines, thinkLine],
          nextChatId: state.nextChatId + 1,
          tabData: {
            ...state.tabData,
            thinking: { lines: newThinkingLines, preview: { Status: t === "thinking_complete" ? "complete" : "active" } },
          },
          statusLine: thinkStatus,
        };
      }
      if (t === "tool_call_complete") {
        const name = String(evt.tool_name ?? evt.name ?? evt.tool ?? "unknown");
        const args = evt.arguments ?? evt.args ?? evt.input;
        const argsStr = args ? ` ${typeof args === "string" ? args : JSON.stringify(args)}` : "";
        const toolLine: ChatLine = { id: `c${state.nextChatId}`, kind: "tool", text: `tool: ${name}` };
        const toolTabLine: TranscriptLine = { id: `tl${state.nextChatId}`, kind: "tool", text: `▶ ${name}${argsStr}` };
        const existingTools = state.tabData.tools?.lines ?? [];
        return {
          ...state,
          chatLines: [...state.chatLines, toolLine],
          nextChatId: state.nextChatId + 1,
          tabData: { ...state.tabData, tools: { lines: [...existingTools, toolTabLine], preview: { Status: "active" } } },
          statusLine: `tool: ${name}`,
        };
      }
      if (t === "tool_result") {
        const toolId = String(evt.tool_use_id ?? evt.tool_id ?? evt.id ?? "");
        const content = evt.content ?? evt.result ?? evt.output ?? "";
        const resultText = typeof content === "string" ? content : JSON.stringify(content);
        const preview = resultText.length > 120 ? resultText.slice(0, 120) + "…" : resultText;
        const toolResultLine: TranscriptLine = { id: `tr${state.nextChatId}`, kind: "system", text: `◀ ${toolId ? `[${toolId}] ` : ""}${preview}` };
        const existingTools = state.tabData.tools?.lines ?? [];
        return {
          ...state,
          nextChatId: state.nextChatId + 1,
          tabData: { ...state.tabData, tools: { lines: [...existingTools, toolResultLine], preview: { Status: "result" } } },
          statusLine: "tool result",
        };
      }
      if (t === "session_start") {
        return { ...state, statusLine: `session started | ${String(evt.model ?? "")}` };
      }
      if (t === "session_end") {
        return { ...state, statusLine: "session ended" };
      }
      if (t === "command.result") {
        const output = stripRichMarkup(String(evt.output ?? ""));
        const command = String(evt.command ?? "?");
        // Always render output in chat so the user sees it
        if (output) {
          const cmdLine: ChatLine = { id: `c${state.nextChatId}`, kind: "system", text: output };
          return { ...state, chatLines: [...state.chatLines, cmdLine], nextChatId: state.nextChatId + 1, statusLine: `/${command}` };
        }
        return { ...state, statusLine: `/${command}` };
      }
      if (t === "bridge.error" || t === "error") {
        const msg = String(evt.message ?? evt.code ?? "error");
        const errLine: ChatLine = { id: `c${state.nextChatId}`, kind: "error", text: `! ${msg}` };
        return { ...state, chatLines: [...state.chatLines, errLine], nextChatId: state.nextChatId + 1, statusLine: msg };
      }
      if (t === "workspace.snapshot.result") {
        const payload = workspaceSnapshotPayloadFromEvent(evt);
        const preview = payload
          ? workspacePayloadToPreview(payload)
          : workspaceSnapshotToPreview(String(evt.content ?? ""));
        const lines = workspacePreviewToLines(preview);
        return { ...state, tabData: { ...state.tabData, repo: { lines, preview } }, statusLine: "workspace loaded" };
      }
      if (t === "model.policy.result") {
        const payload = evt as Record<string, unknown>;
        const lines = modelPolicyToLines(payload);
        const preview = modelPolicyToPreview(payload);
        // Only update Models tab display — do NOT overwrite routeProvider/routeModel.
        // Route is set by handshake.result and explicit user model selection only.
        return {
          ...state,
          tabData: { ...state.tabData, models: { lines, preview } },
          statusLine: "models loaded",
        };
      }
      if (t === "runtime.snapshot.result") {
        const payload = runtimeSnapshotPayloadFromEvent(evt as Record<string, unknown>);
        const preview = payload
          ? runtimePayloadToPreview(payload)
          : runtimeSnapshotToPreview(String(evt.content ?? ""));
        const lines = runtimePreviewToLines(preview);
        return {
          ...state,
          tabData: {
            ...state.tabData,
            control: { lines, preview },
            runtime: { lines, preview },
          },
          statusLine: "runtime loaded",
        };
      }
      if (t === "agent.routes.result") {
        const payload = evt as Record<string, unknown>;
        const lines = agentRoutesToLines(payload);
        const preview = agentRoutesToPreview(payload);
        return { ...state, tabData: { ...state.tabData, agents: { lines, preview } }, statusLine: "agents loaded" };
      }
      if (t === "evolution.surface.result") {
        const payload = evt as Record<string, unknown>;
        const lines = evolutionSurfaceToLines(payload);
        const preview = evolutionSurfaceToPreview(payload);
        return { ...state, tabData: { ...state.tabData, evolution: { lines, preview } }, statusLine: "evolution loaded" };
      }
      if (t === "session.catalog.result") {
        const payload = evt as Record<string, unknown>;
        const lines = sessionCatalogToLines(payload);
        const preview = sessionCatalogToPreview(payload);
        return { ...state, tabData: { ...state.tabData, sessions: { lines, preview } }, statusLine: "sessions loaded" };
      }
      if (t === "session.detail.result") {
        const payload = evt as Record<string, unknown>;
        const lines = sessionDetailToLines(payload);
        const preview = sessionDetailToPreview(payload);
        return { ...state, tabData: { ...state.tabData, sessions: { lines, preview } }, statusLine: "session detail loaded" };
      }
      if (t === "permission.decision") {
        const decision = permissionDecisionFromEvent(evt as Record<string, unknown>);
        if (!decision) return state;
        const now = new Date().toISOString();
        const existing = state.approvalQueue.entriesByActionId[decision.action_id];
        const entry: ApprovalQueueEntry = existing
          ? { ...existing, lastSeenAt: now, seenCount: existing.seenCount + 1, lastSourceEventType: t, status: "pending", pending: true }
          : { decision, status: "pending", firstSeenAt: now, lastSeenAt: now, lastSourceEventType: t, seenCount: 1, pending: true };
        const order = decision.action_id in state.approvalQueue.entriesByActionId
          ? state.approvalQueue.order
          : [...state.approvalQueue.order, decision.action_id];
        const newQueue: ApprovalQueueState = { ...state.approvalQueue, entriesByActionId: { ...state.approvalQueue.entriesByActionId, [decision.action_id]: entry }, order };
        const lines = approvalPaneToLines(newQueue);
        const preview = approvalPaneToPreview(newQueue);
        return { ...state, approvalQueue: newQueue, tabData: { ...state.tabData, approvals: { lines, preview } }, statusLine: `approval: ${decision.tool_name} (${decision.risk})` };
      }
      if (t === "permission.resolution") {
        const resolution = permissionResolutionFromEvent(evt as Record<string, unknown>);
        if (!resolution) return state;
        const existing = state.approvalQueue.entriesByActionId[resolution.action_id];
        if (!existing) return state;
        const now = new Date().toISOString();
        const entry: ApprovalQueueEntry = { ...existing, resolution, status: resolution.resolution, pending: false, lastSeenAt: now, lastSourceEventType: t };
        const newQueue: ApprovalQueueState = { ...state.approvalQueue, entriesByActionId: { ...state.approvalQueue.entriesByActionId, [resolution.action_id]: entry } };
        const lines = approvalPaneToLines(newQueue);
        const preview = approvalPaneToPreview(newQueue);
        return { ...state, approvalQueue: newQueue, tabData: { ...state.tabData, approvals: { lines, preview } }, statusLine: `resolved: ${resolution.resolution}` };
      }
      if (t === "permission.outcome") {
        const outcome = permissionOutcomeFromEvent(evt as Record<string, unknown>);
        if (!outcome) return state;
        const existing = state.approvalQueue.entriesByActionId[outcome.action_id];
        if (!existing) return state;
        const now = new Date().toISOString();
        const entry: ApprovalQueueEntry = { ...existing, outcome, status: outcome.outcome, pending: false, lastSeenAt: now, lastSourceEventType: t };
        const newQueue: ApprovalQueueState = { ...state.approvalQueue, entriesByActionId: { ...state.approvalQueue.entriesByActionId, [outcome.action_id]: entry } };
        const lines = approvalPaneToLines(newQueue);
        const preview = approvalPaneToPreview(newQueue);
        return { ...state, approvalQueue: newQueue, tabData: { ...state.tabData, approvals: { lines, preview } }, statusLine: `outcome: ${outcome.outcome}` };
      }
      if (t === "permission.history.result") {
        const history = permissionHistoryFromEvent(evt as Record<string, unknown>);
        if (!history) return state;
        const entriesByActionId: Record<string, ApprovalQueueEntry> = {};
        const order: string[] = [];
        for (const entry of history.entries) {
          order.push(entry.action_id);
          entriesByActionId[entry.action_id] = {
            decision: entry.decision,
            status: entry.status,
            firstSeenAt: entry.first_seen_at,
            lastSeenAt: entry.last_seen_at,
            lastSourceEventType: "permission.history.result",
            seenCount: entry.seen_count,
            pending: entry.pending,
            resolution: entry.resolution ?? undefined,
            outcome: entry.outcome ?? undefined,
          };
        }
        const newQueue: ApprovalQueueState = { ...state.approvalQueue, entriesByActionId, order, historyBacked: true, lastHistorySyncAt: new Date().toISOString() };
        const lines = approvalPaneToLines(newQueue);
        const preview = approvalPaneToPreview(newQueue);
        return { ...state, approvalQueue: newQueue, tabData: { ...state.tabData, approvals: { lines, preview } }, statusLine: "approvals loaded" };
      }
      if (t === "command.graph.result") {
        const payload = evt as Record<string, unknown>;
        const lines = commandGraphToLines(payload);
        const preview = commandGraphToPreview(payload);
        return { ...state, tabData: { ...state.tabData, commands: { lines, preview } }, statusLine: "commands loaded" };
      }
      if (t === "command.registry.result") {
        const payload = evt as Record<string, unknown>;
        const registry = typeof payload.registry === "object" && payload.registry !== null
          ? (payload.registry as Record<string, unknown>)
          : payload;
        const commands = Array.isArray(registry.commands) ? registry.commands : [];
        const ts = Date.now();
        const registryLines: TranscriptLine[] = [
          { id: `reg-${ts}-0`, kind: "system", text: "# Command Registry" },
          { id: `reg-${ts}-1`, kind: "system", text: `Registered commands: ${commands.length}` },
          ...commands.map((c: unknown, i: number) => {
            const cmd = typeof c === "object" && c !== null ? (c as Record<string, unknown>) : {};
            return { id: `reg-${ts}-${i + 2}`, kind: "system" as const, text: `/${String(cmd.name ?? c)} — ${String(cmd.description ?? "")}` };
          }),
        ];
        const regPreview: TabPreview = { Registered: String(commands.length) };
        const existing = state.tabData.commands;
        const mergedLines = existing ? [...existing.lines, ...registryLines] : registryLines;
        const mergedPreview: TabPreview = existing?.preview ? { ...existing.preview, ...regPreview } : regPreview;
        return { ...state, tabData: { ...state.tabData, commands: { lines: mergedLines, preview: mergedPreview } }, statusLine: "command registry loaded" };
      }
      if (t === "ontology.snapshot.result") {
        const payload = evt as Record<string, unknown>;
        const content = typeof payload.content === "string" ? payload.content : "";
        const ts = Date.now();
        const ontLines: TranscriptLine[] = content
          .split("\n")
          .map((line, i) => ({ id: `ont-${ts}-${i}`, kind: "system" as const, text: line }));
        const ontPreview: TabPreview = { Status: "loaded" };
        return { ...state, tabData: { ...state.tabData, ontology: { lines: ontLines, preview: ontPreview } }, statusLine: "ontology loaded" };
      }
      return state;
    }
    case "live.update":
      return { ...state, live: action.data };
    case "tab.replace":
      return { ...state, tabData: { ...state.tabData, [action.tabId]: { lines: action.lines, preview: action.preview } } };
    default:
      return state;
  }
}

const MOCK_ROUTES = [
  { id: "r1", label: "Claude Sonnet 4.5", provider: "claude", model: "claude-sonnet-4-5", health: "ready" as const },
  { id: "r2", label: "GLM-5 (Ollama Cloud)", provider: "ollama", model: "glm-5:cloud", health: "ready" as const },
  { id: "r3", label: "Codex 5.4", provider: "codex", model: "gpt-5.4", health: "ready" as const },
  { id: "r4", label: "DeepSeek v3.2 (Ollama Cloud)", provider: "ollama", model: "deepseek-v3.2:cloud", health: "ready" as const },
  { id: "r5", label: "MiMo V2 Pro (OpenRouter)", provider: "openrouter", model: "xiaomi/mimo-v2-pro", health: "ready" as const },
];

const SEED_CHAT: ChatLine[] = [
  { id: "c0", kind: "system", text: "DHARMA COMMAND v2 — operator shell ready" },
];

const INITIAL_STATE: UIState = {
  activeTabId: "chat",
  sidebarVisibility: "visible",
  sidebarMode: "dashboard",
  bridgeStatus: "booting",
  prompt: "",
  statusLine: "connecting to bridge…",
  overlay: { kind: "none" },
  chatLines: SEED_CHAT,
  nextChatId: 1,
  live: { overview: null, agents: [], profiles: [], dharma: null, connected: false, lastFetch: 0 },
  routeProvider: "claude",
  routeModel: "claude-sonnet-4-5",
  bridgeRoutes: [],
  tabData: {},
  approvalQueue: { entriesByActionId: {}, order: [], historyBacked: false },
};

const TAB_SHORTCUTS: Record<string, TabId> = {
  g: "chat",
  r: "repo",
  o: "ontology",
  t: "control",
  a: "agents",
  e: "evolution",
  h: "thinking",
  j: "tools",
  n: "timeline",
};

export function App({ initialLive }: { initialLive?: LiveData }) {
  const { exit } = useApp();
  const { stdout } = useStdout();
  const [state, dispatch] = useReducer(reduceUI, INITIAL_STATE);
  const stateRef = useRef(state);
  stateRef.current = state;
  const pendingBootstraps = useRef<Record<string, { prompt: string; provider: string; model: string }>>({});

  const handleBridgeEvent = useCallback((event: BridgeEvent) => {
    const t = String(event.type ?? "");
    // Handle session.bootstrap.result → route by intent or default to session.start
    if (t === "session.bootstrap.result") {
      const requestId = String(event.request_id ?? "");
      const pending = pendingBootstraps.current[requestId];
      if (pending) {
        const intentRaw = event.intent as { kind?: string; auto_execute?: boolean; command?: string; target_tab?: string; provider?: string; model?: string; strategy?: string } | undefined;
        const intentKind = String(intentRaw?.kind ?? "");
        if (intentKind === "command" && intentRaw?.auto_execute) {
          // Bridge detected a slash command intent — auto-execute it
          const command = String(intentRaw.command ?? "");
          if (command) {
            bridgeSendRef.current("command.run", { command });
            const targetTab = String(intentRaw.target_tab ?? "");
            if (targetTab && TAB_DEFS.some((td) => td.id === targetTab)) {
              dispatch({ type: "tab.set", id: targetTab as TabId });
            }
          }
        } else if (intentKind === "model_switch") {
          // Bridge detected a model switch intent — update route
          const provider = String(intentRaw?.provider ?? pending.provider);
          const model = String(intentRaw?.model ?? pending.model);
          const strategy = String(intentRaw?.strategy ?? "responsive");
          bridgeSendRef.current("action.run", { action_type: "model.set", provider, model, strategy });
          dispatch({ type: "bridge.model.set", provider, model });
        } else if (intentKind === "agent") {
          // Bridge detected an agent intent — show agents tab and refresh routes
          dispatch({ type: "tab.set", id: "agents" });
          bridgeSendRef.current("agent.routes", { provider: pending.provider, model: pending.model });
        } else {
          // Default: proceed with normal chat session
          bridgeSendRef.current("session.start", {
            provider: pending.provider,
            model: pending.model,
            prompt: pending.prompt,
            bootstrap: event,
            system_prompt: String(event.system_prompt ?? ""),
          });
        }
        delete pendingBootstraps.current[requestId];
      }
    }
    // Handle handshake.result → authoritative resync
    if (t === "handshake.result") {
      const providers = Array.isArray(event.providers) ? event.providers : [];
      const claudeProv = providers.find((p: unknown) => typeof p === "object" && p !== null && String((p as any).provider_id ?? "") === "claude") as Record<string, unknown> | undefined;
      const fallbackProv = providers.find((p: unknown) => typeof p === "object" && p !== null) as Record<string, unknown> | undefined;
      const prov = claudeProv ?? fallbackProv;
      const provider = String(prov?.provider_id ?? "claude");
      const model = String(prov?.default_model ?? "claude-sonnet-4-5");
      requestAuthoritativeResync(bridgeSendRef.current, provider, model, "responsive");
    }
    // On permission.decision, refresh history to get authoritative state
    if (t === "permission.decision") {
      requestPermissionHistory(bridgeSendRef.current);
    }
    // On session_end, refresh live surfaces and session catalog
    if (t === "session_end") {
      const s = stateRef.current;
      requestLiveSnapshots(bridgeSendRef.current, s.routeProvider, s.routeModel, "responsive");
      requestSessionCatalog(bridgeSendRef.current);
    }
    dispatch({ type: "bridge.event", event });
  }, []);

  const { status: bridgeStatus, send: bridgeSend } = useBridge({
    onEvent: handleBridgeEvent,
    enabled: true,
  });
  const bridgeSendRef = useRef(bridgeSend);
  bridgeSendRef.current = bridgeSend;

  const submitPrompt = useCallback((prompt: string) => {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    const s = stateRef.current;
    if (trimmed.startsWith("/")) {
      // Slash command
      bridgeSend("command.run", { command: trimmed });
    } else {
      // Chat prompt → session.bootstrap → session.start
      const requestId = bridgeSend("session.bootstrap", {
        provider: s.routeProvider,
        model: s.routeModel,
        strategy: "responsive",
        prompt: trimmed,
        active_tab: s.activeTabId,
      });
      pendingBootstraps.current[requestId] = {
        prompt: trimmed,
        provider: s.routeProvider,
        model: s.routeModel,
      };
    }
  }, [bridgeSend]);

  // Apply initial live data fetched before render (top-level await in index.tsx)
  const appliedInitial = React.useRef(false);
  useEffect(() => {
    if (!appliedInitial.current && initialLive && initialLive.lastFetch > 0) {
      appliedInitial.current = true;
      dispatch({ type: "live.update", data: initialLive });
    }
  }, []);

  // Periodic snapshot refresh — every 15s when bridge is connected
  useEffect(() => {
    if (bridgeStatus !== "connected") return;
    const id = setInterval(() => {
      const s = stateRef.current;
      requestLiveSnapshots(bridgeSendRef.current, s.routeProvider, s.routeModel, "responsive");
    }, 15000);
    return () => clearInterval(id);
  }, [bridgeStatus]);

  // Dispatch a pane action (refresh / primary / secondary / tertiary) for the active tab
  const dispatchPaneAction = useCallback((actionKey: "refresh" | "primary" | "secondary" | "tertiary") => {
    const s = stateRef.current;
    const syntheticState = {
      routePolicy: {
        provider: s.routeProvider,
        model: s.routeModel,
        routeId: `${s.routeProvider}:${s.routeModel}`,
        strategy: "responsive",
        routeState: "ready" as const,
        selectable: true,
        fallbackChain: [],
        targets: [],
      },
      sessionPane: { selectedSessionId: undefined, detailsBySessionId: {} },
      approvalPane: s.approvalQueue,
    } as unknown as AppState;
    const actions = paneActionsFor(s.activeTabId, syntheticState, {
      sessionCatalogLimit: 12,
      approvalResolveAction: (entry, resolution, label) => ({
        label,
        summary: `${label} ${entry.decision.tool_name}`,
        requestType: "permission.resolve",
        payload: { action_id: entry.decision.action_id, resolution },
      }),
    });
    const action = actions[actionKey];
    if (!action) return;
    const { requestType, payload } = action;
    if (requestType) {
      bridgeSendRef.current(requestType, payload);
    } else if (payload.action_type === "command.run") {
      bridgeSendRef.current("command.run", { command: String(payload.command ?? "") });
    } else {
      bridgeSendRef.current("action.run", payload);
    }
    dispatch({ type: "status.set", value: `→ ${action.summary}` });
  }, []);

  const live = state.live;
  const activeTab = TAB_DEFS.find((t) => t.id === state.activeTabId) ?? TAB_DEFS[0];
  const compact = (stdout?.columns ?? 120) < 100;
  const effectiveBridgeStatus = bridgeStatus === "connected" ? "connected" : state.bridgeStatus;

  useInput((input, key) => {
    if (input === "q" && state.prompt === "" && state.overlay.kind === "none") { exit(); return; }
    if (key.ctrl && input === "c") { exit(); return; }

    // Overlay mode — intercept all keys
    if (state.overlay.kind !== "none") {
      if (key.escape || (input === "q")) { dispatch({ type: "overlay.close" }); return; }
      if (input === "j" || key.downArrow) { dispatch({ type: "overlay.move", delta: 1 }); return; }
      if (input === "k" || key.upArrow) { dispatch({ type: "overlay.move", delta: -1 }); return; }
      if (key.return) {
        if (state.overlay.kind === "modelPicker") {
          const routes = state.bridgeRoutes.length > 0 ? state.bridgeRoutes : (liveRoutes.length > 0 ? liveRoutes : MOCK_ROUTES);
          const route = routes[state.overlay.selectedIndex];
          if (route) {
            bridgeSend("action.run", { action_type: "model.set", provider: route.provider, model: route.model, strategy: "responsive" });
            dispatch({ type: "bridge.model.set", provider: route.provider, model: route.model });
          } else {
            dispatch({ type: "overlay.close" });
          }
        } else {
          dispatch({ type: "overlay.select" });
        }
        return;
      }
      // Direct number select for model picker
      if (state.overlay.kind === "modelPicker" && /^[1-9]$/.test(input)) {
        const idx = parseInt(input, 10) - 1;
        const routes = state.bridgeRoutes.length > 0 ? state.bridgeRoutes : (liveRoutes.length > 0 ? liveRoutes : MOCK_ROUTES);
        if (idx < routes.length) {
          const route = routes[idx];
          bridgeSend("action.run", { action_type: "model.set", provider: route.provider, model: route.model, strategy: "responsive" });
          dispatch({ type: "bridge.model.set", provider: route.provider, model: route.model });
        }
        return;
      }
      return; // Swallow all other keys in overlay mode
    }

    // Tab navigation
    if (key.tab && !key.shift) { dispatch({ type: "tab.next" }); return; }
    if (key.tab && key.shift) { dispatch({ type: "tab.prev" }); return; }
    if (key.leftArrow && key.ctrl) { dispatch({ type: "tab.prev" }); return; }
    if (key.rightArrow && key.ctrl) { dispatch({ type: "tab.next" }); return; }

    // Ctrl shortcuts
    if (key.ctrl) {
      if (input === "p") { dispatch({ type: "overlay.open", kind: "modelPicker" }); return; }
      if (input === "k") { dispatch({ type: "overlay.open", kind: "paneSwitcher" }); return; }
      if (input === "b") { dispatch({ type: "sidebar.toggle" }); return; }
      if (input === "d") { dispatch({ type: "sidebar.mode.toggle" }); return; }
      if (input === "l") { dispatchPaneAction("refresh"); return; }
      if (input === "x") { dispatchPaneAction("primary"); return; }
      if (input === "f") { dispatchPaneAction("secondary"); return; }
      if (input === "v") { dispatchPaneAction("tertiary"); return; }
      if (TAB_SHORTCUTS[input]) { dispatch({ type: "tab.set", id: TAB_SHORTCUTS[input] }); return; }
    }

    // Prompt input
    if (key.return && state.prompt.length > 0) {
      submitPrompt(state.prompt);
      dispatch({ type: "prompt.submit" });
      return;
    }
    if (key.backspace || key.delete) { dispatch({ type: "prompt.backspace" }); return; }
    if (input && !key.ctrl && !key.meta && input.length === 1) {
      dispatch({ type: "prompt.append", char: input });
    }
  });

  const ov = live.overview;
  const routeLabel = `${state.routeProvider}:${state.routeModel}`;
  const hints = compact
    ? "Tab ←→ │ ^B side │ ^P route │ q quit"
    : "Tab/←→ switch │ Enter send │ ^P route │ ^K panes │ ^B sidebar │ ^D ctx mode │ q quit";

  const uptimeMin = ov ? Math.round(ov.uptime_seconds / 60) : 0;
  const summaryItems = [
    { label: "agents", value: `${ov?.agent_count ?? "?"}`, color: colors.content },
    { label: "tasks", value: `${ov?.tasks_running ?? 0} run / ${ov?.tasks_pending ?? 0} pend`, color: ov?.tasks_running ? colors.attention : colors.positive },
    { label: "fitness", value: ov?.mean_fitness ? ov.mean_fitness.toFixed(2) : "—", color: colors.content },
    { label: "health", value: ov?.health_status ?? "?", color: ov?.health_status === "healthy" ? colors.positive : colors.caution },
    { label: "uptime", value: `${uptimeMin}m`, color: colors.structure },
  ];

  const liveRoutes = useMemo(() =>
    live.profiles.map((p, i) => ({
      id: p.id ?? `p${i}`,
      label: p.label,
      provider: p.provider,
      model: p.model,
      health: (p.available ? "ready" : "unavailable") as "ready" | "degraded" | "slow" | "unavailable",
    })),
  [live.profiles]);

  const liveAgents = useMemo(() =>
    live.agents.map((a) => ({
      id: a.name,
      name: a.display_name ?? a.name,
      role: a.role ?? "agent",
      status: (a.status === "busy" ? "busy" : a.status === "dead" ? "dead" : "idle") as "busy" | "idle" | "dead",
      provider: a.provider,
      model: a.model_label ?? a.model,
      tasksCompleted: a.tasks_completed ?? 0,
    })),
  [live.agents]);

  const dashboardGroups = [
    {
      title: "System",
      fields: [
        { label: "agents", value: `${ov?.agent_count ?? "?"}` },
        { label: "tasks", value: `${ov?.task_count ?? "?"}` },
        { label: "health", value: ov?.health_status ?? "?", color: ov?.health_status === "healthy" ? colors.positive : colors.caution },
      ],
    },
    {
      title: "Dharma",
      fields: [
        { label: "kernel", value: live.dharma?.kernel_integrity ? "✓ intact" : "✕ broken", color: live.dharma?.kernel_integrity ? colors.positive : colors.alarm },
        { label: "axioms", value: `${live.dharma?.kernel_axioms ?? "?"}` },
        { label: "stigm", value: `${live.dharma?.stigmergy_density ?? ov?.stigmergy_density ?? "?"}` },
      ],
    },
    {
      title: "Route",
      fields: live.profiles.length > 0
        ? [
            { label: "model", value: live.profiles[0].model.split("/").pop() ?? "?" },
            { label: "via", value: live.profiles[0].provider },
            { label: "status", value: live.profiles[0].available ? "● ready" : "✕ off", color: live.profiles[0].available ? colors.positive : colors.alarm },
          ]
        : [{ label: "status", value: "no profiles", color: colors.caution }],
    },
  ];

  return (
    <Box flexDirection="column" height="100%">
      <ShellHeader
        bridgeStatus={effectiveBridgeStatus}
        routeLabel={routeLabel}
        activeTabLabel={activeTab.label}
      />
      {!compact && <OperatorSummaryBand items={summaryItems} />}
      <TabBar tabs={[...TAB_DEFS]} activeTabId={state.activeTabId} maxVisible={compact ? 6 : 12} />

      <Box flexGrow={1}>
        <Sidebar
          visibility={state.sidebarVisibility}
          mode={state.sidebarMode}
          dashboardGroups={dashboardGroups}
          detailLines={["branch main", "dirty 0", "loop IDLE", "verify 3/3"]}
          activeTabLabel={activeTab.label}
        />
        <MainPane
          activeTabId={state.activeTabId}
          activeTabLabel={activeTab.label}
          termHeight={stdout?.rows ?? 40}
          compact={compact}
          chatLines={state.chatLines}
          liveAgents={liveAgents}
          liveOverview={ov ?? undefined}
          liveDharma={live.dharma ?? undefined}
          tabData={state.tabData}
        />
      </Box>

      {state.overlay.kind === "modelPicker" && (
        <ModelPicker routes={state.bridgeRoutes.length > 0 ? state.bridgeRoutes : (liveRoutes.length > 0 ? liveRoutes : MOCK_ROUTES)} selectedIndex={state.overlay.selectedIndex} />
      )}
      {state.overlay.kind === "paneSwitcher" && (
        <PaneSwitcher tabs={[...TAB_DEFS]} selectedIndex={state.overlay.selectedIndex} />
      )}

      <Composer prompt={state.prompt} active={state.activeTabId === "chat"} />
      <StatusFooter statusLine={state.statusLine} routeLabel={routeLabel} hints={hints} />
    </Box>
  );
}
