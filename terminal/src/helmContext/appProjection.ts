import {placeForPane} from "../nihonga/shellModel.ts";
import {
  helmContextEnvelopeFromEvent,
  helmContextEnvelopeIsUsableAt,
} from "../protocol/helmContext.ts";
import type {AppAction, AppState, PaneKind} from "../types.ts";
import {
  HELM_CONTEXT_PROJECTION_NAMES,
  type HelmContextEnvelope,
  type HelmContextProjectionName,
} from "./types.ts";

const AVAILABLE_NAVIGATION = [
  "home",
  "conversation",
  "activity",
  "evidence",
  "system",
] as const;

const OWNER_BY_REGION: Readonly<Record<HelmContextProjectionName, string>> = {
  workspace: "TerminalBridge",
  bridge_session: "TerminalBridge",
  ui: "NihongaShell",
  mission_control: "MissionControl",
  task_board: "TaskBoard",
  runtime_state: "RuntimeStateStore",
  session: "SessionStore",
  receipts: "RuntimeStateStore",
  swarm: "SwarmManager",
  a2a: "A2AContactRegistry",
  evolution: "EvolutionArchive",
  actions: "TerminalBridge",
};

const SOURCE_BY_REGION: Readonly<Record<HelmContextProjectionName, string>> = {
  workspace: "TerminalBridge.workspace_inventory",
  bridge_session: "terminal_bridge.session_runtime",
  ui: "helm.context.request.ui",
  mission_control: "MissionControl.get_snapshot",
  task_board: "TaskBoard.list_tasks",
  runtime_state: "RuntimeStateStore.read_projection",
  session: "SessionStore.list_sessions",
  receipts: "RuntimeStateStore.read_recent_receipts",
  swarm: "SwarmManager.status",
  a2a: "A2AContactRegistry.list_all",
  evolution: "EvolutionArchive.list_entries",
  actions: "terminal_bridge.action_projection",
};

const TRANSPORT_FAILURE_CODES = new Set([
  "bridge_exit",
  "bridge_spawn_error",
  "bridge_send_failed",
  "bridge_stdin_unavailable",
  "invalid_bridge_json",
]);

type PlainEvent = Readonly<Record<string, unknown>>;

function plainEvent(value: unknown): PlainEvent | undefined {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return undefined;
  }
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) {
    return undefined;
  }
  const descriptors = Object.getOwnPropertyDescriptors(value);
  if (
    Reflect.ownKeys(value).length !== Object.keys(value).length
    || Object.values(descriptors).some((descriptor) => (
      !Object.hasOwn(descriptor, "value") || !descriptor.enumerable
    ))
  ) {
    return undefined;
  }
  return value as PlainEvent;
}

function normalizedFace(layoutMode: AppState["uiMode"]["layoutMode"], facet: PaneKind): string {
  if (!layoutMode.startsWith("deck-focus:")) {
    return layoutMode;
  }
  return `deck-focus:${facet}`;
}

/**
 * Project only the six bounded, client-owned UI coordinates accepted by the
 * bridge. Authority, runtime epochs, and owner data deliberately have no slot
 * in this payload.
 */
export function helmContextRequestPayload(
  state: Pick<AppState, "uiMode" | "tabs">,
): Record<string, unknown> {
  const activeTab = state.tabs.find((tab) => tab.id === state.uiMode.activeTabId)
    ?? state.tabs[0];
  const facet = activeTab?.kind ?? "control";
  return {
    ui: {
      face: normalizedFace(state.uiMode.layoutMode, facet),
      place: placeForPane(facet),
      facet,
      overlay: state.uiMode.activeOverlay.kind,
      keyboard_focus: state.uiMode.keyboardFocus,
      available_navigation: [...AVAILABLE_NAVIGATION],
    },
  };
}

function eventIsTransportDisconnect(event: PlainEvent): boolean {
  const type = event.type;
  if (type === "bridge.disconnected" || type === "bridge.disconnect" || type === "bridge.closed") {
    return true;
  }
  return type === "bridge.error"
    && typeof event.code === "string"
    && TRANSPORT_FAILURE_CODES.has(event.code);
}

/**
 * Admit an owner envelope only when it is structurally valid, fresh at the
 * point of use, and correlated to the one request the UI currently owns.
 * Narrative booleans and other legacy readiness hints never participate.
 */
export function helmContextActionsForBridgeEvent(
  value: unknown,
  helmContext: AppState["helmContext"],
  now: Date = new Date(),
): AppAction[] {
  const event = plainEvent(value);
  if (!event) {
    return [];
  }
  if (eventIsTransportDisconnect(event)) {
    return [{type: "helm.context.reset"}];
  }

  const pendingRequestId = helmContext.pendingRequestId;
  if (!pendingRequestId) {
    return [];
  }
  const eventType = event.type;
  const requestId = event.request_id;

  if (eventType === "bridge.error") {
    return requestId === pendingRequestId ? [{type: "helm.context.reset"}] : [];
  }
  if (eventType !== "helm.context.result" || requestId !== pendingRequestId) {
    return [];
  }

  const decoded = helmContextEnvelopeFromEvent(event);
  if (!decoded || !helmContextEnvelopeIsUsableAt(decoded.envelope, now)) {
    return [{type: "helm.context.reset"}];
  }
  return [{type: "helm.context.set", envelope: decoded.envelope}];
}

function projectionLine(
  region: HelmContextProjectionName,
  fields: {
    status: string;
    owner: string;
    source: string;
    observed: string;
    expires: string;
    reason: string;
  },
): string {
  return `${region} · status=${fields.status} · owner=${fields.owner} · source=${fields.source} · observed=${fields.observed} · expires=${fields.expires} · reason=${fields.reason}`;
}

function unavailableProjectionLines(
  reason: string,
  envelope?: HelmContextEnvelope,
): string[] {
  return HELM_CONTEXT_PROJECTION_NAMES.map((region) => {
    const projection = envelope?.projections[region];
    return projectionLine(region, {
      status: "unavailable",
      owner: projection?.authority.owner ?? OWNER_BY_REGION[region],
      source: projection?.authority.source ?? `${SOURCE_BY_REGION[region]}:not_observed`,
      observed: projection?.authority.observed_at ?? "unavailable",
      expires: projection?.authority.expires_at ?? "none",
      reason,
    });
  });
}

/** Render all twelve owner regions; absence and expiry expand to typed rows. */
export function helmContextProjectionLines(
  helmContext: AppState["helmContext"],
  now: Date = new Date(),
): string[] {
  const envelope = helmContext.envelope;
  if (!envelope) {
    return unavailableProjectionLines("owner_projection_not_observed");
  }
  if (!helmContextEnvelopeIsUsableAt(envelope, now)) {
    return unavailableProjectionLines("context_expired", envelope);
  }
  return HELM_CONTEXT_PROJECTION_NAMES.map((region) => {
    const projection = envelope.projections[region];
    return projectionLine(region, {
      status: projection.status,
      owner: projection.authority.owner,
      source: projection.authority.source,
      observed: projection.authority.observed_at,
      expires: projection.authority.expires_at ?? "none",
      reason: projection.unavailable_reason ?? "none",
    });
  });
}
