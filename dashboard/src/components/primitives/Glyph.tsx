"use client";

/**
 * Glyph — monochrome status glyph.
 *
 * Per docs/plans/2026-05-21-command-plane-design-lock.md anti-AI checklist:
 *   "No emoji except monochrome status glyphs (✓ ✗ ◐ ⊘)."
 *
 * Always renders a single Unicode glyph in the requested tone. No fill, no
 * background, no animation by default. Use for evidence rows, status dots,
 * and inline indicators.
 */

import { colors } from "@/lib/theme";

export type GlyphKind =
  | "check"    // ✓ — passed / ok
  | "cross"    // ✗ — failed / not present
  | "partial"  // ◐ — partial / degraded
  | "block"    // ⊘ — blocked / forbidden
  | "dot"      // ● — fresh-pulse marker (Rokushō)
  | "ring";    // ◯ — idle marker

export type GlyphTone =
  | "active"
  | "rest"
  | "ok"
  | "warn"
  | "fail"
  | "muted";

interface GlyphProps {
  kind: GlyphKind;
  tone?: GlyphTone;
  /** Pulse the glyph with the ambient cadence (1000ms linear). Used for
   *  fresh-value indicators. Off by default. */
  pulse?: boolean;
  /** Optional className passthrough. */
  className?: string;
  /** Optional title for accessibility / tooltip. */
  title?: string;
}

const KIND_GLYPH: Record<GlyphKind, string> = {
  check: "✓",
  cross: "✗",
  partial: "◐",
  block: "⊘",
  dot: "●",
  ring: "◯",
};

const TONE_COLOR: Record<GlyphTone, string> = {
  active: colors.aozora,
  rest: colors.torinoko,
  ok: colors.rokusho,
  warn: colors.kinpaku,
  fail: colors.shu,
  muted: colors.sumi[600],
};

const KIND_DEFAULT_TONE: Record<GlyphKind, GlyphTone> = {
  check: "ok",
  cross: "fail",
  partial: "warn",
  block: "muted",
  dot: "ok",
  ring: "muted",
};

export function Glyph({
  kind,
  tone,
  pulse = false,
  className,
  title,
}: GlyphProps) {
  const effectiveTone = tone ?? KIND_DEFAULT_TONE[kind];
  const color = TONE_COLOR[effectiveTone];
  const character = KIND_GLYPH[kind];

  return (
    <span
      className={`inline-block font-mono ${className ?? ""}`}
      style={{
        color,
        animation: pulse ? "ambient-pulse 1000ms linear infinite" : undefined,
        lineHeight: 1,
      }}
      role="img"
      aria-label={title ?? kind}
      title={title}
    >
      {character}
    </span>
  );
}
