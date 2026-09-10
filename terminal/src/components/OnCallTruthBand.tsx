import React from "react";
import {Box, Text} from "ink";

import {HELM_SEAT_ORDER, type HelmRouteVerdict, type OnCallTruthState} from "../onCallTruth";
import {THEME} from "../theme";

type Props = {
  truth: OnCallTruthState;
  compact?: boolean;
  width?: number;
  usableNowCount?: number;
  usableLaneTotal?: number;
};

const COMPACT_SEAT_LABELS = ["F5", "G56", "G46", "FU", "K3", "O50", "O48"] as const;

export function formatReceiptAge(ageSeconds: number | null): string {
  if (ageSeconds === null || !Number.isInteger(ageSeconds) || ageSeconds < 0) {
    return "?";
  }
  if (ageSeconds < 60) {
    return `${ageSeconds}s`;
  }
  if (ageSeconds < 3600) {
    return `${Math.floor(ageSeconds / 60)}m`;
  }
  if (ageSeconds < 86_400) {
    return `${Math.floor(ageSeconds / 3600)}h`;
  }
  return `${Math.floor(ageSeconds / 86_400)}d`;
}

function aggregatePresentation(truth: OnCallTruthState): {
  state: string;
  count: string;
  glyph: string;
  color: string;
} {
  if (truth.kind === "unknown" || truth.projection.state === "UNKNOWN") {
    return {state: "UNKNOWN", count: "?/7", glyph: "◌", color: THEME.stone};
  }
  const count = `${truth.projection.on_call_count}/${truth.projection.total}`;
  if (truth.projection.state === "ON_CALL") {
    return {state: "ON_CALL", count, glyph: "●", color: THEME.moss};
  }
  if (truth.projection.state === "CLOCK_SKEW") {
    return {state: "CLOCK_SKEW", count, glyph: "✖", color: THEME.vermilion};
  }
  return {state: "LIVE_DEGRADED", count, glyph: "⚠", color: THEME.persimmon};
}

function compactReason(reason: string): string {
  const normalized = reason.trim().toLowerCase();
  const known: {[key: string]: string} = {
    missing_evidence: "missing",
    identity_mismatch: "identity",
    runtime_epoch_mismatch: "epoch",
    future_timestamp: "skew",
    stale: "stale",
    replayed: "replay",
    synthetic: "synthetic",
  };
  return known[normalized] ?? normalized.replaceAll("_", "-").slice(0, 8);
}

function compactReceiptAge(ageSeconds: number | null): string {
  const formatted = formatReceiptAge(ageSeconds);
  return formatted.length <= 4 ? formatted : `${formatted.slice(0, 3)}…`;
}

function verdictPresentation(
  verdict: HelmRouteVerdict,
  reason: string,
  ageSeconds: number | null,
  compact: boolean,
): {
  text: string;
  color: string;
} {
  if (verdict === "ON_CALL") {
    return {text: `✓${compact ? compactReceiptAge(ageSeconds) : formatReceiptAge(ageSeconds)}`, color: THEME.moss};
  }
  if (verdict === "CLOCK_SKEW") {
    return {text: compact ? "✖" : "✖skew", color: THEME.vermilion};
  }
  if (verdict === "REJECTED") {
    return {text: compact ? "×" : `×${compactReason(reason)}`, color: THEME.persimmon};
  }
  const detail = compactReason(reason);
  return {
    text: compact || !detail || detail === "unknown" ? "?" : `?${detail}`,
    color: THEME.stone,
  };
}

export function OnCallTruthBand({truth, compact = false, width, usableNowCount, usableLaneTotal}: Props): React.ReactElement {
  const aggregate = aggregatePresentation(truth);
  const seats = truth.kind === "authoritative" ? truth.projection.seats : null;
  const explicitUsability = usableNowCount !== undefined && usableLaneTotal !== undefined;
  const presentations = HELM_SEAT_ORDER.map((_seat, index) => {
    const verification = seats?.[index];
    return verification
      ? verdictPresentation(verification.verdict, verification.reason, verification.evidence?.age_seconds ?? null, compact)
      : {text: "?", color: THEME.stone};
  });
  const fullSeatRowWidth = HELM_SEAT_ORDER.reduce(
    (width, seat, index) => width + (index > 0 ? 2 : 0) + seat.displayLabel.length + 1 + presentations[index].text.length,
    0,
  );
  // The non-compact shell begins at 120 columns. Preserve full labels while
  // they fit, then compact labels—not verdict evidence—so all seven truth
  // tokens remain addressable at that exact breakpoint.
  const compactSeatLabels = compact
    || fullSeatRowWidth > 116
    || (width !== undefined && fullSeatRowWidth > Math.max(1, width - 2));
  const compactAggregateState = aggregate.state === "LIVE_DEGRADED"
    ? "DEGRADED"
    : aggregate.state === "CLOCK_SKEW"
      ? "SKEW"
      : aggregate.state;
  const survivalAggregate = compact && width !== undefined && width < 80;
  return (
    <Box flexDirection="column" height={2} overflow="hidden">
      <Box paddingX={1} height={1} overflow="hidden">
        {survivalAggregate && explicitUsability ? (
          <Text wrap="truncate-end">
            <Text color={aggregate.color} bold={aggregate.state !== "UNKNOWN"}>{compactAggregateState} {aggregate.count}</Text>
            <Text color={THEME.ink}> · </Text>
            <Text color={THEME.stone}>usable {usableNowCount}/{usableLaneTotal} · verified {aggregate.count}</Text>
          </Text>
        ) : (
          <>
            <Text color={THEME.stone}>HELM </Text>
            <Text color={aggregate.color} bold={aggregate.state !== "UNKNOWN"}>
              {aggregate.glyph} {aggregate.state} {aggregate.count}
            </Text>
            {explicitUsability
              ? <><Text color={THEME.ink}>{" · "}</Text><Text color={THEME.stone}>Usable now {usableNowCount}/{usableLaneTotal} lanes · Identity verified {aggregate.count}</Text></>
              : <><Text color={THEME.ink}>{"  ·  "}</Text><Text color={THEME.stone}>Python verdict</Text></>}
          </>
        )}
      </Box>
      <Box paddingX={1} height={1} overflow="hidden">
        <Text wrap="truncate-end">
          {HELM_SEAT_ORDER.map((seat, index) => {
            const presentation = presentations[index];
            return (
              <React.Fragment key={seat.seatId}>
                {index > 0 ? <Text color={THEME.ink}>{compactSeatLabels ? " " : "  "}</Text> : null}
                <Text color={THEME.stone}>{compactSeatLabels ? COMPACT_SEAT_LABELS[index] : seat.displayLabel}</Text>
                <Text color={THEME.stone}> </Text>
                <Text color={presentation.color}>{presentation.text}</Text>
              </React.Fragment>
            );
          })}
        </Text>
      </Box>
    </Box>
  );
}
