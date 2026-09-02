#!/usr/bin/env bun
/**
 * Render a Helm seat-matrix report as a deterministic, display-only capture.
 *
 * This utility does not evaluate routes, contact providers, or grant positive
 * authority to serialized data. It rebuilds only the wire-shaped projection
 * embedded in `dharma.helm.seat_matrix_run.v1`, submits that untrusted shape to
 * the terminal's strict decoder, and renders the existing OnCallTruthBand.
 */

import {createHash} from "node:crypto";
import {
  closeSync,
  constants as fsConstants,
  existsSync,
  fchmodSync,
  fstatSync,
  fsyncSync,
  lstatSync,
  mkdirSync,
  openSync,
  readFileSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import {homedir} from "node:os";
import path from "node:path";
import {PassThrough} from "node:stream";
import React from "react";
import {render} from "ink";

import {OnCallTruthBand} from "../src/components/OnCallTruthBand.tsx";
import {
  HELM_ON_CALL_SCHEMA,
  onCallTruthStateWithProjection,
  unknownOnCallTruthState,
  type HelmOnCallProjection,
  type OnCallTruthState,
} from "../src/onCallTruth.ts";
import {decodeHelmOnCallProjection} from "../src/protocol/onCallTruth.ts";

export const SEAT_MATRIX_REPORT_SCHEMA = "dharma.helm.seat_matrix_run.v1" as const;
export const SEAT_STRIP_CAPTURE_SCHEMA = "dharma.helm.seat_strip_capture.v1" as const;
export const CAPTURE_WIDTHS = [80, 120] as const;

type JsonObject = {[key: string]: unknown};
type CaptureWidth = (typeof CAPTURE_WIDTHS)[number];

export type SeatStripFrame = Readonly<{
  width: CaptureWidth;
  height: 2;
  count_token: string;
  text: string;
}>;

export type SeatStripCapture = Readonly<{
  schema_version: typeof SEAT_STRIP_CAPTURE_SCHEMA;
  authority: "NONE";
  purpose: "render_only";
  state_promotion_allowed: false;
  serialized_positive_is_evaluation_authority: false;
  source_report_path: string;
  source_report_schema_version: typeof SEAT_MATRIX_REPORT_SCHEMA;
  source_report_sha256: string;
  projection_schema_version: typeof HELM_ON_CALL_SCHEMA;
  projection_sha256: string;
  state: HelmOnCallProjection["state"];
  on_call_count: number | null;
  total: 7;
  runtime_epoch: string;
  evaluated_at: string;
  before_state: "UNKNOWN";
  before_count_token: "?/7";
  before_frames: readonly SeatStripFrame[];
  after_state: HelmOnCallProjection["state"];
  after_count_token: string;
  frames: readonly SeatStripFrame[];
}>;

export class SeatStripCaptureError extends Error {}

class CaptureStdout extends PassThrough {
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

function asObject(value: unknown): JsonObject | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as JsonObject
    : undefined;
}

function stripAnsi(value: string): string {
  return value.replace(/\u001B\[[0-?]*[ -/]*[@-~]/g, "");
}

function normalizedFrame(value: string): string {
  const text = stripAnsi(value)
    .replaceAll("\r", "")
    .split("\n")
    .map((line) => line.trimEnd())
    .join("\n")
    .trimEnd();
  return `${text}\n`;
}

function canonicalJsonValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(canonicalJsonValue);
  }
  const object = asObject(value);
  if (object) {
    return Object.fromEntries(
      Object.keys(object)
        .sort()
        .map((key) => [key, canonicalJsonValue(object[key])]),
    );
  }
  return value;
}

export function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalJsonValue(value));
}

export function sha256(value: Uint8Array | string): string {
  return createHash("sha256").update(value).digest("hex");
}

/** Decode only the report's evaluator projection; blockers remain metadata. */
export function projectionFromSeatMatrixReport(value: unknown): HelmOnCallProjection {
  const report = asObject(value);
  if (!report || report.schema_version !== SEAT_MATRIX_REPORT_SCHEMA) {
    throw new SeatStripCaptureError(
      `input must use ${SEAT_MATRIX_REPORT_SCHEMA}`,
    );
  }

  const candidate = {
    schema_version: HELM_ON_CALL_SCHEMA,
    state: report.state,
    on_call_count: report.on_call_count,
    total: report.total,
    seats: report.route_verifications,
    evaluated_at: report.evaluated_at,
    runtime_epoch: report.runtime_epoch,
  };
  const projection = decodeHelmOnCallProjection(candidate);
  if (!projection) {
    throw new SeatStripCaptureError(
      "seat-matrix report does not contain a valid ordered evaluator projection",
    );
  }
  return projection;
}

