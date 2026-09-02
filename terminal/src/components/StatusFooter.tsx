import React from "react";
import {Box, Text} from "ink";
import {routeStatePresentation} from "../routePresentation.ts";
import {THEME} from "../theme";
import type {BridgeStatus, RouteState} from "../types.ts";

type Props = {
  mode: string;
  routeLabel: string;
  bridgeStatus: BridgeStatus;
  routeState: RouteState;
  strategy?: string;
  reason?: string;
  compact?: boolean;
};

type Gate = {glyph: string; word: string; color: string};

// Gate semantics per design truth directive #2: expected hermetic-offline is
// a warning (persimmon ○), NEVER vermilion — vermilion is reserved for
// genuine danger. Glyph + word always travel together (color never sole signal).
function gateFor(bridgeStatus: string): Gate {
  switch (bridgeStatus) {
    case "connected":
      return {glyph: "●", word: "bridge", color: THEME.wave};
    case "degraded":
      return {glyph: "⚠", word: "degraded", color: THEME.persimmon};
    case "offline":
      return {glyph: "○", word: "offline", color: THEME.persimmon};
    default:
      return {glyph: "◌", word: bridgeStatus, color: THEME.stone};
  }
}

// The right box never shrinks so the typed reason survives narrow widths; the
// cap keeps a long reason from starving the route label out of the left box.
// 20 keeps the canonical typed marks (e.g. exact_model_unproven) whole while a
// 100-column full row still shows the whole route id.
const REASON_CAP = 20;

export function capReason(reason: string | undefined, _compact: boolean): string | undefined {
  const trimmed = reason?.trim();
  if (!trimmed) {
    return undefined;
  }
  return trimmed.length <= REASON_CAP ? trimmed : `${trimmed.slice(0, REASON_CAP - 1)}…`;
}

// FACE-2 command post status line (F-110 + F-164): EXACTLY one row at every
// size, and the SINGLE source of status truth per frame — mode, route, gate
// state, provider summary. offline / model name / ready never render anywhere
// else in the cockpit chrome. READY is suppressed while the bridge is down
// (a dead bridge cannot certify a ready route).
export function StatusFooter({mode, routeLabel, bridgeStatus, routeState, strategy, reason, compact = false}: Props): React.ReactElement {
  const gate = gateFor(bridgeStatus);
  const route = routeStatePresentation(routeState);
  const shownReason = capReason(reason, compact);
  return (
    <Box paddingX={1} height={1} overflow="hidden">
      <Box flexGrow={1} flexShrink={1} overflow="hidden">
        <Text wrap="truncate-end">
          <Text color={THEME.stone}>{mode}</Text>
          <Text color={THEME.ink}>{"  ·  "}</Text>
          <Text color={THEME.stone}>route </Text>
          <Text color={THEME.parchment}>{routeLabel}</Text>
          {!compact && strategy ? (
            <>
              <Text color={THEME.ink}>{"  ·  "}</Text>
              <Text color={THEME.stone}>{strategy}</Text>
            </>
          ) : null}
        </Text>
      </Box>
      <Box flexShrink={0}>
        <Text>
          {compact && shownReason ? <Text color={THEME.stone}>{shownReason} </Text> : null}
          <Text color={THEME.ink}>{compact ? "" : "  ·  "}</Text>
          <Text color={gate.color}>{gate.glyph} {gate.word}</Text>
          {bridgeStatus === "connected" ? (
            <>
              <Text color={THEME.ink}>{compact ? " " : "  ·  "}</Text>
              <Text color={route.color}>{route.glyph} {route.word}</Text>
            </>
          ) : null}
          {!compact && shownReason ? (
            <>
              <Text color={THEME.ink}>{"  ·  "}</Text>
              <Text color={THEME.stone}>{shownReason}</Text>
            </>
          ) : null}
        </Text>
      </Box>
    </Box>
  );
}
