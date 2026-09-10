import {describe, expect, test} from "bun:test";

import {
  focusModeFor,
  footerHintFor,
  paneActionChordDecision,
  paneActionsFor,
  plainListDirection,
} from "../src/shellControls";
import {initialState} from "../src/state";
import type {AppState} from "../src/types";

const options = {sessionCatalogLimit: 50};

function actionsFor(tabId: string, state: AppState) {
  return paneActionsFor(tabId, state, options);
}

function ownerBackedState(authoritative: boolean): AppState {
  return {
    ...initialState,
    bridgeStatus: "connected",
    uiMode: {...initialState.uiMode, keyboardFocus: "navigation"},
    authoritativeSurfaces: {
      ...initialState.authoritativeSurfaces,
      sessions: authoritative,
      approvals: authoritative,
    },
    sessionPane: {
      ...initialState.sessionPane,
      selectedSessionId: "session-a",
    },
    approvalPane: {
      selectedActionId: "approval-a",
      historyBacked: authoritative,
      order: ["approval-a"],
      entriesByActionId: {
        "approval-a": {
          decision: {
            version: "v1",
            domain: "permission_decision",
            action_id: "approval-a",
            tool_name: "shell",
            risk: "medium",
            decision: "require_approval",
            rationale: "operator decision required",
            policy_source: "fixture",
            requires_confirmation: true,
            metadata: {},
          },
          status: "pending",
          firstSeenAt: "2026-08-27T00:00:00Z",
          lastSeenAt: "2026-08-27T00:00:00Z",
          lastSourceEventType: "permission.decision",
          seenCount: 1,
          pending: true,
        },
      },
    },
  };
}

describe("owner-backed shell controls", () => {
  test("keeps stale and fresh approval history refresh-only", () => {
    for (const authoritative of [false, true]) {
      const actions = actionsFor("approvals", ownerBackedState(authoritative));

      expect(actions).toEqual({
        refresh: {
          label: "refresh approvals",
          summary: "refresh approval history",
          requestType: "permission.history",
          payload: {limit: 50},
        },
      });
      expect(actions.primary).toBeUndefined();
      expect(actions.secondary).toBeUndefined();
      expect(actions.tertiary).toBeUndefined();
    }
  });

  test("labels the approval pane as read-only without effect chords", () => {
    for (const authoritative of [false, true]) {
      const state = ownerBackedState(authoritative);
      for (const compact of [false, true]) {
        const hint = footerHintFor("approvals", state, options, compact);

        expect(hint).toContain("read-only history");
        expect(hint).not.toMatch(/\b(?:approve|deny|dismiss|mark resolved)\b/);
        expect(hint).not.toMatch(/\^(?:X|F|V)\b/);
      }
    }
  });

  test("routes approval chords through the production decision seam without effect requests", () => {
    for (const authoritative of [false, true]) {
      const state = ownerBackedState(authoritative);
      const sent: Array<{requestType?: string; payload: Record<string, unknown>}> = [];

      for (const chord of ["x", "f", "v"]) {
        const decision = paneActionChordDecision(chord, {ctrl: true}, "approvals", state, options);
        expect(decision.handled).toBe(true);
        if (decision.handled && decision.action) {
          sent.push({requestType: decision.action.requestType, payload: decision.action.payload});
        }
      }
      expect(sent).toEqual([]);

      const refresh = paneActionChordDecision("l", {ctrl: true}, "approvals", state, options);
      expect(refresh).toEqual({
        handled: true,
        action: {
          label: "refresh approvals",
          summary: "refresh approval history",
          requestType: "permission.history",
          payload: {limit: 50},
        },
      });
      if (refresh.handled && refresh.action) {
        sent.push({requestType: refresh.action.requestType, payload: refresh.action.payload});
      }
      expect(sent).toEqual([{requestType: "permission.history", payload: {limit: 50}}]);
    }
  });

  test("keeps approval list movement plain-key-only so Ctrl-J and Ctrl-K recover globally", () => {
    expect(plainListDirection("j", {})).toBe(1);
    expect(plainListDirection("k", {})).toBe(-1);
    expect(plainListDirection("j", {ctrl: true})).toBeUndefined();
    expect(plainListDirection("k", {ctrl: true})).toBeUndefined();
    expect(plainListDirection("j", {meta: true})).toBeUndefined();
    expect(plainListDirection("k", {meta: true})).toBeUndefined();
  });

  test("uses the production status mode to expose the read-only approval boundary", () => {
    const state = ownerBackedState(true);
    const approvalsTab = state.tabs.find((tab) => tab.kind === "approvals");

    expect(focusModeFor(approvalsTab, state)).toBe("approval history · read-only");
  });

  test("preserves fresh owner-backed session detail", () => {
    const retained = ownerBackedState(false);
    const observed = ownerBackedState(true);

    expect(actionsFor("sessions", retained).primary).toBeUndefined();
    expect(actionsFor("sessions", observed).primary).toMatchObject({
      requestType: "session.detail",
      payload: {session_id: "session-a", transcript_limit: 40},
    });
  });
});
