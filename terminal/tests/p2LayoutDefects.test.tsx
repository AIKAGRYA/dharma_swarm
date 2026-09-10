import {describe, expect, test} from "bun:test";
import {PassThrough} from "node:stream";
import React from "react";
import {render} from "ink";

import {Composer} from "../src/components/Composer";
import {OnCallTruthBand} from "../src/components/OnCallTruthBand";
import {StatusFooter} from "../src/components/StatusFooter";
import {TranscriptPane} from "../src/components/TranscriptPane";
import {onCallTruthStateWithProjection, unknownOnCallTruthState} from "../src/onCallTruth";
import {decodeHelmOnCallProjection} from "../src/protocol/onCallTruth";
import type {TranscriptLine} from "../src/types";
import {buildOnCallProjection} from "./fixtures/onCallProjection";

class TestStdout extends PassThrough {
  columns: number;
  rows: number;
  isTTY = true;

  constructor(columns: number, rows: number) {
    super();
    this.columns = columns;
    this.rows = rows;
  }

  cursorTo(): boolean { return true; }
  moveCursor(): boolean { return true; }
  clearLine(): boolean { return true; }
  clearScreenDown(): boolean { return true; }
  getColorDepth(): number { return 8; }
  hasColors(): boolean { return true; }
}

function stripAnsi(value: string): string {
  return value.replace(/\u001B\[[0-?]*[ -/]*[@-~]/g, "");
}

async function renderAt(node: React.ReactElement, columns: number, rows: number): Promise<string> {
  const stdout = new TestStdout(columns, rows);
  let frame = "";
  stdout.on("data", (chunk) => { frame += chunk.toString("utf8"); });
  const instance = render(node, {
    stdout: stdout as unknown as NodeJS.WriteStream,
    stderr: new TestStdout(columns, rows) as unknown as NodeJS.WriteStream,
    debug: true,
    patchConsole: false,
    exitOnCtrlC: false,
  });
  await instance.waitUntilRenderFlush();
  const renderedFrame = frame;
  instance.unmount();
  await instance.waitUntilExit();
  instance.cleanup();
  return stripAnsi(renderedFrame);
}

function flattenText(node: React.ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") {
    return "";
  }
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }
  if (Array.isArray(node)) {
    return node.map(flattenText).join("");
  }
  if (React.isValidElement(node)) {
    return flattenText((node.props as {children?: React.ReactNode}).children);
  }
  return "";
}

function missingSeatTruth() {
  const projection = decodeHelmOnCallProjection(buildOnCallProjection({
    state: "LIVE_DEGRADED",
    verdicts: ["UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"],
  }));
  if (!projection) {
    throw new Error("invalid OnCall test fixture");
  }
  return onCallTruthStateWithProjection(unknownOnCallTruthState(), projection);
}

describe("P2 F1/F9 truth-token width budget", () => {
  test("keeps all seven seat verdicts addressable at the exact 120-column breakpoint", async () => {
    const frame = await renderAt(
      <OnCallTruthBand truth={missingSeatTruth()} compact={false} usableNowCount={3} usableLaneTotal={15} />,
      120,
      2,
    );

    for (const seat of [
      /(?:Fable 5|F5) \?missing/,
      /(?:GPT 5\.6|G56) \?missing/,
      /(?:Grok 4\.5\/4\.6|G46) \?missing/,
      /(?:Fugu Ultra|FU) \?missing/,
      /(?:Kimi K3|K3) \?missing/,
      /(?:Opus 5\.0|O50) \?missing/,
      /(?:Opus 4\.8|O48) \?missing/,
    ]) {
      expect(frame).toMatch(seat);
    }
  });

  test("preserves the terminal exact-model reason at narrow and panorama widths", async () => {
    for (const width of [44, 50, 80, 120]) {
      const frame = await renderAt(
        <StatusFooter
          mode="navigate · Esc compose"
          routeLabel="codex_text:gpt-5.6-sol-with-a-deliberately-long-route-label"
          bridgeStatus="connected"
          routeState="unverified"
          strategy="responsive"
          reason="exact_model_unproven"
          compact={width < 100}
        />,
        width,
        1,
      );

      expect(frame).toContain("exact_model_unproven");
    }
  });

  test("a long reason is capped so the route label survives at full width", async () => {
    const reason = "configured route not usable now; live fallback selected after the oracle refreshed";
    const frame = await renderAt(
      <StatusFooter
        mode="compose"
        routeLabel="claude:claude-opus-5.0"
        bridgeStatus="connected"
        routeState="unverified"
        strategy="responsive"
        reason={reason}
        compact={false}
      />,
      100,
      1,
    );

    expect(frame).toContain("route claude:claude-opus-5.0");
    expect(frame).toContain("● bridge");
    expect(frame).toContain("configured route no…");
    expect(frame).not.toContain(reason);
  });

  test("keeps both usability and evaluator identity truth visible at survival width", async () => {
    const frame = await renderAt(
      <OnCallTruthBand truth={unknownOnCallTruthState()} compact width={44} usableNowCount={12} usableLaneTotal={15} />,
      44,
      2,
    );

    expect(frame).toContain("UNKNOWN ?/7");
    expect(frame).toContain("usable 12/15");
    expect(frame).toContain("verified ?/7");
  });
});

