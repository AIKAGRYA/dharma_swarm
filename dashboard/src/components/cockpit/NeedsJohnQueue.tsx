"use client";

/**
 * Zone 1: Needs John Queue — decision-required rows, always visible.
 *
 * Refactored Round 5: dense vertical row list using EvidenceRow + StatusBadge
 * + Glyph + Numeral primitives. 24-28px row density. Mono-protagonist numbers
 * (priority + evidence count). No horizontal card-scroll — context density
 * over breathing room (per command-plane-phase-1 contract).
 */

import type { ControlSurfaceRow } from "@/lib/types";
import { colors } from "@/lib/theme";
import { EvidenceRow } from "@/components/primitives/EvidenceRow";
import { Glyph } from "@/components/primitives/Glyph";
import { Numeral } from "@/components/primitives/Numeral";
import { StatusBadge, type StatusBadgeState } from "@/components/primitives/StatusBadge";

interface NeedsJohnQueueProps {
  rows: ControlSurfaceRow[];
  totalCount: number;
  selectedRowId: string | null;
  onSelectRow: (row: ControlSurfaceRow) => void;
  isLoading: boolean;
}

/** Map priority -> StatusBadge state. */
const PRIORITY_BADGE: Record<string, StatusBadgeState> = {
  p0: "fail",     // alarm-only — Shu
  p1: "stale",    // attention-aged — Ōdo
  p2: "drift",    // notice — Fuji
  backlog: "drift",
};

function priorityState(p: string): StatusBadgeState {
  return PRIORITY_BADGE[p] ?? "drift";
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
      <section
        style={{
          border: `1px solid ${colors.sumi[700]}`,
          backgroundColor: colors.sumi[900],
        }}
      >
        <header
          className="flex items-center px-3"
          style={{
            height: 28,
            borderBottom: `1px solid ${colors.sumi[700]}`,
            backgroundColor: colors.sumi[850],
          }}
        >
          <span
            className="font-mono text-xs uppercase tracking-widest"
            style={{ color: colors.sumi[600], letterSpacing: "0.12em" }}
          >
            NEEDS JOHN · LOADING
          </span>
        </header>
      </section>
    );
  }

  return (
    <section
      style={{
        border: `1px solid ${colors.sumi[700]}`,
        backgroundColor: colors.sumi[900],
      }}
    >
      {/* Header strip — mono uppercase, numeral count is protagonist */}
      <header
        className="flex items-center justify-between px-3"
        style={{
          height: 28,
          borderBottom: `1px solid ${colors.sumi[700]}`,
          backgroundColor: colors.sumi[850],
        }}
      >
        <div className="flex items-center gap-3">
          <span
            className="font-mono text-xs uppercase tracking-widest"
            style={{ color: colors.sumi[600], letterSpacing: "0.12em" }}
          >
            NEEDS JOHN
          </span>
          <Numeral
            value={totalCount}
            tone={totalCount > 0 ? "active" : "muted"}
            size="md"
          />
        </div>
        <span
          className="font-mono text-xs"
          style={{ color: colors.sumi[600] }}
        >
          sorted by priority
        </span>
      </header>

      {/* Body — dense vertical row list */}
      {rows.length === 0 ? (
        <div
          className="flex items-center gap-2 px-3"
          style={{
            height: 28,
            color: colors.sumi[600],
            fontSize: "0.8125rem",
          }}
        >
          <Glyph kind="check" tone="ok" />
          <span>nothing requires attention</span>
        </div>
      ) : (
        <div>
          {rows.map((row) => {
            const selected = row.id === selectedRowId;
            const detailParts: string[] = [];
            if (row.coherence_state && row.coherence_state !== "bound") {
              detailParts.push(row.coherence_state);
            }
            if (row.gap_codes.length > 0) {
              detailParts.push(row.gap_codes.join(", "));
            }
            const detail = detailParts.length > 0 ? detailParts.join(" · ") : undefined;

            return (
              <EvidenceRow
                key={row.id}
                id={row.id}
                density="medium"
                selected={selected}
                onClick={() => onSelectRow(row)}
                leading={
                  <StatusBadge
                    state={priorityState(row.priority)}
                    title={row.priority.toUpperCase()}
                  />
                }
                label={row.label}
                detail={detail}
                value={
                  <Numeral
                    value={row.evidence.length}
                    tone={row.evidence.length > 0 ? "rest" : "muted"}
                    size="sm"
                    unit={row.evidence.length === 1 ? "evidence" : "evidence"}
                  />
                }
                meta={
                  <span className="flex items-center gap-1">
                    <span className="max-w-[140px] truncate">
                      {row.next_action || "inspect"}
                    </span>
                    <Glyph
                      kind="dot"
                      tone={selected ? "active" : "muted"}
                      pulse={selected}
                    />
                  </span>
                }
                title={row.next_action || row.label}
              />
            );
          })}
        </div>
      )}
    </section>
  );
}
