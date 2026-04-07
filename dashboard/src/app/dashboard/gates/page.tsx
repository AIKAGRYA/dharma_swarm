"use client";

/**
 * DHARMA COMMAND -- Gates page (L3).
 * Dharma subsystem health view: kernel, corpus, compiler, canary, stigmergy.
 */

import { motion } from "framer-motion";
import {
  Shield,
  CheckCircle2,
  XCircle,
  BookOpen,
  Cpu,
  Wind,
  GitBranch,
  Hash,
  Activity,
} from "lucide-react";
import { useGates, type DharmaHealth } from "@/hooks/useGates";
import { colors } from "@/lib/theme";

interface SubsystemCard {
  key: keyof DharmaHealth;
  label: string;
  description: string;
  icon: typeof Shield;
  stats?: Array<{ key: keyof DharmaHealth; label: string; format?: (v: unknown) => string }>;
}

const subsystems: SubsystemCard[] = [
  {
    key: "kernel",
    label: "Dharma Kernel",
    description: "25 immutable axioms. SHA-256 signed. The constitution of the swarm.",
    icon: Shield,
    stats: [
      { key: "kernel_axioms", label: "Axioms", format: (v) => String(v ?? 0) },
      {
        key: "kernel_integrity",
        label: "Integrity",
        format: (v) => (v ? "Verified" : "Compromised"),
      },
    ],
  },
  {
    key: "corpus",
    label: "Dharma Corpus",
    description: "Versioned claims corpus. Living memory of validated truths.",
    icon: BookOpen,
    stats: [
      { key: "corpus_claims", label: "Claims", format: (v) => String(v ?? 0) },
    ],
  },
  {
    key: "compiler",
    label: "Policy Compiler",
    description: "Compiles telos gates and dharmic rules into executable policy.",
    icon: Cpu,
  },
  {
    key: "canary",
    label: "Canary Deployer",
    description: "Promote / rollback guard. Ensures safe incremental evolution.",
    icon: Wind,
  },
  {
    key: "stigmergy",
    label: "Stigmergy Store",
    description: "Pheromone-trail coordination. Indirect signaling across agents.",
    icon: GitBranch,
    stats: [
      {
        key: "stigmergy_density",
        label: "Density",
        format: (v) =>
          typeof v === "number" ? v.toFixed(4) : "—",
      },
    ],
  },
];

export default function GatesPage() {
  const { health, isLoading } = useGates();

  const activeCount = health
    ? subsystems.filter((s) => health[s.key] === true).length
    : 0;
  const totalCount = subsystems.length;
  const allHealthy = activeCount === totalCount;
  const overallColor = health
    ? allHealthy
      ? colors.rokusho
      : activeCount === 0
        ? colors.bengara
        : colors.kinpaku
    : colors.sumi[600];

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center gap-3">
          <Activity size={24} className="text-rokusho" />
          <h1 className="glow-rokusho font-heading text-2xl font-bold tracking-tight text-rokusho">
            Dharma Health
          </h1>
        </div>
        <p className="mt-1 text-sm text-sumi-600">
          {isLoading
            ? "Checking subsystem status..."
            : health
              ? `${activeCount} of ${totalCount} subsystems active`
              : "Awaiting dharma status."}
        </p>
      </motion.div>

      {/* Overall status banner */}
      {health && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-panel flex items-center gap-4 p-5"
        >
          <div
            className="flex h-12 w-12 items-center justify-center rounded-lg"
            style={{
              backgroundColor: `color-mix(in srgb, ${overallColor} 15%, transparent)`,
              border: `1px solid color-mix(in srgb, ${overallColor} 30%, transparent)`,
            }}
          >
            <Shield size={24} style={{ color: overallColor }} />
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-kitsurubami">
              System Status
            </p>
            <p
              className="font-heading text-xl font-bold uppercase"
              style={{ color: overallColor }}
            >
              {allHealthy ? "All Systems Operational" : activeCount === 0 ? "All Systems Down" : "Degraded"}
            </p>
          </div>
          <div className="ml-auto flex gap-6">
            <StatBadge
              label="Active"
              value={String(activeCount)}
              color={colors.rokusho}
            />
            <StatBadge
              label="Down"
              value={String(totalCount - activeCount)}
              color={colors.bengara}
            />
          </div>
        </motion.div>
      )}

      {/* Subsystem cards */}
      {isLoading ? (
        <div className="glass-panel flex items-center justify-center py-16">
          <p className="animate-pulse text-sm text-sumi-600">
            Loading dharma subsystems...
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {subsystems.map((sub, i) => (
            <SubsystemCard
              key={sub.key}
              sub={sub}
              health={health}
              index={i}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SubsystemCard
// ---------------------------------------------------------------------------

function SubsystemCard({
  sub,
  health,
  index,
}: {
  sub: SubsystemCard;
  health: DharmaHealth | null;
  index: number;
}) {
  const active = health ? health[sub.key] === true : false;
  const color = active ? colors.rokusho : colors.bengara;
  const Icon = sub.icon;
  const StatusIcon = active ? CheckCircle2 : XCircle;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.07 }}
      className="glass-panel p-5 space-y-4"
    >
      {/* Card header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-lg"
            style={{
              backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)`,
              border: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
            }}
          >
            <Icon size={16} style={{ color }} />
          </div>
          <h3
            className="font-heading text-sm font-bold tracking-wide"
            style={{ color }}
          >
            {sub.label}
          </h3>
        </div>
        <div className="flex items-center gap-1.5">
          <StatusIcon size={15} style={{ color }} />
          <span
            className="text-[10px] font-semibold uppercase tracking-wider"
            style={{ color }}
          >
            {active ? "Active" : "Down"}
          </span>
        </div>
      </div>

      {/* Description */}
      <p className="text-xs leading-relaxed text-sumi-600">{sub.description}</p>

      {/* Stats */}
      {sub.stats && health && (
        <div className="flex gap-4 border-t pt-3" style={{ borderColor: `color-mix(in srgb, ${colors.sumi[700]} 40%, transparent)` }}>
          {sub.stats.map((stat) => {
            const raw = health[stat.key];
            const display = stat.format ? stat.format(raw) : String(raw ?? "—");
            return (
              <div key={stat.key} className="flex items-center gap-2">
                <Hash size={10} className="text-sumi-600" />
                <span className="text-[10px] uppercase tracking-wider text-sumi-600">
                  {stat.label}
                </span>
                <span className="font-mono text-xs font-semibold" style={{ color }}>
                  {display}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// StatBadge
// ---------------------------------------------------------------------------

function StatBadge({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="flex flex-col items-center">
      <span className="font-mono text-lg font-bold" style={{ color }}>
        {value}
      </span>
      <span className="text-[9px] uppercase tracking-widest text-sumi-600">
        {label}
      </span>
    </div>
  );
}
