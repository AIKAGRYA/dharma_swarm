import {afterEach, describe, expect, test} from "bun:test";
import {PassThrough} from "node:stream";
import React from "react";
import {render} from "ink";

import {App} from "../src/app";
import {DharmaBridge} from "../src/bridge";
import {Composer} from "../src/components/Composer";

class TestStdout extends PassThrough {
  columns = 140;
  rows = 40;
  isTTY = true;

  cursorTo(): boolean { return true; }
  moveCursor(): boolean { return true; }
  clearLine(): boolean { return true; }
  clearScreenDown(): boolean { return true; }
  getColorDepth(): number { return 8; }
  hasColors(): boolean { return true; }
}

class TestStdin extends PassThrough {
  isTTY = true;
  isRaw = false;

  setRawMode(value: boolean): this {
    this.isRaw = value;
    return this;
  }

  resume(): this { return this; }
  pause(): this { return this; }
  ref(): this { return this; }
  unref(): this { return this; }
}

function plain(value: string): string {
  return value
    .replace(/\u001B\[[0-?]*[ -/]*[@-~]/g, "")
    .replace(/[┌┐└┘├┤┬┴┼│─]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function elementText(node: React.ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(elementText).join(" ");
  if (React.isValidElement<{children?: React.ReactNode}>(node)) return elementText(node.props.children);
  return "";
}

const restores: Array<() => void> = [];

afterEach(() => {
  while (restores.length > 0) {
    restores.pop()?.();
  }
});

describe("P2 F2 composer draft affordances", () => {
  test("a multiline draft names its send-all behavior while a one-line draft stays quiet", () => {
    const multilineFrame = plain(elementText(Composer({prompt: "first line\nsecond line", focused: true, width: 140})));
    expect(multilineFrame).toMatch(/multi-line draft/i);
    expect(multilineFrame).toMatch(/Enter sends all lines/i);

    const singleLineFrame = plain(elementText(Composer({prompt: "one line", focused: true, width: 140})));
    expect(singleLineFrame).not.toMatch(/multi-line draft/i);
    expect(singleLineFrame).not.toMatch(/Enter sends all lines/i);
  });

  test("a retained multiline draft keeps its routing truth while navigation owns focus", () => {
    const frame = plain(elementText(Composer({
      prompt: "first retained line\nsecond retained line",
      focused: false,
      compact: true,
      width: 44,
    })));

    expect(frame).toMatch(/multi-line draft/i);
    expect(frame).toMatch(/Enter sends all lines/i);
    expect(frame).toMatch(/multi-line → chat/i);
    expect(frame).toMatch(/Esc → compose/i);
  });

  test("Ctrl-U clears the entire multiline draft without submitting any of it", async () => {
    const previousPython = process.env.DHARMA_PYTHON;
    process.env.DHARMA_PYTHON = "/nonexistent/dharma-p2-f2-python";
    restores.push(() => {
      if (previousPython === undefined) delete process.env.DHARMA_PYTHON;
      else process.env.DHARMA_PYTHON = previousPython;
    });

    const sent: Array<{type: string; payload: Record<string, unknown>}> = [];
    const originalSend = DharmaBridge.prototype.send;
    const originalSendBackground = DharmaBridge.prototype.sendBackground;
    DharmaBridge.prototype.send = function mockedSend(type: string, payload: Record<string, unknown> = {}): string {
      sent.push({type, payload});
      return String(sent.length);
    };
    DharmaBridge.prototype.sendBackground = function mockedSendBackground(): string {
      return "background";
    };
    restores.push(() => {
      DharmaBridge.prototype.send = originalSend;
      DharmaBridge.prototype.sendBackground = originalSendBackground;
    });

    const stdin = new TestStdin();
    const stdout = new TestStdout();
    let rendered = "";
    stdout.on("data", (chunk) => { rendered += chunk.toString("utf8"); });
    const instance = render(<App />, {
      stdout: stdout as unknown as NodeJS.WriteStream,
      stderr: new TestStdout() as unknown as NodeJS.WriteStream,
      stdin: stdin as unknown as NodeJS.ReadStream,
      debug: true,
      patchConsole: false,
      exitOnCtrlC: false,
    });

    try {
      await Bun.sleep(75);
      stdin.write("keep neither\nnor this");
      await Bun.sleep(75);
      expect(plain(rendered)).toContain("keep neither");

      rendered = "";
      stdin.write("\u0015");
      await Bun.sleep(75);

      const cleared = plain(rendered);
      expect(cleared).not.toContain("keep neither");
      expect(cleared).not.toContain("nor this");
      expect(cleared).toMatch(/Type a message/i);
      expect(sent.some((request) => request.type === "session.bootstrap")).toBe(false);
    } finally {
      instance.unmount();
      instance.cleanup();
    }
  });
});
