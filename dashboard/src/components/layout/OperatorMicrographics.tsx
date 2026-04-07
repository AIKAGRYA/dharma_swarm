"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp, HelpCircle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { colors } from "@/lib/theme";
import { useOverview } from "@/hooks/useOverview";
import { useHealth } from "@/hooks/useHealth";
import { useAgents } from "@/hooks/useAgents";
import { apiFetch } from "@/lib/api";
import type { FitnessTrendPoint } from "@/lib/types";

const COLLAPSED_KEY = "dharma-micrographics-collapsed";

/* ─── Tooltip ────────────────────────────────────────────── */

function Tip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block">
      <HelpCircle
        size={10}
        className="cursor-help text-sumi-600 transition-colors hover:text-aozora"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      />
      {show && (
        <span className="absolute bottom-full left-1/2 z-50 mb-2 w-48 -translate-x-1/2 rounded-lg border border-sumi-700/40 bg-sumi-900 px-3 py-2 text-[10px] leading-tight text-torinoko shadow-lg">
          {text}
        </span>
      )}
    </span>
  );
}

/* ─── Stat Pill ──────────────────────────────────────────── */

function Pill({
  label,
  value,
  sub,
  color,
  tip,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color: string;
  tip?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className="flex items-center gap-1">
        <span className="text-[8px] font-semibold uppercase tracking-widest text-sumi-600">
          {label}
        </span>
        {tip && <Tip text={tip} />}
      </div>
      <span className="font-mono text-sm font-bold" style={{ color }}>
        {value}
      </span>
      {sub && <span className="text-[8px] text-sumi-600">{sub}</span>}
    </div>
  );
}

/* ─── Heartbeat Waveform ─────────────────────────────────── */

