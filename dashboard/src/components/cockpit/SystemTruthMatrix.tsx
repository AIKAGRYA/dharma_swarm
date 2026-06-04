"use client";

/**
 * Zone 2: System Truth Matrix — TanStack Table replacing hand-built grid.
 * Features: column pinning, sorting, filtering, column visibility.
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

interface SystemTruthMatrixProps {
  rows: ControlSurfaceRow[];
  isLoading: boolean;
  selectedRowId: string | null;
  onSelectRow: (row: ControlSurfaceRow) => void;
  onRefresh: () => void;
  summary: ControlSurfaceSummary | null;
}

type CoherenceState = "bound" | "partial" | "drifted" | "declared_only" | "unknown";

const COHERENCE_COLORS: Record<CoherenceState, { border: string; bg: string; text: string }> = {
  bound: {
    border: `color-mix(in srgb, ${colors.rokusho} 40%, transparent)`,
    bg: `color-mix(in srgb, ${colors.rokusho} 10%, transparent)`,
    text: colors.rokusho,
  },
  partial: {
    border: `color-mix(in srgb, ${colors.kinpaku} 40%, transparent)`,
    bg: `color-mix(in srgb, ${colors.kinpaku} 10%, transparent)`,
    text: colors.kinpaku,
  },
  drifted: {
    border: `color-mix(in srgb, ${colors.bengara} 40%, transparent)`,
    bg: `color-mix(in srgb, ${colors.bengara} 10%, transparent)`,
    text: colors.bengara,
  },
  declared_only: {
    border: `color-mix(in srgb, ${colors.fuji} 40%, transparent)`,
    bg: `color-mix(in srgb, ${colors.fuji} 10%, transparent)`,
    text: colors.fuji,
  },
  unknown: {
    border: `color-mix(in srgb, ${colors.sumi[600]} 40%, transparent)`,
    bg: `color-mix(in srgb, ${colors.sumi[600]} 10%, transparent)`,
    text: colors.sumi[600],
  },
};

function coherenceStyle(state: string) {
  return COHERENCE_COLORS[state as CoherenceState] ?? COHERENCE_COLORS.unknown;
}

const PRIORITY_COLORS: Record<string, string> = {
  p0: colors.bengara,
  p1: colors.kinpaku,
  p2: colors.sumi[600],
  backlog: colors.sumi[600],
};

type FilterKey =
  | "all"
  | "live"
  | "stopped"
  | "stale"
  | "blocked"
  | "needs_john"
  | "live_unauthorized"
  | "pr_queue"
  | "vps_candidate"
  | "heavy_local_load"
  | "p0"
  | "drifted"
  | "broken_register"
  | "organs";

const FILTER_OPTIONS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "live", label: "Live" },
  { key: "stopped", label: "Stopped" },
  { key: "stale", label: "Stale" },
  { key: "blocked", label: "Blocked" },
  { key: "needs_john", label: "Needs John" },
  { key: "live_unauthorized", label: "Live But Unauthorized" },
  { key: "pr_queue", label: "PR Queue" },
  { key: "vps_candidate", label: "VPS Candidate" },
  { key: "heavy_local_load", label: "Heavy Local" },
  { key: "p0", label: "P0" },
  { key: "drifted", label: "Drifted" },
  { key: "broken_register", label: "Broken Register" },
  { key: "organs", label: "Organs" },
];

function applyPreFilter(rows: ControlSurfaceRow[], filter: FilterKey): ControlSurfaceRow[] {
  switch (filter) {
    case "live":
      return rows.filter((r) => r.observed_state === "live");
    case "stopped":
      return rows.filter((r) => r.observed_state === "stopped");
    case "stale":
      return rows.filter((r) => r.observed_state === "stale");
    case "blocked":
      return rows.filter((r) => r.observed_state === "blocked");
    case "needs_john":
      return rows.filter((r) => r.human_decision_required);
    case "live_unauthorized":
      return rows.filter(
        (r) =>
          r.observed_state === "healthy" &&
          ["authority_tier:direct_probe", "authority_tier:projection_only", "authority_tier:mirror_only"].some(
            (code) => r.gap_codes.includes(code),
          ),
      );
    case "pr_queue":
      return rows.filter((r) => r.kind === "pr_queue");
    case "vps_candidate":
      return rows.filter((r) => r.gap_codes.includes("vps_candidate"));
    case "heavy_local_load":
      return rows.filter((r) => r.gap_codes.includes("heavy_local_load"));
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
    size: 180,
    enablePinning: true,
    cell: ({ row }) => (
      <span className="font-medium text-sumi-200">{row.original.label}</span>
    ),
  },
  {
    accessorKey: "kind",
    header: "Kind",
    size: 100,
    cell: ({ row }) => (
      <code className="rounded bg-sumi-800/50 px-1.5 py-0.5 text-[10px] text-sumi-400">
        {row.original.kind}
      </code>
    ),
  },
  {
    accessorKey: "declared_state",
    header: "Declared",
    size: 120,
    cell: ({ row }) => (
      <span className="text-sumi-400">{row.original.declared_state || "—"}</span>
    ),
  },
  {
    accessorKey: "observed_state",
    header: "Observed",
    size: 120,
    cell: ({ row }) => (
      <span className="text-sumi-300">{row.original.observed_state || "—"}</span>
    ),
  },
  {
    accessorKey: "coherence_state",
    header: "Coherence",
    size: 110,
    cell: ({ row }) => {
      const cs = coherenceStyle(row.original.coherence_state);
      return (
        <span
          className="rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em]"
          style={{
            borderColor: cs.border,
            backgroundColor: cs.bg,
            color: cs.text,
          }}
        >
          {row.original.coherence_state}
        </span>
      );
    },
  },
  {
    accessorKey: "priority",
    header: "Priority",
    size: 80,
    cell: ({ row }) => (
      <span
        className="text-[10px] font-bold uppercase"
        style={{ color: PRIORITY_COLORS[row.original.priority] ?? colors.sumi[600] }}
      >
        {row.original.priority}
      </span>
    ),
  },
  {
    accessorKey: "gap_codes",
    header: "Gap",
    size: 140,
    cell: ({ row }) => (
      <span className="max-w-[140px] truncate text-sumi-400">
        {row.original.gap_codes.length > 0 ? row.original.gap_codes.join(", ") : "—"}
      </span>
    ),
  },
  {
    accessorKey: "next_action",
    header: "Next Action",
    size: 180,
    cell: ({ row }) => (
      <span className="max-w-[180px] truncate text-sumi-400">
        {row.original.next_action || "—"}
      </span>
    ),
  },
  {
    accessorKey: "evidence",
    header: "Evidence",
    size: 90,
    cell: ({ row }) => (
      <span className="text-sumi-500">
        {row.original.evidence.length > 0
          ? `${row.original.evidence.length} item${row.original.evidence.length > 1 ? "s" : ""}`
          : "—"}
      </span>
    ),
  },
  {
    accessorKey: "human_decision_required",
    header: "John",
    size: 60,
    cell: ({ row }) =>
      row.original.human_decision_required ? (
        <span
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: colors.botan }}
          title="Human decision required"
        />
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
    <div className="flex h-full flex-col bg-sumi-950/40">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-sumi-800/40 px-3 py-2">
        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-sumi-500">
          System Truth
        </div>

        {/* Summary counts */}
        {summary && (
          <div className="flex gap-1.5 text-[10px] tabular-nums">
            <span style={{ color: colors.aozora }}>{summary.total}</span>
            <span className="text-sumi-600">·</span>
            <span style={{ color: colors.rokusho }}>{summary.bound} bound</span>
            <span className="text-sumi-600">·</span>
            <span style={{ color: colors.bengara }}>{summary.drifted} drift</span>
          </div>
        )}

        <div className="flex-1" />

        {/* Search */}
        <input
          type="text"
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          placeholder="Filter..."
          className="rounded-md border border-sumi-700/40 bg-sumi-900/60 px-2 py-1 text-xs text-sumi-300 placeholder:text-sumi-600 focus:border-aozora/40 focus:outline-none"
        />

        {/* Column visibility toggle */}
        <div className="relative">
          <button
            onClick={() => setShowColumnPicker((p) => !p)}
            className="rounded-md border border-sumi-700/40 bg-sumi-900/60 p-1.5 text-sumi-500 hover:text-sumi-300"
            title="Toggle columns"
          >
            <Columns size={12} />
          </button>
          {showColumnPicker && (
            <div className="absolute right-0 top-full z-20 mt-1 rounded-lg border border-sumi-700/40 bg-sumi-900 p-2 shadow-lg">
              {table.getAllLeafColumns().map((column) => (
                <label
                  key={column.id}
                  className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-[10px] text-sumi-400 hover:bg-sumi-800/50"
                >
                  <input
                    type="checkbox"
                    checked={column.getIsVisible()}
                    onChange={column.getToggleVisibilityHandler()}
                    className="accent-aozora"
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
          className="rounded-md border border-sumi-700/40 bg-sumi-900/60 p-1.5 text-sumi-500 hover:text-aozora"
          title="Refresh"
        >
          <RefreshCw size={12} />
        </button>
      </div>

      {/* Pre-filter tabs */}
      <div className="flex flex-wrap gap-1.5 border-b border-sumi-800/40 px-3 py-1.5">
        {FILTER_OPTIONS.map(({ key, label }) => {
          const count = applyPreFilter(rows, key).length;
          return (
            <button
              key={key}
              onClick={() => setPreFilter(key)}
              className={`rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] transition-all ${
                preFilter === key
                  ? "border-aozora/40 bg-aozora/10 text-aozora"
                  : "border-sumi-700/30 text-sumi-500 hover:text-sumi-300"
              }`}
            >
              {label} ({count})
            </button>
          );
        })}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex h-32 items-center justify-center text-sm text-sumi-500">
            Loading control surface...
          </div>
        ) : (
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 z-10">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr
                  key={headerGroup.id}
                  className="border-b border-sumi-700/40 bg-sumi-900/90 text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-500 backdrop-blur-sm"
                >
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-3 py-2.5"
                      style={{ width: header.getSize() }}
                    >
                      {header.isPlaceholder ? null : (
                        <button
                          className="flex items-center gap-1 hover:text-sumi-300"
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {header.column.getIsSorted() && (
                            <ArrowUpDown size={10} className="text-aozora" />
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
                    className="h-32 text-center text-sm text-sumi-500"
                  >
                    No rows match the current filter.
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => {
                  const selected = row.original.id === selectedRowId;
                  return (
                    <tr
                      key={row.id}
                      onClick={() => onSelectRow(row.original)}
                      className={`cursor-pointer border-b border-sumi-800/30 transition-colors ${
                        selected
                          ? "bg-aozora/5"
                          : "hover:bg-sumi-900/50"
                      }`}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-3 py-2">
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
