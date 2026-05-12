"use client";

/**
 * Zone 1: Needs John Queue — decision-required rows, always visible.
 * Sorted by priority/freshness, each item shows: why now, evidence count,
 * recommended action, and a select button.
 */

import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, ChevronRight, User } from "lucide-react";
import type { ControlSurfaceRow } from "@/lib/types";
import { colors } from "@/lib/theme";

interface NeedsJohnQueueProps {
  rows: ControlSurfaceRow[];
  totalCount: number;
  selectedRowId: string | null;
  onSelectRow: (row: ControlSurfaceRow) => void;
  isLoading: boolean;
}

const PRIORITY_ACCENT: Record<string, string> = {
  p0: colors.bengara,
  p1: colors.kinpaku,
  p2: colors.sumi[600],
  backlog: colors.sumi[600],
};

function priorityAccent(p: string): string {
  return PRIORITY_ACCENT[p] ?? colors.sumi[600];
}

export function NeedsJohnQueue({
  rows,
  totalCount,
  selectedRowId,
  onSelectRow,
  isLoading,
}: NeedsJohnQueueProps) {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-sumi-700/30 bg-sumi-900/50 px-4 py-3">
        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-sumi-500">
          Loading queue...
        </div>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-sumi-700/30 bg-sumi-900/50 px-4 py-3">
        <div className="flex items-center gap-2">
          <User size={14} className="text-rokusho" />
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-rokusho">
            Needs John
          </span>
          <span className="text-xs text-sumi-500">— Nothing requires attention</span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-botan/20 bg-sumi-900/50">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-sumi-800/40 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <AlertTriangle size={14} style={{ color: colors.botan }} />
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: colors.botan }}>
            Needs John
          </span>
          <span
            className="rounded-full px-2 py-0.5 text-[10px] font-bold tabular-nums"
            style={{
              backgroundColor: `color-mix(in srgb, ${colors.botan} 15%, transparent)`,
              color: colors.botan,
            }}
          >
            {totalCount}
          </span>
        </div>
        <span className="text-[10px] text-sumi-500">
          sorted by priority
        </span>
      </div>

      {/* Queue items — horizontal scrollable on overflow */}
      <div className="flex gap-2 overflow-x-auto p-3">
        <AnimatePresence mode="popLayout">
          {rows.map((row) => {
            const selected = row.id === selectedRowId;
            const accent = priorityAccent(row.priority);

            return (
              <motion.button
                key={row.id}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                onClick={() => onSelectRow(row)}
                className={`group flex min-w-[220px] max-w-[300px] shrink-0 flex-col gap-1.5 rounded-lg border px-3 py-2.5 text-left transition-all ${
                  selected
                    ? "ring-1 ring-current"
                    : "hover:border-sumi-600/50"
                }`}
                style={{
                  borderColor: selected
                    ? accent
                    : `color-mix(in srgb, ${colors.sumi[700]} 50%, transparent)`,
                  backgroundColor: selected
                    ? `color-mix(in srgb, ${accent} 8%, transparent)`
                    : `color-mix(in srgb, ${colors.sumi[900]} 60%, transparent)`,
                }}
              >
                {/* Row label + priority */}
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-medium text-sumi-200 line-clamp-1">
                    {row.label}
                  </span>
                  <span
                    className="shrink-0 text-[10px] font-bold uppercase"
                    style={{ color: accent }}
                  >
                    {row.priority}
                  </span>
                </div>

                {/* Why now: coherence state + gap codes */}
                <div className="text-[10px] text-sumi-400 line-clamp-1">
                  {row.coherence_state !== "bound" && (
                    <span className="mr-1 capitalize">{row.coherence_state}</span>
                  )}
                  {row.gap_codes.length > 0 && (
                    <span>· {row.gap_codes.join(", ")}</span>
                  )}
                </div>

                {/* Bottom: evidence count + next action */}
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] text-sumi-500">
                    {row.evidence.length > 0
                      ? `${row.evidence.length} evidence`
                      : "no evidence"}
                  </span>
                  <div className="flex items-center gap-0.5 text-[10px] text-sumi-500 group-hover:text-aozora">
                    <span className="max-w-[100px] truncate">
                      {row.next_action || "inspect"}
                    </span>
                    <ChevronRight size={10} />
                  </div>
                </div>
              </motion.button>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
