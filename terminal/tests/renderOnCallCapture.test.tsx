import {expect, test} from "bun:test";
import {createHash} from "node:crypto";
import {mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync} from "node:fs";
import {tmpdir} from "node:os";
import path from "node:path";

import {
  SEAT_MATRIX_REPORT_SCHEMA,
  SEAT_STRIP_CAPTURE_SCHEMA,
  SeatStripCaptureError,
  buildSeatStripCapture,
  captureReportToFile,
  projectionFromSeatMatrixReport,
  validateOutputPath,
} from "../scripts/render_on_call_capture";
import {buildOnCallProjection, type FixtureProjection} from "./fixtures/onCallProjection";

function matrixReport(projection: FixtureProjection): {[key: string]: unknown} {
  return {
    schema_version: SEAT_MATRIX_REPORT_SCHEMA,
    state: projection.state,
    on_call_count: projection.on_call_count,
    total: projection.total,
    evaluated_at: projection.evaluated_at,
    runtime_epoch: projection.runtime_epoch,
    blocker_authority: "operational_observation_only",
    blocker_vocabulary: [
      "identity_unproven",
      "key_missing",
      "model_missing",
      "quota",
      "unsupported_transport",
    ],
    catalog: [],
    route_verifications: projection.seats,
    blockers: projection.seats
      .filter((seat) => seat.verdict !== "ON_CALL")
      .map((seat) => ({seat_id: seat.seat_id, blocker: "identity_unproven"})),
  };
}

function twoOfSevenReport(): {[key: string]: unknown} {
  return matrixReport(buildOnCallProjection({
    state: "LIVE_DEGRADED",
    verdicts: ["ON_CALL", "ON_CALL", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"],
  }));
}

test("renders the exact decoded evaluator count at 80 and 120 columns with hash linkage", async () => {
  const bytes = Buffer.from(JSON.stringify(twoOfSevenReport()), "utf8");
  const capture = await buildSeatStripCapture(bytes, "/tmp/render-only-seat-matrix.json");

  expect(capture.schema_version).toBe(SEAT_STRIP_CAPTURE_SCHEMA);
  expect(capture.authority).toBe("NONE");
  expect(capture.purpose).toBe("render_only");
  expect(capture.state_promotion_allowed).toBeFalse();
  expect(capture.serialized_positive_is_evaluation_authority).toBeFalse();
  expect(capture.source_report_sha256).toBe(
    createHash("sha256").update(bytes).digest("hex"),
  );
  expect(capture.projection_sha256).toMatch(/^[0-9a-f]{64}$/);
  expect(capture.on_call_count).toBe(2);
  expect(capture.total).toBe(7);
  expect(capture.before_state).toBe("UNKNOWN");
  expect(capture.before_count_token).toBe("?/7");
  expect(capture.before_frames.map((frame) => frame.width)).toEqual([80, 120]);
  for (const frame of capture.before_frames) {
    expect(frame.text).toContain("UNKNOWN ?/7");
    expect(frame.text).toContain(frame.width === 80 ? "F5 ?" : "Fable 5 ?");
    expect(frame.text).toContain(frame.width === 80 ? "O48 ?" : "Opus 4.8 ?");
  }
  expect(capture.after_state).toBe("LIVE_DEGRADED");
  expect(capture.after_count_token).toBe("2/7");
  expect(capture.frames.map((frame) => frame.width)).toEqual([80, 120]);

  for (const frame of capture.frames) {
    expect(frame.count_token).toBe("2/7");
    expect(frame.text).toContain("LIVE_DEGRADED 2/7");
    expect(frame.text).toContain("F5 ✓1m");
    expect(frame.text).toContain("O48 ?");
  }
});

test("rejects forged aggregate count, seat order, report schema, and total", () => {
  const cases: Array<[string, {[key: string]: unknown}]> = [];

  const forgedCount = structuredClone(twoOfSevenReport());
  forgedCount.on_call_count = 7;
  forgedCount.state = "ON_CALL";
  cases.push(["forged count", forgedCount]);

  const wrongOrder = structuredClone(twoOfSevenReport());
  wrongOrder.route_verifications = [
    ...(wrongOrder.route_verifications as unknown[]),
  ].reverse();
  cases.push(["wrong order", wrongOrder]);

  const wrongSchema = structuredClone(twoOfSevenReport());
  wrongSchema.schema_version = "dharma.helm.seat_matrix_run.forged";
  cases.push(["wrong schema", wrongSchema]);

  const wrongTotal = structuredClone(twoOfSevenReport());
  wrongTotal.total = 8;
  cases.push(["wrong total", wrongTotal]);

  for (const [name, report] of cases) {
    expect(
      () => projectionFromSeatMatrixReport(report),
      name,
    ).toThrow(SeatStripCaptureError);
  }
});

test("writes only an explicit private JSON artifact beneath the selected ~/.dharma", async () => {
  const temporaryHome = mkdtempSync(path.join(tmpdir(), "helm-seat-strip-capture-"));
  try {
    const dharmaRoot = path.join(temporaryHome, ".dharma");
    mkdirSync(dharmaRoot, {mode: 0o700});
    const input = path.join(temporaryHome, "seat-matrix.json");
    const output = path.join(dharmaRoot, "campaign", "seat-strip.json");
    writeFileSync(input, JSON.stringify(twoOfSevenReport()), "utf8");

    const capture = await captureReportToFile(input, output, temporaryHome);
    const stored = JSON.parse(readFileSync(output, "utf8")) as {[key: string]: unknown};

    expect(capture.on_call_count).toBe(2);
    expect(stored.schema_version).toBe(SEAT_STRIP_CAPTURE_SCHEMA);
    expect(stored.authority).toBe("NONE");
    expect(statSync(output).mode & 0o777).toBe(0o600);
    expect(() => validateOutputPath(path.join(temporaryHome, "outside.json"), temporaryHome)).toThrow(
      /beneath ~\/\.dharma/,
    );
  } finally {
    rmSync(temporaryHome, {recursive: true, force: true});
  }
});
