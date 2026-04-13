"use client";

/**
 * DHARMA COMMAND -- Dashboard Overview (L1 page).
 * MetricCards, FitnessTrend, Agent cards, Activity table.
 */

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { useOverview } from "@/hooks/useOverview";
import { useAgents } from "@/hooks/useAgents";
import { useHealth } from "@/hooks/useHealth";
import { useTelemetry } from "@/hooks/useTelemetry";
import { useDaemonHealth } from "@/hooks/useDaemonHealth";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { FitnessTrend } from "@/components/dashboard/FitnessTrend";
import { AgentCard } from "@/components/dashboard/AgentCard";
import { ActivityTable } from "@/components/dashboard/ActivityTable";
import { HealthBadge } from "@/components/dashboard/HealthBadge";
import { colors, statusColor } from "@/lib/theme";
import type { DaemonRecentCall } from "@/lib/types";

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06 },
  },
};

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

function formatUsd(value: number): string {
  if (value < 0.01) return `$${value.toFixed(4)}`;
  if (value < 1) return `$${value.toFixed(3)}`;
  return `$${value.toFixed(2)}`;
}

function toneColor(kind: "good" | "warn" | "critical" | "neutral"): string {
  if (kind === "good") return colors.rokusho;
  if (kind === "warn") return colors.kinpaku;
  if (kind === "critical") return colors.bengara;
  return colors.aozora;
}

function SnapshotCell({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "good" | "warn" | "critical" | "neutral";
}) {
  const accent = toneColor(tone);
  return (
    <div className="rounded-xl border border-sumi-700/30 bg-sumi-950/45 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
        {label}
      </p>
      <p
        className="mt-1 font-mono text-lg font-bold"
        style={{ color: accent }}
      >
        {value}
      </p>
      <p className="mt-1 text-xs text-sumi-600">{detail}</p>
    </div>
  );
}

function DrilldownCard({
  title,
  summary,
  detail,
  href,
  accent,
}: {
  title: string;
  summary: string;
  detail: string;
  href: string;
  accent: string;
}) {
  return (
    <Link
      href={href}
      className="group rounded-xl border border-sumi-700/30 bg-sumi-950/45 p-4 transition-all hover:border-sumi-600/40 hover:bg-sumi-950/65"
      style={{
        boxShadow: `0 0 0 1px color-mix(in srgb, ${accent} 8%, transparent)`,
      }}
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
        {title}
      </p>
      <p
        className="mt-2 font-mono text-base font-bold"
        style={{ color: accent }}
      >
        {summary}
      </p>
      <p className="mt-2 text-xs text-sumi-600">{detail}</p>
      <p
        className="mt-3 text-[10px] font-semibold uppercase tracking-[0.12em] transition-colors group-hover:text-torinoko"
        style={{ color: accent }}
      >
        Open →
      </p>
    </Link>
  );
}

