"use client";

import { motion } from "framer-motion";
import { Activity, Database, Play, RefreshCw, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { useGoodworksDgm } from "@/hooks/useGoodworksDgm";
import { colors, glowText } from "@/lib/theme";
import type { GoodworksMetricSnapshot, GoodworksReceipt } from "@/lib/types";

function formatNumber(value: number, digits = 0): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

function formatTime(value?: string | null): string {
  if (!value) return "none";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function receiptLabel(receipt: GoodworksReceipt): string {
  if (typeof receipt.receipt_id === "string") return receipt.receipt_id;
  if (typeof receipt.goal_id === "string") return receipt.goal_id;
  return "receipt";
}

function statusTone(metrics: GoodworksMetricSnapshot | null): string {
  if (!metrics) return "border-sumi-700/50 bg-sumi-800/40 text-sumi-300";
  if (!metrics.reciprocity_chain_valid || !metrics.gaia_chain_valid) {
    return "border-red-900/50 bg-red-950/20 text-red-200";
  }
  if (metrics.invariant_issue_count || metrics.conservation_violation_count) {
    return "border-amber-900/50 bg-amber-950/20 text-amber-200";
  }
  return "border-emerald-900/50 bg-emerald-950/20 text-emerald-200";
}

export default function GoodworksPage() {
  const { status, receipts, isLoading, isFetching, error, createDryRun, refresh } =
    useGoodworksDgm();
  const latest = status?.last_run ?? null;
  const metrics = latest?.metrics ?? status?.current_metrics ?? null;
  const providerTruth = status?.provider_key_truth;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1
            className="font-heading text-2xl font-bold tracking-tight"
            style={{ color: colors.rokusho, textShadow: glowText(colors.rokusho, 0.45) }}
          >
            Goodworks DGM
          </h1>
          <p className="max-w-3xl text-sm text-sumi-400">
            {status?.thesis ??
              "Telos-gated DGM surface for Goodworks MRV and regenerative coordination."}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => refresh()}
            className="inline-flex items-center gap-2 rounded-lg border border-sumi-700/50 bg-sumi-900/70 px-3 py-2 text-sm text-sumi-200 transition-colors hover:border-aozora/60 hover:text-aozora"
          >
            <RefreshCw size={15} className={isFetching ? "animate-spin" : ""} />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => createDryRun.mutate()}
            disabled={createDryRun.isPending}
            className="inline-flex items-center gap-2 rounded-lg border border-rokusho/50 bg-rokusho/10 px-3 py-2 text-sm text-rokusho transition-colors hover:bg-rokusho/20 disabled:opacity-50"
          >
            <Play size={15} />
            Dry Run
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-200">
          {error instanceof Error ? error.message : String(error)}
        </div>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-4 md:grid-cols-2">
        <MetricCard
          icon={<Database size={18} />}
          label="Reciprocity Rows"
          value={metrics ? String(metrics.reciprocity_entries) : isLoading ? "..." : "0"}
          detail={`${metrics?.evidence_records ?? 0} evidence · ${metrics?.audit_records ?? 0} audits`}
        />
        <MetricCard
          icon={<Activity size={18} />}
          label="GAIA Rows"
          value={metrics ? String(metrics.gaia_entries) : isLoading ? "..." : "0"}
          detail={`${formatNumber(metrics?.verified_offsets_tco2e ?? 0, 3)} verified tCO2e`}
        />
        <MetricCard
          icon={<ShieldCheck size={18} />}
          label="Ledger Integrity"
          value={
            metrics?.reciprocity_chain_valid && metrics?.gaia_chain_valid
              ? "valid"
              : metrics
                ? "check"
                : "unknown"
          }
          detail={`${metrics?.invariant_issue_count ?? 0} invariant · ${metrics?.conservation_violation_count ?? 0} conservation`}
        />
        <MetricCard
          icon={<RefreshCw size={18} />}
          label="Runs"
          value={String(status?.run_count ?? 0)}
          detail={`latest ${formatTime(latest?.completed_at ?? latest?.created_at)}`}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-lg border border-sumi-700/50 bg-sumi-900/60 p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-heading text-lg text-sumi-100">Current Goal Loop</h2>
              <p className="text-sm text-sumi-400">
                Dry-run by default. Shadow DGM receipts never apply code.
              </p>
            </div>
            <span className={`rounded-full border px-2.5 py-1 text-[11px] uppercase tracking-[0.12em] ${statusTone(metrics)}`}>
              {latest?.status ?? "no run"}
            </span>
          </div>

          {latest ? (
            <div className="space-y-4">
              <div className="rounded-lg border border-sumi-700/40 bg-sumi-800/30 p-4">
                <div className="text-sm font-medium text-sumi-100">{latest.spec.title}</div>
                <p className="mt-2 text-sm text-sumi-400">{latest.spec.objective}</p>
                <div className="mt-3 grid gap-2 text-xs text-sumi-500 md:grid-cols-3">
                  <span>mode: {latest.spec.mutation_mode}</span>
                  <span>score: {latest.latest_score.toFixed(3)}</span>
                  <span>next: {latest.next_required_action || "review receipts"}</span>
                </div>
              </div>
              <ReceiptList receipts={latest.receipts} />
            </div>
          ) : (
            <div className="rounded-lg border border-sumi-700/40 bg-sumi-800/30 p-6 text-sm text-sumi-500">
              No Goodworks DGM run has been recorded yet.
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-sumi-700/50 bg-sumi-900/60 p-5">
            <h2 className="font-heading text-lg text-sumi-100">Provider Key Truth</h2>
            <p className="mt-1 text-sm text-sumi-400">
              The repo never stores key values. This panel reports only local env-var names.
            </p>
            <div className="mt-4 rounded-lg border border-sumi-700/40 bg-sumi-800/30 p-4">
              <div className="text-2xl font-semibold text-sumi-100">
                {providerTruth?.local_configured_key_count ?? 0}
              </div>
              <div className="text-xs uppercase tracking-[0.16em] text-sumi-500">
                configured provider env vars
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(providerTruth?.local_configured_key_names ?? []).map((name) => (
                  <span key={name} className="rounded border border-sumi-700/50 px-2 py-1 font-mono text-[11px] text-sumi-300">
                    {name}
                  </span>
                ))}
              </div>
              <p className="mt-3 text-xs text-sumi-500">
                {providerTruth?.remote_agent_note ?? "Remote agents must verify local key state with local probes."}
              </p>
            </div>
          </div>

          <div className="rounded-lg border border-sumi-700/50 bg-sumi-900/60 p-5">
            <h2 className="font-heading text-lg text-sumi-100">Recent Receipts</h2>
            <div className="mt-4 space-y-2">
              {receipts.length === 0 ? (
                <div className="rounded-lg border border-sumi-700/40 bg-sumi-800/30 p-4 text-sm text-sumi-500">
                  No receipts yet.
                </div>
              ) : (
                receipts.slice().reverse().map((receipt, index) => (
                  <div key={`${receiptLabel(receipt)}-${index}`} className="rounded-lg border border-sumi-700/40 bg-sumi-800/30 p-3">
                    <div className="font-mono text-xs text-sumi-200">{receiptLabel(receipt)}</div>
                    <div className="mt-1 text-xs text-sumi-500">{formatTime(String(receipt.created_at ?? ""))}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </section>
    </motion.div>
  );
}

function MetricCard({
  icon,
  label,
  value,
  detail,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-lg border border-sumi-700/50 bg-sumi-900/60 p-4">
      <div className="flex items-center gap-2 text-sumi-500">
        {icon}
        <span className="text-xs uppercase tracking-[0.16em]">{label}</span>
      </div>
      <div className="mt-3 text-2xl font-semibold text-sumi-100">{value}</div>
      <p className="mt-2 text-sm text-sumi-400">{detail}</p>
    </div>
  );
}

function ReceiptList({ receipts }: { receipts: GoodworksReceipt[] }) {
  return (
    <div className="grid gap-2 md:grid-cols-3">
      {receipts.slice(-3).map((receipt, index) => (
        <div key={`${receiptLabel(receipt)}-${index}`} className="rounded-lg border border-sumi-700/40 bg-sumi-800/30 p-3">
          <div className="truncate font-mono text-xs text-sumi-200">{receiptLabel(receipt)}</div>
          <div className="mt-1 text-xs text-sumi-500">{formatTime(String(receipt.created_at ?? ""))}</div>
        </div>
      ))}
    </div>
  );
}
