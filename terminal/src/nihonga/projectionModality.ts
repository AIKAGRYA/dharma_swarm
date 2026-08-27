import type {BridgeStatus} from "../types.ts";

export type OwnerProjectionModality = "observed" | "stale" | "unknown";

type ProjectionEvidence = {
  bridgeStatus: BridgeStatus;
  authorityObserved: boolean;
  hasRetainedProjection: boolean;
};

/**
 * Derive display modality without promoting retained rows across a transport
 * break. A loose event row has no current-epoch provenance here, so it cannot
 * promote a retained surface above stale before the owner snapshot arrives.
 */
export function ownerProjectionModality(evidence: ProjectionEvidence): OwnerProjectionModality {
  if (evidence.bridgeStatus !== "connected") {
    return evidence.authorityObserved || evidence.hasRetainedProjection ? "stale" : "unknown";
  }
  if (evidence.authorityObserved) {
    return "observed";
  }
  return evidence.hasRetainedProjection ? "stale" : "unknown";
}
