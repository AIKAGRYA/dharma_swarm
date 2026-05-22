"use client";

/**
 * ZoneTabs — verb-shaped zone navigation per command-plane Phase 4 plan.
 *
 * Collapses the 30+ scattered /dashboard/* routes into 7 verb zones:
 *   COCKPIT (act)   · TALK (converse) · WATCH (observe) · JUDGE (evaluate)
 *   MAP (relate)    · SENSE (trails)  · REMEMBER (recall)
 *
 * Detects current pathname; renders the tab strip for the active zone or
 * nothing if the route isn't yet zone-grouped. Per Nihonga design lock:
 * hairline 1px borders, mono ALLCAPS labels, no drop shadow, active tab
 * carries the aozora active accent only.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { colors } from "@/lib/theme";

type ZoneId = "cockpit" | "talk" | "watch" | "judge" | "map" | "sense" | "remember";

interface ZoneRoute {
  path: string;
  label: string;
  description: string;
}

interface Zone {
  id: ZoneId;
  label: string;
  verb: string;
  description: string;
  landingPath: string;
  routes: ZoneRoute[];
}

const ZONES: Zone[] = [
  {
    id: "cockpit",
    label: "COCKPIT",
    verb: "act",
    landingPath: "/dashboard/cockpit",
    description: "Operator surface. Dirty rows, needs-john queue, evidence drawer, runtime rail.",
    routes: [
      { path: "/dashboard/control-surface", label: "Control Surface", description: "Five-zone operator cockpit: needs-john queue, system truth matrix, evidence drawer, runtime rail." },
      { path: "/dashboard/command-post", label: "Command Post", description: "Active-track view, pending PRs, governance gate status." },
      { path: "/dashboard/synthesizer", label: "Synthesizer", description: "Synthesis surface for combining signals across zones." },
    ],
  },
  {
    id: "talk",
    label: "TALK",
    verb: "converse",
    landingPath: "/dashboard/talk",
    description: "Per-provider transcript surfaces. Local + cloud frontier models.",
    routes: [
      { path: "/dashboard/claude", label: "Claude", description: "Claude Opus / Sonnet / Haiku transcripts and tool-use." },
      { path: "/dashboard/glm5", label: "GLM-5", description: "Z.ai GLM-5 744B — free frontier tier-1." },
      { path: "/dashboard/qwen35", label: "Qwen-3.5", description: "Alibaba Qwen-3.5 / Qwen-3-32B telemetry." },
      { path: "/dashboard/models", label: "Models", description: "Cross-provider model hierarchy and availability." },
    ],
  },
  {
    id: "watch",
    label: "WATCH",
    verb: "observe",
    landingPath: "/dashboard/watch",
    description: "Fleet-wide observability. Agent health, runtime control plane, routing telemetry.",
    routes: [
      { path: "/dashboard/observatory", label: "Observatory", description: "Agent fitness grid, leaderboard, anomaly feed, activity timeline." },
      { path: "/dashboard/runtime", label: "Runtime", description: "Chat profiles, control-plane sync, transport mode, operator handbook." },
      { path: "/dashboard/telemetry", label: "Telemetry", description: "Routing topology, economic flow, policy interventions, outcomes." },
    ],
  },
  {
    id: "judge",
    label: "JUDGE",
    verb: "evaluate",
    landingPath: "/dashboard/judge",
    description: "Evaluation surfaces. Eval results, audit trails, gate status.",
    routes: [
      { path: "/dashboard/eval", label: "Eval", description: "Run evaluations, view scores per skill / agent / model." },
      { path: "/dashboard/gates", label: "Gates", description: "Telos / dharmic / pre-commit gate status across the kernel." },
    ],
  },
  {
    id: "map",
    label: "MAP",
    verb: "relate",
    landingPath: "/dashboard/map",
    description: "Topology surfaces. Concepts, lineage, ecosystem graph, module dependencies.",
    routes: [
      { path: "/dashboard/ontology", label: "Ontology", description: "Concept graph, definitions, relations across the kernel." },
      { path: "/dashboard/lineage", label: "Lineage", description: "Mutation lineage and provenance trails." },
      { path: "/dashboard/ecosystem", label: "Ecosystem", description: "Cross-system links — Claude Code, dharma_swarm, MI research." },
      { path: "/dashboard/modules", label: "Modules", description: "500+ module dependency graph and ownership map." },
    ],
  },
  {
    id: "sense",
    label: "SENSE",
    verb: "trails",
    landingPath: "/dashboard/sense",
    description: "Pheromone trails and self-modification. Hot paths, marks, evolution archive.",
    routes: [
      { path: "/dashboard/stigmergy", label: "Stigmergy", description: "Pheromone marks, hot paths, stigmergic coordination signals." },
      { path: "/dashboard/evolution", label: "Evolution", description: "DarwinEngine fitness trends, archive, diversity-preserving selection." },
    ],
  },
  {
    id: "remember",
    label: "REMEMBER",
    verb: "recall",
    landingPath: "/dashboard/remember",
    description: "Session memory. Captured sessions, timeline, atom revival queue.",
    routes: [
      { path: "/dashboard/log", label: "Log", description: "Session captures, decisions, problems, insights." },
      { path: "/dashboard/timeline", label: "Timeline", description: "Chronological event stream across the kernel." },
    ],
  },
];

function activeZoneFor(pathname: string | null): Zone | null {
  if (!pathname) return null;
  return (
    ZONES.find(
      (z) =>
        pathname === z.landingPath ||
        pathname.startsWith(z.landingPath + "/") ||
        z.routes.some((r) => pathname.startsWith(r.path)),
    ) ?? null
  );
}

export function ZoneTabs() {
  const pathname = usePathname();
  const zone = activeZoneFor(pathname);

  if (!zone) return null;

  return (
    <nav
      aria-label={`${zone.label} zone navigation`}
      style={{
        borderBottom: `1px solid ${colors.sumi[700]}`,
        backgroundColor: colors.sumi[900],
      }}
    >
      <div className="flex items-center gap-3 px-3" style={{ height: 32 }}>
        {/* Zone label */}
        <span
          className="font-mono text-xs uppercase tabular-nums"
          style={{
            letterSpacing: "0.14em",
            color: colors.aozora,
            fontWeight: 500,
          }}
        >
          {zone.label}
        </span>
        <span
          className="font-mono text-[10px] uppercase"
          style={{ color: colors.sumi[600], letterSpacing: "0.10em" }}
        >
          {zone.verb}
        </span>

        <span style={{ color: colors.sumi[700] }}>·</span>

        {/* Route tabs */}
        <div className="flex items-center gap-1">
          {zone.routes.map((route) => {
            const active = pathname === route.path || pathname?.startsWith(route.path + "/");
            return (
              <Link
                key={route.path}
                href={route.path}
                className="font-mono text-xs uppercase"
                style={{
                  padding: "4px 8px",
                  letterSpacing: "0.10em",
                  color: active ? colors.aozora : colors.sumi[600],
                  borderBottom: active
                    ? `1px solid ${colors.aozora}`
                    : "1px solid transparent",
                  marginBottom: -1,
                  transition: "color 100ms cubic-bezier(0.2, 0, 0, 1)",
                }}
              >
                {route.label}
              </Link>
            );
          })}
        </div>

        <div className="flex-1" />

        {/* Zone switcher hint */}
        <span
          className="font-mono text-[10px] uppercase hidden md:inline"
          style={{ color: colors.sumi[600], letterSpacing: "0.10em" }}
        >
          {ZONES.length} zones · ⌘K
        </span>
      </div>
    </nav>
  );
}

export { ZONES, type Zone, type ZoneId, type ZoneRoute };
