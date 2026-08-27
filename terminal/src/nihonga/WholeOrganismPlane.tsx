import React from "react";
import {Box, Text} from "ink";

import {THEME} from "../theme";
import type {OrganismObservation, OrganismRegionView} from "./organismView";

type Props = {
  regions: OrganismRegionView[];
  activeFacet: string;
  compact?: boolean;
};

function observationPresentation(observation: OrganismObservation): {glyph: string; color: string} {
  switch (observation) {
    case "observed":
      return {glyph: "◉", color: THEME.wave};
    case "configured":
      return {glyph: "◇", color: THEME.parchment};
    case "unverified":
      return {glyph: "?", color: THEME.persimmon};
    case "held":
      return {glyph: "▣", color: THEME.persimmon};
    case "stale":
      return {glyph: "~", color: THEME.persimmon};
    default:
      return {glyph: "?", color: THEME.stone};
  }
}

export function WholeOrganismPlane({regions, activeFacet, compact = false}: Props): React.ReactElement {
  return (
    <Box flexDirection="column" flexGrow={1} overflow="hidden">
      <Text color={THEME.wave} bold>WHOLE ORGANISM / OWNER PROJECTIONS</Text>
      <Text color={THEME.stone}>six stable fields · no aggregate health score</Text>
      <Text color={THEME.ink}> </Text>
      {regions.map((region, index) => {
        const presentation = observationPresentation(region.observation);
        const indent = compact ? "" : index % 2 === 0 ? "" : "  ";
        return (
          <Box key={region.id} flexDirection="column">
            <Text wrap="truncate-end">
              <Text color={THEME.ink}>{indent}{region.ordinal} </Text>
              <Text color={presentation.color}>{presentation.glyph} </Text>
              <Text color={THEME.mist} bold>{region.label}</Text>
              <Text color={THEME.stone}> · {region.observation}</Text>
            </Text>
            {!compact ? <Text color={THEME.stone} wrap="truncate-end">{indent}   {region.detail}</Text> : null}
          </Box>
        );
      })}
      <Box flexGrow={1} />
      {!compact ? (
        <Box flexDirection="column" flexShrink={0}>
          <Text color={THEME.river}>{"─".repeat(34)}</Text>
          <Text wrap="truncate-end">
            <Text color={THEME.wave}>◉ observed</Text>
            <Text color={THEME.ink}>{"  "}</Text>
            <Text color={THEME.parchment}>◇ configured</Text>
            <Text color={THEME.ink}>{"  "}</Text>
            <Text color={THEME.stone}>? unknown</Text>
          </Text>
          <Text wrap="truncate-end">
            <Text color={THEME.persimmon}>~ stale</Text>
            <Text color={THEME.ink}>{"  "}</Text>
            <Text color={THEME.persimmon}>▣ held</Text>
            <Text color={THEME.ink}>{"  "}</Text>
            <Text color={THEME.persimmon}>░ SIM fixture only</Text>
          </Text>
        </Box>
      ) : null}
      <Text color={THEME.stone} wrap="truncate-end">focus · {activeFacet}</Text>
    </Box>
  );
}
