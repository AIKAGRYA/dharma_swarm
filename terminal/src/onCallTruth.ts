export const HELM_ON_CALL_SCHEMA = "dharma.helm.on_call_projection.v1" as const;
export const HELM_ROUTE_VERIFICATION_SCHEMA = "dharma.helm.route_verification.v1" as const;
export const HELM_SEAT_COUNT = 7 as const;

export const HELM_SEAT_ORDER = [
  {seatId: "fable-5", displayLabel: "Fable 5", logicalLineage: "fable-5"},
  {seatId: "gpt-5.6", displayLabel: "GPT 5.6", logicalLineage: "openai-gpt-5.6"},
  {
    seatId: "grok-4.5-4.6-lineage",
    displayLabel: "Grok 4.5/4.6",
    logicalLineage: "xai-grok-4.5-4.6",
  },
  {seatId: "fugu-ultra", displayLabel: "Fugu Ultra", logicalLineage: "sakana-fugu-ultra"},
  {seatId: "kimi-k3", displayLabel: "Kimi K3", logicalLineage: "moonshot-kimi-k3"},
  {seatId: "opus-5.0", displayLabel: "Opus 5.0", logicalLineage: "anthropic-opus-5.0"},
  {seatId: "opus-4.8", displayLabel: "Opus 4.8", logicalLineage: "anthropic-opus-4.8"},
] as const;

export type HelmSeatId = (typeof HELM_SEAT_ORDER)[number]["seatId"];
export type HelmRouteVerdict = "ON_CALL" | "UNKNOWN" | "REJECTED" | "CLOCK_SKEW";
export type HelmAggregateState = "ON_CALL" | "LIVE_DEGRADED" | "CLOCK_SKEW" | "UNKNOWN";

export type HelmRouteEvidenceIdentity = Readonly<{
  seat_id: string | null;
  logical_lineage: string | null;
  requested_provider: string | null;
  requested_model: string | null;
  served_provider: string | null;
  served_model: string | null;
  observed_at: string | null;
  expires_at: string | null;
  age_seconds: number | null;
  verifier_id: string | null;
  verifier_version: string | null;
  receipt_ref: string | null;
  receipt_sha256: string | null;
  runtime_epoch: string | null;
}>;

export type HelmRouteVerification = Readonly<{
  schema_version: typeof HELM_ROUTE_VERIFICATION_SCHEMA;
  seat_id: HelmSeatId;
  display_label: string;
  logical_lineage: string;
  verdict: HelmRouteVerdict;
  reason: string;
  evaluated_at: string;
  runtime_epoch: string;
  evidence: HelmRouteEvidenceIdentity | null;
}>;

export type OrderedHelmRouteVerifications = readonly [
  HelmRouteVerification,
  HelmRouteVerification,
  HelmRouteVerification,
  HelmRouteVerification,
  HelmRouteVerification,
  HelmRouteVerification,
  HelmRouteVerification,
];

export type HelmOnCallProjection = Readonly<{
  schema_version: typeof HELM_ON_CALL_SCHEMA;
  state: HelmAggregateState;
  on_call_count: number | null;
  total: typeof HELM_SEAT_COUNT;
  seats: OrderedHelmRouteVerifications;
  evaluated_at: string;
  runtime_epoch: string;
}>;

export type OnCallTruthState =
  | Readonly<{
      kind: "unknown";
      runtimeEpoch: string | null;
    }>
  | Readonly<{
      kind: "authoritative";
      runtimeEpoch: string;
      projection: HelmOnCallProjection;
    }>;

export function unknownOnCallTruthState(runtimeEpoch: string | null = null): OnCallTruthState {
  return {kind: "unknown", runtimeEpoch};
}

export function onCallTruthStateWithProjection(
  current: OnCallTruthState,
  projection: HelmOnCallProjection,
): OnCallTruthState {
  if (current.runtimeEpoch !== null && current.runtimeEpoch !== projection.runtime_epoch) {
    return unknownOnCallTruthState(projection.runtime_epoch);
  }
  return {
    kind: "authoritative",
    runtimeEpoch: projection.runtime_epoch,
    projection,
  };
}
