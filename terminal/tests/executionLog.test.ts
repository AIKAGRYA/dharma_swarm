import {describe, expect, test} from "bun:test";

import {
  canonicalEventsFromBridgeEvent,
  latestChatTurnRoute,
  localCommandResultExecutionEvent,
  mergeExecutionEvents,
  projectActivityEntries,
  projectChatTraceLines,
  projectPaneLines,
  queuedPromptExecutionEvent,
  userPromptExecutionEvent,
} from "../src/executionLog";

describe("canonicalEventsFromBridgeEvent", () => {
  test("renders only explicit completed command outcomes as complete", () => {
    const projected = (event: Record<string, unknown>) => projectChatTraceLines([
      userPromptExecutionEvent("/status", "2026-08-09T00:00:00Z"),
      ...canonicalEventsFromBridgeEvent({
        type: "command.result",
        command: "/status",
        output: "status result",
        created_at: "2026-08-09T00:00:01Z",
        ...event,
      }),
    ]).map((line) => line.text);

    expect(projected({outcome: "completed", ok: true}).some((line) => line.startsWith("■"))).toBe(true);
    expect(projected({outcome: "accepted", ok: true}).some((line) => line.startsWith("… thinking"))).toBe(true);
    for (const event of [
      {outcome: "unsupported", ok: false},
      {outcome: "failed", ok: false},
      {},
      {outcome: "completed", ok: false},
    ]) {
      expect(projected(event).some((line) => line.startsWith("✖ failed"))).toBe(true);
      expect(projected(event).some((line) => line.startsWith("■"))).toBe(false);
    }

    const acceptedEvents = [
      userPromptExecutionEvent("/status", "2026-08-09T00:00:00Z"),
      ...canonicalEventsFromBridgeEvent({
        type: "command.result",
        request_id: "command-accepted",
        command: "/status",
        output: "accepted for background processing",
        outcome: "accepted",
        ok: true,
        created_at: "2026-08-09T00:00:01Z",
      }),
      ...canonicalEventsFromBridgeEvent({
        type: "session_end",
        request_id: "command-accepted",
        session_id: "session-command-accepted",
        success: true,
        created_at: "2026-08-09T00:00:02Z",
      }),
    ];
    const acceptedThenEnded = projectChatTraceLines(acceptedEvents).map((line) => line.text);
    const acceptedExpanded = projectChatTraceLines(acceptedEvents, {expanded: true}).map((line) => line.text);
    const acceptedActivity = projectActivityEntries(acceptedEvents);
    expect(acceptedThenEnded.some((line) => line.startsWith("… thinking"))).toBe(true);
    expect(acceptedThenEnded.some((line) => line.startsWith("■"))).toBe(false);
    expect(acceptedExpanded.some((line) => line.includes("■ status | session ended"))).toBe(false);
    expect(acceptedActivity.some((entry) => entry.title === "session ended" && entry.phase === "complete")).toBe(false);

    const unknownLocal = [
      userPromptExecutionEvent("/hlep", "2026-08-09T00:00:03Z"),
      localCommandResultExecutionEvent("/hlep", "unknown command /hlep", "2026-08-09T00:00:04Z", "unsupported"),
    ];
    const unknownLines = projectChatTraceLines(unknownLocal, {expanded: true}).map((line) => line.text);
    expect(unknownLines.some((line) => line.startsWith("✖ failed"))).toBe(true);
    expect(unknownLines.some((line) => line.startsWith("■"))).toBe(false);
  });

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
    expect(chatLines.filter((line) => /^■ (\d+s|done) · .+ · \^T details$/.test(line.text))).toHaveLength(1);
    expect(chatLines.some((line) => line.text.includes("Reasoning about the second prompt"))).toBe(false);
    expect(chatLines.some((line) => line.text.includes("Turn 1"))).toBe(false);
    // ^T expanded view carries the step detail.
    expect(expandedChatLines.some((line) => line.kind === "system" && line.text.includes("Reasoning about the second prompt"))).toBe(true);
    expect(expandedChatLines.some((line) => line.kind === "tool" && line.text.includes("Tool | exec_command | working tree clean"))).toBe(true);
    expect(expandedChatLines.some((line) => line.kind === "tool" && line.text.includes("Approval | exec_command requires require_approval"))).toBe(true);
    expect(expandedChatLines.filter((line) => /^■ (\d+s|done) · .+ · \^T collapse$/.test(line.text))).toHaveLength(1);
    expect(thinkingLines.some((line) => line.text.includes("Reasoning about the second prompt"))).toBe(true);
    expect(toolLines.some((line) => line.text.includes("git status"))).toBe(true);
    expect(toolLines.some((line) => line.text.includes("working tree clean"))).toBe(true);
    expect(timelineLines.some((line) => line.text.includes("session ended | sess-9"))).toBe(true);
    expect(activityEntries.some((entry) => entry.kind === "thinking")).toBe(true);
    expect(activityEntries.some((entry) => entry.kind === "tool" && entry.correlationId === "tool-42")).toBe(true);
    expect(activityEntries.some((entry) => entry.kind === "approval" && entry.correlationId === "act-1")).toBe(true);
    expect(activityEntries.some((entry) => entry.kind === "status" && entry.title.includes("session ended"))).toBe(true);
  });

  test("projects cancellation acknowledgements without terminating the turn, then renders the correlated terminal as cancelled", () => {
    const base = [
      userPromptExecutionEvent("run the long audit", "2026-07-21T09:00:00Z"),
      ...canonicalEventsFromBridgeEvent({
        type: "session.ack",
        request_id: "run-17",
        session_id: "session-17",
        provider: "claude",
        model: "claude-opus-4-8",
        created_at: "2026-07-21T09:00:01Z",
      }),
    ];
    const rejectedAck = canonicalEventsFromBridgeEvent({
      type: "session.cancelled",
      request_id: "cancel-16",
      target_request_id: "run-17",
      cancelled: false,
      reason: "already_cancelling",
      active_request_id: "run-17",
      session_id: "session-17",
      provider: "claude",
      phase: "cancelling",
      created_at: "2026-07-21T09:00:02Z",
    });

    expect(rejectedAck).toHaveLength(1);
    expect(rejectedAck[0]).toMatchObject({
      kind: "status",
      phase: "failed",
      title: "cancellation rejected",
      summary: "already cancelling",
      correlationId: "run-17",
    });
    const stillRunning = projectChatTraceLines([...base, ...rejectedAck]);
    expect(stillRunning.some((line) => line.text === "… thinking · claude:claude-opus-4-8")).toBe(true);
    expect(stillRunning.some((line) => /cancelled|failed|no response/i.test(line.text))).toBe(false);
    const expandedRejected = projectChatTraceLines([...base, ...rejectedAck], {expanded: true});
    expect(expandedRejected.some((line) => line.text.includes("- ! Status | cancellation rejected | already cancelling"))).toBe(true);
    expect(expandedRejected.some((line) => line.text.includes("- ■ Status | cancellation rejected"))).toBe(false);
    expect(projectPaneLines("timeline", [...base, ...rejectedAck]).some((line) => line.text.includes("cancellation rejected | already cancelling"))).toBe(true);

    const cancelledEnd = canonicalEventsFromBridgeEvent({
      type: "session_end",
      request_id: "run-17",
      session_id: "session-17",
      provider_id: "claude",
      success: false,
      cancelled: true,
      error_code: "cancelled",
      error_message: "cancelled by operator",
      created_at: "2026-07-21T09:00:03Z",
    });
    const acceptedAck = canonicalEventsFromBridgeEvent({
      type: "session.cancelled",
      request_id: "cancel-17",
      target_request_id: "run-17",
      cancelled: true,
      reason: "cancel_requested",
      session_id: "session-17",
      provider: "claude",
      target_phase: "running",
      created_at: "2026-07-21T09:00:04Z",
    });
    const cancelledEvents = [...base, ...cancelledEnd, ...acceptedAck];
    const cancelledLines = projectChatTraceLines(cancelledEvents);

    expect(cancelledEnd[0]).toMatchObject({
      kind: "status",
      phase: "failed",
      title: "session cancelled",
      detail: ["Request run-17", "Turn cancelled"],
    });
    expect(acceptedAck[0]).toMatchObject({
      kind: "status",
      phase: "complete",
      title: "cancellation accepted",
      summary: "cancel requested",
    });
    expect(cancelledLines.filter((line) => line.text === "⊘ cancelled · claude:claude-opus-4-8 · ^T details")).toHaveLength(1);
    expect(cancelledLines.some((line) => /failed|no response/i.test(line.text))).toBe(false);

    const timeline = projectPaneLines("timeline", cancelledEvents);
    expect(timeline.some((line) => line.text.includes("session cancelled | session-17"))).toBe(true);
    expect(timeline.some((line) => line.text.includes("cancellation accepted | cancel requested"))).toBe(true);
    const activity = projectActivityEntries(cancelledEvents);
    expect(activity.some((entry) => entry.kind === "status" && entry.title === "session cancelled")).toBe(true);
    expect(activity.some((entry) => entry.kind === "status" && entry.title === "cancellation accepted")).toBe(true);
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
    const summaryPattern = /^(■ (\d+s|done)|✖ failed|… thinking) · .+( · \^T (details|collapse))?$/;

    const collapsed = projectChatTraceLines(events);
    expect(collapsed.filter((line) => summaryPattern.test(line.text))).toHaveLength(1);
    const responseIndex = collapsed.findIndex((line) => line.text === "Hello! The Helm is listening.");
    const summaryIndex = collapsed.findIndex((line) => summaryPattern.test(line.text));
    expect(responseIndex).toBeGreaterThanOrEqual(0);
    expect(responseIndex).toBeLessThan(summaryIndex);
    // 10:00:00 prompt -> 10:00:06 session_end = a 6s turn.
    expect(collapsed[summaryIndex]?.text).toMatch(/^■ 6s · codex:gpt-5\.4 · \^T details$/);
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

  test("F-174 display truth: latestChatTurnRoute names whichever model actually answered, not the static default", () => {
    // No turns yet → undefined (the caller falls back to the configured route).
    expect(latestChatTurnRoute([])).toBeUndefined();

    const events = [
      userPromptExecutionEvent("what model are you?", "2026-06-16T10:00:00Z"),
      ...canonicalEventsFromBridgeEvent({
        type: "session.ack",
        session_id: "9f86d081884c7d659a2feaa0c55ad015",
        provider: "claude",
        model: "claude-opus-4-8",
        request_id: "3",
        created_at: "2026-06-16T10:00:01Z",
      }),
      ...canonicalEventsFromBridgeEvent({type: "text_complete", content: "I'm Claude.", created_at: "2026-06-16T10:00:02Z"}),
    ];
    // The status line must read claude:claude-opus-4-8 — the real route — even
    // though defaultRoutePolicy() is still codex:gpt-5.4.
    expect(latestChatTurnRoute(events)).toBe("claude:claude-opus-4-8");
  });

  test("response-owned SessionStart outranks requested route without changing selection", () => {
    const prompt = userPromptExecutionEvent("which Grok answered?", "2026-08-13T15:00:00Z");
    const ack = canonicalEventsFromBridgeEvent({type: "session.ack", provider: "grok_oauth", model: "grok-4.6"});
    const served = canonicalEventsFromBridgeEvent({type: "session_start", provider_id: "grok_oauth", model: "grok-4.6-build"});

    expect(latestChatTurnRoute([prompt, ...ack])).toBe("grok_oauth:grok-4.6");
    expect(latestChatTurnRoute([prompt, ...ack, ...served])).toBe("grok_oauth:grok-4.6-build");
    expect(latestChatTurnRoute([prompt, ...served, ...ack])).toBe("grok_oauth:grok-4.6-build");
    expect(canonicalEventsFromBridgeEvent({type: "session_start", provider_id: "grok_oauth", model: ""})).toEqual([]);
    const summary = projectChatTraceLines([prompt, ...ack, ...served]).at(-1)?.text ?? "";
    expect(summary).toContain("grok_oauth:grok-4.6-build");
    expect(summary).not.toContain("grok_oauth:grok-4.6 ·");
  });

  test("session acknowledgement exposes the bounded owned-context disposition", () => {
    const [acknowledgement] = canonicalEventsFromBridgeEvent({
      type: "session.ack",
      session_id: "session-context-1",
      provider: "claude",
      model: "claude-sonnet-5",
      context_disposition: "attached_redacted",
      context_digest: `sha256:${"a".repeat(64)}`,
    });

    expect(acknowledgement?.detail).toContain("Initial lane context attached_redacted · sha256:aaaaaaaaaaaaaaaa");
  });

  test("final context receipt exposes the winning lane disposition", () => {
    const [receipt] = canonicalEventsFromBridgeEvent({
      type: "context_receipt",
      provider_id: "fallback",
      model_id: "winner-model",
      disposition: "not_attached_fallback",
      context_digest: "",
      source_epoch: `sha256:${"b".repeat(64)}`,
      authority: "NONE",
      lane_outcome: "completed",
      timestamp: 100,
      boundary_timestamp: 100,
      outcome_timestamp: 123,
    });

    expect(receipt?.title).toBe("context boundary sealed");
    expect(receipt?.summary).toBe("fallback:winner-model");
    expect(receipt?.detail).toContain("Final lane context not_attached_fallback");
    expect(receipt?.detail).toContain("Lane completed");
    expect(receipt?.detail).toContain("Authority NONE");
    expect(receipt?.timestamp).toBe("123");
  });

  test("F-173: assistant bridge event renders its message as the turn's response in the chat transcript", () => {
    const sessionHex = "9f86d081884c7d659a2feaa0c55ad015";
    const answer = "I am the Helm. Identity intents route straight through me.";
    // Wire shape per bridge_events.md §1.16: {type:"assistant", request_id, message} — no timestamp.
    const assistantEvents = canonicalEventsFromBridgeEvent({type: "assistant", request_id: "7", message: answer});
    expect(assistantEvents).toHaveLength(1);
    expect(assistantEvents[0]?.kind).toBe("assistant_text");
    expect(assistantEvents[0]?.phase).toBe("complete");
    expect(assistantEvents[0]?.content).toBe(answer);
    // Empty messages stay silent instead of minting an empty response.
    expect(canonicalEventsFromBridgeEvent({type: "assistant", request_id: "8", message: "   "})).toHaveLength(0);
    // Identical canned answers on different turns stay distinct (id keys on request_id).
    expect(canonicalEventsFromBridgeEvent({type: "assistant", request_id: "9", message: answer})[0]?.id).not.toBe(assistantEvents[0]?.id);

    const events = [
      userPromptExecutionEvent("who are you and what can you do?", "2026-06-12T11:00:00Z"),
      ...canonicalEventsFromBridgeEvent({
        type: "session.ack",
        session_id: sessionHex,
        provider: "codex",
        model: "gpt-5.4",
        request_id: "7",
        created_at: "2026-06-12T11:00:01Z",
      }),
      ...assistantEvents,
      ...canonicalEventsFromBridgeEvent({type: "session_end", session_id: sessionHex, success: true, request_id: "7", created_at: "2026-06-12T11:00:02Z"}),
    ];

    const collapsed = projectChatTraceLines(events);
    const responseIndex = collapsed.findIndex((line) => line.kind === "assistant" && line.text === answer);
    const summaryIndex = collapsed.findIndex((line) => /^■ (\d+s|done) · codex:gpt-5\.4 · \^T details$/.test(line.text));
    expect(responseIndex).toBeGreaterThanOrEqual(0);
    expect(summaryIndex).toBeGreaterThanOrEqual(0);
    expect(responseIndex).toBeLessThan(summaryIndex);
    expect(collapsed.some((line) => line.text.includes("no response"))).toBe(false);
    expect(collapsed.some((line) => /[0-9a-f]{12,}/i.test(line.text))).toBe(false);
  });

  test("F-173: a turn that ends without any response-bearing event renders an explicit no-response marker, never bare complete", () => {
    const sessionHex = "9f86d081884c7d659a2feaa0c55ad015";
    const events = [
      userPromptExecutionEvent("second question with no answer", "2026-06-12T11:01:00Z"),
      ...canonicalEventsFromBridgeEvent({
        type: "session.ack",
        session_id: sessionHex,
        provider: "codex",
        model: "gpt-5.4",
        request_id: "8",
        created_at: "2026-06-12T11:01:01Z",
      }),
      ...canonicalEventsFromBridgeEvent({type: "session_end", session_id: sessionHex, success: true, request_id: "8", created_at: "2026-06-12T11:01:02Z"}),
    ];

    const collapsed = projectChatTraceLines(events);
    expect(collapsed.some((line) => line.kind === "error" && line.text === "✖ no response — turn ended without output")).toBe(true);
    // The turn's summary line carries the failed glyph — never an ■-complete with an empty body.
    expect(collapsed.filter((line) => /^■ (\d+s|done) · /.test(line.text))).toHaveLength(0);
    expect(collapsed.filter((line) => /^✖ failed · codex:gpt-5\.4 · \^T details$/.test(line.text))).toHaveLength(1);
    const markerIndex = collapsed.findIndex((line) => line.text.includes("no response"));
    const summaryIndex = collapsed.findIndex((line) => /^✖ failed · /.test(line.text));
    expect(markerIndex).toBeLessThan(summaryIndex);

    // A turn answered via a command/intent step (intent.result shortcut) is response-bearing — no marker.
    const commandTurn = [
      userPromptExecutionEvent("show status", "2026-06-12T11:02:00Z"),
      ...canonicalEventsFromBridgeEvent({
        type: "command.result",
        command: {command: "/status"},
        outcome: "completed",
        ok: true,
        output: "bridge connected",
        created_at: "2026-06-12T11:02:01Z",
      }),
      ...canonicalEventsFromBridgeEvent({type: "session_end", session_id: sessionHex, success: true, request_id: "9", created_at: "2026-06-12T11:02:02Z"}),
    ];
    const commandCollapsed = projectChatTraceLines(commandTurn);
    expect(commandCollapsed.some((line) => line.text.includes("no response"))).toBe(false);
    expect(commandCollapsed.filter((line) => /^■ (\d+s|done) · /.test(line.text))).toHaveLength(1);
  });

  test("F-157: a prompt queued while the bridge is offline renders the explicit queued state, never running", () => {
    const events = [
      userPromptExecutionEvent("what is the helm", "2026-06-12T12:00:00Z"),
      queuedPromptExecutionEvent("q1-test", undefined, "2026-06-12T12:00:00Z"),
    ];

    const collapsed = projectChatTraceLines(events, {routeLabel: "codex:gpt-5.4"});
    // The turn row names the queued state explicitly.
    expect(collapsed.filter((line) => /^○ queued \(backend offline\) · codex:gpt-5\.4 · \^T details$/.test(line.text))).toHaveLength(1);
    // Never a running glyph, the word running, or optimistic local steps on an offline turn.
    expect(collapsed.some((line) => line.text.includes("▶"))).toBe(false);
    expect(collapsed.some((line) => /running/i.test(line.text))).toBe(false);
    expect(collapsed.some((line) => line.text.includes("bootstrapping context") || line.text.includes("selecting route"))).toBe(false);

    const expanded = projectChatTraceLines(events, {expanded: true, routeLabel: "codex:gpt-5.4"});
    expect(expanded.some((line) => line.text.includes("Status | queued (backend offline)"))).toBe(true);
    expect(expanded.some((line) => line.text.includes("bootstrapping context") || line.text.includes("selecting route"))).toBe(false);
  });

  test("F-157: bridge connect resolves a queued turn to dispatched or failed — no third silent state", () => {
    const base = [
      userPromptExecutionEvent("what is the helm", "2026-06-12T12:00:00Z"),
      queuedPromptExecutionEvent("q1-test", undefined, "2026-06-12T12:00:00Z"),
    ];

    // Dispatched: the queued event is replaced in place (stable id) and the turn returns to running.
    const dispatched = mergeExecutionEvents(base, [queuedPromptExecutionEvent("q1-test", "dispatched", "2026-06-12T12:00:30Z")]);
    expect(dispatched).toHaveLength(2);
    const dispatchedLines = projectChatTraceLines(dispatched, {routeLabel: "codex:gpt-5.4"});
    expect(dispatchedLines.some((line) => line.text.includes("queued (backend offline)"))).toBe(false);
    // FACE-1: a dispatched (running) turn shows the quiet thinking row — no glyph, no step count.
    expect(dispatchedLines.filter((line) => /^… thinking · codex:gpt-5\.4$/.test(line.text))).toHaveLength(1);

    // The dispatched turn then completes normally once real bridge events stream in.
    const completed = mergeExecutionEvents(dispatched, [
      ...canonicalEventsFromBridgeEvent({type: "text_complete", content: "The Helm hears you.", created_at: "2026-06-12T12:00:31Z"}),
      ...canonicalEventsFromBridgeEvent({type: "session_end", session_id: "s", success: true, request_id: "3", created_at: "2026-06-12T12:00:32Z"}),
    ]);
    const completedLines = projectChatTraceLines(completed, {routeLabel: "codex:gpt-5.4"});
    expect(completedLines.some((line) => line.kind === "assistant" && line.text === "The Helm hears you.")).toBe(true);
    expect(completedLines.filter((line) => /^■ (\d+s|done) · codex:gpt-5\.4 · \^T details$/.test(line.text))).toHaveLength(1);

    // Failed: explicit ✖ on the turn row, never a silent state.
    const failed = mergeExecutionEvents(base, [queuedPromptExecutionEvent("q1-test", "failed", "2026-06-12T12:00:30Z")]);
    const failedLines = projectChatTraceLines(failed, {routeLabel: "codex:gpt-5.4"});
    expect(failedLines.some((line) => line.text.includes("queued (backend offline)"))).toBe(false);
    expect(failedLines.filter((line) => /^✖ failed · codex:gpt-5\.4 · \^T details$/.test(line.text))).toHaveLength(1);
    const failedExpanded = projectChatTraceLines(failed, {expanded: true, routeLabel: "codex:gpt-5.4"});
    expect(failedExpanded.some((line) => line.text.includes("dispatch failed after reconnect"))).toBe(true);
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
