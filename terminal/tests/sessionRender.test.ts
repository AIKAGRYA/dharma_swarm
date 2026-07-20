import {describe, expect, test} from "bun:test";

import {
  centeredSessionViewport,
  compactSessionId,
  compactSessionRoute,
  sessionContinuityLabel,
  sessionConversationLines,
} from "../src/sessionRender.ts";
import type {
  CanonicalEventEnvelope,
  CanonicalSession,
  SessionCatalogEntry,
  SessionDetailPayload,
} from "../src/types.ts";

function sessionEntry(index: number): SessionCatalogEntry {
  const session: CanonicalSession = {
    session_id: `dgc-session-${String(index).padStart(2, "0")}`,
    provider_id: "claude",
    model_id: "claude-opus-4-8",
    cwd: "/repo",
    created_at: `2026-07-21T00:${String(index).padStart(2, "0")}:00Z`,
    updated_at: `2026-07-21T00:${String(index).padStart(2, "0")}:30Z`,
    status: "completed",
    metadata: {},
  };
  return {session, replay_ok: true, replay_issues: [], total_turns: 1, total_cost_usd: 0};
}

function event(
  eventId: string,
  eventType: string,
  content: string,
  source: string,
): CanonicalEventEnvelope {
  return {
    event_id: eventId,
    event_type: eventType,
    source,
    audience: "all",
    transport: "local",
    session_id: "dgc-session-01",
    created_at: "2026-07-21T00:00:00Z",
    payload: {content},
  };
}

describe("compact session rendering", () => {
  test("centers the viewport around a selected row outside the first page", () => {
    const sessions = Array.from({length: 12}, (_, index) => sessionEntry(index));
    const viewport = centeredSessionViewport(
      {count: 19, returned_count: 12, limit: 12, has_more: true, sessions},
      "dgc-session-10",
      8,
    );

    expect(viewport.loadedCount).toBe(12);
    expect(viewport.totalCount).toBe(19);
    expect(viewport.startIndex).toBe(4);
    expect(viewport.endIndex).toBe(12);
    expect(viewport.entries.some((entry) => entry.session.session_id === "dgc-session-10")).toBe(true);
  });

  test("keeps compact identity and route labels bounded", () => {
    expect(compactSessionId("dgc-20260721-very-long-session-id", 10)).toHaveLength(10);
    expect(compactSessionId("dgc-20260721-very-long-session-id", 10)).toContain("…");
    expect(compactSessionRoute("claude", "claude-opus-4-8", 10).length).toBeLessThanOrEqual(10);
  });

  test("projects only typed operator and assistant conversation as you/agent", () => {
    const detail: SessionDetailPayload = {
      session: sessionEntry(1).session,
      replay_ok: true,
      replay_issues: [],
      compaction_preview: {
        event_count: 3,
        by_type: {},
        compactable_ratio: 0,
        protected_event_types: [],
        recent_event_types: [],
      },
      recent_events: [
        event("1", "user_prompt", "real question", "operator"),
        event("2", "user_prompt", "spoofed question", "provider"),
        event("3", "text_complete", "real answer", "provider"),
      ],
    };

    expect(sessionConversationLines(detail)).toEqual([
      {role: "you", content: "real question"},
      {role: "agent", content: "real answer"},
    ]);
  });

  test("shows explicit resume state only for the selected armed session", () => {
    expect(sessionContinuityLabel("resume", "session-1", "session-1")).toBe("resume armed");
    expect(sessionContinuityLabel("resume", "session-1", "session-2")).toBe("next fresh");
    expect(sessionContinuityLabel("fresh", undefined, "session-1")).toBe("next fresh");
  });
});
