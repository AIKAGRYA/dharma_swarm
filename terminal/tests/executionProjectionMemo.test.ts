import {describe, expect, test} from "bun:test";

import {
  canonicalEventsFromBridgeEvent,
  projectActivityEntries,
  projectChatTraceLines,
  projectPaneLines,
  userPromptExecutionEvent,
} from "../src/executionLog";
import {projectExecutionViews} from "../src/executionProjectionMemo";
import {buildBridgeTabs} from "../src/protocol";
import {routeLabel} from "../src/routePolicy";
import {initialState, reduceApp} from "../src/state";
import type {AppState, CanonicalExecutionEvent, CanonicalExecutionEventKind, TranscriptLine} from "../src/types";

const paneIds = ["thinking", "tools", "timeline"] as const;
const timestamp = "2026-09-10T00:00:00Z";

function readyState(): AppState {
  return {
    ...initialState,
    tabs: [...initialState.tabs, ...buildBridgeTabs().filter((tab) => !initialState.tabs.some((existing) => existing.id === tab.id))],
  };
}

function event(kind: CanonicalExecutionEventKind, id = kind): CanonicalExecutionEvent {
  return {id, kind, sourceEventType: kind, phase: "running", title: `${kind} title`,
    content: `${kind} content`, summary: `${kind} summary`, timestamp};
}

function ingest(state: AppState, ...events: CanonicalExecutionEvent[]): AppState {
  return reduceApp(state, {type: "execution.events.ingest", events});
}

function pane(state: AppState, id: string) {
  return state.tabs.find((tab) => tab.id === id)!;
}

// The original projector generates fresh line IDs; compare all rendered fields
// against it, then separately assert the memo's deliberate identity guarantees.
function rendered(lines: TranscriptLine[]) {
  return lines.map(({kind, text, timestamp: stamp}) => ({kind, text, timestamp: stamp}));
}

function expectCanonicalViews(state: AppState): void {
  for (const id of paneIds) {
    expect(rendered(pane(state, id).lines)).toEqual(rendered(projectPaneLines(id, state.executionEventLog)));
  }
  expect(state.activityFeed.entries).toEqual(projectActivityEntries(state.executionEventLog));
  expect(rendered(state.chatTraceLines)).toEqual(rendered(projectChatTraceLines(state.executionEventLog, {
    expanded: state.chatTraceExpanded,
    showRaw: state.activityFeed.showRaw,
    routeLabel: routeLabel(state.routePolicy),
  })));
}

