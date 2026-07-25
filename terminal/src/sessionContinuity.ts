import type {
  AppState,
  CanonicalEventEnvelope,
  ContinuityMessage,
  SessionContinuityState,
  SessionDetailPayload,
  TranscriptLine,
} from "./types.ts";

export const MAX_CONVERSATION_MESSAGES = 24;

type ConversationMessage = {
  role: "user" | "assistant";
  content: string;
};

export type SessionResumeEligibility =
  | {canResume: true; providerSessionId: string; reason: "ready"}
  | {
      canResume: false;
      reason:
        | "detail_unavailable"
        | "provider_unsupported"
        | "provider_mismatch"
        | "replay_unverified"
        | "provider_session_missing";
    };

function eventContent(event: CanonicalEventEnvelope): string {
  const content = event.payload?.content;
  return typeof content === "string" ? content : "";
}

function appendProjectedMessage(
  history: ContinuityMessage[],
  role: "user" | "assistant",
  content: string,
): void {
  const normalized = content.trim();
  if (!normalized) {
    return;
  }
  const previous = history[history.length - 1];
  if (previous?.role === role) {
    if (previous.content === normalized) {
      return;
    }
    previous.content = `${previous.content}\n\n${normalized}`;
    return;
  }
  history.push({role, content: normalized, source: "session_detail"});
}

/**
 * Project a durable canonical transcript into provider conversation history.
 *
 * Only operator-authored `user_prompt` events establish user authority. Legacy
 * prompts embedded in provider/session-start payloads are intentionally ignored.
 * Complete assistant blocks supersede their streamed deltas; deltas are used only
 * when no complete block arrived for that content index.
 */
export function projectSessionDetailHistory(
  detail: SessionDetailPayload,
  historyLimit = MAX_CONVERSATION_MESSAGES,
): ContinuityMessage[] {
  const history: ContinuityMessage[] = [];
  const pendingDeltas = new Map<string, {order: number; parts: string[]}>();
  const completedContentIndices = new Set<string>();
  let nextDeltaOrder = 0;

  const flushUncompletedDeltas = (): void => {
    const pending = [...pendingDeltas.entries()].sort((left, right) => left[1].order - right[1].order);
    for (const [contentIndex, delta] of pending) {
      if (!completedContentIndices.has(contentIndex)) {
        appendProjectedMessage(history, "assistant", delta.parts.join(""));
      }
    }
    pendingDeltas.clear();
    completedContentIndices.clear();
  };

  for (const event of detail.recent_events) {
    if (event.event_type === "user_prompt") {
      flushUncompletedDeltas();
      if (event.source === "operator") {
        appendProjectedMessage(history, "user", eventContent(event));
      }
      continue;
    }

    if (event.event_type !== "text_delta" && event.event_type !== "text_complete") {
      if (event.event_type === "session_end") {
        flushUncompletedDeltas();
      }
      continue;
    }

    const role = event.payload?.role;
    if (role !== undefined && role !== "assistant") {
      continue;
    }
    const content = eventContent(event);
    if (!content) {
      continue;
    }
    const contentIndex = String(event.payload?.content_index ?? 0);

    if (event.event_type === "text_complete") {
      pendingDeltas.delete(contentIndex);
      completedContentIndices.add(contentIndex);
      appendProjectedMessage(history, "assistant", content);
      continue;
    }

    if (completedContentIndices.has(contentIndex)) {
      continue;
    }
    const pending = pendingDeltas.get(contentIndex);
    if (pending) {
      pending.parts.push(content);
    } else {
      pendingDeltas.set(contentIndex, {order: nextDeltaOrder, parts: [content]});
      nextDeltaOrder += 1;
    }
  }

  flushUncompletedDeltas();
  return history.slice(-Math.max(0, historyLimit));
}

export function sessionResumeEligibility(
  state: Pick<AppState, "routePolicy">,
  detail: SessionDetailPayload | undefined,
): SessionResumeEligibility {
  if (!detail) {
    return {canResume: false, reason: "detail_unavailable"};
  }
  // The current bridge only forwards provider-native resume IDs to Claude's
  // `--resume` path. Other providers must remain fresh until their runtime path
  // implements equivalent semantics.
  if (detail.session.provider_id !== "claude") {
    return {canResume: false, reason: "provider_unsupported"};
  }
  if (state.routePolicy.provider !== detail.session.provider_id) {
    return {canResume: false, reason: "provider_mismatch"};
  }
  if (!detail.replay_ok) {
    return {canResume: false, reason: "replay_unverified"};
  }
  const providerSessionId = detail.session.metadata?.provider_session_id;
  if (typeof providerSessionId !== "string" || !providerSessionId.trim()) {
    return {canResume: false, reason: "provider_session_missing"};
  }
  return {canResume: true, providerSessionId: providerSessionId.trim(), reason: "ready"};
}

