"use client";

/**
 * OPERATOR COCKPIT -- Five-zone operational control surface.
 *
 * Zones:
 *  1. Needs John Queue — decision-required rows, always visible
 *  2. System Truth Matrix — TanStack Table with column pinning
 *  3. Evidence Drawer — structured provenance for selected row
 *  4. Agent Handoff Panel — scoped prompt generation (stub)
 *  5. Runtime Rail — live health, freshness, CI status
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
import { OpsRunbookPanel } from "@/components/cockpit/OpsRunbookPanel";
import { DsGoalMissionCardsPanel } from "@/components/cockpit/DsGoalMissionCardsPanel";
import { AgentOpsWorkPacketCardsPanel } from "@/components/cockpit/AgentOpsWorkPacketCardsPanel";
import { A2ASendCardsPanel } from "@/components/cockpit/A2ASendCardsPanel";
import { SemanticReceiptCardsPanel } from "@/components/cockpit/SemanticReceiptCardsPanel";

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
      {/* Zone 1: Needs John Queue — always visible top bar */}
      <NeedsJohnQueue
        rows={needsJohnRows}
        totalCount={summary?.human_decision_required_count ?? 0}
        selectedRowId={selectedRowId}
        onSelectRow={handleSelectRow}
        isLoading={isLoading}
      />

      <OpsRunbookPanel rows={rows} selectedRow={selectedRow} />
      <DsGoalMissionCardsPanel />
      <AgentOpsWorkPacketCardsPanel />
      <A2ASendCardsPanel />
      <SemanticReceiptCardsPanel />

      {/* Zones 2-5: Split layout */}
      <div className="flex flex-1 gap-0 overflow-hidden rounded-xl border border-sumi-700/30">
        {/* Left: System Truth Matrix */}
        <div className={`flex-1 overflow-hidden transition-all ${selectedRow ? "basis-[55%]" : "basis-full"}`}>
          <SystemTruthMatrix
            rows={rows}
            isLoading={isLoading}
            selectedRowId={selectedRowId}
            onSelectRow={handleSelectRow}
            onRefresh={refetch}
            summary={summary}
          />
        </div>

        {/* Right: Evidence Drawer + Runtime Rail (visible when a row is selected) */}
        {selectedRow && (
          <div className="flex basis-[45%] flex-col border-l border-sumi-800/40">
            {/* Evidence Drawer — top portion */}
            <div className="flex-1 overflow-hidden border-b border-sumi-800/40">
              <EvidenceDrawer
                row={selectedRow}
                onClose={() => setSelectedRowId(null)}
              />
            </div>
            {/* Runtime Rail — bottom portion */}
            <div className="h-[200px] shrink-0">
              <RuntimeRail
                summary={summary}
                isLoading={isLoading}
                onRefresh={refetch}
              />
            </div>
          </div>
        )}
      </div>

      {/* Freshness stamp */}
      {summary?.generated_at && (
        <div className="text-[10px] text-sumi-600">
          Generated {summary.generated_at} · Sources:{" "}
          {summary.sources_consulted.join(", ")}
        </div>
      )}
    </div>
  );
}
