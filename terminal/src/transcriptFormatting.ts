import type {BridgeStatus, TranscriptLine} from "./types";

export type TranscriptSegment = {
  text: string;
  color?: string;
  bold?: boolean;
  dimColor?: boolean;
};

export type FormattedTranscriptLine = {
  prefix?: TranscriptSegment;
  segments: TranscriptSegment[];
  color?: string;
  bold?: boolean;
};

const COMMAND_PATTERN = /(^|[^\w/])(?<command>\/[a-z][a-z0-9_-]*)(?=$|[\s:),.])/gi;

export const OFFLINE_NO_SIGNAL_TEXT = "no signal (backend offline)";

// F-161: any 'loading' token offline is a dishonest pending state — the match is
// deliberately broad (substring, case-insensitive) because the offline frame law
// is "no 'loading' text anywhere", not "no known placeholder".
const PENDING_TOKEN_PATTERN = /loading/i;
const PENDING_SUBJECT_PATTERN = /^(?<subject>.*?)\s*loading(?:\.{3}|…)?\s*$/i;

export function isPendingPlaceholderLine(line: TranscriptLine): boolean {
  return PENDING_TOKEN_PATTERN.test(line.text ?? "");
}

export function projectLinesForBridgeStatus(lines: TranscriptLine[], bridgeStatus: BridgeStatus): TranscriptLine[] {
  if (bridgeStatus !== "offline") {
    return lines;
  }
  let changed = false;
  const projected = lines.map((line) => {
    if (!isPendingPlaceholderLine(line)) {
      return line;
    }
    changed = true;
    const subject = (line.text ?? "").match(PENDING_SUBJECT_PATTERN)?.groups?.subject?.trim();
    return {...line, text: subject ? `${subject}: ${OFFLINE_NO_SIGNAL_TEXT}` : OFFLINE_NO_SIGNAL_TEXT};
  });
  return changed ? projected : lines;
}

function baseColorFor(kind: TranscriptLine["kind"]): string {
  switch (kind) {
    case "assistant":
      return "white";
    case "thinking":
      return "gray";
    case "tool":
      return "yellow";
    case "error":
      return "red";
    case "user":
      return "cyan";
    default:
      return "green";
  }
}

export function extractSlashCommands(text: string): string[] {
  const commands: string[] = [];
  const pattern = new RegExp(COMMAND_PATTERN);
  for (const match of text.matchAll(pattern)) {
    const command = match.groups?.command?.trim();
    if (command) {
      commands.push(command);
    }
  }
  return commands;
}

function buildInlineSegments(text: string, color: string): TranscriptSegment[] {
  const segments: TranscriptSegment[] = [];
  let cursor = 0;
  const pattern = new RegExp(COMMAND_PATTERN);

  for (const match of text.matchAll(pattern)) {
    const command = match.groups?.command;
    const index = match.index ?? 0;
    const full = match[0] ?? "";
    const commandOffset = full.lastIndexOf(command ?? "");
    const commandIndex = index + Math.max(0, commandOffset);

    if (commandIndex > cursor) {
      segments.push({text: text.slice(cursor, commandIndex), color});
    }
    if (command) {
      segments.push({text: command, color: "blue", bold: true});
      cursor = commandIndex + command.length;
    }
  }

  if (cursor < text.length) {
    segments.push({text: text.slice(cursor), color});
  }

  return segments.length > 0 ? segments : [{text, color}];
}

export function formatTranscriptLine(line: TranscriptLine): FormattedTranscriptLine {
  const text = line.text ?? "";
  const baseColor = baseColorFor(line.kind);

  if (text.startsWith("### ")) {
    return {
      prefix: {text: "▸ ", color: "blue", bold: true},
      segments: [{text: text.slice(4), color: "blue", bold: true}],
      color: "blue",
      bold: true,
    };
  }
  if (text.startsWith("## ")) {
    return {
      prefix: {text: "◇ ", color: "cyan", bold: true},
      segments: [{text: text.slice(3), color: "cyan", bold: true}],
      color: "cyan",
      bold: true,
    };
  }
  if (text.startsWith("# ")) {
    return {
      prefix: {text: "◆ ", color: "magenta", bold: true},
      segments: [{text: text.slice(2), color: "magenta", bold: true}],
      color: "magenta",
      bold: true,
    };
  }
  if (text.startsWith("- ")) {
    return {
      prefix: {text: "• ", color: "gray"},
      segments: buildInlineSegments(text.slice(2), baseColor),
      color: baseColor,
    };
  }
  if (line.kind === "tool" && (text.startsWith("⠋ ") || text.startsWith("✓ "))) {
    const prefix = text.slice(0, 2);
    const body = text.slice(2);
    return {
      prefix: {text: `${prefix} `, color: baseColor, bold: true},
      segments: buildInlineSegments(body, baseColor),
      color: baseColor,
    };
  }

  return {
    segments: buildInlineSegments(text, baseColor),
    color: baseColor,
  };
}
