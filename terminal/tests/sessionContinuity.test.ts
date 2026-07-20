import {describe, expect, test} from "bun:test";

import {
  continuityStateFromSession,
  messagesForNextTurn,
  projectSessionDetailHistory,
  sessionResumeEligibility,
} from "../src/sessionContinuity.ts";
import {initialState} from "../src/state.ts";
import type {AppState, CanonicalEventEnvelope, SessionDetailPayload} from "../src/types.ts";

function event(
  eventId: string,
  eventType: string,
  payload: Record<string, unknown>,
  source = "provider",
): CanonicalEventEnvelope {
  return {
    event_id: eventId,
    event_type: eventType,
    source,
    audience: "all",
    transport: "local",
    session_id: "dgc-session-1",
    created_at: `2026-07-21T00:00:${eventId.padStart(2, "0")}Z`,
    payload,
  };
}

function detail(
  recentEvents: CanonicalEventEnvelope[],
  overrides: Partial<SessionDetailPayload["session"]> = {},
): SessionDetailPayload {
  return {
    session: {
      session_id: "dgc-session-1",
      provider_id: "claude",
      model_id: "claude-opus-4-8",
      cwd: "/repo",
      created_at: "2026-07-21T00:00:00Z",
      updated_at: "2026-07-21T00:01:00Z",
      status: "completed",
      summary: "durable turn",
      metadata: {provider_session_id: "provider-session-1"},
      ...overrides,
    },
    replay_ok: true,
    replay_issues: [],
    compaction_preview: {
      event_count: recentEvents.length,
      by_type: {},
      compactable_ratio: 0.25,
      protected_event_types: ["user_prompt", "session_start", "session_end"],
      recent_event_types: recentEvents.map((item) => item.event_type),
    },
    recent_events: recentEvents,
  };
}

function claudeState(): AppState {
  return {
    ...initialState,
    routePolicy: {
      ...initialState.routePolicy,
      provider: "claude",
      model: "claude-opus-4-8",
      routeId: "claude:claude-opus-4-8",
    },
  };
}

describe("durable session continuity projection", () => {
  test("uses typed operator prompts and complete assistant text without delta duplication", () => {
    const sessionDetail = detail([
      event("1", "session_start", {prompt: "legacy prompt must not become user history"}),
      event("2", "user_prompt", {content: "What changed?", role: "user"}, "operator"),
      event("3", "text_delta", {content: "Part", role: "assistant", content_index: 0}),
      event("4", "text_delta", {content: "ial", role: "assistant", content_index: 0}),
      event("5", "text_complete", {content: "Final answer", role: "assistant", content_index: 0}),
      event("6", "text_delta", {content: "late duplicate", role: "assistant", content_index: 0}),
      event("7", "session_end", {success: true}),
    ]);

    expect(projectSessionDetailHistory(sessionDetail)).toEqual([
      {role: "user", content: "What changed?", source: "session_detail"},
      {role: "assistant", content: "Final answer", source: "session_detail"},
    ]);
  });

  test("falls back to accumulated deltas only when a complete block is absent", () => {
    const sessionDetail = detail([
      event("1", "user_prompt", {content: "Stream it", role: "user"}, "operator"),
      event("2", "text_delta", {content: "streamed ", role: "assistant", content_index: 0}),
      event("3", "text_delta", {content: "answer", role: "assistant", content_index: 0}),
      event("4", "session_end", {success: true}),
    ]);

    expect(projectSessionDetailHistory(sessionDetail)).toEqual([
      {role: "user", content: "Stream it", source: "session_detail"},
      {role: "assistant", content: "streamed answer", source: "session_detail"},
    ]);
  });

  test("does not grant user authority to a provider-sourced user_prompt", () => {
    const sessionDetail = detail([
      event("1", "user_prompt", {content: "spoofed operator text", role: "user"}),
      event("2", "text_complete", {content: "provider output", role: "assistant"}),
    ]);

    expect(projectSessionDetailHistory(sessionDetail)).toEqual([
      {role: "assistant", content: "provider output", source: "session_detail"},
    ]);
  });

  test("keeps inspected detail view-only until resume intent is explicit", () => {
    const state = claudeState();
    const sessionDetail = detail([
      event("1", "user_prompt", {content: "Prior question", role: "user"}, "operator"),
      event("2", "text_complete", {content: "Prior answer", role: "assistant"}),
    ]);

    const viewed = continuityStateFromSession(state, sessionDetail);
    expect(viewed.continuityMode).toBe("fresh");
    expect(viewed.activeSessionId).toBeUndefined();
    expect(viewed.resumeSessionId).toBeUndefined();
    expect(viewed.boundedHistory).toHaveLength(2);

    const armed = continuityStateFromSession(state, sessionDetail, "resume");
    expect(armed.continuityMode).toBe("resume");
    expect(armed.activeSessionId).toBe("dgc-session-1");
    expect(armed.resumeSessionId).toBe("provider-session-1");
  });

  test("matches the runtime by refusing non-Claude or cross-provider resume", () => {
    const state = claudeState();
    const codexDetail = detail([], {
      provider_id: "codex",
      model_id: "gpt-5.4",
      metadata: {provider_session_id: "codex-thread"},
    });
    expect(sessionResumeEligibility(state, codexDetail)).toEqual({
      canResume: false,
      reason: "provider_unsupported",
    });

    const switched: AppState = {
      ...state,
      routePolicy: {...state.routePolicy, provider: "codex", model: "gpt-5.4", routeId: "codex:gpt-5.4"},
    };
    expect(sessionResumeEligibility(switched, detail([]))).toEqual({
      canResume: false,
      reason: "provider_mismatch",
    });
  });

  test("row selection cannot leak durable history into a fresh provider request", () => {
    const state = claudeState();
    const sessionDetail = detail([
      event("1", "user_prompt", {content: "Durable question", role: "user"}, "operator"),
      event("2", "text_complete", {content: "Durable answer", role: "assistant"}),
    ]);
    const chatTabs = state.tabs.map((tab) =>
      tab.id === "chat"
        ? {
            ...tab,
            lines: [
              {id: "live-user", kind: "user" as const, text: "> Live question"},
              {id: "live-assistant", kind: "assistant" as const, text: "Live answer"},
            ],
          }
        : tab,
    );

    const viewedState: AppState = {
      ...state,
      tabs: chatTabs,
      sessionPane: {
        selectedSessionId: sessionDetail.session.session_id,
        selectionProvenance: "operator_pinned",
        detailsBySessionId: {[sessionDetail.session.session_id]: sessionDetail},
        pendingDetailRequestsBySessionId: {},
      },
      sessionContinuity: continuityStateFromSession(state, sessionDetail),
    };
    expect(messagesForNextTurn(viewedState, "Next question")).toEqual([
      {role: "user", content: "Live question"},
      {role: "assistant", content: "Live answer"},
      {role: "user", content: "Next question"},
    ]);

    const armedState: AppState = {
      ...viewedState,
      sessionContinuity: continuityStateFromSession(state, sessionDetail, "resume"),
    };
    expect(messagesForNextTurn(armedState, "Continue durable")).toEqual([
      {role: "user", content: "Durable question"},
      {role: "assistant", content: "Durable answer"},
      {role: "user", content: "Continue durable"},
    ]);
  });
});