describe("execution projection memo", () => {
  test("first ingestion derives canonical output instead of trusting existing displays", () => {
    const stray: TranscriptLine = {id: "stray", kind: "system", text: "noncanonical display"};
    const source = reduceApp(readyState(), {type: "tab.replace", tabId: "thinking", lines: [stray]});
    const first = ingest(source, userPromptExecutionEvent("Inspect this project", timestamp));
    expect(pane(first, "thinking").lines).toEqual([]);
    expectCanonicalViews(first);
    const narrated = ingest(first, event("assistant_text"));
    expect(narrated.tabs).toBe(first.tabs);
    expect(narrated.activityFeed).toBe(first.activityFeed);
    expectCanonicalViews(narrated);
  });

  test("narration preserves pane, line, and activity identity while updating the chat trace", () => {
    const source = ingest(readyState(), userPromptExecutionEvent("Inspect this project", timestamp),
      event("thinking"), event("tool_call"), event("task"));
    Object.freeze(source.executionEventLog);
    source.executionEventLog.forEach(Object.freeze);
    const next = ingest(source, event("assistant_text"));
    expect(next.executionEventLog).not.toBe(source.executionEventLog);
    expect(next.tabs).toBe(source.tabs);
    expect(next.activityFeed).toBe(source.activityFeed);
    for (const id of paneIds) {
      expect(pane(next, id)).toBe(pane(source, id));
      expect(pane(next, id).lines).toBe(pane(source, id).lines);
      expect(pane(next, id).lines[0]).toBe(pane(source, id).lines[0]);
    }
    expect(next.chatTraceLines).not.toBe(source.chatTraceLines);
    expect(next.chatTraceLines.some((line) => line.text.includes("assistant_text content"))).toBe(true);
    expect(next.uiMode).toBe(source.uiMode);
    expect(next.activeTurn).toBe(source.activeTurn);
    expectCanonicalViews(next);
  });

  test("same-ID replacements and kind transitions invalidate every affected projection", () => {
    const thinking = event("thinking", "replaceable");
    let state = ingest(readyState(), thinking);
    const original = pane(state, "thinking").lines;
    state = ingest(state, {...thinking, content: "revised reasoning"});
    expect(pane(state, "thinking").lines).not.toBe(original);
    expect(pane(state, "thinking").lines[0].text).toBe("revised reasoning");
    expect(state.executionEventLog).toHaveLength(1);
    expectCanonicalViews(state);
    state = ingest(state, {...thinking, kind: "error", phase: "failed", title: "revised failure"});
    for (const id of paneIds) expect(pane(state, id).lines[0].text).toContain("revised failure");
    expectCanonicalViews(state);
    state = ingest(state, {...thinking, kind: "assistant_text", content: "replacement narration"});
    for (const id of paneIds) expect(pane(state, id).lines).toEqual([]);
    expect(state.activityFeed.entries).toEqual([]);
    expectCanonicalViews(state);
  });

  test("evicting a relevant event at retention invalidates its views even for narration input", () => {
    const source = ingest(readyState(), event("thinking", "oldest"),
      ...Array.from({length: 3999}, (_, index) => event("assistant_text", `narration-${index}`)));
    expect(source.executionEventLog).toHaveLength(4000);
    expect(pane(source, "thinking").lines).toHaveLength(1);
    const next = ingest(source, event("assistant_text", "newest"));
    expect(next.executionEventLog).toHaveLength(4000);
    expect(pane(next, "thinking").lines).toEqual([]);
    expect(next.activityFeed.entries).toEqual([]);
    expect(pane(next, "tools")).toBe(pane(source, "tools"));
    expectCanonicalViews(next);
  });

  test("independent tab and activity writers never contaminate cached canonical output", () => {
    const canonical = ingest(readyState(), event("thinking"), event("tool_call"), event("task"));
    const stray: TranscriptLine = {id: "stray", kind: "system", text: "noncanonical extra line"};
    let state = reduceApp(canonical, {type: "tab.append", tabId: "thinking", lines: [stray]});
    state = reduceApp(state, {type: "tab.replace", tabId: "tools", lines: [stray]});
    state = reduceApp(state, {type: "activity.ingest", entries: [{id: "stray", kind: "status", phase: "running", title: "noncanonical activity"}]});
    const next = ingest(state, event("assistant_text"));
    for (const id of paneIds) expect(pane(next, id).lines).toBe(pane(canonical, id).lines);
    expect(pane(next, "thinking")).not.toBe(pane(state, "thinking"));
    expect(pane(next, "timeline")).toBe(pane(state, "timeline"));
    expect(next.activityFeed.entries).toBe(canonical.activityFeed.entries);
    expectCanonicalViews(next);
  });

  test("trace expansion and raw toggles still reproject chat with the current options", () => {
    const thinking = {...event("thinking"), raw: {fixture_detail: "owner evidence"}};
    let state = ingest(readyState(), userPromptExecutionEvent("Explain", timestamp), thinking);
    state = reduceApp(state, {type: "trace.toggle"});
    state = reduceApp(state, {type: "activity.raw.toggle"});
    const next = ingest(state, event("assistant_text"));
    expect(next.chatTraceExpanded).toBe(true);
    expect(next.activityFeed.showRaw).toBe(true);
    expect(next.activityFeed).toBe(state.activityFeed);
    expect(next.tabs).toBe(state.tabs);
    expectCanonicalViews(next);
  });

  test("accepted-command replacement refreshes correlated session-end suppression", () => {
    const accepted = canonicalEventsFromBridgeEvent({type: "command.result", request_id: "command-1", command: "/status", output: "accepted", outcome: "accepted", ok: true, created_at: timestamp})[0];
    const ended = canonicalEventsFromBridgeEvent({type: "session_end", request_id: "command-1", success: true, created_at: timestamp})[0];
    let state = ingest(readyState(), userPromptExecutionEvent("/status", timestamp), accepted, ended);
    expect(state.activityFeed.entries.some((entry) => entry.id === ended.id)).toBe(false);
    const narrated = ingest(state, event("assistant_text"));
    expect(narrated.activityFeed).toBe(state.activityFeed);
    expectCanonicalViews(narrated);
    state = ingest(narrated, {...accepted, phase: "complete", raw: {...accepted.raw, outcome: "completed", completed: true}, content: "completed"});
    expect(state.activityFeed.entries.some((entry) => entry.id === ended.id)).toBe(true);
    expectCanonicalViews(state);
    state = ingest(state, {...accepted, phase: "failed", raw: {...accepted.raw, outcome: "failed", ok: false}, content: "failed"});
    expect(state.activityFeed.entries.find((entry) => entry.id === accepted.id)?.phase).toBe("failed");
    expectCanonicalViews(state);
  });

  test("event order and independent immutable history branches cannot reuse wrong output", () => {
    const first = event("thinking", "first");
    const second = {...event("thinking", "second"), content: "second reasoning"};
    const sourceEvents = [first, second];
    const source = projectExecutionViews([], sourceEvents);
    const reversedEvents = [second, first];
    const reversed = projectExecutionViews(sourceEvents, reversedEvents);
    expect(reversed.thinking).not.toBe(source.thinking);
    expect(reversed.thinking.map((line) => line.text)).toEqual(["second reasoning", "thinking content"]);
    const sibling = projectExecutionViews(sourceEvents, [first, second, event("assistant_text")]);
    expect(sibling.thinking).toBe(source.thinking);
    expect(projectExecutionViews(reversedEvents, sourceEvents)).toBe(source);
  });

  test("restored state with an uncached canonical array derives its own projections", () => {
    const original = ingest(readyState(), event("thinking", "original"));
    const replacement = {...event("thinking", "restored"), content: "restored reasoning"};
    const restored = reduceApp(original, {type: "state.replace", state: {...original, executionEventLog: [replacement]}});
    const next = ingest(restored, event("assistant_text"));
    expect(pane(next, "thinking").lines[0].text).toBe("restored reasoning");
    expectCanonicalViews(next);
  });

  const kinds: CanonicalExecutionEventKind[] = ["user_prompt", "assistant_text", "thinking", "tool_call", "tool_result", "approval", "task", "command", "status", "error"];
  for (const kind of kinds) {
    test(`the ${kind} dependency remains equivalent to direct projection`, () => {
      const item = event(kind, "replaceable");
      const source = ingest(readyState(), userPromptExecutionEvent("Inspect", timestamp), item);
      const next = ingest(source, {...item, phase: "failed", title: "updated title", content: "updated content", summary: "updated summary"});
      expectCanonicalViews(next);
    });
  }
});
