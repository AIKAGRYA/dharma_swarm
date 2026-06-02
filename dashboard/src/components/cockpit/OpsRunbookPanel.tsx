"use client";

import {
  AlertTriangle,
  Battery,
  Plane,
  Server,
  ShieldCheck,
  SquareTerminal,
} from "lucide-react";
import type { ControlSurfaceRow } from "@/lib/types";
import { colors } from "@/lib/theme";

interface OpsRunbookPanelProps {
  rows: ControlSurfaceRow[];
  selectedRow: ControlSurfaceRow | null;
}

type FlightBucket = "keep" | "blocked" | "review" | "optional";

const FLIGHT_SURFACE_ORDER = [
  "live_ops.substrate.dharma_daemon",
  "live_ops.transport.nats",
  "live_ops.dashboard.local",
  "live_ops.revenue.cashclaw_gate",
  "live_ops.remote.agni",
  "live_ops.mission.forge_reality_arena",
  "live_ops.agent.merge_master_mike",
  "live_ops.tmux.cockpit",
  "live_ops.load.colima_openclaw",
  "live_ops.terminal.tui",
];

function rawString(row: ControlSurfaceRow | null, key: string): string {
  const value = row?.raw?.[key];
  return typeof value === "string" ? value : "";
}

function bucketFor(row: ControlSurfaceRow): FlightBucket {
  if (row.gap_codes.includes("human_authority_required") || row.observed_state === "blocked") {
    return "blocked";
  }
  if (row.id.includes("dharma_daemon") || row.id.includes("transport.nats") || row.id.includes("dashboard.local")) {
    return "keep";
  }
  if (row.gap_codes.includes("heavy_local_load") || row.id.includes("terminal.tui")) {
    return "optional";
  }
  return "review";
}

function BucketBadge({ bucket }: { bucket: FlightBucket }) {
  const label = {
    keep: "Keep",
    blocked: "Blocked",
    review: "Review",
    optional: "Optional",
  }[bucket];
  const color = {
    keep: colors.rokusho,
    blocked: colors.botan,
    review: colors.kinpaku,
    optional: colors.sumi[600],
  }[bucket];
  return (
    <span
      className="rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase"
      style={{
        borderColor: `color-mix(in srgb, ${color} 40%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${color} 10%, transparent)`,
        color,
      }}
    >
      {label}
    </span>
  );
}

function StatPill({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="flex min-w-[92px] items-center justify-between gap-3 rounded-md border border-sumi-700/30 bg-sumi-900/40 px-2 py-1.5">
      <span className="text-[10px] uppercase text-sumi-500">{label}</span>
      <span className="text-xs font-semibold tabular-nums" style={{ color }}>
        {value}
      </span>
    </div>
  );
}

export function OpsRunbookPanel({ rows, selectedRow }: OpsRunbookPanelProps) {
  const liveOpsRows = rows.filter((row) => row.id.startsWith("live_ops."));
  const beforeFlightRows = FLIGHT_SURFACE_ORDER
    .map((id) => liveOpsRows.find((row) => row.id === id))
    .filter((row): row is ControlSurfaceRow => Boolean(row));
  const vpsCandidates = liveOpsRows.filter((row) => row.gap_codes.includes("vps_candidate")).length;
  const heavyLocal = liveOpsRows.filter((row) => row.gap_codes.includes("heavy_local_load")).length;
  const blocked = liveOpsRows.filter((row) => row.observed_state === "blocked").length;
  const stale = liveOpsRows.filter((row) => row.observed_state === "stale").length;
  const restartCommand = rawString(selectedRow, "restart_command");
  const stopPolicy = rawString(selectedRow, "stop_policy");

  return (
    <section className="rounded-md border border-sumi-700/30 bg-sumi-950/60">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-sumi-800/40 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Plane size={14} className="text-aozora" />
          <span className="text-[10px] font-semibold uppercase text-sumi-500">
            Tonight / Before Flight
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <StatPill label="Live Ops" value={liveOpsRows.length} color={colors.aozora} />
          <StatPill label="Blocked" value={blocked} color={colors.botan} />
          <StatPill label="Stale" value={stale} color={colors.kinpaku} />
          <StatPill label="VPS" value={vpsCandidates} color={colors.fuji} />
          <StatPill label="Heavy" value={heavyLocal} color={colors.bengara} />
        </div>
      </div>

      <div className="grid gap-3 p-3 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex gap-2 overflow-x-auto">
          {beforeFlightRows.map((row) => {
            const bucket = bucketFor(row);
            return (
              <div
                key={row.id}
                className="min-w-[210px] rounded-md border border-sumi-800/50 bg-sumi-900/40 px-3 py-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="line-clamp-1 text-xs font-medium text-sumi-200">{row.label}</span>
                  <BucketBadge bucket={bucket} />
                </div>
                <div className="mt-2 flex items-center gap-2 text-[10px] text-sumi-500">
                  {bucket === "keep" && <ShieldCheck size={11} className="text-rokusho" />}
                  {bucket === "blocked" && <AlertTriangle size={11} style={{ color: colors.botan }} />}
                  {bucket === "review" && <Server size={11} style={{ color: colors.kinpaku }} />}
                  {bucket === "optional" && <Battery size={11} className="text-sumi-500" />}
                  <span className="capitalize">{row.observed_state || "unknown"}</span>
                  <span>·</span>
                  <span className="truncate">{row.next_action || row.desired_state || "inspect"}</span>
                </div>
              </div>
            );
          })}
        </div>

        <div className="rounded-md border border-sumi-800/50 bg-sumi-900/40 px-3 py-2">
          <div className="flex items-center gap-2">
            <SquareTerminal size={13} className="text-aozora" />
            <span className="text-[10px] font-semibold uppercase text-sumi-500">
              Read-only Runbook
            </span>
          </div>
          <div className="mt-2 space-y-2 text-[10px]">
            <div>
              <div className="text-sumi-500">Selected</div>
              <div className="mt-0.5 truncate text-xs text-sumi-200">{selectedRow?.label ?? "Select a row"}</div>
            </div>
            <div>
              <div className="text-sumi-500">Command Text</div>
              <code className="mt-0.5 block whitespace-pre-wrap break-words rounded bg-sumi-950/70 px-2 py-1 text-aozora">
                {restartCommand || "inspect row evidence first"}
              </code>
            </div>
            <div>
              <div className="text-sumi-500">Stop Policy</div>
              <code className="mt-0.5 block whitespace-pre-wrap break-words rounded bg-sumi-950/70 px-2 py-1 text-sumi-300">
                {stopPolicy || "no policy declared"}
              </code>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
