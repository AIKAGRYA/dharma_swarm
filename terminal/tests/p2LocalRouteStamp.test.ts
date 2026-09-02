import {describe, expect, test} from "bun:test";

import {
  canonicalEventsFromBridgeEvent,
  localAssistantExecutionEvent,
  localCommandResultExecutionEvent,
  localStatusExecutionEvent,
  projectChatTraceLines,
  userPromptExecutionEvent,
} from "../src/executionLog";

describe("P2 F4 immutable route attribution", () => {
  test("stamps provider routes only from explicit provider and model identity fields", () => {
    const stamped = canonicalEventsFromBridgeEvent({
      type: "text_complete",
      content: "owned provider answer",
      provider_id: "claude",
      model_id: "claude-sonnet-5",
    });
    const incomplete = canonicalEventsFromBridgeEvent({
      type: "text_complete",
      content: "identity-incomplete provider answer",
      provider_id: "claude",
    });
    const acknowledgement = canonicalEventsFromBridgeEvent({
      type: "session.ack",
      provider: "codex_text",
      model: "gpt-5.6-sol",
      request_id: "owned-ack",
    });

    expect(stamped[0]?.route).toBe("claude:claude-sonnet-5");
    expect(incomplete[0]?.route).toBeUndefined();
    expect(acknowledgement[0]?.route).toBe("codex_text:gpt-5.6-sol");
  });

  test("local events carry an explicit local route stamp at creation and project it immutably", () => {
    const localStatus = localStatusExecutionEvent("opening sessions", undefined, "queued", "2026-09-02T04:00:01Z");
    const localAssistant = localAssistantExecutionEvent("Opened Sessions.", "2026-09-02T04:00:01Z");
    const localResult = localCommandResultExecutionEvent(
      "open sessions",
      "Opened Sessions.",
      "2026-09-02T04:00:02Z",
    );

    expect(localStatus).toMatchObject({route: "local", raw: {source: "local"}});
    expect(localAssistant).toMatchObject({route: "local", raw: {source: "local"}});
    expect(localResult).toMatchObject({route: "local", raw: {source: "local"}});

    const events = [
      userPromptExecutionEvent("open sessions", "2026-09-02T04:00:00Z"),
      localAssistant,
      localResult,
    ];
    const beforeSwitch = projectChatTraceLines(events, {routeLabel: "codex_text:gpt-5.6-sol"});
    const afterSwitch = projectChatTraceLines(events, {routeLabel: "claude:claude-sonnet-5"});

    expect(beforeSwitch.at(-1)?.text).toMatch(/ · local · \^T details$/);
    expect(afterSwitch.at(-1)?.text).toBe(beforeSwitch.at(-1)?.text);
    expect(afterSwitch.at(-1)?.text).not.toContain("claude-sonnet-5");
  });

  test("an authoritative session start cannot be overwritten by a later stamped provider event", () => {
    const events = [
      userPromptExecutionEvent("served route question", "2026-09-02T04:02:00Z"),
      ...canonicalEventsFromBridgeEvent({
        type: "session_start",
        provider_id: "claude",
        model: "claude-sonnet-5",
        created_at: "2026-09-02T04:02:01Z",
      }),
      ...canonicalEventsFromBridgeEvent({
        type: "text_complete",
        content: "late event with contradictory source fields",
        provider_id: "other",
        model_id: "other-model",
        created_at: "2026-09-02T04:02:02Z",
      }),
    ];

    const projected = projectChatTraceLines(events, {routeLabel: "live:fallback"});
    expect(projected.at(-1)?.text).toContain("claude:claude-sonnet-5");
    expect(projected.at(-1)?.text).not.toContain("other:other-model");
  });

  test("stamp-missing provider turns are frozen to the ingest route and survive a later route switch", () => {
    const servedUnderCodex = [
      userPromptExecutionEvent("provider question", "2026-09-02T04:01:00Z"),
      ...canonicalEventsFromBridgeEvent(
        {type: "text_complete", content: "provider answer without an owned route stamp", created_at: "2026-09-02T04:01:01Z"},
        "codex_text:gpt-5.6-sol",
      ),
      ...canonicalEventsFromBridgeEvent(
        {type: "session_end", success: true, created_at: "2026-09-02T04:01:02Z"},
        "codex_text:gpt-5.6-sol",
      ),
    ];

    const beforeSwitch = projectChatTraceLines(servedUnderCodex, {routeLabel: "codex_text:gpt-5.6-sol"});
    const afterSwitch = projectChatTraceLines(servedUnderCodex, {routeLabel: "claude:claude-sonnet-5"});

    expect(servedUnderCodex[1]?.route).toBe("codex_text:gpt-5.6-sol");
    expect(beforeSwitch.at(-1)?.text).toContain("codex_text:gpt-5.6-sol");
    expect(afterSwitch.at(-1)?.text).toBe(beforeSwitch.at(-1)?.text);
    expect(afterSwitch.at(-1)?.text).not.toContain("claude-sonnet-5");
  });

  test("an owned provider identity on the event outranks the ingest route", () => {
    const [stamped] = canonicalEventsFromBridgeEvent(
      {type: "text_complete", content: "owned", provider_id: "claude", model_id: "claude-sonnet-5"},
      "codex_text:gpt-5.6-sol",
    );
    expect(stamped?.route).toBe("claude:claude-sonnet-5");
  });
});
