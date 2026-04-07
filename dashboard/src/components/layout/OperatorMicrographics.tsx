"use client";

import {
  useEffect,
  useId,
  useMemo,
  useState,
  type CSSProperties,
} from "react";
import { motion, useReducedMotion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp } from "lucide-react";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { colors } from "@/lib/theme";
import { useOverview } from "@/hooks/useOverview";
import { useHealth } from "@/hooks/useHealth";
import { useAgents } from "@/hooks/useAgents";
import { apiFetch } from "@/lib/api";
import type { FitnessTrendPoint, AgentOut, HealthOut, SwarmOverview } from "@/lib/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type LensId = "pulse" | "vsm" | "telos";

interface LensDef {
  id: LensId;
  label: string;
  accent: string;
  summary: string;
}

const LENSES: LensDef[] = [
  {
    id: "pulse",
    label: "System Pulse",
    accent: colors.aozora,
    summary: "Fitness trend, loop closure events, and module health across the living system.",
  },
  {
    id: "vsm",
    label: "VSM Health",
    accent: colors.botan,
    summary: "Beer's Viable System Model: 5 regulatory levels × 7 system domains.",
  },
  {
    id: "telos",
    label: "Telos Vector",
    accent: colors.kinpaku,
    summary: "Ontological priority orbits and telos coherence score across the swarm.",
  },
];

const COLLAPSED_KEY = "dharma-micrographics-collapsed";

const VSM_ROWS = ["S5 Identity", "S4 Intel", "S3 Control", "S2 Coord", "S1 Ops", "Variety"];
const VSM_COLS = ["CTL", "LIV", "EVO", "STG", "AGT", "TEL", "ECO"];

