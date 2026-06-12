import React from "react";
import {Box, Text} from "ink";
import {THEME} from "../theme";

type Props = {
  prompt: string;
  compact?: boolean;
};

export function Composer({prompt}: Props): React.ReactElement {
  // FACE-1 zen-pure: visible block cursor (inverse space — zero glyph-coverage
  // risk) + ghost placeholder when empty. Salience law: the composer must read
  // as "type here" on first paint — it carries the wave accent border, one of
  // the ≤2 sanctioned borders per frame (FACE-2 de-border law).
  return (
    <Box borderStyle="round" borderColor={THEME.wave} paddingX={1} flexDirection="column">
      <Box>
        <Text color={THEME.stone}>&gt; </Text>
        {prompt ? <Text color={THEME.foam}>{prompt}</Text> : null}
        <Text color={THEME.foam} inverse> </Text>
        {prompt ? null : (
          <Text color={THEME.stone} dimColor> Type a message · / commands · ? keys</Text>
        )}
      </Box>
    </Box>
  );
}
