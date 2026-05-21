"use client";

/**
 * Pane — resizable pane primitive wrapping react-resizable-panels.
 *
 * Used for cockpit split-views (e.g. table + persistent evidence drawer).
 * Exposes only the most common 2-pane pattern; extend if 3+ pane layouts
 * become real.
 */

import type { ReactNode } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";
import { colors } from "@/lib/theme";

export type PaneDirection = "horizontal" | "vertical";

interface PaneProps {
  /** Split direction. */
  direction: PaneDirection;
  /** Storage key — persists pane sizes across reloads. */
  storageKey?: string;
  /** Primary pane content. */
  primary: ReactNode;
  /** Secondary pane content. */
  secondary: ReactNode;
  /** Primary pane default size (percent). Defaults to 70. */
  primaryDefaultSize?: number;
  /** Primary pane min size (percent). Defaults to 40. */
  primaryMinSize?: number;
  /** Secondary pane min size (percent). Defaults to 20. */
  secondaryMinSize?: number;
  /** Optional className passthrough on the outer Group. */
  className?: string;
}

type PaneLayout = Record<"primary" | "secondary", number>;

function loadLayout(storageKey: string | undefined): PaneLayout | undefined {
  if (!storageKey || typeof window === "undefined") {
    return undefined;
  }
  try {
    const stored = window.localStorage.getItem(`dharma-pane:${storageKey}`);
    if (!stored) {
      return undefined;
    }
    const parsed = JSON.parse(stored) as Partial<PaneLayout>;
    if (
      typeof parsed.primary === "number" &&
      typeof parsed.secondary === "number"
    ) {
      return { primary: parsed.primary, secondary: parsed.secondary };
    }
  } catch {
    return undefined;
  }
  return undefined;
}

function saveLayout(storageKey: string | undefined, layout: Record<string, number>) {
  if (!storageKey || typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(`dharma-pane:${storageKey}`, JSON.stringify(layout));
}

export function Pane({
  direction,
  storageKey,
  primary,
  secondary,
  primaryDefaultSize = 70,
  primaryMinSize = 40,
  secondaryMinSize = 20,
  className,
}: PaneProps) {
  const defaultLayout = loadLayout(storageKey) ?? {
    primary: primaryDefaultSize,
    secondary: 100 - primaryDefaultSize,
  };

  return (
    <Group
      id={storageKey ?? `dharma-pane-${direction}`}
      orientation={direction}
      defaultLayout={defaultLayout}
      onLayoutChanged={(layout) => saveLayout(storageKey, layout)}
      className={`h-full w-full ${className ?? ""}`}
    >
      <Panel id="primary" minSize={`${primaryMinSize}%`}>
        {primary}
      </Panel>
      <Separator
        className={
          direction === "horizontal"
            ? "w-px transition-colors"
            : "h-px transition-colors"
        }
        style={{ backgroundColor: colors.sumi[700] }}
      />
      <Panel id="secondary" minSize={`${secondaryMinSize}%`}>
        {secondary}
      </Panel>
    </Group>
  );
}
