import React from "react";
import {Box, Text} from "ink";
import {THEME} from "../theme";

type Props = {
  prompt: string;
  compact?: boolean;
};

export function Composer({prompt}: Props): React.ReactElement {
  return (
    <Box borderStyle="round" borderColor={THEME.indigo} paddingX={1} flexDirection="column">
      <Box>
        <Text color={THEME.stone}>&gt; </Text>
        <Text color={THEME.foam}>{prompt || " "}</Text>
      </Box>
    </Box>
  );
}
