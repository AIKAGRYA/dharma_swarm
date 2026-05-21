"use client";

/**
 * ZoneFrame — positioning frame for the 7-zone verb taxonomy.
 *
 * Per docs/plans/2026-05-21-command-plane-design-lock.md §IA:
 *   "Hexagonal 1+6 spatial frame as positioning frame only — never
 *    render the hex outline. The negative space between zones carries
 *    the design."
 *
 * Each zone shares the GRAMMAR (verb + accent + signal) but NOT chrome.
 * Holds verb-appropriate content via children. Renders a hairline-bordered
 * region with verb label top-left and accent dot top-right.
 */

import type { ReactNode } from "react";
import { colors } from "@/lib/theme";

export type ZoneVerb =
  | "operate"   // COCKPIT  — Gunjō azurite
  | "converse"  // TALK     — Rokushō malachite
  | "observe"   // WATCH    — Gofun (no accent; restraint)
  | "evaluate"  // JUDGE    — Ōdo ochre
  | "relate"    // MAP      — Murasaki gentian
  | "sense"     // SENSE    — Bengara iron oxide
  | "recall";   // REMEMBER — Sumi-on-Gofun

const VERB_ACCENT: Record<ZoneVerb, string> = {
  operate: colors.aozora,
  converse: colors.rokusho,
  observe: colors.torinoko, // restraint — no chromatic accent
  evaluate: colors.kinpaku,
  relate: colors.botan,
  sense: colors.bengara,
  recall: colors.sumi[600],
};

const VERB_ZONE_LABEL: Record<ZoneVerb, string> = {
  operate: "COCKPIT",
  converse: "TALK",
  observe: "WATCH",
  evaluate: "JUDGE",
  relate: "MAP",
  sense: "SENSE",
  recall: "REMEMBER",
};

interface ZoneFrameProps {
  /** Verb the zone embodies. */
  verb: ZoneVerb;
  /** Zone content. */
  children: ReactNode;
  /** Optional override label; defaults to canonical verb label. */
  label?: string;
  /** Pulse the accent dot at the ambient cadence (1s linear). Used to
   *  signal fresh activity in this zone. */
  pulse?: boolean;
  /** Optional className passthrough. */
  className?: string;
}

export function ZoneFrame({
  verb,
  children,
  label,
  pulse = false,
  className,
}: ZoneFrameProps) {
  const accent = VERB_ACCENT[verb];
  const displayLabel = label ?? VERB_ZONE_LABEL[verb];

  return (
    <section
      data-zone-verb={verb}
      className={`relative flex flex-col ${className ?? ""}`}
      style={{
        border: `1px solid ${colors.sumi[700]}`,
        backgroundColor: colors.sumi[900],
        color: colors.torinoko,
      }}
    >
      {/* Top bar: verb label (left) + accent dot (right). Always hairline. */}
      <div
        className="flex items-center justify-between border-b px-3"
        style={{
          height: 28,
          borderBottomColor: colors.sumi[700],
          backgroundColor: colors.sumi[850],
        }}
      >
        <span
          className="font-mono text-xs uppercase tracking-widest"
          style={{
            color: colors.sumi[600],
            letterSpacing: "0.12em",
          }}
        >
          {displayLabel}
        </span>
        <span
          className="inline-block"
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            backgroundColor: accent,
            animation: pulse
              ? "ambient-pulse 1000ms linear infinite"
              : undefined,
          }}
          aria-hidden="true"
        />
      </div>

      {/* Body — verb-appropriate chrome lives here. */}
      <div className="flex-1 overflow-auto">{children}</div>
    </section>
  );
}
