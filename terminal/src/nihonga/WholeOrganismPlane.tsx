import React from "react";
import {Box, Text} from "ink";

import {THEME} from "../theme";

type Props = {
  projectionLines: string[];
  activeFacet: string;
  compact?: boolean;
};

function lineColor(line: string): string {
  if (line.includes("status=observed")) return THEME.wave;
  if (line.includes("status=configured")) return THEME.parchment;
  if (line.includes("status=held") || line.includes("status=stale")) return THEME.persimmon;
  return THEME.stone;
}

export function WholeOrganismPlane({projectionLines, activeFacet, compact = false}: Props): React.ReactElement {
  return (
    <Box flexDirection="column" flexGrow={1} overflow="hidden">
      <Text color={THEME.wave} bold flexShrink={0}>WHOLE ORGANISM / OWNER PROJECTIONS</Text>
      {!compact ? <Text color={THEME.stone} flexShrink={0} wrap="truncate-end">twelve owner-stamped fields · no boolean promotion</Text> : null}
      {!compact ? <Text color={THEME.ink} flexShrink={0}> </Text> : null}
      {projectionLines.map((line, index) => (
        <Text key={`${index}-${line}`} color={lineColor(line)} wrap="truncate-end" flexShrink={0}>
          {String(index + 1).padStart(2, "0")} {line}
        </Text>
      ))}
      {!compact ? <Text color={THEME.stone} wrap="truncate-end" flexShrink={0}>focus · {activeFacet}</Text> : null}
    </Box>
  );
}
