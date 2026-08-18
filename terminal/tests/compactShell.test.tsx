// F-022: compactShell <=90 regression fence. The compact layout must keep
// rendering after the F-021 one-line tab bar change — this file pins the
// degradation markers (compact header brand, compact status label, one-line
// tab bar, borderless summary strip) and the exact <=90 threshold.
//
// Width mechanism (the non-obvious part): App computes terminalWidth from
// process.stdout.columns ?? Number(COLUMNS) (src/app.tsx) — NOT from the
// stdout handed to ink's render(). Under bun test process.stdout is piped so
// .columns is normally undefined, but we stub it explicitly (defineProperty,
// restored after every test) so the lever holds even under a TTY runner.
import {afterEach, expect, test} from "bun:test";
import {PassThrough} from "node:stream";
import React from "react";
import {render} from "ink";

import {App} from "../src/app";
import {DharmaBridge} from "../src/bridge";

class TestStdout extends PassThrough {
  columns: number;
  rows: number;
  isTTY = true;

  constructor(columns: number, rows: number) {
    super();
    this.columns = columns;
    this.rows = rows;
  }

  cursorTo(): boolean {
    return true;
  }

  moveCursor(): boolean {
    return true;
  }

  clearLine(): boolean {
    return true;
  }

  clearScreenDown(): boolean {
    return true;
  }

  getColorDepth(): number {
    return 8;
  }

  hasColors(): boolean {
    return true;
  }
}

class TestStdin extends PassThrough {
  isTTY = true;
  isRaw = false;

  setRawMode(value: boolean): this {
    this.isRaw = value;
    return this;
  }

  resume(): this {
    return this;
  }

  pause(): this {
    return this;
  }

  ref(): this {
    return this;
  }

  unref(): this {
    return this;
  }
}

