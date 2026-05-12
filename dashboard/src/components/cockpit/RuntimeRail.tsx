"use client";

/**
 * Zone 5: Runtime Rail — live health, freshness, summary stats.
 * Shows system health indicators and provides refresh controls.
 */

import { RefreshCw, Activity, CheckCircle, AlertTriangle } from "lucide-react";
import type { ControlSurfaceSummary } from "@/lib/types";
import { colors } from "@/lib/theme";

interface RuntimeRailProps {
  summary: ControlSurfaceSummary | null;
  isLoading: boolean;
  onRefresh: () => void;
}

function StatRow({
  label,
  value,
  color,
}: {
  label: string;
  value: number | string;
  color?: string;
}) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-[10px] text-sumi-500">{label}</span>
      <span
        className="text-xs font-semibold tabular-nums"
        style={{ color: color ?? colors.sumi[600] }}
      >
        {value}
      </span>
    </div>
  );
}

export function RuntimeRail({ summary, isLoading, onRefresh }: RuntimeRailProps) {
  return (
    <div className="flex h-full flex-col bg-sumi-950/60">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-sumi-800/40 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Activity size={12} className="text-aozora" />
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-sumi-500">
            Runtime
          </span>
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="rounded-md p-1 text-sumi-500 hover:text-aozora disabled:opacity-50"
          title="Refresh"
        >
          <RefreshCw size={12} className={isLoading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Stats */}
      <div className="flex-1 overflow-auto px-4 py-3">
        {!summary ? (
          <div className="text-[10px] text-sumi-500">Awaiting data...</div>
        ) : (
          <div className="space-y-1">
            <StatRow label="Total Surfaces" value={summary.total} color={colors.aozora} />
            <StatRow label="Bound" value={summary.bound} color={colors.rokusho} />
            <StatRow label="Partial" value={summary.partial} color={colors.kinpaku} />
            <StatRow label="Drifted" value={summary.drifted} color={colors.bengara} />
            <StatRow label="Declared Only" value={summary.declared_only} color={colors.fuji} />
            <StatRow label="Unknown" value={summary.unknown} />

            <div className="my-2 border-t border-sumi-800/30" />

            <StatRow
              label="Needs John"
              value={summary.human_decision_required_count}
              color={colors.botan}
            />
            <StatRow label="P0" value={summary.p0_count} color={colors.bengara} />
            <StatRow label="P1" value={summary.p1_count} color={colors.kinpaku} />

            <div className="my-2 border-t border-sumi-800/30" />

            {/* Health indicator */}
            <div className="flex items-center gap-2 py-1">
              {summary.drifted === 0 && summary.human_decision_required_count === 0 ? (
                <>
                  <CheckCircle size={12} className="text-rokusho" />
                  <span className="text-[10px] text-rokusho">All surfaces coherent</span>
                </>
              ) : (
                <>
                  <AlertTriangle size={12} style={{ color: colors.kinpaku }} />
                  <span className="text-[10px]" style={{ color: colors.kinpaku }}>
                    {summary.drifted} drifted, {summary.human_decision_required_count} need attention
                  </span>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
