import React from "react";
import {Box, Text} from "ink";

import type {BridgeStatus, RouteState} from "../types";
import {routeStatePresentation} from "../routePresentation.ts";
import {THEME} from "../theme";
import {HELM_PLACES, type HelmPlace, type HelmViewportProfile, placeLabel} from "./shellModel";

type RoomBandProps = {
  workspace: string;
  place: HelmPlace;
  profile: HelmViewportProfile;
  routeLabel: string;
  routeState: RouteState;
  bridgeStatus: BridgeStatus;
  width: number;
  height: number;
};

function bridgeGlyph(status: BridgeStatus): {glyph: string; color: string} {
  if (status === "connected") return {glyph: "●", color: THEME.wave};
  if (status === "degraded") return {glyph: "⚠", color: THEME.persimmon};
  if (status === "booting") return {glyph: "◌", color: THEME.parchment};
  return {glyph: "○", color: THEME.ink};
}

export function routeStateForBridge(status: BridgeStatus, routeState: RouteState): RouteState | "stale" {
  return status !== "connected" && routeState === "ready" ? "stale" : routeState;
}

export function NihongaRoomBand(props: RoomBandProps): React.ReactElement {
  const bridge = bridgeGlyph(props.bridgeStatus);
  const compact = props.profile === "compact" || props.profile === "survival";
  const displayedRouteState = routeStateForBridge(props.bridgeStatus, props.routeState);
  const route = routeStatePresentation(displayedRouteState);
  if (compact) {
    return (
      <Box flexDirection="column" flexShrink={0}>
        <Box paddingX={1} justifyContent="space-between">
          <Text wrap="truncate-end">
            <Text color={THEME.wave} bold>◆ DHARMA HELM</Text>
            <Text color={THEME.ink}>{" / "}</Text>
            <Text color={THEME.foam} bold>{placeLabel(props.place).toUpperCase()}</Text>
            <Text color={THEME.ink}>{" · "}</Text>
            <Text color={THEME.stone}>{props.workspace}</Text>
          </Text>
          <Text color={bridge.color}>{bridge.glyph} {props.bridgeStatus.toUpperCase()}</Text>
        </Box>
        <Box paddingX={1}>
          <Text wrap="truncate-end">
            <Text color={THEME.stone}>route </Text>
            <Text color={THEME.parchment}>{props.routeLabel}</Text>
            <Text color={THEME.ink}>{" · "}</Text>
            <Text color={route.color}>{route.glyph} {route.word}</Text>
            <Text color={THEME.ink}>{" · "}</Text>
            <Text color={THEME.stone}>PROJECTION</Text>
          </Text>
        </Box>
      </Box>
    );
  }
  return (
    <Box flexDirection="column" flexShrink={0}>
      <Box paddingX={1} justifyContent="space-between">
        <Text wrap="truncate-end">
          <Text color={THEME.wave} bold>◆ DHARMA HELM</Text>
          <Text color={THEME.ink}>{"  /  "}</Text>
          <Text color={THEME.foam} bold>{placeLabel(props.place).toUpperCase()}</Text>
          <Text color={THEME.ink}>{"  ·  "}</Text>
          <Text color={THEME.stone}>{props.workspace}</Text>
        </Text>
        {!compact ? <Text color={THEME.stone}>{props.width}×{props.height} · {props.profile}</Text> : null}
      </Box>
      <Box paddingX={1}>
        <Text wrap="truncate-end">
          <Text color={bridge.color}>{bridge.glyph} {props.bridgeStatus}</Text>
          <Text color={THEME.ink}>{"  ·  "}</Text>
          <Text color={THEME.parchment}>{props.routeLabel}</Text>
          <Text color={route.color}> [{route.glyph} {route.word}]</Text>
          <Text color={THEME.ink}>{"  ·  PROJECTION · owner truth preserved"}</Text>
        </Text>
      </Box>
      <Text color={THEME.river}>{"─".repeat(Math.max(props.width, 1))}</Text>
    </Box>
  );
}

export function PlaceCompass({active, compact = false}: {active: HelmPlace; compact?: boolean}): React.ReactElement {
  return (
    <Box paddingX={1} flexShrink={0}>
      <Text wrap="truncate-end">
        {HELM_PLACES.map((place, index) => (
          <React.Fragment key={place}>
            {index > 0 ? <Text color={THEME.ink}>{compact ? "  " : "   "}</Text> : null}
            <Text color={place === active ? THEME.wave : THEME.stone} bold={place === active}>
              {place === active ? "◆ " : "· "}{compact ? placeLabel(place).slice(0, 4) : placeLabel(place)}
            </Text>
          </React.Fragment>
        ))}
      </Text>
    </Box>
  );
}

export function BoundaryLine({turnPhase}: {turnPhase: "idle" | "running" | "cancelling"}): React.ReactElement {
  const turnColor = turnPhase === "idle" ? THEME.stone : turnPhase === "running" ? THEME.crest : THEME.persimmon;
  return (
    <Box paddingX={1} flexShrink={0} justifyContent="space-between">
      <Text wrap="truncate-end">
        <Text color={THEME.persimmon} bold>BOUNDARY</Text>
        <Text color={THEME.stone}> · chat no-tools · narration authority NONE · effects owner-gated</Text>
      </Text>
      <Text color={turnColor}>{turnPhase}</Text>
    </Box>
  );
}
