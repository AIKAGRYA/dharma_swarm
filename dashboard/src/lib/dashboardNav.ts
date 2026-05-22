import { ZONES, type ZoneRoute, type ZoneId } from "@/components/dashboard/ZoneTabs";
export { isDashboardPathActive } from "./dashboardPath.js";

export type DashboardNavIcon =
  | "Activity"
  | "Bot"
  | "Brain"
  | "BrainCircuit"
  | "ClipboardCheck"
  | "Dna"
  | "GitBranch"
  | "Globe"
  | "Grid3X3"
  | "HeartPulse"
  | "LayoutDashboard"
  | "ListTodo"
  | "MessageSquare"
  | "Microscope"
  | "Network"
  | "Orbit"
  | "Settings2"
  | "Shield"
  | "Sparkles"
  | "Workflow";

export interface DashboardNavItem {
  label: string;
  href: string;
  icon: DashboardNavIcon;
  level: number;
}

export interface DashboardNavSection {
  label: string;
  level: number;
  items: DashboardNavItem[];
}

// ---------------------------------------------------------------------------
// Phase 4 zone IA — sidebar now reads from the ZONES single source of truth
// in components/dashboard/ZoneTabs.tsx. Per-route icons + per-zone landing
// icon are looked up here so ZoneTabs/CommandPalette stay icon-free.
// ---------------------------------------------------------------------------

const ROUTE_ICONS: Record<string, DashboardNavIcon> = {
  "/dashboard/control-surface": "Settings2",
  "/dashboard/command-post": "LayoutDashboard",
  "/dashboard/synthesizer": "Sparkles",
  "/dashboard/claude": "Brain",
  "/dashboard/glm5": "Brain",
  "/dashboard/qwen35": "Brain",
  "/dashboard/models": "Sparkles",
  "/dashboard/observatory": "Microscope",
  "/dashboard/runtime": "Activity",
  "/dashboard/telemetry": "Activity",
  "/dashboard/eval": "ClipboardCheck",
  "/dashboard/gates": "Shield",
  "/dashboard/ontology": "Globe",
  "/dashboard/lineage": "GitBranch",
  "/dashboard/ecosystem": "Orbit",
  "/dashboard/modules": "Grid3X3",
  "/dashboard/stigmergy": "Network",
  "/dashboard/evolution": "Dna",
  "/dashboard/log": "MessageSquare",
  "/dashboard/timeline": "Activity",
};

const ZONE_LANDING_ICONS: Record<ZoneId, DashboardNavIcon> = {
  cockpit: "LayoutDashboard",
  talk: "MessageSquare",
  watch: "Activity",
  judge: "ClipboardCheck",
  map: "Globe",
  sense: "Network",
  remember: "MessageSquare",
};

function iconFor(path: string): DashboardNavIcon {
  return ROUTE_ICONS[path] ?? "Activity";
}

function zoneItems(zoneRoutes: ZoneRoute[]): DashboardNavItem[] {
  return zoneRoutes.map((r) => ({
    label: r.label,
    href: r.path,
    icon: iconFor(r.path),
    level: 1,
  }));
}

// Orphan surfaces not yet folded into the 7-zone IA. Kept honest in
// their own section rather than force-fit into a zone. Phase 5 ADR will
// either zone them or sunset them.
const ORPHAN_ITEMS: DashboardNavItem[] = [
  { label: "Overview", href: "/dashboard", icon: "LayoutDashboard", level: 1 },
  { label: "Goodworks", href: "/dashboard/goodworks", icon: "HeartPulse", level: 1 },
  { label: "Agents", href: "/dashboard/agents", icon: "Bot", level: 1 },
  { label: "Tasks", href: "/dashboard/tasks", icon: "ListTodo", level: 1 },
  { label: "Audit", href: "/dashboard/audit", icon: "HeartPulse", level: 3 },
  { label: "Workflows", href: "/dashboard/workflows", icon: "Workflow", level: 5 },
  { label: "Blocks", href: "/dashboard/blocks", icon: "Grid3X3", level: 5 },
];

export function buildDashboardNavSections(): DashboardNavSection[] {
  const zoneSections: DashboardNavSection[] = ZONES.map((zone) => ({
    label: zone.label,
    level: 1,
    items: [
      {
        label: `${zone.label} · ${zone.verb}`,
        href: zone.landingPath,
        icon: ZONE_LANDING_ICONS[zone.id],
        level: 1,
      },
      ...zoneItems(zone.routes),
    ],
  }));

  return [
    {
      label: "ENTRY",
      level: 1,
      items: ORPHAN_ITEMS.filter((i) => i.href === "/dashboard"),
    },
    ...zoneSections,
    {
      label: "TO-MIGRATE",
      level: 1,
      items: ORPHAN_ITEMS.filter((i) => i.href !== "/dashboard"),
    },
  ];
}