function stripAnsi(value: string): string {
  return value.replace(/\u001B\[[0-?]*[ -/]*[@-~]/g, "");
}

const restores: Array<() => void> = [];

function stubOwnProperty(target: object, key: string, value: unknown): void {
  const had = Object.prototype.hasOwnProperty.call(target, key);
  const descriptor = had ? Object.getOwnPropertyDescriptor(target, key) : undefined;
  Object.defineProperty(target, key, {configurable: true, writable: true, value});
  restores.push(() => {
    if (descriptor) {
      Object.defineProperty(target, key, descriptor);
    } else {
      delete (target as Record<string, unknown>)[key];
    }
  });
}

function stubEnv(key: string, value: string): void {
  const previous = process.env[key];
  process.env[key] = value;
  restores.push(() => {
    if (previous === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = previous;
    }
  });
}

afterEach(() => {
  while (restores.length > 0) {
    restores.pop()?.();
  }
});

async function renderShellAt(
  columns: number,
  rows: number,
  settled: (frame: string) => boolean,
  layoutCommand: string | null = "/cockpit",
): Promise<string> {
  stubOwnProperty(process.stdout, "columns", columns);
  stubOwnProperty(process.stdout, "rows", rows);
  // Deterministic offline: the spawn fails instantly, so bridgeStatus reaches
  // "offline" within the poll budget.
  stubEnv("DHARMA_PYTHON", "/nonexistent/python-f022");

  const originalSend = DharmaBridge.prototype.send;
  const originalClose = DharmaBridge.prototype.close;
  DharmaBridge.prototype.send = function mockedSend(): string {
    return "1";
  };
  DharmaBridge.prototype.close = function mockedClose(): void {};
  restores.push(() => {
    DharmaBridge.prototype.send = originalSend;
    DharmaBridge.prototype.close = originalClose;
  });

  const stdout = new TestStdout(columns, rows);
  const stdin = new TestStdin();
  let rendered = "";
  stdout.on("data", (chunk) => {
    rendered += chunk.toString("utf8");
  });

  const instance = render(React.createElement(App), {
    stdout: stdout as unknown as NodeJS.WriteStream,
    stdin: stdin as unknown as NodeJS.ReadStream,
    stderr: new TestStdout(columns, rows) as unknown as NodeJS.WriteStream,
    debug: true,
    patchConsole: false,
    exitOnCtrlC: false,
  });

  try {
    await Bun.sleep(150);
    if (layoutCommand) {
      stdin.write(layoutCommand);
      await Bun.sleep(50);
      stdin.write("\r");
    }
    const deadline = Date.now() + 5000;
    while (Date.now() < deadline && !settled(stripAnsi(rendered))) {
      await Bun.sleep(50);
    }
  } finally {
    instance.unmount();
    instance.cleanup();
  }

  return stripAnsi(rendered);
}

function summaryStripLines(frame: string): string[] {
  // "loop unknown" is boot-deterministic in an empty supervisor state and
  // exists only in cockpit chrome, so it also proves cockpit arrival.
  return frame.split("\n").filter((line) => line.includes("loop unknown"));
}

function cockpitSettled(frame: string): boolean {
  return frame.includes("loop unknown") && frame.includes("offline") && frame.includes("HELM") && frame.includes("?/7");
}

test("80x24 uses compact cockpit chrome", async () => {
  const frame = await renderShellAt(80, 24, cockpitSettled);

  expect(frame).toContain("◆ DHARMA");
  expect(frame).not.toContain("COMMAND POST");
  expect(frame).toContain("○ offline");
  expect(frame).toContain("HELM ◌ UNKNOWN ?/7");
  for (const label of ["F5", "G56", "G46", "FU", "K3", "O50", "O48"]) {
    expect(frame).toContain(`${label} ?`);
  }
  expect(frame).not.toContain("OFFLINE");
  const tabLine = frame.split("\n").find((line) => line.includes("[Chat]"));
  expect(tabLine).toBeDefined();
  expect(tabLine).toContain("Mission");
  expect(frame).not.toContain("|  route ");
  expect(frame).not.toContain("|  panes ");
  const stripLines = summaryStripLines(frame);
  expect(stripLines.length).toBeGreaterThan(0);
  for (const line of stripLines) {
    expect(line.trimStart().startsWith("│")).toBe(false);
  }
});

test("80x24 keeps OnCall truth persistent in zen and scroll faces", async () => {
  const zen = await renderShellAt(
    80,
    24,
    (frame) => frame.includes("HELM ◌ UNKNOWN ?/7") && frame.includes("zen/composer"),
    null,
  );
  expect(zen).toContain("HELM ◌ UNKNOWN ?/7");
  expect(zen).toContain("O48 ?");

  const scroll = await renderShellAt(
    80,
    24,
    (frame) => frame.includes("HELM ◌ UNKNOWN ?/7") && frame.includes("composer · the scroll"),
    "/scroll",
  );
  expect(scroll).toContain("HELM ◌ UNKNOWN ?/7");
  expect(scroll).toContain("O48 ?");
  expect(scroll).toContain("composer · the scroll");
});

test("width 90 remains compact (inclusive boundary)", async () => {
  const frame = await renderShellAt(90, 24, cockpitSettled);

  expect(frame).toContain("◆ DHARMA");
  expect(frame).not.toContain("COMMAND POST");
  const stripLines = summaryStripLines(frame);
  expect(stripLines.length).toBeGreaterThan(0);
  for (const line of stripLines) {
    expect(line.trimStart().startsWith("│")).toBe(false);
  }
});

test("width 91 restores wide cockpit chrome", async () => {
  const frame = await renderShellAt(
    91,
    24,
    (current) => cockpitSettled(current) && current.includes("COMMAND POST"),
  );

  expect(frame).toContain("◆ DHARMA");
  expect(frame).toContain("COMMAND POST");
  const stripLines = summaryStripLines(frame);
  expect(stripLines.length).toBeGreaterThan(0);
  for (const line of stripLines) {
    expect(line.trimStart().startsWith("│")).toBe(false);
  }
});

test("wide cockpit sanity check reaches App", async () => {
  const frame = await renderShellAt(
    220,
    60,
    (current) => cockpitSettled(current) && current.includes("COMMAND POST"),
  );

  expect(frame).toContain("COMMAND POST");
  expect(frame).toContain("○ offline");
  expect(frame).not.toContain("OFFLINE");
  expect(frame).not.toContain("DHARMA TERMINAL");
  const stripLines = summaryStripLines(frame);
  expect(stripLines.length).toBeGreaterThan(0);
  for (const line of stripLines) {
    expect(line.trimStart().startsWith("│")).toBe(false);
  }
});
