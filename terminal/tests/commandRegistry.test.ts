import {describe, expect, test} from "bun:test";

import {COMMAND_TAB_REGISTRY, REGISTERED_SLASH_COMMANDS} from "../src/commandRegistry";
import {
  canonicalEventsFromBridgeEvent,
  localCommandResultExecutionEvent,
  mergeExecutionEvents,
  projectChatTraceLines,
  queuedPromptExecutionEvent,
  userPromptExecutionEvent,
} from "../src/executionLog";
import {commandTargetTab} from "../src/protocol";

const VALID_TABS = new Set([
  "chat",
  "agents",
  "models",
  "evolution",
  "sessions",
  "approvals",
  "runtime",
  "repo",
  "ontology",
  "control",
]);

describe("F-158 slash-command registry coverage", () => {
  test("every registered command maps to a valid pane through commandTargetTab", () => {
    expect(REGISTERED_SLASH_COMMANDS.length).toBeGreaterThan(0);
    for (const name of REGISTERED_SLASH_COMMANDS) {
      const tab = commandTargetTab(`/${name}`);
      expect(tab).toBe(COMMAND_TAB_REGISTRY[name] ?? "");
      expect(VALID_TABS.has(tab)).toBe(true);
    }
    expect(commandTargetTab("/definitely-not-registered")).toBe("control");
  });

  test("every registered command path produces a transcript entry — queued, failed, and result; no silent-swallow branch", () => {
    for (const name of REGISTERED_SLASH_COMMANDS) {
      const command = `/${name}`;

      // Offline path: echoed turn + explicit queued status.
      const queuedEvents = mergeExecutionEvents(
        [],
        [
          userPromptExecutionEvent(command, "2026-06-12T08:00:00Z"),
          queuedPromptExecutionEvent(`q-${name}`, undefined, "2026-06-12T08:00:01Z"),
        ],
      );
      const queuedLines = projectChatTraceLines(queuedEvents).map((line) => line.text);
      expect(queuedLines).toContain(`> ${command}`);
      expect(queuedLines.some((text) => text.includes("queued (backend offline)"))).toBe(true);

      // Failed resolution path: explicit ✖, never a vanished turn.
      const failedEvents = mergeExecutionEvents(queuedEvents, [
        queuedPromptExecutionEvent(`q-${name}`, "failed", "2026-06-12T08:00:02Z"),
      ]);
      const failedLines = projectChatTraceLines(failedEvents).map((line) => line.text);
      expect(failedLines).toContain(`> ${command}`);
      expect(failedLines.some((text) => text.startsWith("✖"))).toBe(true);

      // Result path: the command result closes the turn with a visible response.
      const resultEvents = mergeExecutionEvents(
        [],
        [
          userPromptExecutionEvent(command, "2026-06-12T08:00:00Z"),
          ...canonicalEventsFromBridgeEvent({
            type: "command.result",
            command,
            outcome: "completed",
            ok: true,
            summary: `ran ${name}`,
            output: `output for ${name}`,
            created_at: "2026-06-12T08:00:03Z",
          }),
        ],
      );
      const resultLines = projectChatTraceLines(resultEvents).map((line) => line.text);
      expect(resultLines).toContain(`> ${command}`);
      expect(resultLines.some((text) => text.includes(`output for ${name}`))).toBe(true);
      expect(resultLines.some((text) => text.startsWith("■"))).toBe(true);
      expect(resultLines.some((text) => text.startsWith("▶"))).toBe(false);
    }
  });

  test("a locally answered command (bare /model picker) closes its turn complete", () => {
    const events = mergeExecutionEvents(
      [],
      [
        userPromptExecutionEvent("/model", "2026-06-12T08:01:00Z"),
        localCommandResultExecutionEvent("/model", "route picker opened", "2026-06-12T08:01:01Z"),
      ],
    );
    const lines = projectChatTraceLines(events).map((line) => line.text);
    expect(lines).toContain("> /model");
    expect(lines.some((text) => text.includes("route picker opened"))).toBe(true);
    expect(lines.some((text) => text.startsWith("■"))).toBe(true);
  });

  test("a slash turn closes only on its own command result; prompt turns stay governed by session end", () => {
    // Mismatched result leaves the slash turn open (still running, awaiting its result).
    const mismatched = mergeExecutionEvents(
      [],
      [
        userPromptExecutionEvent("/status", "2026-06-12T08:02:00Z"),
        ...canonicalEventsFromBridgeEvent({
          type: "command.result",
          command: "/git",
          outcome: "completed",
          ok: true,
          output: "branch main",
          created_at: "2026-06-12T08:02:01Z",
        }),
      ],
    );
    const mismatchedLines = projectChatTraceLines(mismatched).map((line) => line.text);
    expect(mismatchedLines.some((text) => text.startsWith("… thinking"))).toBe(true);
    expect(mismatchedLines.some((text) => text.startsWith("■"))).toBe(false);

    // A natural-language prompt turn absorbs a command step WITHOUT closing —
    // its lifecycle still ends at session end (F-173 contract untouched).
    const promptTurn = mergeExecutionEvents(
      [],
      [
        userPromptExecutionEvent("show me the repo state", "2026-06-12T08:03:00Z"),
        ...canonicalEventsFromBridgeEvent({
          type: "command.result",
          command: "/git",
          outcome: "completed",
          ok: true,
          output: "branch main",
          created_at: "2026-06-12T08:03:01Z",
        }),
      ],
    );
    const promptLines = projectChatTraceLines(promptTurn).map((line) => line.text);
    expect(promptLines.some((text) => text.startsWith("… thinking"))).toBe(true);
    const closed = mergeExecutionEvents(promptTurn, [
      ...canonicalEventsFromBridgeEvent({
        type: "session_end",
        session_id: "sess-1",
        request_id: "req-1",
        success: true,
        created_at: "2026-06-12T08:03:02Z",
      }),
    ]);
    const closedLines = projectChatTraceLines(closed).map((line) => line.text);
    expect(closedLines.some((text) => text.startsWith("■"))).toBe(true);
  });

  test("command result responses pass the raw-identifier scrub", () => {
    const events = mergeExecutionEvents(
      [],
      [
        userPromptExecutionEvent("/status", "2026-06-12T08:04:00Z"),
        ...canonicalEventsFromBridgeEvent({
          type: "command.result",
          command: "/status",
          outcome: "completed",
          ok: true,
          output: "session 0123456789abcdef0123 active",
          created_at: "2026-06-12T08:04:01Z",
        }),
      ],
    );
    const lines = projectChatTraceLines(events).map((line) => line.text);
    expect(lines.some((text) => /[0-9a-fA-F]{12,}/.test(text))).toBe(false);
    expect(lines.some((text) => text.includes("session … active"))).toBe(true);
  });
});
