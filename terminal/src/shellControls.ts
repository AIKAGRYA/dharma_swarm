import type {AppState, TabSpec} from "./types";
import {routeLabel} from "./routePolicy";

export type PaneAction = {
  label: string;
  summary: string;
  requestType?: string;
  payload: Record<string, unknown>;
};

type PaneActionsOptions = {
  sessionCatalogLimit: number;
};

export function paneActionsFor(
  tabId: string,
  state: AppState,
  options: PaneActionsOptions,
): {refresh: PaneAction; primary?: PaneAction; secondary?: PaneAction; tertiary?: PaneAction} {
  const {sessionCatalogLimit} = options;
  const modelTarget = routeLabel(state.routePolicy);
  switch (tabId) {
    case "repo":
      return {
        refresh: {label: "refresh repo", summary: "refresh repo snapshot", payload: {action_type: "surface.refresh", surface: "repo"}},
        primary: {label: "/git", summary: "run /git", payload: {action_type: "command.run", command: "/git"}},
      };
    case "commands":
      return {
        refresh: {label: "refresh commands", summary: "refresh command registry", payload: {action_type: "surface.refresh", surface: "commands"}},
        primary: {label: "/runtime", summary: "run /runtime", payload: {action_type: "command.run", command: "/runtime"}},
        secondary: {label: "/git", summary: "run /git", payload: {action_type: "command.run", command: "/git"}},
        tertiary: {label: "/foundations", summary: "run /foundations", payload: {action_type: "command.run", command: "/foundations"}},
      };
    case "models":
      return {
        refresh: {
          label: "refresh models",
          summary: "refresh model policy",
          requestType: "model.policy",
          payload: {
            provider: state.routePolicy.provider,
            model: state.routePolicy.model,
            strategy: state.routePolicy.strategy,
          },
        },
        primary: {label: "claude opus", summary: "route to Claude Opus 5.0 genius", payload: {action_type: "model.set", provider: "claude", model: "claude-opus-5.0", strategy: "genius"}},
        secondary: {label: "codex responsive", summary: "route to GPT-5.5 responsive", payload: {action_type: "model.set", provider: "codex", model: "gpt-5.5", strategy: "responsive"}},
        tertiary: {
          label: "cost on current",
          summary: `apply cost strategy to ${modelTarget}`,
          payload: {
            action_type: "model.set",
            provider: state.routePolicy.provider,
            model: state.routePolicy.model,
            strategy: "cost",
          },
        },
      };
    case "ontology":
      return {
        refresh: {label: "refresh ontology", summary: "refresh ontology snapshot", payload: {action_type: "surface.refresh", surface: "ontology"}},
        primary: {label: "/foundations", summary: "run /foundations", payload: {action_type: "command.run", command: "/foundations"}},
        secondary: {label: "/context", summary: "run /context", payload: {action_type: "command.run", command: "/context"}},
      };
    case "control":
    case "runtime":
      return {
        refresh: {label: "refresh control", summary: "refresh runtime snapshot", requestType: "runtime.snapshot", payload: {}},
        primary: {label: "/runtime", summary: "run /runtime", payload: {action_type: "command.run", command: "/runtime"}},
        secondary: {label: "/dashboard", summary: "run /dashboard", payload: {action_type: "command.run", command: "/dashboard"}},
      };
    case "agents":
      return {
        refresh: {label: "refresh agents", summary: "refresh operator and routing view", requestType: "agent.routes", payload: {}},
        primary: {label: "deep_code_work", summary: "preview deep-code route", payload: {action_type: "agent.route", intent: "deep_code_work"}},
        secondary: {label: "/swarm", summary: "run /swarm", payload: {action_type: "command.run", command: "/swarm"}},
        tertiary: {label: "architecture_research", summary: "preview architecture route", payload: {action_type: "agent.route", intent: "architecture_research"}},
      };
    case "evolution":
      return {
        refresh: {label: "refresh evolution", summary: "refresh evolution surface", payload: {action_type: "surface.refresh", surface: "evolution"}},
        primary: {label: "/loops", summary: "open loops lane", payload: {action_type: "evolution.run", command: "/loops"}},
        secondary: {label: "/cascade code", summary: "prepare code cascade", payload: {action_type: "evolution.run", command: "/cascade code"}},
        tertiary: {label: "/evolve shell", summary: "prepare shell evolution", payload: {action_type: "evolution.run", command: "/evolve terminal forward"}},
      };
    case "sessions":
      return {
        refresh: {label: "refresh sessions", summary: "refresh session catalog", requestType: "session.catalog", payload: {limit: sessionCatalogLimit}},
        primary: state.bridgeStatus === "connected"
          && state.authoritativeSurfaces.sessions
          && state.sessionPane.selectedSessionId
          ? {
              label: "refresh detail",
              summary: "refresh selected session detail",
              requestType: "session.detail",
              payload: {session_id: state.sessionPane.selectedSessionId, transcript_limit: 40},
            }
          : undefined,
        secondary: {label: "/archive", summary: "run /archive", payload: {action_type: "command.run", command: "/archive"}},
        tertiary: {label: "/memory", summary: "run /memory", payload: {action_type: "command.run", command: "/memory"}},
      };
    case "approvals":
      return {
        refresh: {label: "refresh approvals", summary: "refresh approval history", requestType: "permission.history", payload: {limit: 50}},
      };
    default:
      return {
        refresh: {label: "refresh shell", summary: "refresh live snapshots", payload: {action_type: "surface.refresh", surface: "control"}},
      };
  }
}

