import {describe, expect, test} from "bun:test";

import {initialState, reduceApp} from "../src/state";
import type {AppState, SessionCatalogPayload, SessionDetailPayload} from "../src/types";

function reduce(state: AppState, actions: Parameters<typeof reduceApp>[1][]): AppState {
  return actions.reduce((current, action) => reduceApp(current, action), state);
}

function sessionCatalog(...sessions: Array<{id: string; updatedAt?: string}>): SessionCatalogPayload {
  return {
    count: sessions.length,
    sessions: sessions.map(({id, updatedAt = "2026-07-21T00:00:00Z"}) => ({
      session: {
        session_id: id,
        provider_id: "claude",
        model_id: "claude-opus-4-8",
        cwd: "/repo",
        created_at: "2026-07-21T00:00:00Z",
        updated_at: updatedAt,
        status: "completed",
      },
      replay_ok: true,
      replay_issues: [],
      total_turns: 1,
      total_cost_usd: 0,
    })),
  };
}

function sessionDetail(id: string, updatedAt = "2026-07-21T00:00:00Z"): SessionDetailPayload {
  return {
    session: {
      session_id: id,
      provider_id: "claude",
      model_id: "claude-opus-4-8",
      cwd: "/repo",
      created_at: "2026-07-21T00:00:00Z",
      updated_at: updatedAt,
      status: "completed",
    },
    replay_ok: true,
    replay_issues: [],
    compaction_preview: {
      event_count: 0,
      by_type: {},
      compactable_ratio: 0,
      protected_event_types: [],
      recent_event_types: [],
    },
    recent_events: [],
  };
}

