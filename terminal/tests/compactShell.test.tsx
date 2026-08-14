// Nihonga Helm responsive regression fence. The cockpit is one semantic view
// projected through compact, standard, and panorama profiles; resize may alter
// composition but never route/OnCall truth or the conversation draft.
//
// Width mechanism (the non-obvious part): App computes terminalWidth from
// process.stdout.columns ?? Number(COLUMNS) (src/app.tsx) — NOT from the
// stdout handed to ink's render(). Under bun test process.stdout is piped so
// .columns is normally undefined, but we stub it explicitly (defineProperty,
// restored after every test) so the lever holds even under a TTY runner.
import {afterEach, expect, test} from "bun:test";
import {PassThrough} from "node:stream";
import React from "react";
import {Box, Text, render} from "ink";

import {App} from "../src/app";
import {DharmaBridge} from "../src/bridge";
import {CausalFlowPlane, causalEventRowBudget} from "../src/nihonga/CausalFlowPlane";

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

function cockpitSettled(frame: string): boolean {
  return frame.includes("◆ DHARMA HELM") && frame.includes("BOUNDARY") && frame.includes("offline") && frame.includes("?/7");
}

test("80x24 uses the compact Quiet Field without losing Helm truth", async () => {
  const frame = await renderShellAt(80, 24, cockpitSettled);

  expect(frame).toContain("◆ DHARMA HELM");
  expect(frame).toContain("CONVERSATION");
  expect(frame).toContain("BOUNDARY");
  expect(frame).toContain("chat no-tools");
  expect(frame).toContain("○ offline");
  expect(frame).toContain("HELM ◌ UNKNOWN ?/7");
  for (const label of ["F5", "G56", "G46", "FU", "K3", "O50", "O48"]) {
    expect(frame).toContain(`${label} ?`);
  }
  expect(frame).not.toContain("OFFLINE");
  expect(frame).toContain("Home");
  expect(frame).toContain("Conv");
  expect(frame).toContain("Acti");
  expect(frame).not.toContain("|  route ");
  expect(frame).not.toContain("|  panes ");
  expect(frame).not.toContain("COMMAND POST");
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

test("90x24 remains compact and truthful", async () => {
  const frame = await renderShellAt(90, 24, cockpitSettled);

  expect(frame).toContain("◆ DHARMA HELM");
  expect(frame).toContain("CONVERSATION / FOCUSED");
  expect(frame).not.toContain("COMMAND POST");
  expect(frame).not.toContain("ECOSYSTEM / ORGANISM");
});

test("100x28 selects the two-plane standard composition", async () => {
  const frame = await renderShellAt(
    100,
    28,
    (current) => cockpitSettled(current) && current.includes("CONTEXT / ORGANISM"),
  );

  expect(frame).toContain("CONVERSATION / INTENT");
  expect(frame).toContain("CONTEXT / ORGANISM");
  expect(frame).toContain("WHOLE ORGANISM");
  expect(frame).not.toContain("CAUSAL / PROOF");
});

test("120x30 and larger use the 45/35/20 panorama", async () => {
  const frame = await renderShellAt(
    120,
    30,
    (current) => cockpitSettled(current) && current.includes("ECOSYSTEM / ORGANISM") && current.includes("CAUSAL / PROOF"),
  );

  expect(frame).toContain("CONVERSATION / INTENT");
  expect(frame).toContain("ECOSYSTEM / ORGANISM");
  expect(frame).toContain("CAUSAL / PROOF");
  expect(frame).toContain("six stable fields");
  expect(frame).toContain("○ offline");
  expect(frame).not.toContain("OFFLINE");
  expect(frame).not.toContain("DHARMA TERMINAL");
});

test("120x30 causal proof keeps newest high-volume event titles and summaries intact", async () => {
  const events = Array.from({length: 15}, (_, index) => ({
    id: `event-${index}`,
    sourceEventType: "fixture",
    kind: "status" as const,
    phase: "running" as const,
    title: `event ${index}`,
    summary: `summary ${index}`,
  }));
  const stdout = new TestStdout(24, 19);
  let rendered = "";
  stdout.on("data", (chunk) => {
    rendered += chunk.toString("utf8");
  });
  const instance = render(
    <Box width={24} height={19} flexDirection="column" borderStyle="single" paddingX={1}>
      <Text>CAUSAL / PROOF</Text>
      <CausalFlowPlane events={events} rowBudget={causalEventRowBudget(30)} />
    </Box>,
    {
      stdout: stdout as unknown as NodeJS.WriteStream,
      debug: true,
      patchConsole: false,
      exitOnCtrlC: false,
    },
  );

  try {
    await Bun.sleep(50);
    const frame = stripAnsi(rendered);
    expect(frame).toContain("event 14");
    expect(frame).toContain("summary 14");
    expect(frame).toContain("event 13");
    expect(frame).toContain("15 canonical events");
  } finally {
    instance.unmount();
    instance.cleanup();
  }
});
