"use client";

/**
 * Zone 2: System Truth Matrix — TanStack Table refactored to primitives
 * (Round 5b). Cell renderers swap to <StatusBadge>, <Numeral>, <Glyph>;
 * dense 26px rows; 8px horizontal padding; tabular figures.
 *
 * Per docs/plans/2026-05-21-command-plane-design-lock.md:
 *   "Row height 24-28px when dense. 8px h-padding. Tabular figures."
 */

import { useMemo, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type ColumnFiltersState,
  type VisibilityState,
} from "@tanstack/react-table";
import { ArrowUpDown, RefreshCw, Columns } from "lucide-react";
import type { ControlSurfaceRow, ControlSurfaceSummary } from "@/lib/types";
import { colors } from "@/lib/theme";
import { StatusBadge, type StatusBadgeState } from "@/components/primitives/StatusBadge";
import { Numeral } from "@/components/primitives/Numeral";
import { Glyph } from "@/components/primitives/Glyph";

interface SystemTruthMatrixProps {
  rows: ControlSurfaceRow[];
  isLoading: boolean;
  selectedRowId: string | null;
  onSelectRow: (row: ControlSurfaceRow) => void;
  onRefresh: () => void;
  summary: ControlSurfaceSummary | null;
}

/** Coherence state -> StatusBadge state. 5→4 lossy mapping; title preserves original. */
const COHERENCE_BADGE: Record<string, StatusBadgeState> = {
  bound: "pass",
  partial: "stale",
  drifted: "drift",
  declared_only: "drift",
  unknown: "drift",
};

/** Priority -> StatusBadge state. Same mapping NeedsJohnQueue uses. */
const PRIORITY_BADGE: Record<string, StatusBadgeState> = {
  p0: "fail",
  p1: "stale",
  p2: "drift",
  backlog: "drift",
};

function coherenceBadgeState(state: string): StatusBadgeState {
  return COHERENCE_BADGE[state] ?? "drift";
}

function priorityBadgeState(p: string): StatusBadgeState {
  return PRIORITY_BADGE[p] ?? "drift";
}

type FilterKey = "all" | "needs_john" | "p0" | "drifted" | "broken_register" | "organs";

const FILTER_OPTIONS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "needs_john", label: "Needs John" },
  { key: "p0", label: "P0" },
  { key: "drifted", label: "Drifted" },
  { key: "broken_register", label: "Broken Register" },
  { key: "organs", label: "Organs" },
];

function applyPreFilter(rows: ControlSurfaceRow[], filter: FilterKey): ControlSurfaceRow[] {
  switch (filter) {
    case "needs_john":
      return rows.filter((r) => r.human_decision_required);
    case "p0":
      return rows.filter((r) => r.priority === "p0");
    case "drifted":
      return rows.filter((r) => r.coherence_state === "drifted");
    case "broken_register":
      return rows.filter((r) => r.kind === "broken_register");
    case "organs":
      return rows.filter((r) => r.kind === "organ");
    default:
      return rows;
  }
}

