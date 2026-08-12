import {describe, expect, test} from "bun:test";
import {EventEmitter} from "node:events";
import {PassThrough} from "node:stream";
import type {ChildProcess} from "node:child_process";

import {DharmaBridge, resolvePython} from "../src/bridge";

class FakeBridgeProcess extends EventEmitter {
  readonly stdin = new PassThrough();
  readonly stdout = new PassThrough();
  killed = false;

  kill(signal: NodeJS.Signals | number = "SIGTERM"): boolean {
    if (this.killed) {
      return false;
    }
    this.killed = true;
    this.emit("exit", null, signal);
    return true;
  }

  asChildProcess(): ChildProcess {
    return this as unknown as ChildProcess;
  }
}

function captureRequests(child: FakeBridgeProcess): Record<string, unknown>[] {
  const requests: Record<string, unknown>[] = [];
  child.stdin.on("data", (chunk) => {
    for (const line of String(chunk).split("\n")) {
      if (line.trim()) {
        requests.push(JSON.parse(line) as Record<string, unknown>);
      }
    }
  });
  return requests;
}

async function flushBridgeEvents(): Promise<void> {
  await new Promise<void>((resolve) => setImmediate(resolve));
}

describe("resolvePython", () => {
  test("honors an explicit DHARMA_PYTHON even when it is an offline test gate", () => {
    expect(resolvePython({DHARMA_PYTHON: "/nonexistent/python"}, "/repo", () => false)).toBe(
      "/nonexistent/python",
    );
  });

  test("prefers the worktree-local virtualenv", () => {
    const existing = new Set(["/repo/.venv/bin/python", "/venv/bin/python"]);
    expect(resolvePython({VIRTUAL_ENV: "/venv"}, "/repo", (candidate) => existing.has(candidate))).toBe(
      "/repo/.venv/bin/python",
    );
  });

  test("uses the canonical sibling checkout virtualenv for lightweight worktrees", () => {
    const canonical = "/workspace/dharma_swarm/.venv/bin/python";
    expect(resolvePython({}, "/workspace/dharma_helm_build", (candidate) => candidate === canonical)).toBe(canonical);
  });

  test("falls back to python3 when no managed interpreter exists", () => {
    expect(resolvePython({}, "/repo", () => false)).toBe("python3");
  });
});