describe("P2 F5 transcript row isolation", () => {
  test("pins each logical history row against Yoga shrink before constrained rendering", () => {
    const lines: TranscriptLine[] = [
      {id: "lead", kind: "system", text: "Type a message below"},
      {id: "ack", kind: "assistant", text: "Opened Sessions. Tab cycles panes."},
      {id: "ack-summary", kind: "thinking", text: "\u25a0 1s \u00b7 local \u00b7 ^T details"},
      {id: "user-route", kind: "user", text: "> change models to claude sonnet 5"},
      {id: "reply-a", kind: "assistant", text: "The route picker is open."},
      {id: "reply-b", kind: "assistant", text: "Choose the owner-backed route."},
      {id: "route-summary", kind: "thinking", text: "\u25a0 1s \u00b7 claude:claude-sonnet-5 \u00b7 ^T details"},
      {id: "user-sessions", kind: "user", text: "> open sessions"},
      {id: "sessions-ack", kind: "assistant", text: "Opened Sessions."},
      {id: "sessions-summary", kind: "thinking", text: "\u25a0 1s \u00b7 local \u00b7 ^T details"},
      ...Array.from({length: 14}, (_, index): TranscriptLine => ({
        id: `filler-${index}`,
        kind: "assistant",
        text: `bounded history row ${index}`,
      })),
    ];
    const pane = TranscriptPane({
      frameless: true,
      title: "Conversation",
      lines,
      windowSize: 24,
    });
    const keyedRows = new Map<string, React.ReactElement>();
    const visit = (node: React.ReactNode): void => {
      if (Array.isArray(node)) {
        node.forEach(visit);
        return;
      }
      if (!React.isValidElement(node)) {
        return;
      }
      if (node.key !== null) {
        keyedRows.set(String(node.key), node);
      }
      visit((node.props as {children?: React.ReactNode}).children);
    };
    visit(pane);

    for (const id of ["user-route", "route-summary", "user-sessions", "sessions-summary"]) {
      const row = keyedRows.get(id);
      expect(row, `missing transcript row ${id}`).toBeDefined();
      expect((row?.props as {flexShrink?: number}).flexShrink, `${id} may shrink into a neighboring row`).toBe(0);
    }
  });

  test("bottom-anchored constrained history keeps the newest wrapped turn summary visible", async () => {
    const frame = await renderAt(
      <TranscriptPane
        frameless
        bottomAnchor
        title="Conversation"
        lines={[
          {id: "user", kind: "user", text: "> open sessions and retain this deliberately wrapping request"},
          {id: "reply", kind: "assistant", text: "Opened Sessions."},
          {id: "summary", kind: "thinking", text: "■ 1s · local · ^T details"},
        ]}
        windowSize={3}
      />,
      32,
      4,
    );

    expect(frame).toContain("Opened Sessions.");
    expect(frame).toContain("^T details");
  });
});

describe("P2 F6 navigation swallow recovery", () => {
  test("a retained non-empty draft still names the visible escape back to composition", () => {
    for (const width of [44, 80]) {
      const frame = flattenText(Composer({
        prompt: "change models to claude sonnet 5\nsecond retained line",
        focused: false,
        compact: width < 80,
        width,
      }));

      expect(frame).toContain("change models");
      expect(frame).toMatch(/Esc.*(?:compose|composition|composer)/i);
    }
  });
});

describe("Composer unfocused overflow elision", () => {
  test("an unfocused overflowing draft keeps the prompt cue on line one and marks the hidden tail", () => {
    const prompt = Array.from({length: 8}, (_, index) => `line ${index + 1}`).join("\n");
    const unfocused = flattenText(Composer({prompt, focused: false, compact: false, width: 80}));

    expect(unfocused).toMatch(/^> line 1/);
    expect(unfocused).toMatch(/⋮ line 4/);
    expect(unfocused).not.toContain("line 5");
    expect(unfocused).toMatch(/Esc.*compose/i);

    const focused = flattenText(Composer({prompt, focused: true, compact: false, width: 80}));
    expect(focused).toMatch(/^⋮ line 5/);
    expect(focused).toContain("line 8");
    expect(focused).not.toContain("> line");
  });
});
