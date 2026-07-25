import React from "react";
import {Box, Text} from "ink";
import {THEME} from "../theme";

type Props = {
  mode: string;
  routeLabel: string;
  bridgeStatus: string;
  routeState: string;
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
      return {glyph: "●", word: "bridge", color: THEME.moss};
    case "degraded":
      return {glyph: "⚠", word: "degraded", color: THEME.persimmon};
    case "offline":
      return {glyph: "○", word: "offline", color: THEME.persimmon};
    default:
      return {glyph: "◌", word: bridgeStatus, color: THEME.stone};
  }
}

function routeStateColor(routeState: string): string {
  if (routeState === "ready") {
    return THEME.moss;
  }
  if (routeState === "unverified" || routeState === "degraded" || routeState === "slow") {
    return THEME.persimmon;
  }
  return THEME.vermilion;
}

// FACE-2 command post status line (F-110 + F-164): EXACTLY one row at every
// size, and the SINGLE source of status truth per frame — mode, route, gate
// state, provider summary. offline / model name / ready never render anywhere
// else in the cockpit chrome. READY is suppressed while the bridge is down
// (a dead bridge cannot certify a ready route).
export function StatusFooter({mode, routeLabel, bridgeStatus, routeState, strategy, reason, compact = false}: Props): React.ReactElement {
  const gate = gateFor(bridgeStatus);
  return (
    <Box paddingX={1} height={1} overflow="hidden">
      <Text wrap="truncate-end">
        <Text color={THEME.stone}>{mode}</Text>
        <Text color={THEME.ink}>{"  ·  "}</Text>
        <Text color={THEME.stone}>route </Text>
        <Text color={THEME.parchment}>{routeLabel}</Text>
        <Text color={THEME.ink}>{"  ·  "}</Text>
        <Text color={gate.color}>
          {gate.glyph} {gate.word}
        </Text>
        {bridgeStatus === "connected" ? (
          <>
            <Text color={THEME.ink}>{"  ·  "}</Text>
            <Text color={routeStateColor(routeState)}>{routeState}</Text>
          </>
        ) : null}
        {!compact && strategy ? (
          <>
            <Text color={THEME.ink}>{"  ·  "}</Text>
            <Text color={THEME.stone}>{strategy}</Text>
          </>
        ) : null}
        {!compact && reason ? (
          <>
            <Text color={THEME.ink}>{"  ·  "}</Text>
            <Text color={THEME.stone}>{reason}</Text>
          </>
        ) : null}
      </Text>
    </Box>
  );
}
