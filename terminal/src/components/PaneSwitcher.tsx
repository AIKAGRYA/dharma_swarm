import React from "react";
import {Box, Text} from "ink";

import type {TabSpec} from "../types";
import {THEME} from "../theme";

type Props = {
  tabs: TabSpec[];
  selectedIndex: number;
};

export function paneSwitcherWindow(
  tabs: TabSpec[],
  selectedIndex: number,
  maximumRows = 10,
): {start: number; tabs: TabSpec[]} {
  const rowCount = Math.max(1, maximumRows);
  const clampedIndex = Math.min(Math.max(selectedIndex, 0), Math.max(tabs.length - 1, 0));
  const maximumStart = Math.max(tabs.length - rowCount, 0);
  const start = Math.max(0, Math.min(clampedIndex - Math.floor(rowCount / 2), maximumStart));
  return {start, tabs: tabs.slice(start, start + rowCount)};
}

export function PaneSwitcher({tabs, selectedIndex}: Props): React.ReactElement {
  const window = paneSwitcherWindow(tabs, selectedIndex);
  const end = window.start + window.tabs.length;
  return (
    <Box flexGrow={1} flexDirection="column" borderStyle="round" borderColor={THEME.ridge} paddingX={1}>
      <Text color={THEME.parchment} bold>Pane Switcher</Text>
      <Text color={THEME.stone} wrap="truncate-end">
        rows {window.tabs.length > 0 ? `${window.start + 1}-${end}` : "0"} of {tabs.length} | Enter jump | Esc close | j/k or arrows move
      </Text>
      <Text color={THEME.stone}> </Text>
      {window.tabs.map((tab, index) => {
        const actualIndex = window.start + index;
        const active = actualIndex === selectedIndex;
        return (
          <Text key={tab.id} color={active ? THEME.parchment : THEME.foam} bold={active} wrap="truncate-end">
            {active ? "▶" : "•"} {actualIndex + 1}. {tab.title} · {tab.kind}{tab.closable ? " · closable" : ""}
          </Text>
        );
      })}
    </Box>
  );
}