async function renderTruthStrip(
  truth: OnCallTruthState,
  width: CaptureWidth,
  expectedState: string,
  expectedCount: string,
): Promise<string> {
  const stdout = new CaptureStdout(width);
  let frame = "";
  stdout.on("data", (chunk: Buffer | string) => {
    frame += chunk.toString();
  });
  const instance = render(
    <OnCallTruthBand
      truth={truth}
      compact={width < 120}
      width={width}
    />,
    {
      stdout: stdout as unknown as NodeJS.WriteStream,
      stderr: new CaptureStdout(width) as unknown as NodeJS.WriteStream,
      debug: true,
      patchConsole: false,
      exitOnCtrlC: false,
    },
  );
  await instance.waitUntilRenderFlush();
  const rendered = normalizedFrame(frame);
  instance.unmount();
  await instance.waitUntilExit();
  instance.cleanup();

  if (!rendered.includes(expectedState) || !rendered.includes(expectedCount)) {
    throw new SeatStripCaptureError(
      `rendered ${width}-column strip omitted state/count ${expectedState} ${expectedCount}`,
    );
  }
  return rendered;
}

export async function renderSeatStrip(
  projection: HelmOnCallProjection,
  width: CaptureWidth,
): Promise<string> {
  const truth = onCallTruthStateWithProjection(
    unknownOnCallTruthState(),
    projection,
  );
  const countToken = `${projection.on_call_count === null ? "?" : projection.on_call_count}/${projection.total}`;
  return renderTruthStrip(truth, width, projection.state, countToken);
}

async function renderUnknownSeatStrip(
  runtimeEpoch: string,
  width: CaptureWidth,
): Promise<string> {
  return renderTruthStrip(
    unknownOnCallTruthState(runtimeEpoch),
    width,
    "UNKNOWN",
    "?/7",
  );
}

export async function buildSeatStripCapture(
  reportBytes: Uint8Array,
  sourceReportPath: string,
): Promise<SeatStripCapture> {
  let report: unknown;
  try {
    report = JSON.parse(Buffer.from(reportBytes).toString("utf8"));
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new SeatStripCaptureError(`input report is not valid JSON: ${detail}`);
  }
  const projection = projectionFromSeatMatrixReport(report);
  const countToken = `${projection.on_call_count === null ? "?" : projection.on_call_count}/${projection.total}`;
  const beforeFrames: SeatStripFrame[] = [];
  const frames: SeatStripFrame[] = [];
  for (const width of CAPTURE_WIDTHS) {
    beforeFrames.push({
      width,
      height: 2,
      count_token: "?/7",
      text: await renderUnknownSeatStrip(projection.runtime_epoch, width),
    });
    frames.push({
      width,
      height: 2,
      count_token: countToken,
      text: await renderSeatStrip(projection, width),
    });
  }

  return {
    schema_version: SEAT_STRIP_CAPTURE_SCHEMA,
    authority: "NONE",
    purpose: "render_only",
    state_promotion_allowed: false,
    serialized_positive_is_evaluation_authority: false,
    source_report_path: path.resolve(sourceReportPath),
    source_report_schema_version: SEAT_MATRIX_REPORT_SCHEMA,
    source_report_sha256: sha256(reportBytes),
    projection_schema_version: HELM_ON_CALL_SCHEMA,
    projection_sha256: sha256(canonicalJson(projection)),
    state: projection.state,
    on_call_count: projection.on_call_count,
    total: projection.total,
    runtime_epoch: projection.runtime_epoch,
    evaluated_at: projection.evaluated_at,
    before_state: "UNKNOWN",
    before_count_token: "?/7",
    before_frames: beforeFrames,
    after_state: projection.state,
    after_count_token: countToken,
    frames,
  };
}

function pathIsBelow(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate);
  return relative.length > 0
    && relative !== ".."
    && !relative.startsWith(`..${path.sep}`)
    && !path.isAbsolute(relative);
}

function ensurePrivateDirectoryTree(root: string, parent: string): void {
  if (!existsSync(root)) {
    mkdirSync(root, {mode: 0o700});
  }
  const rootStat = lstatSync(root);
  if (rootStat.isSymbolicLink() || !rootStat.isDirectory()) {
    throw new SeatStripCaptureError("~/.dharma must be a real directory");
  }

  const relative = path.relative(root, parent);
  let current = root;
  for (const segment of relative.split(path.sep).filter(Boolean)) {
    current = path.join(current, segment);
    if (!existsSync(current)) {
      mkdirSync(current, {mode: 0o700});
      continue;
    }
    const stat = lstatSync(current);
    if (stat.isSymbolicLink() || !stat.isDirectory()) {
      throw new SeatStripCaptureError(
        `output parent must not traverse a symlink or non-directory: ${current}`,
      );
    }
  }
}

