import {describe, expect, test} from "bun:test";

import {BridgeBackgroundScheduler, type BridgeRequest} from "../src/bridgeScheduler";

function request(id: string, type: string, value?: string): BridgeRequest {
  return {id, type, value};
}

describe("BridgeBackgroundScheduler", () => {
  test("admits one background request at a time", () => {
    const scheduler = new BridgeBackgroundScheduler();
    expect(scheduler.enqueue(request("1", "workspace.snapshot"))?.id).toBe("1");
    expect(scheduler.enqueue(request("2", "runtime.snapshot"))).toBeNull();
    expect(scheduler.snapshot()).toEqual({
      activeId: "1",
      queuedTypes: ["runtime.snapshot"],
    });
    expect(scheduler.complete("1")?.id).toBe("2");
  });

  test("coalesces queued refreshes by request type and keeps the newest payload", () => {
    const scheduler = new BridgeBackgroundScheduler();
    scheduler.enqueue(request("1", "workspace.snapshot"));
    scheduler.enqueue(request("2", "model.policy", "old"));
    scheduler.enqueue(request("3", "model.policy", "new"));

    expect(scheduler.complete("1")).toEqual(request("3", "model.policy", "new"));
    expect(scheduler.complete("3")).toBeNull();
  });

  test("ignores unrelated foreground completions", () => {
    const scheduler = new BridgeBackgroundScheduler();
    scheduler.enqueue(request("1", "runtime.snapshot"));
    scheduler.enqueue(request("2", "workspace.snapshot"));

    expect(scheduler.complete("foreground-9")).toBeNull();
    expect(scheduler.snapshot().activeId).toBe("1");
  });

  test("reset drops stale work after a bridge restart", () => {
    const scheduler = new BridgeBackgroundScheduler();
    scheduler.enqueue(request("1", "runtime.snapshot"));
    scheduler.enqueue(request("2", "workspace.snapshot"));
    scheduler.reset();

    expect(scheduler.snapshot()).toEqual({activeId: null, queuedTypes: []});
    expect(scheduler.enqueue(request("3", "status"))?.id).toBe("3");
  });
});