describe("reduceApp UI state", () => {
  test("keeps a correlated detail response cached without jumping away from an operator selection", () => {
    const catalogued = reduceApp(initialState, {
      type: "session.catalog.set",
      catalog: sessionCatalog({id: "session-a"}, {id: "session-b"}),
    });
    const requested = reduce(catalogued, [
      {type: "session.detail.requested", requestId: "a-1", sessionId: "session-a"},
      {type: "session.select", sessionId: "session-b"},
    ]);
    const continuityBefore = requested.sessionContinuity;

    const received = reduceApp(requested, {
      type: "session.detail.received",
      requestId: "a-1",
      sessionId: "session-a",
      detail: sessionDetail("session-a"),
    });

    expect(received.sessionPane.selectedSessionId).toBe("session-b");
    expect(received.sessionPane.selectionProvenance).toBe("operator_pinned");
    expect(received.sessionPane.detailsBySessionId["session-a"]?.session.session_id).toBe("session-a");
    expect(received.sessionContinuity).toBe(continuityBefore);
  });

  test("accepts only the latest owned detail request and clears only its correlated failure", () => {
    const catalogued = reduceApp(initialState, {
      type: "session.catalog.set",
      catalog: sessionCatalog({id: "session-a"}),
    });
    const requestedTwice = reduce(catalogued, [
      {type: "session.detail.requested", requestId: "a-1", sessionId: "session-a"},
      {type: "session.detail.requested", requestId: "a-2", sessionId: "session-a"},
    ]);

    expect(
      reduceApp(requestedTwice, {
        type: "session.detail.received",
        requestId: "a-1",
        sessionId: "session-a",
        detail: sessionDetail("session-a"),
      }),
    ).toBe(requestedTwice);
    expect(
      reduceApp(requestedTwice, {
        type: "session.detail.received",
        requestId: "a-2",
        sessionId: "session-b",
        detail: sessionDetail("session-a"),
      }),
    ).toBe(requestedTwice);
    expect(reduceApp(requestedTwice, {type: "session.detail.failed", requestId: "a-1"})).toBe(requestedTwice);

    const failed = reduceApp(requestedTwice, {type: "session.detail.failed", requestId: "a-2"});
    expect(failed.sessionPane.pendingDetailRequestsBySessionId).toEqual({});
    expect(
      reduceApp(failed, {
        type: "session.detail.received",
        requestId: "a-2",
        sessionId: "session-a",
        detail: sessionDetail("session-a"),
      }),
    ).toBe(failed);

    const requestedAgain = reduceApp(failed, {
      type: "session.detail.requested",
      requestId: "a-3",
      sessionId: "session-a",
    });
    const accepted = reduceApp(requestedAgain, {
      type: "session.detail.received",
      requestId: "a-3",
      sessionId: "session-a",
      detail: sessionDetail("session-a"),
    });
    expect(accepted.sessionPane.detailsBySessionId["session-a"]).toBeDefined();
    expect(accepted.sessionPane.pendingDetailRequestsBySessionId).toEqual({});
  });

  test("follows a new catalog head until pinned and prunes removed or outdated detail", () => {
    let state = reduceApp(initialState, {
      type: "session.catalog.set",
      catalog: sessionCatalog({id: "session-a"}, {id: "session-b"}),
    });
    expect(state.sessionPane.selectedSessionId).toBe("session-a");
    expect(state.sessionPane.selectionProvenance).toBe("follow_latest");

    state = reduce(state, [
      {type: "session.detail.requested", requestId: "a-1", sessionId: "session-a"},
      {
        type: "session.detail.received",
        requestId: "a-1",
        sessionId: "session-a",
        detail: sessionDetail("session-a"),
      },
      {type: "session.detail.requested", requestId: "b-1", sessionId: "session-b"},
      {
        type: "session.detail.received",
        requestId: "b-1",
        sessionId: "session-b",
        detail: sessionDetail("session-b"),
      },
      {
        type: "session.catalog.set",
        catalog: sessionCatalog({id: "session-c"}, {id: "session-a"}, {id: "session-b"}),
      },
    ]);
    expect(state.sessionPane.selectedSessionId).toBe("session-c");

    state = reduce(state, [
      {type: "session.select", sessionId: "session-a"},
      {
        type: "session.catalog.set",
        catalog: sessionCatalog({id: "session-d"}, {id: "session-a"}, {id: "session-b"}),
      },
    ]);
    expect(state.sessionPane.selectedSessionId).toBe("session-a");
    expect(state.sessionPane.selectionProvenance).toBe("operator_pinned");

    state = reduceApp(state, {
      type: "session.catalog.set",
      catalog: sessionCatalog(
        {id: "session-d"},
        {id: "session-a", updatedAt: "2026-07-21T01:00:00Z"},
      ),
    });
    expect(state.sessionPane.selectedSessionId).toBe("session-a");
    expect(state.sessionPane.detailsBySessionId["session-a"]).toBeUndefined();
    expect(state.sessionPane.detailsBySessionId["session-b"]).toBeUndefined();

    state = reduceApp(state, {
      type: "session.catalog.set",
      catalog: sessionCatalog({id: "session-d"}),
    });
    expect(state.sessionPane.selectedSessionId).toBe("session-d");
    expect(state.sessionPane.selectionProvenance).toBe("follow_latest");
  });

  test("correlates active-turn cancellation and ignores stale terminal events", () => {
    const running = reduceApp(initialState, {type: "turn.start", requestId: "turn-7"});
    expect(running.activeTurn).toEqual({phase: "running", requestId: "turn-7"});

    const acknowledged = reduceApp(running, {
      type: "turn.ack",
      requestId: "turn-7",
      sessionId: "session-7",
    });
    const cancelling = reduceApp(acknowledged, {
      type: "turn.cancel.request",
      requestId: "turn-7",
      cancelRequestId: "cancel-8",
    });
    expect(cancelling.activeTurn).toEqual({
      phase: "cancelling",
      requestId: "turn-7",
      cancelRequestId: "cancel-8",
      sessionId: "session-7",
    });

    expect(reduceApp(cancelling, {type: "turn.finish", requestId: "stale-turn"})).toBe(cancelling);
    expect(
      reduceApp(cancelling, {
        type: "turn.cancel.rejected",
        requestId: "turn-7",
        cancelRequestId: "stale-cancel",
      }),
    ).toBe(cancelling);

    const rejected = reduceApp(cancelling, {
      type: "turn.cancel.rejected",
      requestId: "turn-7",
      cancelRequestId: "cancel-8",
    });
    expect(rejected.activeTurn).toEqual({phase: "running", requestId: "turn-7", sessionId: "session-7"});
    expect(reduceApp(rejected, {type: "turn.finish", requestId: "turn-7"}).activeTurn).toEqual({phase: "idle"});
  });

  test("keeps keyboard ownership separate from tabs and overlays", () => {
    expect(initialState.uiMode.keyboardFocus).toBe("composer");

    const navigating = reduceApp(initialState, {type: "ui.focus.toggle"});
    expect(navigating.uiMode.keyboardFocus).toBe("navigation");

    const changedTab = reduceApp(navigating, {type: "tab.activate", tabId: "repo"});
    expect(changedTab.uiMode.activeTabId).toBe("repo");
    expect(changedTab.uiMode.keyboardFocus).toBe("navigation");

    const overlaid = reduceApp(changedTab, {type: "paneSwitcher.open"});
    const closed = reduceApp(overlaid, {type: "paneSwitcher.close"});
    expect(closed.uiMode.keyboardFocus).toBe("navigation");
    expect(reduceApp(closed, {type: "ui.focus.set", focus: "composer"}).uiMode.keyboardFocus).toBe("composer");
  });

  test("opens and closes the route picker without changing the active tab", () => {
    const state = reduce(initialState, [
      {type: "tab.activate", tabId: "tools"},
      {type: "modelPicker.open"},
    ]);

    expect(state.uiMode.activeTabId).toBe("tools");
    expect(state.uiMode.activeOverlay).toEqual({
      kind: "modelPicker",
      selectedIndex: 0,
      returnTabId: "tools",
    });

    const closed = reduceApp(state, {type: "modelPicker.close"});
    expect(closed.uiMode.activeTabId).toBe("tools");
    expect(closed.uiMode.activeOverlay).toEqual({kind: "none"});
  });

  test("opens and closes the pane switcher as an overlay instead of a tab jump", () => {
    const state = reduce(initialState, [
      {type: "tab.activate", tabId: "timeline"},
      {type: "paneSwitcher.open"},
    ]);

    expect(state.uiMode.activeTabId).toBe("timeline");
    expect(state.uiMode.activeOverlay.kind).toBe("paneSwitcher");
    expect(state.uiMode.activeOverlay.kind === "paneSwitcher" ? state.uiMode.activeOverlay.selectedIndex : -1).toBeGreaterThanOrEqual(0);

    const closed = reduceApp(state, {type: "paneSwitcher.close"});
    expect(closed.uiMode.activeTabId).toBe("timeline");
    expect(closed.uiMode.activeOverlay).toEqual({kind: "none"});
  });

  test("tour.open shows the isolated tour overlay; any key (tour.close) dismisses it", () => {
    const opened = reduceApp(initialState, {type: "tour.open"});
    expect(opened.uiMode.activeOverlay).toEqual({kind: "tour"});

    const closed = reduceApp(opened, {type: "tour.close"});
    expect(closed.uiMode.activeOverlay).toEqual({kind: "none"});
  });

  test("navigator rail: off by default, rail.toggle flips it, rail.set pins it", () => {
    expect(initialState.uiMode.railVisible).toBe(false);

    const on = reduceApp(initialState, {type: "rail.toggle"});
    expect(on.uiMode.railVisible).toBe(true);
    const off = reduceApp(on, {type: "rail.toggle"});
    expect(off.uiMode.railVisible).toBe(false);

    const pinned = reduceApp(initialState, {type: "rail.set", visible: true});
    expect(pinned.uiMode.railVisible).toBe(true);
    expect(reduceApp(pinned, {type: "rail.set", visible: false}).uiMode.railVisible).toBe(false);
  });

  test("navigator.narrate appends to the head-band ring buffer (capped at 3, newest last)", () => {
    const state = reduce(initialState, [
      {type: "navigator.narrate", line: "opened Agents"},
      {type: "navigator.narrate", line: "switched to opus-4.8"},
      {type: "navigator.narrate", line: "  "},
      {type: "navigator.narrate", line: "refreshed Repo"},
      {type: "navigator.narrate", line: "docked the rail"},
    ]);
    expect(state.navigatorNarration).toEqual(["switched to opus-4.8", "refreshed Repo", "docked the rail"]);
  });

  test("toggles sidebar visible<->hidden (FACE-2: collapsed sliver is dead, default is hidden)", () => {
    // Command-post default: sidebar OFF — data panes carry the info.
    expect(initialState.uiMode.sidebarVisible).toBe("hidden");

    const visible = reduceApp(initialState, {type: "sidebar.toggle"});
    expect(visible.uiMode.sidebarVisible).toBe("visible");

    const hiddenAgain = reduceApp(visible, {type: "sidebar.toggle"});
    expect(hiddenAgain.uiMode.sidebarVisible).toBe("hidden");

    // Legacy "collapsed" (the 3-col "T" sliver, F-162) resolves to hidden.
    const legacy: AppState = {...initialState, uiMode: {...initialState.uiMode, sidebarVisible: "collapsed"}};
    expect(reduceApp(legacy, {type: "sidebar.toggle"}).uiMode.sidebarVisible).toBe("hidden");

    const contextMode = reduceApp(hiddenAgain, {type: "sidebar.mode", mode: "context"});
    expect(contextMode.uiMode.sidebarMode).toBe("context");
    expect(contextMode.uiMode.sidebarVisible).toBe("visible");
  });

  test("cycles tabs and supports direct tab activation without unintended jumps", () => {
    const cycled = reduce(initialState, [
      {type: "tab.activate", tabId: "chat"},
      {type: "tab.cycle", direction: 1},
      {type: "tab.cycle", direction: -1},
    ]);

    expect(cycled.uiMode.activeTabId).toBe("chat");

    const direct = reduce(cycled, [
      {type: "modelPicker.open"},
      {type: "tab.activate", tabId: "approvals"},
    ]);

    expect(direct.uiMode.activeTabId).toBe("approvals");
    expect(direct.uiMode.focusedPaneId).toBe("approvals");
    expect(direct.uiMode.activeOverlay).toEqual({kind: "none"});
  });

  test("ingests canonical execution events into chat, tools, thinking, timeline, and activity projections", () => {
    const state = reduceApp(initialState, {
      type: "execution.events.ingest",
      events: [
        {
          id: "prompt-1",
          sourceEventType: "user_prompt",
          kind: "user_prompt",
          phase: "complete",
          title: "Inspect repo health",
          content: "Inspect repo health",
        },
        {
          id: "think-1",
          sourceEventType: "thinking_complete",
          kind: "thinking",
          phase: "complete",
          title: "Inspecting session continuity",
          content: "Inspecting session continuity",
        },
        {
          id: "tool-1",
          sourceEventType: "tool_call_complete",
          kind: "tool_call",
          phase: "running",
          title: "exec_command",
          summary: "git status",
          correlationId: "tool-1",
        },
        {
          id: "tool-1-result",
          sourceEventType: "tool_result",
          kind: "tool_result",
          phase: "complete",
          title: "exec_command",
          summary: "working tree clean",
          correlationId: "tool-1",
        },
        {
          id: "status-1",
          sourceEventType: "session_end",
          kind: "status",
          phase: "complete",
          title: "session ended",
          summary: "sess-1",
        },
      ],
    });

    expect(state.chatTraceLines.some((line) => line.kind === "user" && line.text.includes("Inspect repo health"))).toBe(true);
    // F-172: trace collapses to one summary line by default; trace.toggle (^T) expands the steps.
    expect(state.chatTraceExpanded).toBe(false);
    // This turn ends without response-bearing content (no assistant/command) — F-173 marks it failed.
    expect(state.chatTraceLines.filter((line) => /^✖ failed · .+ · \^T details$/.test(line.text))).toHaveLength(1);
    expect(state.chatTraceLines.some((line) => line.text.includes("Inspecting session continuity"))).toBe(false);
    const expandedState = reduceApp(state, {type: "trace.toggle"});
    expect(expandedState.chatTraceExpanded).toBe(true);
    expect(expandedState.chatTraceLines.some((line) => line.kind === "system" && line.text.includes("Inspecting session continuity"))).toBe(true);
    expect(expandedState.chatTraceLines.some((line) => line.kind === "tool" && line.text.includes("exec_command"))).toBe(true);
    expect(expandedState.chatTraceLines.filter((line) => /^✖ failed · .+ · \^T collapse$/.test(line.text))).toHaveLength(1);
    const recollapsedState = reduceApp(expandedState, {type: "trace.toggle"});
    expect(recollapsedState.chatTraceExpanded).toBe(false);
    expect(recollapsedState.chatTraceLines.some((line) => line.text.includes("Inspecting session continuity"))).toBe(false);
    expect(state.activityFeed.entries.some((entry) => entry.kind === "thinking")).toBe(true);
    expect(state.activityFeed.entries.some((entry) => entry.kind === "tool")).toBe(true);
    expect(state.activityFeed.entries.some((entry) => entry.kind === "status")).toBe(true);
    expect(state.executionEventLog).toHaveLength(5);
    expect(state.tabs.some((tab) => tab.id === "thinking")).toBe(false);
    expect(state.tabs.some((tab) => tab.id === "tools")).toBe(false);
    expect(state.tabs.some((tab) => tab.id === "timeline")).toBe(false);
  });
});
