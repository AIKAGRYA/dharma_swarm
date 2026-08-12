import type {ActivityEntry, ActivityPhase, CanonicalExecutionEvent, PaneKind, TranscriptLine} from "./types";
import {stripHelmDirectives} from "./uiIntents";
import {normalizeCommandOutcome, type CommandOutcome} from "./commandOutcome";
import {
  cancellationAckFromEvent,
  permissionDecisionFromEvent,
  permissionOutcomeFromEvent,
  permissionResolutionFromEvent,
  isCancelledSessionEnd,
  resolveEventActionType,
  resolveEventCommand,
  resolveEventOutput,
} from "./protocol";

const EXECUTION_EVENT_RETENTION = 4000;
const CHAT_TURN_RETENTION = 200;
const CHAT_TRACE_LINE_RETENTION = 4000;
const PANE_LINE_RETENTION = 1000;
const ACTIVITY_ENTRY_RETENTION = 1000;

function line(kind: TranscriptLine["kind"], text: string, timestamp?: string): TranscriptLine {
  return {
    id: `${kind}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    kind,
    text,
    timestamp,
  };
}

function activity(
  kind: ActivityEntry["kind"],
  event: CanonicalExecutionEvent,
  summary?: string,
  detail?: string[],
): ActivityEntry {
  return {
    id: event.id,
    kind,
    title: event.title,
    phase: event.phase,
    summary: summary ?? event.summary,
    detail: detail ?? event.detail,
    raw: event.raw,
    timestamp: event.timestamp,
    correlationId: event.correlationId,
  };
}

function compactText(value: string, maxLength = 88): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength - 1)}…` : normalized;
}

function detailLines(value: unknown): string[] {
  if (typeof value === "string") {
    return value
      .split("\n")
      .map((lineText) => lineText.trimEnd())
      .filter((lineText) => lineText.length > 0);
  }
  try {
    return JSON.stringify(value, null, 2)
      .split("\n")
      .map((lineText) => lineText.trimEnd());
  } catch {
    return [String(value)];
  }
}

function phaseForTask(type: string): ActivityPhase {
  if (type === "task_complete") {
    return "complete";
  }
  if (type === "task_started") {
    return "queued";
  }
  return "running";
}

function timestampFromEvent(event: Record<string, unknown>): string | undefined {
  const timestamp = String(event.timestamp ?? event.created_at ?? "").trim();
  return timestamp || undefined;
}

function canonicalEvent(
  event: Record<string, unknown>,
  partial: Omit<CanonicalExecutionEvent, "id" | "raw">,
): CanonicalExecutionEvent {
  const sourceId = String(event.id ?? event.tool_call_id ?? event.action_id ?? event.task_id ?? event.request_id ?? event.type ?? "event");
  return {
    id: `${partial.kind}:${sourceId}:${String(event.created_at ?? event.timestamp ?? "")}:${String(event.content ?? event.summary ?? partial.title).slice(0, 24)}`,
    raw: event,
    ...partial,
  };
}

export function userPromptExecutionEvent(prompt: string, timestamp = new Date().toISOString()): CanonicalExecutionEvent {
  const content = prompt;
  return {
    id: `user_prompt:${timestamp}:${content.trim().slice(0, 24)}`,
    sourceEventType: "user_prompt",
    kind: "user_prompt",
    phase: "complete",
    title: compactText(content.trim() || "prompt"),
    content,
    timestamp,
    raw: {prompt: content, created_at: timestamp},
  };
}

export function localStatusExecutionEvent(
  title: string,
  summary?: string,
  phase: ActivityPhase = "queued",
  timestamp = new Date().toISOString(),
): CanonicalExecutionEvent {
  return {
    id: `status:${timestamp}:${title.slice(0, 24)}`,
    sourceEventType: "local_status",
    kind: "status",
    phase,
    title,
    summary,
    timestamp,
    raw: {title, summary, created_at: timestamp, source: "local"},
  };
}

// F-157: a prompt submitted while the bridge is offline renders as an explicit queued
// state — no optimistic trace steps, never a perpetual running glyph. The stable id
// (status:queued:<queueId>) lets the dispatch/failure resolution replace the queued
// event in place once the bridge connects, so the turn never holds a third silent state.
export type QueuedPromptResolution = "dispatched" | "failed";

export function queuedPromptExecutionEvent(
  queueId: string,
  resolution?: QueuedPromptResolution,
  timestamp = new Date().toISOString(),
): CanonicalExecutionEvent {
  const phase: ActivityPhase = resolution === "dispatched" ? "complete" : resolution === "failed" ? "failed" : "queued";
  const title =
    resolution === "dispatched"
      ? "dispatched to backend"
      : resolution === "failed"
        ? "dispatch failed after reconnect"
        : "queued (backend offline)";
  return {
    id: `status:queued:${queueId}`,
    sourceEventType: "local_status",
    kind: "status",
    phase,
    title,
    timestamp,
    raw: {title, created_at: timestamp, source: "local", queued_offline: true, queue_resolution: resolution ?? "pending"},
  };
}

// F-158: a slash command handled entirely client-side (e.g. the bare /model picker)
// still leaves a completed transcript turn — this local result event closes the echoed
// command turn so it never sits in a perpetual running state.
export function localCommandResultExecutionEvent(
  command: string,
  summary: string,
  timestamp = new Date().toISOString(),
  outcome: CommandOutcome = "completed",
): CanonicalExecutionEvent {
  const normalized = normalizeCommandOutcome({
    outcome,
    ok: outcome === "completed" || outcome === "accepted",
    supported: outcome === "completed" || outcome === "accepted",
    completed: outcome === "completed",
  });
  return {
    id: `command:local:${timestamp}:${command.slice(0, 24)}`,
    sourceEventType: "local_command_result",
    kind: "command",
    phase: normalized.phase,
    title: `intent ${command}`,
    summary,
    content: summary,
    detail: [`Command: ${command}`],
    timestamp,
    raw: {
      command,
      summary,
      outcome,
      ok: outcome === "completed" || outcome === "accepted",
      supported: outcome === "completed" || outcome === "accepted",
      completed: outcome === "completed",
      created_at: timestamp,
      source: "local",
    },
  };
}

export function canonicalEventsFromBridgeEvent(event: Record<string, unknown>): CanonicalExecutionEvent[] {
  const type = String(event.type ?? "");

  if (type === "text_delta" || type === "text_complete") {
    const content = String(event.content ?? "");
    if (!content.trim()) {
      return [];
    }
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "assistant_text",
        phase: type === "text_complete" ? "complete" : "running",
        title: compactText(content),
        content,
        timestamp: timestampFromEvent(event),
      }),
    ];
  }

  // F-173: identity/memory intent answers arrive as {type:"assistant", request_id, message}
  // (bridge_events.md §1.16); without this branch the answer text is silently discarded.
  // The wire shape carries no timestamp, so the id keys on request_id for distinctness.
  if (type === "assistant") {
    const content = String(event.message ?? "");
    if (!content.trim()) {
      return [];
    }
    return [
      {
        id: `assistant_text:assistant:${String(event.request_id ?? "").trim()}:${content.slice(0, 24)}`,
        raw: event,
        sourceEventType: type,
        kind: "assistant_text",
        phase: "complete",
        title: compactText(content),
        content,
        timestamp: timestampFromEvent(event),
      },
    ];
  }

  if (type === "thinking_delta" || type === "thinking_complete") {
    const content = String(event.content ?? "");
    if (!content.trim()) {
      return [];
    }
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "thinking",
        phase: type === "thinking_complete" ? "complete" : "running",
        title: compactText(content),
        content,
        detail: detailLines(content),
        timestamp: timestampFromEvent(event),
      }),
    ];
  }

  if (type === "tool_call_complete") {
    const toolName = String(event.tool_name ?? "tool");
    const argumentsText = String(event.arguments ?? "").trim();
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "tool_call",
        phase: "running",
        title: toolName,
        summary: compactText(argumentsText || toolName),
        content: argumentsText,
        detail: [`Tool: ${toolName}`, ...detailLines(argumentsText || "no arguments")],
        timestamp: timestampFromEvent(event),
        correlationId: String(event.tool_call_id ?? "").trim() || undefined,
      }),
    ];
  }

  if (type === "tool_result") {
    const toolName = String(event.tool_name ?? "tool");
    const content = String(event.content ?? "").trim();
    const failed =
      event.success === false ||
      Boolean(event.error) ||
      Boolean(event.error_message) ||
      String(event.status ?? "").toLowerCase() === "failed";
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "tool_result",
        phase: failed ? "failed" : "complete",
        title: toolName,
        summary: compactText(content || "no output"),
        content,
        detail: [`Tool: ${toolName}`, ...detailLines(content || "no output")],
        timestamp: timestampFromEvent(event),
        correlationId: String(event.tool_call_id ?? "").trim() || undefined,
      }),
    ];
  }

  if (type === "permission.decision") {
    const decision = permissionDecisionFromEvent(event);
    if (!decision) {
      return [];
    }
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "approval",
        phase: decision.decision === "require_approval" ? "queued" : "complete",
        title: `${decision.tool_name} requires ${decision.decision}`,
        summary: `${decision.risk} | ${decision.action_id}`,
        detail: [`Risk: ${decision.risk}`, `Rationale: ${decision.rationale}`, `Policy: ${decision.policy_source}`],
        timestamp: String(decision.metadata.created_at ?? "").trim() || timestampFromEvent(event),
        correlationId: decision.action_id,
      }),
    ];
  }

  if (type === "permission.resolution") {
    const resolution = permissionResolutionFromEvent(event);
    if (!resolution) {
      return [];
    }
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "approval",
        phase: "complete",
        title: `resolution ${resolution.resolution}`,
        summary: `${resolution.action_id} | ${resolution.enforcement_state}`,
        detail: [`Action: ${resolution.action_id}`, `Enforcement: ${resolution.enforcement_state}`, ...(resolution.note ? [`Note: ${resolution.note}`] : [])],
        timestamp: resolution.resolved_at,
        correlationId: resolution.action_id,
      }),
    ];
  }

  if (type === "permission.outcome") {
    const outcome = permissionOutcomeFromEvent(event);
    if (!outcome) {
      return [];
    }
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "approval",
        phase: outcome.outcome === "runtime_record_failed" || outcome.outcome === "runtime_rejected" || outcome.outcome === "runtime_expired" ? "failed" : "complete",
        title: `runtime ${outcome.outcome}`,
        summary: `${outcome.action_id} | ${outcome.source}`,
        detail: [`Action: ${outcome.action_id}`, `Source: ${outcome.source}`, `Summary: ${outcome.summary}`],
        timestamp: outcome.outcome_at,
        correlationId: outcome.action_id,
      }),
    ];
  }

  if (type === "task_started" || type === "task_progress" || type === "task_complete") {
    const taskId = String(event.task_id ?? "task");
    const status = String(event.status ?? type.replace("task_", ""));
    const summary = compactText(String(event.summary ?? event.message ?? status));
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "task",
        phase: phaseForTask(type),
        title: `${taskId} ${status}`,
        summary,
        detail: detailLines(event),
        timestamp: timestampFromEvent(event),
        correlationId: taskId,
      }),
    ];
  }

  if (type === "command.result" || (type === "action.result" && resolveEventActionType(event) === "command.run")) {
    const command = resolveEventCommand(event);
    const output = resolveEventOutput(event).trim();
    const summary = String(event.summary ?? "").trim();
    const outcome = normalizeCommandOutcome(event);
    if (!command && !summary && !output) {
      return [];
    }
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "command",
        phase: outcome.phase,
        title: command ? `intent ${command}` : "command result",
        summary: compactText(summary || output || outcome.outcome),
        content: output || outcome.outcome,
        detail: [...(command ? [`Command: ${command}`] : []), `Outcome: ${outcome.outcome}`],
        timestamp: timestampFromEvent(event),
        correlationId: String(event.request_id ?? event.id ?? "").trim() || undefined,
      }),
    ];
  }

  const cancellationAck = cancellationAckFromEvent(event);
  if (cancellationAck) {
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "status",
        phase: cancellationAck.cancelled ? "complete" : "failed",
        title: cancellationAck.cancelled ? "cancellation accepted" : "cancellation rejected",
        summary: cancellationAck.reasonLabel,
        detail: [
          `Target request ${cancellationAck.targetRequestId ?? "missing"}`,
          `Session ${cancellationAck.sessionId ?? "none"}`,
        ],
        timestamp: timestampFromEvent(event),
        correlationId: cancellationAck.targetRequestId,
      }),
    ];
  }

  if (type === "bridge.ready" || type === "handshake.result" || type === "session_end") {
    const cancelled = isCancelledSessionEnd(event);
    const failedSessionEnd = type === "session_end" && (cancelled || event.success !== true);
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "status",
        phase: failedSessionEnd ? "failed" : "complete",
        title:
          type === "bridge.ready"
            ? "bridge process ready"
            : type === "handshake.result"
              ? "bridge handshake complete"
              : cancelled
                ? "session cancelled"
                : `session ${event.success === false ? "failed" : "ended"}`,
        summary: type === "session_end" ? String(event.session_id ?? "").trim() || undefined : undefined,
        detail:
          type === "session_end"
            ? [
                `Request ${String(event.request_id ?? "").trim() || "pending"}`,
                cancelled ? "Turn cancelled" : event.success === false ? "Turn failed" : "Turn completed",
              ]
            : undefined,
        timestamp: timestampFromEvent(event),
        correlationId: type === "session_end" ? String(event.request_id ?? "").trim() || undefined : undefined,
      }),
    ];
  }

  if (type === "session.bootstrap.result" || type === "session.ack") {
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "status",
        phase: "complete",
        title: type === "session.bootstrap.result" ? "bootstrap ready" : "session acknowledged",
        summary:
          type === "session.ack"
            ? `${String(event.provider ?? "").trim()}:${String(event.model ?? "").trim()}`.replace(/^:/, "") || undefined
            : undefined,
        detail:
          type === "session.bootstrap.result"
            ? ["Context packet prepared", `Request ${String(event.request_id ?? "").trim() || "pending"}`]
            : [
                `Session ${String(event.session_id ?? "").trim() || "pending"}`,
                `${String(event.provider ?? "").trim()}:${String(event.model ?? "").trim()}`.replace(/^:/, "") || "route pending",
              ],
        timestamp: timestampFromEvent(event),
      }),
    ];
  }

  if (type === "error" || type === "bridge.error") {
    return [
      canonicalEvent(event, {
        sourceEventType: type,
        kind: "error",
        phase: "failed",
        title: String(event.message ?? event.code ?? "error"),
        detail: detailLines(event),
        timestamp: timestampFromEvent(event),
      }),
    ];
  }

  return [];
}