export function continuityStateFromSession(
  state: Pick<AppState, "routePolicy" | "sessionContinuity">,
  detail: SessionDetailPayload | undefined,
  intent: "view" | "resume" = "view",
): SessionContinuityState {
  if (!detail) {
    return {
      ...state.sessionContinuity,
      activeSessionId: undefined,
      resumeSessionId: undefined,
      activeRouteId: state.routePolicy.routeId,
      continuityMode: "fresh",
      boundedHistory: [],
      compactionPolicy: {
        eventCount: 0,
        compactableRatio: 0,
        protectedEventTypes: [],
        recentEventTypes: [],
      },
      compactedSummary: undefined,
    };
  }

  const eligibility = sessionResumeEligibility(state, detail);
  const resumeArmed = intent === "resume" && eligibility.canResume;
  return {
    ...state.sessionContinuity,
    activeSessionId: resumeArmed ? detail.session.session_id : undefined,
    resumeSessionId: resumeArmed ? eligibility.providerSessionId : undefined,
    activeRouteId: resumeArmed
      ? `${detail.session.provider_id}:${detail.session.model_id}`
      : state.routePolicy.routeId,
    continuityMode: resumeArmed ? "resume" : "fresh",
    boundedHistory: projectSessionDetailHistory(detail, state.sessionContinuity.historyLimit),
    compactionPolicy: {
      eventCount: detail.compaction_preview.event_count,
      compactableRatio: detail.compaction_preview.compactable_ratio,
      protectedEventTypes: detail.compaction_preview.protected_event_types,
      recentEventTypes: detail.compaction_preview.recent_event_types,
    },
    compactedSummary: detail.session.summary ?? undefined,
  };
}

function normalizeConversationLine(line: TranscriptLine): ConversationMessage | undefined {
  if (line.kind === "user") {
    const content = line.text.replace(/^>\s*/, "").trim();
    return content ? {role: "user", content} : undefined;
  }
  if (line.kind === "assistant") {
    const content = line.text.trim();
    return content ? {role: "assistant", content} : undefined;
  }
  return undefined;
}

function appendSubmittedPrompt(history: ConversationMessage[], submittedPrompt: string): ConversationMessage[] {
  const prompt = submittedPrompt.trim();
  if (prompt) {
    const previous = history[history.length - 1];
    if (previous?.role !== "user" || previous.content !== prompt) {
      history.push({role: "user", content: prompt});
    }
  }
  return history.slice(-MAX_CONVERSATION_MESSAGES);
}

function liveConversationMessages(chatLines: TranscriptLine[], submittedPrompt: string): ConversationMessage[] {
  const firstUserIndex = chatLines.findIndex((line) => line.kind === "user");
  const relevantLines = firstUserIndex >= 0 ? chatLines.slice(firstUserIndex) : [];
  const collapsed: ConversationMessage[] = [];

  for (const line of relevantLines) {
    const normalized = normalizeConversationLine(line);
    if (!normalized) {
      continue;
    }
    const previous = collapsed[collapsed.length - 1];
    if (previous?.role === normalized.role) {
      previous.content = `${previous.content}\n${normalized.content}`.trim();
    } else {
      collapsed.push({...normalized});
    }
  }
  return appendSubmittedPrompt(collapsed, submittedPrompt);
}

/** Build the next provider request without letting row selection leak into it. */
export function messagesForNextTurn(
  state: Pick<AppState, "sessionContinuity" | "tabs">,
  submittedPrompt: string,
): ConversationMessage[] {
  const continuity = state.sessionContinuity;
  if (
    continuity.continuityMode === "resume" &&
    continuity.activeSessionId &&
    continuity.resumeSessionId
  ) {
    const projected = continuity.boundedHistory
      .filter((message): message is ContinuityMessage & {role: "user" | "assistant"} =>
        message.role === "user" || message.role === "assistant",
      )
      .map(({role, content}) => ({role, content}));
    return appendSubmittedPrompt(projected, submittedPrompt);
  }

  const chatLines = state.tabs.find((tab) => tab.id === "chat")?.lines ?? [];
  return liveConversationMessages(chatLines, submittedPrompt);
}
