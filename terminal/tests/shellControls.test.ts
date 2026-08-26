import {describe, expect, test} from "bun:test";

import {footerHintFor, paneActionsFor} from "../src/shellControls";
import {initialState} from "../src/state";
import type {AppState} from "../src/types";

function actionsFor(tabId: string, state: AppState) {
  return paneActionsFor(tabId, state, {
    sessionCatalogLimit: 50,
    approvalResolveAction(entry, resolution, label) {
      return {
        label,
        summary: `${label} ${entry.decision.action_id}`,
        payload: {
          action_type: "approval.resolve",
          action_id: entry.decision.action_id,
          resolution,
        },
      };
    },
  });
}

const options = {
  sessionCatalogLimit: 50,
  approvalResolveAction(entry: AppState["approvalPane"]["entriesByActionId"][string], resolution: "approved" | "denied" | "dismissed" | "resolved", label: string) {
    return {
      label,
      summary: `${label} ${entry.decision.action_id}`,
      payload: {action_type: "approval.resolve", action_id: entry.decision.action_id, resolution},
    };
  },
};

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
  test("holds session detail and every approval resolution until current owner authority exists", () => {
    const retained = ownerBackedState(false);

    expect(actionsFor("sessions", retained).primary).toBeUndefined();
    expect(actionsFor("approvals", retained)).toMatchObject({
      primary: undefined,
      secondary: undefined,
      tertiary: undefined,
    });
    expect(footerHintFor("sessions", retained, options)).toContain("detail/resume held");
    expect(footerHintFor("approvals", retained, options)).toContain("resolution held");
  });

  test("exposes owner actions after the corresponding fresh projection is authoritative", () => {
    const observed = ownerBackedState(true);

    expect(actionsFor("sessions", observed).primary?.requestType).toBe("session.detail");
    expect(actionsFor("approvals", observed).primary?.payload.action_type).toBe("approval.resolve");
    expect(actionsFor("approvals", observed).secondary?.payload.resolution).toBe("denied");
    expect(actionsFor("approvals", observed).tertiary?.payload.resolution).toBe("dismissed");
  });
});
