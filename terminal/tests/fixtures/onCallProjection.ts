import {
  HELM_ON_CALL_SCHEMA,
  HELM_ROUTE_VERIFICATION_SCHEMA,
  HELM_SEAT_COUNT,
  HELM_SEAT_ORDER,
  type HelmAggregateState,
  type HelmRouteVerdict,
} from "../../src/onCallTruth";

type FixtureEvidence = {[key: string]: string | number | null};
export type FixtureSeat = {[key: string]: unknown} & {evidence: FixtureEvidence | null};
export type FixtureProjection = {[key: string]: unknown} & {
  state: HelmAggregateState;
  on_call_count: number | null;
  seats: FixtureSeat[];
  runtime_epoch: string;
};

type FixtureOptions = {
  state?: HelmAggregateState;
  verdicts?: readonly HelmRouteVerdict[];
  onCallCount?: number | null;
  runtimeEpoch?: string;
};

const EVALUATED_AT = "2026-08-09T12:00:00+09:00";

export function buildOnCallProjection(options: FixtureOptions = {}): FixtureProjection {
  const state = options.state ?? "ON_CALL";
  const verdicts = options.verdicts ?? HELM_SEAT_ORDER.map(() => "ON_CALL" as const);
  const runtimeEpoch = options.runtimeEpoch ?? "terminal-bridge:epoch-a";
  const serializedCount = options.onCallCount === undefined
    ? verdicts.filter((verdict) => verdict === "ON_CALL").length
    : options.onCallCount;
  return {
    schema_version: HELM_ON_CALL_SCHEMA,
    state,
    on_call_count: serializedCount,
    total: HELM_SEAT_COUNT,
    evaluated_at: EVALUATED_AT,
    runtime_epoch: runtimeEpoch,
    seats: HELM_SEAT_ORDER.map((seat, position) => {
      const verdict = verdicts[position] ?? "UNKNOWN";
      return {
        schema_version: HELM_ROUTE_VERIFICATION_SCHEMA,
        seat_id: seat.seatId,
        display_label: seat.displayLabel,
        logical_lineage: seat.logicalLineage,
        verdict,
        reason: verdict === "ON_CALL" ? "verified" : verdict.toLowerCase(),
        evaluated_at: EVALUATED_AT,
        runtime_epoch: runtimeEpoch,
        evidence: verdict === "UNKNOWN"
          ? null
          : {
              seat_id: seat.seatId,
              logical_lineage: seat.logicalLineage,
              requested_provider: `requested-${position}`,
              requested_model: `requested-model-${position}`,
              served_provider: `served-${position}`,
              served_model: `served-model-${position}`,
              observed_at: "2026-08-09T11:59:00+09:00",
              expires_at: "2026-08-10T11:59:00+09:00",
              age_seconds: 60,
              verifier_id: "dharma.route_verifier",
              verifier_version: "1.0.0",
              receipt_ref: `receipt-${position}`,
              receipt_sha256: String(position).padStart(64, "0"),
              runtime_epoch: runtimeEpoch,
            },
      };
    }),
  };
}

export function buildOnCallProjectionEvent(projection = buildOnCallProjection()): {[key: string]: unknown} {
  return {
    type: "helm.on_call_projection",
    request_id: "helm-request-1",
    projection,
  };
}
