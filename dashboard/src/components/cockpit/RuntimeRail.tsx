"use client";

/**
 * Runtime Rail — compact horizontal summary strip.
 *
 * Refactored Round 7: vertical right-rail → horizontal top strip.
 * Per command-plane-phase-1 contract criterion #8: "Compact summary strip on
 * /dashboard/control-surface shows simultaneously: active-track health,
 * dirty/drifted count, agents (needs-john), anomaly (P0) count — visible
 * without route-hopping."
 *
 * Consumes Nihonga primitives (Numeral / Glyph / StatusBadge). No vertical
 * stat-row chrome — numerals are the protagonist, labels are tertiary
 * sumi-600 mono uppercase.
 */

import type { ControlSurfaceSummary } from "@/lib/types";
import { colors } from "@/lib/theme";
import { Glyph } from "@/components/primitives/Glyph";
import { Numeral, type NumeralTone } from "@/components/primitives/Numeral";
import { StatusBadge, type StatusBadgeState } from "@/components/primitives/StatusBadge";

interface RuntimeRailProps {
  summary: ControlSurfaceSummary | null;
  isLoading: boolean;
  onRefresh: () => void;
}

/** Compact metric: small uppercase mono label + Numeral protagonist. */
function Metric({
  label,
  value,
  tone = "rest",
  unit,
  title,
}: {
  label: string;
  value: number;
  tone?: NumeralTone;
  unit?: string;
  title?: string;
}) {
  return (
    <span
      className="flex items-baseline gap-1.5"
      title={title}
    >
      <span
        className="font-mono text-xs uppercase tracking-widest"
        style={{ color: colors.sumi[600], letterSpacing: "0.10em" }}
      >
        {label}
      </span>
      <Numeral value={value} tone={tone} size="md" unit={unit} />
    </span>
  );
}

export function RuntimeRail({ summary, isLoading, onRefresh }: RuntimeRailProps) {
  if (isLoading || !summary) {
    return (
      <div
        className="flex items-center justify-between px-3"
        style={{
          height: 36,
          backgroundColor: colors.sumi[900],
          borderBottom: `1px solid ${colors.sumi[700]}`,
          color: colors.sumi[600],
        }}
      >
        <span className="font-mono text-xs uppercase tracking-widest">
          RUNTIME · LOADING
        </span>
      </div>
    );
  }

  const needsJohn = summary.human_decision_required_count;
  const drifted = summary.drifted;
  const p0 = summary.p0_count;

  // Overall health: all-clear if 0 drifted AND 0 needs-john AND 0 p0.
  const healthState: StatusBadgeState =
    p0 > 0
      ? "fail"
      : drifted > 0 || needsJohn > 0
      ? "stale"
      : "pass";

  return (
    <div
      className="flex items-center justify-between px-3"
      style={{
        height: 36,
        backgroundColor: colors.sumi[900],
        borderBottom: `1px solid ${colors.sumi[700]}`,
      }}
    >
      {/* Left cluster — overall health + total surfaces */}
      <div className="flex items-center gap-4">
        <StatusBadge
          state={healthState}
          title={
            healthState === "pass"
              ? "All surfaces coherent"
              : `${drifted} drifted, ${needsJohn} need attention, ${p0} p0`
          }
        />
        <Metric
          label="SURFACES"
          value={summary.total}
          tone="active"
          title="Total surfaces tracked"
        />
        <Metric
          label="BOUND"
          value={summary.bound}
          tone="ok"
          title="Surfaces in bound coherence state"
        />
      </div>

      {/* Middle cluster — drift / attention */}
      <div className="flex items-center gap-4">
        <Metric
          label="DRIFT"
          value={drifted}
          tone={drifted > 0 ? "warn" : "muted"}
          title={`${drifted} drifted surfaces`}
        />
        <Metric
          label="STALE"
          value={summary.partial}
          tone="warn"
          title="Partial / aged surfaces"
        />
        <Metric
          label="NEEDS JOHN"
          value={needsJohn}
          tone={needsJohn > 0 ? "active" : "muted"}
          title={`${needsJohn} surfaces requiring decision`}
        />
        <Metric
          label="P0"
          value={p0}
          tone={p0 > 0 ? "fail" : "muted"}
          title={`${p0} priority-0 surfaces`}
        />
      </div>

      {/* Right cluster — fresh pulse + refresh */}
      <div className="flex items-center gap-3">
        <Glyph
          kind="dot"
          tone={isLoading ? "muted" : "ok"}
          pulse={!isLoading}
          title="Cadence: refresh active"
        />
        <button
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
          className="font-mono text-xs uppercase tracking-widest disabled:opacity-50"
          style={{
            color: colors.sumi[600],
            letterSpacing: "0.10em",
            transition: "color 100ms cubic-bezier(0.2, 0, 0, 1)",
          }}
          title="Refresh control-surface rows"
        >
          REFRESH
        </button>
      </div>
    </div>
  );
}