const columns: ColumnDef<ControlSurfaceRow>[] = [
  {
    accessorKey: "label",
    header: "Entity",
    size: 200,
    enablePinning: true,
    cell: ({ row }) => (
      <span
        className="truncate text-sm"
        style={{ color: colors.torinoko, opacity: 0.92 }}
      >
        {row.original.label}
      </span>
    ),
  },
  {
    accessorKey: "kind",
    header: "Kind",
    size: 100,
    cell: ({ row }) => (
      <code
        className="rounded px-1.5 py-0.5 text-[10px] font-mono"
        style={{
          backgroundColor: `color-mix(in srgb, ${colors.sumi[800]} 60%, transparent)`,
          color: colors.sumi[600],
        }}
      >
        {row.original.kind}
      </code>
    ),
  },
  {
    accessorKey: "declared_state",
    header: "Declared",
    size: 110,
    cell: ({ row }) => (
      <span className="truncate text-xs" style={{ color: colors.sumi[600] }}>
        {row.original.declared_state || "—"}
      </span>
    ),
  },
  {
    accessorKey: "observed_state",
    header: "Observed",
    size: 110,
    cell: ({ row }) => (
      <span className="truncate text-xs" style={{ color: colors.torinoko, opacity: 0.92 }}>
        {row.original.observed_state || "—"}
      </span>
    ),
  },
  {
    accessorKey: "coherence_state",
    header: "Coherence",
    size: 100,
    cell: ({ row }) => (
      <StatusBadge
        state={coherenceBadgeState(row.original.coherence_state)}
        title={row.original.coherence_state}
      />
    ),
  },
  {
    accessorKey: "priority",
    header: "Priority",
    size: 90,
    cell: ({ row }) => (
      <StatusBadge
        state={priorityBadgeState(row.original.priority)}
        title={row.original.priority.toUpperCase()}
      />
    ),
  },
  {
    accessorKey: "gap_codes",
    header: "Gap",
    size: 140,
    cell: ({ row }) => (
      <span
        className="max-w-[140px] truncate text-xs"
        style={{ color: colors.sumi[600] }}
      >
        {row.original.gap_codes.length > 0 ? row.original.gap_codes.join(", ") : "—"}
      </span>
    ),
  },
  {
    accessorKey: "next_action",
    header: "Next Action",
    size: 180,
    cell: ({ row }) => (
      <span
        className="max-w-[180px] truncate text-xs"
        style={{ color: colors.torinoko, opacity: 0.85 }}
      >
        {row.original.next_action || "—"}
      </span>
    ),
  },
  {
    accessorKey: "evidence",
    header: "Evidence",
    size: 90,
    cell: ({ row }) => {
      const n = row.original.evidence.length;
      if (n === 0) {
        return (
          <span className="text-xs" style={{ color: colors.sumi[600] }}>
            —
          </span>
        );
      }
      return (
        <Numeral
          value={n}
          tone={n > 0 ? "rest" : "muted"}
          size="sm"
          unit={n === 1 ? "item" : "items"}
        />
      );
    },
  },
  {
    accessorKey: "human_decision_required",
    header: "John",
    size: 50,
    cell: ({ row }) =>
      row.original.human_decision_required ? (
        <Glyph kind="dot" tone="active" title="Human decision required" />
      ) : null,
  },
];

