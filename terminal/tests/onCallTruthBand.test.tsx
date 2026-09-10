import {expect, test} from "bun:test";
import {PassThrough} from "node:stream";
import React from "react";
import {render} from "ink";

import {formatReceiptAge, OnCallTruthBand} from "../src/components/OnCallTruthBand";
import {onCallTruthStateWithProjection, unknownOnCallTruthState, type OnCallTruthState} from "../src/onCallTruth";
import {decodeHelmOnCallProjection} from "../src/protocol/onCallTruth";
import {buildOnCallProjection} from "./fixtures/onCallProjection";

class TestStdout extends PassThrough {
  columns: number;
  rows = 2;
  isTTY = true;

  constructor(columns: number) {
    super();
    this.columns = columns;
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

async function renderBand(truth: OnCallTruthState, columns = 80): Promise<string> {
  const stdout = new TestStdout(columns);
  let frame = "";
  stdout.on("data", (chunk) => { frame += chunk.toString("utf8"); });
  const instance = render(<OnCallTruthBand truth={truth} compact={columns < 120} />, {
    stdout: stdout as unknown as NodeJS.WriteStream,
    stderr: new TestStdout(columns) as unknown as NodeJS.WriteStream,
    debug: true,
    patchConsole: false,
    exitOnCtrlC: false,
  });
  await Bun.sleep(10);
  instance.unmount();
  instance.cleanup();
  return stripAnsi(frame);
}

function authoritativeTruth(projection: ReturnType<typeof buildOnCallProjection>): OnCallTruthState {
  const decoded = decodeHelmOnCallProjection(projection);
  if (!decoded) {
    throw new Error("invalid OnCall test fixture");
  }
  return onCallTruthStateWithProjection(unknownOnCallTruthState(), decoded);
}

test("80-column UNKNOWN band shows ?/7 and the complete fixed seat census", async () => {
  const frame = await renderBand(unknownOnCallTruthState());

  expect(frame).toContain("HELM ◌ UNKNOWN ?/7");
  for (const label of ["F5", "G56", "G46", "FU", "K3", "O50", "O48"]) {
    expect(frame).toContain(`${label} ?`);
  }
});

test("80-column degraded band keeps all seven ordered seats through O48 visible", async () => {
  const truth = authoritativeTruth(buildOnCallProjection({
    state: "LIVE_DEGRADED",
    verdicts: ["ON_CALL", "REJECTED", "REJECTED", "REJECTED", "REJECTED", "REJECTED", "REJECTED"],
  }));
  const frame = await renderBand(truth);

  expect(frame).toContain("LIVE_DEGRADED 1/7");
  expect(frame).toContain("F5 ✓1m");
  for (const label of ["G56", "G46", "FU", "K3", "O50", "O48"]) {
    expect(frame).toContain(`${label} ×`);
  }
  expect(frame.indexOf("F5")).toBeLessThan(frame.indexOf("O48"));
});

test("renders Python-provided ages and aggregate clock skew without evaluating timestamps", async () => {
  const onCall = await renderBand(authoritativeTruth(buildOnCallProjection()));
  expect(onCall).toContain("ON_CALL 7/7");
  for (const label of ["F5", "G56", "G46", "FU", "K3", "O50", "O48"]) {
    expect(onCall).toContain(`${label} ✓1m`);
  }

  const skewProjection = buildOnCallProjection({
    state: "CLOCK_SKEW",
    verdicts: ["ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "CLOCK_SKEW"],
  });
  if (skewProjection.seats[6]?.evidence) {
    skewProjection.seats[6].evidence.age_seconds = null;
  }
  const skew = await renderBand(authoritativeTruth(skewProjection));
  expect(skew).toContain("CLOCK_SKEW 6/7");
  expect(skew).toContain("O48 ✖");

  expect(formatReceiptAge(0)).toBe("0s");
  expect(formatReceiptAge(60)).toBe("1m");
  expect(formatReceiptAge(3_600)).toBe("1h");
  expect(formatReceiptAge(null)).toBe("?");
});

test("names usable-now lanes separately from evaluator-verified seats", async () => {
  const truth = authoritativeTruth(buildOnCallProjection({
    state: "LIVE_DEGRADED",
    verdicts: ["ON_CALL", "REJECTED", "REJECTED", "REJECTED", "REJECTED", "REJECTED", "REJECTED"],
  }));
  const stdout = new TestStdout(120);
  let frame = "";
  stdout.on("data", (chunk) => { frame += chunk.toString("utf8"); });
  const instance = render(
    <OnCallTruthBand truth={truth} compact={false} usableNowCount={2} usableLaneTotal={5} />,
    {
      stdout: stdout as unknown as NodeJS.WriteStream,
      stderr: new TestStdout(120) as unknown as NodeJS.WriteStream,
      debug: true,
      patchConsole: false,
      exitOnCtrlC: false,
    },
  );
  await Bun.sleep(10);
  instance.unmount();
  instance.cleanup();

  const rendered = stripAnsi(frame);
  expect(rendered).toContain("Usable now 2/5 lanes");
  expect(rendered).toContain("Identity verified 1/7");
  expect(rendered).not.toContain("available 1/7");
});