export function mergeExecutionEvents(current: CanonicalExecutionEvent[], incoming: CanonicalExecutionEvent[]): CanonicalExecutionEvent[] {
  const next = [...current];
  for (const event of incoming) {
    const existingIndex = next.findIndex((candidate) => candidate.id === event.id);
    if (existingIndex >= 0) {
      next[existingIndex] = event;
      continue;
    }
    next.push(event);
  }
  return next.slice(-EXECUTION_EVENT_RETENTION);
}

function stepGlyph(phase: ActivityPhase): string {
  if (phase === "failed") {
    return "!";
  }
  if (phase === "complete") {
    return "✓";
  }
  if (phase === "queued") {
    return "○";
  }
  return "⠋";
}

function stepLabel(event: CanonicalExecutionEvent): string {
  switch (event.kind) {
    case "thinking":
      return "Reasoning";
    case "tool_call":
    case "tool_result":
      return "Tool";
    case "approval":
      return "Approval";
    case "task":
      return "Task";
    case "command":
      return "Command";
    case "status":
      return "Status";
    case "error":
      return "Error";
    default:
      return "Trace";
  }
}

function rawLines(raw: Record<string, unknown> | undefined): string[] {
  if (!raw) {
    return [];
  }
  return JSON.stringify(raw, null, 2)
    .split("\n")
    .map((entry) => entry.trimEnd());
}

