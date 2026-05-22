"use client";

/**
 * Numeral — the protagonist primitive.
 *
 * Per docs/plans/2026-05-21-command-plane-design-lock.md:
 *   "Numbers are the protagonist on every screen. Tabular monospace numerals
 *    are the loudest element. UI chrome is stage-hand."
 *
 * Renders as a span with tabular figures (font-feature-settings: 'tnum'),
 * size scaled relative to surrounding prose, Nihonga-anchored tone tokens.
 */

import type { ReactNode } from "react";
import { colors } from "@/lib/theme";

export type NumeralTone =
  | "active"   // identity / actuation — Gunjō azurite
  | "rest"     // at-rest — Gofun washi cream at 92%
  | "ok"       // success / fresh — Rokushō malachite
  | "warn"     // stale / aged — Kinpaku Ōdo ochre
  | "fail"     // FAIL / urgent — Shu vermillion (sparing)
  | "muted";   // idle / inactive — warm sumi-600

export type NumeralSize = "sm" | "md" | "lg" | "xl" | "hero";

interface NumeralProps {
  /** Value to display (number or pre-formatted string). */
  value: ReactNode;
  /** Tone token; defaults to "rest". */
  tone?: NumeralTone;
  /** Size; defaults to "md". `lg` and `xl` are protagonist sizes. */
  size?: NumeralSize;
  /** Optional unit/suffix label, rendered smaller and muted. */
  unit?: string;
  /** Optional className passthrough. */
  className?: string;
  /** Optional title for hover tooltip. */
  title?: string;
}

const TONE_COLOR: Record<NumeralTone, string> = {
  active: colors.aozora,
  rest: colors.torinoko,
  ok: colors.rokusho,
  warn: colors.kinpaku,
  fail: colors.shu,
  muted: colors.sumi[600],
};

// Protagonist scale: numbers MUST be 1.5-2x surrounding prose.
// Body text is text-sm (~14px). Protagonist xl is text-3xl (~30px) so
// live instrument tiles read as numbers-first, chrome-second.
const SIZE_CLASS: Record<NumeralSize, string> = {
  sm: "text-xs",      // ~12px — chrome / tertiary
  md: "text-sm",      // ~14px — body baseline
  lg: "text-lg",      // ~18px — secondary number
  xl: "text-3xl",     // ~30px — protagonist instrument number
  hero: "text-5xl",   // ~48px — single hero number (cockpit etc.)
};

export function Numeral({
  value,
  tone = "rest",
  size = "md",
  unit,
  className,
  title,
}: NumeralProps) {
  const color = TONE_COLOR[tone];
  const sizeCls = SIZE_CLASS[size];

  return (
    <span
      className={`font-mono tabular-nums ${sizeCls} ${className ?? ""}`}
      style={{
        color,
        fontFeatureSettings: "'tnum' 1, 'lnum' 1",
        fontVariantNumeric: "tabular-nums lining-nums",
      }}
      title={title}
    >
      <span style={{ fontWeight: tone === "rest" ? 400 : 500 }}>{value}</span>
      {unit ? (
        <span
          className="ml-1 text-xs"
          style={{ color: colors.sumi[600], fontWeight: 400 }}
        >
          {unit}
        </span>
      ) : null}
    </span>
  );
}
