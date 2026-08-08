import React from "react";
import {Box, Text} from "ink";

// The Navigator Copilot surface — a persistent companion that steers the Helm
// for the operator and narrates as it goes. v1: a bottom strip; ^N will cycle
// position (strip / right column / corner). Mounted as flexShrink={0} chrome so
// it never breaks the F-163 fill law (content stays on-screen).
export type NavPosition = "strip" | "column" | "corner";

export interface NavigatorStripProps {
  lines: readonly string[]; // the copilot's recent narration / replies (newest last)
  busy?: boolean; // a turn is in flight
  width?: number;
  position?: NavPosition;
}

const HINT = 'Ask me to fly the Helm — "show the swarm", "open runtime", "back to zen". Prefix @ to steer.';

export function NavigatorStrip({lines, busy = false, width, position = "strip"}: NavigatorStripProps) {
  const window = position === "corner" ? 1 : 2;
  const recent = lines.slice(-window);
  const head = busy ? "◆ Navigator · steering…" : "◆ Navigator";
  return (
    <Box flexShrink={0} flexDirection="column" paddingX={1} width={width}>
      <Text color="magenta">
        {head} <Text dimColor>· @ to steer · ^N move</Text>
      </Text>
      {recent.length === 0 ? (
        <Text dimColor wrap="truncate-end">{HINT}</Text>
      ) : (
        recent.map((line, i) => (
          <Text key={i} dimColor wrap="truncate-end">
            {line}
          </Text>
        ))
      )}
    </Box>
  );
}