type InputModifiers = {
  ctrl?: boolean;
  meta?: boolean;
};

export function plainListDirection(input: string, key: InputModifiers): 1 | -1 | undefined {
  if (key.ctrl || key.meta) {
    return undefined;
  }
  if (input === "j") {
    return 1;
  }
  if (input === "k") {
    return -1;
  }
  return undefined;
}

export type PaneActionChordDecision =
  | {handled: false}
  | {handled: true; action?: PaneAction};

export function paneActionChordDecision(
  input: string,
  key: InputModifiers,
  tabId: string,
  state: AppState,
  options: PaneActionsOptions,
): PaneActionChordDecision {
  if (!key.ctrl) {
    return {handled: false};
  }
  const actions = paneActionsFor(tabId, state, options);
  switch (input) {
    case "l":
      return {handled: true, action: actions.refresh};
    case "x":
      return {handled: true, action: actions.primary};
    case "f":
      return {handled: true, action: actions.secondary};
    case "v":
      return {handled: true, action: actions.tertiary};
    default:
      return {handled: false};
  }
}

export function footerHintFor(
  tabId: string,
  state: AppState,
  options: PaneActionsOptions,
  compact = false,
): string {
  const withApprovalBoundary = (hint: string): string =>
    tabId === "approvals" ? `read-only history | ${hint}` : hint;
  if (state.uiMode.activeOverlay.kind === "paneSwitcher") {
    return withApprovalBoundary(
      compact ? "j/k choose | Enter jump | Esc close" : "j/k or ↑/↓ choose pane | Enter jump | Esc close | ^K switcher",
    );
  }
  if (state.uiMode.activeOverlay.kind === "modelPicker") {
    return withApprovalBoundary(
      compact ? "j/k choose | Enter apply | Esc close" : "j/k or ↑/↓ choose route | Enter apply | Esc close",
    );
  }
  if (state.uiMode.keyboardFocus === "composer") {
    return withApprovalBoundary(
      compact
        ? "compose | Enter send | ^J newline | Esc navigate"
        : "composer owns keys | Enter send | ^J newline | Esc navigation",
    );
  }
  if (compact) {
    const actions = paneActionsFor(tabId, state, options);
    const parts = ["navigate", "Esc compose", "Tab tabs", "↑/↓ scroll"];
    if (actions.primary) {
      parts.push(`^X ${actions.primary.label}`);
    }
    return withApprovalBoundary(parts.join(" | "));
  }
  const actions = paneActionsFor(tabId, state, options);
  const parts = [state.footerHint, "↑/↓ scroll", `^L ${actions.refresh.label}`];
  if (tabId === "sessions") {
    parts.push("j/k or ↑/↓ select");
    if (state.bridgeStatus === "connected" && state.authoritativeSurfaces.sessions) {
      parts.push("Enter refresh detail");
      parts.push("r arm resume");
    } else {
      parts.push("detail/resume held pending fresh catalog");
    }
    parts.push("f fresh");
  }
  if (tabId === "approvals") {
    parts.push("j/k or ↑/↓ select");
  }
  if (tabId === "models") {
    parts.push("j/k or ↑/↓ select route");
    parts.push("Enter apply");
  }
  if (tabId === "agents") {
    parts.push("j/k or ↑/↓ select route");
  }
  if (tabId === "repo" || tabId === "control" || tabId === "runtime") {
    parts.push("j/k or ↑/↓ move sections");
  }
  if (tabId === "thinking" || tabId === "tools" || tabId === "timeline") {
    parts.push(`^U ${state.activityFeed.visibilityMode === "compact" ? "expand detail" : "compact detail"}`);
    parts.push(`^I raw ${state.activityFeed.showRaw ? "off" : "on"}`);
  }
  if (tabId === "chat") {
    parts.push(`^U ${state.activityFeed.visibilityMode === "compact" ? "expand trace" : "compact trace"}`);
    parts.push(`^I raw ${state.activityFeed.showRaw ? "off" : "on"}`);
  }
  if (actions.primary) {
    parts.push(`^X ${actions.primary.label}`);
  }
  if (actions.secondary) {
    parts.push(`^F ${actions.secondary.label}`);
  }
  if (actions.tertiary) {
    parts.push(`^V ${actions.tertiary.label}`);
  }
  return withApprovalBoundary(parts.join(" | "));
}

export function focusModeFor(activeTab: TabSpec | undefined, state: AppState): string {
  if (state.uiMode.activeOverlay.kind === "paneSwitcher") {
    return "pane switcher";
  }
  if (state.uiMode.activeOverlay.kind === "modelPicker") {
    return "route selection";
  }
  if (state.uiMode.keyboardFocus === "composer") {
    return "compose · Esc navigate";
  }
  if (activeTab?.kind === "sessions") {
    return "session list";
  }
  if (activeTab?.kind === "approvals") {
    return "approval history · read-only";
  }
  if (activeTab?.kind === "repo" || activeTab?.kind === "control" || activeTab?.kind === "runtime") {
    return "pane section focus";
  }
  if (activeTab?.kind === "thinking" || activeTab?.kind === "tools" || activeTab?.kind === "timeline") {
    return "activity feed";
  }
  if (activeTab?.kind === "agents") {
    return "agent route selection";
  }
  return "navigate · Esc compose";
}
