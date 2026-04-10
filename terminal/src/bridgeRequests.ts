import { DharmaBridge } from "./bridge.ts";
import type { SurfaceAuthorityState } from "./types.ts";

const DEFAULT_SESSION_CATALOG_LIMIT = 12;
const DEFAULT_PERMISSION_HISTORY_LIMIT = 50;
const DEFAULT_SESSION_TRANSCRIPT_LIMIT = 40;

function missingAuthoritativeSurfaces(authoritative: SurfaceAuthorityState): string[] {
  return Object.entries(authoritative)
    .filter(([, ready]) => !ready)
    .map(([surface]) => surface);
}

export function requestLiveSnapshots(bridge: DharmaBridge, provider: string, model: string, strategy: string): void {
  bridge.send("workspace.snapshot");
  bridge.send("runtime.snapshot");
  bridge.send("model.policy", {provider, model, strategy});
  bridge.send("agent.routes");
  bridge.send("routing.manifest", {provider, model, strategy});
  bridge.send("evolution.surface");
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
): void {
  bridge.send("status");
  bridge.send("command.graph");
  bridge.send("command.registry");
  bridge.send("ontology.snapshot");
  requestSessionCatalog(bridge);
  requestPermissionHistory(bridge);
  requestLiveSnapshots(bridge, provider, model, strategy);
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
      bridge.send("workspace.snapshot");
      continue;
    }
    if (surface === "control") {
      bridge.send("runtime.snapshot");
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
      bridge.send("model.policy", {provider, model, strategy});
      continue;
    }
    if (surface === "agents") {
      bridge.send("agent.routes");
      bridge.send("routing.manifest", {provider, model, strategy});
    }
  }
}

export function requestSessionCatalog(bridge: DharmaBridge, limit = DEFAULT_SESSION_CATALOG_LIMIT): void {
  bridge.send("session.catalog", {limit});
}

export function requestPermissionHistory(bridge: DharmaBridge, limit = DEFAULT_PERMISSION_HISTORY_LIMIT): void {
  bridge.send("permission.history", {limit});
}

export function requestSessionDetail(
  bridge: DharmaBridge,
  sessionId: string | undefined,
  transcriptLimit = DEFAULT_SESSION_TRANSCRIPT_LIMIT,
): void {
  if (!sessionId) {
    return;
  }
  bridge.send("session.detail", {session_id: sessionId, transcript_limit: transcriptLimit});
}