const MODULE_LABELS = ["CTL", "CRN", "LIV", "JGK", "MYC", "TRI", "EVO"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function routeLens(pathname: string): LensId {
  if (pathname.includes("/agents") || pathname.includes("/tasks")) return "vsm";
  if (pathname.includes("/evolution") || pathname.includes("/telos")) return "telos";
  return "pulse";
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function sparkle(value: number, accent: string): CSSProperties {
  const alpha = clamp(10 + value * 70, 10, 78);
  return {
    background: `color-mix(in srgb, ${accent} ${alpha}%, ${colors.sumi[900]})`,
    boxShadow: `0 0 14px color-mix(in srgb, ${accent} ${Math.round(alpha * 0.55)}%, transparent)`,
  };
}

function hoursAgo(iso: string): number {
  const ts = new Date(iso).getTime();
  return (Date.now() - ts) / 3_600_000;
}

function buildVSMMatrix(
  overview: SwarmOverview | null,
  health: HealthOut | null,
  agents: AgentOut[],
  fitnessTrend: FitnessTrendPoint[] | undefined,
): number[][] {
  const agentCount = agents.length;
  const agentHealth = health?.agent_health ?? [];
  const meanSuccess =
    agentHealth.length > 0
      ? agentHealth.reduce((s, h) => s + h.success_rate, 0) / agentHealth.length
      : 0;

  const stigmergyDensity = clamp((overview?.stigmergy_density ?? 0) / 100, 0, 1);
  const evolutionEntries = overview?.evolution_entries ?? 0;
  const isHealthy = overview?.health_status === "healthy";
  const meanFitness = overview?.mean_fitness ?? 0;
  const taskCompletionRate =
    (overview?.tasks_completed ?? 0) /
    Math.max(1, (overview?.task_count ?? 1));

  // Distinct providers, models, roles
  const providers = new Set(agents.map((a) => a.provider).filter(Boolean));
  const models = new Set(agents.map((a) => a.model).filter(Boolean));
  const roles = new Set(agents.map((a) => a.role).filter(Boolean));
  const varietyScore = clamp(
    (providers.size / 4 + models.size / 6 + roles.size / 8) / 3,
    0,
    1,
  );

  // Latest fitness point
  const latestFitness =
    fitnessTrend && fitnessTrend.length > 0
      ? fitnessTrend[fitnessTrend.length - 1].fitness
      : 0;

  // 6 rows × 7 cols: CTL, LIV, EVO, STG, AGT, TEL, ECO
  //                   0    1    2    3    4    5    6
  const matrix: number[][] = [
    // S5 Identity — mostly dim (telos gates not actively running)
    [0.28, 0.12, clamp(latestFitness * 0.9, 0, 1), 0.18, 0.35, 0.22, 0.08],
    // S4 Intelligence — evolution, ontology
    [0.2, 0.3, clamp(evolutionEntries > 0 ? 0.7 + latestFitness * 0.25 : 0.15, 0, 1), 0.45, 0.35, 0.55, 0.1],
    // S3 Control — orchestration, health status
    [clamp(isHealthy ? 0.75 : 0.35, 0, 1), 0.22, 0.48, 0.3, clamp(meanSuccess, 0, 1), 0.4, 0.18],
    // S2 Coordination — stigmergy
    [0.12, clamp(stigmergyDensity * 1.2, 0, 1), 0.3, clamp(stigmergyDensity * 1.5, 0, 1), 0.38, 0.28, 0.1],
    // S1 Operations — task throughput, agents
    [clamp(taskCompletionRate, 0, 1), 0.55, clamp(latestFitness, 0, 1), 0.62, clamp(meanSuccess, 0, 1), 0.35, 0.28],
    // Variety — diversity across providers/models/roles
    [varietyScore * 0.8, varietyScore * 0.6, varietyScore, varietyScore * 0.5, clamp(agentCount / 20, 0, 1), varietyScore * 0.7, varietyScore * 0.4],
  ];

  return matrix;
}

function cellColor(value: number): string {
  if (value > 0.6) return colors.aozora;
  if (value > 0.3) return colors.kinpaku;
  return colors.bengara;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MiniReadout({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div className="rounded-xl border border-sumi-700/35 bg-sumi-900/70 px-3 py-2">
      <p className="font-mono uppercase tracking-[0.12em] text-sumi-600">{label}</p>
      <p className="mt-1 font-heading text-sm" style={{ color: accent }}>
        {value}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function OperatorMicrographics() {
  const pathname = usePathname();
  const prefersReducedMotion = useReducedMotion();
  const sparkGradientId = useId();
  const coreGradientId = useId();

  const defaultLens = useMemo(() => routeLens(pathname), [pathname]);
  const [activeLens, setActiveLens] = useState<LensId>(defaultLens);
  const [tick, setTick] = useState(0);
  const [focusBar, setFocusBar] = useState(24);
  const [focusCell, setFocusCell] = useState<number | null>(null);

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    const stored = window.localStorage.getItem(COLLAPSED_KEY);
    return stored === null ? true : stored === "true";
  });

  // Data hooks
  const { overview } = useOverview();
  const { health } = useHealth();
  const { agents } = useAgents();

  const { data: fitnessTrend } = useQuery<FitnessTrendPoint[]>({
    queryKey: ["fitness-trend-micro"],
    queryFn: () => apiFetch<FitnessTrendPoint[]>("/api/evolution/fitness-trend"),
    refetchInterval: 15_000,
  });

  const { data: modulesRaw } = useQuery<unknown[]>({
    queryKey: ["modules-micro"],
    queryFn: () => apiFetch<unknown[]>("/api/modules"),
    refetchInterval: 30_000,
  });

  // Sync lens with route
  useEffect(() => {
    setActiveLens(defaultLens);
  }, [defaultLens]);

  // Tick timer — only when expanded
  useEffect(() => {
    if (prefersReducedMotion) return;
    if (collapsed) return;
    const handle = window.setInterval(() => {
      setTick((v) => v + 1);
    }, 1400);
    return () => window.clearInterval(handle);
  }, [prefersReducedMotion, collapsed]);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(COLLAPSED_KEY, String(next));
      return next;
    });
  }

  const lens = LENSES.find((l) => l.id === activeLens) ?? LENSES[0];

  // ---------------------------------------------------------------------------
  // PANEL 1: System Pulse — sparkline
  // ---------------------------------------------------------------------------

  const sparklineValues = useMemo<number[]>(() => {
    const raw = fitnessTrend ?? [];
    // Take up to 28 points; pad with ~0.45 baseline if fewer
    const pts = raw.slice(-28).map((p) => p.fitness);
    while (pts.length < 28) pts.unshift(0.45);
    // Add subtle jitter per tick
    return pts.map((v, i) =>
      clamp(v + (prefersReducedMotion ? 0 : Math.sin(tick * 0.3 + i * 0.5) * 0.015), 0.05, 0.98),
    );
  }, [fitnessTrend, tick, prefersReducedMotion]);

  const sparklinePath = useMemo(() => {
    return sparklineValues
      .map((v, i) => {
        const x = 8 + i * 14.2;
        const y = 92 - v * 60;
        return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");
  }, [sparklineValues]);

  // Loop closure indicators
  const evolutionStaleHours = useMemo(() => {
    const raw = fitnessTrend ?? [];
    if (raw.length === 0) return Infinity;
    return hoursAgo(raw[raw.length - 1].timestamp);
  }, [fitnessTrend]);

  const stigmergyActive = (overview?.stigmergy_density ?? 0) > 0;

  // Module pips — derive from modulesRaw if present, else from overview health
  const modulePips = useMemo(() => {
    if (modulesRaw && modulesRaw.length >= 7) {
      return (modulesRaw as Array<{ status?: string; live?: boolean }>)
        .slice(0, 7)
        .map((m) => {
          if (m.live === true || m.status === "alive") return "alive" as const;
          if (m.status === "stale") return "stale" as const;
          return "dead" as const;
        });
    }
    // Fallback: derive from overview health
    const isHealthy = overview?.health_status === "healthy";
    return MODULE_LABELS.map((_, i) => {
      if (!isHealthy) return i < 3 ? ("stale" as const) : ("dead" as const);
      return i < 4 ? ("alive" as const) : ("stale" as const);
    });
  }, [modulesRaw, overview]);

  const aliveModules = modulePips.filter((s) => s === "alive").length;

  // Readout values
  const tracesPerHour = health?.traces_last_hour ?? overview?.task_count ?? 0;
  const nonStaleLoops = [
    evolutionStaleHours < 24,
    stigmergyActive,
    false, // Metabolic always stale for now
  ].filter(Boolean).length;

  // ---------------------------------------------------------------------------
  // PANEL 2: VSM Matrix
  // ---------------------------------------------------------------------------

  const vsmMatrix = useMemo(
    () => buildVSMMatrix(overview, health, agents, fitnessTrend),
    [overview, health, agents, fitnessTrend],
  );

  const vsmActiveRows = useMemo(
    () =>
      vsmMatrix.filter(
        (row) => row.reduce((s, v) => s + v, 0) / row.length > 0.3,
      ).length,
    [vsmMatrix],
  );

  const distinctProviders = useMemo(
    () => new Set(agents.map((a) => a.provider).filter(Boolean)).size,
    [agents],
  );
  const distinctModels = useMemo(
    () => new Set(agents.map((a) => a.model).filter(Boolean)).size,
    [agents],
  );
  const distinctRoles = useMemo(
    () => new Set(agents.map((a) => a.role).filter(Boolean)).size,
    [agents],
  );
  const varietyLabel = `${distinctProviders}p·${distinctModels}m·${distinctRoles}r`;

  // ---------------------------------------------------------------------------
  // PANEL 3: Telos Vector — orbital diagram
  // ---------------------------------------------------------------------------

  const TCS = 0.39;
  const tcsState = TCS >= 0.7 ? "COHERENT" : TCS >= 0.5 ? "STABILIZING" : "DRIFTING";
  const tcsStateColor = TCS >= 0.7 ? colors.rokusho : TCS >= 0.5 ? colors.kinpaku : colors.bengara;

  const orbits = useMemo(
    () => [
      { name: "witness", telos: 1.0, color: colors.aozora, instances: 0, r: 20 },
      { name: "experiment", telos: 0.95, color: colors.rokusho, instances: 0, r: 38 },
      { name: "venture", telos: 0.95, color: colors.kinpaku, instances: 0, r: 56 },
      { name: "agent", telos: 0.9, color: colors.botan, instances: agents.length, r: 74 },
      { name: "task", telos: 0.7, color: colors.fuji, instances: overview?.task_count ?? 0, r: 92 },
    ],
    [agents.length, overview?.task_count],
  );

  // Animated particle positions per orbit (CSS animation via inline keyframes is not feasible here;
  // we drive positions via tick so the particles move without CSS @keyframes)
  const particlePositions = useMemo(() => {
    return orbits.map((orbit, oi) => {
      const speed = (8 - Math.min(5, orbit.instances / 20)) * 0.1; // radians/tick
      const angle1 = tick * speed * (0.08 + oi * 0.012);
      const angle2 = angle1 + Math.PI;
      return {
        p1: {
          x: 110 + Math.cos(angle1) * orbit.r,
          y: 110 + Math.sin(angle1) * orbit.r,
        },
        p2: {
          x: 110 + Math.cos(angle2) * orbit.r,
          y: 110 + Math.sin(angle2) * orbit.r,
        },
        opacity: Math.min(1, 0.2 + orbit.instances / 50),
      };
    });
  }, [orbits, tick]);

  // ---------------------------------------------------------------------------
  // Collapsed strip values
  // ---------------------------------------------------------------------------

  const focusValue = sparklineValues[focusBar] ?? sparklineValues[sparklineValues.length - 1];

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <section className="glass-panel relative overflow-hidden px-5 py-4">
      {/* Background gradient */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            `radial-gradient(circle at 12% 20%, color-mix(in srgb, ${lens.accent} 18%, transparent), transparent 28%), ` +
            `radial-gradient(circle at 88% 15%, color-mix(in srgb, ${colors.fuji} 12%, transparent), transparent 22%), ` +
            `linear-gradient(135deg, rgba(255,255,255,0.015), transparent 65%)`,
        }}
      />

      <div className="relative flex flex-col gap-4">
        {/* Header row */}
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex-1">
            <div className="mb-1 flex items-center gap-2">
              <span
                className="rounded-full px-2 py-1 font-mono text-[10px] uppercase tracking-[0.18em]"
                style={{
                  color: lens.accent,
                  background: `color-mix(in srgb, ${lens.accent} 12%, transparent)`,
                }}
              >
                Operator Micrographics
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-sumi-600">
                {pathname.replace("/dashboard", "dashboard") || "dashboard"}
              </span>
              <button
                type="button"
                aria-label={collapsed ? "Expand micrographics" : "Collapse micrographics"}
                onClick={toggleCollapsed}
                className="ml-auto flex items-center gap-1 rounded-full border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] transition-all"
                style={{
                  color: colors.sumi[600],
                  borderColor: `${colors.sumi[700]}66`,
                  background: `${colors.sumi[900]}99`,
                }}
              >
                {collapsed ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
              </button>
            </div>
            <h2
              className="font-heading text-lg font-semibold tracking-tight"
              style={{ color: lens.accent }}
            >
              Cybernetic system state — live swarm telemetry
            </h2>
            {!collapsed && (
              <p className="mt-1 max-w-3xl text-sm text-sumi-600">{lens.summary}</p>
            )}
          </div>

          {/* Lens buttons — shown when expanded */}
          {!collapsed && (
            <div className="flex flex-wrap gap-2">
              {LENSES.map((item) => {
                const active = item.id === activeLens;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setActiveLens(item.id)}
                    className="rounded-full border px-3 py-1.5 font-mono text-[11px] tracking-[0.12em] transition-all"
                    style={{
                      color: active ? item.accent : colors.sumi[600],
                      borderColor: active
                        ? `color-mix(in srgb, ${item.accent} 38%, transparent)`
                        : `${colors.sumi[700]}66`,
                      background: active
                        ? `color-mix(in srgb, ${item.accent} 12%, transparent)`
                        : `${colors.sumi[900]}99`,
                      boxShadow: active
                        ? `0 0 18px color-mix(in srgb, ${item.accent} 18%, transparent)`
                        : "none",
                    }}
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>
          )}

          {/* Collapsed strip */}
          {collapsed && (
            <div className="flex flex-wrap items-center gap-4 font-mono text-[11px]">
              <span className="text-sumi-600">
                Pulse <span style={{ color: colors.aozora }}>{tracesPerHour}/hr</span>
              </span>
              <span className="text-sumi-600">
                Loops <span style={{ color: colors.kinpaku }}>{nonStaleLoops}/3</span>
              </span>
              <span className="text-sumi-600">
                Modules <span style={{ color: colors.rokusho }}>{aliveModules}/7</span>
              </span>
              <span className="text-sumi-600">
                VSM <span style={{ color: colors.botan }}>{vsmActiveRows}/5</span>
              </span>
              <span className="text-sumi-600">
                Variety <span style={{ color: colors.fuji }}>{varietyLabel}</span>
              </span>
              <span className="text-sumi-600">
                TCS <span style={{ color: colors.kinpaku }}>{TCS.toFixed(2)}</span>
              </span>
              <span style={{ color: tcsStateColor }}>{tcsState}</span>
            </div>
          )}
        </div>

        {/* Expanded body */}
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.div
              key="micrographics-body"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={
                prefersReducedMotion
                  ? { duration: 0 }
                  : { duration: 0.28, ease: "easeInOut" }
              }
              style={{ overflow: "hidden" }}
            >
              <div className="grid gap-4 xl:grid-cols-[1.15fr_1fr_0.92fr]">

                {/* ============================================================
                    PANEL 1: SYSTEM PULSE
                ============================================================ */}
                <motion.div
                  layout
                  className="glass-panel-subtle overflow-hidden p-4"
                  onMouseMove={(event) => {
                    const rect = event.currentTarget.getBoundingClientRect();
                    const ratio = clamp((event.clientX - rect.left) / rect.width, 0, 0.999);
                    setFocusBar(Math.floor(ratio * sparklineValues.length));
                  }}
                >
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-sumi-600">
                        System Pulse
                      </p>
                      <p className="font-heading text-sm text-torinoko">
                        Fitness trend + loop closure events
                      </p>
                    </div>
                    <span
                      className="rounded-full px-2 py-1 font-mono text-[10px]"
                      style={{
                        color: colors.aozora,
                        background: `color-mix(in srgb, ${colors.aozora} 10%, transparent)`,
                      }}
                    >
                      {(focusValue * 100).toFixed(0)}%
                    </span>
                  </div>

                  {/* Sparkline SVG */}
                  <svg viewBox="0 0 400 110" className="h-28 w-full">
                    <defs>
                      <linearGradient id={sparkGradientId} x1="0" x2="1">
                        <stop offset="0%" stopColor={colors.aozora} stopOpacity="0.15" />
                        <stop offset="100%" stopColor={colors.fuji} stopOpacity="0.28" />
                      </linearGradient>
                    </defs>
                    {sparklineValues.map((v, i) => {
                      const x = 8 + i * 14.2;
                      const h = v * 62;
                      const isFocus = i === focusBar;
                      return (
                        <rect
                          key={i}
                          x={x - 3}
                          y={102 - h}
                          width="6"
                          height={h}
                          rx="3"
                          fill={isFocus ? colors.aozora : `${colors.sumi[700]}77`}
                          opacity={isFocus ? 0.95 : 0.34}
                        />
                      );
                    })}
                    <path
                      d={`${sparklinePath} L 392 104 L 8 104 Z`}
                      fill={`url(#${sparkGradientId})`}
                      opacity="0.28"
                    />
                    <path
                      d={sparklinePath}
                      fill="none"
                      stroke={colors.aozora}
                      strokeWidth="2.4"
                      strokeLinecap="round"
                    />
                    <circle
                      cx={8 + focusBar * 14.2}
                      cy={92 - focusValue * 60}
                      r="5.5"
                      fill={colors.aozora}
                      style={{ filter: `drop-shadow(0 0 8px ${colors.aozora})` }}
                    />
                  </svg>

                  {/* Loop closure indicators */}
                  <div className="mt-3 flex flex-wrap gap-3">
                    {/* Evolution */}
                    <div className="flex items-center gap-1.5">
                      <div
                        className="h-[5px] w-[5px] rounded-full"
                        style={{
                          background: evolutionStaleHours < 24 ? colors.rokusho : colors.bengara,
                          boxShadow:
                            evolutionStaleHours < 24
                              ? `0 0 4px ${colors.rokusho}`
                              : "none",
                        }}
                      />
                      <span
                        className="font-mono text-[8px]"
                        style={{
                          color: evolutionStaleHours < 24 ? colors.rokusho : colors.bengara,
                        }}
                      >
                        Evolution{" "}
                        {evolutionStaleHours < 24
                          ? `${evolutionStaleHours.toFixed(0)}h ago`
                          : "stale"}
                      </span>
                    </div>
                    {/* Stigmergy */}
                    <div className="flex items-center gap-1.5">
                      <div
                        className="h-[5px] w-[5px] rounded-full"
                        style={{
                          background: stigmergyActive ? colors.aozora : colors.kinpaku,
                          boxShadow: stigmergyActive ? `0 0 4px ${colors.aozora}` : "none",
                        }}
                      />
                      <span
                        className="font-mono text-[8px]"
                        style={{ color: stigmergyActive ? colors.aozora : colors.kinpaku }}
                      >
                        Stigmergy {stigmergyActive ? "active" : "sparse"}
                      </span>
                    </div>
                    {/* Metabolic */}
                    <div className="flex items-center gap-1.5">
                      <div
                        className="h-[5px] w-[5px] rounded-full"
                        style={{ background: colors.bengara }}
                      />
                      <span className="font-mono text-[8px]" style={{ color: colors.bengara }}>
                        Metabolic stale
                      </span>
                    </div>
                  </div>

                  {/* Module pips */}
                  <div className="mt-3">
                    <span className="font-mono text-[7px] uppercase tracking-[0.08em] text-sumi-600">
                      Modules
                    </span>
                    <div className="mt-1.5 flex gap-1.5">
                      {MODULE_LABELS.map((label, i) => {
                        const status = modulePips[i] ?? "dead";
                        const pipColor =
                          status === "alive"
                            ? colors.rokusho
                            : status === "stale"
                              ? colors.kinpaku
                              : colors.bengara;
                        return (
                          <div key={label} className="flex flex-col items-center gap-[3px]">
                            <div
                              className="h-2 w-2 rounded-full"
                              style={{
                                background: pipColor,
                                boxShadow:
                                  status === "alive" ? `0 0 5px ${pipColor}88` : "none",
                              }}
                            />
                            <span
                              className="font-mono text-[6px]"
                              style={{ color: colors.sumi[600] }}
                            >
                              {label}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Readout */}
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <MiniReadout label="Pulse" value={`${tracesPerHour}/hr`} accent={colors.aozora} />
                    <MiniReadout label="Loops" value={`${nonStaleLoops}/3`} accent={colors.kinpaku} />
                    <MiniReadout label="Modules" value={`${aliveModules}/7`} accent={colors.rokusho} />
                  </div>
                </motion.div>

                {/* ============================================================
                    PANEL 2: VIABLE SYSTEM MATRIX
                ============================================================ */}
                <motion.div layout className="glass-panel-subtle p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-sumi-600">
                        Viable System Matrix
                      </p>
                      <p className="font-heading text-sm text-torinoko">
                        Beer VSM levels × system domains
                      </p>
                    </div>
                    <span className="font-mono text-[11px]" style={{ color: colors.botan }}>
                      {vsmActiveRows}/5
                    </span>
                  </div>

                  {/* Grid: header row + 6 data rows */}
                  <div className="overflow-x-auto">
                    <div
                      className="grid gap-[3px]"
                      style={{
                        gridTemplateColumns: "60px repeat(7, 1fr)",
                        minWidth: 280,
                      }}
                    >
                      {/* Column headers */}
                      <div />
                      {VSM_COLS.map((col) => (
                        <div
                          key={col}
                          className="py-[2px] text-center font-mono"
                          style={{ fontSize: 7, color: colors.sumi[600], letterSpacing: "0.05em" }}
                        >
                          {col}
                        </div>
                      ))}

                      {/* Data rows */}
                      {VSM_ROWS.map((rowName, ri) => (
                        <>
                          <div
                            key={`row-${ri}`}
                            className="flex items-center font-mono"
                            style={{
                              fontSize: 7,
                              color: colors.kitsurubami,
                              letterSpacing: "0.05em",
                              fontWeight: 600,
                            }}
                          >
                            {rowName}
                          </div>
                          {vsmMatrix[ri]?.map((value, ci) => {
                            const cellIdx = ri * 7 + ci;
                            const isFocus = focusCell === cellIdx;
                            const col = cellColor(value);
                            const alpha = clamp(10 + value * 70, 10, 78);
                            return (
                              <button
                                key={`cell-${ri}-${ci}`}
                                type="button"
                                aria-label={`VSM ${rowName} × ${VSM_COLS[ci]}`}
                                onMouseEnter={() => setFocusCell(cellIdx)}
                                onMouseLeave={() => setFocusCell(null)}
                                className="h-[18px] rounded-[3px] transition-transform duration-150 hover:scale-110"
                                style={{
                                  background: `color-mix(in srgb, ${col} ${alpha}%, ${colors.sumi[900]})`,
                                  boxShadow:
                                    value > 0.7
                                      ? `0 0 6px color-mix(in srgb, ${col} 35%, transparent)`
                                      : "none",
                                  outline: isFocus ? `1px solid ${col}` : "none",
                                }}
                              />
                            );
                          })}
                        </>
                      ))}
                    </div>
                  </div>

                  <div className="mt-3 h-px bg-sumi-700/40" />

                  {/* Readout */}
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <MiniReadout label="VSM Active" value={`${vsmActiveRows}/5`} accent={colors.aozora} />
                    <MiniReadout label="Variety" value={varietyLabel} accent={colors.botan} />
                    <MiniReadout label="Fleet" value={`${agents.length}`} accent={colors.kinpaku} />
                  </div>
                </motion.div>

                {/* ============================================================
                    PANEL 3: TELOS VECTOR
                ============================================================ */}
                <motion.div layout className="glass-panel-subtle p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <div>
                      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-sumi-600">
                        Telos Vector
                      </p>
                      <p className="font-heading text-sm text-torinoko">
                        Ontological priority orbits + coherence
                      </p>
                    </div>
                    <span className="font-mono text-[11px]" style={{ color: colors.kinpaku }}>
                      TCS {TCS.toFixed(2)}
                    </span>
                  </div>

                  <div className="flex items-center justify-center">
                    <svg viewBox="0 0 220 220" className="h-52 w-52 max-w-full">
                      <defs>
                        <radialGradient id={coreGradientId}>
                          <stop offset="0%" stopColor={colors.aozora} stopOpacity="0.38" />
                          <stop offset="100%" stopColor={colors.aozora} stopOpacity="0" />
                        </radialGradient>
                      </defs>

                      {/* Orbit rings */}
                      {orbits.map((orbit) => (
                        <circle
                          key={`ring-${orbit.name}`}
                          cx="110"
                          cy="110"
                          r={orbit.r}
                          fill="none"
                          stroke={`color-mix(in srgb, ${orbit.color} 12%, transparent)`}
                          strokeWidth="1"
                        />
                      ))}

                      {/* Core glow */}
                      <circle cx="110" cy="110" r="16" fill={`url(#${coreGradientId})`} />
                      <circle cx="110" cy="110" r="6" fill={colors.aozora} opacity="0.4" />

                      {/* TCS label */}
                      <text
                        x="110"
                        y="107"
                        textAnchor="middle"
                        fill={colors.sumi[600]}
                        fontSize="6"
                        fontWeight="600"
                      >
                        TCS
                      </text>
                      <text
                        x="110"
                        y="117"
                        textAnchor="middle"
                        fill={colors.kinpaku}
                        fontSize="8"
                        fontWeight="700"
                        fontFamily="monospace"
                      >
                        {TCS.toFixed(2)}
                      </text>

                      {/* Orbit particles */}
                      {orbits.map((orbit, oi) => {
                        const pos = particlePositions[oi];
                        if (!pos) return null;
                        const show = orbit.instances > 0 || oi < 2; // always show witness/experiment
                        return (
                          <g key={`particles-${orbit.name}`}>
                            <circle
                              cx={pos.p1.x}
                              cy={pos.p1.y}
                              r={3.5 - oi * 0.2}
                              fill={orbit.color}
                              opacity={show ? pos.opacity : 0.15}
                              style={
                                show
                                  ? { filter: `drop-shadow(0 0 4px ${orbit.color})` }
                                  : undefined
                              }
                            />
                            {(orbit.instances > 10 || oi === 3) && (
                              <circle
                                cx={pos.p2.x}
                                cy={pos.p2.y}
                                r={2.5 - oi * 0.1}
                                fill={orbit.color}
                                opacity={pos.opacity * 0.55}
                              />
                            )}
                          </g>
                        );
                      })}

                      {/* Orbit labels */}
                      {orbits.map((orbit, oi) => (
                        <text
                          key={`label-${orbit.name}`}
                          x={120 + orbit.r * 0.22}
                          y={96 - oi * 14}
                          fill={orbit.color}
                          fontSize="6"
                          opacity="0.6"
                        >
                          {orbit.name}
                        </text>
                      ))}
                    </svg>
                  </div>

                  {/* Readout */}
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    <MiniReadout label="TCS" value={TCS.toFixed(2)} accent={colors.kinpaku} />
                    <MiniReadout label="State" value={tcsState} accent={tcsStateColor} />
                    <MiniReadout label="Focus" value="alignment" accent={colors.fuji} />
                  </div>
                </motion.div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}
