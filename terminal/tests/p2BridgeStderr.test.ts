import {afterEach, describe, expect, test} from "bun:test";
import {EventEmitter} from "node:events";
import {existsSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync} from "node:fs";
import os from "node:os";
import path from "node:path";
import {PassThrough} from "node:stream";
import type {ChildProcess} from "node:child_process";

import {DharmaBridge, bridgeStderrLogPath} from "../src/bridge";

class FakeBridgeProcess extends EventEmitter {
  readonly stdin = new PassThrough();
  readonly stdout = new PassThrough();
  readonly stderr = new PassThrough();
  killed = false;

  kill(signal: NodeJS.Signals | number = "SIGTERM"): boolean {
    if (this.killed) return false;
    this.killed = true;
    this.emit("exit", null, signal);
    return true;
  }

  asChildProcess(): ChildProcess {
    return this as unknown as ChildProcess;
  }
}

const tempDirs: string[] = [];
const savedSupervisorStateDir = process.env.DHARMA_TERMINAL_SUPERVISOR_STATE_DIR;
const savedTerminalStateDir = process.env.DHARMA_TERMINAL_STATE_DIR;

afterEach(() => {
  if (savedSupervisorStateDir === undefined) delete process.env.DHARMA_TERMINAL_SUPERVISOR_STATE_DIR;
  else process.env.DHARMA_TERMINAL_SUPERVISOR_STATE_DIR = savedSupervisorStateDir;
  if (savedTerminalStateDir === undefined) delete process.env.DHARMA_TERMINAL_STATE_DIR;
  else process.env.DHARMA_TERMINAL_STATE_DIR = savedTerminalStateDir;
  while (tempDirs.length > 0) rmSync(tempDirs.pop() ?? "", {recursive: true, force: true});
});

async function flushStreams(): Promise<void> {
  await new Promise<void>((resolve) => setImmediate(resolve));
}

async function waitForLog(pathname: string, expectedLength: number): Promise<void> {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if (existsSync(pathname) && statSync(pathname).size >= expectedLength) {
      return;
    }
    await Bun.sleep(5);
  }
}

describe("P2 F8 bridge stderr isolation", () => {
  test("factory-provided bridge stderr is appended to the supervisor state log and never becomes a UI event", async () => {
    const stateDir = mkdtempSync(path.join(os.tmpdir(), "dharma-p2-f8-"));
    tempDirs.push(stateDir);
    process.env.DHARMA_TERMINAL_SUPERVISOR_STATE_DIR = stateDir;
    delete process.env.DHARMA_TERMINAL_STATE_DIR;

    const child = new FakeBridgeProcess();
    const events: Record<string, unknown>[] = [];
    const stderrLog = path.join(stateDir, "bridge.stderr.log");
    writeFileSync(stderrLog, "", {mode: 0o644});
    const bridge = new DharmaBridge((event) => events.push(event), () => child.asChildProcess());

    try {
      child.stderr.write("keys_status.json is stale; falling back to env-presence\n");
      child.stderr.write("non-json diagnostic stays out of the alternate screen\n");
      child.stdout.write(`${JSON.stringify({type: "status.result", request_id: "owned-1", status: "ok"})}\n`);
      await flushStreams();

      const expected =
        "keys_status.json is stale; falling back to env-presence\n" +
        "non-json diagnostic stays out of the alternate screen\n";
      await waitForLog(stderrLog, Buffer.byteLength(expected));

      expect(existsSync(stderrLog)).toBe(true);
      expect(readFileSync(stderrLog, "utf8")).toBe(expected);
      expect(statSync(stderrLog).mode & 0o777).toBe(0o600);
      expect(events).toEqual([{type: "status.result", request_id: "owned-1", status: "ok"}]);
      expect(JSON.stringify(events)).not.toContain("keys_status.json is stale");
      expect(JSON.stringify(events)).not.toContain("non-json diagnostic");
    } finally {
      bridge.close();
    }
  });
});

describe("P2 F8 bridge stderr never vanishes", () => {
  test("without a state dir the log still lands under ~/.dharma", () => {
    const resolved = bridgeStderrLogPath({});
    expect(resolved).toBe(path.join(os.homedir(), ".dharma", "terminal_supervisor", "bridge.stderr.log"));
  });

  test("a non-zero exit carries the last stderr lines on the bridge.error event", async () => {
    const stateDir = mkdtempSync(path.join(os.tmpdir(), "dharma-p2-f8-exit-"));
    tempDirs.push(stateDir);
    process.env.DHARMA_TERMINAL_SUPERVISOR_STATE_DIR = stateDir;
    delete process.env.DHARMA_TERMINAL_STATE_DIR;

    const child = new FakeBridgeProcess();
    const events: Record<string, unknown>[] = [];
    const bridge = new DharmaBridge((event) => events.push(event), () => child.asChildProcess());
    try {
      child.stderr.write("Traceback (most recent call last):\n");
      child.stderr.write("ModuleNotFoundError: No module named 'dharma_swarm.missing'\n");
      await flushStreams();
      child.emit("exit", 1, null);

      const exit = events.find((event) => event.code === "bridge_exit");
      expect(exit).toBeDefined();
      expect(String(exit?.message)).toContain("bridge exited (1)");
      expect(String(exit?.message)).toContain("ModuleNotFoundError: No module named 'dharma_swarm.missing'");
      expect(String(exit?.stderr_tail)).toContain("Traceback");
    } finally {
      bridge.close();
    }
  });
});
