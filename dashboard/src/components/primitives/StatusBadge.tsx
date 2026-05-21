"use client";

/**
 * StatusBadge — ALLCAPS-MONO 4-state badge.
 *
 * Per docs/plans/2026-05-21-command-plane-design-lock.md craft-reviewer report:
 *   "ALLCAPS MONO for status badges (PASS / FAIL / STALE / DRIFT) — only these
 *    four reserved tokens; cannot leak into other labels."
 *
 * Hairline border (1px Tetsu-iro), no shadow, no fill — color carries the
 * meaning; chrome is restraint.
 */

import { colors } from "@/lib/theme";

export type StatusBadgeState = "pass" | "fail" | "stale" | "drift";

interface StatusBadgeProps {
  state: StatusBadgeState;
  /** Optional className passthrough. */
  className?: string;
  /** Optional title for hover tooltip. */
  title?: string;
}

const STATE_COLOR: Record<StatusBadgeState, string> = {
  pass: colors.rokusho,    // 緑青 muted malachite — OK
  fail: colors.shu,        // 朱 vermillion — FAIL (alarm-only)
  stale: colors.kinpaku,   // 黄土 Ōdo ochre — STALE
  drift: colors.fuji,      // 藤 secondary purple — DRIFT (distinct from fail)
};

const STATE_LABEL: Record<StatusBadgeState, string> = {
  pass: "PASS",
  fail: "FAIL",
  stale: "STALE",
  drift: "DRIFT",
};

export function StatusBadge({
  state,
  className,
  title,
}: StatusBadgeProps) {
  const color = STATE_COLOR[state];
  const label = STATE_LABEL[state];

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-mono uppercase tracking-wider ${className ?? ""}`}
      style={{
        color,
        border: `1px solid color-mix(in srgb, ${color} 40%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${color} 6%, transparent)`,
        letterSpacing: "0.08em",
        fontFeatureSettings: "'tnum' 1",
        lineHeight: 1.2,
      }}
      title={title ?? label}
    >
      {label}
    </span>
  );
}
