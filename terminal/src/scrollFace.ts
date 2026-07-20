// FACE-3 "the scroll" — a reading-first manuscript face, entered via /scroll.
// The conversation renders as a clean centered column (~80 cols), with ONE
// thin wave rule between turns and ALL telemetry folded behind a single
// toggleable drawer row (^D). One-row status either way; the composer is the
// frame's only border. Pure projections live here; the render branch sits in
// app.tsx beside the zen face.
import type {TranscriptLine} from "./types";

// Plain ASCII wave: the operator's terminal font shatters exotic glyphs
// (design truth finding #19) — tildes degrade nowhere.
const WAVE_RULE = "~ ~ ~";

// Inserts a thin centered wave rule before each turn after the first. A turn
// boundary is a "user" line that follows a non-user line; the boot prelude
// (no user lines) passes through untouched. Rule lines ride the "thinking"
// kind so they inherit the dim quiet-chrome styling.
export function manuscriptLines(lines: TranscriptLine[], measure: number): TranscriptLine[] {
  // TranscriptPane pads one column each side; center within the inner width.
  const indent = " ".repeat(Math.max(0, Math.floor((measure - 2 - WAVE_RULE.length) / 2)));
  const out: TranscriptLine[] = [];
  for (let i = 0; i < lines.length; i++) {
    const current = lines[i];
    if (!current) continue;
    if (current.kind === "user" && i > 0 && lines[i - 1]?.kind !== "user") {
      out.push({id: `scroll-rule-${i}-${current.id}`, kind: "thinking", text: `${indent}${WAVE_RULE}`});
    }
    out.push(current);
  }
  return out;
}

type ScrollStatusInput = {
  drawerOpen: boolean;
  routeLabel: string;
  bridgeStatus: string;
  routeState: string;
  strategy?: string;
};

// Gate tokens mirror StatusFooter semantics (glyph + word travel together;
// expected-offline is never a danger state).
function gateToken(bridgeStatus: string): string {
  switch (bridgeStatus) {
    case "connected":
      return "● bridge";
    case "degraded":
      return "⚠ degraded";
    case "offline":
      return "○ offline";
    default:
      return `◌ ${bridgeStatus}`;
  }
}

// Closed: silence is health only when transport and route are both ready.
// Connected-but-unverified is visible rather than disappearing behind the
// drawer. Open: the drawer IS the status row (still one row) — route, gate,
// route state, strategy.
export function scrollStatusLine(input: ScrollStatusInput): string {
  if (!input.drawerOpen) {
    const parts = ["the scroll"];
    if (input.bridgeStatus !== "connected") {
      parts.push(gateToken(input.bridgeStatus));
    } else if (input.routeState !== "ready") {
      parts.push(input.routeState);
    }
    parts.push("^D telemetry", "F2 zen");
    return parts.join("  ·  ");
  }
  const parts = [`route ${input.routeLabel}`, gateToken(input.bridgeStatus)];
  if (input.bridgeStatus === "connected" && input.routeState) {
    parts.push(input.routeState);
  }
  if (input.strategy) {
    parts.push(input.strategy);
  }
  parts.push("^D close");
  return parts.join("  ·  ");
}
