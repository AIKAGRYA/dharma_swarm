import {describe, expect, test} from "bun:test";

import {HELM_SEAT_ORDER} from "../src/onCallTruth";
import {
  decodeHelmOnCallProjection,
  helmOnCallProjectionFromEvent,
} from "../src/protocol/onCallTruth";
import {
  buildOnCallProjection,
  buildOnCallProjectionEvent,
} from "./fixtures/onCallProjection";

describe("Helm OnCall projection decoder", () => {
  test("accepts the exact Python-owned 7/7 projection without deriving ages or verdicts", () => {
    const decoded = decodeHelmOnCallProjection(buildOnCallProjection());

    expect(decoded?.state).toBe("ON_CALL");
    expect(decoded?.on_call_count).toBe(7);
    expect(decoded?.seats.map((seat) => seat.seat_id)).toEqual(HELM_SEAT_ORDER.map((seat) => seat.seatId));
    expect(decoded?.seats[0].evidence?.age_seconds).toBe(60);
  });

  test("accepts degraded, clock-skew, and authoritative unknown projections verbatim", () => {
    const degraded = decodeHelmOnCallProjection(buildOnCallProjection({
      state: "LIVE_DEGRADED",
      verdicts: ["ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "REJECTED"],
    }));
    expect(degraded?.state).toBe("LIVE_DEGRADED");
    expect(degraded?.on_call_count).toBe(6);

    const skewPayload = buildOnCallProjection({
      state: "CLOCK_SKEW",
      verdicts: ["ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "CLOCK_SKEW"],
    });
    if (skewPayload.seats[6]?.evidence) {
      skewPayload.seats[6].evidence.age_seconds = null;
      skewPayload.seats[6].evidence.observed_at = "2099-01-01T00:00:00Z";
    }
    const skew = decodeHelmOnCallProjection(skewPayload);
    expect(skew?.state).toBe("CLOCK_SKEW");
    expect(skew?.seats[6].evidence?.age_seconds).toBeNull();

    const unknown = decodeHelmOnCallProjection(buildOnCallProjection({
      state: "UNKNOWN",
      verdicts: HELM_SEAT_ORDER.map(() => "UNKNOWN"),
      onCallCount: null,
    }));
    expect(unknown?.state).toBe("UNKNOWN");
    expect(unknown?.on_call_count).toBeNull();
  });

  test("requires the exact correlated bridge envelope", () => {
    expect(helmOnCallProjectionFromEvent(buildOnCallProjectionEvent())?.state).toBe("ON_CALL");
    expect(helmOnCallProjectionFromEvent({...buildOnCallProjectionEvent(), request_id: ""})).toBeUndefined();
    expect(helmOnCallProjectionFromEvent({...buildOnCallProjectionEvent(), type: "route.receipt"})).toBeUndefined();
    expect(helmOnCallProjectionFromEvent({...buildOnCallProjectionEvent(), extra: true})).toBeUndefined();
  });

  test("rejects wrong schema, total, count, enum, and extra projection fields", () => {
    const wrongSchema = buildOnCallProjection();
    wrongSchema.schema_version = "dharma.helm.on_call_projection.v0";
    expect(decodeHelmOnCallProjection(wrongSchema)).toBeUndefined();

    const wrongTotal = buildOnCallProjection();
    wrongTotal.total = 8;
    expect(decodeHelmOnCallProjection(wrongTotal)).toBeUndefined();

    const wrongCount = buildOnCallProjection();
    wrongCount.on_call_count = 6;
    expect(decodeHelmOnCallProjection(wrongCount)).toBeUndefined();

    const unknownEnum = buildOnCallProjection();
    unknownEnum.state = "READY";
    expect(decodeHelmOnCallProjection(unknownEnum)).toBeUndefined();

    const extraField = buildOnCallProjection();
    extraField.source = "terminal";
    expect(decodeHelmOnCallProjection(extraField)).toBeUndefined();
  });

  test("requires every UNKNOWN aggregate row to remain UNKNOWN", () => {
    for (const forgedVerdict of ["REJECTED", "ON_CALL", "CLOCK_SKEW"] as const) {
      const forged = buildOnCallProjection({
        state: "UNKNOWN",
        verdicts: [forgedVerdict, "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"],
        onCallCount: null,
      });
      expect(decodeHelmOnCallProjection(forged)).toBeUndefined();
    }
  });

  test("rejects missing, duplicate, or reordered fixed seats", () => {
    const missing = buildOnCallProjection();
    missing.seats.pop();
    expect(decodeHelmOnCallProjection(missing)).toBeUndefined();

    const duplicate = buildOnCallProjection();
    duplicate.seats[1] = structuredClone(duplicate.seats[0]);
    expect(decodeHelmOnCallProjection(duplicate)).toBeUndefined();

    const reordered = buildOnCallProjection();
    [reordered.seats[0], reordered.seats[1]] = [reordered.seats[1]!, reordered.seats[0]!];
    expect(decodeHelmOnCallProjection(reordered)).toBeUndefined();
  });

  test("rejects seat schema, context-epoch, and evidence-age malformation", () => {
    const seatSchema = buildOnCallProjection();
    seatSchema.seats[0]!.schema_version = "dharma.helm.route_verification.v0";
    expect(decodeHelmOnCallProjection(seatSchema)).toBeUndefined();

    const wrongEpoch = buildOnCallProjection();
    wrongEpoch.seats[0]!.runtime_epoch = "terminal-bridge:old";
    expect(decodeHelmOnCallProjection(wrongEpoch)).toBeUndefined();

    const wrongEvaluationTime = buildOnCallProjection();
    wrongEvaluationTime.seats[0]!.evaluated_at = "2026-08-09T12:00:01+09:00";
    expect(decodeHelmOnCallProjection(wrongEvaluationTime)).toBeUndefined();

    for (const invalidAge of [-1, 1.5, "60"]) {
      const invalid = buildOnCallProjection();
      if (invalid.seats[0]?.evidence) {
        invalid.seats[0].evidence.age_seconds = invalidAge;
      }
      expect(decodeHelmOnCallProjection(invalid)).toBeUndefined();
    }

    for (const state of ["LIVE_DEGRADED", "CLOCK_SKEW"] as const) {
      const verdict = state === "CLOCK_SKEW" ? "CLOCK_SKEW" : "REJECTED";
      const mismatchedEvidenceEpoch = buildOnCallProjection({
        state,
        verdicts: ["ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", "ON_CALL", verdict],
      });
      mismatchedEvidenceEpoch.seats[6]!.evidence!.runtime_epoch = "terminal-bridge:old";
      expect(decodeHelmOnCallProjection(mismatchedEvidenceEpoch)).toBeUndefined();
    }
  });

  test("rejects forged ON_CALL rows without exact positive evidence", () => {
    const mutations: Array<(projection: ReturnType<typeof buildOnCallProjection>) => void> = [
      (projection) => { projection.seats[0]!.evidence = null; },
      (projection) => { projection.seats[0]!.reason = "provider_success"; },
      (projection) => { projection.seats[0]!.evidence!.seat_id = "gpt-5.6"; },
      (projection) => { projection.seats[0]!.evidence!.logical_lineage = "wrong-lineage"; },
      (projection) => { projection.seats[0]!.evidence!.runtime_epoch = "terminal-bridge:old"; },
      (projection) => { projection.seats[0]!.evidence!.requested_provider = ""; },
      (projection) => { projection.seats[0]!.evidence!.requested_model = ""; },
      (projection) => { projection.seats[0]!.evidence!.served_provider = ""; },
      (projection) => { projection.seats[0]!.evidence!.served_model = ""; },
      (projection) => { projection.seats[0]!.evidence!.observed_at = ""; },
      (projection) => { projection.seats[0]!.evidence!.expires_at = ""; },
      (projection) => { projection.seats[0]!.evidence!.age_seconds = null; },
      (projection) => { projection.seats[0]!.evidence!.verifier_id = "caller"; },
      (projection) => { projection.seats[0]!.evidence!.verifier_version = "9.9.9"; },
      (projection) => { projection.seats[0]!.evidence!.receipt_ref = ""; },
      (projection) => { projection.seats[0]!.evidence!.receipt_sha256 = "not-a-sha256"; },
    ];
    for (const mutate of mutations) {
      const forged = buildOnCallProjection();
      mutate(forged);
      expect(decodeHelmOnCallProjection(forged)).toBeUndefined();
    }
  });
});
