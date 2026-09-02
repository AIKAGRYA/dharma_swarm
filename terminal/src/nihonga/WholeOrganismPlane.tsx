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
      <Box flexShrink={0}><Text color={THEME.wave} bold>WHOLE ORGANISM / OWNER PROJECTIONS</Text></Box>
      {!compact ? <Box flexShrink={0}><Text color={THEME.stone} wrap="truncate-end">twelve owner-stamped fields · no boolean promotion</Text></Box> : null}
      {!compact ? <Box flexShrink={0}><Text color={THEME.ink}> </Text></Box> : null}
      {projectionLines.map((line, index) => (
        <Box key={`${index}-${line}`} flexShrink={0}>
          <Text color={lineColor(line)} wrap="truncate-end">{String(index + 1).padStart(2, "0")} {line}</Text>
        </Box>
      ))}
      {!compact ? <Box flexShrink={0}><Text color={THEME.stone} wrap="truncate-end">focus · {activeFacet}</Text></Box> : null}
    </Box>
  );
}