function formatRecentTimestamp(epochSeconds: number, now: number): string {
  if (now === 0) return "";
  const minutes = Math.max(0, Math.round((now - epochSeconds * 1000) / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

function RecentWorkRow({ call, now }: { call: DaemonRecentCall; now: number }) {
  const label =
    call.task_title?.trim() ||
    call.source?.trim() ||
    call.execution_mode?.trim() ||
    "unlabeled daemon work";
  const detail = [
    call.agent_name?.trim() || call.agent_role?.trim() || null,
    call.provider ? `${call.provider}/${call.model}` : call.model || null,
    call.lane?.trim() || null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="rounded-xl border border-sumi-700/30 bg-sumi-950/45 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-torinoko">{label}</p>
          <p className="mt-1 truncate text-xs text-sumi-600">
            {detail || "No execution metadata attached yet"}
          </p>
        </div>
        <p className="shrink-0 text-[10px] uppercase tracking-[0.12em] text-sumi-600">
          {formatRecentTimestamp(call.timestamp, now)}
        </p>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-sumi-600">
        <span>{call.input_tokens.toLocaleString()} in</span>
        <span>{call.output_tokens.toLocaleString()} out</span>
        <span>{formatUsd(call.estimated_cost_usd ?? 0)}</span>
      </div>
    </div>
  );
}

export default function DashboardOverview() {
  const { overview, isLoading: overviewLoading } = useOverview();
  const { agents } = useAgents();
  const { health } = useHealth();
  const { daemonHealth } = useDaemonHealth();
  const { overview: telemetryOverview, routing, interventions, outcomes } = useTelemetry();

  // Stable clock for render — avoids hydration mismatch from Date.now().
  // Starts at 0 (SSR-safe), populated on mount via useEffect.
  const [now, setNow] = useState(0);
  useEffect(() => {
    const tick = () => setNow(Date.now());
    const id = setInterval(tick, 15_000);
    tick();
    return () => clearInterval(id);
  }, []);

  const agentCount = overview?.agent_count ?? agents.length;
  const taskCount = overview?.task_count ?? 0;
  const fitness = overview?.mean_fitness ?? 0;
  const healthStatus = overview?.health_status ?? health?.overall_status ?? "unknown";
  const activeRosterAgents = agents.filter((agent) => agent.status === "busy");
  const idleRosterAgents = agents.filter((agent) => agent.status === "idle");
  const tracesLastHour = health?.traces_last_hour ?? 0;
  const anomalyCount = health?.anomalies?.length ?? 0;
  const activeTelemetryAgents = telemetryOverview?.active_agents ?? 0;
  const routingDecisions = telemetryOverview?.routing_decision_count ?? 0;
  const rewardEvents = telemetryOverview?.reward_event_count ?? 0;
  const interventionCount = telemetryOverview?.intervention_count ?? interventions.length;
  const outcomeCount = telemetryOverview?.external_outcome_count ?? outcomes.length;
  const routeEscalations = routing?.human_required_count ?? 0;
  const providerDiversity = Object.keys(routing?.provider_counts ?? {}).length;
  const topRoutePath = Object.entries(routing?.path_counts ?? {}).sort((a, b) => b[1] - a[1])[0];
  const topProvider = Object.entries(routing?.provider_counts ?? {}).sort((a, b) => b[1] - a[1])[0];
  const lastHeartbeatEpochs = agents
    .map((agent) => (agent.last_heartbeat ? Date.parse(agent.last_heartbeat) : NaN))
    .filter((value) => Number.isFinite(value)) as number[];
  const freshestHeartbeat = lastHeartbeatEpochs.length > 0 ? Math.max(...lastHeartbeatEpochs) : null;
  const hoursUp = overview ? Math.floor(overview.uptime_seconds / 3600) : null;
  const telemetryCost = telemetryOverview?.total_cost_usd ?? 0;
  const daemonCost1h = daemonHealth?.costs?.["1h"];
  const daemonRecent = daemonCost1h?.recent?.slice(0, 6) ?? [];
  const daemonRecentCount = daemonRecent.length;
  const daemonUptime = daemonHealth?.uptime;
  const daemonExecutionModes = Object.entries(daemonCost1h?.by_execution_mode ?? {}).sort((a, b) => b[1].calls - a[1].calls);
  const daemonSources = Object.entries(daemonCost1h?.by_source ?? {}).sort((a, b) => b[1].calls - a[1].calls);
  const dominantExecutionMode = daemonExecutionModes[0];
  const dominantSource = daemonSources[0];
  const daemonProviders = Object.keys(daemonCost1h?.by_provider ?? {}).length;
  const liveOutcomeCount = outcomeCount;
  const liveInterventions = interventionCount;
  const attentionDetail =
    anomalyCount > 0
      ? `${anomalyCount} ${anomalyCount === 1 ? "anomaly needs" : "anomalies need"} review`
      : routeEscalations > 0
        ? `${routeEscalations} human-routed decision${routeEscalations === 1 ? "" : "s"}`
        : "No immediate operator intervention signals";
  const attentionValue =
    anomalyCount > 0
      ? `${anomalyCount} anomalies`
      : routeEscalations > 0
        ? `${routeEscalations} escalations`
        : "clear";
  const attentionTone =
    anomalyCount > 0 ? "critical" : routeEscalations > 0 ? "warn" : "good";

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      {/* Page heading */}
      <motion.div variants={item}>
        <div className="flex items-center gap-3">
          <h1 className="glow-aozora font-heading text-2xl font-bold tracking-tight text-aozora">
            System Overview
          </h1>
          <HealthBadge
            status={healthStatus as "healthy" | "degraded" | "critical" | "unknown"}
            label
            size="md"
          />
        </div>
        <p className="mt-1 text-sm text-sumi-600">
          {overviewLoading
            ? "Connecting to swarm..."
            : overview
              ? `Uptime ${Math.floor(overview.uptime_seconds / 3600)}h · ${overview.stigmergy_density} marks · ${overview.evolution_entries} evolution entries`
              : "Awaiting swarm telemetry."}
        </p>
      </motion.div>

      <motion.div variants={item} className="glass-panel p-5">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="font-heading text-lg font-semibold tracking-tight text-torinoko">
              Operator Return
            </h2>
            <p className="mt-1 text-sm text-sumi-600">
              One glance after a long break: liveness, throughput, cost pressure, and what to open first if something looks off.
            </p>
          </div>
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-sumi-600">
            {daemonUptime ? `${daemonUptime} daemon uptime` : hoursUp != null ? `${hoursUp}h uptime` : "uptime unknown"}
            {freshestHeartbeat != null && now > 0 ? ` · newest agent heartbeat ${Math.max(0, Math.round((now - freshestHeartbeat) / 60000))}m ago` : ""}
          </p>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <SnapshotCell
            label="Live Throughput"
            value={`${daemonCost1h?.calls ?? tracesLastHour}/h`}
            detail={
              daemonCost1h
                ? `${daemonProviders} provider${daemonProviders === 1 ? "" : "s"} · ${dominantSource ? `top source: ${dominantSource[0]}` : "source mix pending"}`
                : `Trace-based estimate (${tracesLastHour}/h); daemon hourly ledger not loaded yet`
            }
            tone={(daemonCost1h?.calls ?? tracesLastHour) > 0 ? "good" : "warn"}
          />
          <SnapshotCell
            label="Work Mix"
            value={dominantExecutionMode ? dominantExecutionMode[0].replaceAll("_", " ") : topRoutePath ? topRoutePath[0] : "no routes"}
            detail={
              dominantExecutionMode
                ? `${dominantExecutionMode[1].calls} model calls · ${dominantSource ? `${dominantSource[0]} source` : "source pending"}`
                : topRoutePath
                  ? `${topRoutePath[1]} routing decisions · ${providerDiversity} providers in play`
                  : `${routingDecisions} routing decisions recorded`
            }
            tone={(daemonProviders || providerDiversity) > 1 ? "good" : "neutral"}
          />
          <SnapshotCell
            label="Intervention Load"
            value={attentionValue}
            detail={attentionDetail}
            tone={attentionTone}
          />
          <SnapshotCell
            label="Value Signals"
            value={`${rewardEvents} rewards`}
            detail={`Telemetry: ${interventionCount} interventions · ${outcomeCount} external outcomes`}
            tone={outcomeCount > 0 ? "good" : rewardEvents > 0 ? "neutral" : "warn"}
          />
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-[1.4fr_1fr]">
          <div className="rounded-xl border border-sumi-700/30 bg-sumi-950/45 p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
              Totals & Trails
            </p>
            <p className="mt-1 text-xs text-sumi-600">
              Roster size, evolution depth, and stigmergy density are cumulative. Spend is the rolling last hour when the daemon hourly ledger is connected.
            </p>
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
              <div>
                <p className="font-mono text-lg font-bold text-aozora">{agentCount}</p>
                <p className="text-sumi-600">registered agents</p>
              </div>
              <div>
                <p className="font-mono text-lg font-bold text-botan">{overview?.evolution_entries ?? 0}</p>
                <p className="text-sumi-600">evolution entries</p>
              </div>
              <div>
                <p className="font-mono text-lg font-bold text-fuji">{overview?.stigmergy_density ?? 0}</p>
                <p className="text-sumi-600">stigmergy marks</p>
              </div>
              <div>
                <p className="font-mono text-lg font-bold text-kinpaku">{formatUsd(daemonCost1h?.total_cost_usd ?? telemetryOverview?.total_cost_usd ?? 0)}</p>
                <p className="text-sumi-600">{daemonCost1h ? "last hour daemon cost" : "telemetry cost tracked"}</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-sumi-700/30 bg-sumi-950/45 p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
              Current Posture
            </p>
            <div className="mt-3 space-y-2 text-sm text-sumi-600">
              <p>
                <span className="text-torinoko">{activeRosterAgents.length}</span> busy,
                {" "}
                <span className="text-torinoko">{idleRosterAgents.length}</span> idle,
                {" "}
                <span className="text-torinoko">{overview?.tasks_running ?? 0}</span> running tasks.
              </p>
              <p>
                Fitness is <span className="text-torinoko">{fitness.toFixed(3)}</span> with health
                {" "}
                <span className="text-torinoko">{healthStatus}</span>.
              </p>
              <p>
                Telemetry sees <span className="text-torinoko">{routingDecisions}</span> route decisions and
                {" "}
                <span className="text-torinoko">{rewardEvents}</span> reward events.
              </p>
              {daemonCost1h ? (
                <p>
                  Daemon recorded <span className="text-torinoko">{daemonCost1h.calls}</span> model calls in the last hour across
                  {" "}
                  <span className="text-torinoko">{daemonProviders}</span> provider{daemonProviders === 1 ? "" : "s"}.
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </motion.div>

      <motion.div variants={item} className="glass-panel p-5">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="font-heading text-lg font-semibold tracking-tight text-torinoko">
              What The Swarm Did This Hour
            </h2>
            <p className="mt-1 text-sm text-sumi-600">
              Rolling last-hour ledger from the daemon: dominant modes, recent model calls, and where to click next.
            </p>
          </div>
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-sumi-600">
            {daemonCost1h ? `${daemonCost1h.calls} calls · ${formatUsd(daemonCost1h.total_cost_usd)} · ${daemonCost1h.input_tokens.toLocaleString()} in / ${daemonCost1h.output_tokens.toLocaleString()} out` : "daemon ledger unavailable"}
          </p>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="space-y-3">
            <div className="rounded-xl border border-sumi-700/30 bg-sumi-950/45 p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
                Dominant Modes
              </p>
              <div className="mt-3 space-y-2 text-sm text-sumi-600">
                <p>
                  Execution mode:
                  {" "}
                  <span className="text-torinoko">
                    {dominantExecutionMode
                      ? `${dominantExecutionMode[0].replaceAll("_", " ")} (${dominantExecutionMode[1].calls} calls)`
                      : "none in this window"}
                  </span>
                </p>
                <p>
                  Source:
                  {" "}
                  <span className="text-torinoko">
                    {dominantSource ? `${dominantSource[0]} (${dominantSource[1].calls} calls)` : "none in this window"}
                  </span>
                </p>
                <p>
                  Unlabeled recent calls:
                  {" "}
                  <span className="text-torinoko">
                    {daemonRecent.filter((call) => !call.task_title && !call.source && !call.execution_mode).length}
                  </span>
                </p>
              </div>
            </div>

            <div className="rounded-xl border border-sumi-700/30 bg-sumi-950/45 p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
                Where to Go Next
              </p>
              <div className="mt-3 space-y-2">
                <Link
                  href="/dashboard/tasks"
                  className="flex items-center justify-between gap-3 rounded-lg border border-transparent px-2 py-2 text-sm text-sumi-600 transition-colors hover:border-sumi-700/40 hover:bg-sumi-900/40"
                >
                  <span><span className="font-medium text-aozora">Current Work</span> — task board and ownership</span>
                  <span className="shrink-0 text-aozora" aria-hidden>→</span>
                </Link>
                <Link
                  href="/dashboard/telemetry"
                  className="flex items-center justify-between gap-3 rounded-lg border border-transparent px-2 py-2 text-sm text-sumi-600 transition-colors hover:border-sumi-700/40 hover:bg-sumi-900/40"
                >
                  <span><span className="font-medium text-kinpaku">Models + Cost</span> — routes and spend concentration</span>
                  <span className="shrink-0 text-kinpaku" aria-hidden>→</span>
                </Link>
                <Link
                  href="/dashboard/runtime"
                  className="flex items-center justify-between gap-3 rounded-lg border border-transparent px-2 py-2 text-sm text-sumi-600 transition-colors hover:border-sumi-700/40 hover:bg-sumi-900/40"
                >
                  <span><span className="font-medium text-fuji">Coordination</span> — policy, handoffs, runtime pressure</span>
                  <span className="shrink-0 text-fuji" aria-hidden>→</span>
                </Link>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-sumi-700/30 bg-sumi-950/45 p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-sumi-600">
              Recent Model Calls
            </p>
            <div className="mt-3 space-y-3">
              {daemonRecentCount > 0 ? (
                daemonRecent.map((call, index) => (
                  <RecentWorkRow key={`${call.timestamp}-${call.model}-${index}`} call={call} now={now} />
                ))
              ) : (
                <div className="rounded-xl border border-sumi-700/30 bg-sumi-950/45 p-4 text-sm text-sumi-600">
                  No model calls in this snapshot window, or the hourly feed has not populated yet. If throughput above is non-zero, wait one refresh cycle.
                </div>
              )}
            </div>
          </div>
        </div>
      </motion.div>

      <motion.div variants={item} className="glass-panel p-5">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="font-heading text-lg font-semibold tracking-tight text-torinoko">
              Runtime Drilldowns
            </h2>
            <p className="mt-1 text-sm text-sumi-600">
              Click into the live surfaces that explain what the daemon is doing, who is doing it, what it costs, and where coordination pressure sits.
            </p>
          </div>
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-sumi-600">
            Full-width cards — entire tile is the click target
          </p>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
          <DrilldownCard
            title="Current Work"
            summary={`${overview?.tasks_running ?? 0} running · ${tracesLastHour}/h`}
            detail={`Task board + recent execution activity. ${topRoutePath ? `Dominant path: ${topRoutePath[0]}.` : "Route mix not yet visible."}`}
            href="/dashboard/tasks"
            accent={colors.botan}
          />
          <DrilldownCard
            title="Agents"
            summary={`${activeRosterAgents.length} busy · ${agentCount} roster`}
            detail={`${activeTelemetryAgents} telemetry identities observed. Drill into roster, models, heartbeat freshness, and task ownership.`}
            href="/dashboard/agents"
            accent={colors.aozora}
          />
          <DrilldownCard
            title="Models + Cost"
            summary={`${formatUsd(telemetryCost)} tracked`}
            detail={`${topProvider ? `${topProvider[0]} leads with ${topProvider[1]} route decisions.` : "Provider mix available."} Use telemetry to inspect cost and routing concentration.`}
            href="/dashboard/telemetry"
            accent={colors.kinpaku}
          />
          <DrilldownCard
            title="Coordination"
            summary={`${routingDecisions} routes · ${liveInterventions} interventions`}
            detail={`${routeEscalations} human-required decisions. This is the best live surface for handoffs, policy, and disagreement synthesis.`}
            href="/dashboard/runtime"
            accent={colors.fuji}
          />
          <DrilldownCard
            title="Layers"
            summary={`${overview?.evolution_entries ?? 0} evo · ${overview?.stigmergy_density ?? 0} marks`}
            detail={`${liveOutcomeCount} outcomes surfaced. Use runtime and telemetry together to infer which layers are metabolizing, coordinating, or producing.`}
            href="/dashboard/runtime"
            accent={colors.rokusho}
          />
        </div>
      </motion.div>

      {/* Metric cards */}
      <motion.div
        variants={item}
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <MetricCard
          label="Agents"
          value={agentCount}
          trend={agentCount > 0 ? "up" : null}
          trendLabel={`${agents.filter((a) => a.status === "busy").length} active`}
          accentColor={colors.aozora}
          index={0}
          expandable
          href="/dashboard/agents"
          expandContent={
            <div className="space-y-1.5">
              {agents.slice(0, 8).map((a) => (
                <div key={a.id} className="flex items-center gap-2">
                  <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: statusColor(a.status) }} />
                  <span className="truncate text-xs text-torinoko">{a.display_name || a.name}</span>
                  <span className="ml-auto text-[9px] text-sumi-600">{a.role}</span>
                </div>
              ))}
            </div>
          }
        />
        <MetricCard
          label="Tasks"
          value={taskCount}
          trend={
            overview && overview.tasks_completed > overview.tasks_failed
              ? "up"
              : overview && overview.tasks_failed > 0
                ? "down"
                : null
          }
          trendLabel={
            overview
              ? `${overview.tasks_completed} done, ${overview.tasks_failed} failed`
              : undefined
          }
          accentColor={colors.botan}
          index={1}
          expandable
          href="/dashboard/tasks"
          expandContent={<p className="text-xs text-sumi-600">Click to manage tasks</p>}
        />
        <MetricCard
          label="Fitness"
          value={fitness.toFixed(3)}
          trend={fitness > 0.5 ? "up" : fitness > 0 ? "down" : null}
          trendLabel={`${overview?.evolution_entries ?? 0} entries`}
          accentColor={colors.kinpaku}
          index={2}
          expandable
          href="/dashboard/evolution"
          expandContent={<p className="text-xs text-sumi-600">{overview?.evolution_entries ?? 0} evolution entries recorded</p>}
        />
        <MetricCard
          label="Health"
          value={healthStatus}
          trend={healthStatus === "healthy" ? "up" : healthStatus === "critical" ? "down" : null}
          trendLabel={`${health?.anomalies?.length ?? 0} anomalies`}
          accentColor={healthStatus === "healthy" ? colors.rokusho : healthStatus === "critical" ? colors.bengara : colors.kinpaku}
          index={3}
          expandable
          href="/dashboard/audit"
          expandContent={<p className="text-xs text-sumi-600">{health?.anomalies?.length ?? 0} anomalies detected</p>}
        />
      </motion.div>

      {/* Middle section: Fitness trend + Agent list */}
      <motion.div
        variants={item}
        className="grid grid-cols-1 gap-4 lg:grid-cols-3"
      >
        <FitnessTrend className="lg:col-span-2" />

        <div className="space-y-3">
          <h3
            className="text-[11px] font-semibold uppercase tracking-[0.12em]"
            style={{ color: colors.kitsurubami }}
          >
            Active Agents
          </h3>
          {agents.length === 0 ? (
            <div className="glass-panel-subtle flex items-center justify-center py-8">
              <p className="text-sm text-sumi-600">No agents spawned</p>
            </div>
          ) : (
            <div className="space-y-2">
              {agents.slice(0, 6).map((agent, i) => (
                <AgentCard key={agent.id} agent={agent} index={i} />
              ))}
              {agents.length > 6 && (
                <p className="text-center text-xs text-sumi-600">
                  +{agents.length - 6} more
                </p>
              )}
            </div>
          )}
        </div>
      </motion.div>

      {/* Activity table */}
      <motion.div variants={item}>
        <ActivityTable />
      </motion.div>
    </motion.div>
  );
}
