import {describe, expect, test} from "bun:test";

import {
  canonicalEventsFromBridgeEvent,
  mergeExecutionEvents,
  projectActivityEntries,
  projectChatTraceLines,
  projectPaneLines,
  userPromptExecutionEvent,
} from "../src/executionLog";

describe("canonicalEventsFromBridgeEvent", () => {
  test("projects the core session trace into chat, tools, thinking, timeline, and activity views", () => {
    const events = [
      userPromptExecutionEvent("Second prompt", "2026-04-04T11:59:59Z"),
      ...canonicalEventsFromBridgeEvent({
        type: "text_complete",
        content: "First answer",
        created_at: "2026-04-04T12:00:00Z",
      }),
      ...canonicalEventsFromBridgeEvent({
        type: "thinking_complete",
        content: "Reasoning about the second prompt",
        created_at: "2026-04-04T12:00:01Z",
      }),
      ...canonicalEventsFromBridgeEvent({
        type: "tool_call_complete",
        tool_name: "exec_command",
        tool_call_id: "tool-42",
        arguments: "{\"cmd\":\"git status\"}",
        created_at: "2026-04-04T12:00:02Z",
      }),
      ...canonicalEventsFromBridgeEvent({
        type: "tool_result",
        tool_name: "exec_command",
        tool_call_id: "tool-42",
        success: true,
        content: "working tree clean",
        created_at: "2026-04-04T12:00:03Z",
      }),
      ...canonicalEventsFromBridgeEvent({
        type: "permission.decision",
        payload: {
          version: "v1",
          domain: "permission_decision",
          action_id: "act-1",
          tool_name: "exec_command",
          risk: "medium",
          decision: "require_approval",
          rationale: "needs approval",
          policy_source: "runtime",
          requires_confirmation: true,
          metadata: {created_at: "2026-04-04T12:00:04Z"},
        },
      }),
      ...canonicalEventsFromBridgeEvent({
        type: "session_end",
        session_id: "sess-9",
        success: true,
        created_at: "2026-04-04T12:00:05Z",
      }),
    ];

    expect(events.map((event) => event.kind)).toEqual([
      "user_prompt",
      "assistant_text",
      "thinking",
      "tool_call",
      "tool_result",
      "approval",
      "status",
    ]);

    const chatLines = projectChatTraceLines(events);
    const expandedChatLines = projectChatTraceLines(events, {expanded: true});
    const thinkingLines = projectPaneLines("thinking", events);
    const toolLines = projectPaneLines("tools", events);
    const timelineLines = projectPaneLines("timeline", events);
    const activityEntries = projectActivityEntries(events);

    // F-172: collapsed by default — response above one trace summary line, no step detail.
    expect(chatLines.some((line) => line.kind === "user" && line.text.includes("Second prompt"))).toBe(true);
    expect(chatLines.some((line) => line.kind === "assistant" && line.text === "First answer")).toBe(true);
    expect(chatLines.filter((line) => /^✓ \d+ steps? · .+ · \^T expand$/.test(line.text))).toHaveLength(1);
    expect(chatLines.some((line) => line.text.includes("Reasoning about the second prompt"))).toBe(false);
    expect(chatLines.some((line) => line.text.includes("Turn 1"))).toBe(false);
    // ^T expanded view carries the step detail.
    expect(expandedChatLines.some((line) => line.kind === "system" && line.text.includes("Reasoning about the second prompt"))).toBe(true);
    expect(expandedChatLines.some((line) => line.kind === "tool" && line.text.includes("Tool | exec_command | working tree clean"))).toBe(true);
    expect(expandedChatLines.some((line) => line.kind === "tool" && line.text.includes("Approval | exec_command requires require_approval"))).toBe(true);
    expect(expandedChatLines.filter((line) => /^✓ \d+ steps? · .+ · \^T collapse$/.test(line.text))).toHaveLength(1);
    expect(thinkingLines.some((line) => line.text.includes("Reasoning about the second prompt"))).toBe(true);
    expect(toolLines.some((line) => line.text.includes("git status"))).toBe(true);
    expect(toolLines.some((line) => line.text.includes("working tree clean"))).toBe(true);
    expect(timelineLines.some((line) => line.text.includes("session ended | sess-9"))).toBe(true);
    expect(activityEntries.some((entry) => entry.kind === "thinking")).toBe(true);
    expect(activityEntries.some((entry) => entry.kind === "tool" && entry.correlationId === "tool-42")).toBe(true);
    expect(activityEntries.some((entry) => entry.kind === "approval" && entry.correlationId === "act-1")).toBe(true);
    expect(activityEntries.some((entry) => entry.kind === "status" && entry.title.includes("session ended"))).toBe(true);
  });

  test("F-172: completed turn renders response-first with exactly one trace summary line and zero raw id fields", () => {
    const sessionHex = "9f86d081884c7d659a2feaa0c55ad015";
    const events = [
      userPromptExecutionEvent("hello?", "2026-06-12T10:00:00Z"),
      ...canonicalEventsFromBridgeEvent({
        type: "session.ack",
        session_id: sessionHex,
        provider: "codex",
        model: "gpt-5.4",
        request_id: "3",
        created_at: "2026-06-12T10:00:01Z",
      }),
      ...canonicalEventsFromBridgeEvent({type: "thinking_complete", content: "routing the greeting", created_at: "2026-06-12T10:00:02Z"}),
      ...canonicalEventsFromBridgeEvent({
        type: "tool_call_complete",
        tool_name: "exec_command",
        tool_call_id: "c0ffee00c0ffee00",
        arguments: "{\"cmd\":\"true\"}",
        created_at: "2026-06-12T10:00:03Z",
      }),
      ...canonicalEventsFromBridgeEvent({
        type: "tool_result",
        tool_name: "exec_command",
        tool_call_id: "c0ffee00c0ffee00",
        success: true,
        content: "ok",
        created_at: "2026-06-12T10:00:04Z",
      }),
      ...canonicalEventsFromBridgeEvent({type: "text_complete", content: "Hello! The Helm is listening.", created_at: "2026-06-12T10:00:05Z"}),
      ...canonicalEventsFromBridgeEvent({type: "session_end", session_id: sessionHex, success: true, request_id: "3", created_at: "2026-06-12T10:00:06Z"}),
    ];

    const hexId = /[0-9a-f]{12,}/i;
    const summaryPattern = /^[✓✖▶] \d+ steps? · .+ · \^T (expand|collapse)$/;

    const collapsed = projectChatTraceLines(events);
    expect(collapsed.filter((line) => summaryPattern.test(line.text))).toHaveLength(1);
    const responseIndex = collapsed.findIndex((line) => line.text === "Hello! The Helm is listening.");
    const summaryIndex = collapsed.findIndex((line) => summaryPattern.test(line.text));
    expect(responseIndex).toBeGreaterThanOrEqual(0);
    expect(responseIndex).toBeLessThan(summaryIndex);
    expect(collapsed[summaryIndex]?.text).toMatch(/^✓ \d+ steps · codex:gpt-5\.4 · \^T expand$/);
    expect(collapsed.some((line) => hexId.test(line.text))).toBe(false);
    expect(collapsed.some((line) => line.text.includes("routing the greeting"))).toBe(false);

    const expanded = projectChatTraceLines(events, {expanded: true});
    expect(expanded.filter((line) => summaryPattern.test(line.text))).toHaveLength(1);
    expect(expanded.some((line) => line.text.includes("routing the greeting"))).toBe(true);
    expect(expanded.some((line) => hexId.test(line.text))).toBe(false);

    const expandedRaw = projectChatTraceLines(events, {expanded: true, showRaw: true});
    expect(expandedRaw.some((line) => hexId.test(line.text))).toBe(false);

    const recollapsed = projectChatTraceLines(events, {expanded: false});
    expect(recollapsed.some((line) => line.text.includes("routing the greeting"))).toBe(false);
  });

  test("deduplicates canonical execution events by id during merges", () => {
    const original = [
      {
        id: "tool_result:tool-7",
        sourceEventType: "tool_result",
        kind: "tool_result" as const,
        phase: "complete" as const,
        title: "exec_command",
        summary: "first output",
        correlationId: "tool-7",
      },
    ];
    const replacement = [
      {
        id: "tool_result:tool-7",
        sourceEventType: "tool_result",
        kind: "tool_result" as const,
        phase: "complete" as const,
        title: "exec_command",
        summary: "replacement output",
        correlationId: "tool-7",
      },
    ];

    const merged = mergeExecutionEvents(original, replacement);

    expect(merged).toHaveLength(1);
    expect(merged[0]?.summary).toBe("replacement output");
  });

  test("keeps deep chat trace scrollback instead of truncating to a tiny recent window", () => {
    const events = Array.from({length: 30}, (_, index) => [
      userPromptExecutionEvent(`Prompt ${index + 1}`, `2026-04-04T12:${String(index).padStart(2, "0")}:00Z`),
      ...canonicalEventsFromBridgeEvent({
        type: "text_complete",
        content: `Answer ${index + 1}`,
        created_at: `2026-04-04T12:${String(index).padStart(2, "0")}:30Z`,
      }),
    ]).flat();

    const chatLines = projectChatTraceLines(events);

    expect(chatLines.some((line) => line.kind === "user" && line.text.includes("Prompt 1"))).toBe(true);
    expect(chatLines.some((line) => line.kind === "assistant" && line.text.includes("Answer 1"))).toBe(true);
    expect(chatLines.some((line) => line.kind === "user" && line.text.includes("Prompt 30"))).toBe(true);
    expect(chatLines.some((line) => line.kind === "assistant" && line.text.includes("Answer 30"))).toBe(true);
  });

  test("surfaces failed tool results and command results truthfully", () => {
    const events = [
      ...canonicalEventsFromBridgeEvent({
        type: "tool_result",
        tool_name: "exec_command",
        tool_call_id: "tool-8",
        success: false,
        content: "permission denied",
        created_at: "2026-04-04T12:20:00Z",
      }),
      ...canonicalEventsFromBridgeEvent({
        type: "command.result",
        command: {command: "/status"},
        output: "bridge connected",
        created_at: "2026-04-04T12:20:01Z",
      }),
    ];

    const toolLines = projectPaneLines("tools", events);
    const timelineLines = projectPaneLines("timeline", events);
    const activityEntries = projectActivityEntries(events);

    expect(toolLines.some((line) => line.text.includes("! exec_command: permission denied"))).toBe(true);
    expect(timelineLines.some((line) => line.text.includes("intent /status | bridge connected"))).toBe(true);
    expect(activityEntries.some((entry) => entry.kind === "tool" && entry.phase === "failed")).toBe(true);
    expect(activityEntries.some((entry) => entry.kind === "pivot" && entry.title === "intent /status")).toBe(true);
  });
});