export function SystemTruthMatrix({
  rows,
  isLoading,
  selectedRowId,
  onSelectRow,
  onRefresh,
  summary,
}: SystemTruthMatrixProps) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [preFilter, setPreFilter] = useState<FilterKey>("all");
  const [showColumnPicker, setShowColumnPicker] = useState(false);
  const [globalFilter, setGlobalFilter] = useState("");

  const filteredData = useMemo(
    () => applyPreFilter(rows, preFilter),
    [rows, preFilter],
  );

  const table = useReactTable({
    data: filteredData,
    columns,
    state: { sorting, columnFilters, columnVisibility, globalFilter },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    columnResizeMode: "onChange",
  });

  return (
    <div className="flex h-full flex-col" style={{ backgroundColor: colors.sumi[950] }}>
      {/* Toolbar — compact 28px strip */}
      <div
        className="flex flex-wrap items-center gap-2 px-2"
        style={{
          height: 28,
          borderBottom: `1px solid ${colors.sumi[700]}`,
          backgroundColor: colors.sumi[850],
        }}
      >
        <span
          className="font-mono text-xs uppercase"
          style={{ color: colors.sumi[600], letterSpacing: "0.12em" }}
        >
          SYSTEM TRUTH
        </span>

        {/* Summary counts — Numerals are protagonist */}
        {summary && (
          <div className="flex items-center gap-1.5">
            <Numeral value={summary.total} tone="active" size="md" />
            <span className="text-xs" style={{ color: colors.sumi[700] }}>·</span>
            <Numeral value={summary.bound} tone="ok" size="sm" unit="bound" />
            <span className="text-xs" style={{ color: colors.sumi[700] }}>·</span>
            <Numeral value={summary.drifted} tone="warn" size="sm" unit="drift" />
          </div>
        )}

        <div className="flex-1" />

        {/* Search */}
        <input
          type="text"
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          placeholder="Filter..."
          className="font-mono text-xs focus:outline-none"
          style={{
            backgroundColor: colors.sumi[900],
            color: colors.torinoko,
            border: `1px solid ${colors.sumi[700]}`,
            padding: "2px 6px",
            height: 20,
          }}
        />

        {/* Column visibility toggle */}
        <div className="relative">
          <button
            onClick={() => setShowColumnPicker((p) => !p)}
            className="flex items-center justify-center"
            style={{
              width: 20,
              height: 20,
              border: `1px solid ${colors.sumi[700]}`,
              backgroundColor: colors.sumi[900],
              color: colors.sumi[600],
            }}
            title="Toggle columns"
          >
            <Columns size={11} />
          </button>
          {showColumnPicker && (
            <div
              className="absolute right-0 top-full z-20 mt-1 p-2"
              style={{
                backgroundColor: colors.sumi[900],
                border: `1px solid ${colors.sumi[700]}`,
              }}
            >
              {table.getAllLeafColumns().map((column) => (
                <label
                  key={column.id}
                  className="flex cursor-pointer items-center gap-2 px-2 py-1 text-[10px]"
                  style={{ color: colors.sumi[600] }}
                >
                  <input
                    type="checkbox"
                    checked={column.getIsVisible()}
                    onChange={column.getToggleVisibilityHandler()}
                    style={{ accentColor: colors.aozora }}
                  />
                  {typeof column.columnDef.header === "string"
                    ? column.columnDef.header
                    : column.id}
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Refresh */}
        <button
          onClick={onRefresh}
          className="flex items-center justify-center"
          style={{
            width: 20,
            height: 20,
            border: `1px solid ${colors.sumi[700]}`,
            backgroundColor: colors.sumi[900],
            color: colors.sumi[600],
          }}
          title="Refresh"
        >
          <RefreshCw size={11} />
        </button>
      </div>

      {/* Pre-filter tabs — compact 24px strip */}
      <div
        className="flex flex-wrap items-center gap-1 px-2"
        style={{
          minHeight: 24,
          borderBottom: `1px solid ${colors.sumi[700]}`,
          backgroundColor: colors.sumi[900],
        }}
      >
        {FILTER_OPTIONS.map(({ key, label }) => {
          const count = applyPreFilter(rows, key).length;
          const active = preFilter === key;
          return (
            <button
              key={key}
              onClick={() => setPreFilter(key)}
              className="font-mono text-[10px] uppercase tabular-nums"
              style={{
                letterSpacing: "0.1em",
                padding: "2px 6px",
                border: `1px solid ${active ? colors.aozora : "transparent"}`,
                backgroundColor: active
                  ? `color-mix(in srgb, ${colors.aozora} 8%, transparent)`
                  : "transparent",
                color: active ? colors.aozora : colors.sumi[600],
                fontFeatureSettings: "'tnum' 1",
              }}
            >
              {label} ({count})
            </button>
          );
        })}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div
            className="flex h-32 items-center justify-center font-mono text-xs uppercase"
            style={{ color: colors.sumi[600], letterSpacing: "0.12em" }}
          >
            LOADING CONTROL SURFACE
          </div>
        ) : (
          <table className="w-full text-left" style={{ tableLayout: "fixed" }}>
            <thead className="sticky top-0 z-10">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr
                  key={headerGroup.id}
                  style={{
                    borderBottom: `1px solid ${colors.sumi[700]}`,
                    backgroundColor: colors.sumi[900],
                  }}
                >
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-2 font-mono text-[10px] uppercase"
                      style={{
                        width: header.getSize(),
                        height: 24,
                        color: colors.sumi[600],
                        letterSpacing: "0.12em",
                        fontWeight: 500,
                      }}
                    >
                      {header.isPlaceholder ? null : (
                        <button
                          className="flex items-center gap-1"
                          style={{ color: colors.sumi[600] }}
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {header.column.getIsSorted() && (
                            <ArrowUpDown size={9} style={{ color: colors.aozora }} />
                          )}
                        </button>
                      )}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td
                    colSpan={columns.length}
                    className="text-center font-mono text-xs uppercase"
                    style={{
                      height: 64,
                      color: colors.sumi[600],
                      letterSpacing: "0.12em",
                    }}
                  >
                    NO ROWS MATCH FILTER
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => {
                  const selected = row.original.id === selectedRowId;
                  return (
                    <tr
                      key={row.id}
                      onClick={() => onSelectRow(row.original)}
                      className="cursor-pointer"
                      style={{
                        height: 26,
                        borderBottom: `1px solid ${colors.sumi[800]}`,
                        backgroundColor: selected
                          ? `color-mix(in srgb, ${colors.aozora} 6%, transparent)`
                          : "transparent",
                        transition: "background-color 100ms cubic-bezier(0.2, 0, 0, 1)",
                      }}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td
                          key={cell.id}
                          className="px-2 tabular-nums"
                          style={{
                            fontFeatureSettings: "'tnum' 1",
                            lineHeight: 1.2,
                          }}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
