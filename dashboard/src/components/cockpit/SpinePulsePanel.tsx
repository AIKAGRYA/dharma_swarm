"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { ControlSurfaceEnvelope, ControlSurfaceRow } from "@/lib/types";

/** Read-only cockpit pulse over the live EvidenceReceipt stream.
 *
 * Projects `spine.pulse` (owner: operator_core/spine_tail.py →
 * delegation_runs.receipt_json, truth owner runtime_state). Three stat
 * tiles — receipts/hour, last-receipt age, dropoff count — so the operator
 * can SEE and FEEL the spine working (organism-rewire-2026-07 item 2).
 * No writes, no new store; graceful "not live on this host" state.
 */

interface SpinePulseRaw {
  present?: boolean;
  detail?: string;
  db_path?: string;
  receipts_last_hour?: number;
  last_receipt_age_seconds?: number | null;
  dispatch_dropoff_count?: number;
}

function unwrap<T>(payload: T | ControlSurfaceEnvelope<T>): T {
  if (payload && typeof payload === "object" && "data" in payload && "schema_version" in payload) {
    return (payload as ControlSurfaceEnvelope<T>).data;
  }
  return payload as T;
}

function humanizeAge(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

const FRESH_SECONDS = 300;

export function SpinePulsePanel() {
  const { data, isLoading, error } = useQuery<ControlSurfaceRow | null>({
    queryKey: ["control-surface-spine-pulse"],
    queryFn: async () => {
      const payload = await apiFetch<
        ControlSurfaceRow | ControlSurfaceEnvelope<ControlSurfaceRow>
      >("/api/control-surface/rows/spine.pulse");
      return unwrap(payload);
    },
    refetchInterval: 15_000,
  });

  const pulse = (data?.raw ?? {}) as SpinePulseRaw;
  const present = Boolean(pulse.present);
  const age = pulse.last_receipt_age_seconds;
  const live = present && age !== null && age !== undefined && age <= FRESH_SECONDS;
  const dropoffs = pulse.dispatch_dropoff_count ?? 0;

  return (
    <section
      aria-label="Spine pulse — live EvidenceReceipt stream"
      className="rounded-md border border-sumi-800/60 bg-sumi-950/50 p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-aozora">
          <Activity size={13} aria-hidden />
          Spine Pulse · EvidenceReceipt stream
        </div>
        <span
          className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
            live
              ? "border border-aozora/50 bg-aozora/10 text-aozora"
              : "border border-sumi-700/60 bg-sumi-900/50 text-sumi-500"
          }`}
        >
          {live ? "LIVE" : present ? "QUIET" : "NOT LIVE ON THIS HOST"}
        </span>
      </div>

      {isLoading && !data ? (
        <p className="mt-3 text-xs text-sumi-500">Reading receipt stream…</p>
      ) : error ? (
        <p className="mt-3 text-xs text-sumi-500">
          Pulse unavailable: {String(error)}
        </p>
      ) : !present ? (
        <p className="mt-3 text-xs text-sumi-500">
          {pulse.detail || "spine not live on this host — see make orient"}
        </p>
      ) : (
        <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
          <div className="rounded-md border border-sumi-800/50 bg-sumi-900/40 px-2 py-3">
            <dt className="text-[10px] uppercase tracking-wider text-sumi-500">
              Receipts / hour
            </dt>
            <dd className="mt-1 font-mono text-2xl font-semibold tabular-nums text-torinoko">
              {pulse.receipts_last_hour ?? 0}
            </dd>
          </div>
          <div className="rounded-md border border-sumi-800/50 bg-sumi-900/40 px-2 py-3">
            <dt className="text-[10px] uppercase tracking-wider text-sumi-500">
              Last receipt age
            </dt>
            <dd className="mt-1 font-mono text-2xl font-semibold tabular-nums text-torinoko">
              {humanizeAge(age)}
            </dd>
          </div>
          <div
            className={`rounded-md border px-2 py-3 ${
              dropoffs > 0
                ? "border-bengara/50 bg-bengara/10"
                : "border-sumi-800/50 bg-sumi-900/40"
            }`}
          >
            <dt className="text-[10px] uppercase tracking-wider text-sumi-500">
              Dropoffs{dropoffs > 0 ? " ⚠" : ""}
            </dt>
            <dd
              className={`mt-1 font-mono text-2xl font-semibold tabular-nums ${
                dropoffs > 0 ? "text-bengara" : "text-torinoko"
              }`}
            >
              {dropoffs}
            </dd>
          </div>
        </dl>
      )}

      <p className="mt-2 text-[10px] text-sumi-600">
        Read-only · owner: operator_core/spine_tail.py · truth: runtime_state
        (delegation_runs.receipt_json) · CLI: `dgc spine tail --follow`
      </p>
    </section>
  );
}