function Heartbeat({
  data,
  tick,
  noMotion,
}: {
  data: number[];
  tick: number;
  noMotion: boolean;
}) {
  const points = useMemo(() => {
    const w = 400;
    const h = 80;
    const step = w / (data.length - 1 || 1);
    return data
      .map((v, i) => {
        const jitter = noMotion ? 0 : Math.sin(tick * 0.4 + i * 0.7) * 1.5;
        const y = h - v * h * 0.85 - 6 + jitter;
        return `${i * step},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [data, tick, noMotion]);

  const gradientId = "hb-grad";

  return (
    <svg viewBox="0 0 400 80" className="h-20 w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={colors.aozora} stopOpacity={0.4} />
          <stop offset="100%" stopColor={colors.aozora} stopOpacity={0} />
        </linearGradient>
        <filter id="hb-glow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      {/* Fill area */}
      <polygon
        points={`0,80 ${points} 400,80`}
        fill={`url(#${gradientId})`}
      />
      {/* Line */}
      <polyline
        points={points}
        fill="none"
        stroke={colors.aozora}
        strokeWidth="2"
        strokeLinejoin="round"
        filter="url(#hb-glow)"
      />
      {/* Current value dot */}
      {data.length > 0 && (
        <circle
          cx="400"
          cy={80 - data[data.length - 1] * 80 * 0.85 - 6}
          r="3"
          fill={colors.aozora}
          opacity={noMotion ? 1 : 0.5 + Math.sin(tick * 0.5) * 0.5}
        >
          {!noMotion && (
            <animate
              attributeName="r"
              values="3;5;3"
              dur="2s"
              repeatCount="indefinite"
            />
          )}
        </circle>
      )}
    </svg>
  );
}

/* ─── Health Ring ─────────────────────────────────────────── */

function HealthRing({
  layers,
  tick,
  noMotion,
}: {
  layers: { name: string; value: number; color: string; tip: string }[];
  tick: number;
  noMotion: boolean;
}) {
  const size = 180;
  const cx = size / 2;
  const cy = size / 2;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} className="h-full w-full">
        {layers.map((layer, i) => {
          const r = 28 + i * 14;
          const circumference = 2 * Math.PI * r;
          const filled = layer.value * circumference;
          const pulse = noMotion ? 0 : Math.sin(tick * 0.3 + i * 1.2) * 2;

          return (
            <g key={layer.name}>
              {/* Background ring */}
              <circle
                cx={cx}
                cy={cy}
                r={r}
                fill="none"
                stroke="rgba(56,58,68,0.25)"
                strokeWidth="6"
              />
              {/* Filled arc */}
              <circle
                cx={cx}
                cy={cy}
                r={r}
                fill="none"
                stroke={layer.color}
                strokeWidth="6"
                strokeDasharray={`${filled + pulse} ${circumference}`}
                strokeDashoffset={circumference * 0.25}
                strokeLinecap="round"
                opacity={0.6 + layer.value * 0.4}
                style={{
                  filter:
                    layer.value > 0.6
                      ? `drop-shadow(0 0 4px ${layer.color})`
                      : "none",
                  transition: "stroke-dasharray 1s ease",
                }}
              />
            </g>
          );
        })}
        {/* Center label */}
        <text
          x={cx}
          y={cx - 6}
          textAnchor="middle"
          fill={colors.sumi[600]}
          fontSize="8"
          fontWeight="600"
        >
          SYSTEM
        </text>
        <text
          x={cx}
          y={cx + 6}
          textAnchor="middle"
          fill={colors.sumi[600]}
          fontSize="8"
          fontWeight="600"
        >
          HEALTH
        </text>
      </svg>
      {/* Ring labels */}
      {layers.map((layer, i) => {
        const r = 28 + i * 14;
        const angle = -Math.PI / 2 + layer.value * Math.PI * 2 * 0.95;
        const lx = cx + Math.cos(angle) * r;
        const ly = cy + Math.sin(angle) * r;
        return (
          <div
            key={layer.name}
            className="group absolute"
            style={{ left: lx - 4, top: ly - 4, width: 8, height: 8 }}
          >
            <div
              className="h-full w-full rounded-full"
              style={{
                background: layer.color,
                boxShadow: `0 0 6px ${layer.color}`,
              }}
            />
            <div className="pointer-events-none absolute bottom-full left-1/2 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-sumi-900 px-2 py-1 text-[9px] text-torinoko shadow group-hover:block">
              {layer.name}: {Math.round(layer.value * 100)}%
              <br />
              <span className="text-sumi-600">{layer.tip}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ─── Priority Radar ─────────────────────────────────────── */

function PriorityRadar({
  priorities,
  tick,
  noMotion,
}: {
  priorities: { name: string; value: number; color: string; count: number }[];
  tick: number;
  noMotion: boolean;
}) {
  const size = 180;
  const cx = size / 2;
  const cy = size / 2;
  const maxR = 75;
  const n = priorities.length;

  const points = useMemo(() => {
    return priorities.map((p, i) => {
      const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
      const jitter = noMotion ? 0 : Math.sin(tick * 0.25 + i * 2) * 3;
      const r = p.value * maxR + jitter;
      return {
        x: cx + Math.cos(angle) * r,
        y: cy + Math.sin(angle) * r,
        labelX: cx + Math.cos(angle) * (maxR + 16),
        labelY: cy + Math.sin(angle) * (maxR + 16),
        axisX: cx + Math.cos(angle) * maxR,
        axisY: cy + Math.sin(angle) * maxR,
        ...p,
      };
    });
  }, [priorities, tick, noMotion, n]);

  const polygon = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="h-full w-full">
      {/* Grid rings */}
      {[0.25, 0.5, 0.75, 1].map((pct) => (
        <circle
          key={pct}
          cx={cx}
          cy={cy}
          r={maxR * pct}
          fill="none"
          stroke="rgba(56,58,68,0.2)"
          strokeWidth="0.5"
        />
      ))}
      {/* Axis lines */}
      {points.map((p, i) => (
        <line
          key={i}
          x1={cx}
          y1={cy}
          x2={p.axisX}
          y2={p.axisY}
          stroke="rgba(56,58,68,0.2)"
          strokeWidth="0.5"
        />
      ))}
      {/* Filled polygon */}
      <polygon
        points={polygon}
        fill={`${colors.aozora}15`}
        stroke={colors.aozora}
        strokeWidth="1.5"
        strokeLinejoin="round"
        style={{ filter: "drop-shadow(0 0 6px rgba(79,209,217,0.3))" }}
      />
      {/* Dots + labels */}
      {points.map((p, i) => (
        <g key={i}>
          <circle
            cx={p.x}
            cy={p.y}
            r={3}
            fill={p.color}
            style={{ filter: `drop-shadow(0 0 4px ${p.color})` }}
          />
          <text
            x={p.labelX}
            y={p.labelY}
            textAnchor="middle"
            dominantBaseline="middle"
            fill={colors.kitsurubami}
            fontSize="7"
            fontWeight="600"
          >
            {p.name}
          </text>
          <text
            x={p.labelX}
            y={p.labelY + 10}
            textAnchor="middle"
            dominantBaseline="middle"
            fill={p.color}
            fontSize="8"
            fontWeight="700"
            fontFamily="monospace"
          >
            {p.count}
          </text>
        </g>
      ))}
    </svg>
  );
}

/* ─── Main Component ─────────────────────────────────────── */

export default function OperatorMicrographics() {
  const prefersReducedMotion = useReducedMotion() ?? false;
  const { overview } = useOverview();
  const { health } = useHealth();
  const { agents } = useAgents();

  const { data: fitnessTrend } = useQuery<FitnessTrendPoint[]>({
    queryKey: ["fitness-trend-micro"],
    queryFn: () => apiFetch("/api/evolution/fitness-trend"),
    refetchInterval: 15_000,
  });

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    return localStorage.getItem(COLLAPSED_KEY) !== "false";
  });

  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (collapsed || prefersReducedMotion) return;
    const id = setInterval(() => setTick((t) => t + 1), 1400);
    return () => clearInterval(id);
  }, [collapsed, prefersReducedMotion]);

  function toggle() {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(COLLAPSED_KEY, String(next));
      return next;
    });
  }

  /* ── Derived metrics ─────────────────────────────────── */

  const agentCount = overview?.agent_count ?? agents.length;
  const tasksDone = overview?.tasks_completed ?? 0;
  const tasksFailed = overview?.tasks_failed ?? 0;
  const taskCount = overview?.task_count ?? 0;
  const tracesHr = health?.traces_last_hour ?? 0;
  const fitness = overview?.mean_fitness ?? 0;
  const evoEntries = overview?.evolution_entries ?? 0;
  const stigDensity = overview?.stigmergy_density ?? 0;
  const anomalyCount = health?.anomalies?.length ?? 0;
  const healthStatus = overview?.health_status ?? "unknown";

  // Heartbeat data: fitness trend padded to 28 points
  const heartbeatData = useMemo(() => {
    const raw = (fitnessTrend ?? []).slice(-28).map((f) => f.fitness);
    while (raw.length < 28) raw.unshift(raw[0] ?? 0.45);
    return raw;
  }, [fitnessTrend]);

  // Completion rate
  const completionRate = taskCount > 0 ? tasksDone / taskCount : 0;

  // Agent diversity
  const providers = new Set(agents.map((a) => a.provider)).size;
  const models = new Set(agents.map((a) => a.model)).size;
  const roles = new Set(agents.map((a) => a.role)).size;
  const busyAgents = agents.filter((a) => a.status === "busy").length;

  // Health layers for ring
  const agentHealth = health?.agent_health ?? [];
  const meanSuccess =
    agentHealth.length > 0
      ? agentHealth.reduce((s, h) => s + h.success_rate, 0) / agentHealth.length
      : 0;

  const healthLayers = [
    {
      name: "Operations",
      value: completionRate,
      color: completionRate > 0.5 ? colors.rokusho : completionRate > 0.2 ? colors.kinpaku : colors.bengara,
      tip: `${tasksDone} of ${taskCount} tasks completed`,
    },
    {
      name: "Coordination",
      value: Math.min(1, stigDensity / 1500),
      color: stigDensity > 500 ? colors.rokusho : stigDensity > 100 ? colors.kinpaku : colors.bengara,
      tip: `${stigDensity} stigmergy marks (pheromone trails)`,
    },
    {
      name: "Agent Health",
      value: meanSuccess,
      color: meanSuccess > 0.8 ? colors.rokusho : meanSuccess > 0.5 ? colors.kinpaku : colors.bengara,
      tip: `${Math.round(meanSuccess * 100)}% mean success across ${agentHealth.length} agents`,
    },
    {
      name: "Evolution",
      value: Math.min(1, evoEntries / 150),
      color: evoEntries > 50 ? colors.rokusho : evoEntries > 10 ? colors.kinpaku : colors.bengara,
      tip: `${evoEntries} self-improvement cycles completed`,
    },
    {
      name: "Fitness",
      value: fitness,
      color: fitness > 0.6 ? colors.rokusho : fitness > 0.4 ? colors.kinpaku : colors.bengara,
      tip: `System quality score: ${(fitness * 100).toFixed(0)}%`,
    },
  ];

  // Priority radar
  const priorities = [
    { name: "Agents", value: Math.min(1, agentCount / 30), color: colors.aozora, count: agentCount },
    { name: "Tasks", value: Math.min(1, taskCount / 100), color: colors.botan, count: taskCount },
    { name: "Evolution", value: Math.min(1, evoEntries / 150), color: colors.kinpaku, count: evoEntries },
    { name: "Traces", value: Math.min(1, (health?.total_traces ?? 0) / 1500), color: colors.rokusho, count: health?.total_traces ?? 0 },
    { name: "Stigmergy", value: Math.min(1, stigDensity / 1500), color: colors.fuji, count: stigDensity },
  ];

  // Status color
  const statusColor =
    healthStatus === "healthy" ? colors.rokusho
    : healthStatus === "degraded" ? colors.kinpaku
    : colors.bengara;

  /* ── Render ──────────────────────────────────────────── */

  return (
    <section className="glass-panel relative overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3">
        <div className="flex items-center gap-3">
          <div
            className="h-2 w-2 rounded-full"
            style={{
              background: statusColor,
              boxShadow: `0 0 8px ${statusColor}`,
            }}
          />
          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-kitsurubami">
            System Status
          </span>
          <span
            className="rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider"
            style={{
              color: statusColor,
              background: `color-mix(in srgb, ${statusColor} 12%, transparent)`,
            }}
          >
            {healthStatus}
          </span>
        </div>

        <button
          onClick={toggle}
          className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[10px] text-sumi-600 transition-colors hover:text-aozora"
          aria-label={collapsed ? "Expand diagnostics" : "Collapse diagnostics"}
        >
          {collapsed ? "expand" : "collapse"}
          {collapsed ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
        </button>
      </div>

      {/* Collapsed strip */}
      {collapsed && (
        <div className="flex items-center gap-6 border-t border-sumi-700/20 px-5 py-2">
          <Pill
            label="Activity"
            value={tracesHr > 0 ? `${tracesHr}/hr` : "quiet"}
            color={tracesHr > 10 ? colors.aozora : tracesHr > 0 ? colors.kinpaku : colors.bengara}
            tip="Actions performed by agents in the last hour"
          />
          <Pill
            label="Fitness"
            value={`${(fitness * 100).toFixed(0)}%`}
            color={fitness > 0.6 ? colors.rokusho : fitness > 0.4 ? colors.kinpaku : colors.bengara}
            tip="Overall system quality score from self-improvement cycles"
          />
          <Pill
            label="Fleet"
            value={`${busyAgents}/${agentCount}`}
            sub="active"
            color={busyAgents > 0 ? colors.aozora : colors.sumi[600]}
            tip={`${busyAgents} agents working, ${agentCount} total in swarm`}
          />
          <Pill
            label="Tasks"
            value={`${tasksDone}/${taskCount}`}
            sub={`${tasksFailed} failed`}
            color={tasksFailed > tasksDone ? colors.bengara : colors.rokusho}
            tip="Tasks completed vs total dispatched"
          />
          <Pill
            label="Diversity"
            value={`${providers}p ${models}m ${roles}r`}
            color={providers > 3 ? colors.rokusho : colors.kinpaku}
            tip={`${providers} providers, ${models} models, ${roles} roles — more diversity = stronger swarm`}
          />
          <Pill
            label="Evolution"
            value={evoEntries}
            sub="cycles"
            color={evoEntries > 50 ? colors.rokusho : colors.kinpaku}
            tip="Times the system has improved its own code"
          />
          {anomalyCount > 0 && (
            <Pill
              label="Anomalies"
              value={anomalyCount}
              color={colors.bengara}
              tip="Detected issues requiring attention"
            />
          )}
        </div>
      )}

      {/* Expanded panels */}
      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{
              duration: prefersReducedMotion ? 0 : 0.35,
              ease: [0.22, 1, 0.36, 1],
            }}
            className="overflow-hidden"
          >
            <div className="grid grid-cols-1 gap-4 border-t border-sumi-700/20 px-5 py-4 xl:grid-cols-3">
              {/* ── Panel 1: System Pulse ────────────────── */}
              <div className="glass-panel-subtle p-4">
                <div className="mb-1 flex items-center gap-2">
                  <h3 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-kitsurubami">
                    System Pulse
                  </h3>
                  <Tip text="The system's heartbeat — each peak is a period of high activity. Flat line means the swarm is idle." />
                </div>
                <p className="mb-3 text-[9px] text-sumi-600">
                  How active and alive the swarm is right now
                </p>

                <Heartbeat data={heartbeatData} tick={tick} noMotion={prefersReducedMotion} />

                {/* Key stats below waveform */}
                <div className="mt-3 grid grid-cols-3 gap-3">
                  <div>
                    <p className="text-[8px] font-semibold uppercase tracking-widest text-sumi-600">
                      Activity
                    </p>
                    <p className="font-mono text-sm font-bold" style={{ color: tracesHr > 0 ? colors.aozora : colors.bengara }}>
                      {tracesHr > 0 ? `${tracesHr}/hr` : "idle"}
                    </p>
                  </div>
                  <div>
                    <p className="text-[8px] font-semibold uppercase tracking-widest text-sumi-600">
                      Fitness
                    </p>
                    <p className="font-mono text-sm font-bold" style={{ color: fitness > 0.5 ? colors.rokusho : colors.kinpaku }}>
                      {(fitness * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-[8px] font-semibold uppercase tracking-widest text-sumi-600">
                      Anomalies
                    </p>
                    <p className="font-mono text-sm font-bold" style={{ color: anomalyCount > 0 ? colors.bengara : colors.rokusho }}>
                      {anomalyCount}
                    </p>
                  </div>
                </div>
              </div>

              {/* ── Panel 2: System Health Ring ──────────── */}
              <div className="glass-panel-subtle flex flex-col items-center p-4">
                <div className="mb-1 flex w-full items-center gap-2">
                  <h3 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-kitsurubami">
                    System Health
                  </h3>
                  <Tip text="Five concentric rings — each represents a layer of the system. Fuller rings = healthier layers. Hover the dots for details." />
                </div>
                <p className="mb-2 w-full text-[9px] text-sumi-600">
                  Each ring is a system layer — hover dots for detail
                </p>

                <HealthRing layers={healthLayers} tick={tick} noMotion={prefersReducedMotion} />

                {/* Legend */}
                <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1">
                  {healthLayers.map((l) => (
                    <div key={l.name} className="flex items-center gap-1.5">
                      <div
                        className="h-1.5 w-1.5 rounded-full"
                        style={{ background: l.color, boxShadow: `0 0 4px ${l.color}60` }}
                      />
                      <span className="text-[8px] text-sumi-600">{l.name}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* ── Panel 3: Swarm Shape ─────────────────── */}
              <div className="glass-panel-subtle p-4">
                <div className="mb-1 flex items-center gap-2">
                  <h3 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-kitsurubami">
                    Swarm Shape
                  </h3>
                  <Tip text="A radar showing the swarm's capabilities. Each axis is a dimension — a balanced shape means a healthy system. Lopsided = gaps." />
                </div>
                <p className="mb-2 text-[9px] text-sumi-600">
                  Capability profile — balanced shape is healthy
                </p>

                <div style={{ width: 180, height: 180, margin: "0 auto" }}>
                  <PriorityRadar priorities={priorities} tick={tick} noMotion={prefersReducedMotion} />
                </div>

                {/* Fleet summary */}
                <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                  <div>
                    <p className="text-[8px] font-semibold uppercase tracking-widest text-sumi-600">
                      Fleet
                    </p>
                    <p className="font-mono text-xs font-bold text-aozora">
                      {agentCount}
                    </p>
                  </div>
                  <div>
                    <p className="text-[8px] font-semibold uppercase tracking-widest text-sumi-600">
                      Diversity
                    </p>
                    <p className="font-mono text-xs font-bold text-botan">
                      {providers}p·{models}m·{roles}r
                    </p>
                  </div>
                  <div>
                    <p className="text-[8px] font-semibold uppercase tracking-widest text-sumi-600">
                      Active
                    </p>
                    <p className="font-mono text-xs font-bold" style={{ color: busyAgents > 0 ? colors.rokusho : colors.sumi[600] }}>
                      {busyAgents}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
