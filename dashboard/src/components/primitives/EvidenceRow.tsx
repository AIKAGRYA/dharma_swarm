"use client";

/**
 * EvidenceRow — dense row primitive.
 *
 * Per docs/plans/2026-05-21-command-plane-design-lock.md:
 *   "Row height 24-28px when dense. 8px h-padding. Tabular figures.
 *    Hairline 1px borders, NO drop shadows, NO floating cards."
 *
 * The atomic row used by NeedsJohnQueue, EvidenceDrawer, and any list
 * surface that values density over breathing room. Renders a flex row
 * with optional left status indicator, label, ReactNode value column,
 * trailing meta, and click-to-select chrome.
 */

import type { MouseEvent, ReactNode } from "react";
import { colors } from "@/lib/theme";

export type EvidenceRowDensity = "dense" | "medium";

interface EvidenceRowProps {
  /** Unique row id (for selection tracking). */
  id: string;
  /** Left content — typically a Glyph or StatusBadge. */
  leading?: ReactNode;
  /** Primary label text. */
  label: ReactNode;
  /** Secondary detail (shown after label, muted). */
  detail?: ReactNode;
  /** Right-aligned value — typically a Numeral. */
  value?: ReactNode;
  /** Trailing meta (shown after value, muted). */
  meta?: ReactNode;
  /** Density: dense (24px row) or medium (28px row). Defaults to dense. */
  density?: EvidenceRowDensity;
  /** Selected state — toggles accent border. */
  selected?: boolean;
  /** Click handler. */
  onClick?: (event: MouseEvent<HTMLDivElement>) => void;
  /** Optional className passthrough. */
  className?: string;
  /** Optional title for hover tooltip. */
  title?: string;
}

const DENSITY_HEIGHT: Record<EvidenceRowDensity, string> = {
  dense: "24px",
  medium: "28px",
};

export function EvidenceRow({
  id,
  leading,
  label,
  detail,
  value,
  meta,
  density = "dense",
  selected = false,
  onClick,
  className,
  title,
}: EvidenceRowProps) {
  const height = DENSITY_HEIGHT[density];
  const borderColor = selected ? colors.aozora : colors.sumi[700];

  return (
    <div
      data-row-id={id}
      onClick={onClick}
      className={`flex items-center gap-2 px-2 ${onClick ? "cursor-pointer" : ""} ${className ?? ""}`}
      style={{
        height,
        borderBottom: `1px solid ${borderColor}`,
        backgroundColor: selected
          ? `color-mix(in srgb, ${colors.aozora} 6%, transparent)`
          : "transparent",
        color: colors.torinoko,
        lineHeight: 1.2,
        transition: "background-color 100ms cubic-bezier(0.2, 0, 0, 1)",
      }}
      title={title}
    >
      {leading ? (
        <span className="flex shrink-0 items-center" style={{ width: 16 }}>
          {leading}
        </span>
      ) : null}

      <span
        className="truncate text-sm"
        style={{ color: colors.torinoko, opacity: 0.92 }}
      >
        {label}
      </span>

      {detail ? (
        <span
          className="truncate text-xs"
          style={{ color: colors.sumi[600] }}
        >
          {detail}
        </span>
      ) : null}

      <span className="ml-auto flex shrink-0 items-center gap-2">
        {value}
        {meta ? (
          <span className="text-xs" style={{ color: colors.sumi[600] }}>
            {meta}
          </span>
        ) : null}
      </span>
    </div>
  );
}
