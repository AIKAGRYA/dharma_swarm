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

interface Zone {
  id: ZoneId;
  label: string;
  verb: string;
  routes: { path: string; label: string }[];
}

const ZONES: Zone[] = [
  {
    id: "cockpit",
    label: "COCKPIT",
    verb: "act",
    routes: [
      { path: "/dashboard/control-surface", label: "Control Surface" },
      { path: "/dashboard/command-post", label: "Command Post" },
      { path: "/dashboard/synthesizer", label: "Synthesizer" },
    ],
  },
  {
    id: "talk",
    label: "TALK",
    verb: "converse",
    routes: [
      { path: "/dashboard/claude", label: "Claude" },
      { path: "/dashboard/glm5", label: "GLM-5" },
      { path: "/dashboard/qwen35", label: "Qwen-3.5" },
      { path: "/dashboard/models", label: "Models" },
    ],
  },
  {
    id: "watch",
    label: "WATCH",
    verb: "observe",
    routes: [
      { path: "/dashboard/observatory", label: "Observatory" },
      { path: "/dashboard/runtime", label: "Runtime" },
      { path: "/dashboard/telemetry", label: "Telemetry" },
    ],
  },
  {
    id: "judge",
    label: "JUDGE",
    verb: "evaluate",
    routes: [
      { path: "/dashboard/eval", label: "Eval" },
      { path: "/dashboard/gates", label: "Gates" },
    ],
  },
  {
    id: "map",
    label: "MAP",
    verb: "relate",
    routes: [
      { path: "/dashboard/ontology", label: "Ontology" },
      { path: "/dashboard/lineage", label: "Lineage" },
      { path: "/dashboard/ecosystem", label: "Ecosystem" },
      { path: "/dashboard/modules", label: "Modules" },
    ],
  },
  {
    id: "sense",
    label: "SENSE",
    verb: "trails",
    routes: [
      { path: "/dashboard/stigmergy", label: "Stigmergy" },
      { path: "/dashboard/evolution", label: "Evolution" },
    ],
  },
  {
    id: "remember",
    label: "REMEMBER",
    verb: "recall",
    routes: [
      { path: "/dashboard/log", label: "Log" },
      { path: "/dashboard/timeline", label: "Timeline" },
    ],
  },
];

function activeZoneFor(pathname: string | null): Zone | null {
  if (!pathname) return null;
  return ZONES.find((z) => z.routes.some((r) => pathname.startsWith(r.path))) ?? null;
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

export { ZONES, type Zone, type ZoneId };
