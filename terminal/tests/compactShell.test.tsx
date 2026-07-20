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

const restores: Array<() => void> = [];

function stripAnsi(value: string): string {
  return value.replace(/\u001B\[[0-?]*[ -/]*[@-~]/g, "");
}

function stubOwnProperty(target: object, key: string, value: unknown): void {
  const descriptor = Object.getOwnPropertyDescriptor(target, key);
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

async function renderShellAt(columns: number, rows: number): Promise<string> {
  stubOwnProperty(process.stdout, "columns", columns);
  stubOwnProperty(process.stdout, "rows", rows);
  stubEnv("DHARMA_PYTHON", "/nonexistent/dharma-terminal-compact-shell-python");

  const originalSend = DharmaBridge.prototype.send;
  const originalClose = DharmaBridge.prototype.close;
  DharmaBridge.prototype.send = function mockedSend(): string {
    return "compact-shell-test";
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
    const deadline = Date.now() + 3000;
    const tabMarker = columns <= 90 ? "[Chat]" : "◆ Chat";
    while (Date.now() < deadline) {
      const frame = stripAnsi(rendered);
      if (frame.includes("DHARMA") && frame.includes(tabMarker) && frame.includes("keys")) {
        return frame;
      }
      await Bun.sleep(50);
    }
    return stripAnsi(rendered);
  } finally {
    instance.unmount();
    instance.cleanup();
  }
}

test("80x24 uses the compact shell without wide-only chrome", async () => {
  const frame = await renderShellAt(80, 24);

  expect(frame).toContain("DHARMA");
  expect(frame).not.toContain("DHARMA TERMINAL");

  const tabLine = frame.split("\n").find((line) => line.includes("[Chat]"));
  expect(tabLine).toBeDefined();
  expect(tabLine).toContain("Mission");
  expect(tabLine).toContain("Repo");

  expect(frame).toContain("keys");
  expect(frame).toContain("Tab tabs");
  expect(frame).not.toContain("mode  tab navigation");
});

test("width 90 remains compact and width 91 restores the wide header", async () => {
  const compact = await renderShellAt(90, 24);
  const wide = await renderShellAt(91, 24);

  expect(compact).toContain("DHARMA");
  expect(compact).not.toContain("TERMINAL");
  expect(compact).not.toContain("mode  tab navigation");

  expect(wide).toContain("DHARMA");
  expect(wide).toContain("◆ Chat");
  expect(wide).toContain("TERMINAL");
  expect(wide).toContain("mode  tab navigation");
});
