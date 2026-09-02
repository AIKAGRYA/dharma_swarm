import type {DharmaBridge} from "./bridge.ts";
import type {SurfaceAuthorityState} from "./types.ts";

type RequestPayload = Record<string, unknown>;

export const SESSION_CATALOG_LIMIT = 12;

export function sendBackgroundRequest(
  bridge: DharmaBridge,
  type: string,
  payload?: RequestPayload,
): string {
  const backgroundCapable = bridge as DharmaBridge & {
    sendBackground?: (requestType: string, requestPayload?: RequestPayload) => string;
  };
  if (typeof backgroundCapable.sendBackground === "function") {
    return payload === undefined
      ? backgroundCapable.sendBackground(type)
      : backgroundCapable.sendBackground(type, payload);
  }
  return payload === undefined ? bridge.send(type) : bridge.send(type, payload);
}

export function requestLiveSnapshots(bridge: DharmaBridge, provider: string, model: string, strategy: string): void {
  sendBackgroundRequest(bridge, "helm.on_call.request");
  sendBackgroundRequest(bridge, "workspace.snapshot");
  sendBackgroundRequest(bridge, "runtime.snapshot");
  sendBackgroundRequest(bridge, "model.policy", {provider, model, strategy});
  sendBackgroundRequest(bridge, "agent.routes");
  sendBackgroundRequest(bridge, "evolution.surface");
}

export function requestSessionCatalog(bridge: DharmaBridge): void {
  sendBackgroundRequest(bridge, "session.catalog", {limit: SESSION_CATALOG_LIMIT});
}

export function requestPermissionHistory(bridge: DharmaBridge): void {
  sendBackgroundRequest(bridge, "permission.history", {limit: 50});
}

export function requestHelmContext(
  bridge: DharmaBridge,
  payload: RequestPayload,
): string {
  return sendBackgroundRequest(bridge, "helm.context.request", payload);
}

export function missingAuthoritativeSurfaces(
  authoritative: SurfaceAuthorityState,
): Array<keyof SurfaceAuthorityState> {
  return (Object.entries(authoritative) as Array<[keyof SurfaceAuthorityState, boolean]>)
    .filter(([, ready]) => !ready)
    .map(([surface]) => surface);
}

export function authoritativeResyncComplete(authoritative: SurfaceAuthorityState): boolean {
  return missingAuthoritativeSurfaces(authoritative).length === 0;
}

export function markAuthoritativeSurface(
  authoritative: SurfaceAuthorityState,
  surface: keyof SurfaceAuthorityState,
): SurfaceAuthorityState {
  return {
    ...authoritative,
    [surface]: true,
  };
}

export function authoritativeResyncStatus(authoritative: SurfaceAuthorityState): string {
  const remaining = missingAuthoritativeSurfaces(authoritative).length;
  if (remaining === 0) {
    return "operator state live";
  }
  return `resyncing ${remaining} surface${remaining === 1 ? "" : "s"}`;
}

export function requestAuthoritativeResync(
  bridge: DharmaBridge,
  provider: string,
  model: string,
  strategy: string,
  helmContextPayload?: RequestPayload,
): string | undefined {
  sendBackgroundRequest(bridge, "status");
  sendBackgroundRequest(bridge, "command.graph");
  sendBackgroundRequest(bridge, "command.registry");
  sendBackgroundRequest(bridge, "ontology.snapshot");
  requestSessionCatalog(bridge);
  requestPermissionHistory(bridge);
  requestLiveSnapshots(bridge, provider, model, strategy);
  return helmContextPayload === undefined
    ? undefined
    : requestHelmContext(bridge, helmContextPayload);
}

export function requestMissingAuthoritativeSurfaces(
  bridge: DharmaBridge,
  provider: string,
  model: string,
  strategy: string,
  authoritative: SurfaceAuthorityState,
): void {
  for (const surface of missingAuthoritativeSurfaces(authoritative)) {
    if (surface === "repo") {
      sendBackgroundRequest(bridge, "workspace.snapshot");
      continue;
    }
    if (surface === "control") {
      sendBackgroundRequest(bridge, "runtime.snapshot");
      continue;
    }
    if (surface === "sessions") {
      requestSessionCatalog(bridge);
      continue;
    }
    if (surface === "approvals") {
      requestPermissionHistory(bridge);
      continue;
    }
    if (surface === "models") {
      sendBackgroundRequest(bridge, "model.policy", {provider, model, strategy});
      continue;
    }
    if (surface === "agents") {
      sendBackgroundRequest(bridge, "agent.routes");
    }
  }
}
