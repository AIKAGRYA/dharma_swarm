import type {OnCallTruthState} from "../onCallTruth";
import type {ActiveTurnState, BridgeStatus, RoutePolicyState, SurfaceAuthorityState} from "../types";

export type OrganismRegionId = "purpose" | "core" | "intelligence" | "evolution" | "outward" | "delivery";
export type OrganismObservation = "observed" | "configured" | "unverified" | "held" | "stale" | "unknown";

export type OrganismRegionView = {
  id: OrganismRegionId;
  ordinal: string;
  label: string;
  observation: OrganismObservation;
  detail: string;
};

type OrganismProjectionInput = {
  bridgeStatus: BridgeStatus;
  activeTurn: ActiveTurnState;
  routePolicy: RoutePolicyState;
  onCallTruth: OnCallTruthState;
  authority: SurfaceAuthorityState;
};

function onCallDetail(truth: OnCallTruthState): string {
  if (truth.kind !== "authoritative") {
    return "bench ?/7 · awaiting Python projection";
  }
  return `bench ${truth.projection.on_call_count}/${truth.projection.total} · ${truth.projection.state.toLowerCase()}`;
}

export function projectWholeOrganism(input: OrganismProjectionInput): OrganismRegionView[] {
  const runtimeObserved = input.authority.control;
  const workspaceObserved = input.authority.repo;
  const routeObservation: OrganismObservation =
    input.routePolicy.routeState === "ready"
      ? input.bridgeStatus === "connected" ? "configured" : "stale"
      : input.routePolicy.selectable
        ? "unverified"
        : "held";
  const currentOwnerObservation = (observed: boolean): OrganismObservation => {
    if (!observed) return "unknown";
    return input.bridgeStatus === "connected" ? "observed" : "stale";
  };

  return [
    {
      id: "purpose",
      ordinal: "01",
      label: "PURPOSE / GOVERNANCE",
      observation: "unknown",
      detail: "canon and mission remain contextual owners",
    },
    {
      id: "core",
      ordinal: "02",
      label: "CORE ORGANISM",
      observation: currentOwnerObservation(runtimeObserved),
      detail: `${input.bridgeStatus} transport · turn ${input.activeTurn.phase}`,
    },
    {
      id: "intelligence",
      ordinal: "03",
      label: "INTELLIGENCE MESH",
      observation: routeObservation,
      detail: `${input.routePolicy.provider}:${input.routePolicy.model} · ${onCallDetail(input.onCallTruth)}`,
    },
    {
      id: "evolution",
      ordinal: "04",
      label: "EVOLUTION / RESEARCH",
      observation: "unknown",
      detail: "owner records not yet bound to Helm projection",
    },
    {
      id: "outward",
      ordinal: "05",
      label: "OUTWARD ORGANS",
      observation: input.authority.agents
        ? input.bridgeStatus === "connected" ? "configured" : "stale"
        : "unknown",
      detail: input.authority.agents ? "route catalog observed · contact unproved" : "swarm and A2A not observed",
    },
    {
      id: "delivery",
      ordinal: "06",
      label: "DELIVERY SUBSTRATE",
      observation: currentOwnerObservation(workspaceObserved),
      detail: workspaceObserved ? "workspace projection observed" : "workspace projection awaiting resync",
    },
  ];
}