type ChatTraceProjectionOptions = {
  expanded?: boolean;
  showRaw?: boolean;
  routeLabel?: string;
};

// F-172: raw session/request hex IDs never render in the transcript, at any expansion state.
const UUID_ID_PATTERN = /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/g;
const HEX_ID_PATTERN = /[0-9a-fA-F]{12,}/g;

export function scrubRawIdentifiers(text: string): string {
  return text.replace(UUID_ID_PATTERN, "…").replace(HEX_ID_PATTERN, "…");
}

type TraceStep = {
  key: string;
  kind: Exclude<CanonicalExecutionEvent["kind"], "assistant_text" | "user_prompt">;
  phase: ActivityPhase;
  title: string;
  summary?: string;
  detail: string[];
  timestamp?: string;
  raw?: Record<string, unknown>;
};

type ChatTurn = {
  key: string;
  prompt: string;
  phase: ActivityPhase | "cancelled";
  steps: TraceStep[];
  assistant?: string;
  assistantTimestamp?: string;
  route?: string;
  endedWithoutResponse?: boolean;
  acceptedCommandPending?: boolean;
  promptMs?: number;
  lastEventMs?: number;
};

// Wire timestamps arrive as ISO strings (local events) OR epoch-second floats
// (python stream envelopes use time.time()); both must parse for turn timing.
function parseEventTime(value: string | undefined): number | undefined {
  if (!value) {
    return undefined;
  }
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    if (numeric > 1e12) {
      return numeric;
    }
    if (numeric > 1e9) {
      return numeric * 1000;
    }
    return undefined;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function turnDurationSeconds(turn: ChatTurn): number | undefined {
  if (turn.promptMs === undefined || turn.lastEventMs === undefined || turn.lastEventMs < turn.promptMs) {
    return undefined;
  }
  return Math.max(1, Math.round((turn.lastEventMs - turn.promptMs) / 1000));
}

function mergeStepDetail(current: string[], incoming: string[] | undefined): string[] {
  const merged = [...current];
  for (const lineText of incoming ?? []) {
    if (!merged.includes(lineText)) {
      merged.push(lineText);
    }
  }
  return merged;
}

function traceStepFromEvent(event: CanonicalExecutionEvent): TraceStep | undefined {
  if (event.kind === "assistant_text" || event.kind === "user_prompt") {
    return undefined;
  }
  if (event.kind === "tool_call" || event.kind === "tool_result") {
    return {
      key: event.correlationId ? `tool:${event.correlationId}` : event.id,
      kind: "tool_result",
      phase: event.phase,
      title: event.title,
      summary: event.kind === "tool_result" ? event.summary ?? event.content : event.summary ?? event.title,
      detail: mergeStepDetail(
        event.kind === "tool_call" ? [`Call: ${event.summary ?? event.title}`] : [],
        event.detail,
      ),
      timestamp: event.timestamp,
      raw: event.raw,
    };
  }
  return {
    key: event.correlationId ? `${event.kind}:${event.correlationId}` : event.id,
    kind: event.kind,
    phase: event.phase,
    title: event.title,
    summary: event.summary,
    detail: event.detail ?? [],
    timestamp: event.timestamp,
    raw: event.raw,
  };
}

function slashCommandNameFromText(text: string): string {
  const first = text.trim().split(/\s+/, 1)[0] ?? "";
  return first.replace(/^\//, "").toLowerCase();
}

function projectChatTurns(events: CanonicalExecutionEvent[]): ChatTurn[] {
  const turns: ChatTurn[] = [];
  let activeTurn: ChatTurn | undefined;

  for (const event of events) {
    if (event.kind === "user_prompt") {
      activeTurn = {
        key: event.id,
        prompt: event.content ?? event.title,
        phase: "running",
        steps: [],
        promptMs: parseEventTime(event.timestamp),
      };
      turns.push(activeTurn);
      continue;
    }
    if (!activeTurn) {
      continue;
    }
    const eventMs = parseEventTime(event.timestamp);
    if (eventMs !== undefined) {
      activeTurn.lastEventMs = Math.max(activeTurn.lastEventMs ?? 0, eventMs);
    }
    if (event.kind === "assistant_text") {
      const content = (event.content ?? "").trim();
      if (content && activeTurn.assistant !== content) {
        activeTurn.assistant = content;
        activeTurn.assistantTimestamp = event.timestamp;
      }
      if (event.phase === "complete" && activeTurn.phase === "running") {
        activeTurn.phase = "complete";
      }
      continue;
    }
    if (event.sourceEventType === "session.ack" && event.summary) {
      activeTurn.route = event.summary;
    }
    // F-157: queued-offline lifecycle — pending holds the turn in the explicit queued
    // state; dispatched releases it back to running (real bridge events take over);
    // failed flows through the generic failed-phase rule below.
    if (event.kind === "status" && event.raw?.queued_offline === true) {
      const resolution = String(event.raw.queue_resolution ?? "pending");
      if (resolution === "pending") {
        activeTurn.phase = "queued";
      } else if (resolution === "dispatched" && activeTurn.phase === "queued") {
        activeTurn.phase = "running";
      }
    }
    // A transport session ending does not upgrade accepted-but-unperformed
    // command work into a completed trace step.
    const nextStep = event.sourceEventType === "session_end" && activeTurn.acceptedCommandPending
      ? undefined
      : traceStepFromEvent(event);
    if (nextStep) {
      const existing = activeTurn.steps.find((step) => step.key === nextStep.key);
      if (existing) {
        existing.phase = nextStep.phase;
        existing.summary = nextStep.summary ?? existing.summary;
        existing.detail = mergeStepDetail(existing.detail, nextStep.detail);
        existing.raw = nextStep.raw ?? existing.raw;
        existing.timestamp = nextStep.timestamp ?? existing.timestamp;
      } else {
        activeTurn.steps.push(nextStep);
      }
    }
    const isMismatchedSlashCommand = event.kind === "command"
      && activeTurn.prompt.trim().startsWith("/")
      && Boolean(slashCommandNameFromText(String(event.raw?.command ?? "")))
      && slashCommandNameFromText(String(event.raw?.command ?? "")) !== slashCommandNameFromText(activeTurn.prompt);
    // A rejected cancellation is a failed control operation, not a failed provider
    // turn. Keep the live turn running while rendering the acknowledgement with !.
    const isRejectedCancellationAck = event.sourceEventType === "session.cancelled"
      && event.raw?.cancelled !== true;
    if (
      (event.kind === "error" || event.phase === "failed")
      && !isMismatchedSlashCommand
      && !isRejectedCancellationAck
    ) {
      activeTurn.phase = "failed";
    }
    // F-158: a slash-command turn completes on its command result — commands have no
    // session lifecycle, so the matching result event is the turn's terminal state and
    // its text surfaces as the visible response (scrubbed: it is wire-derived trace).
    if (event.kind === "command" && activeTurn.prompt.trim().startsWith("/")) {
      const turnCommand = slashCommandNameFromText(activeTurn.prompt);
      const eventCommand = slashCommandNameFromText(String(event.raw?.command ?? ""));
      if (!eventCommand || eventCommand === turnCommand) {
        const responseText = (event.content ?? event.summary ?? "").trim();
        if (responseText) {
          activeTurn.assistant = scrubRawIdentifiers(responseText);
          activeTurn.assistantTimestamp = event.timestamp;
        }
        if (event.phase === "running") {
          activeTurn.phase = "running";
          activeTurn.acceptedCommandPending = normalizeCommandOutcome(event.raw).reason === "explicit_accepted";
          continue;
        }
        activeTurn.acceptedCommandPending = false;
        activeTurn.phase = event.phase === "complete" ? "complete" : "failed";
        activeTurn = undefined;
        continue;
      }
    }
    if (event.sourceEventType === "session_end") {
      const cancelled = isCancelledSessionEnd(event.raw ?? {});
      activeTurn.phase = cancelled
        ? "cancelled"
        : event.raw?.success === false || event.phase === "failed"
          ? "failed"
          : activeTurn.phase === "failed"
            ? "failed"
            : activeTurn.acceptedCommandPending
              ? "running"
              : "complete";
      // F-173: a turn that ends without any response-bearing content (assistant text
      // or a command/intent answer) never renders as a bare complete — it carries an
      // explicit no-response marker and the failed glyph instead.
      const hasResponse = Boolean(activeTurn.assistant) || activeTurn.steps.some((step) => step.kind === "command");
      if (!cancelled && !hasResponse) {
        activeTurn.endedWithoutResponse = true;
        activeTurn.phase = "failed";
      }
      activeTurn = undefined;
    }
  }

  return turns.slice(-CHAT_TURN_RETENTION);
}

// The model that actually answered the most recent chat turn — the display
// source of truth so the status line names whichever model really ran. Operator
// live-grade 2026-06-16: the labels were "crazy" (status said codex:gpt-5.4, the
// trace said llama-3.3-70b). The trace route is the truth; surface it.
export function latestChatTurnRoute(events: CanonicalExecutionEvent[]): string | undefined {
  const turns = projectChatTurns(events);
  for (let index = turns.length - 1; index >= 0; index -= 1) {
    const route = turns[index]?.route?.trim();
    if (route) {
      return scrubRawIdentifiers(route);
    }
  }
  return undefined;
}

// FACE-1 zen-pure: one quiet line per turn — waiting is "… thinking · <route>"
// (no step counts, no glyph flicker), completion is "✓ <n>s · <route> · ^T details".
function turnSummaryText(turn: ChatTurn, route: string, expanded: boolean): string {
  const hint = expanded ? "^T collapse" : "^T details";
  if (turn.phase === "queued") {
    return `○ queued (backend offline) · ${route} · ${hint}`;
  }
  if (turn.phase === "running") {
    return expanded ? `… thinking · ${route} · ${hint}` : `… thinking · ${route}`;
  }
  if (turn.phase === "failed") {
    return `✖ failed · ${route} · ${hint}`;
  }
  if (turn.phase === "cancelled") {
    return `⊘ cancelled · ${route} · ${hint}`;
  }
  const seconds = turnDurationSeconds(turn);
  return `✓ ${seconds === undefined ? "done" : `${seconds}s`} · ${route} · ${hint}`;
}

// F-172: the response is the star, the trace is one collapsed summary line beneath it.
export function projectChatTraceLines(events: CanonicalExecutionEvent[], options: ChatTraceProjectionOptions = {}): TranscriptLine[] {
  const expanded = options.expanded ?? false;
  const showRaw = options.showRaw ?? false;
  const turns = projectChatTurns(events);
  const projected: TranscriptLine[] = [];

  for (const turn of turns) {
    projected.push(line("user", `> ${turn.prompt}`));

    if (turn.assistant) {
      // Provider-emitted Helm syntax has no authority. Strip it from narration;
      // app.tsx never executes provider directives.
      const visible = stripHelmDirectives(turn.assistant);
      if (visible) {
        for (const responseLine of visible.split("\n")) {
          projected.push(line("assistant", responseLine, turn.assistantTimestamp));
        }
      }
    } else if (turn.endedWithoutResponse) {
      projected.push(line("error", "✖ no response — turn ended without output", turn.steps.at(-1)?.timestamp));
    }

    const route = scrubRawIdentifiers(turn.route ?? options.routeLabel ?? "route pending");
    // F-157: a queued-offline turn names its state on the turn row — never a running
    // glyph or step count while nothing has been dispatched. The summary row renders
    // dim (thinking kind) — it is quiet chrome, not conversation.
    projected.push(
      line(
        turn.phase === "failed" ? "error" : "thinking",
        turnSummaryText(turn, route, expanded),
        turn.assistantTimestamp ?? turn.steps.at(-1)?.timestamp,
      ),
    );

    if (!expanded) {
      continue;
    }
    for (const step of turn.steps) {
      projected.push(
        line(
          step.phase === "failed" || step.kind === "error" ? "error" : step.kind === "tool_call" || step.kind === "tool_result" || step.kind === "approval" ? "tool" : "system",
          scrubRawIdentifiers(`- ${stepGlyph(step.phase)} ${stepLabel({kind: step.kind} as CanonicalExecutionEvent)} | ${step.title}${step.summary ? ` | ${step.summary}` : ""}`),
          step.timestamp,
        ),
      );
      for (const detailLine of step.detail) {
        projected.push(line("system", scrubRawIdentifiers(`  - ${detailLine}`), step.timestamp));
      }
      if (showRaw) {
        for (const rawLine of rawLines(step.raw)) {
          projected.push(line("system", scrubRawIdentifiers(`    ${rawLine}`), step.timestamp));
        }
      }
    }
  }

  return projected.slice(-CHAT_TRACE_LINE_RETENTION);
}

export function projectPaneLines(paneKind: Extract<PaneKind, "thinking" | "tools" | "timeline">, events: CanonicalExecutionEvent[]): TranscriptLine[] {
  return events.flatMap((event) => {
    if (paneKind === "thinking") {
      if (event.kind === "thinking" && event.content) {
        return [line("thinking", event.content, event.timestamp)];
      }
      if (event.kind === "command" || event.kind === "error") {
        return [line(event.kind === "error" ? "error" : "system", `${event.title}${event.summary ? ` | ${event.summary}` : ""}`, event.timestamp)];
      }
      return [];
    }
    if (paneKind === "tools") {
      if (event.kind === "tool_call") {
        return [line("tool", `⠋ ${event.summary ?? event.title}`, event.timestamp)];
      }
      if (event.kind === "tool_result") {
        return [line("tool", `${event.phase === "failed" ? "!" : "✓"} ${event.title}: ${event.summary ?? event.content ?? "no output"}`, event.timestamp)];
      }
      if (event.kind === "approval" || event.kind === "error") {
        return [line(event.kind === "error" ? "error" : "system", `${event.title}${event.summary ? ` | ${event.summary}` : ""}`, event.timestamp)];
      }
      return [];
    }
    if (event.kind === "task" || event.kind === "status" || event.kind === "command" || event.kind === "error") {
      return [line(event.kind === "error" ? "error" : "system", `${event.title}${event.summary ? ` | ${event.summary}` : ""}`, event.timestamp)];
    }
    return [];
  }).slice(-PANE_LINE_RETENTION);
}

export function projectActivityEntries(events: CanonicalExecutionEvent[]): ActivityEntry[] {
  const acceptedRequestIds = new Set(
    events
      .filter((event) => event.kind === "command" && normalizeCommandOutcome(event.raw).reason === "explicit_accepted")
      .map((event) => event.correlationId ?? String(event.raw?.request_id ?? "").trim())
      .filter(Boolean),
  );
  return events.flatMap((event) => {
    if (
      event.sourceEventType === "session_end"
      && acceptedRequestIds.has(event.correlationId ?? String(event.raw?.request_id ?? "").trim())
    ) {
      return [];
    }
    switch (event.kind) {
      case "thinking":
        return [activity("thinking", event)];
      case "tool_call":
      case "tool_result":
        return [activity("tool", event, event.kind === "tool_result" ? event.summary : event.title)];
      case "approval":
        return [activity("approval", event)];
      case "task":
        return [activity("task", event)];
      case "command":
        return [activity("pivot", event)];
      case "status":
        return [activity("status", event)];
      case "error":
        return [activity("error", event)];
      default:
        return [];
    }
  }).slice(-ACTIVITY_ENTRY_RETENTION);
}
