import type {LayoutMode, PaneKind} from "../types";

export type HelmPlace = "home" | "conversation" | "activity" | "evidence" | "system";
export type HelmPlane = "conversation" | "ecosystem" | "causal";
export type HelmViewportProfile = "panorama" | "standard" | "compact" | "survival" | "resize-safe";

export const HELM_PLACES: readonly HelmPlace[] = [
  "home",
  "conversation",
  "activity",
  "evidence",
  "system",
] as const;

export function usesNihongaShell(layoutMode: LayoutMode): boolean {
  return !layoutMode.startsWith("deck-focus:");
}

export function contextControlForLayout(layoutMode: LayoutMode): "navigator" | "legacy-sidebar" {
  return usesNihongaShell(layoutMode) ? "navigator" : "legacy-sidebar";
}

const PLACE_LABELS: Readonly<Record<HelmPlace, string>> = {
  home: "Home",
  conversation: "Conversation",
  activity: "Activity",
  evidence: "Evidence",
  system: "System",
};

const PLACE_BY_PANE: Readonly<Record<PaneKind, HelmPlace>> = {
  chat: "conversation",
  commands: "system",
  agents: "activity",
  models: "system",
  evolution: "activity",
  thinking: "activity",
  tools: "activity",
  timeline: "activity",
  sessions: "conversation",
  approvals: "activity",
  mission: "home",
  runtime: "system",
  repo: "evidence",
  ontology: "evidence",
  control: "home",
};

export function viewportProfile(width: number, height: number): HelmViewportProfile {
  if (width < 44 || height < 18) {
    return "resize-safe";
  }
  if (width >= 120 && height >= 30) {
    return "panorama";
  }
  if (width >= 100 && height >= 28) {
    return "standard";
  }
  if (width >= 80 && height >= 24) {
    return "compact";
  }
  return "survival";
}

export function placeForPane(kind: PaneKind | undefined): HelmPlace {
  return kind ? PLACE_BY_PANE[kind] : "home";
}

export function placeLabel(place: HelmPlace): string {
  return PLACE_LABELS[place];
}

export function planeForPane(kind: PaneKind | undefined): HelmPlane {
  const place = placeForPane(kind);
  if (place === "conversation") {
    return "conversation";
  }
  // Facets render in the 35% contextual plane. The 20% causal plane remains
  // a correlated proof companion; selecting Activity must not highlight a
  // different panel from the one that actually owns keyboard focus.
  return "ecosystem";
}

export function workspaceLabel(cwd: string): string {
  const segments = cwd.replaceAll("\\", "/").split("/").filter(Boolean);
  const terminalIndex = segments.lastIndexOf("terminal");
  const workspaceIndex = terminalIndex >= 0 ? terminalIndex - 1 : segments.length - 1;
  const candidate = segments[workspaceIndex];
  if (!candidate) {
    return "workspace";
  }
  if (candidate === "dharma_swarm" || candidate.startsWith("wt_helm_") || candidate.startsWith("ds_helm_")) {
    return "dharma_swarm";
  }
  return candidate;
}
