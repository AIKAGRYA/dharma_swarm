import {describe, expect, test} from "bun:test";

import {decodeHelmOnCallProjection} from "../src/protocol/onCallTruth";
import {initialState, reduceApp} from "../src/state";
import {buildOnCallProjection} from "./fixtures/onCallProjection";

function decodedProjection(runtimeEpoch: string, state: "ON_CALL" | "LIVE_DEGRADED" = "ON_CALL") {
  const payload = state === "ON_CALL"
    ? buildOnCallProjection({runtimeEpoch})
    : buildOnCallProjection({
        runtimeEpoch,
        state,
        verdicts: ["ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "REJECTED"],
      });
  const decoded = decodeHelmOnCallProjection(payload);
  if (!decoded) {
    throw new Error("test fixture must decode");
  }
  return decoded;
}

describe("OnCall UI state", () => {
  test("starts nonpersistently at UNKNOWN with no runtime epoch", () => {
    expect(initialState.onCallTruth).toEqual({kind: "unknown", runtimeEpoch: null});
  });

  test("accepts only projections in the bound runtime epoch", () => {
    const epochA = decodedProjection("terminal-bridge:epoch-a");
    const authoritative = reduceApp(initialState, {type: "onCall.projection.set", projection: epochA});
    expect(authoritative.onCallTruth.kind).toBe("authoritative");
    expect(authoritative.onCallTruth.runtimeEpoch).toBe("terminal-bridge:epoch-a");

    const degradedA = decodedProjection("terminal-bridge:epoch-a", "LIVE_DEGRADED");
    const refreshed = reduceApp(authoritative, {type: "onCall.projection.set", projection: degradedA});
    expect(refreshed.onCallTruth.kind).toBe("authoritative");
    if (refreshed.onCallTruth.kind === "authoritative") {
      expect(refreshed.onCallTruth.projection.state).toBe("LIVE_DEGRADED");
    }

    const epochB = decodedProjection("terminal-bridge:epoch-b");
    const epochChanged = reduceApp(refreshed, {type: "onCall.projection.set", projection: epochB});
    expect(epochChanged.onCallTruth).toEqual({kind: "unknown", runtimeEpoch: "terminal-bridge:epoch-b"});

    const currentEpoch = reduceApp(epochChanged, {type: "onCall.projection.set", projection: epochB});
    expect(currentEpoch.onCallTruth.kind).toBe("authoritative");
    expect(currentEpoch.onCallTruth.runtimeEpoch).toBe("terminal-bridge:epoch-b");
  });

  test("reset preserves an expected epoch unless reconnect explicitly clears it", () => {
    const projection = decodedProjection("terminal-bridge:epoch-a");
    const authoritative = reduceApp(initialState, {type: "onCall.projection.set", projection});

    const malformedReset = reduceApp(authoritative, {type: "onCall.truth.reset"});
    expect(malformedReset.onCallTruth).toEqual({kind: "unknown", runtimeEpoch: "terminal-bridge:epoch-a"});

    const reconnectReset = reduceApp(authoritative, {type: "onCall.truth.reset", runtimeEpoch: null});
    expect(reconnectReset.onCallTruth).toEqual({kind: "unknown", runtimeEpoch: null});
  });
});