export function validateOutputPath(
  outputPath: string,
  homeDirectory = homedir(),
): string {
  if (!path.isAbsolute(outputPath)) {
    throw new SeatStripCaptureError("--output must be an explicit absolute path");
  }
  const root = path.resolve(homeDirectory, ".dharma");
  const candidate = path.resolve(outputPath);
  if (!pathIsBelow(root, candidate)) {
    throw new SeatStripCaptureError("--output must be a JSON file beneath ~/.dharma");
  }
  if (path.extname(candidate) !== ".json") {
    throw new SeatStripCaptureError("--output must end in .json");
  }
  return candidate;
}

function readRegularFileNoFollow(inputPath: string): Buffer {
  if (!path.isAbsolute(inputPath)) {
    throw new SeatStripCaptureError("--input must be an explicit absolute path");
  }
  let descriptor: number;
  try {
    descriptor = openSync(
      inputPath,
      fsConstants.O_RDONLY | fsConstants.O_NOFOLLOW,
    );
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new SeatStripCaptureError(`cannot open input report: ${detail}`);
  }
  try {
    if (!fstatSync(descriptor).isFile()) {
      throw new SeatStripCaptureError("--input must name a regular file");
    }
    return readFileSync(descriptor);
  } finally {
    closeSync(descriptor);
  }
}

export function writeSeatStripCapture(
  outputPath: string,
  capture: SeatStripCapture,
  homeDirectory = homedir(),
): string {
  const candidate = validateOutputPath(outputPath, homeDirectory);
  ensurePrivateDirectoryTree(
    path.resolve(homeDirectory, ".dharma"),
    path.dirname(candidate),
  );
  if (existsSync(candidate)) {
    throw new SeatStripCaptureError("refusing to overwrite an existing capture");
  }

  let descriptor: number | undefined;
  let created = false;
  try {
    descriptor = openSync(
      candidate,
      fsConstants.O_WRONLY
        | fsConstants.O_CREAT
        | fsConstants.O_EXCL
        | fsConstants.O_NOFOLLOW,
      0o600,
    );
    created = true;
    fchmodSync(descriptor, 0o600);
    writeFileSync(descriptor, `${JSON.stringify(capture, null, 2)}\n`, "utf8");
    fsyncSync(descriptor);
    closeSync(descriptor);
    descriptor = undefined;
  } catch (error) {
    if (descriptor !== undefined) {
      closeSync(descriptor);
    }
    if (created && existsSync(candidate)) {
      unlinkSync(candidate);
    }
    if (error instanceof SeatStripCaptureError) {
      throw error;
    }
    const detail = error instanceof Error ? error.message : String(error);
    throw new SeatStripCaptureError(`cannot write capture: ${detail}`);
  }
  return candidate;
}

export async function captureReportToFile(
  inputPath: string,
  outputPath: string,
  homeDirectory = homedir(),
): Promise<SeatStripCapture> {
  const reportBytes = readRegularFileNoFollow(inputPath);
  const capture = await buildSeatStripCapture(reportBytes, inputPath);
  writeSeatStripCapture(outputPath, capture, homeDirectory);
  return capture;
}

function parseArguments(argv: readonly string[]): {input: string; output: string} {
  let input = "";
  let output = "";
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument !== "--input" && argument !== "--output") {
      throw new SeatStripCaptureError(
        "usage: bun run scripts/render_on_call_capture.tsx --input /absolute/report.json --output /absolute/capture.json",
      );
    }
    const value = argv[index + 1];
    if (!value) {
      throw new SeatStripCaptureError(`${argument} requires a path`);
    }
    if (argument === "--input") input = value;
    if (argument === "--output") output = value;
    index += 1;
  }
  if (!input || !output) {
    throw new SeatStripCaptureError("both --input and --output are required");
  }
  return {input, output};
}

export async function main(argv: readonly string[] = process.argv.slice(2)): Promise<number> {
  try {
    const {input, output} = parseArguments(argv);
    const capture = await captureReportToFile(input, output);
    const count = capture.on_call_count === null ? "?" : String(capture.on_call_count);
    process.stdout.write(`wrote ${path.resolve(output)}: ${count}/${capture.total} ${capture.state} (render-only)\n`);
    return 0;
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    process.stderr.write(`render-on-call-capture: ${detail}\n`);
    return 2;
  }
}

if (import.meta.main) {
  process.exitCode = await main();
}
