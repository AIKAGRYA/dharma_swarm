"use client";

/**
 * ACTIVE_SURFACE_MANIFEST_CONTROLPANE -- Operator cockpit grid.
 *
 * Shows declared intent (from ACTIVE_SURFACE_MANIFEST.yaml) reconciled
 * against observed reality (runtime, code, evidence adapters).
 * The manifest is declared intent, NOT the single source of truth.
 */

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  useControlSurfaceRows,
  useControlSurfaceSummary,
  type ControlSurfaceRow,
} from "@/hooks/useControlSurface";
import { colors } from "@/lib/theme";

// ---------------------------------------------------------------------------
// Animation
// ---------------------------------------------------------------------------

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.03 } },
};

const item = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0 },
};

// ---------------------------------------------------------------------------
// Badge helpers
// ---------------------------------------------------------------------------

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
  unknown: colors.sumi[600],
};

function priorityColor(p: string): string {
  return PRIORITY_COLORS[p] ?? colors.sumi[600];
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

type FilterKey = "all" | "needs_john" | "p0" | "drifted" | "broken_register" | "organs";

const FILTER_LABELS: Record<FilterKey, string> = {
  all: "All",
  needs_john: "Needs John",
  p0: "P0",
  drifted: "Drifted",
  broken_register: "Broken Register",
  organs: "Organs",
};

function applyFilter(rows: ControlSurfaceRow[], filter: FilterKey): ControlSurfaceRow[] {
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

// ---------------------------------------------------------------------------
// Summary cards
// ---------------------------------------------------------------------------

function SummaryCard({
  label,
  value,
  color,
  active,
  onClick,
}: {
  label: string;
  value: number;
  color: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-xl border px-4 py-3 text-left transition-all ${
        active ? "ring-1 ring-current" : ""
      }`}
      style={{
        borderColor: active
          ? color
          : `color-mix(in srgb, ${colors.sumi[700]} 50%, transparent)`,
        backgroundColor: active
          ? `color-mix(in srgb, ${color} 8%, transparent)`
          : `color-mix(in srgb, ${colors.sumi[900]} 60%, transparent)`,
        color: active ? color : undefined,
      }}
    >
      <div
        className="text-2xl font-bold tabular-nums"
        style={{ color }}
      >
        {value}
      </div>
      <div className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-sumi-500">
        {label}
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Expanded row detail
// ---------------------------------------------------------------------------

function RowDetail({ row }: { row: ControlSurfaceRow }) {
  return (
    <tr>
      <td colSpan={10} className="border-t border-sumi-800/40 bg-sumi-950/60 px-4 py-3">
        <div className="grid gap-3 text-xs text-sumi-400 md:grid-cols-2">
          <div>
            <span className="font-semibold text-sumi-500">Owner:</span>{" "}
            <code className="text-sumi-300">{row.owner_module || "—"}</code>
          </div>
          <div>
            <span className="font-semibold text-sumi-500">Truth Owner:</span>{" "}
            <code className="text-sumi-300">{row.truth_owner || "—"}</code>
          </div>
          <div>
            <span className="font-semibold text-sumi-500">Authority Role:</span>{" "}
            <code className="text-sumi-300">{row.authority_role}</code>
          </div>
          <div>
            <span className="font-semibold text-sumi-500">Freshness:</span>{" "}
            <code className="text-sumi-300">{row.freshness || "—"}</code>
          </div>
          {row.evidence.length > 0 && (
            <div className="md:col-span-2">
              <span className="font-semibold text-sumi-500">Evidence:</span>
              <ul className="mt-1 list-inside list-disc space-y-0.5">
                {row.evidence.map((e, i) => (
                  <li key={i} className="text-sumi-400">{e}</li>
                ))}
              </ul>
            </div>
          )}
          {row.gap_codes.length > 0 && (
            <div className="md:col-span-2">
              <span className="font-semibold text-sumi-500">Gap Codes:</span>{" "}
              {row.gap_codes.map((g, i) => (
                <code
                  key={i}
                  className="mr-1 rounded bg-sumi-800/60 px-1.5 py-0.5 text-bengara"
                >
                  {g}
                </code>
              ))}
            </div>
          )}
          {row.source_refs.length > 0 && (
            <div className="md:col-span-2">
              <span className="font-semibold text-sumi-500">Source Refs:</span>{" "}
              {row.source_refs.filter(Boolean).map((s, i) => (
                <code
                  key={i}
                  className="mr-1 rounded bg-sumi-800/60 px-1.5 py-0.5 text-sumi-300"
                >
                  {s}
                </code>
              ))}
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ControlSurfacePage() {
  const { rows, isLoading, error } = useControlSurfaceRows();
  const { summary } = useControlSurfaceSummary();
  const [filter, setFilter] = useState<FilterKey>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = useMemo(() => applyFilter(rows, filter), [rows, filter]);

  if (error) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-bengara">
        Control surface unavailable: {String(error)}
      </div>
    );
  }

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-5"
    >
      {/* Header */}
      <motion.div variants={item}>
        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sumi-500">
          Active Surface Manifest
        </div>
        <h1 className="mt-1 font-heading text-xl font-bold text-torinoko">
          Control Surface
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-sumi-400">
          Declared intent reconciled against observed reality. The manifest
          declares what should exist; runtime, code, and evidence adapters
          show what actually exists.
        </p>
      </motion.div>

      {/* Summary strip */}
      {summary && (
        <motion.div variants={item} className="grid grid-cols-3 gap-3 sm:grid-cols-6">
          <SummaryCard
            label="Total"
            value={summary.total}
            color={colors.aozora}
            active={filter === "all"}
            onClick={() => setFilter("all")}
          />
          <SummaryCard
            label="Bound"
            value={summary.bound}
            color={colors.rokusho}
            active={false}
            onClick={() => setFilter("all")}
          />
          <SummaryCard
            label="Partial"
            value={summary.partial}
            color={colors.kinpaku}
            active={false}
            onClick={() => setFilter("all")}
          />
          <SummaryCard
            label="Drifted"
            value={summary.drifted}
            color={colors.bengara}
            active={filter === "drifted"}
            onClick={() => setFilter("drifted")}
          />
          <SummaryCard
            label="Needs John"
            value={summary.human_decision_required_count}
            color={colors.botan}
            active={filter === "needs_john"}
            onClick={() => setFilter("needs_john")}
          />
          <SummaryCard
            label="P0"
            value={summary.p0_count}
            color={colors.bengara}
            active={filter === "p0"}
            onClick={() => setFilter("p0")}
          />
        </motion.div>
      )}

      {/* Filter tabs */}
      <motion.div variants={item} className="flex flex-wrap gap-2">
        {(Object.keys(FILTER_LABELS) as FilterKey[]).map((key) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`rounded-lg border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] transition-all ${
              filter === key
                ? "border-aozora/40 bg-aozora/10 text-aozora"
                : "border-sumi-700/40 bg-sumi-900/40 text-sumi-500 hover:text-sumi-300"
            }`}
          >
            {FILTER_LABELS[key]} ({applyFilter(rows, key).length})
          </button>
        ))}
      </motion.div>

      {/* Grid table */}
      <motion.div variants={item} className="overflow-x-auto rounded-xl border border-sumi-700/30">
        {isLoading ? (
          <div className="flex h-32 items-center justify-center text-sm text-sumi-500">
            Loading control surface...
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-sm text-sumi-500">
            No rows match the current filter.
          </div>
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-sumi-700/40 bg-sumi-900/70 text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-500">
                <th className="px-3 py-2.5">Entity</th>
                <th className="px-3 py-2.5">Kind</th>
                <th className="px-3 py-2.5">Declared</th>
                <th className="px-3 py-2.5">Observed</th>
                <th className="px-3 py-2.5">Coherence</th>
                <th className="px-3 py-2.5">Priority</th>
                <th className="px-3 py-2.5">Gap</th>
                <th className="px-3 py-2.5">Next Action</th>
                <th className="px-3 py-2.5">Evidence</th>
                <th className="px-3 py-2.5 text-center">John</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => {
                const cs = coherenceStyle(row.coherence_state);
                const expanded = expandedId === row.id;
                return (
                  <>
                    <tr
                      key={row.id}
                      onClick={() => setExpandedId(expanded ? null : row.id)}
                      className="cursor-pointer border-b border-sumi-800/30 transition-colors hover:bg-sumi-900/50"
                    >
                      <td className="px-3 py-2 font-medium text-sumi-200">
                        {row.label}
                      </td>
                      <td className="px-3 py-2">
                        <code className="rounded bg-sumi-800/50 px-1.5 py-0.5 text-[10px] text-sumi-400">
                          {row.kind}
                        </code>
                      </td>
                      <td className="px-3 py-2 text-sumi-400">
                        {row.declared_state || "—"}
                      </td>
                      <td className="px-3 py-2 text-sumi-300">
                        {row.observed_state || "—"}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className="rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em]"
                          style={{
                            borderColor: cs.border,
                            backgroundColor: cs.bg,
                            color: cs.text,
                          }}
                        >
                          {row.coherence_state}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className="text-[10px] font-bold uppercase"
                          style={{ color: priorityColor(row.priority) }}
                        >
                          {row.priority}
                        </span>
                      </td>
                      <td className="max-w-[140px] truncate px-3 py-2 text-sumi-400">
                        {row.gap_codes.length > 0
                          ? row.gap_codes.join(", ")
                          : "—"}
                      </td>
                      <td className="max-w-[180px] truncate px-3 py-2 text-sumi-400">
                        {row.next_action || "—"}
                      </td>
                      <td className="px-3 py-2 text-sumi-500">
                        {row.evidence.length > 0
                          ? `${row.evidence.length} item${row.evidence.length > 1 ? "s" : ""}`
                          : "—"}
                      </td>
                      <td className="px-3 py-2 text-center">
                        {row.human_decision_required ? (
                          <span
                            className="inline-block h-2.5 w-2.5 rounded-full"
                            style={{ backgroundColor: colors.botan }}
                            title="Human decision required"
                          />
                        ) : null}
                      </td>
                    </tr>
                    {expanded && <RowDetail key={`${row.id}-detail`} row={row} />}
                  </>
                );
              })}
            </tbody>
          </table>
        )}
      </motion.div>

      {/* Generated at */}
      {summary?.generated_at && (
        <motion.div variants={item} className="text-[10px] text-sumi-600">
          Generated {summary.generated_at} · Sources:{" "}
          {summary.sources_consulted.join(", ")}
        </motion.div>
      )}
    </motion.div>
  );
}
