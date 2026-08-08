import React from "react";
import {Box, Text} from "ink";
import {THEME} from "../theme";

type Props = {
  lines: readonly string[];
  width?: number;
  height?: number;
};

// The guided tour as an isolated modal box (operator word 2026-06-16: "in its
// own isolated box and not inline text"). Full-screen, bordered, dismiss-hinted;
// the first tour line is the title, the rest are the body. Opened by /tour or ^G.
export function TourOverlay({lines, width, height}: Props): React.ReactElement {
  const [title, ...body] = lines.length > 0 ? lines : ["THE HELM — guided tour"];
  return (
    <Box height={height} width={width} flexDirection="column" alignItems="center" justifyContent="center">
      <Box
        flexDirection="column"
        borderStyle="round"
        borderColor={THEME.wave}
        paddingX={2}
        paddingY={1}
        width={width ? Math.min(width - 4, 92) : undefined}
      >
        <Text color={THEME.wave} bold>{title}</Text>
        <Text color={THEME.stone}> </Text>
        {body.map((line, index) => (
          <Text key={index} color={THEME.foam} wrap="truncate-end">{line}</Text>
        ))}
        <Text color={THEME.stone}> </Text>
        <Text color={THEME.stone}>Esc or any key to close · /tour reopens</Text>
      </Box>
    </Box>
  );
}
