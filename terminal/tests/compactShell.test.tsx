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
): Promise<string> {
  stubOwnProperty(process.stdout, "columns", columns);
  stubOwnProperty(process.stdout, "rows", rows);
  // Deterministic offline: the spawn fails instantly, so bridgeStatus reaches
  // "offline" (compact label OFF / wide label OFFLINE) within the poll budget.
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
  // "loop unknown" is the boot-deterministic summary item (sandboxed empty
  // supervisor state); inside the bordered band the item can wrap onto its own
  // row, so the anchor must be a single item, not the loop+verify pair.
  return frame.split("\n").filter((line) => line.includes("loop unknown"));
}

test("80x24 boots the compact shell: compact brand, OFF label, one-line tab bar, borderless summary strip", async () => {
  const frame = await renderShellAt(80, 24, (current) => /\bOFF\b/.test(current));

  expect(frame).toContain("DHARMA");
  expect(frame).not.toContain("DHARMA TERMINAL");
  // Compact status label is OFF, never the wide OFFLINE (\bOFF\b cannot match
  // inside OFFLINE: F-L has no word boundary).
  expect(/\bOFF\b/.test(frame)).toBe(true);
  expect(frame).not.toContain("OFFLINE");
  // One-line tab bar law: the bracketed active tab shares its row with the
  // next tab titles instead of a bordered pill per tab.
  const tabLine = frame.split("\n").find((line) => line.includes("[Chat]"));
  expect(tabLine).toBeDefined();
  expect(tabLine).toContain("Mission");
  // Wide-only header segments never render in the compact shell.
  expect(frame).not.toContain("|  route ");
  expect(frame).not.toContain("|  panes ");
  // Operator summary rides the borderless one-row strip (no │ gutter).
  const stripLines = summaryStripLines(frame);
  expect(stripLines.length).toBeGreaterThan(0);
  for (const line of stripLines) {
    expect(line.trimStart().startsWith("│")).toBe(false);
  }
});

test("width 90 still degrades to the compact shell (threshold inclusive)", async () => {
  const frame = await renderShellAt(90, 24, (current) => /\bOFF\b/.test(current));

  expect(frame).toContain("DHARMA");
  expect(frame).not.toContain("DHARMA TERMINAL");
  const stripLines = summaryStripLines(frame);
  expect(stripLines.length).toBeGreaterThan(0);
  for (const line of stripLines) {
    expect(line.trimStart().startsWith("│")).toBe(false);
  }
});

test("width 91 leaves the compact shell: summary band regains its border", async () => {
  // The header keeps compact copy below 118 cols (F-021), so the band border
  // is the discriminator that pins compactShell's <=90 edge from above.
  const frame = await renderShellAt(91, 24, (current) => summaryStripLines(current).length > 0);

  const stripLines = summaryStripLines(frame);
  expect(stripLines.length).toBeGreaterThan(0);
  for (const line of stripLines) {
    expect(line.trimStart().startsWith("│")).toBe(true);
  }
});

test("wide boot renders the full shell (lever sanity: the stub reaches App)", async () => {
  const frame = await renderShellAt(220, 60, (current) => current.includes("OFFLINE"));

  expect(frame).toContain("DHARMA TERMINAL");
  expect(frame).toContain("OFFLINE");
  const stripLines = summaryStripLines(frame);
  expect(stripLines.length).toBeGreaterThan(0);
  for (const line of stripLines) {
    expect(line.trimStart().startsWith("│")).toBe(true);
  }
});