describe("DharmaBridge transport scheduling", () => {
  test("writes foreground work before the next queued background request", async () => {
    const child = new FakeBridgeProcess();
    const requests = captureRequests(child);
    const bridge = new DharmaBridge(() => {}, () => child.asChildProcess());

    const activeId = bridge.sendBackground("workspace.snapshot");
    bridge.sendBackground("runtime.snapshot");
    bridge.send("session.bootstrap", {prompt: "operator prompt"});

    expect(requests.map((request) => request.type)).toEqual([
      "workspace.snapshot",
      "session.bootstrap",
    ]);

    child.stdout.write(`${JSON.stringify({type: "workspace.snapshot.result", request_id: activeId})}\n`);
    await flushBridgeEvents();

    expect(requests.map((request) => request.type)).toEqual([
      "workspace.snapshot",
      "session.bootstrap",
      "runtime.snapshot",
    ]);
    bridge.close();
  });

  test("only a matching terminal event advances background work", async () => {
    const child = new FakeBridgeProcess();
    const requests = captureRequests(child);
    const bridge = new DharmaBridge(() => {}, () => child.asChildProcess());

    const activeId = bridge.sendBackground("workspace.snapshot");
    bridge.sendBackground("runtime.snapshot");
    child.stdout.write(`${JSON.stringify({type: "text_delta", request_id: activeId, content: "still running"})}\n`);
    child.stdout.write(`${JSON.stringify({type: "workspace.snapshot.result", request_id: "unrelated"})}\n`);
    await flushBridgeEvents();
    expect(requests.map((request) => request.type)).toEqual(["workspace.snapshot"]);

    child.stdout.write(`${JSON.stringify({type: "workspace.snapshot.result", request_id: activeId})}\n`);
    await flushBridgeEvents();
    expect(requests.map((request) => request.type)).toEqual(["workspace.snapshot", "runtime.snapshot"]);
    bridge.close();
  });

  test("a correlated Helm projection completes its non-result background request", async () => {
    const child = new FakeBridgeProcess();
    const requests = captureRequests(child);
    const bridge = new DharmaBridge(() => {}, () => child.asChildProcess());

    const activeId = bridge.sendBackground("helm.on_call.request");
    bridge.sendBackground("runtime.snapshot");
    child.stdout.write(`${JSON.stringify({type: "helm.on_call_projection", request_id: activeId, projection: {}})}\n`);
    await flushBridgeEvents();

    expect(requests.map((request) => request.type)).toEqual(["helm.on_call.request", "runtime.snapshot"]);
    bridge.close();
  });

  test("transport failure drops stale background work and restarts cleanly", async () => {
    const children: FakeBridgeProcess[] = [];
    const requestLogs: Record<string, unknown>[][] = [];
    const factory = (): ChildProcess => {
      const child = new FakeBridgeProcess();
      children.push(child);
      requestLogs.push(captureRequests(child));
      return child.asChildProcess();
    };
    const events: Record<string, unknown>[] = [];
    const bridge = new DharmaBridge((event) => events.push(event), factory);

    bridge.sendBackground("workspace.snapshot");
    bridge.sendBackground("runtime.snapshot");
    children[0]?.stdin.emit("error", new Error("broken pipe"));
    await flushBridgeEvents();

    expect(events.at(-1)).toMatchObject({type: "bridge.error", code: "bridge_stdin_error"});
    bridge.sendBackground("status");
    expect(children).toHaveLength(2);
    expect(requestLogs[1]?.map((request) => request.type)).toEqual(["status"]);
    bridge.close();
  });

  test("a retired child cannot project stale truth or release the successor scheduler", async () => {
    const children: FakeBridgeProcess[] = [];
    const requestLogs: Record<string, unknown>[][] = [];
    const events: Record<string, unknown>[] = [];
    const bridge = new DharmaBridge((event) => events.push(event), () => {
      const child = new FakeBridgeProcess();
      children.push(child);
      requestLogs.push(captureRequests(child));
      return child.asChildProcess();
    });

    bridge.sendBackground("helm.on_call.request");
    children[0]?.stdin.emit("error", new Error("broken pipe"));
    await flushBridgeEvents();

    const successorId = bridge.sendBackground("status");
    bridge.sendBackground("runtime.snapshot");
    children[0]?.stdout.write(`${JSON.stringify({
      type: "helm.on_call_projection",
      request_id: successorId,
      projection: {runtime_epoch: "retired-child"},
    })}\n`);
    await flushBridgeEvents();

    expect(events.filter((event) => event.type === "helm.on_call_projection")).toEqual([]);
    expect(requestLogs[1]?.map((request) => request.type)).toEqual(["status"]);

    children[1]?.stdout.write(`${JSON.stringify({type: "status.result", request_id: successorId})}\n`);
    await flushBridgeEvents();
    expect(requestLogs[1]?.map((request) => request.type)).toEqual(["status", "runtime.snapshot"]);
    bridge.close();
  });

  test("malformed protocol output restarts instead of pinning the active request", async () => {
    const children: FakeBridgeProcess[] = [];
    const requestLogs: Record<string, unknown>[][] = [];
    const factory = (): ChildProcess => {
      const child = new FakeBridgeProcess();
      children.push(child);
      requestLogs.push(captureRequests(child));
      return child.asChildProcess();
    };
    const bridge = new DharmaBridge((event) => {
      if (event.code === "invalid_bridge_json") {
        bridge.send("handshake");
      }
    }, factory);

    bridge.sendBackground("workspace.snapshot");
    bridge.sendBackground("runtime.snapshot");
    children[0]?.stdout.write("not-json\n");
    await flushBridgeEvents();

    expect(children).toHaveLength(2);
    expect(requestLogs[1]?.map((request) => request.type)).toEqual(["handshake"]);
    bridge.close();
  });

  test("reserved request fields cannot be replaced by payload data", () => {
    const child = new FakeBridgeProcess();
    const requests = captureRequests(child);
    const bridge = new DharmaBridge(() => {}, () => child.asChildProcess());

    const id = bridge.send("status", {id: "forged", type: "forged"});
    expect(requests).toEqual([{id, type: "status"}]);
    bridge.close();
  });

  test("intentional close is idempotent and never respawns", async () => {
    const children: FakeBridgeProcess[] = [];
    const events: Record<string, unknown>[] = [];
    const bridge = new DharmaBridge(
      (event) => events.push(event),
      () => {
        const child = new FakeBridgeProcess();
        children.push(child);
        return child.asChildProcess();
      },
    );

    bridge.close();
    bridge.close();
    await flushBridgeEvents();

    expect(children).toHaveLength(1);
    expect(events).toEqual([]);
    expect(() => bridge.send("handshake")).toThrow("bridge is closed");
    expect(children).toHaveLength(1);
  });
});
