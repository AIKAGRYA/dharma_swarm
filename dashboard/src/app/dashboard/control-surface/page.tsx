"use client";

/**
 * OPERATOR COCKPIT — Five-zone operational control surface.
 *
 * Layout (Round 6 — persistent right-rail composition):
 *   1. NeedsJohnQueue — decision-required rows, always visible (top)
 *   2. RuntimeRail — compact 36px horizontal summary strip, always visible
 *   3. Pane (horizontal) split:
 *        LEFT: SystemTruthMatrix — TanStack Table
 *        RIGHT: EvidenceDrawer — persistent right rail (empty placeholder
 *               when no row selected; never a modal overlay)
 *   4. Freshness stamp
 */

import { useState, useMemo, useCallback } from "react";
import {
  useControlSurfaceRows,
  useControlSurfaceSummary,
} from "@/hooks/useControlSurface";
import type { ControlSurfaceRow } from "@/lib/types";
import { NeedsJohnQueue } from "@/components/cockpit/NeedsJohnQueue";
import { SystemTruthMatrix } from "@/components/cockpit/SystemTruthMatrix";
import { EvidenceDrawer } from "@/components/cockpit/EvidenceDrawer";
import { RuntimeRail } from "@/components/cockpit/RuntimeRail";
import { Pane } from "@/components/primitives/Pane";
import { colors } from "@/lib/theme";

export default function OperatorCockpitPage() {
  const { rows, isLoading, error, refetch } = useControlSurfaceRows();
  const { summary } = useControlSurfaceSummary();
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);

  const selectedRow = useMemo(
    () => rows.find((r) => r.id === selectedRowId) ?? null,
    [rows, selectedRowId],
  );

  const needsJohnRows = useMemo(
    () =>
      rows
        .filter((r) => r.human_decision_required)
        .sort((a, b) => {
          const pOrder: Record<string, number> = { p0: 0, p1: 1, p2: 2, backlog: 3 };
          return (pOrder[a.priority] ?? 4) - (pOrder[b.priority] ?? 4);
        }),
    [rows],
  );

  const handleSelectRow = useCallback((row: ControlSurfaceRow) => {
    setSelectedRowId((prev) => (prev === row.id ? null : row.id));
  }, []);

  if (error) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-bengara">
        Control surface unavailable: {String(error)}
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-3">
      {/* Zone 1: Needs John Queue */}
      <NeedsJohnQueue
        rows={needsJohnRows}
        totalCount={summary?.human_decision_required_count ?? 0}
        selectedRowId={selectedRowId}
        onSelectRow={handleSelectRow}
        isLoading={isLoading}
      />

      {/* Zone 5: Runtime Rail — compact horizontal strip, always visible */}
      <div className="shrink-0">
        <RuntimeRail summary={summary} isLoading={isLoading} onRefresh={refetch} />
      </div>

      {/* Zones 2 + 3: SystemTruthMatrix (left) | EvidenceDrawer (right) — persistent Pane */}
      <div
        className="flex-1 overflow-hidden"
        style={{ border: `1px solid ${colors.sumi[700]}` }}
      >
        <Pane
          direction="horizontal"
          storageKey="control-surface-evidence"
          primaryDefaultSize={62}
          primaryMinSize={40}
          secondaryMinSize={25}
          primary={
            <SystemTruthMatrix
              rows={rows}
              isLoading={isLoading}
              selectedRowId={selectedRowId}
              onSelectRow={handleSelectRow}
              onRefresh={refetch}
              summary={summary}
            />
          }
          secondary={
            <EvidenceDrawer
              row={selectedRow}
              onClose={() => setSelectedRowId(null)}
            />
          }
        />
      </div>

      {/* Freshness stamp */}
      {summary?.generated_at && (
        <div
          className="font-mono text-[10px] tabular-nums"
          style={{ color: colors.sumi[600], letterSpacing: "0.06em" }}
        >
          Generated {summary.generated_at} · Sources:{" "}
          {summary.sources_consulted.join(", ")}
        </div>
      )}
    </div>
  );
}
